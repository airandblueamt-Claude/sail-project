"""End-to-end tests for the floor plan API."""


def test_index_renders(client):
    res = client.get("/floor-plan/")
    assert res.status_code == 200
    assert b"Incubation Floor Plan" in res.data


def test_healthz(client):
    res = client.get("/floor-plan/healthz")
    assert res.status_code == 200
    assert res.json["status"] == "ok"


def test_pins_starts_empty(client):
    res = client.get("/floor-plan/api/pins")
    assert res.status_code == 200
    assert res.json == []


def test_create_pin(client):
    res = client.post("/floor-plan/api/pins", json={
        "id": "P-01", "name": "Aramco.ai", "x": 18.5, "y": 38.2
    })
    assert res.status_code == 201
    body = res.json
    assert body["id"] == "P-01"
    assert body["name"] == "Aramco.ai"
    assert body["x"] == 18.5
    assert body["assets"] == []


def test_create_duplicate_id_rejected(client):
    pin = {"id": "P-01", "name": "First", "x": 50, "y": 50}
    assert client.post("/floor-plan/api/pins", json=pin).status_code == 201
    assert client.post("/floor-plan/api/pins", json=pin).status_code == 409


def test_create_rejects_invalid_coords(client):
    res = client.post("/floor-plan/api/pins", json={
        "id": "P-01", "name": "Bad", "x": 150, "y": 50
    })
    assert res.status_code == 400


def test_create_rejects_missing_fields(client):
    res = client.post("/floor-plan/api/pins", json={"id": "P-01"})
    assert res.status_code == 400


def test_bulk_replace(client):
    pins = [
        {"id": "P-01", "name": "A", "x": 10, "y": 20},
        {"id": "P-02", "name": "B", "x": 30, "y": 40, "sub": "Sub B", "assets": [["chair", "4"]]},
    ]
    res = client.put("/floor-plan/api/pins", json=pins)
    assert res.status_code == 200
    assert res.json["saved"] == 2

    listed = client.get("/floor-plan/api/pins").json
    assert len(listed) == 2
    by_id = {p["id"]: p for p in listed}
    assert by_id["P-02"]["sub"] == "Sub B"
    assert by_id["P-02"]["assets"] == [["chair", "4"]]


def test_bulk_replace_clears_existing(client):
    client.post("/floor-plan/api/pins", json={"id": "P-99", "name": "Old", "x": 1, "y": 1})
    client.put("/floor-plan/api/pins", json=[{"id": "P-01", "name": "New", "x": 50, "y": 50}])
    listed = client.get("/floor-plan/api/pins").json
    assert len(listed) == 1
    assert listed[0]["id"] == "P-01"


def test_bulk_replace_atomic_on_validation_failure(client):
    client.post("/floor-plan/api/pins", json={"id": "P-OLD", "name": "Existing", "x": 5, "y": 5})
    bad = [
        {"id": "P-01", "name": "Good", "x": 50, "y": 50},
        {"id": "P-02", "name": "Bad", "x": 999, "y": 50},  # invalid
    ]
    res = client.put("/floor-plan/api/pins", json=bad)
    assert res.status_code == 400
    # Original pin should still exist — nothing was committed
    listed = client.get("/floor-plan/api/pins").json
    assert len(listed) == 1
    assert listed[0]["id"] == "P-OLD"


def test_patch_pin(client):
    client.post("/floor-plan/api/pins", json={"id": "P-01", "name": "Old name", "x": 50, "y": 50})
    res = client.patch("/floor-plan/api/pins/P-01", json={"name": "New name", "x": 75})
    assert res.status_code == 200
    assert res.json["name"] == "New name"
    assert res.json["x"] == 75
    assert res.json["y"] == 50  # unchanged


def test_patch_nonexistent_returns_404(client):
    res = client.patch("/floor-plan/api/pins/P-NOPE", json={"name": "X"})
    assert res.status_code == 404


def test_delete_pin(client):
    client.post("/floor-plan/api/pins", json={"id": "P-01", "name": "X", "x": 50, "y": 50})
    res = client.delete("/floor-plan/api/pins/P-01")
    assert res.status_code == 204
    assert client.get("/floor-plan/api/pins").json == []


def test_delete_nonexistent_returns_404(client):
    res = client.delete("/floor-plan/api/pins/P-NOPE")
    assert res.status_code == 404


def test_static_assets_served(client):
    for path in [
        "/floor-plan/static/floor_plan/css/floor-plan.css",
        "/floor-plan/static/floor_plan/js/floor-plan.js",
        "/floor-plan/static/floor_plan/images/sail-isometric.jpg",
    ]:
        res = client.get(path)
        assert res.status_code == 200, f"{path} returned {res.status_code}"
