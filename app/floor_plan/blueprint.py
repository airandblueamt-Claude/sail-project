"""Floor plan blueprint — page route + JSON API for pins."""

from flask import (
    Blueprint, render_template, request, jsonify,
    abort, current_app
)
from sqlalchemy.exc import SQLAlchemyError

from .db import db
from .models import Pin, BookableRoom
from .booking import create_booking_ticket, approve_booking, close_booking, BookingError


floor_plan_bp = Blueprint(
    "floor_plan",
    __name__,
    template_folder="templates",
    static_folder="static",
    # static_url_path defaults to /static; combined with the url_prefix at register
    # time (e.g. /floor-plan), assets serve at /floor-plan/static/floor_plan/...
)


# ---------- Page route ----------

@floor_plan_bp.route("/", methods=["GET"])
def index():
    """Serve the interactive floor plan page."""
    return render_template("floor_plan/index.html")


@floor_plan_bp.route("/calendar", methods=["GET"])
def calendar_page():
    """Weekly calendar view of bookings per room.

    Visible to every authenticated user; the booking action redirects to
    the floor plan with prefilled query params so the existing modal
    handles the actual submit.
    """
    return render_template("floor_plan/calendar.html")


@floor_plan_bp.route("/bookings", methods=["GET"])
def bookings_page():
    """Bookings page — visible to every authenticated user.

    Regular employees see only their own bookings (read-only).
    Admin and manager see every booking and get the Approve / Close buttons.
    """
    from flask import g
    user = getattr(g, "user", None)
    is_admin = bool(user and user.get("role") in ("admin", "manager"))
    return render_template("floor_plan/bookings.html", is_admin=is_admin)


# ---------- API: pins ----------

@floor_plan_bp.route("/api/pins", methods=["GET"])
def api_pins_list():
    """Return all pins as a JSON array, ordered by id."""
    pins = Pin.query.order_by(Pin.id).all()
    return jsonify([p.to_dict() for p in pins])


@floor_plan_bp.route("/api/pins", methods=["PUT"])
def api_pins_replace():
    """Bulk replace all pins. Body is a JSON array of pin objects.

    Used by the JS auto-save when the user is editing in authoring mode.
    Wraps the whole replace in a transaction so a partial failure rolls back.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, list):
        abort(400, description="Body must be a JSON array of pin objects.")

    # Validate shape early so we don't half-write
    for item in data:
        _validate_pin_dict(item)

    try:
        Pin.query.delete()
        for item in data:
            db.session.add(Pin.from_dict(item))
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.exception("Pin bulk replace failed")
        abort(500, description=str(e))

    return jsonify({"saved": len(data)}), 200


@floor_plan_bp.route("/api/pins", methods=["POST"])
def api_pins_create():
    """Create a single pin. Used for fine-grained API integration; the JS
    frontend currently uses the bulk PUT route instead."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description="Body must be a JSON object.")
    _validate_pin_dict(data)

    if db.session.get(Pin, data["id"]) is not None:
        abort(409, description=f"Pin {data['id']} already exists.")

    pin = Pin.from_dict(data)
    db.session.add(pin)
    db.session.commit()
    return jsonify(pin.to_dict()), 201


@floor_plan_bp.route("/api/pins/<pin_id>", methods=["PATCH"])
def api_pin_update(pin_id):
    """Patch a single pin by id."""
    pin = db.session.get(Pin, pin_id)
    if pin is None:
        abort(404)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description="Body must be a JSON object.")

    pin.update_from_dict(data)
    db.session.commit()
    return jsonify(pin.to_dict()), 200


@floor_plan_bp.route("/api/pins/<pin_id>", methods=["DELETE"])
def api_pin_delete(pin_id):
    """Delete a single pin by id."""
    pin = db.session.get(Pin, pin_id)
    if pin is None:
        abort(404)
    db.session.delete(pin)
    db.session.commit()
    return "", 204


# ---------- Validation ----------

