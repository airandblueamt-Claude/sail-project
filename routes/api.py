"""
Read-only JSON API for external agents (Ollama, Claude, etc.) under /api/v1/*.

Auth is bearer-token:  Authorization: Bearer sail_<hex>
Tokens are minted by scripts/mint_api_token.py — plaintext is shown once;
only sha256(plaintext) is stored in api_tokens.token_hash.

Every endpoint below requires scope=read. Write-scope routes get added
later as siblings — keep this file additive.
"""
from functools import wraps
import hashlib
from flask import Blueprint, g, jsonify, request

from database import get_db

api_bp = Blueprint('api', __name__)

API_VERSION = '1'
MAX_LIMIT = 500
DEFAULT_LIMIT = 50


# ── auth helpers ───────────────────────────────────────────────────────────

def _hash_token(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode('utf-8')).hexdigest()


def _extract_bearer():
    header = request.headers.get('Authorization', '')
    if not header.lower().startswith('bearer '):
        return None
    return header[7:].strip() or None


def _lookup_token(plaintext: str):
    th = _hash_token(plaintext)
    with get_db() as conn:
        row = conn.execute(
            """SELECT t.id, t.name, t.scopes, t.revoked_at,
                      e.id  AS employee_id, e.name AS employee_name,
                      e.email, e.role, e.is_active
               FROM api_tokens t
               JOIN employees  e ON e.id = t.employee_id
               WHERE t.token_hash = ?""",
            (th,)
        ).fetchone()
        if not row:
            return None
        if row['revoked_at'] is not None or not row['is_active']:
            return None
        conn.execute(
            "UPDATE api_tokens SET last_used_at = datetime('now') WHERE id = ?",
            (row['id'],)
        )
        return dict(row)


