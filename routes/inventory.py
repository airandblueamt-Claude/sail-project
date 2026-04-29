"""Inventory — employee booking browse + admin full inventory management."""
import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, current_app
from werkzeug.utils import secure_filename
from database import get_db, log_audit
from config import PAGE_SIZE

ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'webp', 'gif'}


def save_image(file):
    """Save uploaded image, return relative path from static/."""
    if not file or not file.filename:
        return None
    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in ALLOWED_EXT:
        return None
    filename = f"{uuid.uuid4().hex[:12]}.{ext}"
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file.save(path)
    return f"uploads/{filename}"

inventory_bp = Blueprint('inventory', __name__)


# ── Employee view: only bookable equipment ───────────────────────────

@inventory_bp.route('/')
def models():
    """Equipment catalog — card-grid view of all models."""
    q = request.args.get('q', '').strip()
    cat = request.args.get('category', '')
    page = max(1, request.args.get('page', 1, type=int))

    with get_db() as conn:
        where = []
        params = []

        if q:
            where.append("(em.name LIKE ? OR em.brand LIKE ? OR em.specifications LIKE ?)")
            params += [f'%{q}%'] * 3
        if cat:
            where.append("c.name = ?")
            params.append(cat)

        where_sql = " WHERE " + " AND ".join(where) if where else ""

        total = conn.execute(
            f"SELECT COUNT(*) FROM equipment_models em "
            f"JOIN categories c ON em.category_id = c.id {where_sql}", params
        ).fetchone()[0]

        rows = conn.execute(f"""
            SELECT em.*, c.name as category_name,
                   (SELECT COUNT(*) FROM assets a WHERE a.equipment_model_id = em.id) as registered_assets,
                   (SELECT COUNT(*) FROM assets a WHERE a.equipment_model_id = em.id AND a.status = 'available') as available_assets
            FROM equipment_models em
            JOIN categories c ON em.category_id = c.id
            {where_sql}
            ORDER BY c.name, em.name
            LIMIT ? OFFSET ?
        """, params + [PAGE_SIZE, (page - 1) * PAGE_SIZE]).fetchall()

        categories = conn.execute(
            "SELECT DISTINCT c.name FROM equipment_models em "
            "JOIN categories c ON em.category_id = c.id ORDER BY c.name"
        ).fetchall()

    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return render_template('inventory/models.html',
                           models=rows, categories=categories,
                           total=total, page=page, total_pages=total_pages,
                           q=q, cat=cat)


@inventory_bp.route('/<int:model_id>')
def model_detail(model_id):
    """View equipment model and its individual assets."""
    with get_db() as conn:
        model = conn.execute(
            "SELECT em.*, c.name as category_name FROM equipment_models em "
            "JOIN categories c ON em.category_id = c.id WHERE em.id = ?",
            (model_id,)
        ).fetchone()
        if not model:
            flash('Equipment model not found.', 'error')
            return redirect(url_for('inventory.models'))

        assets = conn.execute("""
            SELECT a.*, l.code as location_code, l.label as location_label,
                   e.name as assigned_to_name
            FROM assets a
            LEFT JOIN locations l ON a.location_id = l.id
            LEFT JOIN employees e ON a.assigned_to = e.id
            WHERE a.equipment_model_id = ?
            ORDER BY a.status, a.asset_tag
        """, (model_id,)).fetchall()

    return render_template('inventory/detail.html', model=model, assets=assets)


# ── Admin: full inventory ────────────────────────────────────────────

@inventory_bp.route('/all')
def all_models():
    """Admin view: full inventory including infrastructure."""
    if g.user['role'] not in ('admin', 'manager', 'technician'):
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.index'))

    q = request.args.get('q', '').strip()
    cat = request.args.get('category', '')
    page = max(1, request.args.get('page', 1, type=int))

    with get_db() as conn:
        where = []
        params = []

        if q:
            where.append("(em.name LIKE ? OR em.brand LIKE ? OR em.specifications LIKE ?)")
            params += [f'%{q}%'] * 3
        if cat:
            where.append("c.name = ?")
            params.append(cat)

        where_sql = " WHERE " + " AND ".join(where) if where else ""

        total = conn.execute(
            f"SELECT COUNT(*) FROM equipment_models em "
            f"JOIN categories c ON em.category_id = c.id {where_sql}", params
        ).fetchone()[0]

        rows = conn.execute(f"""
            SELECT em.*, c.name as category_name,
                   (SELECT COUNT(*) FROM assets a WHERE a.equipment_model_id = em.id) as registered_assets,
                   (SELECT COUNT(*) FROM assets a WHERE a.equipment_model_id = em.id AND a.status = 'available') as available_assets
            FROM equipment_models em
            JOIN categories c ON em.category_id = c.id
            {where_sql}
            ORDER BY c.name, em.name
            LIMIT ? OFFSET ?
        """, params + [PAGE_SIZE, (page - 1) * PAGE_SIZE]).fetchall()

        categories = conn.execute(
            "SELECT DISTINCT c.name FROM equipment_models em "
            "JOIN categories c ON em.category_id = c.id ORDER BY c.name"
        ).fetchall()

    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return render_template('inventory/all_models.html',
                           models=rows, categories=categories,
                           total=total, page=page, total_pages=total_pages,
                           q=q, cat=cat)


