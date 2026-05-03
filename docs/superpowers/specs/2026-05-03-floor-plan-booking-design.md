# Floor Plan + Room Booking — Design Spec

## Summary

Vendor-copy the `sail-incubation` Flask blueprint into `sail-project` on a feature branch, then mark four rooms (Workshop 1, Workshop 2, Workshop 3, Theater) as bookable. Clicking a bookable room opens a request form; submitting it creates a ticket in the existing tickets queue, which the operations team handles to confirm the booking. The room's existing assets — joined via `assets.location_id` — are shown in the panel and may be selected as part of the request.

This deliberately avoids reintroducing the full reserve→approve→checkout→return booking module that was previously removed from sail-project. Bookings ride on the existing tickets workflow.

In v1, the floor plan blueprint keeps its own SQLite file (`floor_plan.db`) so the existing `sail.db` is untouched until we explicitly merge the booking-related tables.

## Motivation

The SAIL portal's existing IT-asset workflow has no way to request a physical room, and the operations team coordinates Workshop and Theater bookings ad hoc over chat and email. The sail-incubation project already produced a working interactive floor plan; reusing it as the visual entry point gives users a clear "click the room I want" experience and gives ops a tracked, queued source of truth without building a reservation system from scratch.

## Out of scope (v1)

- Approve/reject UI separate from the tickets queue — the existing ticket status flow (`open → in_progress → resolved → closed`) doubles as the booking lifecycle.
- Calendar / availability view — collisions are surfaced by the ops team while triaging tickets, not enforced by the system.
- Recurring bookings.
- Email confirmations beyond what the existing `notify_ticket_*` helpers already send.
- Auth changes — the floor plan inherits sail-project's session-based `before_request` gate.
- Editing pin coordinates on the iso authoring view: pins keep working as in sail-incubation, just for visual annotation. Booking is driven entirely from the plan view.
- Merging `floor_plan.db` into `sail.db`. That is step 5 of the build order, deferred until everything else has been click-tested.

## Integration mechanism

**Vendor-copy on a feature branch.** From `sail-project`'s `main`:

```
git checkout -b feature/floor-plan-booking
cp -r ../sail-incubation/app/floor_plan app/floor_plan
```

The blueprint is registered in `app.py`'s `create_app()` alongside the existing blueprints:

```python
from app.floor_plan import floor_plan_bp, init_floor_plan
app.register_blueprint(floor_plan_bp, url_prefix="/floor-plan")
init_floor_plan(app)        # standalone mode → uses floor_plan.db
```

A nav link to `/floor-plan/` is added to `templates/base.html` (visible to authenticated users only — the global `before_request` already enforces this).

The sail-incubation repo is not deleted, but no longer feeds the running app; it remains as the upstream of the v0.2 blueprint. Future edits happen in sail-project. We do not use a git submodule, pip install, or runtime symlink.

## Architecture — two databases, coexisting

The floor plan blueprint is built on SQLAlchemy 2.0 (its `db.py` and `models.py`); sail-project is built on raw `sqlite3` with the `database.get_db()` context manager. In v1 they do not interact at the DB layer.

| File | Library | Tables |
|---|---|---|
| `sail.db` (existing) | raw `sqlite3` via `database.get_db()` | employees, assets, equipment_models, locations, tickets, audit_log, … |
| `floor_plan.db` (new) | SQLAlchemy via `init_floor_plan(app)` | `floor_plan_pins`, `bookable_rooms` |

The booking *handoff* between the two — "click a room, create a ticket" — happens at the application layer: a new POST endpoint in the floor plan blueprint reads the room metadata from `floor_plan.db`, validates the form, then opens a `with get_db() as conn:` against `sail.db` to insert the ticket and audit row.

This is the ONE place the two layers cross. It is implemented in a single helper (`create_booking_ticket()`) so the seam is visible and testable.

### Module layout after the copy