def require_token(scope: str = 'read'):
    """Decorator: 401 if no/invalid token, 403 if scope missing."""
    def deco(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            plaintext = _extract_bearer()
            if not plaintext:
                return jsonify(error='unauthorized',
                               message='Missing Bearer token.'), 401
            tok = _lookup_token(plaintext)
            if not tok:
                return jsonify(error='unauthorized',
                               message='Invalid or revoked token.'), 401
            scopes = {s.strip() for s in (tok['scopes'] or '').split(',') if s.strip()}
            if scope not in scopes:
                return jsonify(error='forbidden',
                               message=f"Token lacks scope '{scope}'."), 403
            g.api_token = tok
            return fn(*args, **kwargs)
        return wrapped
    return deco


# ── pagination + filter helpers ────────────────────────────────────────────

def _paginate():
    try:
        limit = int(request.args.get('limit', DEFAULT_LIMIT))
        offset = int(request.args.get('offset', 0))
    except ValueError:
        return None, None, (jsonify(error='bad_request',
                                    message='limit/offset must be integers.'), 400)
    limit = max(1, min(limit, MAX_LIMIT))
    offset = max(0, offset)
    return limit, offset, None


def _count(conn, sql: str, params: tuple) -> int:
    row = conn.execute(f"SELECT COUNT(*) AS n FROM ({sql})", params).fetchone()
    return int(row['n']) if row else 0


# ── row serializers (single source of truth for response shape) ────────────

def _serialize_asset(r):
    return {
        'id': r['id'],
        'asset_tag': r['asset_tag'],
        'serial_number': r['serial_number'],
        'model_number': r['model_number'],
        'condition': r['condition'],
        'status': r['status'],
        'qty_represented': r['qty_represented'],
        'holder_name': r['holder_name'],
        'remark': r['remark'],
        'notes': r['notes'],
        'purchase_date': r['purchase_date'],
        'warranty_expiry': r['warranty_expiry'],
        'created_at': r['created_at'],
        'updated_at': r['updated_at'],
        'equipment_model': {
            'id': r['equipment_model_id'],
            'name': r['model_name'],
            'brand': r['brand'],
            'category': r['category_name'],
        } if r['equipment_model_id'] else None,
        'location': {
            'id': r['location_id'],
            'code': r['location_code'],
            'label': r['location_label'],
        } if r['location_id'] else None,
        'assigned_to': {
            'id': r['assigned_to'],
            'name': r['assignee_name'],
            'email': r['assignee_email'],
        } if r['assigned_to'] else None,
    }


def _serialize_ticket(r):
    return {
        'id': r['id'],
        'ticket_number': r['ticket_number'],
        'type': r['type'],
        'priority': r['priority'],
        'status': r['status'],
        'title': r['title'],
        'description': r['description'],
        'resolution': r['resolution'],
        'affected_user_name': r['affected_user_name'],
        'affected_user_email': r['affected_user_email'],
        'resolved_at': r['resolved_at'],
        'closed_at': r['closed_at'],
        'created_at': r['created_at'],
        'updated_at': r['updated_at'],
        'asset': {'id': r['asset_id'], 'asset_tag': r['asset_tag']} if r['asset_id'] else None,
        'submitted_by': {'id': r['submitted_by'], 'name': r['submitter_name'],
                         'email': r['submitter_email']} if r['submitted_by'] else None,
        'assigned_to': {'id': r['assigned_to'], 'name': r['assignee_name'],
                        'email': r['assignee_email']} if r['assigned_to'] else None,
        'issue_category': r['issue_category_name'],
    }


def _serialize_employee(r):
    return {
        'id': r['id'],
        'name': r['name'],
        'email': r['email'],
        'phone': r['phone'],
        'badge_number': r['badge_number'],
        'role': r['role'],
        'department': r['department_name'],
        'is_active': bool(r['is_active']),
        'created_at': r['created_at'],
    }


# ── meta ───────────────────────────────────────────────────────────────────

@api_bp.route('/health')
def health():
    """Open endpoint — useful for the agent to confirm reachability."""
    return jsonify(status='ok', service='sail', version=API_VERSION)


@api_bp.route('/me')
@require_token('read')
def me():
    tok = g.api_token
    return jsonify(
        token={'name': tok['name'], 'scopes': tok['scopes']},
        employee={'id': tok['employee_id'], 'name': tok['employee_name'],
                  'email': tok['email'], 'role': tok['role']},
    )


# ── assets ─────────────────────────────────────────────────────────────────

ASSETS_SELECT = """
    SELECT a.id, a.asset_tag, a.serial_number, a.model_number,
           a.condition, a.status, a.qty_represented, a.holder_name,
           a.remark, a.notes, a.purchase_date, a.warranty_expiry,
           a.created_at, a.updated_at,
           a.equipment_model_id, em.name AS model_name, em.brand,
           c.name AS category_name,
           a.location_id, l.code AS location_code, l.label AS location_label,
           a.assigned_to, e.name AS assignee_name, e.email AS assignee_email
    FROM assets a
    LEFT JOIN equipment_models em ON a.equipment_model_id = em.id
    LEFT JOIN categories       c  ON em.category_id = c.id
    LEFT JOIN locations        l  ON a.location_id = l.id
    LEFT JOIN employees        e  ON a.assigned_to = e.id
"""


@api_bp.route('/assets')
@require_token('read')
def list_assets():
    limit, offset, err = _paginate()
    if err:
        return err

    where, params = [], []
    if request.args.get('status'):
        where.append('a.status = ?'); params.append(request.args['status'])
    if request.args.get('condition'):
        where.append('a.condition = ?'); params.append(request.args['condition'])
    if request.args.get('location_id'):
        where.append('a.location_id = ?'); params.append(request.args['location_id'])
    if request.args.get('model_id'):
        where.append('a.equipment_model_id = ?'); params.append(request.args['model_id'])
    if request.args.get('q'):
        q = f"%{request.args['q']}%"
        where.append('(a.asset_tag LIKE ? OR a.serial_number LIKE ? OR a.holder_name LIKE ?)')
        params += [q, q, q]
    where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''

    with get_db() as conn:
        total = _count(conn, f"SELECT a.id FROM assets a {where_sql}", tuple(params))
        rows = conn.execute(
            f"{ASSETS_SELECT} {where_sql} ORDER BY a.asset_tag LIMIT ? OFFSET ?",
            tuple(params) + (limit, offset)
        ).fetchall()

    return jsonify(items=[_serialize_asset(r) for r in rows],
                   total=total, limit=limit, offset=offset)


@api_bp.route('/assets/<identifier>')
@require_token('read')
def get_asset(identifier):
    with get_db() as conn:
        if identifier.isdigit():
            row = conn.execute(f"{ASSETS_SELECT} WHERE a.id = ?", (int(identifier),)).fetchone()
        else:
            row = conn.execute(f"{ASSETS_SELECT} WHERE a.asset_tag = ?", (identifier,)).fetchone()
    if not row:
        return jsonify(error='not_found', message=f"No asset '{identifier}'."), 404
    return jsonify(_serialize_asset(row))


# ── tickets ────────────────────────────────────────────────────────────────

TICKETS_SELECT = """
    SELECT t.id, t.ticket_number, t.type, t.priority, t.status,
           t.title, t.description, t.resolution,
           t.affected_user_name, t.affected_user_email,
           t.resolved_at, t.closed_at, t.created_at, t.updated_at,
           t.asset_id, a.asset_tag,
           t.submitted_by, s.name AS submitter_name, s.email AS submitter_email,
           t.assigned_to, e.name AS assignee_name, e.email AS assignee_email,
           ic.name AS issue_category_name
    FROM tickets t
    LEFT JOIN assets           a  ON t.asset_id = a.id
    LEFT JOIN employees        s  ON t.submitted_by = s.id
    LEFT JOIN employees        e  ON t.assigned_to = e.id
    LEFT JOIN issue_categories ic ON t.issue_category_id = ic.id
"""


@api_bp.route('/tickets')
@require_token('read')
def list_tickets():
    limit, offset, err = _paginate()
    if err:
        return err

    where, params = [], []
    for col in ('status', 'priority', 'type'):
        if request.args.get(col):
            where.append(f't.{col} = ?'); params.append(request.args[col])
    if request.args.get('assignee_id'):
        where.append('t.assigned_to = ?'); params.append(request.args['assignee_id'])
    if request.args.get('submitted_by'):
        where.append('t.submitted_by = ?'); params.append(request.args['submitted_by'])
    if request.args.get('asset_id'):
        where.append('t.asset_id = ?'); params.append(request.args['asset_id'])
    if request.args.get('open') in ('1', 'true', 'yes'):
        where.append("t.status NOT IN ('resolved','closed')")
    if request.args.get('q'):
        q = f"%{request.args['q']}%"
        where.append('(t.title LIKE ? OR t.description LIKE ? OR t.ticket_number LIKE ?)')
        params += [q, q, q]
    where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''

    with get_db() as conn:
        total = _count(conn, f"SELECT t.id FROM tickets t {where_sql}", tuple(params))
        rows = conn.execute(
            f"{TICKETS_SELECT} {where_sql} ORDER BY t.id DESC LIMIT ? OFFSET ?",
            tuple(params) + (limit, offset)
        ).fetchall()

    return jsonify(items=[_serialize_ticket(r) for r in rows],
                   total=total, limit=limit, offset=offset)


@api_bp.route('/tickets/<identifier>')
@require_token('read')
def get_ticket(identifier):
    with get_db() as conn:
        if identifier.isdigit():
            row = conn.execute(f"{TICKETS_SELECT} WHERE t.id = ?", (int(identifier),)).fetchone()
        else:
            row = conn.execute(f"{TICKETS_SELECT} WHERE t.ticket_number = ?", (identifier,)).fetchone()
        if not row:
            return jsonify(error='not_found', message=f"No ticket '{identifier}'."), 404
        comments = conn.execute(
            """SELECT c.id, c.body, c.is_internal, c.created_at,
                      c.author_id, e.name AS author_name
               FROM ticket_comments c
               LEFT JOIN employees e ON c.author_id = e.id
               WHERE c.ticket_id = ? ORDER BY c.created_at""",
            (row['id'],)
        ).fetchall()

    out = _serialize_ticket(row)
    out['comments'] = [{
        'id': c['id'], 'body': c['body'], 'is_internal': bool(c['is_internal']),
        'created_at': c['created_at'],
        'author': {'id': c['author_id'], 'name': c['author_name']} if c['author_id'] else None,
    } for c in comments]
    return jsonify(out)


# ── reference data ─────────────────────────────────────────────────────────

@api_bp.route('/employees')
@require_token('read')
def list_employees():
    limit, offset, err = _paginate()
    if err:
        return err
    where, params = ['e.is_active = 1'], []
    if request.args.get('role'):
        where.append('e.role = ?'); params.append(request.args['role'])
    if request.args.get('q'):
        q = f"%{request.args['q']}%"
        where.append('(e.name LIKE ? OR e.email LIKE ? OR e.badge_number LIKE ?)')
        params += [q, q, q]
    where_sql = 'WHERE ' + ' AND '.join(where)
    with get_db() as conn:
        total = _count(conn, f"SELECT e.id FROM employees e {where_sql}", tuple(params))
        rows = conn.execute(
            f"""SELECT e.id, e.name, e.email, e.phone, e.badge_number, e.role,
                       e.is_active, e.created_at, d.name AS department_name
                FROM employees e LEFT JOIN departments d ON e.department_id = d.id
                {where_sql} ORDER BY e.name LIMIT ? OFFSET ?""",
            tuple(params) + (limit, offset)
        ).fetchall()
    return jsonify(items=[_serialize_employee(r) for r in rows],
                   total=total, limit=limit, offset=offset)


@api_bp.route('/locations')
@require_token('read')
def list_locations():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, code, label, building, floor, is_storage FROM locations ORDER BY code"
        ).fetchall()
    return jsonify(items=[dict(r) for r in rows], total=len(rows))


