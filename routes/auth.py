# ============================================================
# RESIFIX — AUTH ROUTES v2.0
# routes/auth.py
# Handles: login, register, logout, forgot password
# ============================================================

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import (
    get_user_by_username,
    get_user_by_email,
    create_user,
    get_all_residences
)

auth = Blueprint('auth', __name__)


# ── LOGIN ──────────────────────────────────────────────────────────────────

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return _redirect_by_role(session.get('role'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Please enter both username and password.', 'warning')
            return render_template('auth/login.html')

        user = get_user_by_username(username)

        if not user:
            flash('Username not found. Please check and try again.', 'danger')
            return render_template('auth/login.html')

        if not user['is_active']:
            flash('Your account has been deactivated. Please contact admin.', 'danger')
            return render_template('auth/login.html')

        if not check_password_hash(user['password'], password):
            flash('Incorrect password. Please try again.', 'danger')
            return render_template('auth/login.html')

        # Save to session
        session['user_id']        = user['id']
        session['username']       = user['username']
        session['full_name']      = user['full_name']
        session['role']           = user['role']
        session['residence']      = user['residence']      # NEW
        session['room_number']    = user['room_number']

        flash(f"Welcome back, {user['full_name'].split()[0]}!", 'success')
        return _redirect_by_role(user['role'])

    return render_template('auth/login.html')


# ── REGISTER ───────────────────────────────────────────────────────────────

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return _redirect_by_role(session.get('role'))

    residences = get_all_residences()  # for the dropdown

    if request.method == 'POST':
        role           = request.form.get('role', '').strip()
        full_name      = request.form.get('full_name', '').strip()
        username       = request.form.get('username', '').strip()
        email          = request.form.get('email', '').strip().lower()
        password       = request.form.get('password', '')
        confirm        = request.form.get('confirm_password', '')
        room_number    = request.form.get('room_number', '').strip()
        residence      = request.form.get('residence', '').strip()      # NEW
        specialization = request.form.get('specialization', '').strip() # NEW (technicians)

        # ── Validation ────────────────────────────────────────────────────

        if role not in ('resident', 'technician'):
            flash('Please select a valid role.', 'danger')
            return render_template('auth/register.html', residences=residences)

        if not full_name or len(full_name) < 2:
            flash('Please enter your full name.', 'danger')
            return render_template('auth/register.html', residences=residences)

        if not username or len(username) < 3:
            flash('Username must be at least 3 characters.', 'danger')
            return render_template('auth/register.html', residences=residences)

        if not email or '@' not in email:
            flash('Please enter a valid email address.', 'danger')
            return render_template('auth/register.html', residences=residences)

        if not residence:
            flash('Please select your residence building.', 'danger')
            return render_template('auth/register.html', residences=residences)

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('auth/register.html', residences=residences)

        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html', residences=residences)

        # Students must provide room number
        if role == 'resident' and not room_number:
            flash('Room number is required for students.', 'danger')
            return render_template('auth/register.html', residences=residences)

        # Technicians must provide specialization
        if role == 'technician' and not specialization:
            flash('Please select your specialization.', 'danger')
            return render_template('auth/register.html', residences=residences)

        if get_user_by_username(username):
            flash('That username is already taken.', 'danger')
            return render_template('auth/register.html', residences=residences)

        if get_user_by_email(email):
            flash('An account with that email already exists.', 'danger')
            return render_template('auth/register.html', residences=residences)

        # ── Create account ─────────────────────────────────────────────────

        hashed = generate_password_hash(password)

        # Technicians don't have room numbers
        if role == 'technician':
            room_number    = None
            # specialization already set

        success = create_user(
            username       = username,
            email          = email,
            password       = hashed,
            full_name      = full_name,
            room_number    = room_number,
            role           = role,
            residence      = residence,
            specialization = specialization if role == 'technician' else None
        )

        if success:
            flash('Account created successfully! You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Something went wrong. Please try again.', 'danger')
            return render_template('auth/register.html', residences=residences)

    return render_template('auth/register.html', residences=residences)


# ── FORGOT PASSWORD ────────────────────────────────────────────────────────

@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email or '@' not in email:
            flash('Please enter a valid email address.', 'warning')
            return render_template('auth/forgot_password.html')

        # We always show the same message whether the email exists or not
        # This prevents people from finding out which emails are registered
        flash('If that email is registered, a password reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


# ── LOGOUT ─────────────────────────────────────────────────────────────────

@auth.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


# ── HELPER ─────────────────────────────────────────────────────────────────

def _redirect_by_role(role):
    """Redirect user to correct dashboard based on role."""
    if role == 'admin':
        return redirect(url_for('admin.admin_dashboard'))
    elif role == 'technician':
        return redirect(url_for('technician.technician_dashboard'))
    else:
        return redirect(url_for('resident.dashboard'))
