def test_assets_in_room_returns_assets_for_workshop_1(client):
    resp = client.get("/floor-plan/api/rooms/boardroom-1/assets")
    assert resp.status_code == 200
    data = resp.get_json()
    tags = sorted(a["asset_tag"] for a in data)
    assert tags == ["SAIL-0001", "SAIL-0002"]
    assert all("model_name" in a for a in data)


def test_assets_in_room_returns_assets_for_theater(client):
    resp = client.get("/floor-plan/api/rooms/global-theater/assets")
    data = resp.get_json()
    tags = [a["asset_tag"] for a in data]
    assert tags == ["SAIL-0003"]


def test_assets_in_room_404_for_unknown_zone(client):
    resp = client.get("/floor-plan/api/rooms/nope/assets")
    assert resp.status_code == 404


def test_assets_in_room_404_for_non_bookable_zone(client):
    resp = client.get("/floor-plan/api/rooms/west-cluster/assets")
    assert resp.status_code == 404