@api_bp.route('/categories')
@require_token('read')
def list_categories():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, name, description FROM categories ORDER BY name"
        ).fetchall()
    return jsonify(items=[dict(r) for r in rows], total=len(rows))


@api_bp.route('/issue-categories')
@require_token('read')
def list_issue_categories():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, name, is_active FROM issue_categories ORDER BY name"
        ).fetchall()
    return jsonify(items=[dict(r) for r in rows], total=len(rows))


@api_bp.route('/equipment-models')
@require_token('read')
def list_equipment_models():
    limit, offset, err = _paginate()
    if err:
        return err
    with get_db() as conn:
        total = _count(conn, "SELECT id FROM equipment_models", ())
        rows = conn.execute(
            """SELECT em.id, em.name, em.brand, em.model_number, em.specifications,
                      em.unit, em.expected_qty, c.name AS category_name,
                      (SELECT COUNT(*) FROM assets a WHERE a.equipment_model_id = em.id) AS asset_count
               FROM equipment_models em
               JOIN categories c ON em.category_id = c.id
               ORDER BY em.name LIMIT ? OFFSET ?""",
            (limit, offset)
        ).fetchall()
    return jsonify(items=[dict(r) for r in rows],
                   total=total, limit=limit, offset=offset)


# ── GPU subsystem ──────────────────────────────────────────────────────────

