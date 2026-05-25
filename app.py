"""SAIL — Smart Asset Inventory & Logistics."""
from flask import Flask, session, g, redirect, url_for, request, render_template, flash, jsonify
from database import get_db
from config import SECRET_KEY, UPLOAD_FOLDER
import os


def create_app():
    app = Flask(__name__)
    app.secret_key = SECRET_KEY
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # ── Jinja filter: humanise enum values ───────────────────────────
    # Used everywhere a status/priority/condition/category/decision is
    # rendered. snake_case becomes Sentence case ("in_progress" ->
    # "In progress"); values that already have uppercase letters
    # (e.g. "Cloud / HCI", "Head") are left as-is.
    @app.template_filter('pretty')
    def pretty_filter(value):
        if value is None:
            return ''
        s = str(value).strip()
        if not s:
            return ''
        if any(c.isupper() for c in s):
            return s
        return s.replace('_', ' ').capitalize()

    # ── Auth: load user on every request ─────────────────────────────
    @app.before_request
    def load_user():
        g.user = None
        g.api_token = None

        # /api/v1/* uses bearer-token auth, not the session cookie — let it
        # through the session gate entirely. Each route enforces its own
        # @require_token('read'/'write') decorator. /api/v1/health is open.
        if request.path.startswith('/api/v1/'):
            return None

        user_id = session.get('user_id')
        if user_id:
            with get_db() as conn:
                row = conn.execute(
                    "SELECT e.*, d.name as department_name "
                    "FROM employees e LEFT JOIN departments d ON e.department_id = d.id "
                    "WHERE e.id = ? AND e.is_active = 1", (user_id,)
                ).fetchone()
                if row:
                    g.user = dict(row)
                else:
                    session.clear()

        # Allow login/static without auth. The assistant chat endpoint is a
        # JSON-POST surface — it returns its own 401 instead of getting an
        # HTML redirect that would confuse fetch() in the widget.
        public = ('login', 'static')
        if not g.user and request.endpoint and request.endpoint not in public:
            if request.path == '/assistant/chat':
                return jsonify({"error": "not authenticated"}), 401
            return redirect(url_for('login'))

        # If logged-in user must change password, lock them to change_password + logout.
        if g.user and g.user.get('must_change_password') and request.endpoint not in (
                'change_password', 'logout', 'static'):
            flash('Please set a new password before continuing.', 'info')
            return redirect(url_for('change_password'))

    @app.context_processor
    def inject_user():
        return dict(current_user=g.user)

    # ── Login (email + password) ────────────────────────────────────
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        from werkzeug.security import check_password_hash
        if g.user:
            return redirect(url_for('dashboard.index'))
        error = None
        if request.method == 'POST':
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')
            if not email or not password:
                error = 'Email and password are required.'
            else:
                with get_db() as conn:
                    user = conn.execute(
                        "SELECT * FROM employees WHERE LOWER(email) = LOWER(?) AND is_active = 1",
                        (email,)).fetchone()
                if user and user['password_hash'] and check_password_hash(user['password_hash'], password):
                    session['user_id'] = user['id']
                    return redirect(url_for('dashboard.index'))
                error = 'Invalid credentials.'
        return render_template('login.html', error=error)

    # ── Logout ───────────────────────────────────────────────────────
    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))

    # ── Cmd+K palette index ─────────────────────────────────────────
    # Returns a flat search index — pages, assets, tickets, GPU assets,
    # GPU requests, equipment models, employees — that the client-side
    # palette filters on each keypress. Loaded once per session on
    # first open. Auth via the standard before_request gate.
    @app.route('/api/palette')
    def palette_index():
        from flask import jsonify
        if not g.user:
            return jsonify(items=[]), 401
        items = []

        # Static pages — cheap to enumerate, useful as quick jumps.
        is_staff = g.user['role'] in ('admin', 'manager', 'technician')
        pages = [
            ('Dashboard',          url_for('dashboard.index'),         'layout-dashboard', is_staff),
            ('Equipment Catalog',  url_for('inventory.models'),        'layout-grid',      True),
            ('My Tickets',         url_for('tickets.my_tickets'),      'ticket',           is_staff),
            ('Floor plan',         url_for('floor_plan.index'),        'map',              True),
            ('Calendar',           url_for('floor_plan.calendar_page'),'calendar-days',    True),
            ('My Bookings',        url_for('floor_plan.bookings_page'),'calendar-check',   True),
            ('All Tickets',        url_for('tickets.list_tickets'),    'list-checks',      is_staff),
            ('New ticket',         url_for('tickets.new_ticket'),      'plus-circle',      True),
            ('Full Inventory',     url_for('inventory.all_models'),    'package',          is_staff),
            ('Manage Assets',      url_for('inventory.manage_assets'), 'hard-drive',       is_staff),
            ('Inventory Report',   url_for('reports.inventory'),       'bar-chart-3',      is_staff),
            ('Ticket Report',      url_for('reports.tickets'),         'activity',         is_staff),
            ('Booking Report',     url_for('reports.bookings'),        'calendar-check',   is_staff),
            ('GPU Inventory',      url_for('gpu.inventory'),           'cpu',              is_staff),
            ('GPU Requests',       url_for('gpu.request_list'),        'inbox',            is_staff),
            ('New GPU request',   url_for('gpu.request_new'),         'plus-circle',      True),
            ('Employees',          url_for('employees.list_employees'),'users',            is_staff),
            ('Issue Categories',   url_for('issue_categories.index'),  'tags',             is_staff),
            ('How It Works',       url_for('help.guide'),              'help-circle',      is_staff),
            ('Change password',    url_for('change_password'),         'key',              True),
        ]
        for label, url, icon, visible in pages:
            if visible:
                items.append({'label': label, 'subtitle': '',
                              'url': url, 'kind': 'Page', 'icon': icon})

        # Records — only pull what users are likely to jump to.
        with get_db() as conn:
            for r in conn.execute("""
                SELECT a.id, a.asset_tag, em.name AS model_name
                FROM assets a
                JOIN equipment_models em ON a.equipment_model_id = em.id
                ORDER BY a.asset_tag
            """).fetchall():
                items.append({
                    'label': r['asset_tag'],
                    'subtitle': r['model_name'] or '',
                    'url': url_for('inventory.asset_detail', asset_id=r['id']),
                    'kind': 'Asset', 'icon': 'hard-drive',
                })

            for r in conn.execute("""
                SELECT id, ticket_number, title, status
                FROM tickets
                WHERE title NOT LIKE 'Booking request:%'
                ORDER BY id DESC
            """).fetchall():
                items.append({
                    'label': r['ticket_number'],
                    'subtitle': f"{r['title']} · {r['status']}",
                    'url': url_for('tickets.ticket_detail', ticket_id=r['id']),
                    'kind': 'Ticket', 'icon': 'ticket',
                })

            for r in conn.execute("""
                SELECT asset_tag, kind, model, xcc_ip, vram_gb
                FROM gpu_assets ORDER BY asset_tag
            """).fetchall():
                if r['kind'] == 'host':
                    sub = f"{r['model'] or 'host'}"
                    if r['xcc_ip']:
                        sub += f" · {r['xcc_ip']}"
                    icon = 'server'
                else:
                    sub = f"{r['model'] or 'GPU'}"
                    if r['vram_gb']:
                        sub += f" · {r['vram_gb']} GB"
                    icon = 'cpu'
                items.append({
                    'label': r['asset_tag'],
                    'subtitle': sub,
                    'url': url_for('gpu.inventory_detail', asset_tag=r['asset_tag']),
                    'kind': 'GPU' if r['kind'] == 'gpu' else 'Host',
                    'icon': icon,
                })

            for r in conn.execute("""
                SELECT request_number, title, decided_at
                FROM gpu_requests ORDER BY id DESC
            """).fetchall():
                state = 'decided' if r['decided_at'] else 'open'
                items.append({
                    'label': r['request_number'],
                    'subtitle': f"{r['title']} · {state}",
                    'url': url_for('gpu.request_detail', number=r['request_number']),
                    'kind': 'Request', 'icon': 'inbox',
                })

            for r in conn.execute("""
                SELECT em.id, em.name, em.brand, c.name AS category
                FROM equipment_models em
                JOIN categories c ON em.category_id = c.id
                ORDER BY em.name
            """).fetchall():
                sub = r['brand'] or r['category'] or ''
                items.append({
                    'label': r['name'],
                    'subtitle': sub,
                    'url': url_for('inventory.model_detail', model_id=r['id']),
                    'kind': 'Equipment', 'icon': 'box',
                })

            if is_staff:
                for r in conn.execute("""
                    SELECT name, role, email FROM employees
                    WHERE is_active = 1 ORDER BY name
                """).fetchall():
                    items.append({
                        'label': r['name'],
                        'subtitle': f"{r['role']} · {r['email'] or ''}",
                        'url': url_for('employees.list_employees'),
                        'kind': 'Person', 'icon': 'user',
                    })

        return jsonify(items=items)

    # ── Password change (self-service) ──────────────────────────────
    @app.route('/account/password', methods=['GET', 'POST'])
    def change_password():
        from werkzeug.security import check_password_hash, generate_password_hash
        error = None
        if request.method == 'POST':
            current = request.form.get('current_password', '')
            new1 = request.form.get('new_password', '')
            new2 = request.form.get('confirm_password', '')
            if not current or not new1 or not new2:
                error = 'All fields are required.'
            elif new1 != new2:
                error = 'New passwords do not match.'
            elif len(new1) < 8:
                error = 'New password must be at least 8 characters.'
            else:
                with get_db() as conn:
                    row = conn.execute(
                        "SELECT password_hash FROM employees WHERE id = ?",
                        (g.user['id'],)).fetchone()
                    if not row or not row['password_hash'] or not check_password_hash(row['password_hash'], current):
                        error = 'Current password is incorrect.'
                    else:
                        conn.execute(
                            "UPDATE employees SET password_hash = ?, "
                            "must_change_password = 0 WHERE id = ?",
                            (generate_password_hash(new1), g.user['id']))
                        flash('Password updated.', 'success')
                        return redirect(url_for('dashboard.index'))
        return render_template('account/password.html', error=error)

    # ── Blueprints ───────────────────────────────────────────────────
    from routes.dashboard import dashboard_bp
    from routes.inventory import inventory_bp
    from routes.tickets import tickets_bp
    from routes.employees import employees_bp
    from routes.help import help_bp
    from routes.reports import reports_bp
    from routes.issue_categories import issue_categories_bp
    from routes.gpu import gpu_bp
    from routes.api import api_bp
    from routes.assistant import assistant_bp
    from app.floor_plan import floor_plan_bp, init_floor_plan

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(tickets_bp, url_prefix='/tickets')
    app.register_blueprint(employees_bp, url_prefix='/employees')
    app.register_blueprint(help_bp, url_prefix='/help')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(issue_categories_bp, url_prefix='/issue-categories')
    app.register_blueprint(gpu_bp, url_prefix='/gpu')
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    app.register_blueprint(assistant_bp, url_prefix='/assistant')
    app.register_blueprint(floor_plan_bp, url_prefix='/floor-plan')
    init_floor_plan(app)

    return app


if __name__ == '__main__':
    import os
    app = create_app()
    debug = os.environ.get('SAIL_DEBUG', '').lower() in ('1', 'true', 'yes')
    host = os.environ.get('SAIL_HOST', '127.0.0.1')
    port = int(os.environ.get('SAIL_PORT', '5555'))
    print(f"SAIL running at http://{host}:{port} (debug={debug})")
    app.run(debug=debug, host=host, port=port)
