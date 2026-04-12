# Asset Agreements & License Tracking — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add flexible support agreement and license tracking to AssetInventory so admins can attach warranty, support contract, and license entries to any asset, with expiry alerting.

**Architecture:** New `asset_agreements` table (one-to-many with `assets`). Agreement CRUD routes added to `routes/assets.py`. Admin overview page added to `routes/admin.py`. Dashboard widget shows expiring/expired counts. Status (active/expiring/expired) is computed from `end_date`, not stored.

**Tech Stack:** Flask, SQLite, Jinja2, existing CSS design system (badges, cards, detail-grid pattern)

---

### Task 1: Add `asset_agreements` table to database schema

**Files:**
- Modify: `/mnt/c/Users/m.alkhalifa/AssetInventory/database.py:31-117` (SCHEMA_SQL string)

- [ ] **Step 1: Add the table and indexes to SCHEMA_SQL**

In `database.py`, append the following SQL just before the closing `"""` of `SCHEMA_SQL` (after line 116, before line 117):

```sql
CREATE TABLE IF NOT EXISTS asset_agreements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id        INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    agreement_type  TEXT    NOT NULL,
    provider        TEXT,
    start_date      TEXT,
    end_date        TEXT,
    notes           TEXT,
    created_at      TEXT    DEFAULT (datetime('now')),
    updated_at      TEXT    DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_agreements_asset ON asset_agreements(asset_id);
CREATE INDEX IF NOT EXISTS idx_agreements_end_date ON asset_agreements(end_date);
CREATE INDEX IF NOT EXISTS idx_agreements_type ON asset_agreements(agreement_type);
```

- [ ] **Step 2: Verify schema initializes without errors**

Run:
```bash
cd /mnt/c/Users/m.alkhalifa/AssetInventory && python -c "from database import init_db; init_db()"
```
Expected: `Database initialized successfully.` with no errors.

- [ ] **Step 3: Verify the table exists**

Run:
```bash
cd /mnt/c/Users/m.alkhalifa/AssetInventory && python -c "
from database import get_db
with get_db() as conn:
    cols = conn.execute('PRAGMA table_info(asset_agreements)').fetchall()
    for c in cols: print(c['name'], c['type'])
"
```
Expected: Lists all 9 columns (id, asset_id, agreement_type, provider, start_date, end_date, notes, created_at, updated_at).

---

### Task 2: Add agreement CRUD routes to `routes/assets.py`

**Files:**
- Modify: `/mnt/c/Users/m.alkhalifa/AssetInventory/routes/assets.py`

- [ ] **Step 1: Update imports**

Replace the import line at the top of `routes/assets.py`:

```python
from flask import Blueprint, render_template, g, redirect, url_for, request
```

with:

```python
from flask import Blueprint, render_template, g, redirect, url_for, request, flash
from database import get_db, log_audit
```

