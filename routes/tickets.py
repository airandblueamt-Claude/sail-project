"""Tickets — maintenance, moves, requests, incidents."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from database import get_db, log_audit
from email_service import notify_ticket_created, notify_ticket_update, notify_affected_user, notify_ticket_assigned

tickets_bp = Blueprint('tickets', __name__)


def next_ticket_number(conn):
    row = conn.execute(
        "SELECT ticket_number FROM tickets ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row:
        num = int(row['ticket_number'].split('-')[1]) + 1
    else:
        num = 1
    return f"TKT-{num:04d}"


@tickets_bp.route('/mine')
def my_tickets():
    """Employee view: my submitted tickets."""
    with get_db() as conn:
        tickets = conn.execute("""
            SELECT t.*, ea.name as assignee_name,
                   a.asset_tag, em.name as equipment_name
            FROM tickets t
            LEFT JOIN employees ea ON t.assigned_to = ea.id
            LEFT JOIN assets a ON t.asset_id = a.id
            LEFT JOIN equipment_models em ON a.equipment_model_id = em.id
            WHERE t.submitted_by = ?
            ORDER BY t.created_at DESC
        """, (g.user['id'],)).fetchall()
    return render_template('tickets/my_tickets.html', tickets=tickets)


@tickets_bp.route('/')
def list_tickets():
    status = request.args.get('status', '')
    ttype = request.args.get('type', '')

    with get_db() as conn:
        where_parts = []
        params = []
        if status:
            where_parts.append("t.status = ?")
            params.append(status)
        if ttype:
            where_parts.append("t.type = ?")
            params.append(ttype)
        where_sql = " WHERE " + " AND ".join(where_parts) if where_parts else ""

        tickets = conn.execute(f"""
            SELECT t.*, e.name as submitter_name,
                   ea.name as assignee_name,
                   a.asset_tag, em.name as equipment_name
            FROM tickets t
            JOIN employees e ON t.submitted_by = e.id
            LEFT JOIN employees ea ON t.assigned_to = ea.id
            LEFT JOIN assets a ON t.asset_id = a.id
            LEFT JOIN equipment_models em ON a.equipment_model_id = em.id
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

    return render_template('tickets/list.html',
                           tickets=tickets, status=status, ttype=ttype)


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

            # Confirm the asset still exists (avoid a stale-tab IntegrityError).
            asset_exists = conn.execute(
                "SELECT 1 FROM assets WHERE id = ?", (asset_id,)).fetchone()
            if not asset_exists:
                flash('That asset no longer exists.', 'error')
                return redirect(url_for('inventory.manage_assets'))

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


@tickets_bp.route('/<int:ticket_id>')
def ticket_detail(ticket_id):
    with get_db() as conn:
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

        if not ticket:
            flash('Ticket not found.', 'error')
            return redirect(url_for('tickets.list_tickets'))

        comments = conn.execute("""
            SELECT tc.*, e.name as author_name
            FROM ticket_comments tc
            JOIN employees e ON tc.author_id = e.id
            WHERE tc.ticket_id = ?
            ORDER BY tc.created_at
        """, (ticket_id,)).fetchall()

        employees = conn.execute(
            "SELECT id, name FROM employees WHERE is_active=1 ORDER BY name"
        ).fetchall()

    return render_template('tickets/detail.html',
                           ticket=ticket, comments=comments, employees=employees)


@tickets_bp.route('/<int:ticket_id>/comment', methods=['POST'])
def add_comment(ticket_id):
    with get_db() as conn:
        is_internal = 1 if request.form.get('is_internal') else 0
        conn.execute("""
            INSERT INTO ticket_comments (ticket_id, author_id, body, is_internal)
            VALUES (?, ?, ?, ?)
        """, (ticket_id, g.user['id'], request.form['body'], is_internal))

        # Email the ticket submitter (skip internal notes)
        if not is_internal:
            ticket = conn.execute(
                "SELECT t.*, e.email as submitter_email "
                "FROM tickets t JOIN employees e ON t.submitted_by=e.id WHERE t.id=?",
                (ticket_id,)
            ).fetchone()
            if ticket and ticket['submitter_email'] and ticket['submitted_by'] != g.user['id']:
                notify_ticket_update(dict(ticket), ticket['submitter_email'],
                                     'comment', g.user['name'])
        flash('Comment added.', 'success')
    return redirect(url_for('tickets.ticket_detail', ticket_id=ticket_id))


@tickets_bp.route('/<int:ticket_id>/update', methods=['POST'])
def update_ticket(ticket_id):
    with get_db() as conn:
        old = conn.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        if not old:
            flash('Ticket not found.', 'error')
            return redirect(url_for('tickets.list_tickets'))

        new_status = request.form.get('status', old['status'])
        new_priority = request.form.get('priority', old['priority'])
        # Preserve the explicit "unassigned" choice (None != absent field).
        if 'assigned_to' in request.form:
            raw = request.form.get('assigned_to', '').strip()
            new_assignee = int(raw) if raw else None
        else:
            new_assignee = old['assigned_to']
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

        # If the assignee changed, audit and notify the new assignee.
        if new_assignee != old['assigned_to']:
            log_audit(conn, 'tickets', ticket_id, 'update',
                      'assigned_to', old['assigned_to'], new_assignee,
                      changed_by=g.user['id'])
            # Email the new assignee only when there IS one.
            if new_assignee:
                assignee = conn.execute(
                    "SELECT email FROM employees WHERE id=?", (new_assignee,)
                ).fetchone()
                if assignee and assignee['email']:
                    assigned_ticket = conn.execute("""
                        SELECT t.ticket_number, t.title, t.description, t.priority,
                               a.asset_tag, em.name AS equipment_name
                        FROM tickets t
                        LEFT JOIN assets a ON t.asset_id = a.id
                        LEFT JOIN equipment_models em ON a.equipment_model_id = em.id
                        WHERE t.id = ?
                    """, (ticket_id,)).fetchone()
                    notify_ticket_assigned(dict(assigned_ticket),
                                            assignee['email'], g.user['name'])

        # Audit priority changes too.
        if new_priority != old['priority']:
            log_audit(conn, 'tickets', ticket_id, 'update',
                      'priority', old['priority'], new_priority,
                      changed_by=g.user['id'])

        if new_status != old['status']:
            log_audit(conn, 'tickets', ticket_id, 'status_change',
                      'status', old['status'], new_status,
                      changed_by=g.user['id'])

            # Notify the original ticket creator only when the ticket is
            # resolved or closed — mid-flight transitions would just be
            # noise. Skip if the creator is the one making the change
            # (no point emailing yourself).
            if new_status in ('resolved', 'closed') and old['submitted_by'] != g.user['id']:
                submitter = conn.execute(
                    "SELECT email FROM employees WHERE id=?", (old['submitted_by'],)
                ).fetchone()
                if submitter and submitter['email']:
                    updated_ticket = conn.execute(
                        "SELECT * FROM tickets WHERE id=?", (ticket_id,)
                    ).fetchone()
                    notify_ticket_update(dict(updated_ticket), submitter['email'],
                                         'status_change', g.user['name'])

            # Also email the affected end user when the ticket is resolved.
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
