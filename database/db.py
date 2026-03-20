import sqlite3
import os
from datetime import datetime

DATABASE = os.path.join(os.path.dirname(__file__), 'resifix.db')
SCHEMA   = os.path.join(os.path.dirname(__file__), 'schema.sql')


def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    with open(SCHEMA, 'r') as f:
        sql = f.read()
    for statement in sql.split(';'):
        statement = statement.strip()
        if statement:
            try:
                conn.execute(statement)
            except sqlite3.OperationalError as e:
                if 'duplicate column' in str(e).lower():
                    pass
                else:
                    raise
    conn.commit()
    conn.close()
    print("Database initialized successfully.")


# ── RESIDENCE FUNCTIONS ────────────────────────────────────────────────────

def get_all_residences():
    conn = get_connection()
    residences = conn.execute(
        "SELECT * FROM residences WHERE is_active = 1 ORDER BY name ASC"
    ).fetchall()
    conn.close()
    return residences

def get_all_residences_all():
    conn = get_connection()
    residences = conn.execute(
        "SELECT * FROM residences ORDER BY is_active DESC, name ASC"
    ).fetchall()
    conn.close()
    return residences

def get_residence_by_id(residence_id):
    conn = get_connection()
    res = conn.execute("SELECT * FROM residences WHERE id = ?", (residence_id,)).fetchone()
    conn.close()
    return res

