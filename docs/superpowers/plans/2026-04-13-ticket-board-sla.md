# Ticket Kanban Board & SLA Tracking — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a drag-and-drop Kanban board as the default `/tickets` view and admin-editable per-priority SLA thresholds driving an "overdue" indicator on every card.

**Architecture:** One new `sla_thresholds` table seeded with four rows. A new `admin_bp` blueprint for the SLA settings page. Existing `tickets.list_tickets` switches default render to the new board template, with `?view=list` falling back to the current list. A new JSON endpoint `POST /tickets/<id>/status` handles drag-drop updates, reusing a refactored `_apply_status_change` helper that both the existing form handler and the new endpoint call. SortableJS loaded from CDN provides drag — the page still works without JavaScript.

**Tech Stack:** Flask, SQLite (WAL + FK), Jinja2, vanilla JS + fetch, SortableJS (CDN), existing `static/style.css`.

**Testing note:** This project has no pytest suite. Each task ends with a manual verification step (curl, browser, or sqlite query) and a git commit. A final smoke-test task at the end walks through the full user flow.

---

### Task 1: Add `sla_thresholds` table and seed rows to schema

**Files:**
- Modify: `schema.sql` (append after `equipment_agreements` block, before the seed `INSERT OR IGNORE INTO categories` section around line 212)
- Create: `migrate_sla.py` (root of repo — one-off migration for the existing `sail.db`)

- [ ] **Step 1: Append the new table definition to `schema.sql`**

Add this block after the `CREATE INDEX IF NOT EXISTS idx_agreements_type` line (around line 211) and before the `-- =========` separator comment:

```sql
-- ── SLA thresholds (per-priority overdue cutoffs, admin-editable) ──────────

CREATE TABLE IF NOT EXISTS sla_thresholds (
    priority     TEXT PRIMARY KEY
                 CHECK(priority IN ('low','medium','high','critical')),
    hours        INTEGER NOT NULL CHECK(hours > 0),
    updated_at   TEXT DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO sla_thresholds (priority, hours) VALUES
    ('critical', 24),
    ('high',     72),
    ('medium',   168),
    ('low',      336);
```

- [ ] **Step 2: Create `migrate_sla.py` so existing `sail.db` gets the new table without `init_db.py` wiping data**

Create the file with:

```python
"""One-off migration: add sla_thresholds table to an existing sail.db.

Safe to re-run. Does not touch other tables.
Usage: python migrate_sla.py
"""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "sail.db")

SQL = """
CREATE TABLE IF NOT EXISTS sla_thresholds (
    priority     TEXT PRIMARY KEY
                 CHECK(priority IN ('low','medium','high','critical')),
    hours        INTEGER NOT NULL CHECK(hours > 0),
    updated_at   TEXT DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO sla_thresholds (priority, hours) VALUES
    ('critical', 24),
    ('high',     72),
    ('medium',   168),
    ('low',      336);
"""

def main():
    if not os.path.exists(DB_PATH):
        print(f"{DB_PATH} not found. Run init_db.py first.")
        return
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SQL)
    conn.commit()
    rows = conn.execute("SELECT priority, hours FROM sla_thresholds ORDER BY hours").fetchall()
    print("sla_thresholds rows:")
    for p, h in rows:
        print(f"  {p:<10} {h} hours")
    conn.close()

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the migration against the existing DB**

```bash
cd /mnt/d/m.alkhalifa/Documents/sail-project && python migrate_sla.py
```

Expected output:
```
sla_thresholds rows:
  critical   24 hours
  high       72 hours
  medium     168 hours
  low        336 hours
```

- [ ] **Step 4: Commit**

```bash
git add schema.sql migrate_sla.py
git commit -m "Add sla_thresholds table for per-priority overdue cutoffs"
```

---

### Task 2: Add `get_sla_hours` helper to `database.py`

**Files:**
- Modify: `database.py` (append after `log_audit` function, end of file)

- [ ] **Step 1: Append the helper**

Add to the end of `database.py`:

```python
def get_sla_hours(conn):
    """Return a {priority: hours} dict for all SLA thresholds.

    Used by the SLA settings page and by list_tickets to compute overdue.
    """
    rows = conn.execute(
        "SELECT priority, hours FROM sla_thresholds"
    ).fetchall()
    return {row['priority']: row['hours'] for row in rows}
```

- [ ] **Step 2: Verify it works**

```bash
cd /mnt/d/m.alkhalifa/Documents/sail-project && python -c "
from database import get_db, get_sla_hours
with get_db() as conn:
    print(get_sla_hours(conn))
