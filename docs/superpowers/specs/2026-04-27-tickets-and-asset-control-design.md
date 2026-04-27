# Tickets + Asset Control — Design Spec

**Date:** 2026-04-27
**Status:** Specced (awaiting plan)
**Scope:** Re-scope the live SAIL app to its core: ticketing and asset control for a 4-user team. Hide the booking flow without deleting it.

## 1 — Purpose

SAIL currently ships three flows: **inventory**, **bookings**, and **tickets**. In day-to-day use the team needs only two of them — track what assets exist and where they are, and let employees raise tickets to admins. The booking/approve/checkout/return cycle adds friction the 4-user team does not need.

This spec re-scopes the live app to:

1. **Asset control.** Admins maintain the asset list and assign individual units to employees directly. Anyone can see what is available and who is holding what.
2. **Tickets.** Employees raise tickets, admins triage and resolve them. The existing ticket module is kept as-is.
3. **Bookings hidden, not deleted.** The booking module is gated behind a single feature flag so it can be re-enabled later without re-implementation.

## 2 — Users

The system is operated by exactly four people. Accounts are seeded at install time; self-registration is removed from the UI.

| Email                          | Role     |
|--------------------------------|----------|
| airandblueamt@gmail.com        | admin    |
| m.shaikh@amt-arabia.net        | admin    |
| omar.bawadod@aramco.com        | employee |
| ali.almatrood@aramco.com       | employee |

Both admins receive ticket notifications. Employees receive notifications about their own tickets only.

## 3 — Non-goals

- Booking, reservation, approval, or checkout flow in the UI. The tables stay in the schema, the routes stay in the codebase, but nothing surfaces the feature to users.
- Self-registration. The `/register` route is removed from the nav. The four accounts are pre-seeded; new users are created by an admin from the Employees page.
- Per-employee asset history view. The existing `audit_log` already records every `assigned_to` change with timestamp and actor — no separate history page is built.
- Email-as-password change. Auth stays session-based and email-only.
- Reports CSV redesign. The reports page stays; booking-related sections inside it are gated by the same flag.

## 4 — Architecture

### 4.1 Feature flag

A single boolean in `config.py`:

```python
BOOKINGS_ENABLED = False
```

Exposed to Jinja via an `app.context_processor` as `bookings_enabled`. Every booking-related UI element is wrapped in `{% if bookings_enabled %}`. Every booking-related DB query in non-booking routes is guarded by the same Python boolean. Flipping the flag to `True` restores the full booking experience with no code changes.

`routes/bookings.py` registers a `before_request` hook that calls `abort(404)` when the flag is off. The blueprint stays registered so URL-building (`url_for('bookings.…')`) still resolves at template parse time even on pages that don't render those links.

### 4.2 Asset assignment

The `assets.assigned_to` column already exists (FK to `employees.id`, nullable). No schema migration is required.

Behavior:

- The admin asset edit form gains an **"Assign to"** dropdown listing all employees plus an "— Unassigned —" option.
- On save, the route normalizes status:
  - `assigned_to` set **and** current status is `available` → status flips to `in_use`.
  - `assigned_to` cleared **and** current status is `in_use` → status flips to `available`.
  - `maintenance`, `damaged`, `decommissioned` are not auto-overridden; the admin sets those explicitly.
- The change is written through the normal `with get_db() as conn:` block, with `log_audit(conn, 'assets', asset_id, 'assign', …)` capturing the before/after holder in the same transaction.

### 4.3 Inventory views

Two distinct views, distinguished by role:

| View              | Audience  | Behavior                                                                 |
|-------------------|-----------|--------------------------------------------------------------------------|
| `/inventory`      | employee  | Read-only **Equipment Catalog**. All models, all assets. Columns: tag, model, location, status, holder. No "Reserve" button. No `is_bookable` filter. |
| `/inventory/admin`| admin     | Existing full CRUD page. Adds the "Assign to" dropdown described in 4.2.  |

The `is_bookable` column on `equipment_models` is left alone — admins keep the toggle in the model form so the data stays correct for if/when bookings re-enable.

### 4.4 Dashboard

Per-role tiles, with all booking tiles gated by the flag:

- **Admin dashboard:** open tickets count · tickets by priority · assets in use vs available · recent tickets (last 5).
- **Employee dashboard:** my open tickets · "Raise a Ticket" button · assets currently assigned to me.

The booking action card, the "Pending Bookings" stat, and the "Recent Bookings" panel are all wrapped in `{% if bookings_enabled %}`. The corresponding queries in `routes/dashboard.py` are skipped when the flag is off — no point paying for them.

