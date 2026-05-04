"""Booking -> ticket bridge.

This is the place where the floor_plan blueprint writes to sail.db.
It validates the booking payload, fetches room metadata from
floor_plan.db, then opens a transaction against sail.db for ticket
inserts / state changes / audit rows.
"""
import re
from datetime import date as _date, time as _time
from flask import session

from database import get_db, log_audit
from .db import db
from .models import BookableRoom, BookingReturn


# "Booking request: {room.label} on {YYYY-MM-DD}" — match for parsing
TITLE_RE = re.compile(r"^Booking request:\s+(.+)\s+on\s+(\d{4}-\d{2}-\d{2})$")
ALLOWED_RETURN_STATES = {"returned_good", "damaged", "missing"}
RETURN_STATE_TO_ASSET_STATUS = {
    "returned_good": "available",
    "damaged": "damaged",
    "missing": "missing",
}
APPROVER_ROLES = ("admin", "manager")


PURPOSE_MIN = 10
PURPOSE_MAX = 500

# Lab operating hours (24h). Bookings outside this window are rejected.
LAB_OPEN = _time(7, 0)
LAB_CLOSE = _time(16, 0)
SLOT_MINUTES = 15  # bookings align to 15-min slots (informational; client enforces step)


class BookingError(ValueError):
    """Raised on validation failure. Message is safe to surface to users."""


def _next_ticket_number(conn):
    """Replica of routes.tickets.next_ticket_number — keeps blueprint isolated."""
    row = conn.execute(
        "SELECT ticket_number FROM tickets ORDER BY id DESC LIMIT 1"
    ).fetchone()
    num = int(row["ticket_number"].split("-")[1]) + 1 if row else 1
    return f"TKT-{num:04d}"


def _validate(payload):
    """Return a normalised payload dict or raise BookingError."""
    if not isinstance(payload, dict):
        raise BookingError("Body must be a JSON object.")

    required = ("zone_key", "date", "start_time", "end_time", "attendees", "purpose")
    missing = [k for k in required if k not in payload]
    if missing:
        raise BookingError(f"Missing fields: {missing}")

    try:
        d = _date.fromisoformat(payload["date"])
    except (TypeError, ValueError):
        raise BookingError("Date must be YYYY-MM-DD.")
    if d < _date.today():
        raise BookingError("Date must be today or later.")

    try:
        start = _time.fromisoformat(payload["start_time"])
        end = _time.fromisoformat(payload["end_time"])
    except (TypeError, ValueError):
        raise BookingError("start_time / end_time must be HH:MM.")
    if end <= start:
        raise BookingError("end_time must be after start_time.")
    if start < LAB_OPEN or end > LAB_CLOSE:
        raise BookingError(
            f"Bookings must fall within lab hours "
            f"({LAB_OPEN.strftime('%H:%M')}–{LAB_CLOSE.strftime('%H:%M')})."
        )

    try:
        attendees = int(payload["attendees"])
    except (TypeError, ValueError):
        raise BookingError("attendees must be an integer.")
    if attendees < 1:
        raise BookingError("attendees must be >= 1.")

    purpose = (payload.get("purpose") or "").strip()
    if not (PURPOSE_MIN <= len(purpose) <= PURPOSE_MAX):
        raise BookingError(
            f"purpose must be {PURPOSE_MIN}-{PURPOSE_MAX} characters."
        )

    # New shape: equipment_requests = [{model_id, quantity}, ...]
    # Old shape kept for backwards compat: asset_ids = [int, ...]
    equipment_requests = payload.get("equipment_requests") or []
    if not isinstance(equipment_requests, list):
        raise BookingError("equipment_requests must be a list.")
    cleaned_requests = []
    for i, item in enumerate(equipment_requests):
        if not isinstance(item, dict):
            raise BookingError(f"equipment_requests[{i}] must be an object.")
        try:
            mid = int(item["model_id"])
            qty = int(item["quantity"])
        except (KeyError, TypeError, ValueError):
            raise BookingError(
                f"equipment_requests[{i}] must have integer model_id and quantity."
            )
        if qty < 1:
            raise BookingError(f"equipment_requests[{i}].quantity must be >= 1.")
        cleaned_requests.append({"model_id": mid, "quantity": qty})

    asset_ids = payload.get("asset_ids") or []
    if not isinstance(asset_ids, list):
        raise BookingError("asset_ids must be a list.")
    if not all(isinstance(x, int) for x in asset_ids):
        raise BookingError("asset_ids must be integers.")

    return {
        "zone_key": payload["zone_key"],
        "date": d.isoformat(),
        "start_time": start.strftime("%H:%M"),
        "end_time": end.strftime("%H:%M"),
        "attendees": attendees,
        "purpose": purpose,
        "asset_ids": asset_ids,
        "equipment_requests": cleaned_requests,
    }