"
```

Expected: `{'critical': 24, 'high': 72, 'medium': 168, 'low': 336}`

- [ ] **Step 3: Commit**

```bash
git add database.py
git commit -m "Add get_sla_hours helper for threshold lookup"
```

---

### Task 3: Create admin blueprint with SLA settings page

**Files:**
- Create: `routes/admin.py`
- Create: `templates/admin/sla.html`
- Modify: `app.py` (register the new blueprint)

- [ ] **Step 1: Create `routes/admin.py`**

```python
"""Admin-only utility pages (SLA thresholds, future admin tools)."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from database import get_db, log_audit, get_sla_hours

admin_bp = Blueprint('admin', __name__)

PRIORITIES = ('critical', 'high', 'medium', 'low')


def _require_admin():
    if not g.user or g.user['role'] not in ('admin', 'manager'):
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.index'))
    return None


@admin_bp.route('/sla', methods=['GET', 'POST'])
def sla_settings():
    denied = _require_admin()
    if denied:
        return denied

    with get_db() as conn:
        if request.method == 'POST':
            new_values = {}
            for priority in PRIORITIES:
                raw = request.form.get(priority, '').strip()
                try:
                    hours = int(raw)
                except ValueError:
                    flash(f'{priority.title()} hours must be an integer.', 'error')
                    return redirect(url_for('admin.sla_settings'))
                if hours <= 0:
                    flash(f'{priority.title()} hours must be greater than 0.', 'error')
                    return redirect(url_for('admin.sla_settings'))
                new_values[priority] = hours

            current = get_sla_hours(conn)
            for priority, hours in new_values.items():
                if current.get(priority) != hours:
                    conn.execute(
                        "UPDATE sla_thresholds SET hours=?, updated_at=datetime('now') "
                        "WHERE priority=?",
                        (hours, priority))
                    log_audit(conn, 'sla_thresholds', 0, 'update',
                              field_name=priority,
                              old_value=current.get(priority),
                              new_value=hours,
                              changed_by=g.user['id'])
            flash('SLA thresholds saved.', 'success')
            return redirect(url_for('admin.sla_settings'))

        thresholds = get_sla_hours(conn)

    return render_template('admin/sla.html', thresholds=thresholds,
                           priorities=PRIORITIES)
```

- [ ] **Step 2: Create `templates/admin/sla.html`**

```jinja
{% extends "base.html" %}
{% block title %}SAIL - SLA Settings{% endblock %}
{% block content %}
<div class="page-header">
    <h2>SLA Thresholds</h2>
</div>

<div class="info-banner">
    <i data-lucide="info"></i>
    <span>A ticket becomes <strong>overdue</strong> if it stays in an unresolved status
    longer than the threshold for its priority. Resolved and closed tickets are never
    overdue. Enter hours (e.g. 24 = 1 day, 72 = 3 days).</span>
</div>

<form method="POST" class="form-card" style="max-width: 540px;">
    <table class="data-table">
        <thead>
            <tr>
                <th>Priority</th>
                <th>Hours</th>
                <th>Equivalent</th>
            </tr>
        </thead>
        <tbody>
            {% for p in priorities %}
            <tr>
                <td><span class="badge badge-priority-{{ p }}">{{ p }}</span></td>
                <td>
                    <input type="number" name="{{ p }}" min="1" required
                           value="{{ thresholds[p] }}" style="width: 6rem;">
                </td>
                <td>
                    = {{ (thresholds[p] // 24) }}d {{ (thresholds[p] % 24) }}h
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>

    <div class="form-actions" style="margin-top: 1rem;">
        <button type="submit" class="btn btn-primary">Save Thresholds</button>
    </div>
</form>
<script>lucide.createIcons();</script>
{% endblock %}
```

- [ ] **Step 3: Register the blueprint in `app.py`**

Edit `app.py` — add import after the other blueprint imports (around line 117):

```python
from routes.admin import admin_bp
```

And register it after the existing `help` blueprint registration (around line 124):

```python
app.register_blueprint(admin_bp, url_prefix='/admin')
```

- [ ] **Step 4: Smoke-test the page**

Run the app:
```bash
cd /mnt/d/m.alkhalifa/Documents/sail-project && python app.py &
```

Log in as an admin/manager, visit `http://localhost:5555/admin/sla`. Expected:
- Four rows (critical/high/medium/low) with the seeded hours.
- "Equivalent" column shows the day/hour breakdown.
- Change medium from 168 to 100, submit → flash "SLA thresholds saved." → value persists on refresh.
- Check the audit log:
  ```bash
  sqlite3 sail.db "SELECT table_name, field_name, old_value, new_value FROM audit_log WHERE table_name='sla_thresholds' ORDER BY id DESC LIMIT 5;"
  ```
  Expected: a row with `sla_thresholds | medium | 168 | 100`.

Revert the change via the form (back to 168) and kill the app.

- [ ] **Step 5: Commit**

```bash
git add routes/admin.py templates/admin/sla.html app.py
git commit -m "Add /admin/sla page to edit per-priority overdue thresholds"
```

---

### Task 4: Add sidebar link to SLA settings

**Files:**
- Modify: `templates/base.html` (inside the `{% if current_user and current_user.role in ('admin', 'manager') %}` block)

- [ ] **Step 1: Add the nav link**

Insert this `<li>` after the existing "Employees" link (currently the last admin link, around line 54), before the closing `{% endif %}`:

```jinja
            <li><a href="{{ url_for('admin.sla_settings') }}" class="{% if request.endpoint == 'admin.sla_settings' %}active{% endif %}">
                <i data-lucide="timer"></i> SLA Settings
            </a></li>
```

- [ ] **Step 2: Verify**

Reload `http://localhost:5555/` — the admin sidebar now shows "SLA Settings" with a timer icon. Clicking it navigates to `/admin/sla` and highlights the link.

- [ ] **Step 3: Commit**

```bash
git add templates/base.html
git commit -m "Link SLA Settings from the admin sidebar"
```

---

### Task 5: Refactor `_apply_status_change` helper in `routes/tickets.py`

Pure refactor — no behavior change. Extracts the status-update logic from `update_ticket` so both the form handler and the upcoming JSON endpoint use one path.

**Files:**
- Modify: `routes/tickets.py`

- [ ] **Step 1: Add the helper near the top of the file**

Insert just after the `next_ticket_number` function (around line 18):

```python
def _apply_status_change(conn, ticket_id, new_status, resolution, actor):
    """Apply a status change (and optional resolution text) to a ticket.

    Writes audit log, updates resolved_at/closed_at timestamps, and
    triggers the submitter email when status changes. Returns the
    fresh ticket row, or None if the ticket does not exist.

    Caller is responsible for permission checks.
    """
    old = conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not old:
        return None

    extra_sql = ""
    if new_status == 'resolved' and old['status'] != 'resolved':
        extra_sql = ", resolved_at=datetime('now')"
    if new_status == 'closed' and old['status'] != 'closed':
        extra_sql += ", closed_at=datetime('now')"

    conn.execute(f"""
        UPDATE tickets
        SET status=?, resolution=?, updated_at=datetime('now') {extra_sql}
        WHERE id=?
    """, (new_status, resolution or old['resolution'] or '', ticket_id))

    if new_status != old['status']:
        log_audit(conn, 'tickets', ticket_id, 'status_change',
                  'status', old['status'], new_status,
                  changed_by=actor['id'])
        submitter = conn.execute(
            "SELECT email FROM employees WHERE id=?", (old['submitted_by'],)
        ).fetchone()
        if submitter and submitter['email']:
            updated_ticket = conn.execute(
                "SELECT * FROM tickets WHERE id=?", (ticket_id,)
            ).fetchone()
            notify_ticket_update(dict(updated_ticket), submitter['email'],
                                 'status_change', actor['name'])

    return conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
```

- [ ] **Step 2: Rewrite `update_ticket` to use the helper**

Replace the body of `update_ticket` (the function currently at lines 173-214) with:

```python
@tickets_bp.route('/<int:ticket_id>/update', methods=['POST'])
def update_ticket(ticket_id):
    with get_db() as conn:
        old = conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        if not old:
            flash('Ticket not found.', 'error')
            return redirect(url_for('tickets.list_tickets'))

        new_status = request.form.get('status', old['status'])
        new_priority = request.form.get('priority', old['priority'])
        new_assignee = request.form.get('assigned_to', type=int) or old['assigned_to']
        resolution = request.form.get('resolution', old['resolution'] or '')

        # Non-status fields still update here (priority, assignee)
        conn.execute("""
            UPDATE tickets
            SET priority=?, assigned_to=?, updated_at=datetime('now')
            WHERE id=?
        """, (new_priority, new_assignee, ticket_id))

        # Status + resolution go through the shared helper
        _apply_status_change(conn, ticket_id, new_status, resolution, g.user)

        flash('Ticket updated.', 'success')
    return redirect(url_for('tickets.ticket_detail', ticket_id=ticket_id))
```

- [ ] **Step 3: Smoke-test that the existing form still works**

Restart the app, open any ticket, change status via the detail form (e.g. open → in_progress), click Save. Expected: status updates, flash message appears, audit_log has a new `status_change` row for that ticket.

```bash
sqlite3 sail.db "SELECT record_id, field_name, old_value, new_value FROM audit_log WHERE table_name='tickets' AND action='status_change' ORDER BY id DESC LIMIT 3;"
```

- [ ] **Step 4: Commit**

```bash
git add routes/tickets.py
git commit -m "Extract _apply_status_change helper from update_ticket"
```

---

### Task 6: Add JSON status endpoint for drag-drop

**Files:**
- Modify: `routes/tickets.py`

- [ ] **Step 1: Add the route above `update_ticket`**

Insert this new handler just before the `@tickets_bp.route('/<int:ticket_id>/update', ...)` line:

```python
@tickets_bp.route('/<int:ticket_id>/status', methods=['POST'])
def status_update_api(ticket_id):
    """JSON endpoint for the kanban board drag-drop.

    Body (form-encoded or JSON): {status, resolution?}
    """
    if g.user['role'] not in ('admin', 'manager', 'technician'):
        return {'ok': False, 'error': 'Forbidden'}, 403

    payload = request.get_json(silent=True) or request.form
    new_status = (payload.get('status') or '').strip()
    resolution = (payload.get('resolution') or '').strip()

    allowed = ('open', 'in_progress', 'waiting', 'resolved', 'closed')
    if new_status not in allowed:
        return {'ok': False, 'error': f'Invalid status: {new_status}'}, 400

    if new_status == 'resolved' and not resolution:
        return {'ok': False,
                'error': 'Resolution note is required when resolving.'}, 400

    with get_db() as conn:
        row = _apply_status_change(conn, ticket_id, new_status, resolution, g.user)
        if row is None:
            return {'ok': False, 'error': 'Ticket not found.'}, 404

        return {'ok': True,
                'ticket': {'id': row['id'],
                           'status': row['status']}}
```

- [ ] **Step 2: Smoke-test the endpoint with curl**

Start the app, log in as admin via browser so the session cookie is set, then extract the cookie and test:

```bash
# Quick way: use an admin-role user and hit the endpoint while logged in
# From the browser dev console on any SAIL page (Network tab → copy any request as cURL),
# or simply run these in the browser console after logging in:
```

In the browser DevTools console (while logged in as admin), run:

```javascript
fetch('/tickets/1/status', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({status: 'in_progress'})
}).then(r => r.json()).then(console.log);
```

Expected: `{ok: true, ticket: {id: 1, status: "in_progress"}}`.

Try the resolve path:
```javascript
fetch('/tickets/1/status', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({status: 'resolved'})
}).then(r => r.json()).then(console.log);
```

Expected: `{ok: false, error: "Resolution note is required when resolving."}` with HTTP 400.

With resolution:
```javascript
fetch('/tickets/1/status', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({status: 'resolved', resolution: 'Fixed manually'})
}).then(r => r.json()).then(console.log);
```

Expected: `{ok: true, ticket: {...}}` and `sqlite3 sail.db "SELECT resolution, resolved_at FROM tickets WHERE id=1;"` shows the note and a timestamp.

- [ ] **Step 3: Revert test changes**

Manually set the ticket back to its prior status via the detail form.

- [ ] **Step 4: Commit**

```bash
git add routes/tickets.py
git commit -m "Add JSON /tickets/<id>/status endpoint for drag-drop updates"
```

---

### Task 7: Update `list_tickets` to render board by default, add SLA + counters

**Files:**
- Modify: `routes/tickets.py` (the `list_tickets` function at lines 37-74)

- [ ] **Step 1: Replace `list_tickets` with the board-aware version**

```python
@tickets_bp.route('/')
def list_tickets():
    view = request.args.get('view', 'board')           # 'board' | 'list'
    status = request.args.get('status', '')
    ttype = request.args.get('type', '')
    show_closed = request.args.get('show_closed') == '1'

    is_employee_only = g.user['role'] == 'employee'

    with get_db() as conn:
        where_parts = []
        params = []

        if is_employee_only:
            where_parts.append("t.submitted_by = ?")
            params.append(g.user['id'])

        if status:
            where_parts.append("t.status = ?")
            params.append(status)
        if ttype:
            where_parts.append("t.type = ?")
            params.append(ttype)

        # Board hides 'closed' unless ?show_closed=1; list shows everything
        if view == 'board' and not show_closed:
            where_parts.append("t.status != 'closed'")

        where_sql = " WHERE " + " AND ".join(where_parts) if where_parts else ""

        tickets = conn.execute(f"""
            SELECT t.*, e.name as submitter_name,
                   ea.name as assignee_name,
                   a.asset_tag, em.name as equipment_name,
                   CASE
                       WHEN t.status IN ('resolved','closed') THEN 0
                       WHEN s.hours IS NULL THEN 0
                       WHEN (julianday('now') - julianday(t.created_at)) * 24 > s.hours THEN 1
                       ELSE 0
                   END AS is_overdue,
                   CAST((julianday('now') - julianday(t.created_at)) * 24 AS INTEGER) AS age_hours
            FROM tickets t
            JOIN employees e ON t.submitted_by = e.id
            LEFT JOIN employees ea ON t.assigned_to = ea.id
            LEFT JOIN assets a ON t.asset_id = a.id
            LEFT JOIN equipment_models em ON a.equipment_model_id = em.id
            LEFT JOIN sla_thresholds s ON s.priority = t.priority
            {where_sql}
            ORDER BY
                CASE t.priority
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                END,
                t.created_at DESC
        """, params).fetchall()

        # Counters query — unfiltered by status/type (so counts reflect totals
        # the user is allowed to see), but respects the employee-only filter.
        counter_where = "WHERE t.submitted_by = ?" if is_employee_only else ""
        counter_params = [g.user['id']] if is_employee_only else []
        counters_row = conn.execute(f"""
            SELECT
                SUM(CASE WHEN t.status = 'open' THEN 1 ELSE 0 END) AS open_count,
                SUM(CASE WHEN t.status = 'in_progress' THEN 1 ELSE 0 END) AS in_progress_count,
                SUM(CASE
                        WHEN t.status IN ('resolved','closed') THEN 0
                        WHEN s.hours IS NULL THEN 0
                        WHEN (julianday('now') - julianday(t.created_at)) * 24 > s.hours THEN 1
                        ELSE 0
                    END) AS overdue_count,
                SUM(CASE WHEN t.assigned_to IS NULL AND t.status NOT IN ('resolved','closed')
                         THEN 1 ELSE 0 END) AS unassigned_count,
                SUM(CASE WHEN (t.submitted_by = ? OR t.assigned_to = ?)
                              AND t.status NOT IN ('resolved','closed')
                         THEN 1 ELSE 0 END) AS mine_count
            FROM tickets t
            LEFT JOIN sla_thresholds s ON s.priority = t.priority
            {counter_where}
        """, [g.user['id'], g.user['id']] + counter_params).fetchone()

    counters = {
        'open': counters_row['open_count'] or 0,
        'in_progress': counters_row['in_progress_count'] or 0,
        'overdue': counters_row['overdue_count'] or 0,
        'unassigned': counters_row['unassigned_count'] or 0,
        'mine': counters_row['mine_count'] or 0,
    }

    if view == 'list':
        return render_template('tickets/list.html',
                               tickets=tickets, status=status, ttype=ttype)

    # Board view — group tickets by status
    columns = {'open': [], 'in_progress': [], 'waiting': [], 'resolved': []}
    if show_closed:
        columns['closed'] = []
    for t in tickets:
        if t['status'] in columns:
            columns[t['status']].append(t)

    return render_template('tickets/board.html',
                           columns=columns,
                           counters=counters,
                           status=status, ttype=ttype,
                           show_closed=show_closed,
                           can_drag=(g.user['role'] in ('admin', 'manager', 'technician')))
```

- [ ] **Step 2: Verify both views still work before the board template exists**

The board template doesn't exist yet, so for now test only the list view:

```bash
curl -s "http://localhost:5555/tickets?view=list" -b <your-session-cookie> | head -20
```

Or in the browser: visit `/tickets?view=list` — expected: the current list view renders normally, employees see only their own tickets, admin sees all.

Visiting `/tickets` without `?view=list` should error (TemplateNotFound) — that's fine; Task 8 creates the template.

- [ ] **Step 3: Commit**

```bash
git add routes/tickets.py
git commit -m "Switch /tickets to board-by-default, add SLA join and counters"
```

---

### Task 8: Create board template + card partial + CSS

**Files:**
- Create: `templates/tickets/board.html`
- Create: `templates/tickets/_card.html`
- Modify: `static/style.css` (append board + card styles at the end of the file)

- [ ] **Step 1: Create `templates/tickets/_card.html`**

```jinja
{# Ticket card partial. Used by board.html. Variables: t (ticket row), can_drag (bool) #}
<a href="{{ url_for('tickets.ticket_detail', ticket_id=t.id) }}"
   class="ticket-card {% if t.is_overdue %}ticket-card-overdue{% endif %}"
   data-ticket-id="{{ t.id }}"
   data-status="{{ t.status }}"
   {% if can_drag %}draggable="true"{% endif %}>
    <div class="ticket-card-head">
        <span class="ticket-card-priority priority-dot-{{ t.priority }}" title="{{ t.priority }}"></span>
        <span class="ticket-card-number">{{ t.ticket_number }}</span>
    </div>
    <div class="ticket-card-title">{{ t.title }}</div>
    <div class="ticket-card-foot">
        <span class="ticket-card-assignee">
            {% if t.assignee_name %}{{ t.assignee_name }}{% else %}Unassigned{% endif %}
        </span>
        <span class="ticket-card-age {% if t.is_overdue %}age-overdue{% endif %}">
            {% if t.age_hours < 24 %}{{ t.age_hours }}h{% else %}{{ (t.age_hours // 24) }}d{% endif %}
        </span>
    </div>
</a>
```

- [ ] **Step 2: Create `templates/tickets/board.html`**

```jinja
{% extends "base.html" %}
{% block title %}SAIL - Tickets{% endblock %}
{% block content %}
<div class="page-header">
    <h2>Tickets</h2>
    <div class="page-header-actions">
        <a href="{{ url_for('tickets.new_ticket') }}" class="btn btn-primary">New Ticket</a>
    </div>
</div>

<div class="view-toggle">
    <a href="?view=board" class="btn btn-sm active">Board</a>
    <a href="?view=list" class="btn btn-sm">List</a>
    <span class="filter-sep">|</span>
    {% if show_closed %}
        <a href="?view=board" class="btn btn-sm">Hide Closed</a>
    {% else %}
        <a href="?view=board&show_closed=1" class="btn btn-sm">Show Closed</a>
    {% endif %}
</div>

<div class="board-counters">
    <button type="button" class="counter-pill" data-filter="all">
        <span class="counter-label">All</span>
        <span class="counter-value">{{ counters.open + counters.in_progress }}</span>
    </button>
    <button type="button" class="counter-pill" data-filter="open">
        <span class="counter-label">Open</span>
        <span class="counter-value">{{ counters.open }}</span>
    </button>
    <button type="button" class="counter-pill" data-filter="in_progress">
        <span class="counter-label">In Progress</span>
        <span class="counter-value">{{ counters.in_progress }}</span>
    </button>
    <button type="button" class="counter-pill counter-pill-overdue" data-filter="overdue">
        <span class="counter-label">Overdue</span>
        <span class="counter-value">{{ counters.overdue }}</span>
    </button>
    <button type="button" class="counter-pill" data-filter="unassigned">
        <span class="counter-label">Unassigned</span>
        <span class="counter-value">{{ counters.unassigned }}</span>
    </button>
    <button type="button" class="counter-pill" data-filter="mine">
        <span class="counter-label">Mine</span>
        <span class="counter-value">{{ counters.mine }}</span>
    </button>
</div>

<div class="ticket-board" data-can-drag="{{ '1' if can_drag else '0' }}"
                        data-current-user-id="{{ current_user.id }}">
    {% for col_key, col_tickets in columns.items() %}
    <div class="board-column" data-status="{{ col_key }}">
        <div class="board-column-head">
            <span class="board-column-title">
                {% if col_key == 'open' %}Open
                {% elif col_key == 'in_progress' %}In Progress
                {% elif col_key == 'waiting' %}Waiting
                {% elif col_key == 'resolved' %}Resolved
                {% elif col_key == 'closed' %}Closed
                {% endif %}
            </span>
            <span class="board-column-count">{{ col_tickets|length }}</span>
        </div>
        <div class="board-column-body" data-status="{{ col_key }}">
            {% for t in col_tickets %}
                {% include "tickets/_card.html" %}
            {% endfor %}
            {% if not col_tickets %}
                <div class="board-column-empty">—</div>
            {% endif %}
        </div>
    </div>
    {% endfor %}
</div>

{# Resolve modal — hidden by default, shown by JS when dragging to Resolved #}
<div id="resolve-modal" class="modal-backdrop" hidden>
    <div class="modal">
        <h3>Resolve ticket</h3>
        <p id="resolve-modal-ticket" class="modal-subtitle"></p>
        <label for="resolve-note"><strong>Resolution note</strong> (required)</label>
        <textarea id="resolve-note" rows="4" required
                  placeholder="What was done to resolve this?"></textarea>
        <div class="modal-actions">
            <button type="button" class="btn" id="resolve-cancel">Cancel</button>
            <button type="button" class="btn btn-primary" id="resolve-confirm">Resolve</button>
        </div>
    </div>
</div>

{% if can_drag %}
<script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.2/Sortable.min.js"></script>
{% endif %}
<script src="{{ url_for('static', filename='ticket_board.js') }}"></script>
<script>lucide.createIcons();</script>
{% endblock %}
```

- [ ] **Step 3: Append board styles to `static/style.css`**

Append to the end of `static/style.css`:

```css
/* ── Ticket Board ────────────────────────────────────────────── */

.view-toggle {
    display: flex;
    gap: .5rem;
    align-items: center;
    margin-bottom: 1rem;
}

.board-counters {
    display: flex;
    flex-wrap: wrap;
    gap: .5rem;
    margin-bottom: 1rem;
}
.counter-pill {
    display: inline-flex;
    gap: .5rem;
    align-items: center;
    padding: .35rem .75rem;
    border: 1px solid var(--border);
    border-radius: 999px;
    background: var(--card-bg);
    color: var(--text);
    cursor: pointer;
    font-size: .85rem;
}
.counter-pill:hover { background: var(--hover); }
.counter-pill.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.counter-pill-overdue .counter-value { color: #c92a2a; font-weight: 700; }
.counter-pill-overdue.active .counter-value { color: #fff; }

.ticket-board {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 1rem;
    align-items: start;
}
.board-column {
    background: var(--bg-alt);
    border: 1px solid var(--border);
    border-radius: 8px;
    min-height: 200px;
}
.board-column-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: .6rem .8rem;
    border-bottom: 1px solid var(--border);
}
.board-column-title { font-weight: 600; font-size: .9rem; text-transform: uppercase; letter-spacing: .05em; }
.board-column-count {
    background: var(--border);
    color: var(--text);
    border-radius: 999px;
    padding: .1rem .5rem;
    font-size: .75rem;
}
.board-column-body {
    padding: .6rem;
    display: flex;
    flex-direction: column;
    gap: .5rem;
    min-height: 100px;
}
.board-column-empty {
    color: var(--muted);
    text-align: center;
    padding: 1rem 0;
    font-size: .85rem;
}

.ticket-card {
    display: block;
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-left: 3px solid transparent;
    border-radius: 6px;
    padding: .55rem .7rem;
    text-decoration: none;
    color: var(--text);
    cursor: pointer;
    transition: box-shadow .1s ease, transform .1s ease;
}
.ticket-card:hover { box-shadow: 0 2px 6px rgba(0,0,0,.08); }
.ticket-card[draggable="true"] { cursor: grab; }
.ticket-card.sortable-chosen { opacity: .6; }
.ticket-card.sortable-ghost { opacity: .3; }
.ticket-card-overdue { border-left-color: #c92a2a; }

.ticket-card-head {
    display: flex;
    align-items: center;
    gap: .4rem;
    margin-bottom: .3rem;
}
.ticket-card-number { color: var(--muted); font-size: .75rem; margin-left: auto; }
.ticket-card-priority {
    display: inline-block;
    width: 10px; height: 10px; border-radius: 50%;
    flex-shrink: 0;
}
.priority-dot-critical { background: #c92a2a; }
.priority-dot-high     { background: #e8590c; }
.priority-dot-medium   { background: #f59f00; }
.priority-dot-low      { background: #868e96; }

.ticket-card-title {
    font-size: .9rem;
    line-height: 1.3;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}
.ticket-card-foot {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: .5rem;
    font-size: .75rem;
    color: var(--muted);
}
.ticket-card-age {
    background: var(--border);
    color: var(--text);
    padding: .1rem .4rem;
    border-radius: 4px;
    font-weight: 600;
}
.ticket-card-age.age-overdue {
    background: #c92a2a;
    color: #fff;
}

/* ── Resolve modal ─────────────────────────────────────────── */
.modal-backdrop {
    position: fixed; inset: 0;
    background: rgba(0,0,0,.45);
    display: flex; align-items: center; justify-content: center;
    z-index: 1000;
}
.modal-backdrop[hidden] { display: none; }
.modal {
    background: var(--card-bg);
    border-radius: 8px;
    padding: 1.25rem 1.5rem;
    width: min(440px, 90vw);
    box-shadow: 0 10px 40px rgba(0,0,0,.3);
}
.modal h3 { margin: 0 0 .25rem 0; }
.modal-subtitle { color: var(--muted); font-size: .85rem; margin: 0 0 1rem 0; }
.modal label { display: block; margin-bottom: .3rem; }
.modal textarea { width: 100%; font: inherit; padding: .5rem; resize: vertical;
                  border: 1px solid var(--border); border-radius: 4px; background: var(--bg); color: var(--text); }
.modal-actions { display: flex; justify-content: flex-end; gap: .5rem; margin-top: 1rem; }
```

> **Note on CSS variables:** This stylesheet uses `var(--border)`, `var(--card-bg)`, `var(--bg-alt)`, `var(--text)`, `var(--muted)`, `var(--hover)`, `var(--accent)`. Verify these already exist in the top of `static/style.css` (open the file and grep for `--border`). If any are missing in the light/dark theme blocks, use the closest existing variable (e.g. `--border-color`, `--bg-card`) and adjust these class rules to match. Do not invent new variables in this task — matching existing ones keeps the theme switch working.

- [ ] **Step 4: Verify CSS variable names**

```bash
cd /mnt/d/m.alkhalifa/Documents/sail-project && grep -E "^\s+--" static/style.css | head -30
```

If a variable used above doesn't exist, rename in the new rules to match the actual names. Commit with the matching names.

- [ ] **Step 5: Smoke-test the board renders (no drag yet — Task 9 wires JS)**

Restart the app, visit `/tickets`. Expected:
- Four columns render (Open / In Progress / Waiting / Resolved).
- Any existing tickets appear in their status column with title, priority dot, age, assignee.
- Counter pills show correct totals at the top.
- `[Board] [List]` toggle works — clicking List returns to the old view.
- As an employee, board shows only tickets you submitted.

If any ticket's `created_at` is older than its SLA threshold, verify the red left-border and red age badge appear.

- [ ] **Step 6: Commit**

```bash
git add templates/tickets/board.html templates/tickets/_card.html static/style.css
git commit -m "Add kanban board template, card partial, and board styles"
```

---

### Task 9: Wire drag-drop, counter filters, and resolve modal in JS

**Files:**
- Create: `static/ticket_board.js`

- [ ] **Step 1: Create `static/ticket_board.js`**

```javascript
/* Ticket board: counter filters (always), drag-drop (admin/manager/technician only),
   resolve-modal gating on drop-to-resolved. */
(function () {
    const board = document.querySelector('.ticket-board');
    if (!board) return;

    const canDrag = board.dataset.canDrag === '1';
    const currentUserId = parseInt(board.dataset.currentUserId, 10);

    /* ── Counter filters (client-side hide/show, no reload) ─────────── */
    const pills = document.querySelectorAll('.counter-pill');
    pills.forEach(pill => pill.addEventListener('click', () => {
        const filter = pill.dataset.filter;
        const alreadyActive = pill.classList.contains('active');
        pills.forEach(p => p.classList.remove('active'));
        if (alreadyActive) {
            // Toggle off — show all
            showAllCards();
            return;
        }
        pill.classList.add('active');
        applyFilter(filter);
    }));

    function showAllCards() {
        document.querySelectorAll('.ticket-card').forEach(c => c.style.display = '');
    }

    function applyFilter(filter) {
        document.querySelectorAll('.ticket-card').forEach(card => {
            card.style.display = matches(card, filter) ? '' : 'none';
        });
    }

    function matches(card, filter) {
        if (filter === 'all') return true;
        const status = card.dataset.status;
        if (filter === 'open') return status === 'open';
        if (filter === 'in_progress') return status === 'in_progress';
        if (filter === 'overdue') return card.classList.contains('ticket-card-overdue');
        if (filter === 'unassigned') {
            const who = card.querySelector('.ticket-card-assignee');
            return who && who.textContent.trim() === 'Unassigned' &&
                   status !== 'resolved' && status !== 'closed';
        }
        if (filter === 'mine') {
            // Mine = assigned to me OR submitted by me. The card doesn't carry
            // submitter id, so we can only filter by assignee label here.
            // Keep scope simple: match assignee name containing current user name.
            const myName = (document.querySelector('.user-name') || {}).textContent || '';
            const who = (card.querySelector('.ticket-card-assignee') || {}).textContent || '';
            return who.trim() === myName.trim();
        }
        return true;
    }

    /* ── Drag-drop ──────────────────────────────────────────────────── */
    if (!canDrag || typeof Sortable === 'undefined') return;

    const columns = document.querySelectorAll('.board-column-body');
    columns.forEach(col => {
        new Sortable(col, {
            group: 'tickets',
            animation: 150,
            ghostClass: 'sortable-ghost',
            chosenClass: 'sortable-chosen',
            onEnd: handleDrop,
        });
    });

    async function handleDrop(evt) {
        const card = evt.item;
        const ticketId = card.dataset.ticketId;
        const newStatus = evt.to.dataset.status;
        const oldStatus = card.dataset.status;
        if (newStatus === oldStatus) return;

        if (newStatus === 'resolved') {
            const note = await promptResolution(card);
            if (note === null) {
                revert(card, evt.from, evt.oldIndex);
                return;
            }
            await postStatus(card, newStatus, note, evt);
        } else {
            await postStatus(card, newStatus, '', evt);
        }
    }

    async function postStatus(card, newStatus, resolution, evt) {
        try {
            const resp = await fetch(`/tickets/${card.dataset.ticketId}/status`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({status: newStatus, resolution}),
            });
            const data = await resp.json();
            if (!resp.ok || !data.ok) {
                toast(data.error || 'Update failed.');
                revert(card, evt.from, evt.oldIndex);
                return;
            }
            card.dataset.status = newStatus;
        } catch (err) {
            toast('Network error. Please retry.');
            revert(card, evt.from, evt.oldIndex);
        }
    }

    function revert(card, originalCol, originalIndex) {
        // Put the card back where it started
        const sibling = originalCol.children[originalIndex];
        if (sibling) {
            originalCol.insertBefore(card, sibling);
        } else {
            originalCol.appendChild(card);
        }
    }

    /* ── Resolve modal ──────────────────────────────────────────────── */
    const modal = document.getElementById('resolve-modal');
    const noteInput = document.getElementById('resolve-note');
    const subtitle = document.getElementById('resolve-modal-ticket');
    const btnCancel = document.getElementById('resolve-cancel');
    const btnConfirm = document.getElementById('resolve-confirm');

    function promptResolution(card) {
        return new Promise(resolve => {
            subtitle.textContent = card.querySelector('.ticket-card-number').textContent
                                 + ' — ' + card.querySelector('.ticket-card-title').textContent;
            noteInput.value = '';
            modal.hidden = false;
            noteInput.focus();

            const cleanup = () => {
                btnCancel.removeEventListener('click', onCancel);
                btnConfirm.removeEventListener('click', onConfirm);
                modal.hidden = true;
            };
            const onCancel = () => { cleanup(); resolve(null); };
            const onConfirm = () => {
                const v = noteInput.value.trim();
                if (!v) { noteInput.focus(); return; }
                cleanup(); resolve(v);
            };
            btnCancel.addEventListener('click', onCancel);
            btnConfirm.addEventListener('click', onConfirm);
        });
    }

    /* ── Toast ──────────────────────────────────────────────────────── */
    function toast(msg) {
        const el = document.createElement('div');
        el.className = 'flash flash-error';
        el.textContent = msg;
        el.style.cssText = 'position:fixed;top:1rem;right:1rem;z-index:1100;box-shadow:0 4px 12px rgba(0,0,0,.2);';
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 4000);
    }
})();
```

- [ ] **Step 2: Smoke-test drag-drop as admin**

Reload `/tickets` logged in as an admin. Expected:

1. **Drag open→in_progress:** card moves, a very brief network request fires, status persists on refresh.
2. **Drag something→resolved:** modal appears. Click Cancel → card snaps back. Re-drag → enter a note → click Resolve → card lands in Resolved column, `resolved_at` gets set.
3. **Drag something→resolved** with an empty note and click Resolve → nothing happens (validation blocks submit).
4. **Counter pills:** click Overdue — only overdue cards remain visible. Click the same pill again — all show. Click Mine — only cards assigned to you.
5. Log out, log back in as an `employee` role — cards are not draggable (no grab cursor), but clicking opens the detail page.

- [ ] **Step 3: Commit**

```bash
git add static/ticket_board.js
git commit -m "Wire SortableJS drag-drop, counter filters, and resolve modal"
```

---

### Task 10: Final smoke test + documentation cross-check

- [ ] **Step 1: Backdate a ticket to force overdue**

```bash
cd /mnt/d/m.alkhalifa/Documents/sail-project && sqlite3 sail.db \
    "UPDATE tickets SET created_at = datetime('now', '-30 days') WHERE id = (SELECT id FROM tickets LIMIT 1);"
```

Reload `/tickets` — that ticket's card should now have a red left-border and red age badge ("30d").

- [ ] **Step 2: End-to-end check**

Walk through as a manager user:
1. `/admin/sla` — change medium to 1 hour, save.
2. `/tickets` — every open/in_progress/waiting ticket with medium priority older than 1h is now overdue.
3. Drag one to In Progress, one to Waiting, one to Resolved (enter a note). Each persists, each shows in audit_log.
4. Toggle `[List]` — the same tickets appear in the list view with their new statuses.
5. `/admin/sla` — restore medium back to 168.
6. Remove the backdate: `sqlite3 sail.db "UPDATE tickets SET created_at = datetime('now') WHERE id = <the-id-you-backdated>;"`

As a plain employee:
1. `/tickets` — only your submitted tickets appear, no drag handles.
2. Click a card — detail page loads normally. Comment and close normally.

- [ ] **Step 3: Cross-check that the existing update flow still works**

Open any ticket from the list view, change priority via the detail form, save. Confirm the change reflects on the board (priority dot color changes).

- [ ] **Step 4: Final commit (only if anything was tweaked during smoke-testing; otherwise skip)**

```bash
git status
# If clean: done. If not, fix and:
# git add <files> && git commit -m "fix: <what>"
```

- [ ] **Step 5: Mark plan complete**

Check all boxes in this plan document, add a note at the top:

```markdown
> **Status:** Completed 2026-04-XX
```

---

## Out of scope (reminder)

- Weekly / monthly reports
- Spreadsheet export
- Per-ticket-type SLA overrides, pause/resume, business-hours calendar
- Ticket attachments, rich comments, full-text search
- Inventory-side improvements (bulk actions, pagination, richer search, asset history)

Each of these is a separate spec when you're ready.
