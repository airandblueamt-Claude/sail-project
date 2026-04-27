# Asset Issue Tracking — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-purpose SAIL as a single-team tool where the AMT control team logs issues against specific assets, emails the affected end user, and accumulates per-asset issue history. Booking flow is hidden behind a feature flag, not deleted.

**Architecture:** Same Flask app, same blueprints, same SQLite DB. Three additive schema changes (two `tickets` columns, one `employees` column, one new `issue_categories` lookup table). One new blueprint for issue-category admin. One new asset-detail route. Existing email service gains one helper. The booking module stays registered behind a `BOOKINGS_ENABLED` feature flag.

**Tech Stack:** Flask, Jinja2, SQLite via `database.get_db()` context manager, `werkzeug.security` for password hashing (already a Flask dependency), Gmail SMTP via existing `email_service.py`. No automated test suite — verification is manual against a freshly-rebuilt `sail.db`.

**Source spec:** `docs/superpowers/specs/2026-04-27-tickets-and-asset-control-design.md`

---

## File Map

**Created:**
- `routes/issue_categories.py` — list / add / toggle-active endpoints for the team-managed dropdown.
- `templates/issue_categories/index.html` — admin page.
- `templates/account/password.html` — self-service password change form.
- `templates/inventory/asset_detail.html` — per-asset page with issue history + Raise Issue button.

**Modified:**
- `schema.sql` — add 3 `tickets` columns, 1 `employees` column, new `issue_categories` table.
- `init_db.py` — after schema load, seed the four control-team accounts (with hashed `Aramco@123`) and the ten starter issue categories.
- `config.py` — add `BOOKINGS_ENABLED = False`.
- `app.py` — context processor exposing `bookings_enabled`; rewrite `/login` to require password; add `/account/password`; remove `/register` from public routes; register the new `issue_categories_bp`.
- `email_service.py` — add `notify_affected_user(ticket, kind)`.
- `routes/bookings.py` — `before_request` 404 guard.
- `routes/dashboard.py` — replace booking-centric tiles with control-team tiles; gate booking queries.
- `routes/inventory.py` — new `/inventory/asset/<id>` detail route.
- `routes/tickets.py` — accept `?asset_id=`; require resolution on resolve transition; trigger affected-user emails; load issue categories for the form; default `type='incident'`.
- `routes/reports.py` — gate booking SELECTs.
- `templates/login.html` — add password field.
- `templates/base.html` — gate booking sidebar links; add Settings → Issue Categories link.
- `templates/dashboard.html` — control-team tiles; gate booking blocks.
- `templates/tickets/new.html` — drop type field, add issue-category dropdown + affected-user fields, asset preselect.
- `templates/tickets/detail.html` — show affected user + issue category in header; require resolution when status set to resolved.
- `templates/reports/inventory.html` — gate booking blocks.

---

## Task 1: Schema delta + seed script

**Files:**
- Modify: `schema.sql:53-57` (employees), `schema.sql:142-167` (tickets), append a new `issue_categories` table block before the audit_log section at `schema.sql:182`.
- Modify: `init_db.py` — extend `main()` to seed users + categories.

- [ ] **Step 1: Add `password_hash` column to employees**

In `schema.sql`, replace the existing `employees` CREATE TABLE (lines 46-57) with:

```sql
CREATE TABLE IF NOT EXISTS employees (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    badge_number    TEXT UNIQUE,
    department_id   INTEGER REFERENCES departments(id),
    phone           TEXT,
    email           TEXT,
    role            TEXT DEFAULT 'employee'
                    CHECK(role IN ('admin','manager','technician','employee')),
    password_hash   TEXT,
    is_active       INTEGER DEFAULT 1,
    created_at      TEXT DEFAULT (datetime('now'))
);
```

- [ ] **Step 2: Add three columns to tickets**

In `schema.sql`, replace the existing `tickets` CREATE TABLE (the block starting at line 144 with `CREATE TABLE IF NOT EXISTS tickets`) — add the three new columns just before `created_at`:

```sql
CREATE TABLE IF NOT EXISTS tickets (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_number       TEXT NOT NULL UNIQUE,
    type                TEXT NOT NULL
                        CHECK(type IN ('maintenance','move','new_request',
                                       'incident','decommission','other')),
    priority            TEXT DEFAULT 'medium'
                        CHECK(priority IN ('low','medium','high','critical')),
    status              TEXT DEFAULT 'open'
                        CHECK(status IN ('open','in_progress','waiting','resolved','closed')),
    asset_id            INTEGER REFERENCES assets(id),
    submitted_by        INTEGER NOT NULL REFERENCES employees(id),
    assigned_to         INTEGER REFERENCES employees(id),
    title               TEXT NOT NULL,
    description         TEXT,
    resolution          TEXT,
    resolved_at         TEXT,
    closed_at           TEXT,
    affected_user_name  TEXT,
    affected_user_email TEXT,
    issue_category_id   INTEGER REFERENCES issue_categories(id),
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);
```

Then add this index right after the existing ticket indexes:

```sql
CREATE INDEX IF NOT EXISTS idx_tickets_issue_cat ON tickets(issue_category_id);
```

- [ ] **Step 3: Add issue_categories table**

In `schema.sql`, insert this block immediately above the `-- ── Audit log ──` divider (line 182):

```sql
-- ── Issue categories (team-managed dropdown for tickets) ───────────────────

CREATE TABLE IF NOT EXISTS issue_categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    is_active   INTEGER DEFAULT 1,
    created_by  INTEGER REFERENCES employees(id),
    created_at  TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_issue_categories_active ON issue_categories(is_active);

```

Note SQLite needs `issue_categories` to exist *before* the `tickets` foreign key references it. Because both tables are created in the same `executescript()` call inside `init_db.py` and SQLite enforces FKs at insert time (not at CREATE), placement order is not strict — but for readability put `issue_categories` above the audit_log section, which keeps it ahead of the actual ticket inserts that the seed script will perform.

- [ ] **Step 4: Extend init_db.py to seed users + categories**

Replace the entire body of `init_db.py` with:

```python
"""
Initialize the SAIL database from schema.sql, then seed the four
control-team accounts and the starter issue categories.

Usage:  python init_db.py
Output: sail.db (SQLite, schema applied, seed data inserted).
        Any existing sail.db is deleted.

After running this, run import_assets_v3.py to load the inventory data.
"""
import sqlite3
import os
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "sail.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

CONTROL_TEAM = [
    ("Mohammad Khalifa",      "airandblueamt@gmail.com"),
    ("M. Shaikh",             "m.shaikh@amt-arabia.net"),
    ("Omar Bawadod",          "omar.bawadod@aramco.com"),
    ("Ali Almatrood",         "ali.almatrood@aramco.com"),
]
SEED_PASSWORD = "Aramco@123"

ISSUE_CATEGORIES = [
    "Display / Screen issue",
    "Touch / Calibration failure",
    "Won't power on",
    "Slow / Freezing",
    "Software / OS issue",
    "Network / Connectivity",
    "Printer issue (jam, toner, quality)",
    "Peripheral issue (keyboard, mouse, audio, camera)",
    "Physical damage",
    "Other",
]


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")

    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())

    # Seed the four control-team accounts.
    pw_hash = generate_password_hash(SEED_PASSWORD)
    for name, email in CONTROL_TEAM:
        conn.execute(
            "INSERT INTO employees (name, email, role, password_hash, is_active) "
            "VALUES (?, ?, 'admin', ?, 1)",
            (name, email, pw_hash))
    print(f"Seeded {len(CONTROL_TEAM)} control-team accounts (password: {SEED_PASSWORD!r}).")

    # Seed the starter issue categories.
    creator_id = conn.execute(
        "SELECT id FROM employees WHERE email = ?",
        (CONTROL_TEAM[0][1],)).fetchone()[0]
    for name in ISSUE_CATEGORIES:
        conn.execute(
            "INSERT INTO issue_categories (name, is_active, created_by) "
            "VALUES (?, 1, ?)",
            (name, creator_id))
    print(f"Seeded {len(ISSUE_CATEGORIES)} issue categories.")

    conn.commit()
    conn.close()

    print(f"Schema + seed applied. Database ready at {DB_PATH}")
    print("Next: python import_assets_v3.py")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run init + verify schema**

Run:

```bash
python init_db.py
```

Expected output:
```
Removed existing /home/malkhalifa/sail-project/sail.db
Seeded 4 control-team accounts (password: 'Aramco@123').
Seeded 10 issue categories.
Schema + seed applied. Database ready at /home/malkhalifa/sail-project/sail.db
Next: python import_assets_v3.py
```

Then verify the schema and seed:

```bash
sqlite3 sail.db "SELECT email, role, length(password_hash) > 0 AS has_pw FROM employees;"
sqlite3 sail.db "SELECT name, is_active FROM issue_categories;"
sqlite3 sail.db ".schema tickets"
```

Expected: 4 rows from employees (all `admin`, all `has_pw=1`); 10 rows from issue_categories (all `is_active=1`); the tickets schema includes `affected_user_name`, `affected_user_email`, `issue_category_id`.

- [ ] **Step 6: Re-run the asset import (the spreadsheet still imports cleanly into the new schema)**

```bash
python import_assets_v3.py
```

Expected: backs up the empty DB, imports 230 assets, no errors. Verify:

```bash
sqlite3 sail.db "SELECT COUNT(*) FROM assets;"
```

Expected: `230`.

- [ ] **Step 7: Commit**

```bash
git add schema.sql init_db.py
git commit -m "$(cat <<'EOF'
Schema + seed: password hashes, issue categories, control-team accounts

