# Ticket Kanban Board & SLA Tracking — Design Spec

## Summary

Improve the tickets workflow with two additions:

1. **Kanban board** at `/tickets` — drag-and-drop cards across status columns (Open / In Progress / Waiting / Resolved). List view is kept as a toggle.
2. **SLA age tracking** — admin-editable thresholds per priority drive an "overdue" flag shown on every card and usable by future reports.

No existing columns are changed. One new table (`sla_thresholds`). No new runtime dependencies beyond SortableJS served from a CDN.

## Database

### New table: `sla_thresholds`

```sql
CREATE TABLE IF NOT EXISTS sla_thresholds (
    priority     TEXT PRIMARY KEY
                 CHECK(priority IN ('low','medium','high','critical')),
    hours        INTEGER NOT NULL CHECK(hours > 0),
    updated_at   TEXT DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO sla_thresholds (priority, hours) VALUES
    ('critical', 24),    -- 1 day
    ('high',     72),    -- 3 days
    ('medium',   168),   -- 7 days
    ('low',      336);   -- 14 days
```

Stored in hours so admins can tune to fractions of a day if needed. UI renders as "= X days Y hours" next to the input.

### Overdue — computed, not stored

Computed in the list/board query:

```sql
CASE
    WHEN t.status IN ('resolved','closed') THEN 0
    WHEN (julianday('now') - julianday(t.created_at)) * 24 > s.hours THEN 1
    ELSE 0
END AS is_overdue
```

Joined via `LEFT JOIN sla_thresholds s ON s.priority = t.priority`. Resolved/closed tickets are never overdue.

## Routes

