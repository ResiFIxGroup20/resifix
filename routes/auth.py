# ============================================================
# RESIFIX — AUTH ROUTES v3.0
# routes/auth.py
# Handles: login, register, logout, forgot password, reset password
# ============================================================

import os
import requests as http_requests

from flask import (Blueprint, render_template, request,
                   redirect, url_for, flash, session)
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

from database.db import (
    get_user_by_username,
    get_user_by_email,
    create_user,
    get_all_residences,
    create_reset_token,
    get_reset_token,
    mark_token_used,
    update_user_password,
)

load_dotenv()

auth = Blueprint('auth', __name__)


# ── HELPERS ────────────────────────────────────────────────────────────────

def _redirect_by_role(role):
    if role == 'admin':
        return redirect(url_for('admin.admin_dashboard'))
    elif role == 'technician':
        return redirect(url_for('technician.technician_dashboard'))
    else:
        return redirect(url_for('resident.dashboard'))


def _send_reset_email(to_email, reset_link, user_name):
    """
    Send a password-reset email via Resend HTTP API.
    Render's free tier blocks all outbound SMTP (ports 465 and 587 both
    return Errno 101 Network unreachable). HTTP is never blocked.
    Raises RuntimeError if RESEND_API_KEY is not configured.
    """
    api_key   = os.getenv('RESEND_API_KEY', '').strip()
    from_name = os.getenv('MAIL_FROM_NAME', 'ResiFix')
    # Resend requires a verified sender domain in production.
    # Use MAIL_FROM_ADDRESS env var (e.g. noreply@yourdomain.com).
    # Falls back to Resend's shared test address for local/staging use.
    from_addr = os.getenv('MAIL_FROM_ADDRESS', 'onboarding@resend.dev')

    if not api_key:
        raise RuntimeError(
            "RESEND_API_KEY is not configured. "
            "Sign up at resend.com, create an API key, and add it "
            "to your Render environment variables."
        )

    # ── Plain-text version ────────────────────────────────────────────────
    text_body = f"""Hi {user_name},

We received a request to reset the password for your ResiFix account.

Click the link below to choose a new password (valid for 1 hour):

{reset_link}

If you didn't request this, you can safely ignore this email —
your password will not change.

— The ResiFix Team
DUT Group 20
"""

    # ── HTML version ──────────────────────────────────────────────────────
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background:#0a0f1e; font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:#0a0f1e; padding:40px 16px;">
    <tr>
      <td align="center">
        <table width="560" cellpadding="0" cellspacing="0"
               style="background:#0f1629; border:1px solid #1e2d4a;
                      border-radius:12px; overflow:hidden; max-width:100%;">

          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#2563eb,#7c3aed);
                        padding:28px 32px; text-align:center;">
              <div style="font-size:28px; font-weight:800; color:#fff;
                           letter-spacing:-0.5px;">
                🔧 ResiFix
              </div>
              <div style="color:rgba(255,255,255,0.75); font-size:13px;
                           margin-top:4px;">
                DUT Hostel Maintenance System
              </div>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:32px;">
              <h2 style="color:#e2e8f0; font-size:20px; font-weight:700;
                          margin:0 0 12px;">
                Password Reset Request
              </h2>
              <p style="color:#94a3b8; font-size:15px; line-height:1.6;
                         margin:0 0 24px;">
                Hi <strong style="color:#e2e8f0;">{user_name}</strong>,<br><br>
                We received a request to reset the password for your ResiFix account.
                Click the button below to choose a new password.
              </p>

              <!-- CTA Button -->
              <table cellpadding="0" cellspacing="0" style="margin:0 0 24px;">
                <tr>
                  <td style="background:linear-gradient(135deg,#2563eb,#7c3aed);
                              border-radius:8px;">
                    <a href="{reset_link}"
                       style="display:inline-block; padding:14px 32px;
                              color:#fff; font-size:15px; font-weight:700;
                              text-decoration:none; letter-spacing:0.2px;">
                      Reset My Password
                    </a>
                  </td>
                </tr>
              </table>

              <p style="color:#64748b; font-size:13px; line-height:1.6;
                         margin:0 0 16px;">
                This link expires in <strong style="color:#94a3b8;">1 hour</strong>.
                If you didn't request a password reset you can safely ignore this email.
              </p>

              <!-- Fallback link -->
              <div style="background:#0a0f1e; border:1px solid #1e2d4a;
                           border-radius:6px; padding:12px 16px;">
                <p style="color:#64748b; font-size:11px; margin:0 0 6px;">
                  If the button doesn't work, copy and paste this link:
                </p>
                <p style="color:#2563eb; font-size:11px; word-break:break-all; margin:0;">
                  {reset_link}
                </p>
              </div>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:16px 32px 28px; border-top:1px solid #1e2d4a;
                        text-align:center;">
              <p style="color:#475569; font-size:12px; margin:0;">
                ResiFix · DUT Group 20 · Durban University of Technology
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    # ── Send via Resend HTTP API ──────────────────────────────────────────
    # Render's free tier blocks all outbound SMTP (errno 101 — network
    # unreachable on both port 465 and 587). HTTP is never blocked.
    response = http_requests.post(
        'https://api.resend.com/emails',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type':  'application/json',
        },
        json={
            'from':    f'{from_name} <{from_addr}>',
            'to':      [to_email],
            'subject': 'Reset your ResiFix password',
            'text':    text_body,
            'html':    html_body,
        },
        timeout=15,
    )
    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"Resend API error {response.status_code}: {response.text}"
        )


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

        session['user_id']     = user['id']
        session['username']    = user['username']
        session['full_name']   = user['full_name']
        session['role']        = user['role']
        session['residence']   = user['residence']
        session['room_number'] = user['room_number']

        flash(f"Welcome back, {user['full_name'].split()[0]}!", 'success')
        return _redirect_by_role(user['role'])

    return render_template('auth/login.html')


