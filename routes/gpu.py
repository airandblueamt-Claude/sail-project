"""GPU subsystem — separate inventory and allocation-request flow.

Lives apart from the existing assets/tickets domain. A request has one of
three kinds (new_infra / gpu_allocation / compute_partnership / other);
all child sections are optional regardless of kind — request_kind is a UI
hint, not a constraint.

Child tables read/written here:

    gpu_request_models         flat: model_name, vram_gb, gpu_count [, max]
    gpu_request_workloads      flat: name, config, estimated_hours
    gpu_request_deliverables   flat: description
    gpu_request_phases         flat: name, target_date, description
    gpu_request_contributions  flat: name, description, benefit
    gpu_request_vm_groups
      └─ gpu_request_vm_roles  nested under each group
    gpu_request_fields         section/key/value bucket — used for
                               networking + remote-access sections

A request is "open" while gpu_requests.decided_at IS NULL; once a reviewer
records a response, decided_at is set. Reopen clears all six response fields.
"""
import re
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from database import get_db, log_audit

gpu_bp = Blueprint('gpu', __name__)

REQUESTER_TYPES = ('internal', 'partner', 'academic', 'vendor')
REQUEST_KINDS = ('new_infra', 'gpu_allocation', 'compute_partnership', 'other')
DECISIONS = ('approved', 'approved_with_conditions', 'rejected')
REVIEW_ROLES = ('admin', 'manager', 'technician')

# Flat blocks parsed by _parse_blocks (block[idx][field] form names).
# VM groups are 2-level and parsed separately by _parse_vm_groups.
BLOCK_NAMES = ('models', 'workloads', 'deliverables', 'phases', 'contributions')
# Per-block required + optional fields. Required must be non-empty for the
# row to count; rows where every required field is empty are silently dropped.
BLOCK_FIELDS = {
    'models':        {'required': ('model_name',),
                      'optional': ('vram_gb', 'gpu_count', 'gpu_count_max')},
    'workloads':     {'required': ('name',),
                      'optional': ('config', 'estimated_hours')},
    'deliverables':  {'required': ('description',),
                      'optional': ()},
    'phases':        {'required': ('name',),
                      'optional': ('target_date', 'description')},
    'contributions': {'required': ('name',),
                      'optional': ('description', 'benefit')},
}
INT_FIELDS = {'vram_gb', 'gpu_count', 'gpu_count_max', 'estimated_hours'}

# Sections persisted into gpu_request_fields. The keys listed are what the
# template renders as labelled inputs; extra section/key pairs from the
# extractor are accepted on POST too (the template just doesn't surface
# them yet).
FIELD_SECTIONS = ('networking', 'access', 'relationship')

# VM-role columns (per-role spec under each VM group).
VM_ROLE_FIELDS = ('role_name', 'vm_count', 'vcpu_per_vm', 'ram_gb_per_vm',
                  'disk_gb_per_vm', 'disk_type', 'os', 'notes')
VM_ROLE_INT_FIELDS = {'vm_count', 'vcpu_per_vm', 'ram_gb_per_vm', 'disk_gb_per_vm'}


# ── Inventory ──────────────────────────────────────────────────────────────

