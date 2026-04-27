# Asset Issue Tracking — Design Spec

**Date:** 2026-04-27
**Status:** Specced (awaiting plan)
**Scope:** Re-purpose SAIL as a single-team tool for the AMT control team to log, work, and recall issues raised against company assets.

## 1 — Purpose

The control team receives ad-hoc emails from end users about issues with company equipment — anything from the AMT asset inventory (`Assets Inventory _20-04-2026-Tool (V3).xlsx` — 230 individual assets across workstations, laptops, monitors, displays, printers, networking gear, and so on). A user reports "the conference-room display is black" or "this laptop won't boot" or "the printer is jammed"; today there is no record. Once a ticket is closed, nothing is left behind — when the same unit fails again next month, the team starts from zero.

This tool exists to do three things, for **any asset** in the inventory:

1. Let the control team raise a ticket against the **specific asset** that is failing, with a type, a priority, and a description.
2. Notify the **affected end user** (by email) that their issue was received and, later, that it was resolved.
3. Build a **per-asset issue history** so the team can open any asset (by tag, model, or location) and see every past failure and how it was fixed.

End users do not log in. They send an email; the team raises the ticket on their behalf.

## 2 — Users

The system has exactly one role: **team** (the four control-team accounts). All four are functionally admins. Self-registration is removed; accounts are seeded at install.

| Email                     | Initial password |
|---------------------------|------------------|
| airandblueamt@gmail.com   | `Aramco@123`     |
| m.shaikh@amt-arabia.net   | `Aramco@123`     |
| omar.bawadod@aramco.com   | `Aramco@123`     |
| ali.almatrood@aramco.com  | `Aramco@123`     |

All four accounts ship with the same seed password (`Aramco@123`). This is convenient for a 4-user team but is a known weakness: anyone who reads this spec or the seed script can log in until the passwords are rotated. The expectation is that each user changes their password after first login (see 4.2).

For schema compatibility these accounts are stored with `role='admin'` — the existing role check unblocks every screen for them. No employee role is used.

## 3 — Non-goals

- Self-service portal for end users. End users are email recipients, not SAIL users.
- Booking, reservation, approval, or checkout flow. The tables and routes stay in the codebase but the UI is hidden behind a feature flag.
- Asset assignment ("who currently holds this laptop"). Not part of this problem; if needed later, the `assets.assigned_to` column is already there.
- Standalone tickets unattached to an asset. Every ticket created through the new flow is bound to one asset.
- A separate knowledge-base table. The asset's own ticket history *is* the knowledge base — title, description, comments, resolution per past ticket.
- Reports redesign. The reports page stays as-is; booking-only sections inside it are gated by the same flag.

## 4 — Architecture

### 4.1 Schema delta

Two nullable columns added to the existing `tickets` table, one to `employees`, and one new lookup table for team-managed issue categories:

```sql
ALTER TABLE tickets   ADD COLUMN affected_user_name  TEXT;
ALTER TABLE tickets   ADD COLUMN affected_user_email TEXT;
ALTER TABLE tickets   ADD COLUMN issue_category_id   INTEGER REFERENCES issue_categories(id);
ALTER TABLE employees ADD COLUMN password_hash       TEXT;

CREATE TABLE IF NOT EXISTS issue_categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    is_active   INTEGER DEFAULT 1,
    created_by  INTEGER REFERENCES employees(id),
    created_at  TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_tickets_issue_cat ON tickets(issue_category_id);
```

`tickets` columns are nullable because older tickets do not have these values, and a team member may legitimately raise a ticket with no specific affected user (preventive maintenance, asset audit, etc.). When the email field is blank, the affected-user notification is simply skipped. `issue_category_id` is required by the form (see 4.5) but stays nullable in the schema for the same migration-safety reason.

`employees.password_hash` is nullable in the schema for migration safety, but the login route requires it: an account with no hash cannot sign in. The seed script populates the hash for all four control-team accounts.

`issue_categories` ships with a starter list grounded in the V3 inventory's actual asset mix (workstations, monitors, smart boards, touch screens, TV screens, Google TVs, printers, smart podiums, eye-tracking systems, access control). The team adds and deactivates rows from a small admin page (see 4.9).