def _validate_pin_dict(data: dict) -> None:
    """Validate the JSON shape coming from the JS frontend."""
    if not isinstance(data, dict):
        abort(400, description="Pin must be a JSON object.")

    required = {"id", "name", "x", "y"}
    missing = required - set(data)
    if missing:
        abort(400, description=f"Pin missing required keys: {sorted(missing)}")

    if not isinstance(data["id"], str) or not data["id"]:
        abort(400, description="Pin id must be a non-empty string.")

    for coord in ("x", "y"):
        v = data[coord]
        if not isinstance(v, (int, float)):
            abort(400, description=f"Pin {coord} must be a number.")
        if not (0 <= v <= 100):
            abort(400, description=f"Pin {coord} must be between 0 and 100.")

    assets = data.get("assets", [])
    if assets and not isinstance(assets, list):
        abort(400, description="Pin assets must be a list.")
    for a in assets:
        if not (isinstance(a, list) and len(a) == 2):
            abort(400, description="Each asset must be a [name, count] pair.")


# ---------- API: bookable rooms ----------

@floor_plan_bp.route("/api/bookable-rooms", methods=["GET"])
def api_bookable_rooms():
    """List the rooms that can be booked from the plan view."""
    rooms = BookableRoom.query.filter_by(is_active=1).order_by(BookableRoom.label).all()
    return jsonify([r.to_dict() for r in rooms])