def _build_description(room_label, location_code, p, asset_rows, equipment_rows=None):
    lines = [
        f"Booking request for {room_label} ({location_code}).",
        "",
        f"Date: {p['date']}",
        f"Time: {p['start_time']} - {p['end_time']}",
        f"Attendees: {p['attendees']}",
        "Purpose:",
        f"  {p['purpose']}",
    ]
    if equipment_rows:
        lines.append("")
        lines.append("Equipment requested:")
        for er in equipment_rows:
            line = f"  - {er['quantity']} x {er['name']}"
            if er.get('brand'):
                line += f" ({er['brand']})"
            line += f" [model_id={er['model_id']}]"
            lines.append(line)
    if asset_rows:
        lines.append("")
        lines.append("Assets requested:")
        for a in asset_rows:
            lines.append(f"  - {a['asset_tag']} - {a['model_name']} ({a['condition']})")
    return "\n".join(lines)


def _parse_equipment_requests_from_description(description):
    """Return [{model_id, quantity, name}, ...] parsed from the description.

    Format written by _build_description:
        Equipment requested:
          - 2 x Dell Monitor (Dell) [model_id=5]
          - 1 x PC [model_id=8]
    """
    if not description or "Equipment requested:" not in description:
        return []
    block = description.split("Equipment requested:", 1)[1]
    # Stop the parse at the next double-newline / next heading
    block = block.split("\n\nAssets ")[0]
    out = []
    for line in block.splitlines():
        m = re.match(r"\s*-\s+(\d+)\s+x\s+(.+?)\s*\[model_id=(\d+)\]\s*$", line)
        if m:
            out.append({
                "quantity": int(m.group(1)),
                "name": m.group(2).strip(),
                "model_id": int(m.group(3)),
            })
    return out


def _check_equipment_capacity(conn, requested_models, date_str, start_time, end_time):
    """For each {model_id, quantity} in requested_models, ensure there is
    enough free inventory of that model during the time window — i.e.
    total_inventory >= already_committed_to_overlapping_bookings + new_demand.

    Raises BookingError with a clear message on first failure.
    """
    if not requested_models:
        return

    # Find every booking ticket for this date that overlaps the window and is
    # still active (open / in_progress / waiting). Use a generic prefix LIKE
    # to grab all booking-request tickets, then narrow on date and overlap.
    title_prefix = f"Booking request:%on {date_str}"
    rows = conn.execute(
        """SELECT id, ticket_number, description FROM tickets
           WHERE title LIKE ?
             AND type = 'new_request'
             AND status IN ('open', 'in_progress', 'waiting')""",
        (title_prefix,),
    ).fetchall()

    # Tally committed quantity per model_id from overlapping bookings
    committed = {}  # model_id -> qty
    for r in rows:
        ex_start, ex_end = _parse_times_from_description(r["description"])
        if not (ex_start and ex_end):
            continue
        if not _times_overlap(start_time, end_time, ex_start, ex_end):
            continue
        for er in _parse_equipment_requests_from_description(r["description"]):
            committed[er["model_id"]] = committed.get(er["model_id"], 0) + er["quantity"]

    # For each requested model, ensure capacity. Pull total counts in one query.
    model_ids = list({rm["model_id"] for rm in requested_models})
    placeholders = ",".join("?" * len(model_ids))
    total = {
        r["equipment_model_id"]: r["n"]
        for r in conn.execute(
            f"""SELECT a.equipment_model_id, COUNT(*) AS n
                FROM assets a
                WHERE a.equipment_model_id IN ({placeholders})
                  AND a.status != 'missing'
                GROUP BY a.equipment_model_id""",
            model_ids,
        ).fetchall()
    }
    names = {
        r["id"]: r["name"]
        for r in conn.execute(
            f"SELECT id, name FROM equipment_models WHERE id IN ({placeholders})",
            model_ids,
        ).fetchall()
    }

    for rm in requested_models:
        mid, qty = rm["model_id"], rm["quantity"]
        if mid not in names:
            raise BookingError(f"Unknown equipment model id {mid}.")
        avail = total.get(mid, 0) - committed.get(mid, 0)
        if avail < qty:
            raise BookingError(
                f"Not enough '{names[mid]}' available for that time window — "
                f"{max(avail, 0)} free, you asked for {qty}. Pick a different "
                f"slot or fewer units."
            )