Adds employees.password_hash, three new tickets columns
(affected_user_name, affected_user_email, issue_category_id),
and the issue_categories lookup table. init_db.py now seeds the
four control-team accounts with Aramco@123 and the ten starter
issue categories.
EOF
)"
```

---

## Task 2: Password authentication

**Files:**
- Modify: `app.py:42-103` — rewrite login route, remove standalone register route, add `/account/password`.
- Modify: `templates/login.html:21-27` — add password field.
- Create: `templates/account/password.html` — password change form.

- [ ] **Step 1: Rewrite the login route to require a password**

In `app.py`, replace the entire `def login()` block (lines 42-61) with:

```python
    # ── Login (email + password) ────────────────────────────────────
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        from werkzeug.security import check_password_hash
        if g.user:
            return redirect(url_for('dashboard.index'))
        error = None
        if request.method == 'POST':
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')
            if not email or not password:
                error = 'Email and password are required.'
            else:
                with get_db() as conn:
                    user = conn.execute(
                        "SELECT * FROM employees WHERE LOWER(email) = LOWER(?) AND is_active = 1",
                        (email,)).fetchone()
                if user and user['password_hash'] and check_password_hash(user['password_hash'], password):
                    session['user_id'] = user['id']
                    return redirect(url_for('dashboard.index'))
                error = 'Invalid credentials.'
        return render_template('login.html', error=error)
```

- [ ] **Step 2: Remove the public /register route**

In `app.py`, delete the entire `def register()` block (was lines 64-103 before edits). Replace it with nothing — registration is no longer offered to anonymous visitors.

Then update the `public` tuple inside `load_user()` (line 33). Change:

```python
        public = ('login', 'register', 'static')
```

to:

```python
        public = ('login', 'static')
```

This means any unauthenticated request to `/register` will redirect to `/login`, but since the route no longer exists at all, hitting it directly will 404. Both behaviors are acceptable.

- [ ] **Step 3: Add /account/password route**

In `app.py`, immediately after the `def logout()` block, add:

```python
    # ── Password change (self-service) ──────────────────────────────
    @app.route('/account/password', methods=['GET', 'POST'])
    def change_password():
        from werkzeug.security import check_password_hash, generate_password_hash
        error = None
        if request.method == 'POST':
            current = request.form.get('current_password', '')
            new1 = request.form.get('new_password', '')
            new2 = request.form.get('confirm_password', '')
            if not current or not new1 or not new2:
                error = 'All fields are required.'
            elif new1 != new2:
                error = 'New passwords do not match.'
            elif len(new1) < 8:
                error = 'New password must be at least 8 characters.'
            else:
                with get_db() as conn:
                    row = conn.execute(
                        "SELECT password_hash FROM employees WHERE id = ?",
                        (g.user['id'],)).fetchone()
                    if not row or not row['password_hash'] or not check_password_hash(row['password_hash'], current):
                        error = 'Current password is incorrect.'
                    else:
                        conn.execute(
                            "UPDATE employees SET password_hash = ? WHERE id = ?",
                            (generate_password_hash(new1), g.user['id']))
                        flash('Password updated.', 'success')
                        return redirect(url_for('dashboard.index'))
        return render_template('account/password.html', error=error)
```

- [ ] **Step 4: Add the password field to the login form**

In `templates/login.html`, replace the `<form>` block (lines 21-27) with:

```html
        <form method="post">
            <div class="form-row">
                <label>Email</label>
                <input type="email" name="email" class="input" placeholder="name@amt.com" required autofocus>
            </div>
            <div class="form-row">
                <label>Password</label>
                <input type="password" name="password" class="input" placeholder="••••••••" required>
            </div>
            <button type="submit" class="btn btn-primary btn-full">Sign In</button>
        </form>
```

Then delete the line below the form that says `<p class="auth-footer">Don't have an account? <a href="{{ url_for('register') }}">Register here</a></p>` — `url_for('register')` will fail at template render once the route is gone.

- [ ] **Step 5: Create the password change template**

Create `templates/account/password.html`:

```html
{% extends "base.html" %}
{% block title %}SAIL - Change Password{% endblock %}
{% block content %}
<div class="page-header">
    <h2>Change Password</h2>
</div>

{% if error %}
<div class="flash flash-error">{{ error }}</div>
{% endif %}

<form method="post" class="form-card" style="max-width:480px">
    <div class="form-row">
        <label>Current Password</label>
        <input type="password" name="current_password" class="input" required autofocus>
    </div>
    <div class="form-row">
        <label>New Password</label>
        <input type="password" name="new_password" class="input" minlength="8" required>
    </div>
    <div class="form-row">
        <label>Confirm New Password</label>
        <input type="password" name="confirm_password" class="input" minlength="8" required>
    </div>
    <div class="form-actions">
        <button type="submit" class="btn btn-primary">Update Password</button>
        <a href="{{ url_for('dashboard.index') }}" class="btn btn-ghost">Cancel</a>
    </div>
</form>
{% endblock %}
```

- [ ] **Step 6: Boot the app and verify login**

Run:

```bash
python app.py
```

In a browser, open `http://localhost:5555` — you should be redirected to `/login`. The form has email + password fields.

Verify the four scenarios:

1. Empty password → "Email and password are required."
2. Email `airandblueamt@gmail.com` + wrong password → "Invalid credentials."
3. Unknown email + any password → "Invalid credentials." (same wording — no enumeration)
4. Email `airandblueamt@gmail.com` + password `Aramco@123` → redirects to dashboard.

Then visit `http://localhost:5555/account/password` and confirm the form renders. Change your password to `NewTest@123`, log out (click the logout link in the sidebar), and verify the new password works while `Aramco@123` no longer does.

**Reset for the next task:** stop the app (Ctrl+C), then re-run `python init_db.py && python import_assets_v3.py` to restore the seeded password.

- [ ] **Step 7: Commit**

```bash
git add app.py templates/login.html templates/account/password.html
git commit -m "$(cat <<'EOF'
Auth: require password on login, add self-service password change

Login now validates email + password against employees.password_hash
using werkzeug.security. Public /register route removed; team
accounts are seeded by init_db.py. New /account/password lets
logged-in users rotate their own password.
EOF
)"
```

---

## Task 3: Hide bookings behind feature flag