@api_bp.route('/gpu/assets')
@require_token('read')
def list_gpu_assets():
    with get_db() as conn:
        rows = conn.execute(
            """SELECT id, asset_tag, kind, model, vram_gb, xcc_ip,
                      cluster, node_role, pci_slot, parent_asset_id, notes,
                      created_at, updated_at
               FROM gpu_assets ORDER BY asset_tag"""
        ).fetchall()
    return jsonify(items=[dict(r) for r in rows], total=len(rows))


@api_bp.route('/gpu/requests')
@require_token('read')
def list_gpu_requests():
    where, params = [], []
    if request.args.get('open') in ('1', 'true', 'yes'):
        where.append('decided_at IS NULL')
    where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''
    with get_db() as conn:
        rows = conn.execute(
            f"""SELECT id, request_number, title, requester_name, requester_email,
                       requester_type, requested_hours, start_date, end_date,
                       decision, decided_at, created_at
                FROM gpu_requests {where_sql} ORDER BY id DESC""",
            tuple(params)
        ).fetchall()
    return jsonify(items=[dict(r) for r in rows], total=len(rows))


# ── inspections ────────────────────────────────────────────────────────────

def _serialize_inspection_summary(r):
    return {
        'id': r['id'],
        'date': r['inspection_date'],
        'submitted_at': r['submitted_at'],
        'created_at': r['created_at'],
        'recorded': int(r['recorded'] or 0),
        'total_items': int(r['total'] or 0),
        'inactive': int(r['inactive'] or 0),
        'engineer': r['engineer_name'],
        'amt_supervisor': r['amt_supervisor_name'],
        'sail_supervisor': r['sail_supervisor_name'],
    }