def _times_overlap(s1, e1, s2, e2):
    """Strict overlap on [s,e) HH:MM strings — adjacent (e==s) is allowed."""
    return s1 < e2 and s2 < e1


def _check_no_overlap(conn, room_label, date_str, start_time, end_time,
                       exclude_ticket_id=None):
    """Raise BookingError if another open/approved booking on the same room
    + date overlaps the given time window."""
    rows = conn.execute(
        """SELECT id, ticket_number, description FROM tickets
           WHERE title = ?
             AND type = 'new_request'
             AND status IN ('open', 'in_progress', 'waiting')""",
        (f"Booking request: {room_label} on {date_str}",),
    ).fetchall()
    for r in rows:
        if exclude_ticket_id and r["id"] == exclude_ticket_id:
            continue
        ex_start, ex_end = _parse_times_from_description(r["description"])
        if not (ex_start and ex_end):
            continue
        if _times_overlap(start_time, end_time, ex_start, ex_end):
            raise BookingError(
                f"Time conflict: {r['ticket_number']} already covers "
                f"{ex_start}–{ex_end} on {date_str}. "
                f"Pick a different time."
            )


def create_booking_ticket(payload):
    """Validate + insert a ticket. Returns {ticket_id, ticket_number}.

    Raises BookingError (caller maps to 400/404).
    """
    p = _validate(payload)

    room = BookableRoom.query.filter_by(zone_key=p["zone_key"], is_active=1).first()
    if room is None:
        raise BookingError(f"No bookable room for zone '{p['zone_key']}'.")

    user_id = session.get("user_id")
    if not user_id:
        raise BookingError("Login required.")

    asset_dicts = []
    submitter = None
    with get_db() as conn:
        loc = conn.execute(
            "SELECT id, code, label FROM locations WHERE id = ?",
            (room.sail_location_id,),
        ).fetchone()
        if loc is None:
            raise BookingError("Room is not configured.")

        # Reject overlap with any existing open/approved booking on this
        # room+date so two people can not double-book the same window.
        _check_no_overlap(conn, room.label, p["date"], p["start_time"], p["end_time"])

        # Equipment-level capacity: for each requested {model_id, qty},
        # ensure inventory minus already-committed-to-overlapping-bookings
        # is enough. Same equipment cannot be promised to two overlapping
        # bookings.
        _check_equipment_capacity(
            conn, p["equipment_requests"], p["date"],
            p["start_time"], p["end_time"],
        )

        # Verify each requested asset exists. We deliberately do NOT
        # require the asset to live in the room — the user describes what
        # they need; ops physically arranges the room when they approve.
        if p["asset_ids"]:
            placeholders = ",".join("?" * len(p["asset_ids"]))
            asset_rows = conn.execute(
                f"""SELECT a.id, a.asset_tag, a.condition, em.name AS model_name
                    FROM assets a JOIN equipment_models em ON em.id = a.equipment_model_id
                    WHERE a.id IN ({placeholders})""",
                p["asset_ids"],
            ).fetchall()
            if len(asset_rows) != len(p["asset_ids"]):
                raise BookingError("One or more assets do not exist.")
        else:
            asset_rows = []

        # Resolve equipment_requests model_ids to {model_id, name, brand, quantity}
        equipment_rows = []
        if p["equipment_requests"]:
            mids = [er["model_id"] for er in p["equipment_requests"]]
            placeholders_m = ",".join("?" * len(mids))
            model_lookup = {
                r["id"]: dict(r)
                for r in conn.execute(
                    f"SELECT id, name, brand FROM equipment_models WHERE id IN ({placeholders_m})",
                    mids,
                ).fetchall()
            }
            for er in p["equipment_requests"]:
                m = model_lookup.get(er["model_id"])
                if m:
                    equipment_rows.append({
                        "model_id": m["id"],
                        "name": m["name"],
                        "brand": m["brand"],
                        "quantity": er["quantity"],
                    })

        ticket_number = _next_ticket_number(conn)
        title = f"Booking request: {room.label} on {p['date']}"
        description = _build_description(
            room.label, loc["code"], p, asset_rows, equipment_rows
        )

        cursor = conn.execute(
            """INSERT INTO tickets
               (ticket_number, type, priority, status, submitted_by, title, description)
               VALUES (?, 'new_request', 'medium', 'open', ?, ?, ?)""",
            (ticket_number, user_id, title, description),
        )
        ticket_id = cursor.lastrowid
        log_audit(conn, "tickets", ticket_id, "create", changed_by=user_id)

        # Materialise asset details + submitter contact for the email helpers
        # while we still have the connection open.
        asset_dicts = [dict(r) for r in asset_rows]
        sub_row = conn.execute(
            "SELECT id, name, email FROM employees WHERE id = ?", (user_id,)
        ).fetchone()
        submitter = dict(sub_row) if sub_row else None

    # Emails go out *after* commit so a mail-server hiccup never rolls back the
    # ticket. send_email() is non-blocking (background thread).
    _send_booking_emails(
        ticket_id=ticket_id,
        ticket_number=ticket_number,
        title=title,
        description=description,
        room_label=room.label,
        payload=p,
        asset_dicts=asset_dicts,
        submitter=submitter,
    )

    return {"ticket_id": ticket_id, "ticket_number": ticket_number}


