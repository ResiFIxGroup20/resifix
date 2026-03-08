from flask import Blueprint

admin = Blueprint('admin', __name__)

@admin.route('/admin')
def admin_dashboard():
    return 'Admin dashboard - coming soon'

@admin.route('/admin/users')
def manage_users():
    return 'Manage users - coming soon'
