# ============================================
# RESIFIX — AUTH ROUTES
# routes/auth.py
# Handles: login, register, logout
# ============================================

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import (
    get_user_by_username,
    get_user_by_email,
    create_user
)

auth = Blueprint('auth', __name__)


# LOGIN 

@auth.route('/login', methods=['GET', 'POST'])
def login():
    # If already logged in redirect to correct dashboard
    if 'user_id' in session:
        return redirect(url_for('resident.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        # Basic validation
        if not username or not password:
            flash('Please enter both username and password.', 'warning')
            return render_template('auth/login.html')

        # Check user exists
        user = get_user_by_username(username)

        if not user:
            flash('Username not found. Please check and try again.', 'danger')
            return render_template('auth/login.html')

        # Check account is active
        if not user['is_active']:
            flash('Your account has been deactivated. Please contact admin.', 'danger')
            return render_template('auth/login.html')

        # Check password
        if not check_password_hash(user['password'], password):
            flash('Incorrect password. Please try again.', 'danger')
            return render_template('auth/login.html')

        # Save user info to session
        session['user_id']   = user['id']
        session['username']  = user['username']
        session['full_name'] = user['full_name']
        session['role']      = user['role']

        flash(f"Welcome back, {user['full_name'].split()[0]}!", 'success')

        # Redirect based on role
        if user['role'] == 'admin':
            return redirect(url_for('admin.admin_dashboard'))
        elif user['role'] == 'technician':
            return redirect(url_for('technician.technician_dashboard'))
        else:
            return redirect(url_for('resident.dashboard'))

    return render_template('auth/login.html')


#  REGISTER

@auth.route('/register', methods=['GET', 'POST'])
def register():
    # If already logged in redirect away
    if 'user_id' in session:
        return redirect(url_for('resident.dashboard'))

    if request.method == 'POST':
        # Get form data
        role         = request.form.get('role', '').strip()
        full_name    = request.form.get('full_name', '').strip()
        username     = request.form.get('username', '').strip()
        email        = request.form.get('email', '').strip().lower()
        password     = request.form.get('password', '')
        confirm      = request.form.get('confirm_password', '')
        room_number  = request.form.get('room_number', '').strip()

        # ── Validation ──────────────────────────────────────────────────────

        # Role must be student or technician (admin created by admin only)
        if role not in ('resident', 'technician'):
            flash('Please select a valid role.', 'danger')
            return render_template('auth/register.html')

        if not full_name or len(full_name) < 2:
            flash('Please enter your full name.', 'danger')
            return render_template('auth/register.html')

        if not username or len(username) < 3:
            flash('Username must be at least 3 characters.', 'danger')
            return render_template('auth/register.html')

        if not email or '@' not in email:
            flash('Please enter a valid email address.', 'danger')
            return render_template('auth/register.html')

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('auth/register.html')

        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html')

        # Room number required for students only
        if role == 'resident' and not room_number:
            flash('Room number is required for students.', 'danger')
            return render_template('auth/register.html')

        # Check username not already taken
        if get_user_by_username(username):
            flash('That username is already taken. Please choose another.', 'danger')
            return render_template('auth/register.html')

        # Check email not already registered
        if get_user_by_email(email):
            flash('An account with that email already exists.', 'danger')
            return render_template('auth/register.html')

        #  Create Account 

        hashed_password = generate_password_hash(password)

        # Technicians don't have room numbers
        if role == 'technician':
            room_number = None

        success = create_user(
            username=username,
            email=email,
            password=hashed_password,
            full_name=full_name,
            room_number=room_number,
            role=role
        )

        if success:
            flash('Account created successfully! You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Something went wrong. Please try again.', 'danger')
            return render_template('auth/register.html')

    return render_template('auth/register.html')


#  LOGOUT 

@auth.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))