@api_bp.route('/inspections')
@require_token('read')
def list_inspections():
    limit, offset, err = _paginate()
    if err:
        return err
    where, params = [], []
    if request.args.get('from'):
        where.append('i.inspection_date >= ?'); params.append(request.args['from'])
    if request.args.get('to'):
        where.append('i.inspection_date <= ?'); params.append(request.args['to'])
    where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''
    with get_db() as conn:
        total_count = _count(conn, f"SELECT i.id FROM inspections i {where_sql}",
                             tuple(params))
        rows = conn.execute(
            f"""SELECT i.id, i.inspection_date, i.submitted_at, i.created_at,
                       e.name  AS engineer_name,
                       am.name AS amt_supervisor_name,
                       ss.name AS sail_supervisor_name,
                       (SELECT COUNT(*) FROM inspection_results r
                          WHERE r.inspection_id = i.id) AS recorded,
                       (SELECT COUNT(*) FROM inspection_results r
                          WHERE r.inspection_id = i.id
                            AND r.status = 'inactive') AS inactive,
                       (SELECT COUNT(*) FROM inspection_items
                          WHERE is_active = 1) AS total
                FROM inspections i
                LEFT JOIN employees e  ON i.inspection_engineer_id = e.id
                LEFT JOIN employees am ON i.amt_supervisor_id      = am.id
                LEFT JOIN employees ss ON i.sail_supervisor_id     = ss.id
                {where_sql}
                ORDER BY i.inspection_date DESC
                LIMIT ? OFFSET ?""",
            tuple(params) + (limit, offset)
        ).fetchall()
    return jsonify(items=[_serialize_inspection_summary(r) for r in rows],
                   total=total_count, limit=limit, offset=offset)


@api_bp.route('/inspections/<inspection_date>')
@require_token('read')
def get_inspection(inspection_date):
    with get_db() as conn:
        head = conn.execute(
            """SELECT i.*,
                      e.name  AS engineer_name,
                      am.name AS amt_supervisor_name,
                      ss.name AS sail_supervisor_name
               FROM inspections i
               LEFT JOIN employees e  ON i.inspection_engineer_id = e.id
               LEFT JOIN employees am ON i.amt_supervisor_id      = am.id
               LEFT JOIN employees ss ON i.sail_supervisor_id     = ss.id
               WHERE i.inspection_date = ?""",
            (inspection_date,)).fetchone()
        if not head:
            return jsonify(error='not_found',
                           message=f"No inspection for '{inspection_date}'."), 404
        rows = conn.execute(
            """SELECT ar.id AS area_id, ar.name AS area_name,
                      ar.display_order AS area_order,
                      it.id AS item_id, it.name AS item_name,
                      it.display_order AS item_order,
                      r.status, r.notes, r.updated_at
               FROM inspection_areas ar
               JOIN inspection_items it ON it.area_id = ar.id
               LEFT JOIN inspection_results r
                      ON r.item_id = it.id AND r.inspection_id = ?
               WHERE ar.is_active = 1 AND it.is_active = 1
               ORDER BY ar.display_order, ar.name, it.display_order, it.name""",
            (head['id'],)).fetchall()

    by_area = {}
    for r in rows:
        a = by_area.setdefault(r['area_id'], {
            'id': r['area_id'], 'name': r['area_name'], 'items': []
        })
        a['items'].append({
            'id': r['item_id'], 'name': r['item_name'],
            'status': r['status'], 'notes': r['notes'],
            'updated_at': r['updated_at'],
        })
    return jsonify({
        'id': head['id'],
        'date': head['inspection_date'],
        'submitted_at': head['submitted_at'],
        'notes': head['notes'],
        'engineer': head['engineer_name'],
        'amt_supervisor': head['amt_supervisor_name'],
        'sail_supervisor': head['sail_supervisor_name'],
        'areas': list(by_area.values()),
    })


