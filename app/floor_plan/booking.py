"""Booking -> ticket bridge.

This is the ONE place where the floor_plan blueprint writes to sail.db.
It validates the booking payload, fetches the room metadata from
floor_plan.db, then opens a transaction against sail.db to insert the
ticket and audit row in a single commit.
"""
from datetime import date as _date, time as _time
from flask import session

from database import get_db, log_audit
from .models import BookableRoom


PURPOSE_MIN = 10
PURPOSE_MAX = 500


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

    return {"ticket_id": ticket_id, "ticket_number": ticket_number}