No other schema changes. `assets`, `equipment_models`, `categories`, `locations`, `bookings`, `ticket_comments`, `audit_log` are all left intact.

### 4.2 Authentication

Login becomes **email + password** (today the app is email-only).

- The login form gains a password field. The route looks up the employee by email and validates against `password_hash` using `werkzeug.security.check_password_hash`. No hash, wrong password, or inactive (`is_active = 0`) account → generic "invalid credentials" error. Sessions stay as they are (`session['user_id']`).
- Hashing uses `werkzeug.security.generate_password_hash` (PBKDF2-SHA256, the Werkzeug default — no extra dependency since Flask already pulls Werkzeug). Plain passwords are never stored or logged.
- A new route `/account/password` lets a logged-in user change their own password. The form requires the current password (validated) plus the new password twice. On success, the new hash is written and the session is preserved.
- The seed script (see 4.1) calls `generate_password_hash('Aramco@123')` once and writes the same hash to all four accounts. The `Aramco@123` literal lives only in the seed script — it is never read from a config file, env var, or DB.
- **No "forgot password" flow.** With four users in one room, password recovery is "ask the admin to update your hash" or rerun the seed script.

### 4.3 Core flow

```
End user emails the team about any asset issue (e.g. "display in CR3 is black",
"my laptop SAIL-16038 keeps freezing", "printer in finance is jammed")
            │
            ▼
Team member opens SAIL → /inventory → searches by tag, model, or location
                       → opens that asset's detail page
            │
            ▼
Clicks "Raise Issue"  (form is pre-populated with asset_id)
   fills in: type, priority, title, description,
             affected_user_name, affected_user_email
            │
            ▼
POST /tickets/new
   INSERT INTO tickets (..., asset_id=42, submitted_by=team_member)
   email_service.notify_affected_user(ticket, kind='created')
            │
            ▼
Team works the ticket: comments, status changes (open → in_progress → resolved)
   On resolve: team writes the `resolution` field
   email_service.notify_affected_user(ticket, kind='resolved')
            │
            ▼
Next time anyone opens that asset's detail page, the ticket appears in
its "Issue History" section — title, status, resolution, all comments.
```

### 4.4 Asset detail page (the load-bearing screen)

`/inventory/asset/<id>` — visible to all team members. Three sections:

1. **Asset summary** — tag, model, brand, location, status, condition, notes.
2. **Issue history** — table of every ticket where `asset_id = this`, sorted newest first. Columns: opened date, priority, status, title, resolved date. Each row expands to show description, resolution, and comment thread.
3. **Action** — single button: **Raise New Issue** → `/tickets/new?asset_id=<id>`.

This page replaces the prior "browse and book" affordance. There is no longer any reason to filter the asset list by `is_bookable`; the team needs to see everything.

### 4.5 Ticket form

`/tickets/new` accepts an optional `?asset_id=` query param. Fields shown to the team:

- **Asset** (required) — preselected if `asset_id` came in the URL; otherwise a searchable dropdown.
- **Issue Category** (required) — populated from `issue_categories` where `is_active = 1`, ordered by name. The form has a small "+ add new" link next to the dropdown that opens the admin page (see 4.9) in a new tab so the team can extend the list without losing their in-progress ticket.
- **Priority** — `low` / `medium` / `high` / `critical`. Default `medium`.
- **Title** (required, short).
- **Description** (free text).
- **Affected user name** (optional).
- **Affected user email** (optional, validated as email if provided).

The legacy `type` column is set server-side to `'incident'` for every ticket created from this form. The column itself is preserved so tickets remain queryable by the older typology if it earns its keep later, but it is no longer surfaced to the user — the issue category is the single classification field they touch.

On submit: insert the ticket, audit-log the creation, send the "ticket received" email to the affected user (if email present).

### 4.6 Ticket workflow (mostly unchanged)

The existing kanban / SLA board stays. The only behavioral additions:

- When a ticket transitions to `resolved`, the team must fill in the `resolution` field (form-level required). On save, send the "your issue is resolved" email to the affected user.
- The ticket detail page shows the affected user's name + email in the header so the team can reach them by phone if needed.