@gpu_bp.route('/')
def inventory():
    f_cluster = request.args.get('cluster', '').strip()
    f_role = request.args.get('role', '').strip()
    q = request.args.get('q', '').strip()

    where = ['1=1']
    params = []
    if f_cluster:
        where.append('cluster = ?')
        params.append(f_cluster)
    if f_role:
        where.append('node_role = ?')
        params.append(f_role)
    if q:
        where.append('(asset_tag LIKE ? OR model LIKE ? OR xcc_ip LIKE ? OR notes LIKE ?)')
        like = f'%{q}%'
        params += [like, like, like, like]
    where_sql = ' AND '.join(where)

    with get_db() as conn:
        rows = conn.execute(f"""
            SELECT * FROM gpu_assets
            WHERE {where_sql}
            ORDER BY (parent_asset_id IS NOT NULL),
                     (cluster='HPC-Linux'),
                     asset_tag
        """, params).fetchall()
        clusters = conn.execute(
            "SELECT DISTINCT cluster FROM gpu_assets WHERE cluster IS NOT NULL ORDER BY cluster"
        ).fetchall()
        roles = conn.execute(
            "SELECT DISTINCT node_role FROM gpu_assets WHERE node_role IS NOT NULL ORDER BY node_role"
        ).fetchall()

    rows_dicts = [dict(r) for r in rows]
    by_id = {r['id']: r for r in rows_dicts}
    hosts = [r for r in rows_dicts if r['kind'] == 'host']
    children_by_parent = {}
    orphans = []
    for r in rows_dicts:
        if r['kind'] != 'gpu':
            continue
        parent = by_id.get(r['parent_asset_id'])
        if parent is None:
            orphans.append(r)
        else:
            children_by_parent.setdefault(parent['id'], []).append(r)

    return render_template('gpu/inventory_list.html',
                           hosts=hosts,
                           children_by_parent=children_by_parent,
                           orphans=orphans,
                           clusters=clusters, roles=roles,
                           f_cluster=f_cluster, f_role=f_role, q=q)


@gpu_bp.route('/<asset_tag>')
def inventory_detail(asset_tag):
    with get_db() as conn:
        asset = conn.execute("""
            SELECT a.*, p.asset_tag AS parent_tag
            FROM gpu_assets a
            LEFT JOIN gpu_assets p ON a.parent_asset_id = p.id
            WHERE a.asset_tag = ?
        """, (asset_tag,)).fetchone()
        if not asset:
            flash('GPU asset not found.', 'error')
            return redirect(url_for('gpu.inventory'))
        children = conn.execute(
            "SELECT * FROM gpu_assets WHERE parent_asset_id = ? ORDER BY pci_slot, asset_tag",
            (asset['id'],)).fetchall()
        # Decided requests that allocated this asset_tag — substring match is
        # safe at this volume (no asset_tag is a prefix of another).
        related = conn.execute(
            "SELECT request_number, title, decided_at, decision "
            "FROM gpu_requests "
            "WHERE decided_at IS NOT NULL AND allocated_asset_tags LIKE ? "
            "ORDER BY decided_at DESC LIMIT 20",
            (f'%{asset["asset_tag"]}%',)).fetchall()
    return render_template('gpu/inventory_detail.html',
                           asset=asset, children=children, related=related)


# ── Request list / detail / submit / respond / reopen ──────────────────────

def _next_request_number(conn):
    year = date.today().year
    row = conn.execute(
        "SELECT request_number FROM gpu_requests "
        "WHERE request_number LIKE ? ORDER BY id DESC LIMIT 1",
        (f"GPU-{year}-%",)).fetchone()
    if row:
        try:
            n = int(row['request_number'].split('-')[-1]) + 1
        except (ValueError, IndexError):
            n = 1
    else:
        n = 1
    return f"GPU-{year}-{n:04d}"


@gpu_bp.route('/requests/')
def request_list():
    f_state = request.args.get('state', '').strip()
    f_mine = request.args.get('mine', '').strip()

    where = ['1=1']
    params = []
    if f_state == 'open':
        where.append('decided_at IS NULL')
    elif f_state == 'decided':
        where.append('decided_at IS NOT NULL')
    if f_mine == 'yes':
        where.append('requester_id = ?')
        params.append(g.user['id'])
    where_sql = ' AND '.join(where)

    with get_db() as conn:
        rows = conn.execute(f"""
            SELECT r.*, e.name AS requester_name_resolved,
                   (SELECT COUNT(*) FROM gpu_request_models    WHERE request_id = r.id) AS n_models,
                   (SELECT COUNT(*) FROM gpu_request_workloads WHERE request_id = r.id) AS n_workloads
            FROM gpu_requests r
            LEFT JOIN employees e ON r.requester_id = e.id
            WHERE {where_sql}
            ORDER BY (r.decided_at IS NOT NULL), r.created_at DESC
        """, params).fetchall()

    is_reviewer = g.user['role'] in REVIEW_ROLES
    return render_template('gpu/request_list.html',
                           requests=rows,
                           f_state=f_state, f_mine=f_mine,
                           is_reviewer=is_reviewer)


