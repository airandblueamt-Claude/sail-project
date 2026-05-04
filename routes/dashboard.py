"""Dashboard — single-role landing page for the control team."""
from flask import Blueprint, render_template
from database import get_db
from config import SMTP_PASSWORD

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

        # Unhealthy assets (missing or damaged).
        stats['unhealthy_assets'] = conn.execute("""
            SELECT a.id, a.asset_tag, a.status, a.condition,
                   em.name AS model_name, l.label, l.code
            FROM assets a
            JOIN equipment_models em ON a.equipment_model_id = em.id
            LEFT JOIN locations l ON a.location_id = l.id
            WHERE a.status = 'missing' OR a.condition = 'damaged'
            ORDER BY a.asset_tag
            LIMIT 20
        """).fetchall()

        # Asset counts (totals + assigned vs available).
        counts = conn.execute("""
            SELECT
                SUM(CASE WHEN status='available' THEN 1 ELSE 0 END) AS available,
                SUM(CASE WHEN status='assigned'  THEN 1 ELSE 0 END) AS assigned,
                COUNT(*) AS total
            FROM assets
        """).fetchone()
        stats['asset_counts'] = dict(counts) if counts else {'available': 0, 'assigned': 0, 'total': 0}

        # SMTP configured? (Same check email_service.send_email uses.)
        stats['smtp_configured'] = bool(
            SMTP_PASSWORD and SMTP_PASSWORD != "YOUR_APP_PASSWORD_HERE")

    return render_template('dashboard.html', stats=stats)