# ── REGISTER ───────────────────────────────────────────────────────────────

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return _redirect_by_role(session.get('role'))

    residences = get_all_residences()

    if request.method == 'POST':
        role           = request.form.get('role',           '').strip()
        full_name      = request.form.get('full_name',      '').strip()
        username       = request.form.get('username',       '').strip()
        email          = request.form.get('email',          '').strip().lower()
        password       = request.form.get('password',       '')
        confirm        = request.form.get('confirm_password', '')
        room_number    = request.form.get('room_number',    '').strip()
        residence      = request.form.get('residence',      '').strip()
        specialization = request.form.get('specialization', '').strip()

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
        if role == 'resident' and not room_number:
            flash('Room number is required for students.', 'danger')
            return render_template('auth/register.html', residences=residences)
        if role == 'technician' and not specialization:
            flash('Please select your specialization.', 'danger')
            return render_template('auth/register.html', residences=residences)
        if get_user_by_username(username):
            flash('That username is already taken.', 'danger')
            return render_template('auth/register.html', residences=residences)
        if get_user_by_email(email):
            flash('An account with that email already exists.', 'danger')
            return render_template('auth/register.html', residences=residences)

        if role == 'technician':
            room_number = None

        success = create_user(
            username       = username,
            email          = email,
            password       = generate_password_hash(password),
            full_name      = full_name,
            room_number    = room_number,
            role           = role,
            residence      = residence,
            specialization = specialization if role == 'technician' else None,
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
    if 'user_id' in session:
        return _redirect_by_role(session.get('role'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email or '@' not in email:
            flash('Please enter a valid email address.', 'warning')
            return render_template('auth/forgot_password.html')

        user = get_user_by_email(email)

        # Always show the same message — prevents email enumeration
        if user and user['is_active']:
            try:
                token      = create_reset_token(user['id'])
                base_url   = os.getenv('APP_BASE_URL', request.host_url.rstrip('/'))
                reset_link = f"{base_url}/reset-password/{token}"
                _send_reset_email(user['email'], reset_link, user['full_name'].split()[0])
            except RuntimeError as e:
                # Mail not configured — show a developer-friendly flash in debug mode
                from flask import current_app
                if current_app.debug:
                    flash(f'Mail not configured: {e}', 'warning')
                    return render_template('auth/forgot_password.html')
            except Exception:
                # Mail failed to send — still show the generic message so
                # we don't reveal whether the email exists
                pass

        flash(
            'If that email is registered, a password reset link has been sent. '
            'Please check your inbox (and spam folder).',
            'info'
        )
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


# ── RESET PASSWORD ─────────────────────────────────────────────────────────

@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if 'user_id' in session:
        return _redirect_by_role(session.get('role'))

    token_row = get_reset_token(token)

    if not token_row:
        flash(
            'This password reset link is invalid or has expired. '
            'Please request a new one.',
            'danger'
        )
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password',         '')
        confirm  = request.form.get('confirm_password', '')

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('auth/reset_password.html', token=token)

        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/reset_password.html', token=token)

        update_user_password(token_row['user_id'], generate_password_hash(password))
        mark_token_used(token)

        flash('Your password has been reset successfully. Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)


# ── LOGOUT ─────────────────────────────────────────────────────────────────

@auth.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))