def _parse_blocks(form):
    """Pull indexed fields out of the form. Returns dict[block][idx][field]=value."""
    blocks = {b: {} for b in BLOCK_NAMES}
    pat = re.compile(
        r'^(' + '|'.join(BLOCK_NAMES) + r')\[(\d+)\]\[(\w+)\]$')
    for key, val in form.items():
        m = pat.match(key)
        if not m:
            continue
        block, idx, field = m.group(1), int(m.group(2)), m.group(3)
        blocks[block].setdefault(idx, {})[field] = val.strip()
    return blocks


def _validate_block_rows(blocks):
    """Drop empty rows; coerce ints; report errors keyed by 'block[idx].field'.
    Returns (cleaned_rows_per_block, errors_list).
    cleaned_rows_per_block is dict[block] -> list of dicts (in idx-sorted order).
    """
    errors = []
    cleaned = {b: [] for b in BLOCK_NAMES}
    for block, by_idx in blocks.items():
        spec = BLOCK_FIELDS[block]
        for idx in sorted(by_idx.keys()):
            row = by_idx[idx]
            # Drop rows where every field (req + opt) is empty.
            if not any((row.get(f) or '').strip() for f in spec['required'] + spec['optional']):
                continue
            # Required fields must be non-empty.
            for f in spec['required']:
                if not (row.get(f) or '').strip():
                    errors.append(f'{block} row #{idx + 1}: {f} is required.')
            # Coerce ints.
            for f in spec['optional']:
                if f in INT_FIELDS:
                    raw = (row.get(f) or '').strip()
                    if raw == '':
                        row[f] = None
                    else:
                        try:
                            row[f] = int(raw)
                        except ValueError:
                            errors.append(f'{block} row #{idx + 1}: {f} must be a whole number.')
                            row[f] = None
                else:
                    row[f] = (row.get(f) or '').strip() or None
            # Strip required text fields.
            for f in spec['required']:
                row[f] = (row.get(f) or '').strip()
            cleaned[block].append(row)
    return cleaned, errors


def _parse_vm_groups(form):
    """Pull vm_groups[g][name|summary] and vm_groups[g][roles][r][field] from the form.

    Returns a list of group dicts, each with a 'roles' list inside.
    Group-level pattern: vm_groups[g_idx][name]  /  vm_groups[g_idx][summary]
    Role-level pattern:  vm_groups[g_idx][roles][r_idx][role_name|vm_count|...]

    Empty groups (no name and no non-empty role) are dropped silently.
    """
    g_pat = re.compile(r'^vm_groups\[(\d+)\]\[(name|summary)\]$')
    r_pat = re.compile(r'^vm_groups\[(\d+)\]\[roles\]\[(\d+)\]\[(\w+)\]$')
    groups = {}
    for key, val in form.items():
        m = g_pat.match(key)
        if m:
            g_idx = int(m.group(1))
            groups.setdefault(g_idx, {'name': '', 'summary': '', 'roles': {}})
            groups[g_idx][m.group(2)] = val.strip()
            continue
        m = r_pat.match(key)
        if m:
            g_idx = int(m.group(1))
            r_idx = int(m.group(2))
            field = m.group(3)
            groups.setdefault(g_idx, {'name': '', 'summary': '', 'roles': {}})
            groups[g_idx]['roles'].setdefault(r_idx, {})[field] = val.strip()

    # Flatten + drop empties; coerce role ints.
    cleaned = []
    errors = []
    for g_idx in sorted(groups.keys()):
        g = groups[g_idx]
        roles_clean = []
        for r_idx in sorted(g['roles'].keys()):
            role = g['roles'][r_idx]
            # Drop a role row if every field is empty.
            if not any((role.get(f) or '').strip() for f in VM_ROLE_FIELDS):
                continue
            if not (role.get('role_name') or '').strip():
                errors.append(
                    f'VM group #{g_idx + 1} role #{r_idx + 1}: role name is required.')
            for f in VM_ROLE_FIELDS:
                raw = (role.get(f) or '').strip()
                if f in VM_ROLE_INT_FIELDS:
                    if raw == '':
                        role[f] = None
                    else:
                        try:
                            role[f] = int(raw)
                        except ValueError:
                            errors.append(
                                f'VM group #{g_idx + 1} role #{r_idx + 1}: '
                                f'{f} must be a whole number.')
                            role[f] = None
                else:
                    role[f] = raw or None
            roles_clean.append(role)
        if not g['name'].strip() and not roles_clean:
            continue
        if not g['name'].strip():
            errors.append(f'VM group #{g_idx + 1}: group name is required.')
        cleaned.append({
            'name': g['name'].strip(),
            'summary': g['summary'].strip() or None,
            'roles': roles_clean,
        })
    return cleaned, errors


