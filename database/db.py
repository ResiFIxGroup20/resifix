
# RESIFIX — DATABASE LAYER
# Supports both PostgreSQL (Render/production) and
# SQLite (local dev) depending on DATABASE_URL env var.


import os
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', '').strip()

# ── Driver detection ───────────────────────────────────────────────────────
if DATABASE_URL:
    import psycopg2
    import psycopg2.extras
    DRIVER = 'postgres'
    # Render gives URLs starting with postgres:// — psycopg2 needs postgresql://
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
else:
    import sqlite3
    DRIVER = 'sqlite'
    DATABASE = os.path.join(os.path.dirname(__file__), 'resifix.db')

SCHEMA_SQLITE   = os.path.join(os.path.dirname(__file__), 'schema.sql')
SCHEMA_POSTGRES = os.path.join(os.path.dirname(__file__), 'schema_postgres.sql')

PH = '%s' if DRIVER == 'postgres' else '?'   # placeholder character


# ── Connection helpers ─────────────────────────────────────────────────────

def get_connection():
    if DRIVER == 'postgres':
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


def _cursor(conn):
    """Return a dict-like cursor appropriate for the driver."""
    if DRIVER == 'postgres':
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        return conn  # SQLite connection supports .execute() directly


def _convert_row(row):
    """
    Convert a psycopg2 RealDictRow to a plain dict, turning any datetime/date
    objects into ISO-format strings so Jinja2 templates can use [:10] slicing
    just like they did with SQLite string results.
    """
    if row is None:
        return None
    result = {}
    for key, value in row.items():
        if hasattr(value, 'strftime'):
            result[key] = value.strftime('%Y-%m-%d %H:%M:%S')
        else:
            result[key] = value
    return result


def _fetchone(conn, sql, params=()):
    if DRIVER == 'postgres':
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        return _convert_row(cur.fetchone())
    else:
        return conn.execute(sql, params).fetchone()


def _fetchall(conn, sql, params=()):
    if DRIVER == 'postgres':
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        return [_convert_row(r) for r in cur.fetchall()]
    else:
        return conn.execute(sql, params).fetchall()


def _execute(conn, sql, params=()):
    if DRIVER == 'postgres':
        cur = conn.cursor()
        cur.execute(sql, params)
    else:
        conn.execute(sql, params)


def _scalar(conn, sql, params=()):
    """Return a single scalar value from the first column of the first row."""
    if DRIVER == 'postgres':
        cur = conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row else None
    else:
        row = conn.execute(sql, params).fetchone()
        return row[0] if row else None


def _integrityerror():
    if DRIVER == 'postgres':
        return psycopg2.IntegrityError
    else:
        return sqlite3.IntegrityError


# ── init_db ────────────────────────────────────────────────────────────────

def init_db():
    schema_file = SCHEMA_POSTGRES if DRIVER == 'postgres' else SCHEMA_SQLITE
    conn = get_connection()
    with open(schema_file, 'r') as f:
        sql = f.read()

    if DRIVER == 'postgres':
        cur = conn.cursor()
        # Split on semicolons, run each statement
        for stmt in sql.split(';'):
            stmt = stmt.strip()
            if stmt:
                try:
                    cur.execute(stmt)
                except Exception as e:
                    err = str(e).lower()
                    if 'already exists' in err or 'duplicate column' in err:
                        conn.rollback()
                    else:
                        conn.rollback()
                        raise
        conn.commit()
    else:
        for stmt in sql.split(';'):
            stmt = stmt.strip()
            if stmt:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError as e:
                    if 'duplicate column' in str(e).lower() or 'already exists' in str(e).lower():
                        pass
                    else:
                        raise
        conn.commit()

    conn.close()
    print(f"Database initialised successfully ({DRIVER}).")


# ── RESIDENCE FUNCTIONS ────────────────────────────────────────────────────

