

import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
from database.db import (
    get_requests_by_resident,
    get_request_by_id,
    create_request,
    get_comments_by_request,
    add_comment,
    get_images_by_request,
    get_user_by_id,
    save_image
)

resident = Blueprint('resident', __name__)

UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('auth.login'))
        if session.get('role') != 'resident':
            flash('Access denied.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# DASHBOARD

@resident.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    requests_list = get_requests_by_resident(user_id)

    # Build stats
    stats = {
        'total': len(requests_list),
        'pending': sum(1 for r in requests_list if r['status'] == 'pending'),
        'assigned': sum(1 for r in requests_list if r['status'] == 'assigned'),
        'in_progress': sum(1 for r in requests_list if r['status'] == 'in_progress'),
        'resolved': sum(1 for r in requests_list if r['status'] == 'resolved'),
    }

    return render_template('resident/dashboard.html', requests=requests_list, stats=stats)


# NEW REQUEST

@resident.route('/request/new', methods=['GET', 'POST'])
@login_required
def new_request():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        category = request.form.get('category', '').strip()
        priority = request.form.get('priority', 'low').strip()
        description = request.form.get('description', '').strip()
        room_number = session.get('room_number', '')

        # Basic validation
        if not title or not category or not description:
            flash('Please fill in all required fields.', 'danger')
            return render_template('resident/new_request.html')

        # Create the request
        ticket_no = create_request(
            resident_id=session['user_id'],
            room_number=room_number,
            category=category,
            priority=priority,
            title=title,
            description=description
        )

        # Handle image uploads
        if 'images' in request.files:
            files = request.files.getlist('images')
            for file in files:
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                    file_path = os.path.join(UPLOAD_FOLDER, filename)
                    file.save(file_path)
                    # Get the request id from ticket_no
                    from database.db import get_connection
                    conn = get_connection()
                    row = conn.execute(
                        "SELECT id FROM maintenance_requests WHERE ticket_no = ?", (ticket_no,)
                    ).fetchone()
                    conn.close()
                    if row:
                        save_image(row['id'], os.path.join('uploads', filename))

        flash(f'Request {ticket_no} submitted successfully!', 'success')
        return redirect(url_for('resident.dashboard'))

    return render_template('resident/new_request.html')


# VIEW REQUEST

@resident.route('/request/<int:request_id>')
@login_required
def view_request(request_id):
    req = get_request_by_id(request_id)

    # Make sure resident can only view their own requests
    if not req or req['resident_id'] != session['user_id']:
        flash('Request not found.', 'danger')
        return redirect(url_for('resident.dashboard'))

    # Get technician info if assigned
    technician = None
    if req['technician_id']:
        technician = get_user_by_id(req['technician_id'])

    # Get comments with author names
    raw_comments = get_comments_by_request(request_id, include_internal=False)
    comments = []
    for c in raw_comments:
        author = get_user_by_id(c['author_id'])
        comments.append({
            'author_name': author['full_name'] if author else 'Unknown',
            'role': author['role'] if author else '',
            'body': c['body'],
            'created_at': c['created_at'],
        })

    # Build progress timeline
    timeline = [
        {'title': 'Request Submitted', 'done': True, 'date': req['submitted_at']},
        {'title': 'Technician Assigned', 'done': req['technician_id'] is not None, 'date': req['updated_at'] if req['technician_id'] else None},
        {'title': 'In Progress', 'done': req['status'] in ('in_progress', 'resolved'), 'date': req['updated_at'] if req['status'] in ('in_progress', 'resolved') else None},
        {'title': 'Resolved', 'done': req['status'] == 'resolved', 'date': req['resolved_at']},
    ]

    images = get_images_by_request(request_id)

    return render_template('resident/view_request.html',
                           request=req,
                           technician=technician,
                           comments=comments,
                           timeline=timeline,
                           images=images)


# ADD COMMENT

@resident.route('/request/<int:request_id>/comment', methods=['POST'])
@login_required
def add_request_comment(request_id):
    req = get_request_by_id(request_id)

    if not req or req['resident_id'] != session['user_id']:
        flash('Request not found.', 'danger')
        return redirect(url_for('resident.dashboard'))

    comment_body = request.form.get('comment', '').strip()
    if comment_body:
        add_comment(request_id, session['user_id'], comment_body, is_internal=False)
        flash('Comment added.', 'success')
    else:
        flash('Comment cannot be empty.', 'warning')

    return redirect(url_for('resident.view_request', request_id=request_id))


# NOTIFICATIONS

@resident.route('/notifications')
@login_required
def notifications():
    return 'Notifications - coming soon'
