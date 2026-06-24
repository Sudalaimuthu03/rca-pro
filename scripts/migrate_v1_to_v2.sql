-- Optional: run this ONCE if you have an existing v1 deployment with real
-- incident data you want to keep. Fresh installs should just let
-- database/schema.sql create everything via init_db() — skip this file.
--
-- This creates a placeholder user and attaches all existing incidents to it,
-- since v1 had no user accounts. Update the email/password after running.

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(120) NOT NULL,
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW()
);

INSERT INTO users (name, email, password_hash)
VALUES ('Migrated Admin', 'admin@example.com', 'CHANGE_ME_RUN_RESET_PASSWORD')
ON CONFLICT (email) DO NOTHING;

ALTER TABLE incidents ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;
UPDATE incidents SET user_id = (SELECT id FROM users WHERE email = 'admin@example.com') WHERE user_id IS NULL;
ALTER TABLE incidents ALTER COLUMN user_id SET NOT NULL;

ALTER TABLE incidents DROP COLUMN IF EXISTS cpu_usage;
ALTER TABLE incidents DROP COLUMN IF EXISTS memory_usage;
ALTER TABLE incidents DROP COLUMN IF EXISTS disk_usage;
ALTER TABLE incidents DROP COLUMN IF EXISTS response_time_ms;
ALTER TABLE incidents DROP COLUMN IF EXISTS description;
ALTER TABLE incidents RENAME COLUMN error_log TO error_log; -- already named correctly

ALTER TABLE root_causes ADD COLUMN IF NOT EXISTS summary TEXT;
ALTER TABLE root_causes ADD COLUMN IF NOT EXISTS root_causes JSONB;
ALTER TABLE root_causes ADD COLUMN IF NOT EXISTS five_whys JSONB;
ALTER TABLE root_causes ADD COLUMN IF NOT EXISTS affected_services JSONB;
ALTER TABLE root_causes ADD COLUMN IF NOT EXISTS category VARCHAR(100);
ALTER TABLE root_causes ADD COLUMN IF NOT EXISTS recurrence_count INTEGER DEFAULT 0;
ALTER TABLE root_causes ADD COLUMN IF NOT EXISTS historical_solution TEXT;

DROP TABLE IF EXISTS incident_embeddings;
