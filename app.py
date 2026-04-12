"""SAIL — Smart Asset Inventory & Logistics."""
from flask import Flask, session, g, redirect, url_for, request, render_template, flash
from database import get_db
from config import SECRET_KEY, UPLOAD_FOLDER
from email_service import notify_registration
import os


def create_app():
    app = Flask(__name__)
    app.secret_key = SECRET_KEY
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # ── Auth: load user on every request ─────────────────────────────
    @app.before_request
    def load_user():
        g.user = None
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

        # Allow login/register/static without auth
        public = ('login', 'register', 'static')
        if not g.user and request.endpoint and request.endpoint not in public:
            return redirect(url_for('login'))

    @app.context_processor
    def inject_user():
        return dict(current_user=g.user)

    # ── Login ────────────────────────────────────────────────────────
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if g.user:
            return redirect(url_for('dashboard.index'))
        error = None
        if request.method == 'POST':
            email = request.form.get('email', '').strip()
            if not email:
                error = 'Please enter your email.'
            else:
                with get_db() as conn:
                    user = conn.execute(
                        "SELECT * FROM employees WHERE LOWER(email) = LOWER(?) AND is_active = 1",
                        (email,)).fetchone()
                if user:
                    session['user_id'] = user['id']
                    return redirect(url_for('dashboard.index'))
                else:
                    error = 'Email not found. Please register first.'
        return render_template('login.html', error=error)

    # ── Register ─────────────────────────────────────────────────────
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if g.user:
            return redirect(url_for('dashboard.index'))
        error = None
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip() or None
            dept_new = request.form.get('department', '').strip()

            if not name or not email:
                error = 'Name and email are required.'
            else:
                with get_db() as conn:
                    existing = conn.execute(
                        "SELECT id FROM employees WHERE LOWER(email) = LOWER(?)",
                        (email,)).fetchone()
                    if existing:
                        error = f'{email} is already registered. Try signing in.'
                    else:
                        dept_id = None
                        if dept_new:
                            conn.execute(
                                "INSERT OR IGNORE INTO departments (name) VALUES (?)",
                                (dept_new,))
                            dept_id = conn.execute(
                                "SELECT id FROM departments WHERE name = ?",
                                (dept_new,)).fetchone()['id']

                        cur = conn.execute(
                            "INSERT INTO employees (name, email, phone, "
                            "department_id, role) VALUES (?, ?, ?, ?, 'employee')",
                            (name, email, phone, dept_id))
                        session['user_id'] = cur.lastrowid
                        notify_registration(name, email)
                        flash(f'Welcome, {name}! Your account has been created.', 'success')
                        return redirect(url_for('dashboard.index'))

        return render_template('register.html', error=error)

    # ── Logout ───────────────────────────────────────────────────────
    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))

    # ── Blueprints ───────────────────────────────────────────────────
    from routes.dashboard import dashboard_bp
    from routes.inventory import inventory_bp
    from routes.bookings import bookings_bp
    from routes.tickets import tickets_bp
    from routes.employees import employees_bp
    from routes.help import help_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(bookings_bp, url_prefix='/bookings')
    app.register_blueprint(tickets_bp, url_prefix='/tickets')
    app.register_blueprint(employees_bp, url_prefix='/employees')
    app.register_blueprint(help_bp, url_prefix='/help')

    return app


if __name__ == '__main__':
    app = create_app()
    print("SAIL running at http://localhost:5555")
    app.run(debug=True, host='0.0.0.0', port=5555)
