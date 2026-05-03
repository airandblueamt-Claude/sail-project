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
    }


def _build_description(room_label, location_code, p, asset_rows):
    lines = [
        f"Booking request for {room_label} ({location_code}).",
        "",
        f"Date: {p['date']}",
        f"Time: {p['start_time']} - {p['end_time']}",
        f"Attendees: {p['attendees']}",
        "Purpose:",
        f"  {p['purpose']}",
    ]
    if asset_rows:
        lines.append("")
        lines.append("Assets requested:")
        for a in asset_rows:
            lines.append(f"  - {a['asset_tag']} - {a['model_name']} ({a['condition']})")
    return "\n".join(lines)


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

        if p["asset_ids"]:
            placeholders = ",".join("?" * len(p["asset_ids"]))
            asset_rows = conn.execute(
                f"""SELECT a.id, a.asset_tag, a.condition, em.name AS model_name
                    FROM assets a JOIN equipment_models em ON em.id = a.equipment_model_id
                    WHERE a.id IN ({placeholders}) AND a.location_id = ?""",
                (*p["asset_ids"], room.sail_location_id),
            ).fetchall()
            if len(asset_rows) != len(p["asset_ids"]):
                raise BookingError("One or more assets are not in this room.")
        else:
            asset_rows = []

        ticket_number = _next_ticket_number(conn)
        title = f"Booking request: {room.label} on {p['date']}"
        description = _build_description(room.label, loc["code"], p, asset_rows)

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

        start_time, end_time = _parse_times_from_description(row["description"])
        result = {
            "ticket_id": ticket_id,
            "ticket_number": row["ticket_number"],
            "room_label": room_label,
            "date": date_str,
            "start_time": start_time,
            "end_time": end_time,
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
                    f"""SELECT a.id, a.asset_tag, a.status, em.name AS model_name
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

        # Apply asset status updates + audit each one
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
