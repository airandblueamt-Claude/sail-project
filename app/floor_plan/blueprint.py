"""Floor plan blueprint — page route + JSON API for pins."""

from flask import (
    Blueprint, render_template, request, jsonify,
    abort, current_app
)
from sqlalchemy.exc import SQLAlchemyError

from .db import db
from .models import Pin, BookableRoom


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


@floor_plan_bp.route("/api/rooms/<zone_key>/assets", methods=["GET"])
def api_room_assets(zone_key):
    """List assets in the physical location backing this bookable room.

    Crosses databases: `bookable_rooms` is in floor_plan.db (SQLAlchemy),
    `assets` lives in sail.db (raw sqlite via database.get_db()).
    """
    room = BookableRoom.query.filter_by(zone_key=zone_key, is_active=1).first()
    if room is None:
        abort(404, description=f"No bookable room for zone '{zone_key}'.")

    # Late import so the test fixture's monkeypatch on database.DB_PATH lands first
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
            (room.sail_location_id,),
        ).fetchall()

    return jsonify([
        {
            "id": r["id"],
            "asset_tag": r["asset_tag"],
            "status": r["status"],
            "condition": r["condition"],
            "model_name": r["model_name"],
            "brand": r["brand"],
        }
        for r in rows
    ])


# ---------- Healthcheck ----------

@floor_plan_bp.route("/healthz", methods=["GET"])
def healthz():
    """Simple health check — verifies DB is reachable."""
    try:
        Pin.query.limit(1).all()
        return jsonify({"status": "ok", "service": "floor_plan"}), 200
    except Exception as e:
        return jsonify({"status": "degraded", "service": "floor_plan", "error": str(e)}), 503