def _check_role(allowed):
    """Look up the current session user; raise BookingError if role not allowed.

    Returns (user_id, role).
    """
    user_id = session.get("user_id")
    if not user_id:
        raise BookingError("Login required.")
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, role FROM employees WHERE id = ? AND is_active = 1",
            (user_id,),
        ).fetchone()
    if row is None:
        raise BookingError("User not found.")
    if row["role"] not in allowed:
        raise BookingError(f"Forbidden: requires role {sorted(allowed)}.")
    return row["id"], row["role"]


def _parse_booking_title(title):
    """Return (room_label, date_str) or (None, None) if not a booking title."""
    if not title:
        return None, None
    m = TITLE_RE.match(title)
    return (m.group(1), m.group(2)) if m else (None, None)


def _parse_assigned_assets_from_description(description):
    """Return [SAIL-XXX, ...] from the 'Assets assigned:' block written by
    approve_booking. Distinct from _parse_assets_from_description (which
    reads the original user-requested 'Assets requested:' block)."""
    if not description or "Assets assigned:" not in description:
        return []
    block = description.split("Assets assigned:", 1)[1]
    return re.findall(r"-\s+(SAIL-\S+)\b", block)


def _parse_times_from_description(description):
    """Best-effort extraction of 'HH:MM - HH:MM' from the description block."""
    if not description:
        return None, None
    m = re.search(r"Time:\s*(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})", description)
    return (m.group(1), m.group(2)) if m else (None, None)


def _parse_assets_from_description(description):
    """Return list of asset_tags mentioned in the 'Assets requested' block.

    Description format written by _build_description:
        Assets requested:
          - SAIL-0001 - Display (good)
          - SAIL-0002 - Display (good)
    """
    if not description or "Assets requested:" not in description:
        return []
    block = description.split("Assets requested:", 1)[1]
    return re.findall(r"-\s+(SAIL-\S+)\s+-\s+", block)