def _query_assets_at_location(location_id):
    """Late-import wrapper around the sail.db assets-by-location query.

    The late `from database import get_db` is required so the test fixture's
    monkeypatch on database.DB_PATH lands first.
    """
    from database import get_db
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT a.id, a.asset_tag, a.status, a.condition,
                   em.name AS model_name, em.brand
            FROM assets a
            JOIN equipment_models em ON em.id = a.equipment_model_id
            WHERE a.location_id = ?
            ORDER BY em.name, a.asset_tag
            """,
            (location_id,),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "asset_tag": r["asset_tag"],
            "status": r["status"],
            "condition": r["condition"],
            "model_name": r["model_name"],
            "brand": r["brand"],
        }
        for r in rows
    ]


@floor_plan_bp.route("/api/rooms/<zone_key>/assets", methods=["GET"])
def api_room_assets(zone_key):
    """List assets in a *bookable* room (legacy shape: bare list, 404 if
    the zone is not in bookable_rooms). Used by the booking modal.
    """
    room = BookableRoom.query.filter_by(zone_key=zone_key, is_active=1).first()
    if room is None:
        abort(404, description=f"No bookable room for zone '{zone_key}'.")
    return jsonify(_query_assets_at_location(room.sail_location_id))


@floor_plan_bp.route("/api/equipment-catalog", methods=["GET"])
def api_equipment_catalog():
    """List equipment models with total inventory count.

    Used by the booking modal: the user picks an equipment *type*
    (Dell Monitor, PC, etc.) plus a quantity; the ops team picks the
    specific physical assets to assign at approval time.

    Excludes decommissioned and missing assets from the count — those
    are not available for booking.
    """
    from database import get_db
    with get_db() as conn:
        rows = conn.execute(
            """SELECT em.id, em.name, em.brand,
                      COALESCE(c.name, 'Other') AS category,
                      COUNT(a.id) AS total_count
               FROM equipment_models em
               LEFT JOIN categories c ON c.id = em.category_id
               LEFT JOIN assets a ON a.equipment_model_id = em.id
                                  AND a.status NOT IN ('decommissioned', 'missing')
               GROUP BY em.id, em.name, em.brand, c.name
               HAVING total_count > 0
               ORDER BY em.name, em.brand""",
        ).fetchall()
    return jsonify([
        {
            "id": r["id"],
            "name": r["name"],
            "brand": r["brand"],
            "category": r["category"],
            "total_count": r["total_count"],
        }
        for r in rows
    ])


@floor_plan_bp.route("/api/inventory/search", methods=["GET"])
def api_inventory_search():
    """Search across all of sail.db's assets — used by the booking modal
    so users can pick any asset, not just ones already in the room.

    Query params:
        q     — substring matched against asset_tag, model name, brand
                (case-insensitive). Empty q returns the first `limit`
                rows ordered by model name.
        limit — max rows to return (default 20, capped at 100).
    """
    q = (request.args.get("q") or "").strip()
    try:
        limit = max(1, min(int(request.args.get("limit", 20)), 100))
    except ValueError:
        limit = 20

    sql = (
        "SELECT a.id, a.asset_tag, a.status, a.condition, a.assigned_to, "
        "       a.location_id, em.name AS model_name, em.brand, "
        "       l.label AS location_label "
        "FROM assets a "
        "JOIN equipment_models em ON em.id = a.equipment_model_id "
        "LEFT JOIN locations l ON l.id = a.location_id "
    )
    params = []
    if q:
        like = f"%{q}%"
        sql += ("WHERE a.asset_tag LIKE ? COLLATE NOCASE "
                "   OR em.name LIKE ? COLLATE NOCASE "
                "   OR em.brand LIKE ? COLLATE NOCASE ")
        params.extend([like, like, like])
    sql += "ORDER BY em.name, a.asset_tag LIMIT ?"
    params.append(limit)

    from database import get_db
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return jsonify([
        {
            "id": r["id"],
            "asset_tag": r["asset_tag"],
            "status": r["status"],
            "condition": r["condition"],
            "assigned_to": r["assigned_to"],
            "location_id": r["location_id"],
            "location_label": r["location_label"],
            "model_name": r["model_name"],
            "brand": r["brand"],
        }
        for r in rows
    ])


@floor_plan_bp.route("/api/zones/<zone_key>/assets", methods=["GET"])
def api_zone_assets(zone_key):
    """List assets for any zone that has a sail.db location mapping —
    bookable rooms plus the broader ZONE_TO_LOCATION map. Returns
    `{assets, linked, zone_key}`; `linked` is False when the zone has no
    mapping, so the side panel can render a calm empty state instead of
    a 404.
    """
    from .zone_map import location_for
    location_id = None
    room = BookableRoom.query.filter_by(zone_key=zone_key, is_active=1).first()
    if room is not None:
        location_id = room.sail_location_id
    else:
        location_id = location_for(zone_key)

    if location_id is None:
        return jsonify({"assets": [], "linked": False, "zone_key": zone_key}), 200
    return jsonify({
        "assets": _query_assets_at_location(location_id),
        "linked": True,
        "zone_key": zone_key,
    })


@floor_plan_bp.route("/api/rooms/<zone_key>/schedule", methods=["GET"])
def api_room_schedule(zone_key):
    """Return the booked time windows for a room on a given date so the
    booking modal can render a visual day-strip of free vs busy slots.

    Returns: {"date": ..., "lab_open": "07:00", "lab_close": "16:00",
              "slot_minutes": 15,
              "bookings": [{"ticket_number", "start_time", "end_time", "status",
                            "submitter_name"}, ...]}
    """
    date = request.args.get("date", "")
    if not date:
        abort(400, description="date query param is required (YYYY-MM-DD).")

    room = BookableRoom.query.filter_by(zone_key=zone_key, is_active=1).first()
    if room is None:
        abort(404, description=f"No bookable room for zone '{zone_key}'.")

    from .booking import _parse_times_from_description, LAB_OPEN, LAB_CLOSE, SLOT_MINUTES
    title = f"Booking request: {room.label} on {date}"
    from database import get_db
    with get_db() as conn:
        rows = conn.execute(
            """SELECT t.ticket_number, t.description, t.status, e.name AS submitter_name
               FROM tickets t
               LEFT JOIN employees e ON e.id = t.submitted_by
               WHERE t.title = ?
                 AND t.type = 'new_request'
                 AND t.status IN ('open', 'in_progress', 'waiting')
               ORDER BY t.id""",
            (title,),
        ).fetchall()

    bookings = []
    for r in rows:
        s, e = _parse_times_from_description(r["description"])
        if s and e:
            bookings.append({
                "ticket_number": r["ticket_number"],
                "start_time": s,
                "end_time": e,
                "status": r["status"],
                "submitter_name": r["submitter_name"],
            })

    return jsonify({
        "date": date,
        "lab_open": LAB_OPEN.strftime("%H:%M"),
        "lab_close": LAB_CLOSE.strftime("%H:%M"),
        "slot_minutes": SLOT_MINUTES,
        "bookings": bookings,
    })


@floor_plan_bp.route("/api/rooms/<zone_key>/bookings", methods=["GET"])
def api_room_bookings(zone_key):
    """Count pending booking requests for a room on a given date.

    Used by the booking modal to show "X pending requests for this date" so
    users see if a room is already in demand. Looks up tickets by the title
    pattern that booking.create_booking_ticket() writes; safe because we own
    the format.
    """
    date = request.args.get("date", "")
    if not date:
        abort(400, description="date query param is required (YYYY-MM-DD).")

    room = BookableRoom.query.filter_by(zone_key=zone_key, is_active=1).first()
    if room is None:
        abort(404, description=f"No bookable room for zone '{zone_key}'.")

    title = f"Booking request: {room.label} on {date}"
    from database import get_db
    with get_db() as conn:
        rows = conn.execute(
            """SELECT ticket_number, status FROM tickets
               WHERE title = ?
                 AND type = 'new_request'
                 AND status IN ('open', 'in_progress', 'waiting')
               ORDER BY id DESC""",
            (title,),
        ).fetchall()

    return jsonify({
        "date": date,
        "open_count": len(rows),
        "tickets": [{"ticket_number": r["ticket_number"], "status": r["status"]} for r in rows],
    })


@floor_plan_bp.route("/api/bookings", methods=["GET"])
def api_list_bookings():
    """List booking tickets with parsed room/date/asset metadata.

    Optional ?status=open|in_progress|closed|all (default open + in_progress).
    Powers the ops bookings page.
    """
    from .booking import (_parse_booking_title, _parse_times_from_description,
                          _parse_assets_from_description,
                          _parse_assigned_assets_from_description)
    from database import get_db

    status_q = (request.args.get("status") or "active").lower()
    if status_q == "all":
        statuses = None
    elif status_q == "active":
        statuses = ("open", "in_progress")
    else:
        statuses = (status_q,)

    sql = (
        "SELECT t.id, t.ticket_number, t.title, t.description, t.status, "
        "       t.created_at, t.closed_at, t.submitted_by, "
        "       e.name AS submitter_name, e.email AS submitter_email "
        "FROM tickets t "
        "LEFT JOIN employees e ON e.id = t.submitted_by "
        "WHERE t.title LIKE 'Booking request:%'"
    )
    params = []
    if statuses:
        sql += " AND t.status IN (" + ",".join("?" * len(statuses)) + ")"
        params.extend(statuses)

    # Regular users see only their own bookings; admin/manager see all.
    from flask import g
    user = getattr(g, "user", None)
    if user and user.get("role") not in ("admin", "manager"):
        sql += " AND t.submitted_by = ?"
        params.append(user["id"])

    sql += " ORDER BY t.id DESC"

    # Build label -> zone_key map from bookable_rooms (floor_plan.db)
    label_to_zone = {r.label: r.zone_key for r in BookableRoom.query.all()}

    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()

        # Collect every asset_tag mentioned across all bookings — both
        # user-requested (open tickets) and ops-assigned (in_progress / closed).
        # Prefer the assigned set when it exists so the close modal sees
        # the actual allocation.
        all_tags = set()
        parsed = []
        for r in rows:
            assigned_tags = _parse_assigned_assets_from_description(r["description"])
            if assigned_tags:
                tags = assigned_tags
            else:
                tags = _parse_assets_from_description(r["description"])
            parsed.append(tags)
            all_tags.update(tags)
        tag_to_asset = {}
        if all_tags:
            placeholders = ",".join("?" * len(all_tags))
            asset_rows = conn.execute(
                f"""SELECT a.id, a.asset_tag, a.status, em.name AS model_name
                    FROM assets a
                    JOIN equipment_models em ON em.id = a.equipment_model_id
                    WHERE a.asset_tag IN ({placeholders})""",
                tuple(all_tags),
            ).fetchall()
            tag_to_asset = {ar["asset_tag"]: dict(ar) for ar in asset_rows}

    out = []
    for r, tags in zip(rows, parsed):
        room_label, date_str = _parse_booking_title(r["title"])
        start_time, end_time = _parse_times_from_description(r["description"])
        assets = []
        for tag in tags:
            a = tag_to_asset.get(tag)
            if a:
                assets.append({
                    "id": a["id"],
                    "asset_tag": a["asset_tag"],
                    "model_name": a["model_name"],
                    "status": a["status"],
                })
            else:
                # Asset removed from sail.db since the booking — keep the tag
                assets.append({"id": None, "asset_tag": tag, "model_name": "", "status": "unknown"})
        out.append({
            "id": r["id"],
            "ticket_number": r["ticket_number"],
            "status": r["status"],
            "room_label": room_label,
            "zone_key": label_to_zone.get(room_label or "", ""),
            "date": date_str,
            "start_time": start_time,
            "end_time": end_time,
            "assets": assets,
            "submitter": {
                "name": r["submitter_name"],
                "email": r["submitter_email"],
            },
            "created_at": r["created_at"],
            "closed_at": r["closed_at"],
        })
    return jsonify(out)


@floor_plan_bp.route("/api/bookings", methods=["POST"])
def api_create_booking():
    """Submit a booking request. Creates a ticket in sail.db."""
    payload = request.get_json(silent=True)
    try:
        result = create_booking_ticket(payload)
    except BookingError as e:
        msg = str(e)
        if "No bookable room" in msg:
            return jsonify({"error": msg}), 404
        return jsonify({"error": msg}), 400
    return jsonify(result), 201


@floor_plan_bp.route("/api/bookings/<int:ticket_id>/approve", methods=["POST"])
def api_approve_booking(ticket_id):
    """Ops/admin marks a booking request approved.

    Flips the ticket from open to in_progress, audit-logs the transition,
    and emails the requester.
    """
    try:
        result = approve_booking(ticket_id)
    except BookingError as e:
        msg = str(e)
        if "not found" in msg.lower():
            return jsonify({"error": msg}), 404
        if "forbidden" in msg.lower() or "login required" in msg.lower():
            return jsonify({"error": msg}), 403
        return jsonify({"error": msg}), 400
    return jsonify(result), 200


@floor_plan_bp.route("/api/bookings/<int:ticket_id>/close", methods=["POST"])
def api_close_booking(ticket_id):
    """Ops/admin closes a booking with asset return verification.

    Body: {"returns": [{"asset_id": int, "state": "returned_good"|"damaged"|"missing", "notes": str?}, ...]}
    Updates each asset's status, closes the ticket, persists booking_returns
    rows, and emails the requester (CCs admin if any return was damaged or
    missing).
    """
    payload = request.get_json(silent=True) or {}
    try:
        result = close_booking(ticket_id, payload)
    except BookingError as e:
        msg = str(e)
        if "not found" in msg.lower():
            return jsonify({"error": msg}), 404
        if "forbidden" in msg.lower() or "login required" in msg.lower():
            return jsonify({"error": msg}), 403
        return jsonify({"error": msg}), 400
    return jsonify(result), 200


# ---------- Healthcheck ----------

@floor_plan_bp.route("/healthz", methods=["GET"])
def healthz():
    """Simple health check — verifies DB is reachable."""
    try:
        Pin.query.limit(1).all()
        return jsonify({"status": "ok", "service": "floor_plan"}), 200
    except Exception as e:
        return jsonify({"status": "degraded", "service": "floor_plan", "error": str(e)}), 503