### New routes

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/tickets/<int:ticket_id>/status` | admin / manager / technician | JSON drag-drop status update |
| `GET`  | `/admin/sla` | admin / manager | SLA threshold editor |
| `POST` | `/admin/sla` | admin / manager | Save thresholds |

### Changed routes

- `GET /tickets` — renders the board by default. `?view=list` shows the existing list. Users with `role='employee'` see only tickets where `submitted_by = g.user.id`, rendered as non-draggable cards. Admins, managers, and technicians see all tickets.
- Board/list toggle lives in the page header: `[Board] [List]` linked via `?view=`.

### JSON status endpoint

`POST /tickets/<id>/status`

Request body (form-encoded or JSON):
```
{
    "status":     "in_progress" | "waiting" | "resolved" | "closed" | "open",
    "resolution": "..."   // required only when status == 'resolved'
}
```

Response:
```
200 { "ok": true,  "ticket": { "id": 12, "status": "resolved", "is_overdue": 0 } }
400 { "ok": false, "error": "Resolution note is required when resolving." }
403 { "ok": false, "error": "Forbidden" }
404 { "ok": false, "error": "Ticket not found." }
```

Reuses the exact same DB logic as the existing `update_ticket` form handler (extracted into a `_apply_status_change(conn, ticket_id, new_status, resolution)` helper in `routes/tickets.py`): writes the `audit_log` row, sets `resolved_at` / `closed_at`, and sends the existing email notification.

## UI

### Board layout

Four columns: **Open · In Progress · Waiting · Resolved**. Closed tickets are hidden by default; appending `?show_closed=1` adds a fifth column.

### Counters strip (above the board)

Small pill counters — click to filter the board client-side (no reload):

- Open
- In Progress
- Overdue
- Unassigned
- Mine (tickets where `submitted_by = g.user.id` OR `assigned_to = g.user.id`)

### Card contents

- Ticket number (small, top-right)
- Title (primary line, truncated to 2 lines)
- Priority dot (color-coded: critical=red, high=orange, medium=yellow, low=gray)
- Age badge: "4d" / "2h" — red background when `is_overdue = 1`
- Assignee: name or initials; "Unassigned" if `assigned_to IS NULL`

### Overdue styling

- 3px solid red left-border on the card
- Red background on the age badge

### Drag behavior

SortableJS CDN script loaded on the board page. One `new Sortable(...)` per column.

- Users with role `admin`, `manager`, or `technician`: cards draggable between columns.
- Users with role `employee`: `Sortable` is not initialised; cards remain clickable to open the detail page.
- On drop: optimistic UI moves the card, then `fetch('/tickets/<id>/status', { method: 'POST', body: ... })`.
  - If target column is **Resolved**, an inline modal opens first. Modal contains a required `<textarea>` and Save/Cancel buttons. Cancel reverts the card to its original column without a network call.
  - On HTTP 4xx/5xx: revert the card, show a toast with the error message.

### Progressive enhancement

Without JavaScript:
- Board still renders as a static grouped grid (CSS-only columns).
- Cards are anchors to `/tickets/<id>` — all updates still work via the existing detail-page form.
- Nothing drags, but nothing breaks.

### Admin SLA settings page

`GET /admin/sla` renders a simple form:

| Priority | Hours | (calculated: X days Y hours) |
|---|---|---|
| Critical | [24]  | = 1 day |
| High     | [72]  | = 3 days |
| Medium   | [168] | = 7 days |
| Low      | [336] | = 14 days |

- Submit button saves all four rows in one POST.
- Validation: `hours` must be a positive integer. On failure: flash error, re-render with submitted values.
- Audit: one `audit_log` entry per priority whose value changed (`table_name='sla_thresholds'`, `record_id=0`, `field_name=priority`, `old_value`, `new_value`).
- Sidebar link under the existing admin section of the nav, visible only to admin/manager.

## Files touched

### New

- `templates/tickets/board.html` — board template
- `templates/tickets/_card.html` — card partial
- `static/js/ticket_board.js` — SortableJS init, drop handler, resolve modal
- `static/css/board.css` — columns, card, overdue styling (or appended to the existing global stylesheet if there is one)
- `routes/admin.py` — new blueprint for `/admin/sla` (the project does not currently have an `admin_bp`; add one and register it in `app.py`)
- `templates/admin/sla.html` — threshold editor form

### Changed

- `routes/tickets.py`
  - `list_tickets()` — switch default render to `board.html`; honour `?view=list`; add the `is_overdue` / SLA join and the counters query
  - new `status_update_api(ticket_id)` route
  - extract `_apply_status_change(conn, ticket_id, new_status, resolution, actor)` helper used by both the existing form handler and the new JSON endpoint
- `schema.sql` — append the `sla_thresholds` table and seed `INSERT OR IGNORE` rows
- `database.py` — add `get_sla_hours(conn) -> dict[str, int]` helper (returns `{'critical': 24, ...}`), used by the SLA settings page
- `app.py` — register the new `admin_bp`
- `templates/base.html` — add sidebar link to SLA settings (admin/manager only)

### Unchanged

- The existing `update_ticket` form handler keeps working identically (it just calls the new `_apply_status_change` helper internally).
- The existing `/tickets/mine` route stays.
- Email notifications (`notify_ticket_update`) are unchanged.

## Testing

No pytest suite exists in the project. Manual smoke tests:

1. Create one ticket per priority. Back-date `created_at` in SQLite so ages cross the thresholds; verify red border + red age badge appear once past the limit.
2. Log in as admin — drag a card from Open → In Progress → Waiting → Resolved. Resolution modal must block empty submits; must write `resolved_at` and add an audit row.
3. Log in as a plain employee — board shows only own tickets, no drag handles, cards still clickable through to detail.
4. Edit SLA on `/admin/sla` — reduce "medium" to 1h — refresh board, ticket becomes overdue immediately.
5. With JS disabled, board renders as a static grid and links still work.

## Migration

`init_db.py` runs `schema.sql` on startup. Adding the new `CREATE TABLE IF NOT EXISTS` and `INSERT OR IGNORE` lines is safe on existing databases — no separate migration script required.

## Out of scope (deferred to a later spec)

- Weekly / monthly reports (history + status summaries)
- Spreadsheet export of all data
- SLA per-type overrides, pause/resume, business-hours calendar
- Ticket attachments, rich comments, full-text search
- Inventory-side improvements (bulk actions, pagination of `manage_assets`, richer search, asset history view)
