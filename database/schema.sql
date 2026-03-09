


-- Users Table (students, admins, technicians)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(80) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    full_name VARCHAR(120),
    room_number VARCHAR(20),
    role VARCHAR(20) DEFAULT 'resident',
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Maintenance Requests Table
CREATE TABLE IF NOT EXISTS maintenance_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_no VARCHAR(20) NOT NULL UNIQUE,
    resident_id INTEGER NOT NULL,
    technician_id INTEGER,
    room_number VARCHAR(20),
    category VARCHAR(50),
    priority VARCHAR(20) DEFAULT 'low',
    title VARCHAR(200),
    description TEXT,
    status VARCHAR(30) DEFAULT 'pending',
    is_worsening BOOLEAN DEFAULT 0,
    submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME,
    resolved_at DATETIME,
    FOREIGN KEY (resident_id) REFERENCES users(id),
    FOREIGN KEY (technician_id) REFERENCES users(id)
);

-- Comments Table (internal notes and public updates)
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    author_id INTEGER NOT NULL,
    body TEXT NOT NULL,
    is_internal BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (request_id) REFERENCES maintenance_requests(id),
    FOREIGN KEY (author_id) REFERENCES users(id)
);

-- Notifications Table (in_app, email, sms)
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    request_id INTEGER,
    message TEXT NOT NULL,
    type VARCHAR(20) DEFAULT 'in_app',
    is_read BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (request_id) REFERENCES maintenance_requests(id)
);

-- Ratings Table (resident rates technician after resolution)
CREATE TABLE IF NOT EXISTS ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    resident_id INTEGER NOT NULL,
    technician_id INTEGER NOT NULL,
    score INTEGER CHECK(score BETWEEN 1 AND 5),
    review TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (request_id) REFERENCES maintenance_requests(id),
    FOREIGN KEY (resident_id) REFERENCES users(id),
    FOREIGN KEY (technician_id) REFERENCES users(id)
);

-- Images Table (photo uploads per request)
CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (request_id) REFERENCES maintenance_requests(id)
);



-- REFERENCE VALUES
-- Roles:    resident | technician | admin
-- Status:   pending | assigned | in_progress | resolved | closed | cancelled
-- Priority: low | medium | high | critical
-- Type:     in_app | email | sms

-- also final notes keep the comments in code as it helps us locate where to fix errors 

