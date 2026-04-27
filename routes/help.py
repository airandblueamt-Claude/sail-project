"""Help — in-app guide for admins and employees."""
from flask import Blueprint, render_template, g

help_bp = Blueprint('help', __name__)


@help_bp.route('/')
def guide():
    is_admin = g.user['role'] in ('admin', 'manager', 'technician')
    return render_template('help.html', is_admin=is_admin)
