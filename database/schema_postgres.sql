
-- ResiFix — PostgreSQL Schema


CREATE TABLE IF NOT EXISTS residences (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(100) NOT NULL UNIQUE,
    is_active  BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id               SERIAL PRIMARY KEY,
    username         VARCHAR(80)  NOT NULL UNIQUE,
    email            VARCHAR(120) NOT NULL UNIQUE,
    password         VARCHAR(255) NOT NULL,
    full_name        VARCHAR(120),
    room_number      VARCHAR(20),
    residence        VARCHAR(100),
    specialization   VARCHAR(50),
    role             VARCHAR(20)  DEFAULT 'resident',
    is_active        BOOLEAN DEFAULT TRUE,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS maintenance_requests (
    id            SERIAL PRIMARY KEY,
    ticket_no     VARCHAR(20) NOT NULL UNIQUE,
    resident_id   INTEGER NOT NULL REFERENCES users(id),
    technician_id INTEGER REFERENCES users(id),
    room_number   VARCHAR(20),
    residence     VARCHAR(100),
    category      VARCHAR(50),
    priority      VARCHAR(20) DEFAULT 'low',
    title         VARCHAR(200),
    description   TEXT,
    status        VARCHAR(30) DEFAULT 'pending',
    is_worsening  BOOLEAN DEFAULT FALSE,
    submitted_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP,
    resolved_at   TIMESTAMP
);

CREATE TABLE IF NOT EXISTS comments (
    id          SERIAL PRIMARY KEY,
    request_id  INTEGER NOT NULL REFERENCES maintenance_requests(id),
    author_id   INTEGER NOT NULL REFERENCES users(id),
    body        TEXT NOT NULL,
    is_internal INTEGER DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notifications (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    request_id INTEGER REFERENCES maintenance_requests(id),
    message    TEXT NOT NULL,
    type       VARCHAR(20) DEFAULT 'in_app',
    is_read    BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ratings (
    id            SERIAL PRIMARY KEY,
    request_id    INTEGER NOT NULL REFERENCES maintenance_requests(id),
    resident_id   INTEGER NOT NULL REFERENCES users(id),
    technician_id INTEGER NOT NULL REFERENCES users(id),
    score         INTEGER CHECK(score BETWEEN 1 AND 5),
    review        TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS images (
    id          SERIAL PRIMARY KEY,
    request_id  INTEGER NOT NULL REFERENCES maintenance_requests(id),
    file_path   VARCHAR(255) NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    token      VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    used       BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