(Also remove the separate `from database import get_db` line since it's now in the combined import.)

- [ ] **Step 2: Update the detail route to fetch agreements**

In the `detail()` function, after the bookings query (after line 55) and before the `return render_template` call, add:

```python
        # Agreements & licenses
        agreements = conn.execute('''
            SELECT *,
                CASE
                    WHEN end_date IS NULL THEN 'active'
                    WHEN end_date < date('now') THEN 'expired'
                    WHEN end_date <= date('now', '+30 days') THEN 'expiring'
                    ELSE 'active'
                END as status
            FROM asset_agreements
            WHERE asset_id = ?
            ORDER BY end_date ASC NULLS LAST
        ''', (asset_id,)).fetchall()
```

Then update the `render_template` call to pass `agreements=agreements`:

```python
    return render_template('assets/detail.html',
                           asset=asset, active_booking=active_booking,
                           bookings=bookings, agreements=agreements)
```

- [ ] **Step 3: Add the "add agreement" route**

After the `detail()` function, add:

```python
@assets_bp.route('/<int:asset_id>/agreements/add', methods=['POST'])
def add_agreement(asset_id):
    if not g.user or g.user['role'] != 'admin':
        flash('Admin access required.', 'error')
        return redirect(url_for('assets.detail', asset_id=asset_id))

    agreement_type = request.form.get('agreement_type', '').strip()
    provider = request.form.get('provider', '').strip() or None
    start_date = request.form.get('start_date', '').strip() or None
    end_date = request.form.get('end_date', '').strip() or None
    notes = request.form.get('notes', '').strip() or None

    if not agreement_type:
        flash('Agreement type is required.', 'error')
        return redirect(url_for('assets.detail', asset_id=asset_id))

    if start_date and end_date and end_date < start_date:
        flash('End date must be on or after start date.', 'error')
        return redirect(url_for('assets.detail', asset_id=asset_id))

    with get_db() as conn:
        cursor = conn.execute('''
            INSERT INTO asset_agreements (asset_id, agreement_type, provider, start_date, end_date, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (asset_id, agreement_type, provider, start_date, end_date, notes))
        log_audit(conn, 'asset_agreements', cursor.lastrowid, 'create',
                  field_name='agreement_type', new_value=agreement_type,
                  changed_by=g.user['name'])

    flash('Agreement added successfully.', 'success')
    return redirect(url_for('assets.detail', asset_id=asset_id))
```

- [ ] **Step 4: Add the "edit agreement" route**

```python
@assets_bp.route('/<int:asset_id>/agreements/<int:agreement_id>/edit', methods=['POST'])
def edit_agreement(asset_id, agreement_id):
    if not g.user or g.user['role'] != 'admin':
        flash('Admin access required.', 'error')
        return redirect(url_for('assets.detail', asset_id=asset_id))

    agreement_type = request.form.get('agreement_type', '').strip()
    provider = request.form.get('provider', '').strip() or None
    start_date = request.form.get('start_date', '').strip() or None
    end_date = request.form.get('end_date', '').strip() or None
    notes = request.form.get('notes', '').strip() or None

    if not agreement_type:
        flash('Agreement type is required.', 'error')
        return redirect(url_for('assets.detail', asset_id=asset_id))

    if start_date and end_date and end_date < start_date:
        flash('End date must be on or after start date.', 'error')
        return redirect(url_for('assets.detail', asset_id=asset_id))

    with get_db() as conn:
        conn.execute('''
            UPDATE asset_agreements
            SET agreement_type = ?, provider = ?, start_date = ?, end_date = ?,
                notes = ?, updated_at = datetime('now')
            WHERE id = ? AND asset_id = ?
        ''', (agreement_type, provider, start_date, end_date, notes,
              agreement_id, asset_id))
        log_audit(conn, 'asset_agreements', agreement_id, 'update',
                  field_name='agreement_type', new_value=agreement_type,
                  changed_by=g.user['name'])

    flash('Agreement updated.', 'success')
    return redirect(url_for('assets.detail', asset_id=asset_id))
```

- [ ] **Step 5: Add the "delete agreement" route**

```python
@assets_bp.route('/<int:asset_id>/agreements/<int:agreement_id>/delete', methods=['POST'])
def delete_agreement(asset_id, agreement_id):
    if not g.user or g.user['role'] != 'admin':
        flash('Admin access required.', 'error')
        return redirect(url_for('assets.detail', asset_id=asset_id))

    with get_db() as conn:
        agreement = conn.execute(
            'SELECT agreement_type FROM asset_agreements WHERE id = ? AND asset_id = ?',
            (agreement_id, asset_id)
        ).fetchone()
        if agreement:
            conn.execute('DELETE FROM asset_agreements WHERE id = ? AND asset_id = ?',
                         (agreement_id, asset_id))
            log_audit(conn, 'asset_agreements', agreement_id, 'delete',
                      field_name='agreement_type', old_value=agreement['agreement_type'],
                      changed_by=g.user['name'])

    flash('Agreement deleted.', 'success')
    return redirect(url_for('assets.detail', asset_id=asset_id))
```

- [ ] **Step 6: Verify routes register**

Run:
```bash
cd /mnt/c/Users/m.alkhalifa/AssetInventory && python -c "
from app import create_app
app = create_app()
for rule in app.url_map.iter_rules():
    if 'agreement' in rule.rule:
        print(rule.rule, rule.methods)
"
```
Expected: Three routes printed — add, edit, delete — each with POST method.

---

### Task 3: Add agreements section to asset detail template

**Files:**
- Modify: `/mnt/c/Users/m.alkhalifa/AssetInventory/templates/assets/detail.html:126-154`

- [ ] **Step 1: Add agreements card between the Status card and Booking History card**

In `detail.html`, find the `<!-- Booking History -->` comment (line 127). Insert the following block BEFORE it:

```html
    <!-- Agreements & Licenses -->
    <div class="detail-card">
      <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;">
        <span><i class="lucide-file-check" style="font-size:16px;"></i> Agreements & Licenses{% if agreements %} ({{ agreements|length }}){% endif %}</span>
        {% if current_user.role == 'admin' %}
        <button class="btn btn-sm btn-primary" onclick="document.getElementById('addAgreementForm').style.display='block'" style="font-size:12px;">
          <i class="lucide-plus" style="font-size:12px;"></i> Add
        </button>
        {% endif %}
      </div>

      {% if current_user.role == 'admin' %}
      <!-- Add Agreement Form (hidden by default) -->
      <div id="addAgreementForm" style="display:none;padding:16px;border-bottom:1px solid var(--gray-100);">
        <form method="POST" action="{{ url_for('assets.add_agreement', asset_id=asset.id) }}">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;">
            <div>
              <label style="font-size:12px;color:var(--gray-600);display:block;margin-bottom:4px;">Type *</label>
              <select name="agreement_type" class="form-control" required>
                <option value="">Select type...</option>
                <option value="Warranty">Warranty</option>
                <option value="Support Contract">Support Contract</option>
                <option value="Software License">Software License</option>
                <option value="Subscription">Subscription</option>
              </select>
            </div>
            <div>
              <label style="font-size:12px;color:var(--gray-600);display:block;margin-bottom:4px;">Provider</label>
              <input type="text" name="provider" class="form-control" placeholder="e.g., Dell, Microsoft">
            </div>
            <div>
              <label style="font-size:12px;color:var(--gray-600);display:block;margin-bottom:4px;">Start Date</label>
              <input type="date" name="start_date" class="form-control">
            </div>
            <div>
              <label style="font-size:12px;color:var(--gray-600);display:block;margin-bottom:4px;">End Date</label>
              <input type="date" name="end_date" class="form-control">
            </div>
          </div>
          <div style="margin-bottom:12px;">
            <label style="font-size:12px;color:var(--gray-600);display:block;margin-bottom:4px;">Notes</label>
            <textarea name="notes" class="form-control" rows="2" placeholder="Contract number, license key, etc."></textarea>
          </div>
          <div style="display:flex;gap:8px;">
            <button type="submit" class="btn btn-primary btn-sm">Save Agreement</button>
            <button type="button" class="btn btn-outline btn-sm" onclick="document.getElementById('addAgreementForm').style.display='none'">Cancel</button>
          </div>
        </form>
      </div>
      {% endif %}

      {% if agreements %}
      <table style="width:100%;font-size:13px;">
        <thead style="background:var(--gray-50);">
          <tr>
            <th style="padding:8px 12px;color:var(--gray-600);font-size:12px;">Type</th>
            <th style="padding:8px 12px;color:var(--gray-600);font-size:12px;">Provider</th>
            <th style="padding:8px 12px;color:var(--gray-600);font-size:12px;">Period</th>
            <th style="padding:8px 12px;color:var(--gray-600);font-size:12px;">Status</th>
            {% if current_user.role == 'admin' %}
            <th style="padding:8px 12px;color:var(--gray-600);font-size:12px;">Actions</th>
            {% endif %}
          </tr>
        </thead>
        <tbody>
        {% for ag in agreements %}
          <tr>
            <td style="padding:10px 12px;font-weight:600;">{{ ag.agreement_type }}</td>
            <td style="padding:10px 12px;">{{ ag.provider or '-' }}</td>
            <td style="padding:10px 12px;font-size:12px;">
              {{ ag.start_date or '—' }} to {{ ag.end_date or 'No expiry' }}
            </td>
            <td style="padding:10px 12px;">
              {% if ag.status == 'expired' %}
                <span class="badge badge-damaged">Expired</span>
              {% elif ag.status == 'expiring' %}
                <span class="badge badge-pending">Expiring Soon</span>
              {% else %}
                <span class="badge badge-good">Active</span>
              {% endif %}
            </td>
            {% if current_user.role == 'admin' %}
            <td style="padding:10px 12px;">
              <div style="display:flex;gap:4px;">
                <button class="btn btn-sm btn-outline" onclick="editAgreement({{ ag.id }}, '{{ ag.agreement_type }}', '{{ ag.provider or '' }}', '{{ ag.start_date or '' }}', '{{ ag.end_date or '' }}', `{{ ag.notes or '' }}`)" style="font-size:11px;">Edit</button>
                <form method="POST" action="{{ url_for('assets.delete_agreement', asset_id=asset.id, agreement_id=ag.id) }}" onsubmit="return confirm('Delete this agreement?')">
                  <button type="submit" class="btn btn-sm btn-danger" style="font-size:11px;">Delete</button>
                </form>
              </div>
            </td>
            {% endif %}
          </tr>
        {% endfor %}
        </tbody>
      </table>
      {% else %}
      <div style="padding:32px;text-align:center;color:var(--gray-400);">No agreements or licenses recorded for this asset.</div>
      {% endif %}
    </div>
```

- [ ] **Step 2: Add the edit modal and JavaScript**

At the bottom of `detail.html`, before `{% endblock %}`, add:

```html
<!-- Edit Agreement Modal -->
<div id="editAgreementModal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:1000;display:none;align-items:center;justify-content:center;">
  <div style="background:var(--bg);border-radius:var(--radius);padding:24px;width:500px;max-width:90vw;">
    <h3 style="margin-bottom:16px;">Edit Agreement</h3>
    <form id="editAgreementFormEl" method="POST">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;">
        <div>
          <label style="font-size:12px;color:var(--gray-600);display:block;margin-bottom:4px;">Type *</label>
          <select name="agreement_type" id="edit_type" class="form-control" required>
            <option value="Warranty">Warranty</option>
            <option value="Support Contract">Support Contract</option>
            <option value="Software License">Software License</option>
            <option value="Subscription">Subscription</option>
          </select>
        </div>
        <div>
          <label style="font-size:12px;color:var(--gray-600);display:block;margin-bottom:4px;">Provider</label>
          <input type="text" name="provider" id="edit_provider" class="form-control">
        </div>
        <div>
          <label style="font-size:12px;color:var(--gray-600);display:block;margin-bottom:4px;">Start Date</label>
          <input type="date" name="start_date" id="edit_start" class="form-control">
        </div>
        <div>
          <label style="font-size:12px;color:var(--gray-600);display:block;margin-bottom:4px;">End Date</label>
          <input type="date" name="end_date" id="edit_end" class="form-control">
        </div>
      </div>
      <div style="margin-bottom:12px;">
        <label style="font-size:12px;color:var(--gray-600);display:block;margin-bottom:4px;">Notes</label>
        <textarea name="notes" id="edit_notes" class="form-control" rows="2"></textarea>
      </div>
      <div style="display:flex;gap:8px;">
        <button type="submit" class="btn btn-primary btn-sm">Save Changes</button>
        <button type="button" class="btn btn-outline btn-sm" onclick="closeEditModal()">Cancel</button>
      </div>
    </form>
  </div>
</div>

<script>
function editAgreement(id, type, provider, start, end, notes) {
  document.getElementById('editAgreementFormEl').action = '/assets/{{ asset.id }}/agreements/' + id + '/edit';
  document.getElementById('edit_type').value = type;
  document.getElementById('edit_provider').value = provider;
  document.getElementById('edit_start').value = start;
  document.getElementById('edit_end').value = end;
  document.getElementById('edit_notes').value = notes;
  const modal = document.getElementById('editAgreementModal');
  modal.style.display = 'flex';
}
function closeEditModal() {
  document.getElementById('editAgreementModal').style.display = 'none';
}
document.getElementById('editAgreementModal').addEventListener('click', function(e) {
  if (e.target === this) closeEditModal();
});
</script>
```

- [ ] **Step 3: Verify the detail page renders without errors**

Run the app and navigate to any asset detail page:
```bash
cd /mnt/c/Users/m.alkhalifa/AssetInventory && python -c "
from app import create_app
app = create_app()
with app.test_client() as c:
    # Login as admin first
    with app.app_context():
        from database import get_db
        with get_db() as conn:
            admin = conn.execute('SELECT id FROM employees WHERE role=\"admin\" LIMIT 1').fetchone()
    with c.session_transaction() as sess:
        sess['user_id'] = admin['id']
    resp = c.get('/assets/1')
    print('Status:', resp.status_code)
    print('Has agreements section:', b'Agreements' in resp.data)
"
```
Expected: Status 200, `Has agreements section: True`.

---

### Task 4: Add admin agreements overview page

**Files:**
- Modify: `/mnt/c/Users/m.alkhalifa/AssetInventory/routes/admin.py`
- Create: `/mnt/c/Users/m.alkhalifa/AssetInventory/templates/admin/agreements.html`

- [ ] **Step 1: Add the overview route to `routes/admin.py`**

At the end of `admin.py` (after the `export_csv` function), add:

```python
@admin_bp.route('/agreements')
def agreements():
    if not g.user or g.user['role'] != 'admin':
        flash('Admin access required.', 'error')
        return redirect(url_for('dashboard.index'))

    type_filter = request.args.get('type', '')
    status_filter = request.args.get('status', '')
    page = request.args.get('page', 1, type=int)
    per_page = 50
    offset = (page - 1) * per_page

    base_query = '''
        FROM asset_agreements ag
        JOIN assets a ON ag.asset_id = a.id
        LEFT JOIN categories c ON a.category_id = c.id
    '''
    conditions = []
    params = []

    if type_filter:
        conditions.append('ag.agreement_type = ?')
        params.append(type_filter)

    if status_filter == 'expired':
        conditions.append("ag.end_date < date('now')")
    elif status_filter == 'expiring':
        conditions.append("ag.end_date >= date('now') AND ag.end_date <= date('now', '+30 days')")
    elif status_filter == 'active':
        conditions.append("(ag.end_date IS NULL OR ag.end_date > date('now', '+30 days'))")

    where = (' WHERE ' + ' AND '.join(conditions)) if conditions else ''

    with get_db() as conn:
        total = conn.execute('SELECT COUNT(*) as c ' + base_query + where, params).fetchone()['c']

        agreements = conn.execute('''
            SELECT ag.*, a.id as asset_id, a.product_id, a.item_name,
                   c.name as category_name,
                   CASE
                       WHEN ag.end_date IS NULL THEN 'active'
                       WHEN ag.end_date < date('now') THEN 'expired'
                       WHEN ag.end_date <= date('now', '+30 days') THEN 'expiring'
                       ELSE 'active'
                   END as status
        ''' + base_query + where + '''
            ORDER BY
                CASE WHEN ag.end_date IS NULL THEN 1 ELSE 0 END,
                ag.end_date ASC
            LIMIT ? OFFSET ?
        ''', params + [per_page, offset]).fetchall()

    total_pages = (total + per_page - 1) // per_page
    return render_template('admin/agreements.html',
                           agreements=agreements, page=page,
                           total_pages=total_pages, total=total,
                           type_filter=type_filter, status_filter=status_filter)
```

- [ ] **Step 2: Create the agreements overview template**

Create `/mnt/c/Users/m.alkhalifa/AssetInventory/templates/admin/agreements.html`:

```html
{% extends "base.html" %}
{% block title %}Agreements Overview — Asset Inventory{% endblock %}
{% block content %}
<div class="page-header">
  <div class="breadcrumb"><a href="{{ url_for('admin.panel') }}">Admin</a> / Agreements</div>
  <h2><i class="lucide-file-check" style="font-size:20px;"></i> Agreements & Licenses ({{ total }})</h2>
</div>
<div class="page-content">
  <!-- Filters -->
  <form method="GET" style="display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap;">
    <select name="type" class="form-control" style="width:auto;" onchange="this.form.submit()">
      <option value="">All Types</option>
      <option value="Warranty" {% if type_filter == 'Warranty' %}selected{% endif %}>Warranty</option>
      <option value="Support Contract" {% if type_filter == 'Support Contract' %}selected{% endif %}>Support Contract</option>
      <option value="Software License" {% if type_filter == 'Software License' %}selected{% endif %}>Software License</option>
      <option value="Subscription" {% if type_filter == 'Subscription' %}selected{% endif %}>Subscription</option>
    </select>
    <select name="status" class="form-control" style="width:auto;" onchange="this.form.submit()">
      <option value="">All Statuses</option>
      <option value="active" {% if status_filter == 'active' %}selected{% endif %}>Active</option>
      <option value="expiring" {% if status_filter == 'expiring' %}selected{% endif %}>Expiring Soon</option>
      <option value="expired" {% if status_filter == 'expired' %}selected{% endif %}>Expired</option>
    </select>
  </form>

  {% if agreements %}
  <div class="activity-card">
    <table style="width:100%;font-size:13px;">
      <thead style="background:var(--gray-50);">
        <tr>
          <th style="padding:8px 12px;color:var(--gray-600);font-size:12px;">Asset</th>
          <th style="padding:8px 12px;color:var(--gray-600);font-size:12px;">Type</th>
          <th style="padding:8px 12px;color:var(--gray-600);font-size:12px;">Provider</th>
          <th style="padding:8px 12px;color:var(--gray-600);font-size:12px;">Period</th>
          <th style="padding:8px 12px;color:var(--gray-600);font-size:12px;">Status</th>
          <th style="padding:8px 12px;color:var(--gray-600);font-size:12px;">Notes</th>
        </tr>
      </thead>
      <tbody>
      {% for ag in agreements %}
        <tr>
          <td style="padding:10px 12px;">
            <a href="{{ url_for('assets.detail', asset_id=ag.asset_id) }}" style="text-decoration:none;">
              <div style="font-weight:600;">{{ ag.item_name or ag.product_id }}</div>
              <div style="font-size:11px;color:var(--gray-500);">{{ ag.product_id }} · {{ ag.category_name }}</div>
            </a>
          </td>
          <td style="padding:10px 12px;font-weight:600;">{{ ag.agreement_type }}</td>
          <td style="padding:10px 12px;">{{ ag.provider or '-' }}</td>
          <td style="padding:10px 12px;font-size:12px;">{{ ag.start_date or '—' }} to {{ ag.end_date or 'No expiry' }}</td>
          <td style="padding:10px 12px;">
            {% if ag.status == 'expired' %}
              <span class="badge badge-damaged">Expired</span>
            {% elif ag.status == 'expiring' %}
              <span class="badge badge-pending">Expiring Soon</span>
            {% else %}
              <span class="badge badge-good">Active</span>
            {% endif %}
          </td>
          <td style="padding:10px 12px;font-size:12px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{{ ag.notes or '-' }}</td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>

  <!-- Pagination -->
  {% if total_pages > 1 %}
  <div style="display:flex;justify-content:center;gap:8px;margin-top:20px;">
    {% if page > 1 %}
    <a href="?page={{ page - 1 }}&type={{ type_filter }}&status={{ status_filter }}" class="btn btn-outline btn-sm">&laquo; Prev</a>
    {% endif %}
    <span style="padding:6px 12px;font-size:13px;color:var(--gray-500);">Page {{ page }} of {{ total_pages }}</span>
    {% if page < total_pages %}
    <a href="?page={{ page + 1 }}&type={{ type_filter }}&status={{ status_filter }}" class="btn btn-outline btn-sm">Next &raquo;</a>
    {% endif %}
  </div>
  {% endif %}

  {% else %}
  <div style="padding:48px;text-align:center;color:var(--gray-400);">
    <i class="lucide-file-x" style="font-size:32px;display:block;margin-bottom:8px;"></i>
    No agreements found{% if type_filter or status_filter %} matching the selected filters{% endif %}.
  </div>
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 3: Add link to agreements overview in admin panel**

In `/mnt/c/Users/m.alkhalifa/AssetInventory/templates/admin/panel.html`, find the quick-actions div (line 19-23). Add a new link after the existing ones:

```html
    <a href="{{ url_for('admin.agreements') }}" class="btn btn-outline"><i class="lucide-file-check" style="font-size:14px;"></i> Agreements Overview</a>
```

- [ ] **Step 4: Add sidebar link for agreements (admin only)**

In `/mnt/c/Users/m.alkhalifa/AssetInventory/templates/base.html`, find the admin section (lines 50-56). After the Admin Panel link (line 55), add:

```html
      <a href="{{ url_for('admin.agreements') }}" class="{% if '/admin/agreements' in request.path %}active{% endif %}">
        <i class="lucide-file-check"></i> Agreements
      </a>
```

- [ ] **Step 5: Verify the overview page renders**

Run:
```bash
cd /mnt/c/Users/m.alkhalifa/AssetInventory && python -c "
from app import create_app
app = create_app()
with app.test_client() as c:
    with app.app_context():
        from database import get_db
        with get_db() as conn:
            admin = conn.execute('SELECT id FROM employees WHERE role=\"admin\" LIMIT 1').fetchone()
    with c.session_transaction() as sess:
        sess['user_id'] = admin['id']
    resp = c.get('/admin/agreements')
    print('Status:', resp.status_code)
    print('Has title:', b'Agreements' in resp.data)
"
```
Expected: Status 200, `Has title: True`.

---

### Task 5: Add expiring agreements widget to the dashboard

**Files:**
- Modify: `/mnt/c/Users/m.alkhalifa/AssetInventory/routes/dashboard.py:13-67`
- Modify: `/mnt/c/Users/m.alkhalifa/AssetInventory/templates/dashboard.html`

- [ ] **Step 1: Add agreement counts to the dashboard route**

In `routes/dashboard.py`, inside the `with get_db() as conn:` block (after the overdue_list query, around line 60), add:

```python
        # Agreement expiry counts (admin only)
        expiring_agreements = 0
        expired_agreements = 0
        if g.user['role'] == 'admin':
            expiring_agreements = conn.execute("""
                SELECT COUNT(*) as c FROM asset_agreements
                WHERE end_date >= date('now') AND end_date <= date('now', '+30 days')
            """).fetchone()['c']
            expired_agreements = conn.execute("""
                SELECT COUNT(*) as c FROM asset_agreements
                WHERE end_date < date('now')
            """).fetchone()['c']
```

Then add these to the stats dict (after line 67):

```python
        'expiring_agreements': expiring_agreements,
        'expired_agreements': expired_agreements,
```

- [ ] **Step 2: Add the widget to the dashboard template**

In `templates/dashboard.html`, after the quick-actions div (after line 84), add:

```html
  <!-- Agreement Alerts (admin only) -->
  {% if current_user.role == 'admin' and (stats.expiring_agreements > 0 or stats.expired_agreements > 0) %}
  <div class="flash flash-warning" style="margin-bottom:20px;display:flex;align-items:center;justify-content:space-between;">
    <div>
      <i class="lucide-file-check"></i>
      <strong>Agreement Alerts:</strong>
      {% if stats.expired_agreements > 0 %}
        {{ stats.expired_agreements }} expired
      {% endif %}
      {% if stats.expired_agreements > 0 and stats.expiring_agreements > 0 %} · {% endif %}
      {% if stats.expiring_agreements > 0 %}
        {{ stats.expiring_agreements }} expiring within 30 days
      {% endif %}
    </div>
    <a href="{{ url_for('admin.agreements', status='expiring') }}" class="btn btn-sm btn-outline">View All</a>
  </div>
  {% endif %}
```

- [ ] **Step 3: Verify the dashboard renders with agreement data**

Run:
```bash
cd /mnt/c/Users/m.alkhalifa/AssetInventory && python -c "
from app import create_app
app = create_app()
with app.test_client() as c:
    with app.app_context():
        from database import get_db
        with get_db() as conn:
            admin = conn.execute('SELECT id FROM employees WHERE role=\"admin\" LIMIT 1').fetchone()
    with c.session_transaction() as sess:
        sess['user_id'] = admin['id']
    resp = c.get('/')
    print('Status:', resp.status_code)
"
```
Expected: Status 200, no errors.

---

### Task 6: End-to-end manual verification

- [ ] **Step 1: Start the app**

```bash
cd /mnt/c/Users/m.alkhalifa/AssetInventory && python app.py
```

- [ ] **Step 2: Test the full flow**

1. Log in as an admin user
2. Navigate to any asset detail page
3. Verify the "Agreements & Licenses" card appears (empty state)
4. Click "Add" and create a test agreement (e.g., Warranty, Dell, start today, end in 10 days)
5. Verify it shows with "Expiring Soon" badge
6. Click Edit, change end date to next year, save — verify "Active" badge
7. Navigate to Admin Panel > Agreements Overview — verify the entry appears
8. Test the type and status filters
9. Return to dashboard — verify the expiring agreements widget appears/disappears based on data
10. Delete the test agreement and verify audit log entry

- [ ] **Step 3: Verify audit logging**

Navigate to Admin Panel > Audit Log. Verify entries for agreement create, update, and delete actions.