**Files:**
- Modify: `config.py` — add `BOOKINGS_ENABLED = False`.
- Modify: `app.py` — context processor exposing the flag.
- Modify: `routes/bookings.py` — `before_request` guard.
- Modify: `templates/base.html` — gate the three booking sidebar links.
- Modify: `routes/dashboard.py` — skip booking queries when flag off (template gating in Task 8).
- Modify: `routes/reports.py` — skip booking queries when flag off.
- Modify: `templates/reports/inventory.html` — gate booking blocks.

- [ ] **Step 1: Add the flag to config**

Append to `config.py`:

```python

# ── Feature flags ───────────────────────────────────────────────────
BOOKINGS_ENABLED = False
```

- [ ] **Step 2: Expose the flag to templates**

In `app.py`, find the existing `inject_user` context processor (around line 37-39):

```python
    @app.context_processor
    def inject_user():
        return dict(current_user=g.user)
```

Replace it with:

```python
    @app.context_processor
    def inject_globals():
        from config import BOOKINGS_ENABLED
        return dict(current_user=g.user, bookings_enabled=BOOKINGS_ENABLED)
```

- [ ] **Step 3: Add the 404 guard to the bookings blueprint**

Open `routes/bookings.py`. Find the line that creates the blueprint (likely `bookings_bp = Blueprint('bookings', __name__)` near the top). Immediately after that line, add:

```python
from flask import abort
from config import BOOKINGS_ENABLED


@bookings_bp.before_request
def gate_bookings():
    if not BOOKINGS_ENABLED:
        abort(404)
```

(If `abort` is already imported via `from flask import …`, just add `abort` to the existing import list rather than duplicating the line.)

- [ ] **Step 4: Gate the booking sidebar links**

Open `templates/base.html`. Find the three booking-related `<li>` blocks at lines 22-25, 25-26, and 37-38 (the `Browse & Book`, `My Bookings`, and `Booking Approvals` links from the sidebar grep). Wrap each one's `<li>...</li>` in a `{% if bookings_enabled %} ... {% endif %}` block.

Concretely, find this segment (around line 22):

```html
            <li><a href="{{ url_for('inventory.models') }}" class="...">
                <i data-lucide="search"></i> Browse &amp; Book
            </a></li>
            <li><a href="{{ url_for('bookings.my_bookings') }}" class="...">
                <i data-lucide="calendar-check"></i> My Bookings
            </a></li>
```

Replace it with:

```html
            {% if bookings_enabled %}
            <li><a href="{{ url_for('inventory.models') }}" class="...">
                <i data-lucide="search"></i> Browse &amp; Book
            </a></li>
            <li><a href="{{ url_for('bookings.my_bookings') }}" class="...">
                <i data-lucide="calendar-check"></i> My Bookings
            </a></li>
            {% endif %}
```

(Preserve the actual class attributes that are already in the file — the snippet above truncates them.)

Then find the admin "Booking Approvals" link (around line 37-38):

```html
            <li><a href="{{ url_for('bookings.admin_queue') }}" class="...">
                <i data-lucide="clipboard-check"></i> Booking Approvals
            </a></li>
```

Wrap it the same way:

```html
            {% if bookings_enabled %}
            <li><a href="{{ url_for('bookings.admin_queue') }}" class="...">
                <i data-lucide="clipboard-check"></i> Booking Approvals
            </a></li>
            {% endif %}
```

- [ ] **Step 5: Skip booking queries in dashboard route**

Open `routes/dashboard.py`. Find every booking SELECT (lines 35, 39, 53, 65-66, 81 per the earlier grep). Wrap each block in an `if BOOKINGS_ENABLED:` guard. At the top of the file, add:

```python
from config import BOOKINGS_ENABLED
```

Then for every block of code that touches the `bookings` table, wrap it. For example, replace:

```python
        admin_stats['pending_bookings'] = conn.execute(
            "SELECT COUNT(*) FROM bookings WHERE status='pending'"
        ).fetchone()[0]
```

with:

```python
        if BOOKINGS_ENABLED:
            admin_stats['pending_bookings'] = conn.execute(
                "SELECT COUNT(*) FROM bookings WHERE status='pending'"
            ).fetchone()[0]
        else:
            admin_stats['pending_bookings'] = 0
```

For the per-user `my_bookings_count` and `recent_bookings` queries (lines 35-39 and 53), default to `0` and `[]` respectively when the flag is off so the template gating in Task 8 doesn't crash on missing keys.

(Task 8 rewrites the dashboard template entirely, so any references in the *current* template that fall outside an `{% if bookings_enabled %}` block can stay as-is for now — the route just stops paying for the data.)

- [ ] **Step 6: Skip booking queries in reports route**

Open `routes/reports.py`. At the top, add:

```python
from config import BOOKINGS_ENABLED
```

Then wrap the booking query blocks (lines 94-118 per the earlier grep — `bookings_created`, the top-models query, `recent_bookings`) in `if BOOKINGS_ENABLED:` guards. For each variable consumed by the template, set a safe default in the `else:` branch:

```python
        if BOOKINGS_ENABLED:
            history['bookings_created'] = conn.execute(
                "SELECT COUNT(*) FROM bookings WHERE created_at >= ? AND created_at < ?",
                (start, end)).fetchone()[0]
            # ... the other booking aggregates ...
            recent_bookings = conn.execute("""...""").fetchall()
            top_models = conn.execute("""...""").fetchall()
        else:
            history['bookings_created'] = 0
            history['bookings_approved'] = 0
            history['bookings_returned'] = 0
            history['bookings_pending'] = 0
            recent_bookings = []
            top_models = []
```

(Use whatever the existing variable names are — adapt the dict keys to match the actual code.)

- [ ] **Step 7: Gate booking blocks in the reports template**

Open `templates/reports/inventory.html`. Wrap the three booking-related sections (around lines 87, 114, 122-128 from the earlier grep) in `{% if bookings_enabled %} ... {% endif %}`:

```html
{% if bookings_enabled %}
<div class="stat-body"><span class="stat-value">{{ history.bookings_created }}</span><span class="stat-label">Bookings Created</span></div>
{% endif %}
```

Same pattern for the table column showing `r.bookings` and the `{% if recent_bookings %} ... {% endif %}` block.

- [ ] **Step 8: Run and verify**

```bash
python app.py
```

Log in. Verify:

1. Sidebar shows **no** booking links (no "Browse & Book", "My Bookings", or "Booking Approvals").
2. Visit `http://localhost:5555/bookings` directly → 404.
3. Visit `http://localhost:5555/bookings/admin` directly → 404.
4. Dashboard loads without errors (it may look sparse — Task 8 fills it in).
5. Reports page (`/reports`) loads, no booking stats visible.

- [ ] **Step 9: Commit**

```bash
git add config.py app.py routes/bookings.py routes/dashboard.py routes/reports.py templates/base.html templates/reports/inventory.html
git commit -m "$(cat <<'EOF'
Hide bookings behind BOOKINGS_ENABLED feature flag

Sidebar links, dashboard queries, reports queries, and the
bookings blueprint itself all gate on the flag. Flipping
BOOKINGS_ENABLED back to True restores everything; tables
and route logic are untouched.
EOF
)"
```

---

## Task 4: Issue category admin page

**Files:**
- Create: `routes/issue_categories.py` — new blueprint with list/add/toggle endpoints.
- Create: `templates/issue_categories/index.html` — admin page.
- Modify: `app.py` — register the new blueprint.
- Modify: `templates/base.html` — add a Settings → Issue Categories sidebar link.

- [ ] **Step 1: Create the blueprint module**

Create `routes/issue_categories.py`:

```python
"""Team-managed issue category list (the dropdown on the ticket form)."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from database import get_db, log_audit

issue_categories_bp = Blueprint('issue_categories', __name__)


@issue_categories_bp.route('/')
def index():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT ic.*, e.name AS creator_name
            FROM issue_categories ic
            LEFT JOIN employees e ON ic.created_by = e.id
            ORDER BY ic.is_active DESC, ic.name COLLATE NOCASE
        """).fetchall()
    return render_template('issue_categories/index.html', categories=rows)


@issue_categories_bp.route('/add', methods=['POST'])
def add():
    name = request.form.get('name', '').strip()
    if not name:
        flash('Name is required.', 'error')
        return redirect(url_for('issue_categories.index'))
    with get_db() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO issue_categories (name, is_active, created_by) "
                "VALUES (?, 1, ?)",
                (name, g.user['id']))
            log_audit(conn, 'issue_categories', cur.lastrowid, 'create',
                      changed_by=g.user['id'])
            flash(f'Added "{name}".', 'success')
        except Exception as e:
            if 'UNIQUE' in str(e):
                flash('Category already exists.', 'error')
            else:
                raise
    return redirect(url_for('issue_categories.index'))


@issue_categories_bp.route('/<int:cat_id>/toggle', methods=['POST'])
def toggle(cat_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT name, is_active FROM issue_categories WHERE id = ?",
            (cat_id,)).fetchone()
        if not row:
            flash('Category not found.', 'error')
            return redirect(url_for('issue_categories.index'))
        new_active = 0 if row['is_active'] else 1
        conn.execute(
            "UPDATE issue_categories SET is_active = ? WHERE id = ?",
            (new_active, cat_id))
        log_audit(conn, 'issue_categories', cat_id, 'status_change',
                  'is_active', row['is_active'], new_active,
                  changed_by=g.user['id'])
        flash(f'"{row["name"]}" {"reactivated" if new_active else "deactivated"}.', 'success')
    return redirect(url_for('issue_categories.index'))
```

- [ ] **Step 2: Create the template**

Create `templates/issue_categories/index.html`:

```html
{% extends "base.html" %}
{% block title %}SAIL - Issue Categories{% endblock %}
{% block content %}
<div class="page-header">
    <h2>Issue Categories</h2>
    <p class="muted">The dropdown on the ticket form. Add new ones as new failure modes appear.</p>
</div>

<form method="post" action="{{ url_for('issue_categories.add') }}" class="form-card" style="max-width:560px;margin-bottom:24px">
    <div class="form-row" style="display:flex;gap:8px;align-items:flex-end">
        <div style="flex:1">
            <label>New category name</label>
            <input type="text" name="name" class="input" required maxlength="80"
                   placeholder="e.g. HDMI cable failure">
        </div>
        <button type="submit" class="btn btn-primary">Add</button>
    </div>
</form>

<table class="data-table">
    <thead>
        <tr>
            <th>Name</th>
            <th>Status</th>
            <th>Created by</th>
            <th>Created</th>
            <th></th>
        </tr>
    </thead>
    <tbody>
        {% for c in categories %}
        <tr {% if not c.is_active %}style="opacity:.55"{% endif %}>
            <td>{{ c.name }}</td>
            <td>
                {% if c.is_active %}
                    <span class="badge badge-success">Active</span>
                {% else %}
                    <span class="badge badge-muted">Inactive</span>
                {% endif %}
            </td>
            <td>{{ c.creator_name or '—' }}</td>
            <td>{{ c.created_at[:10] }}</td>
            <td>
                <form method="post" action="{{ url_for('issue_categories.toggle', cat_id=c.id) }}" style="display:inline">
                    <button type="submit" class="btn btn-sm btn-ghost">
                        {% if c.is_active %}Deactivate{% else %}Reactivate{% endif %}
                    </button>
                </form>
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>
{% endblock %}
```

- [ ] **Step 3: Register the blueprint**

In `app.py`, find the blueprint registration block (lines 112-126). Add the import alongside the others:

```python
    from routes.issue_categories import issue_categories_bp
```

And register it:

```python
    app.register_blueprint(issue_categories_bp, url_prefix='/issue-categories')
```

- [ ] **Step 4: Add a sidebar link**

In `templates/base.html`, find a sensible spot near the bottom of the sidebar nav (after the existing admin links). Add:

```html
            <li><a href="{{ url_for('issue_categories.index') }}" class="{% if request.endpoint and request.endpoint.startswith('issue_categories.') %}active{% endif %}">
                <i data-lucide="tags"></i> Issue Categories
            </a></li>
```

- [ ] **Step 5: Run and verify**

```bash
python app.py
```

Log in. Click the new "Issue Categories" sidebar link. Expected: a table with the 10 seeded categories, all marked Active. Verify:

1. Add a new category called `Test Category 1` → it appears in the table.
2. Try to add `test category 1` (lowercase) → "Category already exists." error.
3. Click Deactivate on `Other` → row dimmed and badge shows Inactive.
4. Click Reactivate on `Other` → back to Active.

- [ ] **Step 6: Commit**

```bash
git add routes/issue_categories.py templates/issue_categories/ app.py templates/base.html
git commit -m "$(cat <<'EOF'
Add team-managed issue categories admin page

New /issue-categories page for the team to add and toggle the
dropdown that appears on the ticket form. UNIQUE COLLATE NOCASE
on the name column blocks case-variant duplicates. Deactivating
hides from the dropdown without breaking historical references.
EOF
)"
```

---

## Task 5: Ticket form — issue category, affected user, asset preselect

**Files:**
- Modify: `routes/tickets.py:77-113` — load issue categories, accept `?asset_id=`, default `type='incident'`, persist new fields.
- Modify: `templates/tickets/new.html` — replace type field with issue category dropdown, add affected-user fields, asset preselect.

- [ ] **Step 1: Update the new_ticket route**

In `routes/tickets.py`, replace the entire `new_ticket()` function (lines 77-113) with:

```python
@tickets_bp.route('/new', methods=['GET', 'POST'])
def new_ticket():
    with get_db() as conn:
        if request.method == 'POST':
            asset_id = request.form.get('asset_id', type=int)
            issue_cat_id = request.form.get('issue_category_id', type=int)
            if not asset_id:
                flash('Asset is required.', 'error')
                return redirect(request.url)
            if not issue_cat_id:
                flash('Issue category is required.', 'error')
                return redirect(request.url)

            ticket_num = next_ticket_number(conn)
            cur = conn.execute("""
                INSERT INTO tickets
                    (ticket_number, type, priority, title, description,
                     asset_id, submitted_by, issue_category_id,
                     affected_user_name, affected_user_email)
                VALUES (?, 'incident', ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticket_num,
                request.form.get('priority', 'medium'),
                request.form['title'],
                request.form.get('description', ''),
                asset_id,
                g.user['id'],
                issue_cat_id,
                request.form.get('affected_user_name', '').strip() or None,
                request.form.get('affected_user_email', '').strip() or None,
            ))
            log_audit(conn, 'tickets', cur.lastrowid, 'create',
                      changed_by=g.user['id'])
            flash(f'Ticket {ticket_num} created.', 'success')
            return redirect(url_for('tickets.ticket_detail', ticket_id=cur.lastrowid))

        preselect_asset_id = request.args.get('asset_id', type=int)
        assets = conn.execute("""
            SELECT a.id, a.asset_tag, em.name, em.brand
            FROM assets a JOIN equipment_models em ON a.equipment_model_id = em.id
            ORDER BY a.asset_tag
        """).fetchall()
        categories = conn.execute("""
            SELECT id, name FROM issue_categories
            WHERE is_active = 1 ORDER BY name COLLATE NOCASE
        """).fetchall()

    return render_template('tickets/new.html',
                           assets=assets,
                           categories=categories,
                           preselect_asset_id=preselect_asset_id)
```

(Note: the affected-user email notification is wired in Task 7, not here. This task ships the form changes only.)

- [ ] **Step 2: Replace the ticket form template**

Replace the entire contents of `templates/tickets/new.html` with:

```html
{% extends "base.html" %}
{% block title %}SAIL - New Ticket{% endblock %}
{% block content %}
<div class="page-header">
    <div>
        <a href="{{ url_for('tickets.list_tickets') }}" class="breadcrumb">Tickets</a>
        <h2>Raise New Issue</h2>
    </div>
</div>

<form method="post" class="form-card">
    <div class="form-row">
        <label>Asset *</label>
        <select name="asset_id" required class="input">
            <option value="">-- pick an asset --</option>
            {% for a in assets %}
            <option value="{{ a.id }}" {% if preselect_asset_id == a.id %}selected{% endif %}>
                {{ a.asset_tag }} — {{ a.name }}{% if a.brand %} ({{ a.brand }}){% endif %}
            </option>
            {% endfor %}
        </select>
    </div>

    <div class="form-row-group">
        <div class="form-row" style="flex:1">
            <label>Issue Category *</label>
            <select name="issue_category_id" required class="input">
                <option value="">-- pick a category --</option>
                {% for c in categories %}
                <option value="{{ c.id }}">{{ c.name }}</option>
                {% endfor %}
            </select>
            <small><a href="{{ url_for('issue_categories.index') }}" target="_blank">+ add new category</a></small>
        </div>
        <div class="form-row">
            <label>Priority</label>
            <select name="priority" class="input">
                <option value="low">Low</option>
                <option value="medium" selected>Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
            </select>
        </div>
    </div>

    <div class="form-row">
        <label>Title *</label>
        <input type="text" name="title" required class="input" maxlength="200"
               placeholder="One-line summary, e.g. 'Display flickers under 1080p'">
    </div>
    <div class="form-row">
        <label>Description</label>
        <textarea name="description" rows="4" class="input"
                  placeholder="What is happening? When did it start? Anything the user already tried?"></textarea>
    </div>

    <h4 style="margin-top:24px;margin-bottom:8px">Affected user (optional)</h4>
    <p class="muted" style="margin-top:0;margin-bottom:12px">If you fill in an email, the user will be notified when the ticket is received and again when it is resolved.</p>
    <div class="form-row-group">
        <div class="form-row" style="flex:1">
            <label>Name</label>
            <input type="text" name="affected_user_name" class="input" maxlength="120">
        </div>
        <div class="form-row" style="flex:1">
            <label>Email</label>
            <input type="email" name="affected_user_email" class="input" placeholder="user@aramco.com">
        </div>
    </div>

    <div class="form-actions">
        <button type="submit" class="btn btn-primary">Submit Ticket</button>
        <a href="{{ url_for('tickets.list_tickets') }}" class="btn btn-ghost">Cancel</a>
    </div>
</form>
{% endblock %}
```

- [ ] **Step 3: Run and verify**

```bash
python app.py
```

Log in. Navigate to `http://localhost:5555/tickets/new`. Expected:

1. Asset dropdown is populated; nothing preselected.
2. Issue Category dropdown shows the 10 seeded categories.
3. Priority defaults to Medium.
4. There is no "Type" dropdown anymore.
5. Affected user fields are present at the bottom.

Then visit `http://localhost:5555/tickets/new?asset_id=1` (or any valid asset id from `sqlite3 sail.db "SELECT id, asset_tag FROM assets LIMIT 5;"`). Expected: that asset is preselected in the Asset dropdown.

Submit a ticket with affected user `Test User` / `test@example.com`. Verify in DB:

```bash
sqlite3 sail.db "SELECT ticket_number, type, issue_category_id, affected_user_name, affected_user_email FROM tickets ORDER BY id DESC LIMIT 1;"
```

Expected: type is `incident`, issue_category_id is non-null, affected_user_name and affected_user_email are populated.

Submit a second ticket with no asset selected → form rejects with "Asset is required." Submit with no category → "Issue category is required."

- [ ] **Step 4: Commit**

```bash
git add routes/tickets.py templates/tickets/new.html
git commit -m "$(cat <<'EOF'
Ticket form: issue category, affected user, asset preselect

Replaces the legacy Type dropdown with a single Issue Category
dropdown sourced from issue_categories. Asset is now required
and can be preselected via ?asset_id=. Optional affected-user
name + email fields capture who reported the issue (email is
used by Task 7 for notifications). Tickets are stamped
type='incident' server-side for compatibility with the
existing schema.
EOF
)"
```

---

## Task 6: Asset detail page with issue history

**Files:**
- Modify: `routes/inventory.py` — add a new `/inventory/asset/<int:asset_id>` route.
- Create: `templates/inventory/asset_detail.html`.
- Modify: `templates/inventory/manage_assets.html` — make the asset tag a link to the new detail page.

- [ ] **Step 1: Add the asset detail route**

Open `routes/inventory.py`. After the existing `manage_assets()` function (around line 391-411), add:

```python
@inventory_bp.route('/asset/<int:asset_id>')
def asset_detail(asset_id):
    with get_db() as conn:
        asset = conn.execute("""
            SELECT a.*, em.name AS model_name, em.brand, em.model_number,
                   c.name AS category_name, l.name AS location_name
            FROM assets a
            JOIN equipment_models em ON a.equipment_model_id = em.id
            LEFT JOIN categories c ON em.category_id = c.id
            LEFT JOIN locations l ON a.location_id = l.id
            WHERE a.id = ?
        """, (asset_id,)).fetchone()
        if not asset:
            flash('Asset not found.', 'error')
            return redirect(url_for('inventory.manage_assets'))

        tickets = conn.execute("""
            SELECT t.id, t.ticket_number, t.title, t.status, t.priority,
                   t.created_at, t.resolved_at, t.resolution,
                   ic.name AS category_name,
                   e.name AS submitter_name
            FROM tickets t
            LEFT JOIN issue_categories ic ON t.issue_category_id = ic.id
            LEFT JOIN employees e ON t.submitted_by = e.id
            WHERE t.asset_id = ?
            ORDER BY t.created_at DESC
        """, (asset_id,)).fetchall()

    return render_template('inventory/asset_detail.html',
                           asset=asset, tickets=tickets)
```

- [ ] **Step 2: Create the asset detail template**

Create `templates/inventory/asset_detail.html`:

```html
{% extends "base.html" %}
{% block title %}SAIL - {{ asset.asset_tag }}{% endblock %}
{% block content %}
<div class="page-header">
    <div>
        <a href="{{ url_for('inventory.manage_assets') }}" class="breadcrumb">Assets</a>
        <h2>{{ asset.asset_tag }}</h2>
        <p class="muted">{{ asset.model_name }}{% if asset.brand %} — {{ asset.brand }}{% endif %}</p>
    </div>
    <div>
        <a href="{{ url_for('tickets.new_ticket', asset_id=asset.id) }}" class="btn btn-primary">
            <i data-lucide="alert-circle"></i> Raise New Issue
        </a>
    </div>
</div>

<div class="card" style="margin-bottom:24px">
    <h4 style="margin-top:0">Asset Summary</h4>
    <table class="data-table compact">
        <tr><th>Tag</th><td>{{ asset.asset_tag }}</td></tr>
        <tr><th>Model</th><td>{{ asset.model_name }}{% if asset.model_number %} ({{ asset.model_number }}){% endif %}</td></tr>
        <tr><th>Category</th><td>{{ asset.category_name or '—' }}</td></tr>
        <tr><th>Location</th><td>{{ asset.location_name or '—' }}</td></tr>
        <tr><th>Status</th><td><span class="badge">{{ asset.status }}</span></td></tr>
        <tr><th>Condition</th><td>{{ asset.condition }}</td></tr>
        <tr><th>Serial</th><td>{{ asset.serial_number or '—' }}</td></tr>
        <tr><th>Holder (from import)</th><td>{{ asset.holder_name or '—' }}</td></tr>
        {% if asset.notes %}<tr><th>Notes</th><td>{{ asset.notes }}</td></tr>{% endif %}
    </table>
</div>

<div class="card">
    <h4 style="margin-top:0">Issue History</h4>
    {% if not tickets %}
        <p class="muted">No tickets have been raised against this asset yet.</p>
    {% else %}
    <table class="data-table">
        <thead>
            <tr>
                <th>Ticket</th>
                <th>Opened</th>
                <th>Category</th>
                <th>Priority</th>
                <th>Status</th>
                <th>Title</th>
                <th>Resolved</th>
            </tr>
        </thead>
        <tbody>
            {% for t in tickets %}
            <tr>
                <td><a href="{{ url_for('tickets.ticket_detail', ticket_id=t.id) }}">{{ t.ticket_number }}</a></td>
                <td>{{ t.created_at[:10] }}</td>
                <td>{{ t.category_name or '—' }}</td>
                <td><span class="badge badge-{{ t.priority }}">{{ t.priority }}</span></td>
                <td><span class="badge">{{ t.status }}</span></td>
                <td>{{ t.title }}</td>
                <td>{{ t.resolved_at[:10] if t.resolved_at else '—' }}</td>
            </tr>
            {% if t.resolution %}
            <tr><td></td><td colspan="6" class="muted" style="font-size:0.9em"><strong>Resolution:</strong> {{ t.resolution }}</td></tr>
            {% endif %}
            {% endfor %}
        </tbody>
    </table>
    {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 3: Link from the asset list to the detail page**

Open `templates/inventory/manage_assets.html`. Find the line that displays `asset_tag` for each row. It will look something like:

```html
<td>{{ a.asset_tag }}</td>
```

Replace it with:

```html
<td><a href="{{ url_for('inventory.asset_detail', asset_id=a.id) }}">{{ a.asset_tag }}</a></td>
```

If the existing template uses a different cell structure, just wrap the asset_tag value in the same `<a href="...">` link.

- [ ] **Step 4: Run and verify**

```bash
python app.py
```

Log in. Visit `http://localhost:5555/inventory/assets`. Expected: asset tags are now clickable. Click one — you land on the detail page showing the asset summary card and (since you raised a test ticket against an asset in Task 5) the Issue History table.