### 4.5 Tickets

Unchanged. The existing module already handles type, priority, assignment, comments, and the kanban/SLA board. The only change is the notification routing:

- New ticket created → email both admins.
- Ticket status changed or admin comment added → email the ticket creator (always) and the assignee (if different).

These hooks already exist in `email_service.py` for booking notifications; the same pattern is reused.

### 4.6 Reports

The reports page stays. Booking-specific blocks (`bookings_created` stat, top-booked-models table, recent-bookings list) are wrapped in `{% if bookings_enabled %}`. The corresponding SELECTs in `routes/reports.py` are short-circuited when the flag is off.

## 5 — Data flow

Assignment, end to end:

```
Admin opens /inventory/admin
  → clicks edit on asset SAIL-16038
  → picks Omar from "Assign to" dropdown
  → POST /inventory/admin/<id>/edit
      with get_db() as conn:
        UPDATE assets SET assigned_to=?, status='in_use', updated_at=now()
        log_audit(conn, 'assets', id, 'assign',
                  before={'assigned_to': null, 'status': 'available'},
                  after ={'assigned_to': 3,    'status': 'in_use'})
  → redirect back to /inventory/admin
  → Omar's dashboard "assets assigned to me" tile now shows SAIL-16038
  → Employee /inventory view shows holder="Omar Bawadod" on that row
```

Ticket, end to end:

```
Omar opens /tickets/new → fills form → submit
  → INSERT into tickets (created_by=Omar, status='open')
  → email_service.notify_new_ticket(['airandblueamt@gmail.com', 'm.shaikh@amt-arabia.net'])
  → admin opens /tickets, assigns to themselves, comments
  → email_service.notify_ticket_update(omar.email)
```

## 6 — Error handling

- **Email send failures** are already swallowed with a log message in `email_service.py` (no `SAIL_SMTP_PASSWORD` → no send, no crash). Behavior unchanged.
- **Assigning to a non-existent employee** is prevented at form level (the dropdown is populated from `employees` and the FK constraint catches anything else).
- **Status conflict** (e.g. admin tries to assign an asset currently in `maintenance`) — the route refuses the assignment and flashes "Asset is in maintenance; clear the maintenance status first." It does not silently override admin-set states.
- **Booking URLs hit directly while flag is off** → 404 from the blueprint's `before_request` guard. No template ever links to them, so this is the misbehaving-bookmark case only.

## 7 — Testing

There is no test suite in this repo (per CLAUDE.md). Verification is manual, captured as a checklist in the implementation plan:

1. Fresh DB → seed script creates exactly the four accounts with correct roles.
2. Admin can assign Omar an asset; status flips to `in_use`; audit log row exists.
3. Admin clears the assignment; status flips back to `available`; audit log row exists.
4. Employee `/inventory` shows the holder column and has no Reserve button.
5. Employee files a ticket → both admin inboxes receive the notification (or the log line, if SMTP not configured).
6. Sidebar contains no booking links for any role; `/bookings` returns 404.
7. Flipping `BOOKINGS_ENABLED = True` restores all booking links and pages without further code changes.

## 8 — Files touched

- `config.py` — add `BOOKINGS_ENABLED = False`.
- `app.py` — context processor exposing `bookings_enabled`; remove `/register` from public routes (admin-only via Employees page).
- `init_db.py` (or new `seed_users.py`) — insert the four accounts.
- `routes/bookings.py` — `before_request` 404 guard.
- `routes/dashboard.py` — skip booking queries when flag off; add "assets assigned to me" query for employees.
- `routes/inventory.py` — split employee view (read-only catalog) from admin view; add "Assign to" handling with status flip + audit.
- `routes/reports.py` — skip booking queries when flag off.
- `templates/base.html` — gate the three booking sidebar links.
- `templates/dashboard.html` — gate booking tiles; add "assets assigned to me" tile for employees.
- `templates/inventory/*.html` — read-only catalog template; admin form gains "Assign to" dropdown.
- `templates/reports/inventory.html` — gate booking blocks.
- `email_service.py` — confirm `notify_new_ticket` sends to both admin emails (extend if currently single-recipient).

## 9 — Reversibility

Every UI removal is a flag check, not a deletion. To restore the full experience:

```python
# config.py
BOOKINGS_ENABLED = True
```

…and the booking sidebar, dashboard tiles, reports blocks, and `/bookings/*` routes all light up again. The schema, data, and route logic were never touched.