def get_all_residences():
    conn = get_connection()
    rows = _fetchall(conn,
        "SELECT * FROM residences WHERE is_active = TRUE ORDER BY name ASC"
        if DRIVER == 'postgres' else
        "SELECT * FROM residences WHERE is_active = 1 ORDER BY name ASC"
    )
    conn.close()
    return rows

def get_all_residences_all():
    conn = get_connection()
    rows = _fetchall(conn,
        "SELECT * FROM residences ORDER BY is_active DESC, name ASC"
    )
    conn.close()
    return rows

def get_residence_by_id(residence_id):
    conn = get_connection()
    row = _fetchone(conn, f"SELECT * FROM residences WHERE id = {PH}", (residence_id,))
    conn.close()
    return row

def add_residence(name):
    conn = get_connection()
    try:
        _execute(conn, f"INSERT INTO residences (name) VALUES ({PH})", (name,))
        conn.commit()
        return True
    except _integrityerror().__class__:
        return False
    finally:
        conn.close()

def set_residence_active(residence_id, is_active):
    conn = get_connection()
    _execute(conn, f"UPDATE residences SET is_active = {PH} WHERE id = {PH}", (is_active, residence_id))
    conn.commit()
    conn.close()


# ── USER FUNCTIONS ─────────────────────────────────────────────────────────

def create_user(username, email, password, full_name, room_number,
                role='resident', residence=None, specialization=None):
    conn = get_connection()
    try:
        _execute(conn, f"""
            INSERT INTO users
              (username, email, password, full_name, room_number, role, residence, specialization)
            VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})
        """, (username, email, password, full_name, room_number, role, residence, specialization))
        conn.commit()
        return True
    except Exception as e:
        if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
            return False
        raise
    finally:
        conn.close()

def get_user_by_id(user_id):
    conn = get_connection()
    row = _fetchone(conn, f"SELECT * FROM users WHERE id = {PH}", (user_id,))
    conn.close()
    return row

def get_user_by_username(username):
    conn = get_connection()
    row = _fetchone(conn, f"SELECT * FROM users WHERE username = {PH}", (username,))
    conn.close()
    return row

def get_user_by_email(email):
    conn = get_connection()
    row = _fetchone(conn, f"SELECT * FROM users WHERE email = {PH}", (email,))
    conn.close()
    return row

def get_all_users():
    conn = get_connection()
    rows = _fetchall(conn, "SELECT * FROM users ORDER BY created_at DESC")
    conn.close()
    return rows

def get_all_technicians():
    conn = get_connection()
    rows = _fetchall(conn,
        "SELECT * FROM users WHERE role = 'technician' AND is_active = TRUE"
        if DRIVER == 'postgres' else
        "SELECT * FROM users WHERE role = 'technician' AND is_active = 1"
    )
    conn.close()
    return rows

def get_available_technicians_for_request(residence, category, exclude_request_id=None):
    category_map = {
        'Plumbing': 'plumbing', 'Electrical': 'electrical', 'Furniture': 'furniture',
        'Appliance': 'appliance', 'Internet': 'internet', 'Cleaning': 'cleaning',
        'Security': 'security', 'General': 'general',
        'plumbing': 'plumbing', 'electrical': 'electrical', 'furniture': 'furniture',
        'appliance': 'appliance', 'internet': 'internet', 'cleaning': 'cleaning',
        'security': 'security', 'general': 'general', 'other': 'general',
    }
    specialization = category_map.get(category, category.lower())
    active_val = True if DRIVER == 'postgres' else 1
    conn = get_connection()
    rows = _fetchall(conn, f"""
        SELECT * FROM users
        WHERE role = 'technician'
          AND is_active = {PH}
          AND residence = {PH}
          AND (specialization = {PH} OR specialization = 'general')
          AND id NOT IN (
              SELECT technician_id FROM maintenance_requests
              WHERE status NOT IN ('resolved', 'closed', 'cancelled')
                AND technician_id IS NOT NULL
                AND ({PH} IS NULL OR id != {PH})
          )
    """, (active_val, residence, specialization, exclude_request_id, exclude_request_id))
    conn.close()
    return rows