def _parse_fields(form):
    """Pull fields[section][key]=value pairs out of the form (networking/access/etc).

    Empty values are dropped. Returns a list of (section, key, value) tuples.
    """
    pat = re.compile(r'^fields\[(\w+)\]\[(\w+)\]$')
    out = []
    for key, val in form.items():
        m = pat.match(key)
        if not m:
            continue
        section, k = m.group(1), m.group(2)
        v = val.strip()
        if v:
            out.append((section, k, v))
    return out


def _validate_parent(form):
    errors = []
    title = form.get('title', '').strip()
    if not title:
        errors.append('Title is required.')

    requester_type = form.get('requester_type', 'internal')
    if requester_type not in REQUESTER_TYPES:
        errors.append('Invalid requester type.')

    request_kind = form.get('request_kind', '').strip() or None
    if request_kind is not None and request_kind not in REQUEST_KINDS:
        errors.append('Invalid request kind.')

    def _int(name, label):
        raw = form.get(name, '').strip()
        if not raw:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            errors.append(f'{label} must be a whole number.')
            return None

    requested_hours = _int('requested_hours', 'Requested hours')

    start = form.get('start_date', '').strip() or None
    end = form.get('end_date', '').strip() or None
    if start and end and end < start:
        errors.append('End date cannot be before start date.')

    return {
        'request_kind': request_kind,
        'title': title,
        'use_case': form.get('use_case', '').strip() or None,
        'requester_type': requester_type,
        'requester_name': form.get('requester_name', '').strip() or None,
        'requester_email': form.get('requester_email', '').strip() or None,
        'requester_org': form.get('requester_org', '').strip() or None,
        'requested_hours': requested_hours,
        'start_date': start,
        'end_date': end,
        'duration_text': form.get('duration_text', '').strip() or None,
        'existing_resource_ref': form.get('existing_resource_ref', '').strip() or None,
        'notes': form.get('notes', '').strip() or None,
    }, errors


