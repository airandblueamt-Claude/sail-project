"""Team-managed issue category list (the dropdown on the ticket form)."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from database import get_db, log_audit

issue_categories_bp = Blueprint('issue_categories', __name__)


@issue_categories_bp.before_request
def _require_admin():
    if not g.user or g.user['role'] not in ('admin', 'manager', 'technician'):
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.index'))


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