### 4.7 Dashboard

Single role, single dashboard. Tiles:

- **Open tickets** count.
- **High / critical priority** queue (top 5, click-through to ticket).
- **Recently resolved** (last 5) — quick lookback for "didn't I just fix this?"
- **Unhealthy assets** — assets with `status = 'maintenance'` or `condition = 'damaged'`.

All booking tiles are gated by the feature flag (see 4.8).

### 4.8 Bookings — hidden, not deleted

A single boolean in `config.py`:

```python
BOOKINGS_ENABLED = False
```

Exposed to Jinja via `app.context_processor` as `bookings_enabled`. Three things gate on it:

- Sidebar links to `bookings.*` endpoints in `templates/base.html`.
- Booking-related tiles and panels in `templates/dashboard.html` and `templates/reports/inventory.html`.
- A `before_request` guard on `bookings_bp` that calls `abort(404)` when the flag is off. The blueprint stays registered so any stray `url_for('bookings.…')` still resolves at template parse time.

In `routes/dashboard.py` and `routes/reports.py` the booking SELECTs are short-circuited when the flag is off — no point paying for them.

Reversibility: flip the flag back to `True` and every booking link, page, and stat returns. No deletions to undo.

### 4.9 Issue categories — admin page

A small admin screen at `/issue-categories` lets the team manage the dropdown:

- **List view** — table of all categories with name, active/inactive status, who created it, when. Inline toggle to flip `is_active` (deactivating just hides it from the form; existing tickets keep their category reference). No hard delete, since tickets reference the row.
- **Add form** — single text input (`name`), uniqueness enforced by the `UNIQUE` constraint on the column. Records `created_by = g.user.id`.
- **Audit log** — every add and every active/inactive flip is written to `audit_log` via the standard `log_audit(conn, 'issue_categories', id, action, …)` helper.

The page is reachable from the sidebar (under a "Settings" group) and from the `+ add new` link on the ticket form (see 4.5).