def update_profile(user_id, full_name, email,
                   room_number=None, residence=None, specialization=None):
    conn = get_connection()
    fields = [f'full_name={PH}', f'email={PH}']
    values = [full_name, email]
    if room_number is not None:
        fields.append(f'room_number={PH}')
        values.append(room_number)
    if residence is not None:
        fields.append(f'residence={PH}')
        values.append(residence)
    if specialization is not None:
        fields.append(f'specialization={PH}')
        values.append(specialization)
    values.append(user_id)
    _execute(conn, f"UPDATE users SET {', '.join(fields)} WHERE id={PH}", values)
    conn.commit()
    conn.close()

def set_user_active(user_id, is_active):
    conn = get_connection()
    _execute(conn, f"UPDATE users SET is_active={PH} WHERE id={PH}", (is_active, user_id))
    conn.commit()
    conn.close()

def update_user_password(user_id, hashed_password):
    conn = get_connection()
    _execute(conn, f"UPDATE users SET password={PH} WHERE id={PH}", (hashed_password, user_id))
    conn.commit()
    conn.close()


# ── MAINTENANCE REQUEST FUNCTIONS ──────────────────────────────────────────

def generate_ticket_number():
    conn = get_connection()
    count = _scalar(conn, "SELECT COUNT(*) FROM maintenance_requests")
    conn.close()
    return f"TKT-{str((count or 0) + 1).zfill(5)}"

def create_request(resident_id, room_number, category, priority,
                   title, description, residence=None):
    conn = get_connection()
    ticket_no = generate_ticket_number()
    try:
        _execute(conn, f"""
            INSERT INTO maintenance_requests
              (ticket_no, resident_id, room_number, residence, category, priority, title, description)
            VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})
        """, (ticket_no, resident_id, room_number, residence,
              category, priority, title, description))
        conn.commit()
        return ticket_no
    finally:
        conn.close()

def get_request_by_id(request_id):
    conn = get_connection()
    row = _fetchone(conn,
        f"SELECT * FROM maintenance_requests WHERE id={PH}", (request_id,))
    conn.close()
    return row

def get_requests_by_resident(resident_id):
    conn = get_connection()
    rows = _fetchall(conn,
        f"SELECT * FROM maintenance_requests WHERE resident_id={PH} ORDER BY submitted_at DESC",
        (resident_id,))
    conn.close()
    return rows

def get_requests_by_technician(technician_id):
    conn = get_connection()
    rows = _fetchall(conn,
        f"SELECT * FROM maintenance_requests WHERE technician_id={PH} ORDER BY submitted_at DESC",
        (technician_id,))
    conn.close()
    return rows

def get_all_requests():
    conn = get_connection()
    rows = _fetchall(conn,
        "SELECT * FROM maintenance_requests ORDER BY submitted_at DESC")
    conn.close()
    return rows

def update_request_status(request_id, status):
    conn = get_connection()
    resolved_at = datetime.now() if status == 'resolved' else None
    _execute(conn, f"""
        UPDATE maintenance_requests
        SET status={PH}, updated_at={PH}, resolved_at={PH}
        WHERE id={PH}
    """, (status, datetime.now(), resolved_at, request_id))
    conn.commit()
    conn.close()

def assign_technician(request_id, technician_id):
    conn = get_connection()
    _execute(conn, f"""
        UPDATE maintenance_requests
        SET technician_id={PH}, status='assigned', updated_at={PH}
        WHERE id={PH}
    """, (technician_id, datetime.now(), request_id))
    conn.commit()
    conn.close()

