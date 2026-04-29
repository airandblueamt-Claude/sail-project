# Asset Edit Page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `/inventory/asset/<id>/edit` so admin/manager/technician can update an existing asset's status, condition, location, serial number, quantity, and notes from the webpage, with each field-level change written to `audit_log`.

**Architecture:** One new route on the existing `inventory_bp` blueprint. One new Jinja template that mirrors `register_asset.html`'s visual style. One "Edit asset" button added to the asset detail page, gated on role. No schema change, no new dependencies. The template is rendered from a single `values` dict that the route populates either from the current asset row (GET) or from the submitted form (POST validation failure) so the user never loses typed input.

**Tech Stack:** Flask, SQLite (WAL + FK), Jinja2, existing `database.get_db()` and `log_audit()` helpers, existing `static/style.css`.

**Testing note:** This project has no pytest suite. Each task ends with manual verification (browser + sqlite query against `audit_log`) and a git commit. The final task is a smoke-test of the full user flow including permission denial and a validation failure.

**Spec:** `docs/superpowers/specs/2026-04-29-asset-edit-design.md`

---

### Task 1: Add the GET handler and form template

**Files:**
- Modify: `routes/inventory.py` (add a new view function after `asset_detail` around line 327)
- Create: `templates/inventory/edit_asset.html`

- [ ] **Step 1: Add `edit_asset` view function (GET path only) to `routes/inventory.py`**

Insert this block in `routes/inventory.py` immediately after the `asset_detail` view (i.e. after the `return render_template('inventory/asset_detail.html', ...)` line around line 326) and before the existing `register_asset` view.

```python
@inventory_bp.route('/asset/<int:asset_id>/edit', methods=['GET', 'POST'])
def edit_asset(asset_id):
    """Admin/manager/technician edit form for a single asset row."""
    if g.user['role'] not in ('admin', 'manager', 'technician'):
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.index'))

    STATUS_VALUES = ('available', 'in_use', 'reserved', 'checked_out',
                     'maintenance', 'decommissioned', 'missing')
    CONDITION_VALUES = ('good', 'fair', 'damaged', 'decommissioned')

    with get_db() as conn:
        asset = conn.execute("""
            SELECT a.*, em.name AS model_name, em.brand, em.model_number,
                   c.name AS category_name
            FROM assets a
            JOIN equipment_models em ON a.equipment_model_id = em.id
            LEFT JOIN categories c ON em.category_id = c.id
            WHERE a.id = ?
        """, (asset_id,)).fetchone()
        if not asset:
            flash('Asset not found.', 'error')
            return redirect(url_for('inventory.manage_assets'))

        locations = conn.execute(
            "SELECT id, code, label FROM locations ORDER BY code"
        ).fetchall()

        # POST handling lands here in Task 2.

        # GET: prefill from the current asset row.
        values = {
            'status': asset['status'],
            'condition': asset['condition'],
            'location_id': asset['location_id'],
            'serial_number': asset['serial_number'] or '',
            'qty_represented': asset['qty_represented'],
            'notes': asset['notes'] or '',
        }

    return render_template('inventory/edit_asset.html',
                           asset=asset, locations=locations,
                           values=values,
                           statuses=STATUS_VALUES,
                           conditions=CONDITION_VALUES)
```

- [ ] **Step 2: Create `templates/inventory/edit_asset.html`**

Create the file with this exact content:

```jinja
{% extends "base.html" %}
{% block title %}SAIL - Edit {{ asset.asset_tag }}{% endblock %}
{% block content %}
<div class="page-header">
    <div>
        <a href="{{ url_for('inventory.manage_assets') }}" class="breadcrumb">Assets</a>
        <span class="breadcrumb-sep">/</span>
        <a href="{{ url_for('inventory.asset_detail', asset_id=asset.id) }}" class="breadcrumb">{{ asset.asset_tag }}</a>
        <h2>Edit Asset</h2>
    </div>
</div>

<div class="detail-grid">
    <div class="detail-card">
        <h4>Asset (read-only)</h4>
        <dl class="detail-list">
            <dt>Asset Tag</dt><dd>{{ asset.asset_tag }}</dd>
            <dt>Model</dt><dd>{{ asset.model_name }}{% if asset.model_number %} ({{ asset.model_number }}){% endif %}</dd>
            <dt>Brand</dt><dd>{{ asset.brand or '—' }}</dd>
            <dt>Category</dt><dd>{{ asset.category_name or '—' }}</dd>
            <dt>Created</dt><dd>{{ asset.created_at[:10] if asset.created_at else '—' }}</dd>
            <dt>Last updated</dt><dd>{{ asset.updated_at[:10] if asset.updated_at else '—' }}</dd>
        </dl>
        <p class="muted" style="font-size:0.9em;margin-top:12px">
            Asset tag and equipment model are immutable. To reclassify or rename, contact an administrator.
        </p>
    </div>

    <form method="post" class="form-card">
        <h4>Editable fields</h4>

        <div class="form-row">
            <label>Status *</label>
            <select name="status" required class="input">
                {% for s in statuses %}
                <option value="{{ s }}" {% if values.status == s %}selected{% endif %}>{{ s }}</option>
                {% endfor %}
            </select>
        </div>

        <div class="form-row">
            <label>Condition *</label>
            <select name="condition" required class="input">
                {% for c in conditions %}
                <option value="{{ c }}" {% if values.condition == c %}selected{% endif %}>{{ c }}</option>
                {% endfor %}
            </select>
        </div>

        <div class="form-row">
            <label>Location</label>
            <select name="location_id" class="input">
                <option value="">-- Not Set --</option>
                {% for l in locations %}
                <option value="{{ l.id }}" {% if values.location_id == l.id %}selected{% endif %}>
                    {{ l.code }}{% if l.label %} ({{ l.label }}){% endif %}
                </option>
                {% endfor %}
            </select>
        </div>

        <div class="form-row">
            <label>Serial Number</label>
            <input type="text" name="serial_number" value="{{ values.serial_number }}" class="input"
                   placeholder="Manufacturer serial number">
        </div>

        <div class="form-row">
            <label>Quantity Represented *</label>
            <input type="number" name="qty_represented" min="1" value="{{ values.qty_represented }}" required class="input">
            <p class="muted" style="margin-top:4px;font-size:0.9em">
                For bulk lots that aren't individually tagged. Use 1 for a single physical unit.
            </p>
        </div>

        <div class="form-row">
            <label>Notes</label>
            <textarea name="notes" rows="3" class="input" placeholder="Any additional notes...">{{ values.notes }}</textarea>
        </div>

        <div class="form-actions">
            <button type="submit" class="btn btn-primary">Save changes</button>
            <a href="{{ url_for('inventory.asset_detail', asset_id=asset.id) }}" class="btn btn-ghost">Cancel</a>
        </div>
    </form>
</div>
{% endblock %}
```

- [ ] **Step 3: Run the app and verify the form renders prefilled**

Run:
```bash
python app.py
```

In another terminal, find an asset id:
```bash
sqlite3 sail.db "SELECT id, asset_tag, status, condition FROM assets LIMIT 3"
```

In the browser, log in as `airandblueamt@gmail.com` / `Aramco@123` (or any other admin in the seeded list), then visit:
```
http://localhost:5555/inventory/asset/<id>/edit
```

Expected:
- Page loads with title "Edit Asset" and breadcrumb `Assets / SAIL-XXXX / Edit Asset`.
- Read-only summary on the left shows the tag, model, brand, category, created/updated dates.
- Form on the right has the asset's current status, condition, location, serial, qty, and notes pre-selected/prefilled.
- Submitting the form right now should reload the page (no error, no change yet — POST handler is empty until Task 2).

Stop the dev server (Ctrl-C).

- [ ] **Step 4: Commit**

```bash
git add routes/inventory.py templates/inventory/edit_asset.html
git commit -m "Add asset edit form (GET only, no save yet)

The route renders /inventory/asset/<id>/edit with the current asset values
pre-selected. POST handler is wired but empty — Task 2 adds save + audit."
```

---

### Task 2: Wire up POST — validate, update, log audit, preserve form values on error

**Files:**
- Modify: `routes/inventory.py` (extend the `edit_asset` view added in Task 1)

- [ ] **Step 1: Replace the `# POST handling lands here in Task 2.` placeholder with the full POST branch**

In `routes/inventory.py`, find the `# POST handling lands here in Task 2.` line inside `edit_asset`. Replace that single comment with this block (note the `if request.method == 'POST':` indent matches the rest of the `with` body):

