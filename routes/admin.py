# ============================================
# RESIFIX — ADMIN ROUTES
# routes/admin.py
# ============================================

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.db import (
    get_all_users,
    get_all_requests,
    get_request_by_id,
    get_user_by_id,
    assign_technician,
    update_request_status,
    set_user_active,
    add_comment,
    get_comments_by_request,
    get_available_technicians_for_request,
    get_all_residences,
    add_residence,
    set_residence_active
)
from functools import wraps
import math

admin    = Blueprint('admin', __name__)
PER_PAGE = 10


# ── Access control ─────────────────────────────────────────────────────────

def admin_required(f):
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


# ── Dashboard ──────────────────────────────────────────────────────────────

@admin.route('/admin')
@admin_required
def admin_dashboard():
    all_requests = get_all_requests()
    all_users    = get_all_users()

    status_filter   = request.args.get('status',   '').strip()
    priority_filter = request.args.get('priority', '').strip()
    residence_filter= request.args.get('residence','').strip()
    room_search     = request.args.get('room',     '').strip().lower()
    page            = max(1, int(request.args.get('page', 1) or 1))

    filtered = all_requests
    if status_filter:
        filtered = [r for r in filtered if r['status'] == status_filter]
    if priority_filter:
        filtered = [r for r in filtered if r['priority'] == priority_filter]
    if residence_filter:
        filtered = [r for r in filtered if r['residence'] == residence_filter]
    if room_search:
        filtered = [r for r in filtered if r['room_number'] and room_search in r['room_number'].lower()]

    total_results = len(filtered)
    total_pages   = max(1, math.ceil(total_results / PER_PAGE))
    page          = min(page, total_pages)
    paginated     = filtered[(page-1)*PER_PAGE : page*PER_PAGE]

    stats = {
        'total':       len(all_requests),
        'pending':     sum(1 for r in all_requests if r['status'] == 'pending'),
        'in_progress': sum(1 for r in all_requests if r['status'] == 'in_progress'),
        'resolved':    sum(1 for r in all_requests if r['status'] == 'resolved'),
        'critical':    sum(1 for r in all_requests if r['priority'] == 'critical'),
        'worsening':   sum(1 for r in all_requests if r['is_worsening']),
        'total_users': len(all_users),
    }

    user_map   = {u['id']: u for u in all_users}
    residences = get_all_residences()

    return render_template('admin/dashboard.html',
        requests         = paginated,
        stats            = stats,
        user_map         = user_map,
        residences       = residences,
        status_filter    = status_filter,
        priority_filter  = priority_filter,
        residence_filter = residence_filter,
        room_search      = room_search,
        page             = page,
        total_pages      = total_pages,
        total_results    = total_results,
    )


# ── Request Detail ─────────────────────────────────────────────────────────

@admin.route('/admin/request/<int:request_id>', methods=['GET', 'POST'])
@admin_required
def request_detail(request_id):
    req       = get_request_by_id(request_id)
    all_users = get_all_users()
    user_map  = {u['id']: u for u in all_users}

    if not req:
        flash('Request not found.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))

    # ── Filtered technicians — same residence + matching specialization ──
    technicians = get_available_technicians_for_request(
        residence = req['residence'] or '',
        category  = req['category']  or ''
    )

    comments = get_comments_by_request(request_id, include_internal=True)

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'assign':
            tech_id = request.form.get('technician_id')
            if not tech_id:
                flash('Please select a technician.', 'warning')
            else:
                assign_technician(request_id, int(tech_id))
                flash('Technician assigned successfully.', 'success')
            return redirect(url_for('admin.request_detail', request_id=request_id))

        if action == 'update_status':
            new_status = request.form.get('status')
            if new_status not in ['pending','assigned','in_progress','resolved','closed','cancelled']:
                flash('Invalid status.', 'danger')
            else:
                update_request_status(request_id, new_status)
                flash(f'Status updated to "{new_status}".', 'success')
            return redirect(url_for('admin.request_detail', request_id=request_id))

        if action == 'add_note':
            body = request.form.get('note_body', '').strip()
            if not body:
                flash('Note cannot be empty.', 'warning')
            else:
                add_comment(request_id, session['user_id'], body, is_internal=True)
                flash('Internal note added.', 'success')
            return redirect(url_for('admin.request_detail', request_id=request_id))

    return render_template('admin/request_detail.html',
        req         = req,
        technicians = technicians,
        user_map    = user_map,
        comments    = comments,
    )


# ── Manage Users ───────────────────────────────────────────────────────────

@admin.route('/admin/users')
@admin_required
def manage_users():
    all_users   = get_all_users()
    role_filter = request.args.get('role',   '').strip()
    search      = request.args.get('search', '').strip().lower()
    page        = max(1, int(request.args.get('page', 1) or 1))

    counts = {
        'all':        len(all_users),
        'resident':   sum(1 for u in all_users if u['role'] == 'resident'),
        'technician': sum(1 for u in all_users if u['role'] == 'technician'),
        'admin':      sum(1 for u in all_users if u['role'] == 'admin'),
    }

    filtered = all_users
    if role_filter:
        filtered = [u for u in filtered if u['role'] == role_filter]
    if search:
        filtered = [u for u in filtered if search in u['username'].lower() or search in u['email'].lower()]

    total_results = len(filtered)
    total_pages   = max(1, math.ceil(total_results / PER_PAGE))
    page          = min(page, total_pages)
    paginated     = filtered[(page-1)*PER_PAGE : page*PER_PAGE]

    return render_template('admin/manage_users.html',
        users         = paginated,
        counts        = counts,
        role_filter   = role_filter,
        search        = search,
        page          = page,
        total_pages   = total_pages,
        total_results = total_results,
    )


# ── Toggle User Active ─────────────────────────────────────────────────────

@admin.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@admin_required
def toggle_user(user_id):
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


# ── Manage Residences ──────────────────────────────────────────────────────

@admin.route('/admin/residences', methods=['GET', 'POST'])
@admin_required
def manage_residences():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Residence name cannot be empty.', 'warning')
        else:
            success = add_residence(name)
            if success:
                flash(f'"{name}" added successfully.', 'success')
            else:
                flash(f'"{name}" already exists.', 'warning')
        return redirect(url_for('admin.manage_residences'))

    residences = get_all_residences()
    return render_template('admin/manage_residences.html', residences=residences)


# ── Toggle Residence Active ────────────────────────────────────────────────

@admin.route('/admin/residences/<int:residence_id>/toggle', methods=['POST'])
@admin_required
def toggle_residence(residence_id):
    from database.db import get_connection
    conn = get_connection()
    res  = conn.execute("SELECT * FROM residences WHERE id = ?", (residence_id,)).fetchone()
    conn.close()

    if not res:
        flash('Residence not found.', 'danger')
        return redirect(url_for('admin.manage_residences'))

    new_state = 0 if res['is_active'] else 1
    set_residence_active(residence_id, new_state)
    action = 'activated' if new_state else 'deactivated'
    flash(f'"{res["name"]}" has been {action}.', 'success')
    return redirect(url_for('admin.manage_residences'))