```
sail-project/
├── app/
│   └── floor_plan/                 ← copied from sail-incubation
│       ├── __init__.py
│       ├── blueprint.py            ← edited: + booking routes, + ticket bridge
│       ├── db.py
│       ├── models.py               ← edited: + BookableRoom model
│       ├── booking.py              ← new: form validation + ticket bridge
│       ├── templates/floor_plan/
│       │   └── index.html          ← edited: bookable badge in panel, request form
│       └── static/floor_plan/
│           ├── css/floor-plan.css  ← edited: bookable-zone styling
│           ├── js/floor-plan.js    ← edited: zone relabel + bookable wiring
│           └── images/sail-isometric.jpg
├── instance/floor_plan.db          ← created on first request
├── app.py                          ← edited: register blueprint, add nav link
├── templates/base.html             ← edited: nav link
└── …
```

## Bookable rooms — data model

New table in `floor_plan.db`:

```sql
CREATE TABLE bookable_rooms (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_key      TEXT NOT NULL UNIQUE,    -- floor-plan zone, e.g. 'global-theater'
    sail_location_id INTEGER NOT NULL,     -- references sail.db locations(id) — soft FK
    label         TEXT NOT NULL,           -- "Workshop 1", "Theater"
    capacity      INTEGER,                 -- nullable; informational
    is_active     INTEGER DEFAULT 1,
    created_at    TEXT DEFAULT (datetime('now'))
);
```

`sail_location_id` is a *soft* foreign key — SQLite cross-database FKs are not enforced. The application layer is responsible for keeping it valid; if a referenced location is deleted in sail.db, the booking form on that room flashes "Room is not configured." and disables the submit button.

### Seed (4 rows)

| zone_key | sail_location_id | label | capacity |
|---|---|---|---|
| `global-theater` | 11 (DIGITAL-THEATER) | Theater | 80 |
| `boardroom-1`    | 38 (WORKSHOP-1)      | Workshop 1 | 20 |
| `boardroom-2`    | 39 (WORKSHOP-2)      | Workshop 2 | 20 |
| `conference-long`| 40 (WORKSHOP-3)      | Workshop 3 | 20 |

Capacities are placeholder values — they may be edited later via a small admin route or by hand. They are informational only; the form does not enforce attendees ≤ capacity in v1 (it warns).

### Zone relabeling

The four zone keys above keep their identity in code (used as DB keys, JS lookup keys, template selectors), but their **display labels** change in `static/floor_plan/js/floor-plan.js`:

| zone_key | Old label | New label |
|---|---|---|
| `global-theater` | Global Theater | Theater |
| `boardroom-1` | Boardroom 1 | Workshop 1 |
| `boardroom-2` | Boardroom 2 | Workshop 2 |
| `conference-long` | Long Conference | Workshop 3 |

The schematic SVG label `<text>` elements in `templates/floor_plan/index.html` are updated to match. Zone descriptions (`desc` field in `ZONES`) are rewritten to reflect the rooms' real purpose.

### Bookable indication on the plan

A bookable room is visually distinct on the plan view: a small badge `Bookable` appears in the side panel header and the zone fill gets a subtle accent (e.g. left border in the panel + a badge dot on the SVG). Non-bookable zones look exactly as they do today.

The `Bookable` badge and the "Request to book" button are rendered conditionally in JS based on the `bookable_rooms` list fetched once on page load (`GET /floor-plan/api/bookable-rooms`). Zones not in that list show their existing read-only panel.

## Booking flow

```
User clicks bookable zone on plan view
        │
        ▼
Side panel shows:
  • Room name + capacity
  • Assets currently in this room  (read-only list, fetched from /floor-plan/api/rooms/<zone_key>/assets)
  • [Request to book]  button
        │
        ▼
Modal form (date, start, end, attendees, purpose, asset multi-select)
        │
        ▼  POST /floor-plan/api/bookings
Validate → open sail.db tx → INSERT ticket + audit_log → COMMIT
        │
        ▼
Toast "Booking request submitted — ticket #TKT-NNNN" with link to ticket detail
```

### API endpoints (new)

All under `/floor-plan/api/`:

| Method | Path | Body | Returns |
|---|---|---|---|
| `GET` | `/bookable-rooms` | — | `[{zone_key, label, capacity, sail_location_id}, …]` |
| `GET` | `/rooms/<zone_key>/assets` | — | `[{asset_id, asset_tag, model_name, status, condition}, …]` |
| `POST` | `/bookings` | booking payload (see below) | `{ticket_id, ticket_number}` (201) |

The existing pin endpoints (`/api/pins`, `/api/healthz`) remain unchanged.

### Asset list query

`/rooms/<zone_key>/assets` runs against **sail.db** via `get_db()`:

```sql
SELECT a.id, a.asset_tag, a.status, a.condition,
       em.name AS model_name, em.brand
FROM assets a
JOIN equipment_models em ON em.id = a.equipment_model_id
WHERE a.location_id = ?     -- the bookable_rooms.sail_location_id
ORDER BY em.name, a.asset_tag;
```

The `zone_key → sail_location_id` translation happens via a single read of `floor_plan.db` first. Both reads are inside the same request handler — there is no transaction spanning the two databases.

## Booking form

Modal shown over the plan view. Fields:

| Field | Input | Validation |
|---|---|---|
| Date | `<input type="date">` | required, today or later |
| Start time | `<input type="time">` | required |
| End time | `<input type="time">` | required, > start time |
| Attendees | `<input type="number" min="1">` | required, integer ≥ 1; warning (not error) if > room capacity |
| Purpose | `<textarea>` | required, 10-500 chars |
| Assets needed | multi-select checkboxes | optional; only IDs from this room's asset list are accepted server-side |

Submit button is disabled while the request is in flight. On success the modal closes, a toast appears with the ticket number, and the panel updates to show "Last request: ticket #TKT-NNNN — open" until the page is reloaded.

## Ticket creation

The booking POST handler (`booking.create_booking_ticket`) opens a `with get_db() as conn:` and inserts:

| Column | Value |
|---|---|
| `ticket_number` | next auto-generated `TKT-NNNN` via the existing `routes.tickets.next_ticket_number(conn)` helper |
| `type` | `'new_request'` |
| `priority` | `'medium'` |
| `status` | `'open'` |
| `submitted_by` | `g.user.id` |
| `title` | `f"Booking request: {room.label} on {date}"` |
| `description` | structured block (see below) |
| `asset_id` | `NULL` (the request is for the room, not a single asset; specific assets requested go in the description) |

Description body:

```
Booking request for {room.label} ({room.code}).

Date: 2026-05-12
Time: 09:00 – 11:00
Attendees: 12
Purpose:
  Quarterly UX review session.

Assets requested:
  • SAIL-0042 — Smart Board (good)
  • SAIL-0107 — Workstation (good)
```

A single `audit_log` row is written in the same transaction with `action='create'`, `table='tickets'`. Existing `notify_ticket_created` is called after commit.

The form does **not** put booking metadata in dedicated columns. v1 keeps the schema unchanged; if booking volume grows we can promote the parsed fields to columns later (out of scope here).

## Permissions

The floor plan and the booking form inherit sail-project's session gate via `before_request`. No additional role checks in v1: any authenticated employee can submit a booking request. The receiving ticket is visible per the existing tickets permission rules.

The pin authoring view (already part of sail-incubation) keeps its current behaviour — anyone authenticated can drop and edit pins. Restricting pin edits to admins is deferred (`docs/INTEGRATION.md` section 6 in sail-incubation has a recipe).

## Don't-disrupt safeguards

This is the spec's reason-for-being. Concretely:

1. **Feature branch only.** All changes land on `feature/floor-plan-booking`. `main` is untouched.
2. **Backup `sail.db`** before the first run on the branch (`python backup_db.py` keeps the last 10 in `backups/`).
3. **Separate `floor_plan.db`** in v1 — no DDL against `sail.db` until step 5.
4. **One additive ticket insert** is the only mutation against `sail.db` from the new code, and it goes through the same `get_db()` + `log_audit()` path as every other ticket insert in the app.
5. **Soft FK only** between `bookable_rooms.sail_location_id` and `locations.id` — a missing referent flashes a friendly error, never a 500.
6. **Manual smoke test before merging the branch:**
   - Plan view loads, all 26 zones still clickable
   - 4 bookable rooms show the badge + button
   - Asset list shows real assets from sail.db (not mock data)
   - Submitting a booking creates a ticket visible in `/tickets`
   - Existing inventory, employees, reports, dashboard pages still work
   - `pytest` (sail-incubation's 15 tests) still passes when run from `app/floor_plan/` (we keep its `tests/` next to the blueprint copy)
7. **Rollback plan:** `git checkout main` removes the blueprint, the nav link, and stops creating `floor_plan.db`. Tickets created during testing remain in `sail.db` but are normal tickets with the existing schema — no orphans.

## Build order

Each step ships as its own commit on `feature/floor-plan-booking` and is verified before moving on.

1. **Copy blueprint, register, run.** Confirm `/floor-plan/` loads. Pins work. Existing app unchanged. (No `bookable_rooms` yet.)
2. **Add `bookable_rooms` table + seed + visual badge.** Bookable zones show the badge. No request flow yet.
3. **Side-panel "Assets in this room" list** (read-only join via `location_id`).
4. **Booking form + POST `/bookings` + ticket creation.** Full end-to-end flow.
5. **Optional: merge `floor_plan.db` into `sail.db`** as a follow-up. Out of scope for v1; tracked separately.

Step 1 is two commits: one for the copy, one for the registration. This gives a clean revert point if the SQLAlchemy + sqlite3 coexistence misbehaves.

## Risks and unknowns

- **Two ORMs in one app.** SQLAlchemy and raw `sqlite3` will both be imported. They do not share a connection or transaction; the seam is the booking POST handler. Watched-for failure modes: SQLAlchemy holding a write lock on `floor_plan.db` while the ticket insert is in flight (different file, should not contend), or import-order issues if `db.create_all()` runs during `app.py` import (it runs in `init_floor_plan(app)` after `create_app()` returns).
- **CSS collisions are real, not hypothetical.** The blueprint's `floor-plan.css` is **not** prefixed/namespaced — it ships global `* { margin: 0; padding: 0; box-sizing: border-box }`, `html, body { … }`, and CSS variables on `:root`. sail-project's `static/style.css` also defines a `:root` token system with light/dark themes and global resets. Loading both on the same page would visibly break sail-project. Mitigation in step 1: the floor-plan template uses its own minimal `<head>` and does **not** extend `base.html`, so the CSS is loaded ONLY on `/floor-plan/*` pages. Verify in step 1 that navigating to `/floor-plan/`, then to `/inventory`, then back keeps both pages looking correct. (Long-term fix: scope the blueprint's selectors under a wrapper class — out of scope for v1.)
- **Authentication on the floor plan API.** sail-incubation's pin API is unauthenticated by default. After step 1, requests that hit `/floor-plan/api/pins` from outside the session may 200 without a logged-in user. The global `before_request` redirects unauthenticated users to `/login` for HTML routes; we need to confirm it covers JSON routes too (it should — there is no `static`-style exemption for `/floor-plan/api/`).
- **Capacity is informational only.** Two requests for the same room at overlapping times both succeed and both produce tickets. Conflict resolution is human (ops team triages). Acceptable for v1; flagged so we don't promise availability enforcement.
- **Tickets schema currently has no `booking_*` columns.** The whole booking payload lives in `description` text. This is deliberate (zero-schema-change-to-sail.db) but means filtering "show me booking tickets" relies on `type='new_request'` + title prefix. If volume justifies it later, promote to dedicated columns.

## Follow-ups (not in v1)

- Calendar view of confirmed bookings (resolved tickets) per room.
- Conflict detection at submit time.
- Recurring bookings.
- Promote booking fields out of `description` into dedicated columns on `tickets` (or a side table).
- Merge `floor_plan.db` tables into `sail.db`.
- Auth gating on pin edits (admin / manager only).
- Make capacity, label, and `is_active` editable via an admin page.
