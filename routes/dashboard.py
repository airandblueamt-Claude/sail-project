"""Dashboard — role-aware landing page."""
from flask import Blueprint, render_template, g
from database import get_db
from config import BOOKINGS_ENABLED

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
def index():
    user = g.user
    is_admin = user['role'] in ('admin', 'manager')

    with get_db() as conn:
        stats = {}

        # Equipment models
        stats['total_models'] = conn.execute(
            "SELECT COUNT(*) FROM equipment_models").fetchone()[0]
        stats['total_expected_units'] = conn.execute(
            "SELECT COALESCE(SUM(expected_qty),0) FROM equipment_models"
        ).fetchone()[0]
        stats['bookable_models'] = conn.execute(
            "SELECT COUNT(*) FROM equipment_models WHERE is_bookable=1"
        ).fetchone()[0]

        # Registered assets
        stats['total_assets'] = conn.execute(
            "SELECT COUNT(*) FROM assets").fetchone()[0]
        stats['available_assets'] = conn.execute(
            "SELECT COUNT(*) FROM assets WHERE status='available'"
        ).fetchone()[0]

        # My bookings
        if BOOKINGS_ENABLED:
            stats['my_active'] = conn.execute(
                "SELECT COUNT(*) FROM bookings WHERE requested_by=? "
                "AND status IN ('approved','checked_out')", (user['id'],)
            ).fetchone()[0]
            stats['my_pending'] = conn.execute(
                "SELECT COUNT(*) FROM bookings WHERE requested_by=? AND status='pending'",
                (user['id'],)
            ).fetchone()[0]
        else:
            stats['my_active'] = 0
            stats['my_pending'] = 0

        # My tickets
        stats['my_tickets'] = conn.execute(
            "SELECT COUNT(*) FROM tickets WHERE submitted_by=? "
            "AND status IN ('open','in_progress','waiting')", (user['id'],)
        ).fetchone()[0]

        # My current checkouts
        if BOOKINGS_ENABLED:
            my_checkouts = conn.execute("""
                SELECT b.*, a.asset_tag, em.name as eq_name, em.brand,
                       l.code as location_code
                FROM bookings b
                JOIN assets a ON b.asset_id = a.id
                JOIN equipment_models em ON a.equipment_model_id = em.id
                LEFT JOIN locations l ON a.location_id = l.id
                WHERE b.requested_by = ? AND b.status IN ('approved','checked_out')
                ORDER BY b.booked_from
            """, (user['id'],)).fetchall()
        else:
            my_checkouts = []

        # Admin stats
        admin_stats = {}
        pending_approvals = []
        if is_admin:
            if BOOKINGS_ENABLED:
                admin_stats['pending_bookings'] = conn.execute(
                    "SELECT COUNT(*) FROM bookings WHERE status='pending'"
                ).fetchone()[0]
            else:
                admin_stats['pending_bookings'] = 0
            admin_stats['open_tickets'] = conn.execute(
                "SELECT COUNT(*) FROM tickets WHERE status IN ('open','in_progress','waiting')"
            ).fetchone()[0]
            admin_stats['checked_out'] = conn.execute(
                "SELECT COUNT(*) FROM assets WHERE status='checked_out'"
            ).fetchone()[0]
            admin_stats['maintenance'] = conn.execute(
                "SELECT COUNT(*) FROM assets WHERE status='maintenance'"
            ).fetchone()[0]

            if BOOKINGS_ENABLED:
                pending_approvals = conn.execute("""
                    SELECT b.*, a.asset_tag, em.name as eq_name, em.brand,
                           e.name as requester_name
                    FROM bookings b
                    JOIN assets a ON b.asset_id = a.id
                    JOIN equipment_models em ON a.equipment_model_id = em.id
                    JOIN employees e ON b.requested_by = e.id
                    WHERE b.status = 'pending'
                    ORDER BY b.created_at
                    LIMIT 10
                """).fetchall()
            else:
                pending_approvals = []

            admin_stats['expiring_agreements'] = conn.execute(
                "SELECT COUNT(*) FROM equipment_agreements "
                "WHERE end_date >= date('now') AND end_date <= date('now', '+30 days')"
            ).fetchone()[0]
            admin_stats['expired_agreements'] = conn.execute(
                "SELECT COUNT(*) FROM equipment_agreements WHERE end_date < date('now')"
            ).fetchone()[0]

        # Category breakdown
        categories = conn.execute("""
            SELECT c.name, COUNT(*) as models,
                   COALESCE(SUM(em.expected_qty),0) as units
            FROM equipment_models em
            JOIN categories c ON em.category_id = c.id
            GROUP BY c.name ORDER BY units DESC
        """).fetchall()

    return render_template('dashboard.html',
                           stats=stats, admin_stats=admin_stats,
                           categories=categories, is_admin=is_admin,
                           my_checkouts=my_checkouts,
                           pending_approvals=pending_approvals)
