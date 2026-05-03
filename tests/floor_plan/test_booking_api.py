import sqlite3
from datetime import date, timedelta


def _payload(**overrides):
    base = {
        "zone_key": "boardroom-1",
        "date": (date.today() + timedelta(days=14)).isoformat(),
        "start_time": "09:00",
        "end_time": "11:00",
        "attendees": 12,
        "purpose": "Quarterly UX review session.",
        "asset_ids": [1, 2],
    }
    base.update(overrides)
    return base


def test_post_booking_creates_ticket(client, temp_sail_db):
    resp = client.post("/floor-plan/api/bookings", json=_payload())
    assert resp.status_code == 201, resp.data
    body = resp.get_json()
    assert body["ticket_number"].startswith("TKT-")
    assert "ticket_id" in body

    conn = sqlite3.connect(temp_sail_db)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (body["ticket_id"],)).fetchone()
    assert row is not None
    assert row["type"] == "new_request"
    assert row["status"] == "open"
    assert "Workshop 1" in row["title"]
    desc = row["description"]
    assert "09:00" in desc and "11:00" in desc
    assert "Quarterly UX" in desc
    assert "SAIL-0001" in desc and "SAIL-0002" in desc
    conn.close()


def test_post_booking_rejects_unknown_zone(client):
    resp = client.post("/floor-plan/api/bookings", json=_payload(zone_key="nope"))
    assert resp.status_code == 404


def test_post_booking_rejects_end_before_start(client):
    resp = client.post("/floor-plan/api/bookings",
                       json=_payload(start_time="11:00", end_time="09:00"))
    assert resp.status_code == 400
    assert "end" in resp.get_json()["error"].lower()


def test_post_booking_rejects_short_purpose(client):
    resp = client.post("/floor-plan/api/bookings", json=_payload(purpose="hi"))
    assert resp.status_code == 400


def test_post_booking_accepts_assets_from_any_room(client):
    """The 'must live in this room' rule was dropped — users describe what
    they need, ops physically arranges the room when approving. Asset 3 is
    in the Theater but the user can still request it for a Workshop-1
    booking (ops will move it or substitute)."""
    resp = client.post("/floor-plan/api/bookings",
                       json=_payload(asset_ids=[1, 3]))
    assert resp.status_code == 201, resp.data


def test_post_booking_rejects_unknown_asset_id(client):
    resp = client.post("/floor-plan/api/bookings",
                       json=_payload(asset_ids=[1, 99999]))
    assert resp.status_code == 400
    assert "do not exist" in resp.get_json()["error"]


def test_post_booking_rejects_overlap(client, temp_sail_db):
    # First booking 09:00-10:00 lands; second one with overlapping window
    # on the same room+date must be rejected.
    p1 = _payload(start_time="09:00", end_time="10:00")
    r1 = client.post("/floor-plan/api/bookings", json=p1)
    assert r1.status_code == 201, r1.data

    p2 = _payload(start_time="09:30", end_time="10:30")
    r2 = client.post("/floor-plan/api/bookings", json=p2)
    assert r2.status_code == 400
    assert "conflict" in r2.get_json()["error"].lower()


def test_post_booking_allows_adjacent_times(client):
    """Back-to-back bookings (one ends exactly when the next starts) are
    not a conflict — the overlap check uses strict less-than."""
    p1 = _payload(start_time="09:00", end_time="10:00")
    r1 = client.post("/floor-plan/api/bookings", json=p1)
    assert r1.status_code == 201, r1.data

    p2 = _payload(start_time="10:00", end_time="11:00")
    r2 = client.post("/floor-plan/api/bookings", json=p2)
    assert r2.status_code == 201, r2.data


def test_post_booking_with_equipment_request_succeeds(client):
    """User picks 'one Display' (model_id=1) instead of a specific asset id.
    The conftest seeds 3 Displays so capacity is fine."""
    resp = client.post("/floor-plan/api/bookings", json=_payload(
        equipment_requests=[{"model_id": 1, "quantity": 1}],
        asset_ids=[],
    ))
    assert resp.status_code == 201, resp.data


def test_post_booking_rejects_equipment_capacity_overflow(client):
    """Conftest has 3 Displays total. Three overlapping bookings each
    asking for 1 Display fit. A fourth overlapping booking asking for 1
    must be rejected with a clear capacity message."""
    base = _payload()
    # 3 successful overlapping bookings using equipment_requests
    for slot in [("09:00","10:00"), ("09:15","10:15"), ("09:30","10:30")]:
        # Each on a different room so the room-overlap rule doesn't fire
        rooms = ["boardroom-1", "boardroom-2", "conference-long"]
        room = rooms[["09:00","09:15","09:30"].index(slot[0])]
        r = client.post("/floor-plan/api/bookings", json=_payload(
            zone_key=room, start_time=slot[0], end_time=slot[1],
            asset_ids=[], equipment_requests=[{"model_id": 1, "quantity": 1}],
        ))
        assert r.status_code == 201, r.data
    # Fourth booking overlapping all three → capacity exceeded
    r4 = client.post("/floor-plan/api/bookings", json=_payload(
        zone_key="global-theater", start_time="09:30", end_time="10:30",
        asset_ids=[], equipment_requests=[{"model_id": 1, "quantity": 1}],
    ))
    assert r4.status_code == 400
    assert "not enough" in r4.get_json()["error"].lower()


def test_post_booking_rejects_past_date(client):
    from datetime import date, timedelta
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    r = client.post("/floor-plan/api/bookings", json=_payload(date=yesterday))
    assert r.status_code == 400
    assert "today or later" in r.get_json()["error"].lower()


def test_post_booking_writes_audit_row(client, temp_sail_db):
    resp = client.post("/floor-plan/api/bookings", json=_payload())
    ticket_id = resp.get_json()["ticket_id"]
    conn = sqlite3.connect(temp_sail_db)
    n = conn.execute(
        "SELECT COUNT(*) FROM audit_log WHERE table_name='tickets' AND record_id = ?",
        (ticket_id,),
    ).fetchone()[0]
    assert n >= 1
    conn.close()
