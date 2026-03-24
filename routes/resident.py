# ============================================================
# RESIFIX — RESIDENT ROUTES v2.1
# routes/resident.py
# ============================================================

import os
import uuid
import requests as http_requests
from dotenv import load_dotenv
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session, jsonify, current_app)
from werkzeug.utils import secure_filename
from database.db import (
    get_requests_by_resident,
    get_request_by_id,
    create_request,
    get_comments_by_request,
    add_comment,
    get_images_by_request,
    get_user_by_id,
    save_image,
    get_all_residences,
    update_profile,
    mark_worsening,
)

load_dotenv()

# ── Cloudinary — only configure if all three env vars are present ──────────
_cld_name   = os.getenv('CLOUDINARY_CLOUD_NAME')
_cld_key    = os.getenv('CLOUDINARY_API_KEY')
_cld_secret = os.getenv('CLOUDINARY_API_SECRET')
CLOUDINARY_CONFIGURED = bool(_cld_name and _cld_key and _cld_secret)

if CLOUDINARY_CONFIGURED:
    import cloudinary
    import cloudinary.uploader
    cloudinary.config(
        cloud_name = _cld_name,
        api_key    = _cld_key,
        api_secret = _cld_secret,
    )

resident = Blueprint('resident', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


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


def _save_image_file(file):
    """
    Upload to Cloudinary if configured, otherwise save to static/uploads/ locally.
    Returns the URL/path string to store in the DB.
    """
    if CLOUDINARY_CONFIGURED:
        result = cloudinary.uploader.upload(
            file,
            folder='resifix/requests',
            resource_type='image',
        )
        return result.get('secure_url')
    else:
        filename = secure_filename(file.filename)
        unique   = f"{uuid.uuid4().hex}_{filename}"
        save_dir = os.path.join(current_app.root_path, 'static', 'uploads')
        os.makedirs(save_dir, exist_ok=True)
        file.save(os.path.join(save_dir, unique))
        return f"uploads/{unique}"


# ── DASHBOARD ─────────────────────────────────────────────────────────────

@resident.route('/dashboard')
@login_required
def dashboard():
    user_id       = session['user_id']
    requests_list = get_requests_by_resident(user_id)
    stats = {
        'total':       len(requests_list),
        'pending':     sum(1 for r in requests_list if r['status'] == 'pending'),
        'assigned':    sum(1 for r in requests_list if r['status'] == 'assigned'),
        'in_progress': sum(1 for r in requests_list if r['status'] == 'in_progress'),
        'resolved':    sum(1 for r in requests_list if r['status'] == 'resolved'),
    }
    groq_enabled = bool(os.getenv('GROQ_API_KEY'))
    return render_template('resident/dashboard.html',
                           requests=requests_list,
                           stats=stats,
                           groq_enabled=groq_enabled)


# ── NEW REQUEST ────────────────────────────────────────────────────────────

@resident.route('/request/new', methods=['GET', 'POST'])
@login_required
def new_request():
    if request.method == 'POST':
        title       = request.form.get('title',       '').strip()
        category    = request.form.get('category',    '').strip()
        priority    = request.form.get('priority',    'low').strip()
        description = request.form.get('description', '').strip()
        room_number = session.get('room_number', '')
        residence   = session.get('residence',   '')

        if not title or not category or not description:
            flash('Please fill in all required fields.', 'danger')
            return render_template('resident/new_request.html')

        ticket_no = create_request(
            resident_id = session['user_id'],
            room_number = room_number,
            category    = category,
            priority    = priority,
            title       = title,
            description = description,
            residence   = residence,
        )

        # ── Image uploads (Cloudinary or local fallback) ───────────────────
        if 'images' in request.files:
            for file in request.files.getlist('images'):
                if not file or not file.filename:
                    continue
                if not allowed_file(file.filename):
                    continue
                try:
                    image_url = _save_image_file(file)
                    from database.db import get_request_id_by_ticket
                    row = get_request_id_by_ticket(ticket_no)
                    if row:
                        save_image(row['id'], image_url)
                except Exception as e:
                    flash(f'One image could not be uploaded and was skipped: {e}', 'warning')

        flash(f'Request {ticket_no} submitted successfully!', 'success')
        return redirect(url_for('resident.dashboard'))

    return render_template('resident/new_request.html')


# ── VIEW REQUEST ───────────────────────────────────────────────────────────

@resident.route('/request/<int:request_id>')
@login_required
def view_request(request_id):
    req = get_request_by_id(request_id)

    if not req or req['resident_id'] != session['user_id']:
        flash('Request not found.', 'danger')
        return redirect(url_for('resident.dashboard'))

    technician = None
    if req['technician_id']:
        technician = get_user_by_id(req['technician_id'])

    raw_comments = get_comments_by_request(request_id, include_internal=False)
    comments = []
    for c in raw_comments:
        author = get_user_by_id(c['author_id'])
        comments.append({
            'author_name': author['full_name'] if author else 'Unknown',
            'role':        author['role']      if author else '',
            'body':        c['body'],
            'created_at':  c['created_at'],
        })

    raw_direct = get_comments_by_request(request_id, direct_only=True)
    direct_messages = []
    for c in raw_direct:
        author = get_user_by_id(c['author_id'])
        direct_messages.append({
            'author_name': author['full_name'] if author else 'Unknown',
            'role':        author['role']      if author else '',
            'body':        c['body'],
            'created_at':  c['created_at'],
            'is_mine':     c['author_id'] == session['user_id'],
        })

    timeline = [
        {'title': 'Request Submitted',   'done': True,
         'date': req['submitted_at']},
        {'title': 'Technician Assigned', 'done': req['technician_id'] is not None,
         'date': req['updated_at'] if req['technician_id'] else None},
        {'title': 'In Progress',         'done': req['status'] in ('in_progress', 'resolved'),
         'date': req['updated_at'] if req['status'] in ('in_progress', 'resolved') else None},
        {'title': 'Resolved',            'done': req['status'] == 'resolved',
         'date': req['resolved_at']},
    ]

    images = get_images_by_request(request_id)

    from database.db import get_existing_rating
    existing_rating = get_existing_rating(request_id, session['user_id'])

    return render_template('resident/view_request.html',
                           request=req,
                           technician=technician,
                           comments=comments,
                           direct_messages=direct_messages,
                           timeline=timeline,
                           images=images,
                           existing_rating=existing_rating)


# ── ADD COMMENT (public channel) ───────────────────────────────────────────

@resident.route('/request/<int:request_id>/comment', methods=['POST'])
@login_required
def add_request_comment(request_id):
    req = get_request_by_id(request_id)
    if not req or req['resident_id'] != session['user_id']:
        flash('Request not found.', 'danger')
        return redirect(url_for('resident.dashboard'))

    body = request.form.get('comment', '').strip()
    if body:
        add_comment(request_id, session['user_id'], body, is_internal=0)
        flash('Comment added.', 'success')
    else:
        flash('Comment cannot be empty.', 'warning')
    return redirect(url_for('resident.view_request', request_id=request_id))


# ── DIRECT MESSAGE TECHNICIAN (is_internal=2) ─────────────────────────────

@resident.route('/request/<int:request_id>/direct', methods=['POST'])
@login_required
def direct_message_technician(request_id):
    req = get_request_by_id(request_id)
    if not req or req['resident_id'] != session['user_id']:
        flash('Request not found.', 'danger')
        return redirect(url_for('resident.dashboard'))
    if not req['technician_id']:
        flash('No technician has been assigned yet.', 'warning')
        return redirect(url_for('resident.view_request', request_id=request_id))

    body = request.form.get('direct_message', '').strip()
    if body:
        add_comment(request_id, session['user_id'], body, is_internal=2)
        flash('Message sent to technician.', 'success')
    else:
        flash('Message cannot be empty.', 'warning')
    return redirect(url_for('resident.view_request', request_id=request_id))


# ── TOGGLE WORSENING FLAG ──────────────────────────────────────────────────

@resident.route('/request/<int:request_id>/worsening', methods=['POST'])
@login_required
def toggle_worsening(request_id):
    req = get_request_by_id(request_id)
    if not req or req['resident_id'] != session['user_id']:
        flash('Request not found.', 'danger')
        return redirect(url_for('resident.dashboard'))
    if req['status'] in ('resolved', 'closed', 'cancelled'):
        flash('Cannot flag a resolved or closed request.', 'warning')
        return redirect(url_for('resident.view_request', request_id=request_id))

    new_val = 0 if req['is_worsening'] else 1
    mark_worsening(request_id, new_val)
    if new_val:
        flash('Issue flagged as worsening. The admin will be notified.', 'warning')
    else:
        flash('Worsening flag removed.', 'info')
    return redirect(url_for('resident.view_request', request_id=request_id))


# ── PROFILE ────────────────────────────────────────────────────────────────

@resident.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user_id    = session['user_id']
    user       = get_user_by_id(user_id)
    residences = get_all_residences()

    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('resident.dashboard'))

    all_requests = get_requests_by_resident(user_id)
    stats = {
        'total':       len(all_requests),
        'pending':     sum(1 for r in all_requests if r['status'] == 'pending'),
        'in_progress': sum(1 for r in all_requests if r['status'] in ('assigned', 'in_progress')),
        'resolved':    sum(1 for r in all_requests if r['status'] == 'resolved'),
    }

    if request.method == 'POST':
        full_name   = request.form.get('full_name',   '').strip()
        email       = request.form.get('email',       '').strip()
        room_number = request.form.get('room_number', '').strip()
        residence   = request.form.get('residence',   '').strip()

        if not full_name:
            flash('Full name cannot be empty.', 'danger')
            return redirect(url_for('resident.profile'))
        if not email or '@' not in email:
            flash('Please enter a valid email address.', 'danger')
            return redirect(url_for('resident.profile'))

        try:
            update_profile(user_id, full_name, email,
                           room_number=room_number, residence=residence)
        except Exception as e:
            if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
                flash('That email address is already in use by another account.', 'danger')
            else:
                flash('An error occurred while saving. Please try again.', 'danger')
            return redirect(url_for('resident.profile'))
        session['full_name']   = full_name
        session['room_number'] = room_number
        session['residence']   = residence
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('resident.profile'))

    return render_template('resident/profile.html',
                           user=user, stats=stats, residences=residences)


