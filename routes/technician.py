# Handles: technician dashboard, task detail, profile

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.db import (
    get_requests_by_technician,
    get_request_by_id,
    get_all_users,
    get_user_by_id,
    update_profile,
    update_request_status,
    add_comment,
    get_comments_by_request,
    get_images_by_request,
    get_average_rating,
    get_ratings_by_technician,
    get_all_residences,
)
from functools import wraps
import math

technician = Blueprint('technician', __name__)
PER_PAGE   = 10


# ── Access control ─────────────────────────────────────────────────────────

def technician_required(f):
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


# ── Dashboard ──────────────────────────────────────────────────────────────

@technician.route('/technician')
@technician_required
def technician_dashboard():
    tech_id   = session['user_id']
    all_tasks = get_requests_by_technician(tech_id)
    all_users = get_all_users()
    user_map  = {u['id']: u for u in all_users}

    status_filter = request.args.get('status', '').strip()
    page          = max(1, int(request.args.get('page', 1) or 1))

    filtered = all_tasks
    if status_filter:
        filtered = [t for t in filtered if t['status'] == status_filter]

    stats = {
        'total':       len(all_tasks),
        'assigned':    sum(1 for t in all_tasks if t['status'] == 'assigned'),
        'in_progress': sum(1 for t in all_tasks if t['status'] == 'in_progress'),
        'resolved':    sum(1 for t in all_tasks if t['status'] == 'resolved'),
        'critical':    sum(1 for t in all_tasks if t['priority'] == 'critical'),
    }

    avg_rating    = get_average_rating(tech_id)
    ratings       = get_ratings_by_technician(tech_id)
    total_ratings = len(ratings)

    total_results = len(filtered)
    total_pages   = max(1, math.ceil(total_results / PER_PAGE))
    page          = min(page, total_pages)
    paginated     = filtered[(page-1)*PER_PAGE : page*PER_PAGE]

    return render_template('technician/dashboard.html',
        tasks=paginated, stats=stats, user_map=user_map,
        status_filter=status_filter, page=page,
        total_pages=total_pages, total_results=total_results,
        avg_rating=avg_rating, total_ratings=total_ratings,
    )


# ── Task Detail ────────────────────────────────────────────────────────────

@technician.route('/technician/task/<int:request_id>', methods=['GET', 'POST'])
@technician_required
def task_detail(request_id):
    tech_id = session['user_id']
    task    = get_request_by_id(request_id)

    if not task:
        flash('Task not found.', 'danger')
        return redirect(url_for('technician.technician_dashboard'))

    if task['technician_id'] != tech_id:
        flash('You are not assigned to this task.', 'warning')
        return redirect(url_for('technician.technician_dashboard'))

    all_users = get_all_users()
    user_map  = {u['id']: u for u in all_users}
    comments  = get_comments_by_request(request_id, include_internal=True)
    images    = get_images_by_request(request_id)

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_status':
            new_status = request.form.get('status')
            if new_status not in ['assigned', 'in_progress', 'resolved']:
                flash('Invalid status selection.', 'danger')
            else:
                update_request_status(request_id, new_status)
                flash(f'Status updated to "{new_status.replace("_"," ").title()}".', 'success')
            return redirect(url_for('technician.task_detail', request_id=request_id))

        if action == 'add_note':
            body = request.form.get('note_body', '').strip()
            if not body:
                flash('Note cannot be empty.', 'warning')
            else:
                add_comment(request_id, tech_id, body, is_internal=True)
                flash('Work note added.', 'success')
            return redirect(url_for('technician.task_detail', request_id=request_id))

    return render_template('technician/task_detail.html',
                           task=task, user_map=user_map,
                           comments=comments, images=images)


# ── Profile ────────────────────────────────────────────────────────────────

@technician.route('/technician/profile', methods=['GET', 'POST'])
@technician_required
def profile():
    """Technician profile — edit name, email and residence."""
    tech_id    = session['user_id']
    user       = get_user_by_id(tech_id)
    residences = get_all_residences()

    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('technician.technician_dashboard'))

    all_tasks     = get_requests_by_technician(tech_id)
    avg_rating    = get_average_rating(tech_id)
    ratings       = get_ratings_by_technician(tech_id)
    total_ratings = len(ratings)
    stats = {
        'total':       len(all_tasks),
        'in_progress': sum(1 for t in all_tasks if t['status'] == 'in_progress'),
        'resolved':    sum(1 for t in all_tasks if t['status'] == 'resolved'),
    }

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email     = request.form.get('email',     '').strip()
        residence = request.form.get('residence', '').strip()

        if not full_name:
            flash('Full name cannot be empty.', 'danger')
            return redirect(url_for('technician.profile'))
        if not email or '@' not in email:
            flash('Please enter a valid email address.', 'danger')
            return redirect(url_for('technician.profile'))

        update_profile(tech_id, full_name, email, residence=residence)
        session['full_name'] = full_name
        session['residence'] = residence

        flash('Profile updated successfully.', 'success')
        return redirect(url_for('technician.profile'))

    return render_template('technician/profile.html',
                           user=user, stats=stats,
                           avg_rating=avg_rating, total_ratings=total_ratings,
                           residences=residences)