def add_residence(name):
    conn = get_connection()
    try:
        conn.execute("INSERT INTO residences (name) VALUES (?)", (name,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def set_residence_active(residence_id, is_active):
    conn = get_connection()
    conn.execute("UPDATE residences SET is_active = ? WHERE id = ?", (is_active, residence_id))
    conn.commit()
    conn.close()


# ── USER FUNCTIONS ─────────────────────────────────────────────────────────

def create_user(username, email, password, full_name, room_number,
                role='resident', residence=None, specialization=None):
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO users
              (username, email, password, full_name, room_number, role, residence, specialization)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (username, email, password, full_name, room_number, role, residence, specialization))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_user_by_id(user_id):
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user

def get_user_by_username(username):
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return user

def get_user_by_email(email):
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return user

def get_all_users():
    conn = get_connection()
    users = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return users

def get_all_technicians():
    conn = get_connection()
    technicians = conn.execute(
        "SELECT * FROM users WHERE role = 'technician' AND is_active = 1"
    ).fetchall()
    conn.close()
    return technicians

def get_available_technicians_for_request(residence, category, exclude_request_id=None):
    """
    Returns active technicians matching residence and category.
    exclude_request_id: skips this request in the busy-check so the currently
    assigned technician still appears in the reassign dropdown.
    """
    category_map = {
        'Plumbing': 'plumbing', 'Electrical': 'electrical', 'Furniture': 'furniture',
        'Appliance': 'appliance', 'Internet': 'internet', 'Cleaning': 'cleaning',
        'Security': 'security', 'General': 'general',
    }
    specialization = category_map.get(category, category.lower())
    conn = get_connection()
    technicians = conn.execute("""
        SELECT * FROM users
        WHERE role = 'technician'
          AND is_active = 1
          AND residence = ?
          AND (specialization = ? OR specialization = 'general')
          AND id NOT IN (
              SELECT technician_id FROM maintenance_requests
              WHERE status NOT IN ('resolved', 'closed', 'cancelled')
                AND technician_id IS NOT NULL
                AND (? IS NULL OR id != ?)
          )
    """, (residence, specialization, exclude_request_id, exclude_request_id)).fetchall()
    conn.close()
    return technicians

def update_user(user_id, full_name, email, room_number):
    conn = get_connection()
    conn.execute("UPDATE users SET full_name=?, email=?, room_number=? WHERE id=?",
                 (full_name, email, room_number, user_id))
    conn.commit()
    conn.close()

def update_technician_profile(user_id, full_name, email):
    conn = get_connection()
    conn.execute("UPDATE users SET full_name=?, email=? WHERE id=?", (full_name, email, user_id))
    conn.commit()
    conn.close()

def update_profile(user_id, full_name, email,
                   room_number=None, residence=None, specialization=None):
    conn = get_connection()
    conn.execute("UPDATE users SET full_name=?, email=? WHERE id=?", (full_name, email, user_id))
    if room_number is not None:
        conn.execute("UPDATE users SET room_number=? WHERE id=?", (room_number, user_id))
    if residence is not None:
        conn.execute("UPDATE users SET residence=? WHERE id=?", (residence, user_id))
    if specialization is not None:
        conn.execute("UPDATE users SET specialization=? WHERE id=?", (specialization, user_id))
    conn.commit()
    conn.close()

def set_user_active(user_id, is_active):
    conn = get_connection()
    conn.execute("UPDATE users SET is_active=? WHERE id=?", (is_active, user_id))
    conn.commit()
    conn.close()


# ── MAINTENANCE REQUEST FUNCTIONS ──────────────────────────────────────────

def generate_ticket_number():
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM maintenance_requests").fetchone()[0]
    conn.close()
    return f"TKT-{str(count + 1).zfill(5)}"

def create_request(resident_id, room_number, category, priority,
                   title, description, residence=None):
    conn = get_connection()
    ticket_no = generate_ticket_number()
    try:
        conn.execute("""
            INSERT INTO maintenance_requests
              (ticket_no, resident_id, room_number, residence, category, priority, title, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ticket_no, resident_id, room_number, residence,
              category, priority, title, description))
        conn.commit()
        return ticket_no
    finally:
        conn.close()

def get_request_by_id(request_id):
    conn = get_connection()
    req = conn.execute(
        "SELECT * FROM maintenance_requests WHERE id=?", (request_id,)
    ).fetchone()
    conn.close()
    return req

def get_requests_by_resident(resident_id):
    conn = get_connection()
    requests = conn.execute(
        "SELECT * FROM maintenance_requests WHERE resident_id=? ORDER BY submitted_at DESC",
        (resident_id,)
    ).fetchall()
    conn.close()
    return requests

def get_requests_by_technician(technician_id):
    conn = get_connection()
    requests = conn.execute(
        "SELECT * FROM maintenance_requests WHERE technician_id=? ORDER BY submitted_at DESC",
        (technician_id,)
    ).fetchall()
    conn.close()
    return requests

def get_all_requests():
    conn = get_connection()
    requests = conn.execute(
        "SELECT * FROM maintenance_requests ORDER BY submitted_at DESC"
    ).fetchall()
    conn.close()
    return requests

def update_request_status(request_id, status):
    conn = get_connection()
    resolved_at = datetime.now() if status == 'resolved' else None
    conn.execute("""
        UPDATE maintenance_requests
        SET status=?, updated_at=?, resolved_at=?
        WHERE id=?
    """, (status, datetime.now(), resolved_at, request_id))
    conn.commit()
    conn.close()

def assign_technician(request_id, technician_id):
    conn = get_connection()
    conn.execute("""
        UPDATE maintenance_requests
        SET technician_id=?, status='assigned', updated_at=?
        WHERE id=?
    """, (technician_id, datetime.now(), request_id))
    conn.commit()
    conn.close()

def mark_worsening(request_id, is_worsening):
    conn = get_connection()
    conn.execute(
        "UPDATE maintenance_requests SET is_worsening=? WHERE id=?",
        (is_worsening, request_id)
    )
    conn.commit()
    conn.close()


# ── COMMENT FUNCTIONS ──────────────────────────────────────────────────────

def add_comment(request_id, author_id, body, is_internal=False):
    conn = get_connection()
    conn.execute(
        "INSERT INTO comments (request_id, author_id, body, is_internal) VALUES (?,?,?,?)",
        (request_id, author_id, body, is_internal)
    )
    conn.commit()
    conn.close()

def get_comments_by_request(request_id, include_internal=False, staff_only=False):
    """
    Visibility rules:
    - Default            → public only (student sees this)
    - include_internal   → everything (admin sees this)
    - staff_only         → internal only (technician sees this — not student-admin chat)
    """
    conn = get_connection()
    if staff_only:
        comments = conn.execute(
            "SELECT * FROM comments WHERE request_id=? AND is_internal=1 ORDER BY created_at ASC",
            (request_id,)
        ).fetchall()
    elif include_internal:
        comments = conn.execute(
            "SELECT * FROM comments WHERE request_id=? ORDER BY created_at ASC",
            (request_id,)
        ).fetchall()
    else:
        comments = conn.execute(
            "SELECT * FROM comments WHERE request_id=? AND is_internal=0 ORDER BY created_at ASC",
            (request_id,)
        ).fetchall()
    conn.close()
    return comments


# ── NOTIFICATION FUNCTIONS ─────────────────────────────────────────────────

def create_notification(user_id, message, request_id=None, type='in_app'):
    conn = get_connection()
    conn.execute(
        "INSERT INTO notifications (user_id, request_id, message, type) VALUES (?,?,?,?)",
        (user_id, request_id, message, type)
    )
    conn.commit()
    conn.close()

def get_notifications_by_user(user_id):
    conn = get_connection()
    notifications = conn.execute(
        "SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC", (user_id,)
    ).fetchall()
    conn.close()
    return notifications

def get_unread_count(user_id):
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (user_id,)
    ).fetchone()[0]
    conn.close()
    return count

def mark_notifications_read(user_id):
    conn = get_connection()
    conn.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


# ── RATINGS FUNCTIONS ──────────────────────────────────────────────────────

def create_rating(request_id, resident_id, technician_id, score, review):
    conn = get_connection()
    conn.execute(
        "INSERT INTO ratings (request_id, resident_id, technician_id, score, review) VALUES (?,?,?,?,?)",
        (request_id, resident_id, technician_id, score, review)
    )
    conn.commit()
    conn.close()

def get_ratings_by_technician(technician_id):
    conn = get_connection()
    ratings = conn.execute(
        "SELECT * FROM ratings WHERE technician_id=?", (technician_id,)
    ).fetchall()
    conn.close()
    return ratings

def get_average_rating(technician_id):
    conn = get_connection()
    result = conn.execute(
        "SELECT AVG(score) FROM ratings WHERE technician_id=?", (technician_id,)
    ).fetchone()[0]
    conn.close()
    return round(result, 1) if result else 0.0


# ── IMAGES FUNCTIONS ───────────────────────────────────────────────────────

def save_image(request_id, file_path):
    conn = get_connection()
    conn.execute(
        "INSERT INTO images (request_id, file_path) VALUES (?,?)",
        (request_id, file_path)
    )
    conn.commit()
    conn.close()

def get_images_by_request(request_id):
    conn = get_connection()
    images = conn.execute(
        "SELECT * FROM images WHERE request_id=?", (request_id,)
    ).fetchall()
    conn.close()
    return images


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
    create_request(4, 'A101', 'Plumbing', 'high',
                   'Leaking tap in bathroom', 'The tap has been leaking for 2 days',
                   residence='Residence A')
    create_request(4, 'A101', 'Electrical', 'medium',
                   'Faulty light switch', 'Light switch in bedroom is not working',
                   residence='Residence A')
    print("Seed data inserted successfully.")


if __name__ == '__main__':
    init_db()
    seed_data()
    print("Database ready at:", DATABASE)