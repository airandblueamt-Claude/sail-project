"""Tests for the BookableRoom model."""

def test_bookable_room_model_persists(app):
    from app.floor_plan.models import BookableRoom
    from app.floor_plan.db import db
    with app.app_context():
        room = BookableRoom(
            zone_key="test-room",
            sail_location_id=99,
            label="Test Room",
            capacity=10,
        )
        db.session.add(room)
        db.session.commit()

        fetched = BookableRoom.query.filter_by(zone_key="test-room").one()
        assert fetched.label == "Test Room"
        assert fetched.capacity == 10
        assert fetched.is_active == 1


def test_bookable_room_zone_key_is_unique(app):
    from app.floor_plan.models import BookableRoom
    from app.floor_plan.db import db
    from sqlalchemy.exc import IntegrityError
    with app.app_context():
        db.session.add(BookableRoom(zone_key="x", sail_location_id=1, label="A"))
        db.session.commit()
        db.session.add(BookableRoom(zone_key="x", sail_location_id=2, label="B"))
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return
        raise AssertionError("expected IntegrityError on duplicate zone_key")


def test_seed_creates_four_rooms(app):
    from app.floor_plan.models import BookableRoom
    with app.app_context():
        rooms = {r.zone_key: r for r in BookableRoom.query.all()}
        assert set(rooms) == {"global-theater", "boardroom-1", "boardroom-2", "conference-long"}
        assert rooms["global-theater"].label == "Theater"
        assert rooms["boardroom-1"].label == "Workshop 1"
        assert rooms["boardroom-2"].label == "Workshop 2"
        assert rooms["conference-long"].label == "Workshop 3"
        assert rooms["global-theater"].sail_location_id == 11
        assert rooms["boardroom-1"].sail_location_id == 38


def test_seed_is_idempotent(app):
    from app.floor_plan.seed import seed_bookable_rooms
    from app.floor_plan.models import BookableRoom
    with app.app_context():
        before = BookableRoom.query.count()
        seed_bookable_rooms()
        after = BookableRoom.query.count()
        assert before == after == 4