```python
        if request.method == 'POST':
            status = request.form.get('status', '')
            condition = request.form.get('condition', '')
            location_id_raw = request.form.get('location_id', '')
            serial = request.form.get('serial_number', '').strip() or None
            qty_raw = request.form.get('qty_represented', '')
            notes = request.form.get('notes', '').strip() or None

            submitted = {
                'status': status,
                'condition': condition,
                'location_id': int(location_id_raw) if location_id_raw.isdigit() else None,
                'serial_number': serial or '',
                'qty_represented': qty_raw,
                'notes': notes or '',
            }

            def _reject(msg):
                flash(msg, 'error')
                return render_template('inventory/edit_asset.html',
                                       asset=asset, locations=locations,
                                       values=submitted,
                                       statuses=STATUS_VALUES,
                                       conditions=CONDITION_VALUES)

            if status not in STATUS_VALUES:
                return _reject('Invalid status.')
            if condition not in CONDITION_VALUES:
                return _reject('Invalid condition.')

            try:
                qty = int(qty_raw)
                if qty < 1:
                    raise ValueError
            except (TypeError, ValueError):
                return _reject('Quantity must be a whole number greater than zero.')

            if location_id_raw:
                if not location_id_raw.isdigit():
                    return _reject('Invalid location.')
                location_id = int(location_id_raw)
                loc_exists = conn.execute(
                    "SELECT 1 FROM locations WHERE id = ?", (location_id,)
                ).fetchone()
                if not loc_exists:
                    return _reject('Selected location no longer exists.')
            else:
                location_id = None

            new_values = {
                'status': status,
                'condition': condition,
                'location_id': location_id,
                'serial_number': serial,
                'qty_represented': qty,
                'notes': notes,
            }
            changes = {col: (asset[col], new_val)
                       for col, new_val in new_values.items()
                       if asset[col] != new_val}

            if not changes:
                flash('No changes.', 'info')
                return redirect(url_for('inventory.asset_detail', asset_id=asset_id))

            set_clause = ', '.join(f"{col} = ?" for col in changes)
            params = [new_values[col] for col in changes] + [asset_id]
            conn.execute(
                f"UPDATE assets SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                params,
            )
            for col, (old, new) in changes.items():
                log_audit(conn, 'assets', asset_id, 'update',
                          field_name=col, old_value=old, new_value=new,
                          changed_by=g.user['id'])

            flash(f'Asset {asset["asset_tag"]} updated.', 'success')
            return redirect(url_for('inventory.asset_detail', asset_id=asset_id))

```

The `set_clause` f-string is safe: keys come from a fixed local dict (`new_values`), never from request input.

- [ ] **Step 2: Verify a happy-path save**

Run:
```bash
python app.py
```

Pick an asset id you used in Task 1. Note its current `notes` and `condition`:
```bash
sqlite3 sail.db "SELECT id, asset_tag, condition, notes FROM assets WHERE id = <id>"
```

In the browser, visit `http://localhost:5555/inventory/asset/<id>/edit`. Change Condition (e.g. `good` → `fair`) and add a Note like `edit-test 1`. Submit.

Expected:
- Redirected to the asset detail page.
- Green flash: "Asset SAIL-XXXX updated."
- Asset Summary shows the new condition and note.

Then verify the audit rows:
```bash
sqlite3 sail.db "SELECT field_name, old_value, new_value, changed_by, changed_at FROM audit_log WHERE table_name='assets' AND record_id=<id> AND action='update' ORDER BY id DESC LIMIT 5"
```

Expected: two rows (one for `condition`, one for `notes`), each with old/new values and your user id in `changed_by`.

- [ ] **Step 3: Verify the no-changes case**

Visit `/inventory/asset/<id>/edit` again. Submit without changing anything.

Expected:
- Redirected to the asset detail page.
- Blue/grey "No changes." flash.
- `audit_log` row count for that asset is unchanged from the previous step:
```bash
sqlite3 sail.db "SELECT count(*) FROM audit_log WHERE table_name='assets' AND record_id=<id> AND action='update'"
```

- [ ] **Step 4: Verify validation error preserves typed values**

Visit `/inventory/asset/<id>/edit`. In the browser DevTools console, run:
```javascript
document.querySelector('input[name="qty_represented"]').value = '0';
document.querySelector('textarea[name="notes"]').value = 'this should survive the rejection';
document.querySelector('form').submit();
```

Expected:
- Page re-renders (does not redirect).
- Red flash: "Quantity must be a whole number greater than zero."
- The Notes textarea still shows `this should survive the rejection`.
- Quantity field shows `0` (the bad value the user typed) so they can see and fix it.

Stop the dev server.

- [ ] **Step 5: Commit**

```bash
git add routes/inventory.py
git commit -m "Save + audit asset edits, preserve form on validation error

POST validates the status and condition enums server-side, coerces
qty_represented to a positive int, and confirms location_id still exists.
Each changed column writes one audit_log row in the same transaction as
the UPDATE. On a validation rejection the form re-renders with the user's
submitted values so they don't have to retype."
```

---

### Task 3: Add the "Edit asset" entry-point button on the detail page

**Files:**
- Modify: `templates/inventory/asset_detail.html` (the page-header action area, around lines 10-14)

- [ ] **Step 1: Add the Edit button next to "Raise New Issue"**

In `templates/inventory/asset_detail.html`, replace this block:

```jinja
    <div>
        <a href="{{ url_for('tickets.new_ticket', asset_id=asset.id) }}" class="btn btn-primary">
            <i data-lucide="alert-circle"></i> Raise New Issue
        </a>
    </div>
```

with:

```jinja
    <div>
        {% if g.user.role in ('admin', 'manager', 'technician') %}
        <a href="{{ url_for('inventory.edit_asset', asset_id=asset.id) }}" class="btn btn-ghost">
            <i data-lucide="pencil"></i> Edit asset
        </a>
        {% endif %}
        <a href="{{ url_for('tickets.new_ticket', asset_id=asset.id) }}" class="btn btn-primary">
            <i data-lucide="alert-circle"></i> Raise New Issue
        </a>
    </div>
```

- [ ] **Step 2: Verify the button appears for admin and is hidden for employee**

Run:
```bash
python app.py
```

Logged in as an admin, visit `/inventory/asset/<id>`. Expect the "Edit asset" ghost button to the left of the red "Raise New Issue" button. Click it — it should land on the edit form.

Then, log out, log back in as an employee-role account (create one from `/employees` with role `employee` if you don't have one — set its password by visiting `/account/password` after a fresh login). Visit the same asset page. Expected: no "Edit asset" button anywhere on the page; "Raise New Issue" still visible.

If you don't want to spin up an extra account, you can spot-check the conditional in a sqlite shell:
```bash
sqlite3 sail.db "UPDATE employees SET role='employee' WHERE email='<test-email>'"
# refresh, verify button is gone
sqlite3 sail.db "UPDATE employees SET role='admin' WHERE email='<test-email>'"
# refresh, verify button is back
```

Stop the dev server.

- [ ] **Step 3: Commit**

```bash
git add templates/inventory/asset_detail.html
git commit -m "Link asset detail page to the new edit form

Admin/manager/technician see an 'Edit asset' ghost button next to the
existing 'Raise New Issue' primary button. Employees see only the
ticket button."
```

---

### Task 4: End-to-end smoke test + permission denial

This task only verifies — no new files or commits unless something breaks.

- [ ] **Step 1: Full happy-path flow as admin**

Run:
```bash
python app.py
```

Log in as admin. From the navigation:
1. Click `Inventory` → `Manage Assets` (or visit `/inventory/assets`).
2. Click any asset row to land on `/inventory/asset/<id>`.
3. Click the new `Edit asset` ghost button.
4. Change three fields at once (e.g. status `available` → `in_use`, location to a different one, qty `1` → `2`).
5. Click `Save changes`.

Expected:
- Redirected to `/inventory/asset/<id>`.
- Asset Summary shows all three new values.
- Green flash: "Asset SAIL-XXXX updated."

Verify three audit rows:
```bash
sqlite3 sail.db "SELECT field_name, old_value, new_value FROM audit_log WHERE table_name='assets' AND record_id=<id> ORDER BY id DESC LIMIT 3"
```

Expected: three rows showing `status`, `location_id`, `qty_represented` with the correct old → new values.

- [ ] **Step 2: Permission-denied flow as employee**

In a private/incognito window (so sessions don't collide), log in with an account that has role `employee` (use the sqlite shell trick from Task 3 Step 2 if needed).

Visit `/inventory/asset/<any id>/edit` directly.

Expected:
- Redirected to `/` (dashboard).
- Red flash: "Access denied."

Restore the test account's role to admin afterwards if you switched it.

- [ ] **Step 3: Validation rejection flow**

Back as admin, visit `/inventory/asset/<id>/edit`. Change the dropdown for Status by tampering — open DevTools, run:

```javascript
const opt = document.createElement('option');
opt.value = 'totally_invalid';
opt.text = 'TAMPER';
opt.selected = true;
document.querySelector('select[name="status"]').appendChild(opt);
document.querySelector('form').submit();
```

Expected:
- Page re-renders (no redirect).
- Red flash: "Invalid status."
- Notes / serial / qty values you didn't change are still in the form.
- No new audit row was written:
```bash
sqlite3 sail.db "SELECT count(*) FROM audit_log WHERE table_name='assets' AND record_id=<id>"
```

Stop the dev server.

- [ ] **Step 4: Verify acceptance criteria from the spec**

Walk down `docs/superpowers/specs/2026-04-29-asset-edit-design.md` § "Acceptance criteria" and tick each one against what you just observed:

1. Admin → edit → save → updated values shown on detail page. ✓ (Task 4 Step 1)
2. Employee → `/edit` → "Access denied." ✓ (Task 4 Step 2)
3. Tampered enum → friendly flash + values preserved → no 500. ✓ (Task 4 Step 3)
4. Three-field save → exactly three audit rows. ✓ (Task 4 Step 1)
5. Empty save → "No changes." flash + zero audit rows. ✓ (Task 2 Step 3)
6. Asset tag and equipment model not editable on the form. ✓ (Task 1 — they appear only in the read-only summary card)

If any check fails, do **not** mark this task complete — go back and fix it before considering the feature done.