Click "Raise New Issue" → ticket form opens with that asset preselected (this confirms the round-trip from Task 5).

- [ ] **Step 5: Commit**

```bash
git add routes/inventory.py templates/inventory/asset_detail.html templates/inventory/manage_assets.html
git commit -m "$(cat <<'EOF'
Asset detail page with per-asset issue history

New /inventory/asset/<id> route renders the asset summary plus
every ticket ever raised against it (newest first), with a
prominent Raise New Issue button that pre-fills the ticket form.
This is the load-bearing screen that turns the ticket trail
into the team's institutional memory.
EOF
)"
```

---

## Task 7: Resolution required + affected-user email notifications

**Files:**
- Modify: `email_service.py` — append `notify_affected_user(ticket, kind)`.
- Modify: `routes/tickets.py` — call `notify_affected_user` on create (kind='created') and on resolve transition (kind='resolved'); reject resolve without resolution.
- Modify: `templates/tickets/detail.html` — show affected user + issue category in header; add `required` to resolution textarea when status is resolved.

- [ ] **Step 1: Add the email helper**

Append to `email_service.py`:

```python
def notify_affected_user(ticket, kind):
    """Email the affected end user about ticket creation or resolution.

    `ticket` is a dict-like row that must include: ticket_number, title,
    description, resolution, asset_tag, equipment_name, affected_user_email.
    `kind` ∈ {'created', 'resolved'}. No-op if affected_user_email is blank.
    """
    email = ticket.get('affected_user_email')
    if not email:
        return

    asset_label = f"{ticket.get('asset_tag', '')} — {ticket.get('equipment_name', '')}".strip(" —")
    if kind == 'created':
        subject = f"Ticket #{ticket['ticket_number']} received: {ticket['title']}"
        body_html = f"""
        <p>Hi,</p>
        <p>We have received your issue and opened ticket
           <strong>#{ticket['ticket_number']}</strong>.</p>
        <p><strong>Asset:</strong> {asset_label}<br>
           <strong>Issue:</strong> {ticket['title']}</p>
        <p><strong>What you reported:</strong><br>
           {(ticket.get('description') or '').replace(chr(10), '<br>')}</p>
        <p>We will email you again once it is resolved. If you need to add
           anything, just reply to this email.</p>
        <p>— SAIL (AMT control team)</p>
        """
    elif kind == 'resolved':
        subject = f"Ticket #{ticket['ticket_number']} resolved: {ticket['title']}"
        body_html = f"""
        <p>Hi,</p>
        <p>Ticket <strong>#{ticket['ticket_number']}</strong> has been
           resolved.</p>
        <p><strong>Asset:</strong> {asset_label}<br>
           <strong>Issue:</strong> {ticket['title']}</p>
        <p><strong>Resolution:</strong><br>
           {(ticket.get('resolution') or '').replace(chr(10), '<br>')}</p>
        <p>If the issue is not actually fixed, reply to this email and we
           will reopen the ticket.</p>
        <p>— SAIL (AMT control team)</p>
        """
    else:
        return

    send_email(email, subject, _base_html(body_html))
```

- [ ] **Step 2: Wire the helper into ticket creation**

Open `routes/tickets.py`. At the top of the file, replace the existing email import:

```python
from email_service import notify_ticket_created, notify_ticket_update
```

with:

```python
from email_service import notify_ticket_created, notify_ticket_update, notify_affected_user
```

Then, inside `new_ticket()` (which Task 5 already rewrote), after the existing `log_audit(...)` call and before the `flash(...)` line, add:

```python
            # Send "we got your ticket" to the affected user (no-op if blank).
            created = conn.execute("""
                SELECT t.ticket_number, t.title, t.description, t.resolution,
                       t.affected_user_email, a.asset_tag, em.name AS equipment_name
                FROM tickets t
                LEFT JOIN assets a ON t.asset_id = a.id
                LEFT JOIN equipment_models em ON a.equipment_model_id = em.id
                WHERE t.id = ?
            """, (cur.lastrowid,)).fetchone()
            notify_affected_user(dict(created), 'created')
```

- [ ] **Step 3: Require resolution + email on resolve transition**

In `routes/tickets.py`, replace the entire `update_ticket()` function (lines 173-214) with:

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
        resolution = request.form.get('resolution', old['resolution'] or '').strip()

        # Resolution is required when transitioning into 'resolved'.
        if new_status == 'resolved' and old['status'] != 'resolved' and not resolution:
            flash('Resolution is required when resolving a ticket.', 'error')
            return redirect(url_for('tickets.ticket_detail', ticket_id=ticket_id))

        extra = ""
        params = [new_status, new_priority, new_assignee, resolution]
        if new_status == 'resolved' and old['status'] != 'resolved':
            extra = ", resolved_at=datetime('now')"
        if new_status == 'closed' and old['status'] != 'closed':
            extra += ", closed_at=datetime('now')"

        conn.execute(f"""
            UPDATE tickets SET status=?, priority=?, assigned_to=?,
                   resolution=?, updated_at=datetime('now') {extra}
            WHERE id=?
        """, params + [ticket_id])

        if new_status != old['status']:
            log_audit(conn, 'tickets', ticket_id, 'status_change',
                      'status', old['status'], new_status,
                      changed_by=g.user['id'])
            # Email the original ticket submitter (existing behavior).
            submitter = conn.execute(
                "SELECT email FROM employees WHERE id=?", (old['submitted_by'],)
            ).fetchone()
            if submitter and submitter['email']:
                updated_ticket = conn.execute(
                    "SELECT * FROM tickets WHERE id=?", (ticket_id,)
                ).fetchone()
                notify_ticket_update(dict(updated_ticket), submitter['email'],
                                     'status_change', g.user['name'])

            # NEW: when resolved, also email the affected end user.
            if new_status == 'resolved':
                resolved = conn.execute("""
                    SELECT t.ticket_number, t.title, t.description, t.resolution,
                           t.affected_user_email, a.asset_tag, em.name AS equipment_name
                    FROM tickets t
                    LEFT JOIN assets a ON t.asset_id = a.id
                    LEFT JOIN equipment_models em ON a.equipment_model_id = em.id
                    WHERE t.id = ?
                """, (ticket_id,)).fetchone()
                notify_affected_user(dict(resolved), 'resolved')

        flash('Ticket updated.', 'success')
    return redirect(url_for('tickets.ticket_detail', ticket_id=ticket_id))
