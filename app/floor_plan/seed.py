"""One-shot seed for bookable_rooms.

Runs on init_floor_plan() if the table is empty. Idempotent — calling it on a
populated table is a no-op.
"""
from .db import db
from .models import BookableRoom

BOOKABLE_ROOMS = [
    # zone_key,         sail_location_id, label,        capacity
    ("global-theater",  11, "Theater",    80),
    ("boardroom-1",     38, "Workshop 1", 20),
    ("boardroom-2",     39, "Workshop 2", 20),
    ("conference-long", 40, "Workshop 3", 20),
]


def seed_bookable_rooms() -> int:
    """Insert the four bookable rooms if they don't exist. Returns rows added."""
    added = 0
    for zone_key, loc_id, label, capacity in BOOKABLE_ROOMS:
        if BookableRoom.query.filter_by(zone_key=zone_key).first() is None:
            db.session.add(BookableRoom(
                zone_key=zone_key,
                sail_location_id=loc_id,
                label=label,
                capacity=capacity,
            ))
            added += 1
    if added:
        db.session.commit()
    return added
