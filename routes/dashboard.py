"""Dashboard — role-aware landing page."""
from flask import Blueprint, render_template, g
from database import get_db

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

        # Registered assets
        stats['total_assets'] = conn.execute(
            "SELECT COUNT(*) FROM assets").fetchone()[0]
        stats['available_assets'] = conn.execute(
            "SELECT COUNT(*) FROM assets WHERE status='available'"
        ).fetchone()[0]

        # My tickets
        stats['my_tickets'] = conn.execute(
            "SELECT COUNT(*) FROM tickets WHERE submitted_by=? "
            "AND status IN ('open','in_progress','waiting')", (user['id'],)
        ).fetchone()[0]

        # Admin stats
        admin_stats = {}
        if is_admin:
            admin_stats['open_tickets'] = conn.execute(
                "SELECT COUNT(*) FROM tickets WHERE status IN ('open','in_progress','waiting')"
            ).fetchone()[0]
            admin_stats['checked_out'] = conn.execute(
                "SELECT COUNT(*) FROM assets WHERE status='checked_out'"
            ).fetchone()[0]
            admin_stats['maintenance'] = conn.execute(
                "SELECT COUNT(*) FROM assets WHERE status='maintenance'"
            ).fetchone()[0]

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
                           categories=categories, is_admin=is_admin)