def approve_booking(ticket_id):
    """Flip a booking ticket from 'open' to 'in_progress'.

    Permission: admin or manager. Returns the resolved booking metadata
    (room_label, date, submitter, ...) for the caller to use in emails.
    """
    actor_id, actor_role = _check_role(APPROVER_ROLES)

    with get_db() as conn:
        row = conn.execute(
            """SELECT t.id, t.ticket_number, t.title, t.description, t.status,
                      t.type, t.submitted_by,
                      e.name AS submitter_name, e.email AS submitter_email
               FROM tickets t
               LEFT JOIN employees e ON e.id = t.submitted_by
               WHERE t.id = ?""",
            (ticket_id,),
        ).fetchone()
        if row is None:
            raise BookingError(f"Ticket {ticket_id} not found.")

        room_label, date_str = _parse_booking_title(row["title"])
        if not room_label:
            raise BookingError(f"Ticket {ticket_id} is not a booking ticket.")
        if row["status"] != "open":
            raise BookingError(
                f"Ticket {row['ticket_number']} is already {row['status']}; "
                f"cannot approve."
            )

        conn.execute(
            "UPDATE tickets SET status='in_progress', assigned_to = ? WHERE id = ?",
            (actor_id, ticket_id),
        )
        log_audit(
            conn, "tickets", ticket_id, "update",
            field_name="status", old_value="open", new_value="in_progress",
            changed_by=actor_id,
        )

        # Assign every requested asset to the submitter for the duration of
        # the booking: status -> assigned, assigned_to -> submitted_by.
        # Each transition is audited so the history shows when the asset
        # moved into / out of the user's hands.
        assigned = []

        # Path 1: legacy asset-tag requests
        asset_tags = _parse_assets_from_description(row["description"])
        # Path 2: new equipment_request shape (model_id + quantity).
        # Auto-allocate the first N available assets per model that are
        # not already assigned to another booking. Ops can change the
        # picks later via a manual reassign flow if needed.
        equipment_requests = _parse_equipment_requests_from_description(row["description"])
        for er in equipment_requests:
            picks = conn.execute(
                """SELECT asset_tag FROM assets
                   WHERE equipment_model_id = ?
                     AND status = 'available'
                     AND assigned_to IS NULL
                   ORDER BY id LIMIT ?""",
                (er["model_id"], er["quantity"]),
            ).fetchall()
            asset_tags.extend(p["asset_tag"] for p in picks)

        if asset_tags:
            placeholders = ",".join("?" * len(asset_tags))
            asset_rows = conn.execute(
                f"""SELECT id, asset_tag, status, assigned_to
                    FROM assets WHERE asset_tag IN ({placeholders})""",
                asset_tags,
            ).fetchall()
            for a in asset_rows:
                if a["status"] != "assigned":
                    conn.execute(
                        "UPDATE assets SET status='assigned', updated_at=datetime('now') WHERE id = ?",
                        (a["id"],),
                    )
                    log_audit(
                        conn, "assets", a["id"], "update",
                        field_name="status",
                        old_value=a["status"], new_value="assigned",
                        changed_by=actor_id,
                    )
                if a["assigned_to"] != row["submitted_by"]:
                    conn.execute(
                        "UPDATE assets SET assigned_to = ?, updated_at=datetime('now') WHERE id = ?",
                        (row["submitted_by"], a["id"]),
                    )
                    log_audit(
                        conn, "assets", a["id"], "update",
                        field_name="assigned_to",
                        old_value=str(a["assigned_to"]) if a["assigned_to"] is not None else None,
                        new_value=str(row["submitted_by"]),
                        changed_by=actor_id,
                    )
                assigned.append({"id": a["id"], "asset_tag": a["asset_tag"]})

        # Persist the actual allocation to the ticket description so the close
        # modal (and any later viewer) can see which specific assets were
        # picked. Append a single 'Assets assigned:' block — never duplicate.
        if assigned:
            new_desc = row["description"] or ""
            if "Assets assigned:" not in new_desc:
                lines = ["", "Assets assigned:"]
                for a in assigned:
                    lines.append(f"  - {a['asset_tag']}")
                new_desc = new_desc.rstrip() + "\n" + "\n".join(lines) + "\n"
                conn.execute(
                    "UPDATE tickets SET description = ? WHERE id = ?",
                    (new_desc, ticket_id),
                )

        start_time, end_time = _parse_times_from_description(row["description"])
        result = {
            "ticket_id": ticket_id,
            "ticket_number": row["ticket_number"],
            "room_label": room_label,
            "date": date_str,
            "start_time": start_time,
            "end_time": end_time,
            "assets_assigned": assigned,
            "submitter": {
                "id": row["submitted_by"],
                "name": row["submitter_name"],
                "email": row["submitter_email"],
            },
        }

    # Email after commit
    try:
        from email_service import notify_booking_approved
        notify_booking_approved(
            ticket={"id": ticket_id, "ticket_number": result["ticket_number"]},
            submitter=result["submitter"],
            room_label=result["room_label"],
            date=result["date"],
            start_time=result["start_time"] or "",
            end_time=result["end_time"] or "",
        )
    except Exception:  # pragma: no cover
        pass

    return result