**Seed list** (inserted by the seed script, grounded in the V3 inventory's actual asset mix):

| Category                       | Covers (informally)                                  |
|--------------------------------|------------------------------------------------------|
| Display / Screen issue         | Monitor, TV Screen, Google TV, Smart Board, Smart Podium, Touch Screen |
| Touch / Calibration failure    | Smart Board, Touch Screen, Smart Podium              |
| Won't power on                 | Any powered asset                                    |
| Slow / Freezing                | Workstation, Smart Board, Smart Podium               |
| Software / OS issue            | Workstation, Smart Podium, Eye Tracking System       |
| Network / Connectivity         | Any networked asset                                  |
| Printer issue (jam, toner, quality) | Printers                                        |
| Peripheral issue (keyboard, mouse, audio, camera) | Workstation, Smart Podium         |
| Physical damage                | Any                                                  |
| Other                          | Catch-all                                            |

The team is expected to add more as new failure modes appear.

### 4.10 Email

A new helper in `email_service.py`:

```python
def notify_affected_user(ticket, kind):
    """kind ∈ {'created', 'resolved'}. No-op if affected_user_email is blank."""
```

Subjects:

- `created` → `[SAIL] Ticket #TKT-0123 received: <title>`
- `resolved` → `[SAIL] Ticket #TKT-0123 resolved: <title>`

Body includes the asset tag + model, the ticket title, the description (for `created`) or the resolution text (for `resolved`), and a "Reply to this email" line. The reply lands in the team's shared mailbox, not SAIL — comment threading from external email is out of scope for this version.

Existing internal-team notification helpers (assignment, comments) are unchanged.

## 5 — Error handling

- **No `SAIL_SMTP_PASSWORD`** — `email_service` already logs and returns. Behavior unchanged.
- **Affected email field blank** — `notify_affected_user` returns silently. The ticket is still created and worked normally; the team just doesn't email anyone.
- **Invalid email format** — caught by HTML5 form validation; the form rejects submission before hitting the route.
- **Booking URL hit while flag is off** — 404 from the blueprint guard.
- **Resolution field blank on resolve** — form rejects submission with "Resolution required when resolving a ticket."
- **Login attempt for an account with no `password_hash`** — generic "invalid credentials" error, same as a wrong password. The system never reveals whether the email exists.
- **Password change with wrong current password** — generic "current password is incorrect" error; new password is not written.
- **Adding an issue category that already exists** — the column is declared `name TEXT NOT NULL UNIQUE COLLATE NOCASE` so SQLite rejects the insert when a case-insensitive match exists; the form flashes "Category already exists." This avoids `Display issue` and `display issue` cluttering the list.
- **Deactivating a category referenced by existing tickets** — allowed. The dropdown stops offering it; ticket pages still render the original name via the FK join.

## 6 — Testing

No automated test suite (per CLAUDE.md). Manual verification checklist, to be expanded into the implementation plan:

1. Fresh DB → seed inserts the four accounts, all with `role='admin'` and a `password_hash` set.
2. Fresh DB → seed inserts the ten starter issue categories with `is_active = 1`.
3. `/register` is no longer reachable from the nav.
4. Login form rejects empty password, wrong password, and unknown email with the same generic error.
5. Login with `airandblueamt@gmail.com` + `Aramco@123` → succeeds, session set, lands on dashboard.
6. `/account/password` lets the logged-in user change their password; logging out and back in with the new password works; the old password no longer works.
7. Open an asset detail page → "Raise New Issue" button is visible → form pre-populates `asset_id`.
8. Ticket form shows the Issue Category dropdown populated with the ten seeded categories; submission without a category is rejected.
9. `/issue-categories` lets the team add a new category; it appears in the dropdown immediately on next form load. Deactivating it removes it from the dropdown but existing tickets still show its name.
10. Submit the form with an affected_user_email → ticket created with the chosen issue category, log shows email send (or actual send if SMTP configured).
11. Resolve the ticket with a resolution note → second email sent to the same address.
12. Re-open the asset's detail page → the ticket appears in Issue History with status `resolved`, its issue category, and the resolution text.
13. Sidebar contains no booking links; `/bookings` returns 404.
14. Flipping `BOOKINGS_ENABLED = True` restores everything booking-related with no other change.

## 7 — Files touched

- `schema.sql` — add the three `tickets` columns, the `employees.password_hash` column, and the `issue_categories` table + index.
- `init_db.py` (or a new `seed_users.py`) — insert the four accounts as `role='admin'` with `generate_password_hash('Aramco@123')`, and seed the ten starter issue categories.
- `config.py` — `BOOKINGS_ENABLED = False`.
- `app.py` — context processor for `bookings_enabled`; remove the public `/register` route; rewrite the login route to validate `password_hash`; add `/account/password` for password changes.
- `templates/login.html` — add password field.
- `templates/account/password.html` — new template for the password-change form.
- `routes/bookings.py` — `before_request` 404 guard.
- `routes/inventory.py` — asset detail page with issue-history section.
- `routes/tickets.py` — accept `?asset_id=` query param; require `resolution` on resolve transition; trigger affected-user emails.
- `routes/dashboard.py` — control-team tiles; gate booking queries.
- `routes/reports.py` — gate booking queries.
- `templates/base.html` — gate booking sidebar links; rename app sections if needed.
- `templates/dashboard.html` — single-role dashboard.
- `templates/inventory/detail.html` — issue history section + "Raise New Issue" button.
- `templates/tickets/form.html` — affected-user fields, asset preselection, issue-category dropdown, "+ add new" link, removal of the type field.
- `templates/tickets/detail.html` — show affected user and issue category in header.
- `templates/reports/inventory.html` — gate booking blocks.
- `routes/issue_categories.py` (new) — list + add + toggle-active endpoints.
- `templates/issue_categories/index.html` (new) — admin page.
- `email_service.py` — `notify_affected_user(ticket, kind)`.

## 8 — Reversibility

The booking module is gated, not deleted. The new `tickets` and `employees` columns are all nullable, and the new `issue_categories` table is purely additive. Reverting this entire spec is `git revert` of the implementation commits — no destructive schema migrations. (Reverting the auth change does mean every account effectively becomes login-less again; rotating credentials beforehand is the safer reversal path.)
