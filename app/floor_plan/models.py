"""SQLAlchemy models for the floor plan."""

from datetime import datetime, timezone
from .db import db


def _now():
    """Timezone-aware UTC now — replaces deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc)


class Pin(db.Model):
    """A user-placed pin on the isometric SAIL render.

    Coordinates are percentages of the stage size (0-100), not pixels — see
    docs/DATA-MODEL.md for the rationale. The `assets` field is a JSON array of
    [name, count] pairs since asset shape varies per pin.
    """
    __tablename__ = "floor_plan_pins"

    id = db.Column(db.String(16), primary_key=True)  # e.g. "P-01"
    name = db.Column(db.String(200), nullable=False, default="Untitled")
    sub = db.Column(db.String(200), default="")
    x = db.Column(db.Float, nullable=False)  # 0-100
    y = db.Column(db.Float, nullable=False)  # 0-100
    type = db.Column(db.String(40), default="custom")
    type_label = db.Column(db.String(80), default="Custom")
    capacity = db.Column(db.String(80), default="")
    cap_sub = db.Column(db.String(120), default="")
    occupancy = db.Column(db.Integer, nullable=True)  # 0-100, optional
    desc = db.Column(db.Text, default="")
    assets = db.Column(db.JSON, default=list)  # [[name, count], ...]

    created_at = db.Column(db.DateTime, default=_now)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)
    created_by = db.Column(db.String(120), nullable=True)  # populated if auth available

    def to_dict(self) -> dict:
        """Shape matches what the JS frontend expects in SAIL_PINS[]."""
        return {
            "id": self.id,
            "name": self.name,
            "sub": self.sub,
            "x": self.x,
            "y": self.y,
            "type": self.type,
            "typeLabel": self.type_label,
            "capacity": self.capacity,
            "capSub": self.cap_sub,
            "occupancy": self.occupancy,
            "desc": self.desc,
            "assets": self.assets or [],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Pin":
        """Build (or update) a Pin from JS-shaped JSON."""
        return cls(
            id=data["id"],
            name=data.get("name", "Untitled"),
            sub=data.get("sub", ""),
            x=float(data["x"]),
            y=float(data["y"]),
            type=data.get("type", "custom"),
            type_label=data.get("typeLabel", "Custom"),
            capacity=data.get("capacity", ""),
            cap_sub=data.get("capSub", ""),
            occupancy=data.get("occupancy"),
            desc=data.get("desc", ""),
            assets=data.get("assets", []),
        )

    def update_from_dict(self, data: dict) -> None:
        """Mutate this pin in place from JS-shaped JSON."""
        for js_key, py_key in [
            ("name", "name"), ("sub", "sub"),
            ("x", "x"), ("y", "y"),
            ("type", "type"), ("typeLabel", "type_label"),
            ("capacity", "capacity"), ("capSub", "cap_sub"),
            ("occupancy", "occupancy"), ("desc", "desc"),
            ("assets", "assets"),
        ]:
            if js_key in data:
                setattr(self, py_key, data[js_key])

    def __repr__(self) -> str:
        return f"<Pin {self.id} {self.name!r} at ({self.x:.1f}, {self.y:.1f})>"


class BookableRoom(db.Model):
    """A room on the floor plan that users can request to book.

    `zone_key` matches a key in the JS ZONES object on the plan view.
    `sail_location_id` is a SOFT FK into sail.db locations(id) — SQLite cannot
    enforce cross-database FKs, so the application layer guards reads.
    """
    __tablename__ = "bookable_rooms"

    id = db.Column(db.Integer, primary_key=True)
    zone_key = db.Column(db.String(80), nullable=False, unique=True)
    sail_location_id = db.Column(db.Integer, nullable=False)
    label = db.Column(db.String(120), nullable=False)
    capacity = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Integer, default=1, nullable=False)
    created_at = db.Column(db.DateTime, default=_now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "zone_key": self.zone_key,
            "sail_location_id": self.sail_location_id,
            "label": self.label,
            "capacity": self.capacity,
            "is_active": bool(self.is_active),
        }

    def __repr__(self) -> str:
        return f"<BookableRoom {self.zone_key} -> loc {self.sail_location_id}>"


class BookingReturn(db.Model):
    """One row per asset returned at the close of a booking.

    Booking tickets live in sail.db (cross-DB seam at ticket level), but the
    return-verification metadata stays here in floor_plan.db. We denormalise
    `asset_tag` and `model_name` so the audit stays readable even if the
    asset row is later renumbered or deleted in sail.db.

    `state` is enforced at the application layer (no SQLite ENUM); allowed
    values are `returned_good`, `damaged`, `missing`.
    """
    __tablename__ = "booking_returns"

    id = db.Column(db.Integer, primary_key=True)
    booking_ticket_id = db.Column(db.Integer, nullable=False, index=True)
    asset_id = db.Column(db.Integer, nullable=False)
    asset_tag = db.Column(db.String(40), nullable=False)
    model_name = db.Column(db.String(200), default="")
    state = db.Column(db.String(20), nullable=False)
    notes = db.Column(db.Text, default="")
    verified_at = db.Column(db.DateTime, default=_now, nullable=False)
    verified_by = db.Column(db.Integer, nullable=True)  # sail.db employees.id

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "booking_ticket_id": self.booking_ticket_id,
            "asset_id": self.asset_id,
            "asset_tag": self.asset_tag,
            "model_name": self.model_name,
            "state": self.state,
            "notes": self.notes,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "verified_by": self.verified_by,
        }

    def __repr__(self) -> str:
        return f"<BookingReturn ticket={self.booking_ticket_id} asset={self.asset_tag} {self.state}>"