def mark_worsening(request_id, is_worsening):
    conn = get_connection()
    _execute(conn,
        f"UPDATE maintenance_requests SET is_worsening={PH} WHERE id={PH}",
        (is_worsening, request_id))
    conn.commit()
    conn.close()


# ── COMMENT FUNCTIONS ──────────────────────────────────────────────────────

def add_comment(request_id, author_id, body, is_internal=0):
    conn = get_connection()
    _execute(conn,
        f"INSERT INTO comments (request_id, author_id, body, is_internal) VALUES ({PH},{PH},{PH},{PH})",
        (request_id, author_id, body, is_internal))
    conn.commit()
    conn.close()

def get_comments_by_request(request_id, include_internal=False,
                             staff_only=False, direct_only=False, notes_only=False):
    conn = get_connection()
    if notes_only:
        rows = _fetchall(conn,
            f"SELECT * FROM comments WHERE request_id={PH} AND is_internal=3 ORDER BY created_at ASC",
            (request_id,))
    elif direct_only:
        rows = _fetchall(conn,
            f"SELECT * FROM comments WHERE request_id={PH} AND is_internal=2 ORDER BY created_at ASC",
            (request_id,))
    elif staff_only:
        rows = _fetchall(conn,
            f"SELECT * FROM comments WHERE request_id={PH} AND is_internal=1 ORDER BY created_at ASC",
            (request_id,))
    elif include_internal:
        rows = _fetchall(conn,
            f"SELECT * FROM comments WHERE request_id={PH} AND is_internal IN (0,1) ORDER BY created_at ASC",
            (request_id,))
    else:
        rows = _fetchall(conn,
            f"SELECT * FROM comments WHERE request_id={PH} AND is_internal=0 ORDER BY created_at ASC",
            (request_id,))
    conn.close()
    return rows


# ── NOTIFICATION FUNCTIONS ─────────────────────────────────────────────────

def create_notification(user_id, message, request_id=None, type='in_app'):
    conn = get_connection()
    _execute(conn,
        f"INSERT INTO notifications (user_id, request_id, message, type) VALUES ({PH},{PH},{PH},{PH})",
        (user_id, request_id, message, type))
    conn.commit()
    conn.close()

def get_unread_count(user_id):
    conn = get_connection()
    val  = True if DRIVER == 'postgres' else 0
    # is_read = FALSE (postgres) or 0 (sqlite)
    count = _scalar(conn,
        f"SELECT COUNT(*) FROM notifications WHERE user_id={PH} AND is_read=FALSE"
        if DRIVER == 'postgres' else
        f"SELECT COUNT(*) FROM notifications WHERE user_id={PH} AND is_read=0",
        (user_id,))
    conn.close()
    return count or 0


# ── RATINGS FUNCTIONS ──────────────────────────────────────────────────────

def create_rating(request_id, resident_id, technician_id, score, review):
    conn = get_connection()
    _execute(conn,
        f"INSERT INTO ratings (request_id, resident_id, technician_id, score, review) VALUES ({PH},{PH},{PH},{PH},{PH})",
        (request_id, resident_id, technician_id, score, review))
    conn.commit()
    conn.close()

def get_ratings_by_technician(technician_id):
    conn = get_connection()
    rows = _fetchall(conn,
        f"SELECT * FROM ratings WHERE technician_id={PH}", (technician_id,))
    conn.close()
    return rows

def get_average_rating(technician_id):
    conn = get_connection()
    result = _scalar(conn,
        f"SELECT AVG(score) FROM ratings WHERE technician_id={PH}", (technician_id,))
    conn.close()
    return round(float(result), 1) if result else 0.0


# ── IMAGES FUNCTIONS ───────────────────────────────────────────────────────

def save_image(request_id, file_path):
    conn = get_connection()
    _execute(conn,
        f"INSERT INTO images (request_id, file_path) VALUES ({PH},{PH})",
        (request_id, file_path))
    conn.commit()
    conn.close()

