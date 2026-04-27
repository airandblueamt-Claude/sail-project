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

| Email                     |
|---------------------------|
| airandblueamt@gmail.com   |
| m.shaikh@amt-arabia.net   |
| omar.bawadod@aramco.com   |
| ali.almatrood@aramco.com  |

(For schema compatibility these accounts are stored with `role='admin'` — the existing role check unblocks every screen for them. No employee role is used.)

## 3 — Non-goals

- Self-service portal for end users. End users are email recipients, not SAIL users.
- Booking, reservation, approval, or checkout flow. The tables and routes stay in the codebase but the UI is hidden behind a feature flag.
- Asset assignment ("who currently holds this laptop"). Not part of this problem; if needed later, the `assets.assigned_to` column is already there.
- Standalone tickets unattached to an asset. Every ticket created through the new flow is bound to one asset.
- A separate knowledge-base table. The asset's own ticket history *is* the knowledge base — title, description, comments, resolution per past ticket.
- Reports redesign. The reports page stays as-is; booking-only sections inside it are gated by the same flag.

## 4 — Architecture

### 4.1 Schema delta

Two nullable columns added to the existing `tickets` table:

```sql
ALTER TABLE tickets ADD COLUMN affected_user_name  TEXT;
ALTER TABLE tickets ADD COLUMN affected_user_email TEXT;
```

Why nullable: older tickets do not have these values, and a team member may legitimately raise a ticket with no specific affected user (preventive maintenance, asset audit, etc.). When the email field is blank, the affected-user notification is simply skipped.

No other schema changes. `assets`, `equipment_models`, `categories`, `locations`, `bookings`, `ticket_comments`, `audit_log` are all left intact.

### 4.2 Core flow

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
Next time anyone opens that TV's asset page, the ticket appears in
its "Issue History" section — title, status, resolution, all comments.
```

### 4.3 Asset detail page (the load-bearing screen)

`/inventory/asset/<id>` — visible to all team members. Three sections:

1. **Asset summary** — tag, model, brand, location, status, condition, notes.
2. **Issue history** — table of every ticket where `asset_id = this`, sorted newest first. Columns: opened date, priority, status, title, resolved date. Each row expands to show description, resolution, and comment thread.
3. **Action** — single button: **Raise New Issue** → `/tickets/new?asset_id=<id>`.

This page replaces the prior "browse and book" affordance. There is no longer any reason to filter the asset list by `is_bookable`; the team needs to see everything.

### 4.4 Ticket form

`/tickets/new` accepts an optional `?asset_id=` query param. Fields:

- **Asset** (required) — preselected if `asset_id` came in the URL; otherwise a searchable dropdown.
- **Type** — existing CHECK values (`maintenance`, `incident`, etc.). Default `incident` since that's the dominant case.
- **Priority** — `low` / `medium` / `high` / `critical`. Default `medium`.
- **Title** (required, short).
- **Description** (free text).
- **Affected user name** (optional).
- **Affected user email** (optional, validated as email if provided).

On submit: insert the ticket, audit-log the creation, send the "ticket received" email to the affected user (if email present).

### 4.5 Ticket workflow (mostly unchanged)

The existing kanban / SLA board stays. The only behavioral additions:

- When a ticket transitions to `resolved`, the team must fill in the `resolution` field (form-level required). On save, send the "your issue is resolved" email to the affected user.
- The ticket detail page shows the affected user's name + email in the header so the team can reach them by phone if needed.

### 4.6 Dashboard

Single role, single dashboard. Tiles:

- **Open tickets** count.
- **High / critical priority** queue (top 5, click-through to ticket).
- **Recently resolved** (last 5) — quick lookback for "didn't I just fix this?"
- **Unhealthy assets** — assets with `status = 'maintenance'` or `condition = 'damaged'`.

All booking tiles are gated by the feature flag (see 4.7).

### 4.7 Bookings — hidden, not deleted

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

### 4.8 Email

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

## 6 — Testing

No automated test suite (per CLAUDE.md). Manual verification checklist, to be expanded into the implementation plan:

1. Fresh DB → seed inserts the four accounts, all with `role='admin'`.
2. `/register` is no longer reachable from the nav.
3. Open an asset detail page → "Raise New Issue" button is visible → form pre-populates `asset_id`.
4. Submit the form with an affected_user_email → ticket created, log shows email send (or actual send if SMTP configured).
5. Resolve the ticket with a resolution note → second email sent to the same address.
6. Re-open the asset's detail page → the ticket appears in Issue History with status `resolved` and the resolution text.
7. Sidebar contains no booking links; `/bookings` returns 404.
8. Flipping `BOOKINGS_ENABLED = True` restores everything booking-related with no other change.

## 7 — Files touched

- `schema.sql` — add the two `tickets` columns.
- `init_db.py` (or a new `seed_users.py`) — insert the four accounts as `role='admin'`.
- `config.py` — `BOOKINGS_ENABLED = False`.
- `app.py` — context processor for `bookings_enabled`; remove the public `/register` route from the nav.
- `routes/bookings.py` — `before_request` 404 guard.
- `routes/inventory.py` — asset detail page with issue-history section.
- `routes/tickets.py` — accept `?asset_id=` query param; require `resolution` on resolve transition; trigger affected-user emails.
- `routes/dashboard.py` — control-team tiles; gate booking queries.
- `routes/reports.py` — gate booking queries.
- `templates/base.html` — gate booking sidebar links; rename app sections if needed.
- `templates/dashboard.html` — single-role dashboard.
- `templates/inventory/detail.html` — issue history section + "Raise New Issue" button.
- `templates/tickets/form.html` — affected-user fields, asset preselection.
- `templates/tickets/detail.html` — show affected user in header.
- `templates/reports/inventory.html` — gate booking blocks.
- `email_service.py` — `notify_affected_user(ticket, kind)`.

## 8 — Reversibility

The booking module is gated, not deleted. The two new ticket columns are nullable. Reverting this entire spec is `git revert` of the implementation commits — no destructive schema migrations.