@api_bp.route('/inspections/items/recurring')
@require_token('read')
def inspection_recurring_problems():
    try:
        days  = int(request.args.get('days',  30))
        limit = int(request.args.get('limit', 10))
    except ValueError:
        return jsonify(error='bad_request',
                       message='days and limit must be integers.'), 400
    days  = max(1, min(days, 365))
    limit = max(1, min(limit, 100))
    with get_db() as conn:
        rows = conn.execute(
            f"""SELECT it.id AS item_id, it.name AS item_name,
                       ar.name AS area_name, COUNT(*) AS hits
                FROM inspection_results r
                JOIN inspection_items it ON r.item_id = it.id
                JOIN inspection_areas ar ON it.area_id = ar.id
                JOIN inspections i        ON r.inspection_id = i.id
                WHERE r.status = 'inactive'
                  AND i.inspection_date >= date('now', '-{int(days)} days')
                GROUP BY it.id
                ORDER BY hits DESC, item_name
                LIMIT ?""",
            (limit,)).fetchall()
    return jsonify(items=[dict(r) for r in rows],
                   total=len(rows), days=days)


# ── aggregate stats ────────────────────────────────────────────────────────

@api_bp.route('/stats')
@require_token('read')
def stats():
    """One-shot dashboard summary — handy for the agent's first sniff."""
    with get_db() as conn:
        def scalar(sql, params=()):
            row = conn.execute(sql, params).fetchone()
            return int(row[0]) if row else 0

        def group(sql):
            return {r[0]: int(r[1]) for r in conn.execute(sql).fetchall()}

        return jsonify(
            assets={
                'total': scalar("SELECT COUNT(*) FROM assets"),
                'by_status':    group("SELECT status, COUNT(*) FROM assets GROUP BY status"),
                'by_condition': group("SELECT condition, COUNT(*) FROM assets GROUP BY condition"),
            },
            tickets={
                'total':       scalar("SELECT COUNT(*) FROM tickets"),
                'open':        scalar("SELECT COUNT(*) FROM tickets WHERE status NOT IN ('resolved','closed')"),
                'by_status':   group("SELECT status, COUNT(*) FROM tickets GROUP BY status"),
                'by_priority': group("SELECT priority, COUNT(*) FROM tickets GROUP BY priority"),
                'by_type':     group("SELECT type, COUNT(*) FROM tickets GROUP BY type"),
            },
            employees={
                'total':   scalar("SELECT COUNT(*) FROM employees WHERE is_active = 1"),
                'by_role': group("SELECT role, COUNT(*) FROM employees WHERE is_active = 1 GROUP BY role"),
            },
            gpu={
                'assets':         scalar("SELECT COUNT(*) FROM gpu_assets"),
                'requests_open':  scalar("SELECT COUNT(*) FROM gpu_requests WHERE decided_at IS NULL"),
                'requests_total': scalar("SELECT COUNT(*) FROM gpu_requests"),
            },
        )