def get_images_by_request(request_id):
    conn = get_connection()
    rows = _fetchall(conn,
        f"SELECT * FROM images WHERE request_id={PH}", (request_id,))
    conn.close()
    return rows

def get_connection_and_fetchone(sql, params=()):
    """One-shot helper used in routes for raw queries."""
    conn = get_connection()
    row  = _fetchone(conn, sql, params)
    conn.close()
    return row


# ── PASSWORD RESET TOKEN FUNCTIONS ─────────────────────────────────────────

def create_reset_token(user_id):
    token      = uuid.uuid4().hex + uuid.uuid4().hex
    expires_at = datetime.now() + timedelta(hours=1)
    conn = get_connection()
    _execute(conn,
        f"UPDATE password_reset_tokens SET used=TRUE WHERE user_id={PH} AND used=FALSE"
        if DRIVER == 'postgres' else
        f"UPDATE password_reset_tokens SET used=1 WHERE user_id={PH} AND used=0",
        (user_id,))
    _execute(conn,
        f"INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES ({PH},{PH},{PH})",
        (user_id, token, expires_at))
    conn.commit()
    conn.close()
    return token

def get_reset_token(token):
    conn = get_connection()
    row = _fetchone(conn, f"""
        SELECT * FROM password_reset_tokens
        WHERE token={PH} AND used=FALSE AND expires_at > {PH}
    """ if DRIVER == 'postgres' else f"""
        SELECT * FROM password_reset_tokens
        WHERE token={PH} AND used=0 AND expires_at > {PH}
    """, (token, datetime.now()))
    conn.close()
    return row

def mark_token_used(token):
    conn = get_connection()
    _execute(conn,
        f"UPDATE password_reset_tokens SET used=TRUE WHERE token={PH}"
        if DRIVER == 'postgres' else
        f"UPDATE password_reset_tokens SET used=1 WHERE token={PH}",
        (token,))
    conn.commit()
    conn.close()


# ── SEED DATA ──────────────────────────────────────────────────────────────

def seed_data():
    from werkzeug.security import generate_password_hash
    add_residence('Residence A')
    add_residence('Residence B')
    add_residence('Residence C')
    add_residence('Residence D')
    create_user('admin1', 'admin@resifix.com', generate_password_hash('admin123'),
                'Admin User', None, 'admin', residence='Residence A')
    create_user('tech1', 'tech@resifix.com', generate_password_hash('tech123'),
                'John Technician', None, 'technician',
                residence='Residence A', specialization='plumbing')
    create_user('tech2', 'tech2@resifix.com', generate_password_hash('tech123'),
                'Sara Technician', None, 'technician',
                residence='Residence A', specialization='electrical')
    create_user('student1', 'student@resifix.com', generate_password_hash('student123'),
                'Jane Resident', 'A101', 'resident', residence='Residence A')
    print("Seed data inserted.")

if __name__ == '__main__':
    init_db()
    seed_data()

# ── EXTRA HELPERS (used by routes to avoid inline raw SQL) ─────────────────

def get_request_id_by_ticket(ticket_no):
    conn = get_connection()
    row  = _fetchone(conn,
        f"SELECT id FROM maintenance_requests WHERE ticket_no={PH}", (ticket_no,))
    conn.close()
    return row

def get_existing_rating(request_id, resident_id):
    conn = get_connection()
    row  = _fetchone(conn,
        f"SELECT * FROM ratings WHERE request_id={PH} AND resident_id={PH}",
        (request_id, resident_id))
    conn.close()
    return row

def get_rating_by_request(request_id):
    conn = get_connection()
    row  = _fetchone(conn,
        f"SELECT * FROM ratings WHERE request_id={PH}", (request_id,))
    conn.close()
    return row

def get_residence_raw(residence_id):
    conn = get_connection()
    row  = _fetchone(conn,
        f"SELECT * FROM residences WHERE id={PH}", (residence_id,))
    conn.close()
    return row