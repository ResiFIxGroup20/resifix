# Handles: dashboard, user management, request management

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.db import (
    get_all_users,
    get_all_requests,
    get_all_technicians,
    get_request_by_id,
    get_user_by_id,
    assign_technician,
    update_request_status,
    set_user_active,
    add_comment
)
from functools import wraps
import math


admin = Blueprint('admin', __name__)

# How many rows per page
PER_PAGE = 10


#  Access control decorator 

def admin_required(f):
    """Redirect non-admins away from admin pages."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('auth.login'))
        if session.get('role') != 'admin':
            flash('Access denied. Admins only.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


#  Dashboard

@admin.route('/admin')
@admin_required
def admin_dashboard():
    """Main admin dashboard — requests with filters, room search, and pagination."""

    all_requests = get_all_requests()
    all_users    = get_all_users()

    #  Filters 
    status_filter   = request.args.get('status', '').strip()
    priority_filter = request.args.get('priority', '').strip()
    room_search     = request.args.get('room', '').strip().lower()   # room number search
    page            = max(1, int(request.args.get('page', 1) or 1))

    # Apply filters
    filtered = all_requests
    if status_filter:
        filtered = [r for r in filtered if r['status'] == status_filter]
    if priority_filter:
        filtered = [r for r in filtered if r['priority'] == priority_filter]
    if room_search:
        filtered = [r for r in filtered if r['room_number'] and room_search in r['room_number'].lower()]

    #  Pagination 
    total_results = len(filtered)
    total_pages   = max(1, math.ceil(total_results / PER_PAGE))
    page          = min(page, total_pages)   # clamp page to valid range
    offset        = (page - 1) * PER_PAGE
    paginated     = filtered[offset: offset + PER_PAGE]

    # Stats (always on full unfiltered data) 
    stats = {
        'total':       len(all_requests),
        'pending':     sum(1 for r in all_requests if r['status'] == 'pending'),
        'in_progress': sum(1 for r in all_requests if r['status'] == 'in_progress'),
        'resolved':    sum(1 for r in all_requests if r['status'] == 'resolved'),
        'critical':    sum(1 for r in all_requests if r['priority'] == 'critical'),
        'worsening':   sum(1 for r in all_requests if r['is_worsening']),
        'total_users': len(all_users),
    }

    # User lookup for the table
    user_map = {u['id']: u for u in all_users}

    return render_template(
        'admin/dashboard.html',
        requests=paginated,
        stats=stats,
        user_map=user_map,
        status_filter=status_filter,
        priority_filter=priority_filter,
        room_search=room_search,
        page=page,
        total_pages=total_pages,
        total_results=total_results,
    )


#  Request Detail / Assign 

@admin.route('/admin/request/<int:request_id>', methods=['GET', 'POST'])
@admin_required
def request_detail(request_id):
    """View a single request and assign a technician or update its status."""

    req         = get_request_by_id(request_id)
    technicians = get_all_technicians()
    all_users   = get_all_users()
    user_map    = {u['id']: u for u in all_users}

    if not req:
        flash('Request not found.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))

    if request.method == 'POST':
        action = request.form.get('action')

        # Assign a technician
        if action == 'assign':
            tech_id = request.form.get('technician_id')
            if not tech_id:
                flash('Please select a technician.', 'warning')
            else:
                assign_technician(request_id, int(tech_id))
                flash('Technician assigned successfully.', 'success')
            return redirect(url_for('admin.request_detail', request_id=request_id))

        # Update status
        if action == 'update_status':
            new_status = request.form.get('status')
            valid_statuses = ['pending', 'assigned', 'in_progress', 'resolved', 'closed', 'cancelled']
            if new_status not in valid_statuses:
                flash('Invalid status.', 'danger')
            else:
                update_request_status(request_id, new_status)
                flash(f'Status updated to "{new_status}".', 'success')
            return redirect(url_for('admin.request_detail', request_id=request_id))

        # Add an internal note
        if action == 'add_note':
            body = request.form.get('note_body', '').strip()
            if not body:
                flash('Note cannot be empty.', 'warning')
            else:
                add_comment(request_id, session['user_id'], body, is_internal=True)
                flash('Internal note added.', 'success')
            return redirect(url_for('admin.request_detail', request_id=request_id))

    return render_template(
        'admin/request_detail.html',
        req=req,
        technicians=technicians,
        user_map=user_map,
    )


#  Manage Users 

@admin.route('/admin/users')
@admin_required
def manage_users():
    """List all users — filter by role, search by username or email, paginate."""

    all_users   = get_all_users()
    role_filter = request.args.get('role', '').strip()
    search      = request.args.get('search', '').strip().lower()   # username/email search
    page        = max(1, int(request.args.get('page', 1) or 1))

    # Counts on unfiltered data (for the role tabs)
    counts = {
        'all':        len(all_users),
        'resident':   sum(1 for u in all_users if u['role'] == 'resident'),
        'technician': sum(1 for u in all_users if u['role'] == 'technician'),
        'admin':      sum(1 for u in all_users if u['role'] == 'admin'),
    }

    # Apply role filter
    filtered = all_users
    if role_filter:
        filtered = [u for u in filtered if u['role'] == role_filter]

    # Apply username / email search
    if search:
        filtered = [
            u for u in filtered
            if search in u['username'].lower() or search in u['email'].lower()
        ]

    #  Pagination 
    total_results = len(filtered)
    total_pages   = max(1, math.ceil(total_results / PER_PAGE))
    page          = min(page, total_pages)
    offset        = (page - 1) * PER_PAGE
    paginated     = filtered[offset: offset + PER_PAGE]

    return render_template(
        'admin/manage_users.html',
        users=paginated,
        counts=counts,
        role_filter=role_filter,
        search=search,
        page=page,
        total_pages=total_pages,
        total_results=total_results,
    )


#  Toggle User Active 

@admin.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user(user_id):
    """Activate or deactivate a user account."""

    # Prevent admin from deactivating themselves
    if user_id == session['user_id']:
        flash('You cannot deactivate your own account.', 'warning')
        return redirect(url_for('admin.manage_users'))

    user = get_user_by_id(user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('admin.manage_users'))

    new_state = 0 if user['is_active'] else 1
    set_user_active(user_id, new_state)

    action = 'activated' if new_state else 'deactivated'
    flash(f'{user["full_name"]} has been {action}.', 'success')
    return redirect(url_for('admin.manage_users'))
