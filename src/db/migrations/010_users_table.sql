-- 010: Users table for authentication
BEGIN;

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20) NOT NULL DEFAULT 'viewer'
                  CHECK (role IN ('admin', 'purchaser', 'viewer')),
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login    TIMESTAMPTZ
);

-- Seed initial admin users (password: Admin@2026 — hashed with Argon2id)
INSERT INTO users (username, password_hash, role) VALUES
    ('kshitij', '$argon2id$v=19$m=65536,t=3,p=4$oDWPfH86CsXMKSw/4GyRjg$bbcqw0+h7ZGuoXHA2fYHrfWVoYquRkOr6QBu+jwIwgs', 'admin'),
    ('yash',    '$argon2id$v=19$m=65536,t=3,p=4$e/U24lRwsPLLqmDzZsQEZw$t0nGl1bU/udjFKgJGjFe8DLHlP07qdWNeIkoQNb8h3E', 'admin'),
    ('sonali',  '$argon2id$v=19$m=65536,t=3,p=4$dDMKz4UoISorXcS+ueA8ww$xEOvmRIaXmq/8pncnlCPMCX9FND/GpXI/Ot5p6Rj2HQ', 'admin')
ON CONFLICT (username) DO NOTHING;

COMMIT;
