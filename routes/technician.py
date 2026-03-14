# Handles: technician dashboard (task list) and task detail (status updates + notes)

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.db import (
    get_requests_by_technician,
    get_request_by_id,
    get_all_users,
    update_request_status,
    add_comment,
    get_comments_by_request,
    get_images_by_request,
    get_average_rating,
    get_ratings_by_technician,
)
from functools import wraps
import math

technician = Blueprint('technician', __name__)

PER_PAGE = 10


#  Access-control decorator 

def technician_required(f):
    """Redirect non-technicians away from technician pages."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('auth.login'))
        if session.get('role') != 'technician':
            flash('Access denied. Technicians only.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


#  Dashboard

@technician.route('/technician')
@technician_required
def technician_dashboard():
    """Technician task list — filtered by status, sorted, paginated."""

    tech_id   = session['user_id']
    all_tasks = get_requests_by_technician(tech_id)
    all_users = get_all_users()
    user_map  = {u['id']: u for u in all_users}

    # Filters
    status_filter = request.args.get('status', '').strip()
    page          = max(1, int(request.args.get('page', 1) or 1))

    filtered = all_tasks
    if status_filter:
        filtered = [t for t in filtered if t['status'] == status_filter]

    # Stats (always on all tasks for this technician)
    stats = {
        'total':       len(all_tasks),
        'assigned':    sum(1 for t in all_tasks if t['status'] == 'assigned'),
        'in_progress': sum(1 for t in all_tasks if t['status'] == 'in_progress'),
        'resolved':    sum(1 for t in all_tasks if t['status'] == 'resolved'),
        'critical':    sum(1 for t in all_tasks if t['priority'] == 'critical'),
    }

    # Rating summary
    avg_rating    = get_average_rating(tech_id)
    ratings       = get_ratings_by_technician(tech_id)
    total_ratings = len(ratings)

    # Pagination
    total_results = len(filtered)
    total_pages   = max(1, math.ceil(total_results / PER_PAGE))
    page          = min(page, total_pages)
    offset        = (page - 1) * PER_PAGE
    paginated     = filtered[offset: offset + PER_PAGE]

    return render_template(
        'technician/dashboard.html',
        tasks=paginated,
        stats=stats,
        user_map=user_map,
        status_filter=status_filter,
        page=page,
        total_pages=total_pages,
        total_results=total_results,
        avg_rating=avg_rating,
        total_ratings=total_ratings,
    )


# Task Detail 

@technician.route('/technician/task/<int:request_id>', methods=['GET', 'POST'])
@technician_required
def task_detail(request_id):
    """View a single assigned task; update status or add a work note."""

    tech_id = session['user_id']
    task    = get_request_by_id(request_id)

    if not task:
        flash('Task not found.', 'danger')
        return redirect(url_for('technician.technician_dashboard'))

    # Technicians may only view tasks assigned to them
    if task['technician_id'] != tech_id:
        flash('You are not assigned to this task.', 'warning')
        return redirect(url_for('technician.technician_dashboard'))

    all_users = get_all_users()
    user_map  = {u['id']: u for u in all_users}

    # Fetch comments (include internal so technician can see their own notes)
    comments = get_comments_by_request(request_id, include_internal=True)
    images   = get_images_by_request(request_id)

    if request.method == 'POST':
        action = request.form.get('action')

        # Update status — technicians move between assigned / in_progress / resolved
        if action == 'update_status':
            new_status = request.form.get('status')
            allowed    = ['assigned', 'in_progress', 'resolved']
            if new_status not in allowed:
                flash('Invalid status selection.', 'danger')
            else:
                update_request_status(request_id, new_status)
                flash(f'Status updated to "{new_status.replace("_", " ").title()}".', 'success')
            return redirect(url_for('technician.task_detail', request_id=request_id))

        # Add a work note (saved as internal comment)
        if action == 'add_note':
            body = request.form.get('note_body', '').strip()
            if not body:
                flash('Note cannot be empty.', 'warning')
            else:
                add_comment(request_id, tech_id, body, is_internal=True)
                flash('Work note added.', 'success')
            return redirect(url_for('technician.task_detail', request_id=request_id))

    return render_template(
        'technician/task_detail.html',
        task=task,
        user_map=user_map,
        comments=comments,
        images=images,
    )