@inventory_bp.route('/new', methods=['GET', 'POST'])
def new_model():
    if g.user['role'] not in ('admin', 'manager', 'technician'):
        flash('Access denied.', 'error')
        return redirect(url_for('inventory.models'))

    with get_db() as conn:
        if request.method == 'POST':
            name = request.form['name'].strip()
            if not name:
                flash('Name is required.', 'error')
                return redirect(url_for('inventory.new_model'))

            cat_id = request.form.get('category_id', type=int)
            cat_new = request.form.get('category_new', '').strip()
            if cat_new and not cat_id:
                conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)",
                             (cat_new,))
                cat_id = conn.execute(
                    "SELECT id FROM categories WHERE name = ?", (cat_new,)
                ).fetchone()['id']

            image_path = save_image(request.files.get('image'))

            cur = conn.execute("""
                INSERT INTO equipment_models
                    (category_id, name, brand, model_number, specifications,
                     unit, expected_qty, notes, image_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cat_id, name,
                request.form.get('brand', '').strip(),
                request.form.get('model_number', '').strip(),
                request.form.get('specifications', '').strip(),
                request.form.get('unit', 'EA'),
                request.form.get('expected_qty', type=int),
                request.form.get('notes', '').strip(),
                image_path,
            ))
            log_audit(conn, 'equipment_models', cur.lastrowid, 'create',
                      changed_by=g.user['id'])
            flash(f'Equipment model "{name}" added.', 'success')
            return redirect(url_for('inventory.model_detail', model_id=cur.lastrowid))

        categories = conn.execute("SELECT id, name FROM categories ORDER BY name").fetchall()

    return render_template('inventory/new_model.html', categories=categories)


@inventory_bp.route('/<int:model_id>/edit', methods=['GET', 'POST'])
def edit_model(model_id):
    if g.user['role'] not in ('admin', 'manager', 'technician'):
        flash('Access denied.', 'error')
        return redirect(url_for('inventory.models'))

    with get_db() as conn:
        model = conn.execute(
            "SELECT em.*, c.name as category_name FROM equipment_models em "
            "JOIN categories c ON em.category_id = c.id WHERE em.id = ?",
            (model_id,)
        ).fetchone()
        if not model:
            flash('Not found.', 'error')
            return redirect(url_for('inventory.models'))

        categories = conn.execute("SELECT id, name FROM categories ORDER BY name").fetchall()

        if request.method == 'POST':
            image_path = save_image(request.files.get('image'))
            image_update = ", image_path=?" if image_path else ""
            params = [
                request.form['name'], request.form['brand'],
                request.form['model_number'], request.form['specifications'],
                request.form['category_id'],
                request.form.get('expected_qty', type=int),
                request.form['notes'], request.form.get('unit', 'EA'),
            ]
            if image_path:
                params.append(image_path)
            conn.execute(f"""
                UPDATE equipment_models
                SET name=?, brand=?, model_number=?, specifications=?,
                    category_id=?, expected_qty=?, notes=?, unit=?
                    {image_update}
                WHERE id=?""",
                params + [model_id])
            log_audit(conn, 'equipment_models', model_id, 'update',
                      changed_by=g.user['id'])
            flash('Equipment model updated.', 'success')
            return redirect(url_for('inventory.model_detail', model_id=model_id))

    return render_template('inventory/edit.html', model=model, categories=categories)


@inventory_bp.route('/<int:model_id>/delete', methods=['POST'])
def delete_model(model_id):
    if g.user['role'] not in ('admin', 'manager', 'technician'):
        flash('Access denied.', 'error')
        return redirect(url_for('inventory.models'))

    with get_db() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM assets WHERE equipment_model_id=?",
            (model_id,)).fetchone()[0]
        if count > 0:
            flash(f'Cannot delete: {count} assets registered.', 'error')
            return redirect(url_for('inventory.model_detail', model_id=model_id))
        conn.execute("DELETE FROM equipment_models WHERE id=?", (model_id,))
        log_audit(conn, 'equipment_models', model_id, 'delete',
                  changed_by=g.user['id'])
        flash('Equipment model deleted.', 'success')
    return redirect(url_for('inventory.all_models'))


# ── Admin: manage individual assets ──────────────────────────────────

@inventory_bp.route('/assets')
def manage_assets():
    if g.user['role'] not in ('admin', 'manager', 'technician'):
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.index'))

    with get_db() as conn:
        assets = conn.execute("""
            SELECT a.*, em.name as eq_name, em.brand,
                   c.name as category_name,
                   l.code as location_code,
                   e.name as assigned_to_name
            FROM assets a
            JOIN equipment_models em ON a.equipment_model_id = em.id
            JOIN categories c ON em.category_id = c.id
            LEFT JOIN locations l ON a.location_id = l.id
            LEFT JOIN employees e ON a.assigned_to = e.id
            ORDER BY a.asset_tag
        """).fetchall()

    return render_template('inventory/manage_assets.html', assets=assets)


@inventory_bp.route('/asset/<int:asset_id>')
def asset_detail(asset_id):
    with get_db() as conn:
        asset = conn.execute("""
            SELECT a.*, em.name AS model_name, em.brand, em.model_number,
                   c.name AS category_name,
                   COALESCE(l.label, l.code) AS location_name
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


@inventory_bp.route('/assets/register/<int:model_id>', methods=['GET', 'POST'])
def register_asset(model_id):
    if g.user['role'] not in ('admin', 'manager', 'technician'):
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.index'))

    with get_db() as conn:
        model = conn.execute(
            "SELECT em.*, c.name as category_name FROM equipment_models em "
            "JOIN categories c ON em.category_id = c.id WHERE em.id = ?",
            (model_id,)
        ).fetchone()
        if not model:
            flash('Equipment model not found.', 'error')
            return redirect(url_for('inventory.models'))

        if request.method == 'POST':
            asset_tag = request.form['asset_tag'].strip()
            serial = request.form.get('serial_number', '').strip() or None
            location_id = request.form.get('location_id', type=int) or None
            condition = request.form.get('condition', 'good')
            notes = request.form.get('notes', '').strip()

            existing = conn.execute(
                "SELECT id FROM assets WHERE asset_tag=?", (asset_tag,)
            ).fetchone()
            if existing:
                flash(f'Asset tag {asset_tag} already exists.', 'error')
                return redirect(url_for('inventory.register_asset', model_id=model_id))

            cur = conn.execute("""
                INSERT INTO assets (asset_tag, equipment_model_id, serial_number,
                                    location_id, condition, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (asset_tag, model_id, serial, location_id, condition, notes))
            log_audit(conn, 'assets', cur.lastrowid, 'create',
                      changed_by=g.user['id'])
            flash(f'Asset {asset_tag} registered.', 'success')
            return redirect(url_for('inventory.model_detail', model_id=model_id))

        last = conn.execute(
            "SELECT asset_tag FROM assets ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if last:
            try:
                num = int(last['asset_tag'].split('-')[-1]) + 1
            except (ValueError, IndexError):
                num = 1
        else:
            num = 1
        suggested_tag = f"SAIL-{num:04d}"

        locations = conn.execute(
            "SELECT id, code, label FROM locations ORDER BY code"
        ).fetchall()

    return render_template('inventory/register_asset.html',
                           model=model, suggested_tag=suggested_tag,
                           locations=locations)


@inventory_bp.route('/locations/add', methods=['POST'])
def add_location():
    if g.user['role'] not in ('admin', 'manager', 'technician'):
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.index'))

    code = request.form.get('code', '').strip()
    label = request.form.get('label', '').strip()
    if not code:
        flash('Location code is required.', 'error')
    else:
        with get_db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO locations (code, label) VALUES (?, ?)",
                (code, label or None))
        flash(f'Location {code} added.', 'success')

    return redirect(request.referrer or url_for('inventory.manage_assets'))
