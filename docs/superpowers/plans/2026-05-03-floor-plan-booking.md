# Floor Plan + Room Booking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vendor-copy the sail-incubation floor plan blueprint into sail-project on a feature branch, mark four rooms (Workshop 1/2/3 + Theater) as bookable, and turn booking requests into tickets in the existing tickets queue.

**Architecture:** Two databases coexist — `sail.db` (raw `sqlite3` via existing `get_db()`) stays the source of truth for assets, employees, tickets; `floor_plan.db` (SQLAlchemy via `init_floor_plan(app)`) stores pins and the new `bookable_rooms` table. The booking POST endpoint is the only seam between the two — it reads bookable-room metadata from `floor_plan.db`, then opens a `with get_db() as conn:` against `sail.db` to insert the ticket and audit row.

**Tech Stack:** Flask 3, Flask-SQLAlchemy 3, SQLAlchemy 2, raw `sqlite3`, plain JS/CSS (no build step), pytest.

**Spec:** `docs/superpowers/specs/2026-05-03-floor-plan-booking-design.md`

---

## File map

### Created

| File | Purpose |
|---|---|
| `app/floor_plan/__init__.py` | (vendor copy) blueprint export + `init_floor_plan` |
| `app/floor_plan/blueprint.py` | (vendor copy + edits) routes — page, pin API, +new booking API |
| `app/floor_plan/db.py` | (vendor copy) SQLAlchemy init |
| `app/floor_plan/models.py` | (vendor copy + edits) `Pin` model + new `BookableRoom` model |
| `app/floor_plan/booking.py` | NEW — `create_booking_ticket()` cross-DB helper |
| `app/floor_plan/seed.py` | NEW — seed `bookable_rooms` on first boot |
| `app/floor_plan/templates/floor_plan/index.html` | (vendor copy + edits) SVG label renames + booking modal |
| `app/floor_plan/static/floor_plan/css/floor-plan.css` | (vendor copy + edits) bookable badge + modal styles |
| `app/floor_plan/static/floor_plan/js/floor-plan.js` | (vendor copy + edits) zone relabel, asset list, booking flow |
| `app/floor_plan/static/floor_plan/images/sail-isometric.jpg` | (vendor copy) |
| `app/floor_plan/tests/` | (vendor copy) the 15 existing pin tests |
| `tests/floor_plan/conftest.py` | NEW — pytest fixtures with two temp DBs |
| `tests/floor_plan/test_bookable_rooms.py` | NEW — model + seed tests |
| `tests/floor_plan/test_booking_api.py` | NEW — booking POST → ticket integration test |
| `tests/floor_plan/test_assets_api.py` | NEW — assets-in-room cross-DB query test |

### Modified

| File | Change |
|---|---|
| `app.py` | Register `floor_plan_bp` and call `init_floor_plan(app)` in `create_app()` |
| `templates/base.html` | Add "Floor plan" nav link in the main `<ul class="nav-links">` |
| `requirements.txt` | Add `Flask-SQLAlchemy>=3.1,<4.0` and `SQLAlchemy>=2.0,<3.0` |

---

## XSS guidance for all JS edits

Every DOM mutation in the JS tasks below uses `textContent` for any value that came from the server (asset tags, model names, brands, room labels, ticket numbers, error messages from the API). Static structural HTML uses `createElement` + `appendChild`. **Never set `innerHTML` with interpolated server data.** If you need to clear a container, use `node.replaceChildren()` or assign empty string. The plan's code follows this rule; if you adapt it, hold the line.

---

## Task 1: Branch + safety backup

**Files:** none yet

- [ ] **Step 1: Create feature branch**

```bash
cd /home/malkhalifa/sail-project
git checkout main
git status   # confirm clean working tree before branching
git checkout -b feature/floor-plan-booking
```

Expected: `Switched to a new branch 'feature/floor-plan-booking'`

- [ ] **Step 2: Backup sail.db**

```bash
python backup_db.py
ls -lt backups/ | head -3
```

Expected: a fresh `sail-YYYYMMDD-HHMMSS.db` file appears in `backups/`.

- [ ] **Step 3: No commit yet** — branch + backup is environment setup, not a code change. Continue to Task 2.

---

## Task 2: Vendor-copy the blueprint and its tests

**Files:**
- Create: `app/floor_plan/` (whole tree, copied from `../sail-incubation/app/floor_plan/`)
- Create: `app/floor_plan/tests/` (copied from `../sail-incubation/tests/`)

- [ ] **Step 1: Copy the blueprint package**

```bash
cp -r /home/malkhalifa/sail-incubation/app/floor_plan app/floor_plan
```

Expected: `app/floor_plan/__init__.py`, `blueprint.py`, `db.py`, `models.py`, `templates/`, `static/` exist.

- [ ] **Step 2: Copy the existing pytest suite next to the blueprint**

```bash
cp -r /home/malkhalifa/sail-incubation/tests app/floor_plan/tests
ls app/floor_plan/tests
```

Expected: `conftest.py` and 3-4 `test_*.py` files appear under `app/floor_plan/tests/`.

- [ ] **Step 3: Verify the copy**

```bash
ls app/floor_plan
```

Expected: `__init__.py  blueprint.py  db.py  models.py  static  templates  tests` (plus `__pycache__` is OK).

- [ ] **Step 4: Commit the raw copy (no edits yet)**