@gpu_bp.route('/requests/new', methods=['GET', 'POST'])
def request_new():
    if request.method == 'POST':
        values, errors_p = _validate_parent(request.form)
        raw_blocks = _parse_blocks(request.form)
        cleaned_blocks, errors_b = _validate_block_rows(raw_blocks)
        vm_groups, errors_v = _parse_vm_groups(request.form)
        field_rows = _parse_fields(request.form)
        errors = errors_p + errors_b + errors_v

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('gpu/request_new.html',
                                   values=values,
                                   blocks=cleaned_blocks,
                                   vm_groups=vm_groups,
                                   field_rows=field_rows,
                                   requester_types=REQUESTER_TYPES,
                                   request_kinds=REQUEST_KINDS,
                                   field_sections=FIELD_SECTIONS)

        with get_db() as conn:
            number = _next_request_number(conn)
            cur = conn.execute("""
                INSERT INTO gpu_requests (
                    request_number, request_kind, title, use_case,
                    requester_id, requester_name, requester_email,
                    requester_org, requester_type,
                    requested_hours, start_date, end_date, duration_text,
                    existing_resource_ref, notes, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual')
            """, (
                number, values['request_kind'], values['title'], values['use_case'],
                g.user['id'], values['requester_name'], values['requester_email'],
                values['requester_org'], values['requester_type'],
                values['requested_hours'], values['start_date'], values['end_date'],
                values['duration_text'],
                values['existing_resource_ref'],
                values['notes'],
            ))
            req_id = cur.lastrowid

            for sort_order, row in enumerate(cleaned_blocks['models']):
                conn.execute(
                    "INSERT INTO gpu_request_models "
                    "(request_id, sort_order, model_name, vram_gb, gpu_count, gpu_count_max) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (req_id, sort_order, row['model_name'],
                     row.get('vram_gb'), row.get('gpu_count'), row.get('gpu_count_max')))
            for sort_order, row in enumerate(cleaned_blocks['workloads']):
                conn.execute(
                    "INSERT INTO gpu_request_workloads "
                    "(request_id, sort_order, name, config, estimated_hours) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (req_id, sort_order, row['name'], row.get('config'), row.get('estimated_hours')))
            for sort_order, row in enumerate(cleaned_blocks['deliverables']):
                conn.execute(
                    "INSERT INTO gpu_request_deliverables "
                    "(request_id, sort_order, description) VALUES (?, ?, ?)",
                    (req_id, sort_order, row['description']))
            for sort_order, row in enumerate(cleaned_blocks['phases']):
                conn.execute(
                    "INSERT INTO gpu_request_phases "
                    "(request_id, sort_order, name, target_date, description) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (req_id, sort_order, row['name'], row.get('target_date'), row.get('description')))
            for sort_order, row in enumerate(cleaned_blocks['contributions']):
                conn.execute(
                    "INSERT INTO gpu_request_contributions "
                    "(request_id, sort_order, name, description, benefit) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (req_id, sort_order, row['name'],
                     row.get('description'), row.get('benefit')))
            for g_order, group in enumerate(vm_groups):
                cur_g = conn.execute(
                    "INSERT INTO gpu_request_vm_groups "
                    "(request_id, sort_order, name, summary) VALUES (?, ?, ?, ?)",
                    (req_id, g_order, group['name'], group['summary']))
                group_id = cur_g.lastrowid
                for r_order, role in enumerate(group['roles']):
                    conn.execute(
                        "INSERT INTO gpu_request_vm_roles "
                        "(group_id, sort_order, role_name, vm_count, vcpu_per_vm, "
                        " ram_gb_per_vm, disk_gb_per_vm, disk_type, os, notes) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (group_id, r_order, role['role_name'],
                         role.get('vm_count'), role.get('vcpu_per_vm'),
                         role.get('ram_gb_per_vm'), role.get('disk_gb_per_vm'),
                         role.get('disk_type'), role.get('os'), role.get('notes')))
            for section, key, value in field_rows:
                conn.execute(
                    "INSERT INTO gpu_request_fields (request_id, section, key, value) "
                    "VALUES (?, ?, ?, ?)",
                    (req_id, section, key, value))

            log_audit(conn, 'gpu_requests', req_id, 'create',
                      changed_by=g.user['id'])
        flash(f'Request {number} submitted.', 'success')
        return redirect(url_for('gpu.request_detail', number=number))

    # GET — empty form prefilled from current user.
    values = {
        'request_kind': '',
        'title': '',
        'use_case': '',
        'requester_type': 'internal',
        'requester_name': g.user['name'],
        'requester_email': g.user.get('email', '') or '',
        'requester_org': '',
        'requested_hours': '',
        'start_date': '',
        'end_date': '',
        'duration_text': '',
        'existing_resource_ref': '',
        'notes': '',
    }
    blocks = {b: [] for b in BLOCK_NAMES}
    return render_template('gpu/request_new.html',
                           values=values, blocks=blocks,
                           vm_groups=[],
                           field_rows=[],
                           requester_types=REQUESTER_TYPES,
                           request_kinds=REQUEST_KINDS,
                           field_sections=FIELD_SECTIONS)