```

- [ ] **Step 4: Show affected user + category in ticket detail**

Open `templates/tickets/detail.html`. Find the existing header / metadata block (where it shows submitter, status, priority, etc.). Add two rows for the affected user and the issue category.

Look for an existing block that resembles:

```html
<dt>Submitted by</dt><dd>{{ ticket.submitter_name }}</dd>
```

Add immediately after it (or in the equivalent metadata grid):

```html
<dt>Issue Category</dt>
<dd>{% if ticket.category_name %}{{ ticket.category_name }}{% else %}—{% endif %}</dd>

<dt>Affected User</dt>
<dd>
    {% if ticket.affected_user_name or ticket.affected_user_email %}
        {{ ticket.affected_user_name or '' }}
        {% if ticket.affected_user_email %}
            &lt;<a href="mailto:{{ ticket.affected_user_email }}">{{ ticket.affected_user_email }}</a>&gt;
        {% endif %}
    {% else %}
        —
    {% endif %}
</dd>
```

For these to render, the `ticket_detail()` route's SELECT must include those columns. Update the SELECT in `routes/tickets.py:119-128` from:

```python
        ticket = conn.execute("""
            SELECT t.*, e.name as submitter_name, ea.name as assignee_name,
                   a.asset_tag, em.name as equipment_name
            FROM tickets t
            JOIN employees e ON t.submitted_by = e.id
            LEFT JOIN employees ea ON t.assigned_to = ea.id
            LEFT JOIN assets a ON t.asset_id = a.id
            LEFT JOIN equipment_models em ON a.equipment_model_id = em.id
            WHERE t.id = ?
        """, (ticket_id,)).fetchone()
```

to:

```python
        ticket = conn.execute("""
            SELECT t.*, e.name as submitter_name, ea.name as assignee_name,
                   a.asset_tag, em.name as equipment_name,
                   ic.name as category_name
            FROM tickets t
            JOIN employees e ON t.submitted_by = e.id
            LEFT JOIN employees ea ON t.assigned_to = ea.id
            LEFT JOIN assets a ON t.asset_id = a.id
            LEFT JOIN equipment_models em ON a.equipment_model_id = em.id
            LEFT JOIN issue_categories ic ON t.issue_category_id = ic.id
            WHERE t.id = ?
        """, (ticket_id,)).fetchone()
```

(`affected_user_name`, `affected_user_email`, and `issue_category_id` already come through via `t.*`; only the joined `category_name` is new.)

- [ ] **Step 5: Run and verify**

```bash
python app.py
```

1. Open the test ticket created in Task 5. Verify the detail page shows the issue category and the affected user (`Test User <test@example.com>`).
2. Without filling the resolution field, set status to `resolved` and submit. Expected: the form is rejected with "Resolution is required when resolving a ticket."
3. Fill the resolution field with `Replaced HDMI cable.` and set status to `resolved`. Expected: success flash; the resolution is saved.
4. Look at the terminal where `python app.py` is running. Without `SAIL_SMTP_PASSWORD` set, you should see two `[EMAIL SKIP] ...` lines logged — one for the original ticket creation (when this ticket was created in Task 5 — wait, that ticket was created before this code existed, so only the resolved one should log). Resolve the ticket and confirm one log line:
   ```
   [EMAIL SKIP] No SMTP password configured. Would send to test@example.com: SAIL - Ticket #TKT-0001 resolved: ...
   ```
5. Create a brand-new ticket with affected_user_email set, then immediately resolve it. Expected: two log lines (one created, one resolved).
6. Open the asset's detail page (Task 6's screen). The resolved ticket now shows `Replaced HDMI cable.` under "Resolution" in the issue history table.

- [ ] **Step 6: Commit**

```bash
git add email_service.py routes/tickets.py templates/tickets/detail.html
git commit -m "$(cat <<'EOF'
Email affected users on ticket create + resolve, require resolution

New email_service.notify_affected_user(ticket, kind) sends the
affected end user a confirmation when their ticket is created
and a "your issue is resolved" message when it is closed out.
The ticket update route now rejects status='resolved'
without a resolution note. Ticket detail page surfaces both
the issue category and the affected user.
EOF
)"
```

---

## Task 8: Control-team dashboard

**Files:**
- Modify: `routes/dashboard.py` — replace booking-centric stats with the four control-team tiles.
- Modify: `templates/dashboard.html` — render the new tiles, gate any leftover booking blocks.

- [ ] **Step 1: Inspect the current dashboard route**

Open `routes/dashboard.py` and read it end-to-end so you understand the existing structure (it's ~111 lines). Note which template variables it currently passes — your replacement must keep the names the template expects, OR you replace both together (which is what we do here).

- [ ] **Step 2: Replace the dashboard route**

Replace the entire body of `routes/dashboard.py` with:

```python
"""Dashboard — single-role landing page for the control team."""
from flask import Blueprint, render_template, g
from database import get_db
from config import BOOKINGS_ENABLED

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
def index():
    with get_db() as conn:
        stats = {}

        # Open tickets count.
        stats['open_tickets'] = conn.execute(
            "SELECT COUNT(*) FROM tickets WHERE status IN ('open','in_progress','waiting')"
        ).fetchone()[0]

        # High / critical priority queue (top 5).
        stats['priority_queue'] = conn.execute("""
            SELECT t.id, t.ticket_number, t.title, t.priority, t.created_at,
                   a.asset_tag, ic.name AS category_name
            FROM tickets t
            LEFT JOIN assets a ON t.asset_id = a.id
            LEFT JOIN issue_categories ic ON t.issue_category_id = ic.id
            WHERE t.status IN ('open','in_progress','waiting')
              AND t.priority IN ('critical','high')
            ORDER BY CASE t.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 END,
                     t.created_at DESC
            LIMIT 5
        """).fetchall()

        # Recently resolved (last 5).
        stats['recently_resolved'] = conn.execute("""
            SELECT t.id, t.ticket_number, t.title, t.resolved_at,
                   a.asset_tag, ic.name AS category_name
            FROM tickets t
            LEFT JOIN assets a ON t.asset_id = a.id
            LEFT JOIN issue_categories ic ON t.issue_category_id = ic.id
            WHERE t.status = 'resolved'
            ORDER BY t.resolved_at DESC
            LIMIT 5
        """).fetchall()

        # Unhealthy assets (in maintenance or damaged).
        stats['unhealthy_assets'] = conn.execute("""
            SELECT a.id, a.asset_tag, a.status, a.condition,
                   em.name AS model_name, l.name AS location_name
            FROM assets a
            JOIN equipment_models em ON a.equipment_model_id = em.id
            LEFT JOIN locations l ON a.location_id = l.id
            WHERE a.status = 'maintenance' OR a.condition = 'damaged'
            ORDER BY a.asset_tag
            LIMIT 20
        """).fetchall()

        # Asset counts (totals + in-use vs available).
        counts = conn.execute("""
            SELECT
                SUM(CASE WHEN status='available' THEN 1 ELSE 0 END) AS available,
                SUM(CASE WHEN status='in_use'    THEN 1 ELSE 0 END) AS in_use,
                COUNT(*) AS total
            FROM assets
        """).fetchone()
        stats['asset_counts'] = dict(counts) if counts else {'available': 0, 'in_use': 0, 'total': 0}

        # Bookings — only if the flag is on (used by the gated template block).
        if BOOKINGS_ENABLED:
            stats['pending_bookings'] = conn.execute(
                "SELECT COUNT(*) FROM bookings WHERE status='pending'"
            ).fetchone()[0]
        else:
            stats['pending_bookings'] = 0

    return render_template('dashboard.html', stats=stats)
```

- [ ] **Step 3: Replace the dashboard template**

Replace the entire contents of `templates/dashboard.html` with:

```html
{% extends "base.html" %}
{% block title %}SAIL - Dashboard{% endblock %}
{% block content %}

