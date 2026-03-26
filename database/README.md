# ResiFix — Database Guide
## For All Team Members

---

## How to Initialize the Database( this was created and added to help with work flow when working on teams online)

Run this **once** after cloning the repo:
```bash
python database/db.py
```

This will:
- Create the `resifix.db` file automatically
- Create all 6 tables
- Insert test data so you can start building immediately

---

## Test Login Credentials

Use these to test your pages:

| Role | Username | Password |
|------|----------|----------|
| Admin | admin1 | admin123 |
| Technician | tech1 | tech123 |
| Resident | student1 | student123 |

---

## How to Use db.py in Your Route Files

At the top of your route file, import only what you need:
```python
from database.db import get_user_by_username, get_requests_by_resident
```

---

## Available Functions — Quick Reference

### USER FUNCTIONS
```python
# Create a new user
create_user(username, email, password, full_name, room_number, role)

# Get user by ID
get_user_by_id(user_id)

# Get user by username (use for login)
get_user_by_username(username)

# Get user by email
get_user_by_email(email)

# Get all users (admin only)
get_all_users()

# Get all technicians (for assignment dropdown)
get_all_technicians()

# Update user profile
update_user(user_id, full_name, email, room_number)

# Activate or deactivate user (admin only)
set_user_active(user_id, is_active)
```


### REQUEST FUNCTIONS
```python
# Create a new maintenance request
create_request(resident_id, room_number, category, priority, title, description)
# Returns: ticket number e.g. "TKT-00001"

# Get single request by ID
get_request_by_id(request_id)

# Get all requests by a resident (for resident dashboard)
get_requests_by_resident(resident_id)

# Get all requests assigned to a technician
get_requests_by_technician(technician_id)

# Get all requests (admin dashboard)
get_all_requests()

# Update request status
update_request_status(request_id, status)
# Status options: pending | assigned | in_progress | resolved | closed | cancelled

# Assign a technician to a request
assign_technician(request_id, technician_id)

# Mark request as worsening
mark_worsening(request_id, is_worsening)
```

### COMMENT FUNCTIONS
```python
# Add a comment to a request
add_comment(request_id, author_id, body, is_internal=False)
# Set is_internal=True for technician/admin notes hidden from resident

# Get comments for a request
get_comments_by_request(request_id, include_internal=False)
# Set include_internal=True for admin/technician views
```

### NOTIFICATION FUNCTIONS
```python
# Create a notification
create_notification(user_id, message, request_id=None, type='in_app')
# Type options: in_app | email | sms

# Get all notifications for a user
get_notifications_by_user(user_id)

# Get unread notification count (for the bell badge)
get_unread_count(user_id)

# Mark all notifications as read
mark_notifications_read(user_id)
```

### RATING FUNCTIONS
```python
# Submit a rating after request is resolved
create_rating(request_id, resident_id, technician_id, score, review)
# Score: 1 to 5

# Get all ratings for a technician
get_ratings_by_technician(technician_id)

# Get average rating score for a technician
get_average_rating(technician_id)
```

### IMAGE FUNCTIONS
```python
# Save an uploaded image path
save_image(request_id, file_path)

# Get all images for a request
get_images_by_request(request_id)
```

---

## Example Usage in a Route File
```python
from flask import Blueprint, render_template, session, redirect, url_for
from database.db import get_requests_by_resident, create_notification

resident = Blueprint('resident', __name__)

@resident.route('/dashboard')
def dashboard():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))
    
    requests = get_requests_by_resident(user_id)
    return render_template('resident/dashboard.html', requests=requests)
```

---

## Important Rules

- **Never write raw SQL in your route files** — always use the functions above
- **Never push `resifix.db` to GitHub** — it is in `.gitignore` already
- **If you need a function that doesn't exist** — ask the database team to add it, do not write it yourself
- **Always import from `database.db`** — never from `db` alone

---

## Database Tables Reference

| Table | Purpose |
|-------|---------|
| `users` | All users — residents, technicians, admins |
| `maintenance_requests` | All repair/maintenance tickets |
| `comments` | Notes and updates on requests |
| `notifications` | In-app, email and SMS alerts |
| `ratings` | Technician reviews after resolution |
| `images` | Photo uploads linked to requests |