@gpu_bp.route('/requests/<number>')
def request_detail(number):
    with get_db() as conn:
        req = conn.execute("""
            SELECT r.*,
                   e.name AS requester_name_resolved,
                   e.email AS requester_email_resolved,
                   d.name AS decided_by_name
            FROM gpu_requests r
            LEFT JOIN employees e ON r.requester_id = e.id
            LEFT JOIN employees d ON r.decided_by = d.id
            WHERE r.request_number = ?
        """, (number,)).fetchone()
        if not req:
            flash('Request not found.', 'error')
            return redirect(url_for('gpu.request_list'))
        models = conn.execute(
            "SELECT * FROM gpu_request_models WHERE request_id=? ORDER BY sort_order, id",
            (req['id'],)).fetchall()
        workloads = conn.execute(
            "SELECT * FROM gpu_request_workloads WHERE request_id=? ORDER BY sort_order, id",
            (req['id'],)).fetchall()
        deliverables = conn.execute(
            "SELECT * FROM gpu_request_deliverables WHERE request_id=? ORDER BY sort_order, id",
            (req['id'],)).fetchall()
        phases = conn.execute(
            "SELECT * FROM gpu_request_phases WHERE request_id=? ORDER BY sort_order, id",
            (req['id'],)).fetchall()
    is_reviewer = g.user['role'] in REVIEW_ROLES
    return render_template('gpu/request_detail.html',
                           request_=req,
                           models=models, workloads=workloads,
                           deliverables=deliverables, phases=phases,
                           is_reviewer=is_reviewer,
                           decisions=DECISIONS)


@gpu_bp.route('/requests/<number>/respond', methods=['POST'])
def request_respond(number):
    if g.user['role'] not in REVIEW_ROLES:
        flash('Only reviewers can respond to requests.', 'error')
        return redirect(url_for('gpu.request_detail', number=number))

    decision = request.form.get('decision', '').strip()
    if decision not in DECISIONS:
        flash('Invalid decision.', 'error')
        return redirect(url_for('gpu.request_detail', number=number))

    fit_notes = request.form.get('fit_notes', '').strip() or None
    response_notes = request.form.get('response_notes', '').strip() or None
    allocated = request.form.get('allocated_asset_tags', '').strip() or None

    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM gpu_requests WHERE request_number = ?",
            (number,)).fetchone()
        if not row:
            flash('Request not found.', 'error')
            return redirect(url_for('gpu.request_list'))
        conn.execute("""
            UPDATE gpu_requests
               SET decision = ?, fit_notes = ?, response_notes = ?,
                   allocated_asset_tags = ?,
                   decided_by = ?, decided_at = datetime('now'),
                   updated_at = datetime('now')
             WHERE id = ?
        """, (decision, fit_notes, response_notes, allocated,
              g.user['id'], row['id']))
        log_audit(conn, 'gpu_requests', row['id'], 'update',
                  field_name='decision', new_value=decision,
                  changed_by=g.user['id'])
    flash(f'Response recorded for {number}.', 'success')
    return redirect(url_for('gpu.request_detail', number=number))


@gpu_bp.route('/requests/<number>/reopen', methods=['POST'])
def request_reopen(number):
    if g.user['role'] not in REVIEW_ROLES:
        flash('Only reviewers can reopen requests.', 'error')
        return redirect(url_for('gpu.request_detail', number=number))
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM gpu_requests WHERE request_number = ?",
            (number,)).fetchone()
        if not row:
            flash('Request not found.', 'error')
            return redirect(url_for('gpu.request_list'))
        conn.execute("""
            UPDATE gpu_requests
               SET decision = NULL, fit_notes = NULL, response_notes = NULL,
                   allocated_asset_tags = NULL,
                   decided_by = NULL, decided_at = NULL,
                   updated_at = datetime('now')
             WHERE id = ?
        """, (row['id'],))
        log_audit(conn, 'gpu_requests', row['id'], 'update',
                  field_name='decided_at', old_value='set', new_value=None,
                  changed_by=g.user['id'])
    flash(f'Request {number} reopened.', 'success')
    return redirect(url_for('gpu.request_detail', number=number))