<div class="page-header">
    <div>
        <h2>Welcome, {{ current_user.name.split()[0] }}</h2>
        <p class="muted">{{ stats.open_tickets }} open ticket{{ '' if stats.open_tickets == 1 else 's' }} · {{ stats.asset_counts.total }} assets tracked</p>
    </div>
    <div>
        <a href="{{ url_for('tickets.new_ticket') }}" class="btn btn-primary">
            <i data-lucide="plus"></i> Raise New Issue
        </a>
    </div>
</div>

<div class="stat-grid">
    <div class="stat-card">
        <div class="stat-label">Open Tickets</div>
        <div class="stat-value">{{ stats.open_tickets }}</div>
        <a href="{{ url_for('tickets.list_tickets') }}" class="muted">View all</a>
    </div>
    <div class="stat-card">
        <div class="stat-label">Assets Available</div>
        <div class="stat-value">{{ stats.asset_counts.available or 0 }}</div>
        <span class="muted">of {{ stats.asset_counts.total }}</span>
    </div>
    <div class="stat-card">
        <div class="stat-label">Assets In Use</div>
        <div class="stat-value">{{ stats.asset_counts.in_use or 0 }}</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Unhealthy Assets</div>
        <div class="stat-value">{{ stats.unhealthy_assets|length }}</div>
        <span class="muted">maintenance or damaged</span>
    </div>
    {% if bookings_enabled %}
    <div class="stat-card">
        <div class="stat-label">Pending Bookings</div>
        <div class="stat-value">{{ stats.pending_bookings }}</div>
    </div>
    {% endif %}
</div>

<div class="dashboard-row" style="display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-top:24px">

    <div class="card">
        <h4 style="margin-top:0">High / Critical Priority Queue</h4>
        {% if not stats.priority_queue %}
            <p class="muted">No high or critical priority tickets open. Nice.</p>
        {% else %}
        <table class="data-table compact">
            <thead><tr><th>Ticket</th><th>Title</th><th>Asset</th><th>Priority</th></tr></thead>
            <tbody>
                {% for t in stats.priority_queue %}
                <tr>
                    <td><a href="{{ url_for('tickets.ticket_detail', ticket_id=t.id) }}">{{ t.ticket_number }}</a></td>
                    <td>{{ t.title }}</td>
                    <td>{{ t.asset_tag or '—' }}</td>
                    <td><span class="badge badge-{{ t.priority }}">{{ t.priority }}</span></td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% endif %}
    </div>

    <div class="card">
        <h4 style="margin-top:0">Recently Resolved</h4>
        {% if not stats.recently_resolved %}
            <p class="muted">Nothing resolved yet.</p>
        {% else %}
        <table class="data-table compact">
            <thead><tr><th>Ticket</th><th>Title</th><th>Asset</th><th>Resolved</th></tr></thead>
            <tbody>
                {% for t in stats.recently_resolved %}
                <tr>
                    <td><a href="{{ url_for('tickets.ticket_detail', ticket_id=t.id) }}">{{ t.ticket_number }}</a></td>
                    <td>{{ t.title }}</td>
                    <td>{{ t.asset_tag or '—' }}</td>
                    <td>{{ t.resolved_at[:10] if t.resolved_at else '—' }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% endif %}
    </div>

</div>

<div class="card" style="margin-top:24px">
    <h4 style="margin-top:0">Unhealthy Assets</h4>
    {% if not stats.unhealthy_assets %}
        <p class="muted">All assets are healthy.</p>
    {% else %}
    <table class="data-table compact">
        <thead><tr><th>Tag</th><th>Model</th><th>Location</th><th>Status</th><th>Condition</th></tr></thead>
        <tbody>
            {% for a in stats.unhealthy_assets %}
            <tr>
                <td><a href="{{ url_for('inventory.asset_detail', asset_id=a.id) }}">{{ a.asset_tag }}</a></td>
                <td>{{ a.model_name }}</td>
                <td>{{ a.location_name or '—' }}</td>
                <td><span class="badge">{{ a.status }}</span></td>
                <td>{{ a.condition }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% endif %}
</div>

{% endblock %}
```

- [ ] **Step 4: Run and verify**

```bash
python app.py
```

Log in. The dashboard should now show:

1. A header welcoming the logged-in user, with totals.
2. Four stat cards (Open Tickets, Assets Available, Assets In Use, Unhealthy Assets). No booking card.
3. A two-column layout with the High/Critical queue and Recently Resolved (one of these will be populated from the test ticket you resolved in Task 7).
4. A bottom card listing unhealthy assets (likely empty on a fresh import).
5. The "Raise New Issue" button at top right takes you to the ticket form.

Verify nothing references `bookings.*` endpoints anywhere on the dashboard (search the rendered HTML or just confirm no broken links).

- [ ] **Step 5: Final smoke test against the full spec checklist**

Walk through Section 6 of the spec end-to-end:

```bash
# Reset to a known state.
rm -f sail.db
python init_db.py
python import_assets_v3.py
python app.py
```

In the browser:

1. Log in as `airandblueamt@gmail.com` / `Aramco@123` → success.
2. `/account/password` → change to `NewPass@123`. Log out, log back in with new password. Reset to `Aramco@123` for the next user.
3. Visit `/issue-categories` → 10 seeded categories.
4. Visit `/inventory/assets` → click any asset tag → land on its detail page → click Raise New Issue → ticket form preselects the asset.
5. Fill in: category `Display / Screen issue`, title `Display flickers`, description `User reports intermittent flicker`, affected user `John Doe` / `john@example.com`. Submit.
6. Check terminal log: `[EMAIL SKIP]` line for the create email.
7. Open the new ticket. Try to set status `resolved` without a resolution → rejected.
8. Add resolution `Reseated HDMI cable, no further flicker.`, set status `resolved`, save.
9. Check terminal: another `[EMAIL SKIP]` line for the resolve email.
10. Go back to the asset detail page → ticket appears in Issue History with the resolution shown.
11. Sidebar has no booking links; visiting `/bookings` returns 404.
12. Open `config.py`, flip `BOOKINGS_ENABLED = True`, restart the app, refresh the page → booking links and stat card reappear. Flip back to `False` for production.

- [ ] **Step 6: Commit**

```bash
git add routes/dashboard.py templates/dashboard.html
git commit -m "$(cat <<'EOF'
Control-team dashboard: open tickets, priority queue, asset health

Replaces the booking-centric tiles with four cards (Open Tickets,
Available, In Use, Unhealthy Assets), a side-by-side High/Critical
priority queue and Recently Resolved table, and a bottom panel
listing assets in maintenance or damaged condition. Pending
Bookings tile remains gated behind BOOKINGS_ENABLED for the
day we want it back.
EOF
)"
```

---

## Self-Review

After all tasks complete, walk through this checklist:

1. **Spec coverage** — every numbered section of `docs/superpowers/specs/2026-04-27-tickets-and-asset-control-design.md` should map to a task above. (Task 1 → §4.1, Task 2 → §4.2, Task 3 → §4.8, Task 4 → §4.9, Task 5 → §4.5, Task 6 → §4.4, Task 7 → §4.6 + §4.10, Task 8 → §4.7.)

2. **Smoke test** — run the 12-step sequence in Task 8 Step 5 from a fresh DB. Every step must succeed.

3. **No leftover booking UI** — `grep -RIn "bookings\." templates/ | grep -v "{% if bookings_enabled %}"` should only show lines that already live inside an `{% if bookings_enabled %}` block, or no lines at all from non-bookings templates.

4. **No leftover `register` references** — `grep -RIn "url_for('register')" templates/ app.py` should return nothing.

5. **Audit log populated** — `sqlite3 sail.db "SELECT table_name, action, COUNT(*) FROM audit_log GROUP BY 1, 2;"` should show rows for `tickets:create`, `tickets:status_change`, `issue_categories:create`, `issue_categories:status_change` after exercising the flows.
