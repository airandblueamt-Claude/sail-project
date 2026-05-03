def test_get_bookable_rooms_returns_seeded_rooms(client):
    resp = client.get("/floor-plan/api/bookable-rooms")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) == 4
    keys = {r["zone_key"] for r in data}
    assert keys == {"global-theater", "boardroom-1", "boardroom-2", "conference-long"}
    theater = next(r for r in data if r["zone_key"] == "global-theater")
    assert theater["label"] == "Theater"
    assert theater["capacity"] == 80
    assert theater["sail_location_id"] == 11


def test_get_bookable_rooms_excludes_inactive(client, app):
    from app.floor_plan.models import BookableRoom
    from app.floor_plan.db import db
    with app.app_context():
        room = BookableRoom.query.filter_by(zone_key="boardroom-2").one()
        room.is_active = 0
        db.session.commit()

    resp = client.get("/floor-plan/api/bookable-rooms")
    keys = {r["zone_key"] for r in resp.get_json()}
    assert "boardroom-2" not in keys
    assert len(keys) == 3