```bash
git add app/floor_plan
git commit -m "vendor: copy sail-incubation floor_plan blueprint"
```

---

## Task 3: Add SQLAlchemy to requirements; verify blueprint tests still pass

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Append SQLAlchemy deps to requirements.txt**

After this task `requirements.txt` should read:

```
flask>=3.0
openpyxl>=3.1
gunicorn>=21.0
Flask-SQLAlchemy>=3.1,<4.0
SQLAlchemy>=2.0,<3.0
```

- [ ] **Step 2: Install the new deps**

```bash
pip install -r requirements.txt
```

Expected: `Flask-SQLAlchemy` and `SQLAlchemy` install (or "already satisfied"). No errors.

- [ ] **Step 3: Run the vendored test suite**

```bash
pytest app/floor_plan/tests -v
```

Expected: **15 passed**. (If pytest's discovery from project root collides with multiple `conftest.py` files, run instead `cd app/floor_plan && pytest tests -v`.)

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "deps: add Flask-SQLAlchemy and SQLAlchemy for floor_plan blueprint"
```

---

## Task 4: Register the blueprint and add a nav link

**Files:**
- Modify: `app.py:106-122` (blueprint registration block)
- Modify: `templates/base.html:24-34` (nav-links list)

- [ ] **Step 1: Edit `app.py` to register the blueprint + init**

In `app.py`, append to the imports block at lines 107-113 (after `from routes.issue_categories import issue_categories_bp`):

```python
    from app.floor_plan import floor_plan_bp, init_floor_plan
```

In the registration block (after the existing `app.register_blueprint(issue_categories_bp, ...)` line), add:

```python
    app.register_blueprint(floor_plan_bp, url_prefix='/floor-plan')
    init_floor_plan(app)
```

`init_floor_plan(app)` is called with no `existing_db` so the blueprint creates its own `floor_plan.db` (Flask defaults the SQLite file to the `instance/` folder).

- [ ] **Step 2: Add a nav link in `templates/base.html`**

Find the block at lines 24-34 (the user-facing nav-links). After the existing "Tickets" link (around line 31-33), add:

```html
            <li><a href="{{ url_for('floor_plan.index') }}" class="{% if request.blueprint == 'floor_plan' %}active{% endif %}">
                <i data-lucide="map"></i> Floor plan
            </a></li>
```

- [ ] **Step 3: Launch the app and smoke-test**

```bash
python app.py
```

In a browser, log in, then visit:
- `http://127.0.0.1:5555/` — dashboard renders, nav link "Floor plan" appears
- `http://127.0.0.1:5555/floor-plan/` — the floor plan page renders (plan view default)
- `http://127.0.0.1:5555/inventory` — inventory still works
- `http://127.0.0.1:5555/tickets/mine` — tickets still works

Confirm `instance/floor_plan.db` was created on first request:

```bash
ls instance/
```

Expected: `floor_plan.db` file present.

- [ ] **Step 4: Stop the app (Ctrl-C) and commit**

```bash
git add app.py templates/base.html
git commit -m "feat(floor-plan): register blueprint and add nav link"
```

---

## Task 5: Add the BookableRoom model

**Files:**
- Modify: `app/floor_plan/models.py` (append at end)
- Create: `tests/floor_plan/__init__.py` (empty)
- Create: `tests/floor_plan/conftest.py`
- Create: `tests/floor_plan/test_bookable_rooms.py`

- [ ] **Step 1: Write the failing model test**

Create `tests/floor_plan/__init__.py` (empty file).

Create `tests/floor_plan/conftest.py`:

```python
"""Pytest fixtures for the floor_plan booking tests.

Spins up a Flask app with a temporary floor_plan.db (SQLAlchemy) and a
temporary sail.db (raw sqlite3, schema applied from schema.sql).
"""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def temp_sail_db(monkeypatch):
    """A temp sail.db with schema applied + a couple of seed rows."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    schema = (PROJECT_ROOT / "schema.sql").read_text()
    conn = sqlite3.connect(path)
    conn.executescript(schema)
    conn.executescript(
        """
        INSERT INTO categories (name) VALUES ('Furniture');
        INSERT INTO locations (id, code, label) VALUES
          (11, 'DIGITAL-THEATER', 'Digital Theater'),
          (38, 'WORKSHOP-1', 'Workshop -1'),
          (39, 'WORKSHOP-2', 'Workshop -2'),
          (40, 'WORKSHOP-3', 'Workshop -3');
        INSERT INTO equipment_models (id, category_id, name) VALUES (1, 1, 'Display');
        INSERT INTO assets (id, asset_tag, equipment_model_id, location_id, status, condition)
          VALUES (1, 'SAIL-0001', 1, 38, 'available', 'good'),
                 (2, 'SAIL-0002', 1, 38, 'available', 'good'),
                 (3, 'SAIL-0003', 1, 11, 'available', 'good');
        """
    )
    conn.execute(
        "INSERT INTO employees (id, name, email, password_hash, role, is_active) "
        "VALUES (1, 'Test User', 'test@example.com', ?, 'admin', 1)",
        (generate_password_hash("Password1!"),),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr("config.DB_PATH", path)
    monkeypatch.setattr("database.DB_PATH", path)
    yield path
    os.unlink(path)


@pytest.fixture
def app(temp_sail_db, tmp_path):
    """Flask app with floor_plan registered and a temp floor_plan.db."""
    from app.floor_plan import floor_plan_bp, init_floor_plan
    from app.floor_plan.db import db as fp_db

    fp_path = tmp_path / "floor_plan.db"

    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{fp_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.register_blueprint(floor_plan_bp, url_prefix="/floor-plan")
    init_floor_plan(app)

    yield app

    with app.app_context():
        fp_db.session.remove()
        fp_db.engine.dispose()


@pytest.fixture
def client(app):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["user_id"] = 1
    return c
```

Create `tests/floor_plan/test_bookable_rooms.py`:

```python
"""Tests for the BookableRoom model."""

def test_bookable_room_model_persists(app):
    from app.floor_plan.models import BookableRoom
    from app.floor_plan.db import db
    with app.app_context():
        room = BookableRoom(
            zone_key="global-theater",
            sail_location_id=11,
            label="Theater",
            capacity=80,
        )
        db.session.add(room)
        db.session.commit()

        fetched = BookableRoom.query.filter_by(zone_key="global-theater").one()
        assert fetched.label == "Theater"
        assert fetched.capacity == 80
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/floor_plan/test_bookable_rooms.py -v
```

Expected: FAIL with `ImportError` or `AttributeError: module 'app.floor_plan.models' has no attribute 'BookableRoom'`.

- [ ] **Step 3: Implement the model**

Append to `app/floor_plan/models.py` (after the `Pin` class):

```python
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
```

- [ ] **Step 4: Run test to verify pass**

```bash
pytest tests/floor_plan/test_bookable_rooms.py -v
```

Expected: **2 passed**.

- [ ] **Step 5: Commit**

```bash
git add app/floor_plan/models.py tests/floor_plan/
git commit -m "feat(floor-plan): add BookableRoom model"
```

---

## Task 6: Seed the four bookable rooms on first boot

**Files:**
- Create: `app/floor_plan/seed.py`
- Modify: `app/floor_plan/db.py:46-50` (the `db.create_all()` block at end of `init_floor_plan`)

- [ ] **Step 1: Add a seed test**

Append to `tests/floor_plan/test_bookable_rooms.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/floor_plan/test_bookable_rooms.py::test_seed_creates_four_rooms -v
```

Expected: FAIL — `assert set(rooms) == ...` because nothing seeded yet.

- [ ] **Step 3: Create `app/floor_plan/seed.py`**

```python
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
```

- [ ] **Step 4: Wire the seed into `init_floor_plan`**

In `app/floor_plan/db.py`, replace the existing `with app.app_context(): db.create_all()` block (lines 46-50) with:

```python
    with app.app_context():
        db.create_all()
        from .seed import seed_bookable_rooms
        seed_bookable_rooms()
```

- [ ] **Step 5: Run tests to verify pass**

```bash
pytest tests/floor_plan/test_bookable_rooms.py -v
```

Expected: **4 passed**.

- [ ] **Step 6: Smoke-test the seed against the dev DB**

```bash
rm -f instance/floor_plan.db
python -c "from app import create_app; create_app()"
sqlite3 instance/floor_plan.db "SELECT zone_key, label, capacity FROM bookable_rooms ORDER BY zone_key;"
```

Expected output:
```
boardroom-1|Workshop 1|20
boardroom-2|Workshop 2|20
conference-long|Workshop 3|20
global-theater|Theater|80
```

- [ ] **Step 7: Commit**

```bash
git add app/floor_plan/seed.py app/floor_plan/db.py tests/floor_plan/test_bookable_rooms.py
git commit -m "feat(floor-plan): seed four bookable rooms on first boot"
```

---

## Task 7: API — `GET /api/bookable-rooms`

**Files:**
- Modify: `app/floor_plan/blueprint.py` (append a new route block before the healthcheck)
- Create: `tests/floor_plan/test_bookable_api.py`

- [ ] **Step 1: Write the failing API test**

Create `tests/floor_plan/test_bookable_api.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/floor_plan/test_bookable_api.py -v
```

Expected: FAIL with 404.

- [ ] **Step 3: Implement the route**

In `app/floor_plan/blueprint.py`, near the top with the other model imports, add:

```python
from .models import Pin, BookableRoom
```

(Replace the existing `from .models import Pin` line.)

Just before the `# ---------- Healthcheck ----------` divider, add:

```python
# ---------- API: bookable rooms ----------

@floor_plan_bp.route("/api/bookable-rooms", methods=["GET"])
def api_bookable_rooms():
    """List the rooms that can be booked from the plan view."""
    rooms = BookableRoom.query.filter_by(is_active=1).order_by(BookableRoom.label).all()
    return jsonify([r.to_dict() for r in rooms])
```

- [ ] **Step 4: Run tests to verify pass**

```bash
pytest tests/floor_plan/test_bookable_api.py -v
```

Expected: **2 passed**.

- [ ] **Step 5: Commit**

```bash
git add app/floor_plan/blueprint.py tests/floor_plan/test_bookable_api.py
git commit -m "feat(floor-plan): GET /api/bookable-rooms"
```

---

## Task 8: API — `GET /api/rooms/<zone_key>/assets` (cross-DB read)

**Files:**
- Modify: `app/floor_plan/blueprint.py` (add another route)
- Create: `tests/floor_plan/test_assets_api.py`

- [ ] **Step 1: Write the failing test**

Create `tests/floor_plan/test_assets_api.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/floor_plan/test_assets_api.py -v
```

Expected: FAIL with 404 (route doesn't exist).

- [ ] **Step 3: Implement the route**

In `app/floor_plan/blueprint.py`, after the `api_bookable_rooms` route, add:

```python
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
```

- [ ] **Step 4: Run tests to verify pass**

```bash
pytest tests/floor_plan/test_assets_api.py -v
```

Expected: **4 passed**.

- [ ] **Step 5: Commit**

```bash
git add app/floor_plan/blueprint.py tests/floor_plan/test_assets_api.py
git commit -m "feat(floor-plan): GET /api/rooms/<zone>/assets (cross-DB read)"
```

---

## Task 9: Booking helper — `create_booking_ticket()`

**Files:**
- Create: `app/floor_plan/booking.py`
- Create: `tests/floor_plan/test_booking_api.py`
- Modify: `app/floor_plan/blueprint.py` (add POST `/api/bookings` route)

- [ ] **Step 1: Write the failing booking test**

Create `tests/floor_plan/test_booking_api.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/floor_plan/test_booking_api.py -v
```

Expected: FAIL with 404 (route missing).

- [ ] **Step 3: Implement the booking helper**

Create `app/floor_plan/booking.py`:

```python
"""Booking -> ticket bridge.

This is the ONE place where the floor_plan blueprint writes to sail.db.
It validates the booking payload, fetches the room metadata from
floor_plan.db, then opens a transaction against sail.db to insert the
ticket and audit row in a single commit.
"""
from datetime import date as _date, time as _time
from flask import session

from database import get_db, log_audit
from .models import BookableRoom


PURPOSE_MIN = 10
PURPOSE_MAX = 500


class BookingError(ValueError):
    """Raised on validation failure. Message is safe to surface to users."""


def _next_ticket_number(conn):
    """Replica of routes.tickets.next_ticket_number — keeps blueprint isolated."""
    row = conn.execute(
        "SELECT ticket_number FROM tickets ORDER BY id DESC LIMIT 1"
    ).fetchone()
    num = int(row["ticket_number"].split("-")[1]) + 1 if row else 1
    return f"TKT-{num:04d}"


def _validate(payload):
    """Return a normalised payload dict or raise BookingError."""
    if not isinstance(payload, dict):
        raise BookingError("Body must be a JSON object.")

    required = ("zone_key", "date", "start_time", "end_time", "attendees", "purpose")
    missing = [k for k in required if k not in payload]
    if missing:
        raise BookingError(f"Missing fields: {missing}")

    try:
        d = _date.fromisoformat(payload["date"])
    except (TypeError, ValueError):
        raise BookingError("Date must be YYYY-MM-DD.")
    if d < _date.today():
        raise BookingError("Date must be today or later.")

    try:
        start = _time.fromisoformat(payload["start_time"])
        end = _time.fromisoformat(payload["end_time"])
    except (TypeError, ValueError):
        raise BookingError("start_time / end_time must be HH:MM.")
    if end <= start:
        raise BookingError("end_time must be after start_time.")

    try:
        attendees = int(payload["attendees"])
    except (TypeError, ValueError):
        raise BookingError("attendees must be an integer.")
    if attendees < 1:
        raise BookingError("attendees must be >= 1.")

    purpose = (payload.get("purpose") or "").strip()
    if not (PURPOSE_MIN <= len(purpose) <= PURPOSE_MAX):
        raise BookingError(
            f"purpose must be {PURPOSE_MIN}-{PURPOSE_MAX} characters."
        )

    asset_ids = payload.get("asset_ids") or []
    if not isinstance(asset_ids, list):
        raise BookingError("asset_ids must be a list.")
    if not all(isinstance(x, int) for x in asset_ids):
        raise BookingError("asset_ids must be integers.")

    return {
        "zone_key": payload["zone_key"],
        "date": d.isoformat(),
        "start_time": start.strftime("%H:%M"),
        "end_time": end.strftime("%H:%M"),
        "attendees": attendees,
        "purpose": purpose,
        "asset_ids": asset_ids,
    }


def _build_description(room_label, location_code, p, asset_rows):
    lines = [
        f"Booking request for {room_label} ({location_code}).",
        "",
        f"Date: {p['date']}",
        f"Time: {p['start_time']} - {p['end_time']}",
        f"Attendees: {p['attendees']}",
        "Purpose:",
        f"  {p['purpose']}",
    ]
    if asset_rows:
        lines.append("")
        lines.append("Assets requested:")
        for a in asset_rows:
            lines.append(f"  - {a['asset_tag']} - {a['model_name']} ({a['condition']})")
    return "\n".join(lines)


def create_booking_ticket(payload):
    """Validate + insert a ticket. Returns {ticket_id, ticket_number}.

    Raises BookingError (caller maps to 400/404).
    """
    p = _validate(payload)

    room = BookableRoom.query.filter_by(zone_key=p["zone_key"], is_active=1).first()
    if room is None:
        raise BookingError(f"No bookable room for zone '{p['zone_key']}'.")

    user_id = session.get("user_id")
    if not user_id:
        raise BookingError("Login required.")

    with get_db() as conn:
        loc = conn.execute(
            "SELECT id, code, label FROM locations WHERE id = ?",
            (room.sail_location_id,),
        ).fetchone()
        if loc is None:
            raise BookingError("Room is not configured.")

        if p["asset_ids"]:
            placeholders = ",".join("?" * len(p["asset_ids"]))
            asset_rows = conn.execute(
                f"""SELECT a.id, a.asset_tag, a.condition, em.name AS model_name
                    FROM assets a JOIN equipment_models em ON em.id = a.equipment_model_id
                    WHERE a.id IN ({placeholders}) AND a.location_id = ?""",
                (*p["asset_ids"], room.sail_location_id),
            ).fetchall()
            if len(asset_rows) != len(p["asset_ids"]):
                raise BookingError("One or more assets are not in this room.")
        else:
            asset_rows = []

        ticket_number = _next_ticket_number(conn)
        title = f"Booking request: {room.label} on {p['date']}"
        description = _build_description(room.label, loc["code"], p, asset_rows)

        cursor = conn.execute(
            """INSERT INTO tickets
               (ticket_number, type, priority, status, submitted_by, title, description)
               VALUES (?, 'new_request', 'medium', 'open', ?, ?, ?)""",
            (ticket_number, user_id, title, description),
        )
        ticket_id = cursor.lastrowid
        log_audit(conn, "tickets", ticket_id, "create", changed_by=user_id)

    return {"ticket_id": ticket_id, "ticket_number": ticket_number}
```

- [ ] **Step 4: Add the POST route**

In `app/floor_plan/blueprint.py`, after `api_room_assets`, add:

```python
from .booking import create_booking_ticket, BookingError


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
```

- [ ] **Step 5: Run all booking tests**

```bash
pytest tests/floor_plan/ -v
```

Expected: model + seed + bookable-rooms API + assets API + booking API tests all pass.

- [ ] **Step 6: Commit**

```bash
git add app/floor_plan/booking.py app/floor_plan/blueprint.py tests/floor_plan/
git commit -m "feat(floor-plan): POST /api/bookings creates ticket in sail.db"
```

---

## Task 10: Frontend — zone relabel + bookable badge + asset list

**Files:**
- Modify: `app/floor_plan/static/floor_plan/js/floor-plan.js`
- Modify: `app/floor_plan/templates/floor_plan/index.html`
- Modify: `app/floor_plan/static/floor_plan/css/floor-plan.css`

This task has no automated test — frontend rendering is verified manually. Use safe DOM methods (`createElement`, `textContent`, `appendChild`); never assign `innerHTML` with server data.

- [ ] **Step 1: Relabel zones in the JS `ZONES` object**

In `app/floor_plan/static/floor_plan/js/floor-plan.js`, replace the four entries:

- The `boardroom-1` block (~line 77): `name: 'Boardroom A'` -> `name: 'Workshop 1'`; rewrite `desc` to "Bookable workshop room. Used for hands-on sessions, design reviews, and small-team training."
- The `boardroom-2` block (~line 87): `name: 'Boardroom B'` -> `name: 'Workshop 2'`; rewrite `desc` similarly.
- The `conference-long` block (~line 96): `name: 'Long Conference Room'` -> `name: 'Workshop 3'`; rewrite `desc` similarly.
- The `global-theater` block (~line 182): `name: 'Global Theater'` -> `name: 'Theater'`. Keep the existing desc but trim "Global" if it appears mid-sentence.

- [ ] **Step 2: Update SVG labels in the template**

In `app/floor_plan/templates/floor_plan/index.html`:

- Line 252 area: comment `<!-- Z8: Boardroom A -->` -> `<!-- Z8: Workshop 1 -->`; line 254 text content `Boardroom A` -> `Workshop 1`
- Line 260 area: `Boardroom B` -> `Workshop 2`
- Line 268 area: `Long Conference` -> `Workshop 3`
- Line 369 area: `Global Theater` -> `Theater`

- [ ] **Step 3: Add the bookable-room loader at top of JS**

Near the top of `floor-plan.js` (after `ZONES` is declared), add:

```js
// Bookable rooms (server source of truth). Populated on page load.
const BOOKABLE = new Map();   // zone_key -> {label, capacity, sail_location_id}

async function loadBookableRooms() {
  try {
    const r = await fetch(`${API_BASE}/bookable-rooms`);
    if (!r.ok) return;
    const list = await r.json();
    BOOKABLE.clear();
    list.forEach(room => BOOKABLE.set(room.zone_key, room));
    document.querySelectorAll('g.zone[data-z]').forEach(g => {
      if (BOOKABLE.has(g.dataset.z)) g.classList.add('zone--bookable');
    });
  } catch (e) {
    console.warn('bookable-rooms fetch failed', e);
  }
}
```

Call `loadBookableRooms()` from the existing page-init function (near where pins are loaded — search for `loadAuto` or the DOMContentLoaded block).

- [ ] **Step 4: Append CSS for the bookable indicator**

Append to `app/floor_plan/static/floor_plan/css/floor-plan.css`:

```css
/* Bookable room visual marker on the plan view */
.zone--bookable .hit { stroke: var(--accent); stroke-width: 2; }
.zone--bookable .label { fill: var(--accent); }

/* Side-panel "Bookable" badge */
.fp-bookable-badge {
  display: inline-block;
  padding: 2px 8px;
  background: var(--accent-soft);
  color: var(--accent);
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-left: 8px;
}

/* Asset list inside the side panel */
.fp-asset-list {
  margin-top: 12px;
  padding: 0;
  list-style: none;
  border-top: 1px solid var(--line-faint);
}
.fp-asset-list li {
  padding: 6px 0;
  border-bottom: 1px solid var(--line-faint);
  font-size: 13px;
  display: flex;
  justify-content: space-between;
  gap: 8px;
}
.fp-asset-list .asset-tag {
  font-family: ui-monospace, monospace;
  color: var(--ink-2);
}
.fp-asset-empty {
  padding: 8px 0;
  color: var(--ink-3);
  font-size: 13px;
}

/* "Request to book" button */
.fp-book-btn {
  margin-top: 12px;
  padding: 8px 16px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}
.fp-book-btn:hover { opacity: 0.9; }
.fp-book-btn[disabled] { opacity: 0.4; cursor: not-allowed; }
```

- [ ] **Step 5: Add panel slot elements in the template**

Find the side-panel detail container in `app/floor_plan/templates/floor_plan/index.html` (search for the existing zone-detail panel block). Inside the panel, ensure these three elements exist (add if missing — placement: header has the title, `extra` goes after the description, `actions` goes at the bottom of the panel):

```html
<div id="zone-detail-header"></div>           <!-- title and badge -->
<div id="zone-detail-extra"></div>            <!-- asset list slot -->
<div id="zone-detail-actions"></div>          <!-- request-to-book button slot -->
```

If the existing panel uses different IDs, prefer those; the JS in step 6 should be updated to match.

- [ ] **Step 6: Render the badge + asset list in the side panel (safe DOM only)**

Find the `showZone(key)` function in `floor-plan.js` (the function that populates the side panel when a zone is clicked). After it sets the title/desc/capacity, add:

```js
  const room = BOOKABLE.get(key);
  const headerEl = document.getElementById('zone-detail-header');
  const oldBadge = headerEl.querySelector('.fp-bookable-badge');
  if (oldBadge) oldBadge.remove();
  if (room) {
    const badge = document.createElement('span');
    badge.className = 'fp-bookable-badge';
    badge.textContent = 'Bookable';
    headerEl.appendChild(badge);
    renderRoomAssets(key);
    renderBookButton(key);
  } else {
    clearRoomAssets();
    clearBookButton();
  }
```

Add the helper functions further down in `floor-plan.js`. **All server data flows through `textContent`** — no string-concatenated HTML:

```js
function _emptyAssetMessage(text) {
  const p = document.createElement('p');
  p.className = 'fp-asset-empty';
  p.textContent = text;
  return p;
}

async function renderRoomAssets(zoneKey) {
  const container = document.getElementById('zone-detail-extra');
  container.replaceChildren(_emptyAssetMessage('Loading assets…'));
  let list;
  try {
    const r = await fetch(`${API_BASE}/rooms/${encodeURIComponent(zoneKey)}/assets`);
    if (!r.ok) {
      container.replaceChildren(_emptyAssetMessage('No assets in this room.'));
      return;
    }
    list = await r.json();
  } catch (e) {
    container.replaceChildren(_emptyAssetMessage('Could not load assets.'));
    return;
  }
  if (!list.length) {
    container.replaceChildren(_emptyAssetMessage('No assets in this room.'));
    return;
  }
  const ul = document.createElement('ul');
  ul.className = 'fp-asset-list';
  ul.dataset.zone = zoneKey;
  list.forEach(a => {
    const li = document.createElement('li');
    li.dataset.assetId = String(a.id);

    const left = document.createElement('span');
    left.textContent = (a.model_name || '') + (a.brand ? ' ' + a.brand : '');

    const right = document.createElement('span');
    right.className = 'asset-tag';
    right.textContent = a.asset_tag || '';

    li.appendChild(left);
    li.appendChild(right);
    ul.appendChild(li);
  });
  container.replaceChildren(ul);
}

function clearRoomAssets() {
  const c = document.getElementById('zone-detail-extra');
  if (c) c.replaceChildren();
}

function renderBookButton(zoneKey) {
  const slot = document.getElementById('zone-detail-actions');
  if (!slot) return;
  slot.replaceChildren();
  const btn = document.createElement('button');
  btn.className = 'fp-book-btn';
  btn.textContent = 'Request to book';
  btn.addEventListener('click', () => openBookingModal(zoneKey));
  slot.appendChild(btn);
}

function clearBookButton() {
  const slot = document.getElementById('zone-detail-actions');
  if (slot) slot.replaceChildren();
}

function openBookingModal(zoneKey) {
  // Replaced in Task 11.
  console.log('open booking modal', zoneKey);
}
```

- [ ] **Step 7: Smoke test in the browser**

```bash
python app.py
```

Logged in:
- `/floor-plan/` shows the plan
- The four zones (Workshop 1/2/3, Theater) have a red outline (`.zone--bookable` style)
- Clicking Workshop 1 shows the "Bookable" badge in the panel header
- The panel lists assets currently in WORKSHOP-1 location (sail.db has assets in this location since the import script populated it)
- Clicking a non-bookable zone (e.g. Pod 1) shows no badge, no asset list, no button
- A "Request to book" button is visible on bookable zones (clicking it logs to console for now)

- [ ] **Step 8: Commit**

```bash
git add app/floor_plan/static app/floor_plan/templates
git commit -m "feat(floor-plan): relabel zones, mark bookable rooms, render asset list"
```

---

## Task 11: Booking modal + form submission

**Files:**
- Modify: `app/floor_plan/templates/floor_plan/index.html` (add modal markup)
- Modify: `app/floor_plan/static/floor_plan/css/floor-plan.css` (modal styles)
- Modify: `app/floor_plan/static/floor_plan/js/floor-plan.js` (replace stub `openBookingModal`)

No automated test — this wires already-tested API endpoints into a UI.

- [ ] **Step 1: Add the modal markup to the template**

In `app/floor_plan/templates/floor_plan/index.html`, just before `</body>`:

```html
<div id="fp-booking-modal" class="fp-modal" hidden>
  <div class="fp-modal-backdrop" data-close></div>
  <div class="fp-modal-card" role="dialog" aria-labelledby="fp-modal-title">
    <header class="fp-modal-header">
      <h2 id="fp-modal-title">Request to book</h2>
      <button class="fp-modal-close" data-close aria-label="Close">x</button>
    </header>
    <form id="fp-booking-form">
      <input type="hidden" name="zone_key">

      <label>Date <input name="date" type="date" required></label>
      <div class="fp-row">
        <label>Start <input name="start_time" type="time" required></label>
        <label>End <input name="end_time" type="time" required></label>
      </div>
      <label>Attendees <input name="attendees" type="number" min="1" value="1" required></label>
      <label>Purpose
        <textarea name="purpose" minlength="10" maxlength="500" rows="3" required></textarea>
      </label>

      <fieldset class="fp-asset-pick">
        <legend>Assets needed (optional)</legend>
        <div id="fp-asset-checks">
          <p class="fp-asset-empty">Select a room first.</p>
        </div>
      </fieldset>

      <div class="fp-form-error" id="fp-booking-error" hidden></div>
      <footer class="fp-modal-footer">
        <button type="button" class="fp-btn-ghost" data-close>Cancel</button>
        <button type="submit" class="fp-book-btn">Submit request</button>
      </footer>
    </form>
  </div>
</div>
```

(All inserted markup is static — no server data interpolation, so it is XSS-safe even though it appears as static HTML in the template.)

- [ ] **Step 2: Append modal CSS**

Append to `app/floor_plan/static/floor_plan/css/floor-plan.css`:

```css
.fp-modal[hidden] { display: none; }
.fp-modal {
  position: fixed; inset: 0; z-index: 1000;
  display: grid; place-items: center;
}
.fp-modal-backdrop {
  position: absolute; inset: 0;
  background: rgba(0,0,0,0.45);
}
.fp-modal-card {
  position: relative;
  background: var(--paper);
  color: var(--ink);
  width: min(540px, 92vw);
  max-height: 90vh; overflow: auto;
  border-radius: 12px;
  box-shadow: var(--shadow);
  padding: 24px;
}
.fp-modal-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px;
}
.fp-modal-header h2 { font-size: 18px; font-weight: 500; margin: 0; }
.fp-modal-close {
  background: none; border: none; font-size: 24px; cursor: pointer; color: var(--ink-2);
}
#fp-booking-form label {
  display: block; margin-bottom: 12px; font-size: 13px; color: var(--ink-2);
}
#fp-booking-form input[type="date"],
#fp-booking-form input[type="time"],
#fp-booking-form input[type="number"],
#fp-booking-form textarea {
  display: block; width: 100%; margin-top: 4px;
  padding: 8px 10px; font-size: 14px;
  border: 1px solid var(--line-soft); border-radius: 6px;
  background: var(--bg); color: var(--ink);
  font-family: inherit;
}
#fp-booking-form .fp-row {
  display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
}
.fp-asset-pick {
  border: 1px solid var(--line-faint); border-radius: 8px;
  padding: 12px; margin-bottom: 16px;
}
.fp-asset-pick legend {
  padding: 0 6px; font-size: 12px; color: var(--ink-3);
}
.fp-asset-pick label {
  display: flex; align-items: center; gap: 8px;
  margin: 0; padding: 4px 0; font-size: 13px;
}
.fp-modal-footer {
  display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px;
}
.fp-btn-ghost {
  background: transparent; border: 1px solid var(--line-soft);
  color: var(--ink-2); padding: 8px 16px; border-radius: 6px;
  cursor: pointer; font-size: 13px;
}
.fp-form-error {
  background: rgba(200,54,45,0.10);
  color: var(--bad);
  padding: 8px 12px; border-radius: 6px;
  font-size: 13px; margin-bottom: 12px;
}
```

- [ ] **Step 3: Replace the stub `openBookingModal` in JS (safe DOM only)**

In `floor-plan.js`, replace the stub `openBookingModal(zoneKey)` with:

```js
function openBookingModal(zoneKey) {
  const modal = document.getElementById('fp-booking-modal');
  const form = document.getElementById('fp-booking-form');
  const checks = document.getElementById('fp-asset-checks');
  const errorBox = document.getElementById('fp-booking-error');

  form.reset();
  errorBox.hidden = true;
  errorBox.textContent = '';
  form.elements['zone_key'].value = zoneKey;

  // Default date = today, min = today
  const today = new Date().toISOString().slice(0, 10);
  form.elements['date'].value = today;
  form.elements['date'].min = today;

  // Build asset checkboxes from the panel's already-rendered list
  checks.replaceChildren();
  const ul = document.querySelector('.fp-asset-list');
  if (ul && ul.dataset.zone === zoneKey && ul.children.length) {
    Array.from(ul.querySelectorAll('li')).forEach(li => {
      const id = Number(li.dataset.assetId);
      const tagEl = li.querySelector('.asset-tag');
      const labelText = li.firstElementChild ? li.firstElementChild.textContent.trim() : '';
      const tagText = tagEl ? tagEl.textContent : '';

      const lbl = document.createElement('label');
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.name = 'asset_ids';
      cb.value = String(id);
      cb.id = `fp-asset-${id}`;
      lbl.appendChild(cb);

      const text = document.createTextNode(' ' + labelText + ' ');
      lbl.appendChild(text);

      const tag = document.createElement('span');
      tag.className = 'asset-tag';
      tag.textContent = tagText;
      lbl.appendChild(tag);

      checks.appendChild(lbl);
    });
  } else {
    const p = document.createElement('p');
    p.className = 'fp-asset-empty';
    p.textContent = 'No assets in this room.';
    checks.appendChild(p);
  }

  modal.hidden = false;
}

function closeBookingModal() {
  document.getElementById('fp-booking-modal').hidden = true;
}

// Close on backdrop / [data-close] click
document.addEventListener('click', e => {
  if (e.target.closest('#fp-booking-modal [data-close]')) closeBookingModal();
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeBookingModal();
});

// Submit
document.getElementById('fp-booking-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const form = e.currentTarget;
  const fd = new FormData(form);
  const errorBox = document.getElementById('fp-booking-error');
  errorBox.hidden = true;
  errorBox.textContent = '';
  const submitBtn = form.querySelector('button[type="submit"]');
  submitBtn.disabled = true;

  const payload = {
    zone_key: fd.get('zone_key'),
    date: fd.get('date'),
    start_time: fd.get('start_time'),
    end_time: fd.get('end_time'),
    attendees: Number(fd.get('attendees')),
    purpose: fd.get('purpose'),
    asset_ids: fd.getAll('asset_ids').map(Number),
  };

  try {
    const r = await fetch(`${API_BASE}/bookings`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    const body = await r.json();
    if (!r.ok) {
      errorBox.textContent = body.error || 'Booking failed.';
      errorBox.hidden = false;
      return;
    }
    closeBookingModal();
    toast(`Booking request submitted - ticket ${body.ticket_number}`);
  } catch (err) {
    errorBox.textContent = 'Network error. Please try again.';
    errorBox.hidden = false;
  } finally {
    submitBtn.disabled = false;
  }
});
```

(`toast()` already exists in `floor-plan.js` from sail-incubation. The error message rendered into `errorBox` uses `textContent`, so server messages cannot inject HTML.)

- [ ] **Step 4: Manual smoke test**

```bash
python app.py
```

Logged in:
- `/floor-plan/` -> click Workshop 1 -> click "Request to book"
- Modal opens with today's date prefilled, asset checkboxes for Workshop-1 assets
- Fill: Start `09:00`, End `11:00`, Attendees `8`, Purpose `Test booking from feature branch.`
- Submit -> toast "Booking request submitted - ticket TKT-NNNN"
- Visit `/tickets/list` (admin) -> the new ticket appears with type `new_request`, status `open`

Negative tests:
- Submit with End < Start -> red error in modal: "end_time must be after start_time."
- Submit with Purpose `hi` -> "purpose must be 10-500 characters."
- Submit selecting an asset, then deselect, then change room and re-open modal -> previous selection cleared.

- [ ] **Step 5: Commit**

```bash
git add app/floor_plan/templates app/floor_plan/static
git commit -m "feat(floor-plan): booking modal with asset multi-select"
```

---

## Task 12: Final smoke test + branch readiness

**Files:** none

- [ ] **Step 1: Run the full test suite**

```bash
pytest app/floor_plan/tests tests/floor_plan -v
```

Expected: 15 (vendored) + 4 (model+seed) + 2 (bookable API) + 4 (assets API) + 6 (booking API) = **31 passed**.

- [ ] **Step 2: Smoke check every blueprint in sail-project**

Boot the app and click through:

- `/` - dashboard renders
- `/inventory` - equipment list renders
- `/inventory/manage` - admin asset list
- `/tickets/mine` - user tickets
- `/tickets/list` - admin tickets queue (new booking ticket from Task 11 visible)
- `/employees` - employees list
- `/reports/inventory` - inventory report
- `/reports/tickets` - tickets report
- `/help` - help guide
- `/floor-plan/` - floor plan + booking flow

The most likely failure mode is CSS bleed (the blueprint's CSS is not namespaced). Confirm `/inventory` looks correct **after** visiting `/floor-plan/` in the same session — if pages render with stripped margins or wrong fonts, the blueprint's global selectors are bleeding through. Mitigation: ensure the blueprint's `index.html` does not extend `base.html` (it has its own `<head>`).

- [ ] **Step 3: Confirm the rollback plan works**

```bash
git checkout main
ls instance/
# floor_plan.db file may still be on disk but not loaded by the app on main
python app.py    # should run as before, no /floor-plan route
```

Then return to the feature branch:

```bash
git checkout feature/floor-plan-booking
```

- [ ] **Step 4: No final commit needed.** The branch is ready for review.

Tell the user the branch is ready and ask whether to merge to main, open a PR, or hand off for ops-team smoke testing first.

---

## Open follow-ups (not in v1)

- Calendar view of confirmed bookings per room
- Conflict detection at submit time
- Promote booking metadata into dedicated ticket columns
- Merge `floor_plan.db` tables into `sail.db`
- Auth gating on pin edits (admin/manager only)
- Editable bookable_rooms admin page (capacity, label, is_active)
- Namespace the blueprint's CSS under a wrapper class so `index.html` can extend `base.html`