def close_booking(ticket_id, payload):
    """Close a booking and verify asset returns.

    `payload` shape: {"returns": [{"asset_id": int, "state": str, "notes": str?}, ...]}.
    Permission: admin or manager.

    Each return:
      - state must be one of returned_good / damaged / missing
      - asset_id must reference an existing asset
    Asset.status is updated based on state mapping; each change is audited.
    The ticket is moved to status='closed' with closed_at = now.
    BookingReturn rows are written in floor_plan.db (post-commit, to keep
    the sail.db transaction tight; orphans on rare failure are acceptable
    in v1 and visible via audit_log).
    """
    actor_id, actor_role = _check_role(APPROVER_ROLES)

    if not isinstance(payload, dict):
        raise BookingError("Body must be a JSON object.")
    raw_returns = payload.get("returns") or []
    if not isinstance(raw_returns, list):
        raise BookingError("returns must be a list.")

    # Validate shape early
    cleaned = []
    for i, item in enumerate(raw_returns):
        if not isinstance(item, dict):
            raise BookingError(f"returns[{i}] must be an object.")
        if "asset_id" not in item or not isinstance(item["asset_id"], int):
            raise BookingError(f"returns[{i}].asset_id must be an integer.")
        state = item.get("state")
        if state not in ALLOWED_RETURN_STATES:
            raise BookingError(
                f"returns[{i}].state must be one of {sorted(ALLOWED_RETURN_STATES)}."
            )
        notes = (item.get("notes") or "").strip()
        cleaned.append({"asset_id": item["asset_id"], "state": state, "notes": notes})

    asset_ids = [r["asset_id"] for r in cleaned]
    enriched_returns = []
    booking_meta = {}
    with get_db() as conn:
        # Ticket lookup + status check
        row = conn.execute(
            """SELECT t.id, t.ticket_number, t.title, t.description, t.status,
                      t.submitted_by,
                      e.name AS submitter_name, e.email AS submitter_email
               FROM tickets t
               LEFT JOIN employees e ON e.id = t.submitted_by
               WHERE t.id = ?""",
            (ticket_id,),
        ).fetchone()
        if row is None:
            raise BookingError(f"Ticket {ticket_id} not found.")
        room_label, date_str = _parse_booking_title(row["title"])
        if not room_label:
            raise BookingError(f"Ticket {ticket_id} is not a booking ticket.")
        if row["status"] not in ("open", "in_progress"):
            raise BookingError(
                f"Ticket {row['ticket_number']} is {row['status']}; cannot close."
            )

        # Resolve every return.asset_id to a real asset
        if asset_ids:
            placeholders = ",".join("?" * len(asset_ids))
            asset_lookup = {
                r["id"]: dict(r)
                for r in conn.execute(
                    f"""SELECT a.id, a.asset_tag, a.status, a.assigned_to,
                               em.name AS model_name
                        FROM assets a
                        JOIN equipment_models em ON em.id = a.equipment_model_id
                        WHERE a.id IN ({placeholders})""",
                    asset_ids,
                ).fetchall()
            }
            missing = [aid for aid in asset_ids if aid not in asset_lookup]
            if missing:
                raise BookingError(f"Unknown asset ids: {sorted(missing)}.")
        else:
            asset_lookup = {}

        # Apply asset status updates + clear assignment + audit each one
        for r in cleaned:
            asset = asset_lookup[r["asset_id"]]
            new_status = RETURN_STATE_TO_ASSET_STATUS[r["state"]]
            if asset["status"] != new_status:
                conn.execute(
                    "UPDATE assets SET status = ?, updated_at = datetime('now') WHERE id = ?",
                    (new_status, r["asset_id"]),
                )
                log_audit(
                    conn, "assets", r["asset_id"], "update",
                    field_name="status",
                    old_value=asset["status"], new_value=new_status,
                    changed_by=actor_id,
                )
            # Whatever the return state, the asset is no longer with the user.
            if asset.get("assigned_to") is not None:
                conn.execute(
                    "UPDATE assets SET assigned_to = NULL, updated_at = datetime('now') WHERE id = ?",
                    (r["asset_id"],),
                )
                log_audit(
                    conn, "assets", r["asset_id"], "update",
                    field_name="assigned_to",
                    old_value=str(asset["assigned_to"]),
                    new_value=None,
                    changed_by=actor_id,
                )
            enriched_returns.append({
                "asset_id": r["asset_id"],
                "asset_tag": asset["asset_tag"],
                "model_name": asset["model_name"],
                "state": r["state"],
                "notes": r["notes"],
            })

        # Close the ticket
        conn.execute(
            "UPDATE tickets SET status='closed', closed_at = datetime('now') WHERE id = ?",
            (ticket_id,),
        )
        log_audit(
            conn, "tickets", ticket_id, "update",
            field_name="status", old_value=row["status"], new_value="closed",
            changed_by=actor_id,
        )

        booking_meta = {
            "ticket_number": row["ticket_number"],
            "room_label": room_label,
            "date": date_str,
            "submitter": {
                "id": row["submitted_by"],
                "name": row["submitter_name"],
                "email": row["submitter_email"],
            },
        }

    # After sail.db commit, persist the verification rows in floor_plan.db.
    # Failure here logs but does not roll back the closure (ops can re-add
    # the verification record manually; ticket already closed).
    try:
        for r in enriched_returns:
            db.session.add(BookingReturn(
                booking_ticket_id=ticket_id,
                asset_id=r["asset_id"],
                asset_tag=r["asset_tag"],
                model_name=r["model_name"] or "",
                state=r["state"],
                notes=r["notes"],
                verified_by=actor_id,
            ))
        db.session.commit()
    except Exception:  # pragma: no cover
        db.session.rollback()

    # Notification email to the requester (and admin CC if any issue)
    try:
        from email_service import notify_booking_closed
        notify_booking_closed(
            ticket={"id": ticket_id, "ticket_number": booking_meta["ticket_number"]},
            submitter=booking_meta["submitter"],
            room_label=booking_meta["room_label"],
            date=booking_meta["date"],
            returns=enriched_returns,
        )
    except Exception:  # pragma: no cover
        pass

    return {
        "ticket_id": ticket_id,
        "ticket_number": booking_meta["ticket_number"],
        "returns": enriched_returns,
    }


def _send_booking_emails(*, ticket_id, ticket_number, title, description,
                         room_label, payload, asset_dicts, submitter):
    """Fire the two emails that go out on a successful booking submit:
    - Ops team gets the existing notify_ticket_created (admin queue alert).
    - Requester gets notify_booking_submitted with the booking details.
    Both are best-effort; failures are logged inside email_service.send_email.
    """
    try:
        from email_service import notify_ticket_created, notify_booking_submitted
    except Exception:  # pragma: no cover — only fires if email_service breaks
        return

    ticket_dict = {
        "id": ticket_id,
        "ticket_number": ticket_number,
        "type": "new_request",
        "priority": "medium",
        "title": title,
        "description": description,
    }
    if submitter:
        notify_ticket_created(ticket_dict, submitter)
        notify_booking_submitted(
            ticket_dict, submitter,
            room_label=room_label,
            date=payload["date"],
            start_time=payload["start_time"],
            end_time=payload["end_time"],
            attendees=payload["attendees"],
            purpose=payload["purpose"],
            asset_rows=asset_dicts,
        )
