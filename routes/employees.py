"""Employees — register and manage staff."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from database import get_db, log_audit

employees_bp = Blueprint('employees', __name__)


@employees_bp.route('/')
def list_employees():
    q = request.args.get('q', '').strip()
    with get_db() as conn:
        if q:
            employees = conn.execute(
                """SELECT e.*, d.name as department_name
                   FROM employees e
                   LEFT JOIN departments d ON e.department_id = d.id
                   WHERE e.name LIKE ? OR e.badge_number LIKE ? OR e.email LIKE ?
                   ORDER BY e.name""",
                (f'%{q}%', f'%{q}%', f'%{q}%')
            ).fetchall()
        else:
            employees = conn.execute(
                """SELECT e.*, d.name as department_name
                   FROM employees e
                   LEFT JOIN departments d ON e.department_id = d.id
                   ORDER BY e.name"""
            ).fetchall()

    return render_template('employees/list.html', employees=employees, q=q)


@employees_bp.route('/new', methods=['GET', 'POST'])
def new_employee():
    with get_db() as conn:
        if request.method == 'POST':
            name = request.form['name'].strip()
            badge = request.form.get('badge_number', '').strip() or None
            email = request.form.get('email', '').strip() or None
            phone = request.form.get('phone', '').strip() or None
            role = request.form.get('role', 'employee')
            dept_id = request.form.get('department_id', type=int) or None
            dept_new = request.form.get('department_new', '').strip()

            if not name:
                flash('Name is required.', 'error')
                return redirect(url_for('employees.new_employee'))

            # Create new department if specified
            if dept_new and not dept_id:
                conn.execute("INSERT OR IGNORE INTO departments (name) VALUES (?)",
                             (dept_new,))
                dept_id = conn.execute(
                    "SELECT id FROM departments WHERE name = ?", (dept_new,)
                ).fetchone()['id']

            # Check for duplicate badge
            if badge:
                existing = conn.execute(
                    "SELECT id FROM employees WHERE badge_number = ?", (badge,)
                ).fetchone()
                if existing:
                    flash(f'Badge number {badge} already exists.', 'error')
                    return redirect(url_for('employees.new_employee'))

            cur = conn.execute("""
                INSERT INTO employees (name, badge_number, email, phone, role, department_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, badge, email, phone, role, dept_id))
            log_audit(conn, 'employees', cur.lastrowid, 'create')
            flash(f'Employee {name} added.', 'success')
            return redirect(url_for('employees.list_employees'))

        departments = conn.execute(
            "SELECT id, name FROM departments ORDER BY name"
        ).fetchall()

    return render_template('employees/new.html', departments=departments)


@employees_bp.route('/<int:emp_id>/edit', methods=['GET', 'POST'])
def edit_employee(emp_id):
    with get_db() as conn:
        emp = conn.execute("SELECT * FROM employees WHERE id = ?", (emp_id,)).fetchone()
        if not emp:
            flash('Employee not found.', 'error')
            return redirect(url_for('employees.list_employees'))

        if request.method == 'POST':
            name = request.form['name'].strip()
            badge = request.form.get('badge_number', '').strip() or None
            email = request.form.get('email', '').strip() or None
            phone = request.form.get('phone', '').strip() or None
            role = request.form.get('role', 'employee')
            dept_id = request.form.get('department_id', type=int) or None
            dept_new = request.form.get('department_new', '').strip()
            is_active = 1 if request.form.get('is_active') else 0

            if dept_new and not dept_id:
                conn.execute("INSERT OR IGNORE INTO departments (name) VALUES (?)",
                             (dept_new,))
                dept_id = conn.execute(
                    "SELECT id FROM departments WHERE name = ?", (dept_new,)
                ).fetchone()['id']

            # Check badge uniqueness (excluding self)
            if badge:
                existing = conn.execute(
                    "SELECT id FROM employees WHERE badge_number = ? AND id != ?",
                    (badge, emp_id)
                ).fetchone()
                if existing:
                    flash(f'Badge number {badge} already in use.', 'error')
                    return redirect(url_for('employees.edit_employee', emp_id=emp_id))

            conn.execute("""
                UPDATE employees
                SET name=?, badge_number=?, email=?, phone=?, role=?,
                    department_id=?, is_active=?
                WHERE id=?
            """, (name, badge, email, phone, role, dept_id, is_active, emp_id))
            log_audit(conn, 'employees', emp_id, 'update')
            flash('Employee updated.', 'success')
            return redirect(url_for('employees.list_employees'))

        departments = conn.execute(
            "SELECT id, name FROM departments ORDER BY name"
        ).fetchall()

    return render_template('employees/edit.html', emp=emp, departments=departments)
