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


def test_post_booking_rejects_assets_not_in_this_room(client):
    # Asset id 3 lives in the Theater (loc 11), not Workshop 1
    resp = client.post("/floor-plan/api/bookings",
                       json=_payload(asset_ids=[1, 3]))
    assert resp.status_code == 400


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
