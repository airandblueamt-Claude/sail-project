"""Bookings — employee booking flow + admin approval queue."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort
from database import get_db, log_audit
from email_service import notify_booking_submitted, notify_booking_status
from config import BOOKINGS_ENABLED

bookings_bp = Blueprint('bookings', __name__)


@bookings_bp.before_request
def gate_bookings():
    if not BOOKINGS_ENABLED:
        abort(404)


@bookings_bp.route('/mine')
def my_bookings():
    """Employee view: my bookings grouped by status."""
    with get_db() as conn:
        bookings = conn.execute("""
            SELECT b.*, a.asset_tag, em.name as eq_name, em.brand,
                   l.code as location_code,
                   ea.name as approver_name
            FROM bookings b
            JOIN assets a ON b.asset_id = a.id
            JOIN equipment_models em ON a.equipment_model_id = em.id
            LEFT JOIN locations l ON a.location_id = l.id
            LEFT JOIN employees ea ON b.approved_by = ea.id
            WHERE b.requested_by = ?
            ORDER BY
                CASE b.status
                    WHEN 'checked_out' THEN 1
                    WHEN 'approved' THEN 2
                    WHEN 'pending' THEN 3
                    ELSE 4
                END,
                b.booked_from DESC
        """, (g.user['id'],)).fetchall()

    return render_template('bookings/my_bookings.html', bookings=bookings)


@bookings_bp.route('/admin')
def admin_queue():
    """Admin view: all bookings with pending first."""
    if g.user['role'] not in ('admin', 'manager'):
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.index'))

    status_filter = request.args.get('status', '')
    with get_db() as conn:
        where = ""
        params = []
        if status_filter:
            where = "WHERE b.status = ?"
            params = [status_filter]

        bookings = conn.execute(f"""
            SELECT b.*, a.asset_tag, em.name as eq_name, em.brand,
                   e.name as requester_name, e.badge_number,
                   ea.name as approver_name,
                   l.code as location_code
            FROM bookings b
            JOIN assets a ON b.asset_id = a.id
            JOIN equipment_models em ON a.equipment_model_id = em.id
            JOIN employees e ON b.requested_by = e.id
            LEFT JOIN employees ea ON b.approved_by = ea.id
            LEFT JOIN locations l ON a.location_id = l.id
            {where}
            ORDER BY
                CASE b.status
                    WHEN 'pending' THEN 1
                    WHEN 'approved' THEN 2
                    WHEN 'checked_out' THEN 3
                    ELSE 4
                END,
                b.created_at DESC
        """, params).fetchall()

    return render_template('bookings/admin_queue.html',
                           bookings=bookings, status_filter=status_filter)


@bookings_bp.route('/book/<int:asset_id>', methods=['GET', 'POST'])
def book_asset(asset_id):
    """Employee books a specific asset — arrives here from inventory browse."""
    with get_db() as conn:
        asset = conn.execute("""
            SELECT a.*, em.name as eq_name, em.brand, em.is_bookable,
                   em.specifications, l.code as location_code, l.label as location_label
            FROM assets a
            JOIN equipment_models em ON a.equipment_model_id = em.id
            LEFT JOIN locations l ON a.location_id = l.id
            WHERE a.id = ?
        """, (asset_id,)).fetchone()

        if not asset:
            flash('Asset not found.', 'error')
            return redirect(url_for('inventory.models'))

        if not asset['is_bookable']:
            flash('This asset is not available for booking.', 'error')
            return redirect(url_for('inventory.models'))

        if asset['status'] not in ('available',):
            flash(f'This asset is currently {asset["status"]}.', 'error')
            return redirect(url_for('inventory.model_detail',
                                    model_id=asset['equipment_model_id']))

        if request.method == 'POST':
            booked_from = request.form['booked_from']
            booked_to = request.form['booked_to']
            purpose = request.form.get('purpose', '').strip()

            if not booked_from or not booked_to:
                flash('Please select both dates.', 'error')
                return redirect(url_for('bookings.book_asset', asset_id=asset_id))

            if booked_to < booked_from:
                flash('Return date must be after start date.', 'error')
                return redirect(url_for('bookings.book_asset', asset_id=asset_id))

            # Check conflicts
            conflict = conn.execute("""
                SELECT id FROM bookings
                WHERE asset_id = ? AND status IN ('approved','checked_out')
                  AND booked_from < ? AND booked_to > ?
            """, (asset_id, booked_to, booked_from)).fetchone()
            if conflict:
                flash('This asset is already booked for those dates.', 'error')
                return redirect(url_for('bookings.book_asset', asset_id=asset_id))

            cur = conn.execute("""
                INSERT INTO bookings (asset_id, requested_by, booked_from,
                                      booked_to, purpose)
                VALUES (?, ?, ?, ?, ?)
            """, (asset_id, g.user['id'], booked_from, booked_to, purpose))
            log_audit(conn, 'bookings', cur.lastrowid, 'create',
                      changed_by=g.user['id'])
            notify_booking_submitted(
                {'booked_from': booked_from, 'booked_to': booked_to, 'purpose': purpose},
                dict(asset), g.user)
            flash('Booking request submitted! An admin will review it.', 'success')
            return redirect(url_for('bookings.my_bookings'))

    return render_template('bookings/book.html', asset=asset)


@bookings_bp.route('/<int:booking_id>/action', methods=['POST'])
def booking_action(booking_id):
    """Admin actions: approve, reject, checkout, return. Employee: cancel."""
    action = request.form.get('action')
    valid = {
        'approve':  ('pending', 'approved'),
        'reject':   ('pending', 'rejected'),
        'checkout': ('approved', 'checked_out'),
        'return':   ('checked_out', 'returned'),
        'cancel':   ('pending', 'cancelled'),
    }
    if action not in valid:
        flash('Invalid action.', 'error')
        return redirect(url_for('bookings.my_bookings'))

    expected, new_status = valid[action]

    with get_db() as conn:
        booking = conn.execute("SELECT * FROM bookings WHERE id=?",
                               (booking_id,)).fetchone()
        if not booking or booking['status'] != expected:
            flash(f'Cannot {action}: booking is '
                  f'{booking["status"] if booking else "missing"}.', 'error')
            return redirect(url_for('bookings.my_bookings'))

        # Permission check
        is_admin = g.user['role'] in ('admin', 'manager')
        is_owner = booking['requested_by'] == g.user['id']
        if action == 'cancel' and not is_owner:
            flash('You can only cancel your own bookings.', 'error')
            return redirect(url_for('bookings.my_bookings'))
        if action in ('approve', 'reject', 'checkout', 'return') and not is_admin:
            flash('Only admins can perform this action.', 'error')
            return redirect(url_for('bookings.my_bookings'))

        # Perform the action
        if action == 'approve':
            conn.execute(
                "UPDATE bookings SET status=?, approved_by=?, updated_at=datetime('now') WHERE id=?",
                (new_status, g.user['id'], booking_id))
            conn.execute(
                "UPDATE assets SET status='reserved', updated_at=datetime('now') WHERE id=?",
                (booking['asset_id'],))
        elif action == 'checkout':
            conn.execute(
                "UPDATE bookings SET status=?, checkout_date=datetime('now'), updated_at=datetime('now') WHERE id=?",
                (new_status, booking_id))
            conn.execute(
                "UPDATE assets SET status='checked_out', updated_at=datetime('now') WHERE id=?",
                (booking['asset_id'],))
        elif action == 'return':
            ret_cond = request.form.get('return_condition', 'good')
            conn.execute(
                "UPDATE bookings SET status=?, actual_return=datetime('now'), return_condition=?, updated_at=datetime('now') WHERE id=?",
                (new_status, ret_cond, booking_id))
            conn.execute(
                "UPDATE assets SET status='available', condition=?, updated_at=datetime('now') WHERE id=?",
                (ret_cond, booking['asset_id'],))
        else:  # reject or cancel
            conn.execute(
                "UPDATE bookings SET status=?, updated_at=datetime('now') WHERE id=?",
                (new_status, booking_id))
            conn.execute(
                "UPDATE assets SET status='available', updated_at=datetime('now') WHERE id=?",
                (booking['asset_id'],))

        log_audit(conn, 'bookings', booking_id, 'status_change',
                  'status', expected, new_status, g.user['id'])

        # Email notification to requester
        requester = conn.execute(
            "SELECT * FROM employees WHERE id=?", (booking['requested_by'],)
        ).fetchone()
        asset_info = conn.execute(
            "SELECT a.asset_tag, em.name as eq_name, em.brand "
            "FROM assets a JOIN equipment_models em ON a.equipment_model_id=em.id "
            "WHERE a.id=?", (booking['asset_id'],)
        ).fetchone()
        if requester and asset_info:
            notify_booking_status(
                dict(booking), dict(asset_info), dict(requester),
                new_status, g.user['name'])

        flash(f'Booking {action}d successfully.', 'success')

    if is_admin and action != 'cancel':
        return redirect(url_for('bookings.admin_queue'))
    return redirect(url_for('bookings.my_bookings'))
