from flask import Blueprint, render_template, redirect, url_for, session, flash, request
from database.db import (
    get_requests_by_technician,
    get_request_by_id,
    get_user_by_id,
    get_comments_by_request,
    update_request_status,
    add_comment,
    create_notification,
    get_ratings_by_technician,
    get_average_rating,
    get_images_by_request,
)

technician = Blueprint('technician', __name__)


# --- Auth guard helper ---

def technician_required():
    """Return a redirect if the user is not a logged-in technician, else None."""
    if not session.get('user_id'):
        flash('Please log in to continue.', 'warning')
        return redirect(url_for('auth.login'))
    if session.get('role') != 'technician':
        flash('Access denied — technicians only.', 'error')
        return redirect(url_for('auth.login'))
    return None  # all good


# --- Status badge helper (passed to templates via context) ---

STATUS_ORDER = ['pending', 'assigned', 'in_progress', 'resolved', 'closed', 'cancelled']

# Statuses a technician is allowed to transition TO from a given current status
ALLOWED_TRANSITIONS = {
    'assigned':    ['in_progress', 'cancelled'],
    'in_progress': ['resolved',    'cancelled'],
    # technician cannot re-open resolved/closed/cancelled tickets
    'resolved':    [],
    'closed':      [],
    'cancelled':   [],
    'pending':     [],  # pending tickets must be assigned by admin first
}


# ─────────────────────────────────────────────
#  Dashboard  —  /technician
# ─────────────────────────────────────────────

@technician.route('/technician')
def technician_dashboard():
    """Main technician dashboard: shows all jobs assigned to this technician."""

    guard = technician_required()
    if guard:
        return guard

    tech_id = session['user_id']

    # Fetch all requests for this technician (ordered by submitted_at DESC in db)
    all_requests = get_requests_by_technician(tech_id)

    # Optional status filter via query param e.g. ?status=in_progress
    status_filter = request.args.get('status', '').strip().lower()
    valid_statuses = ['pending', 'assigned', 'in_progress', 'resolved', 'closed', 'cancelled']

    if status_filter and status_filter in valid_statuses:
        filtered = [r for r in all_requests if r['status'] == status_filter]
    else:
        status_filter = ''  # clear invalid values
        filtered = all_requests

    # Build summary counts for the stat cards
    counts = {s: 0 for s in valid_statuses}
    for r in all_requests:
        if r['status'] in counts:
            counts[r['status']] += 1

    # Rating summary for the sidebar card
    avg_rating  = get_average_rating(tech_id)
    all_ratings = get_ratings_by_technician(tech_id)

    return render_template(
        'technician/dashboard.html',
        requests=filtered,
        counts=counts,
        total=len(all_requests),
        status_filter=status_filter,
        avg_rating=avg_rating,
        rating_count=len(all_ratings),
    )


# ─────────────────────────────────────────────
#  Job Detail  —  /technician/job/<id>
# ─────────────────────────────────────────────

@technician.route('/technician/job/<int:request_id>')
def job_detail(request_id):
    """Full detail view for a single maintenance request."""

    guard = technician_required()
    if guard:
        return guard

    tech_id = session['user_id']

    # Fetch the request and verify it belongs to this technician
    job = get_request_by_id(request_id)
    if not job or job['technician_id'] != tech_id:
        flash('Job not found or not assigned to you.', 'error')
        return redirect(url_for('technician.technician_dashboard'))

    # Resident info for display
    resident = get_user_by_id(job['resident_id'])

    # Include internal notes for technicians (include_internal=True)
    comments = get_comments_by_request(request_id, include_internal=True)

    # Fetch author info for each comment so template can show names
    comments_with_authors = []
    for c in comments:
        author = get_user_by_id(c['author_id'])
        comments_with_authors.append({'comment': c, 'author': author})

    # Images attached to this request
    images = get_images_by_request(request_id)

    # What status transitions are allowed from the current status
    allowed_next = ALLOWED_TRANSITIONS.get(job['status'], [])

    return render_template(
        'technician/job_detail.html',
        job=job,
        resident=resident,
        comments=comments_with_authors,
        images=images,
        allowed_next=allowed_next,
        status_order=STATUS_ORDER,
    )


# ─────────────────────────────────────────────
#  Update Status  —  POST /technician/job/<id>/status
# ─────────────────────────────────────────────

@technician.route('/technician/job/<int:request_id>/status', methods=['POST'])
def update_status(request_id):
    """Handle status change form submission from the job detail page."""

    guard = technician_required()
    if guard:
        return guard

    tech_id = session['user_id']

    # Verify ownership
    job = get_request_by_id(request_id)
    if not job or job['technician_id'] != tech_id:
        flash('Job not found or not assigned to you.', 'error')
        return redirect(url_for('technician.technician_dashboard'))

    new_status = request.form.get('status', '').strip().lower()
    allowed_next = ALLOWED_TRANSITIONS.get(job['status'], [])

    # Validate the requested transition
    if new_status not in allowed_next:
        flash(f'Cannot change status from "{job["status"]}" to "{new_status}".', 'error')
        return redirect(url_for('technician.job_detail', request_id=request_id))

    # Persist the status change
    update_request_status(request_id, new_status)

    # Notify the resident about the status update
    status_labels = {
        'in_progress': 'is now in progress',
        'resolved':    'has been resolved',
        'cancelled':   'has been cancelled',
    }
    label = status_labels.get(new_status, f'status changed to {new_status}')
    create_notification(
        user_id=job['resident_id'],
        message=f'Your request "{job["title"]}" ({job["ticket_no"]}) {label}.',
        request_id=request_id,
        type='in_app',
    )

    flash(f'Status updated to "{new_status}".', 'success')
    return redirect(url_for('technician.job_detail', request_id=request_id))


# ─────────────────────────────────────────────
#  Add Comment / Internal Note  —  POST /technician/job/<id>/comment
# ─────────────────────────────────────────────

@technician.route('/technician/job/<int:request_id>/comment', methods=['POST'])
def add_job_comment(request_id):
    """Submit a comment or internal note on a job."""

    guard = technician_required()
    if guard:
        return guard

    tech_id = session['user_id']

    # Verify ownership
    job = get_request_by_id(request_id)
    if not job or job['technician_id'] != tech_id:
        flash('Job not found or not assigned to you.', 'error')
        return redirect(url_for('technician.technician_dashboard'))

    body = request.form.get('body', '').strip()
    if not body:
        flash('Comment cannot be empty.', 'warning')
        return redirect(url_for('technician.job_detail', request_id=request_id))

    # is_internal checkbox — technicians can post internal notes
    is_internal = bool(request.form.get('is_internal'))

    add_comment(request_id, tech_id, body, is_internal=is_internal)

    # Notify resident only for public (non-internal) comments
    if not is_internal:
        create_notification(
            user_id=job['resident_id'],
            message=f'A technician left an update on your request "{job["title"]}" ({job["ticket_no"]}).',
            request_id=request_id,
            type='in_app',
        )

    flash('Note added.', 'success')
    return redirect(url_for('technician.job_detail', request_id=request_id))
