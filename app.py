"""SAIL — Smart Asset Inventory & Logistics."""
from flask import Flask, session, g, redirect, url_for, request, render_template, flash
from database import get_db
from config import SECRET_KEY, UPLOAD_FOLDER
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

        # Allow login/static without auth
        public = ('login', 'static')
        if not g.user and request.endpoint and request.endpoint not in public:
            return redirect(url_for('login'))

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
                            "UPDATE employees SET password_hash = ? WHERE id = ?",
                            (generate_password_hash(new1), g.user['id']))
                        flash('Password updated.', 'success')
                        return redirect(url_for('dashboard.index'))
        return render_template('account/password.html', error=error)

    # ── Blueprints ───────────────────────────────────────────────────
    from routes.dashboard import dashboard_bp
    from routes.inventory import inventory_bp
    from routes.bookings import bookings_bp
    from routes.tickets import tickets_bp
    from routes.employees import employees_bp
    from routes.help import help_bp
    from routes.reports import reports_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(bookings_bp, url_prefix='/bookings')
    app.register_blueprint(tickets_bp, url_prefix='/tickets')
    app.register_blueprint(employees_bp, url_prefix='/employees')
    app.register_blueprint(help_bp, url_prefix='/help')
    app.register_blueprint(reports_bp, url_prefix='/reports')

    return app


if __name__ == '__main__':
    app = create_app()
    print("SAIL running at http://localhost:5555")
    app.run(debug=True, host='0.0.0.0', port=5555)