# ── RATE REQUEST ───────────────────────────────────────────────────────────

@resident.route('/request/<int:request_id>/rate', methods=['POST'])
@login_required
def rate_request(request_id):
    req = get_request_by_id(request_id)
    if not req or req['resident_id'] != session['user_id']:
        flash('Request not found.', 'danger')
        return redirect(url_for('resident.dashboard'))
    if req['status'] != 'resolved':
        flash('You can only rate resolved requests.', 'warning')
        return redirect(url_for('resident.view_request', request_id=request_id))

    score  = request.form.get('score')
    review = request.form.get('review', '').strip()
    if not score:
        flash('Please select a star rating.', 'warning')
        return redirect(url_for('resident.view_request', request_id=request_id))

    from database.db import create_rating
    create_rating(request_id, session['user_id'], req['technician_id'], int(score), review)
    flash('Thank you for your rating!', 'success')
    return redirect(url_for('resident.view_request', request_id=request_id))


# ── GROQ AI PROXY — keeps API key server-side ──────────────────────────────

_GROQ_SYSTEM = """You are ResiFix Assistant, a helpful AI for university hostel students at DUT (Durban University of Technology) in South Africa.

Your job is to:
1. Help students describe their maintenance issues clearly
2. Suggest simple things they can try themselves first (e.g. reset a trip switch, check if others have the same WiFi issue, tighten a loose fitting)
3. Help them decide what category and priority level to use when submitting a request
4. Guide them on what photos to take to help technicians
5. Reassure them and set realistic expectations

Categories available: Plumbing, Electrical, Furniture, Appliance, Internet/WiFi, Cleaning, Security, Other

Priority levels:
- Low: cosmetic issues, minor inconveniences
- Medium: functional problem but not urgent
- High: affects daily life
- Critical: emergency (flooding, no power, safety risk)

Keep responses short, friendly and practical. Use simple language. You can use emojis. Always end with either a suggestion to submit a request or a self-fix tip."""

@resident.route('/api/groq-chat', methods=['POST'])
@login_required
def groq_chat():
    groq_key = os.getenv('GROQ_API_KEY', '').strip()
    if not groq_key:
        return jsonify({'error': 'AI assistant is not configured on this server.'}), 503

    data     = request.get_json(force=True, silent=True) or {}
    messages = data.get('messages', [])

    try:
        resp = http_requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {groq_key}',
                'Content-Type':  'application/json',
            },
            json={
                'model':       'llama-3.1-8b-instant',
                'max_tokens':  400,
                'temperature': 0.7,
                'messages':    [{'role': 'system', 'content': _GROQ_SYSTEM}] + messages,
            },
            timeout=30,
        )
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 500