-- RCAI Database Schema (v2 — auth + LLM-based analysis)

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(120) NOT NULL,
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS incidents (
    id                SERIAL PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title             VARCHAR(255) NOT NULL,
    error_log         TEXT NOT NULL,
    severity          VARCHAR(20) DEFAULT 'MEDIUM' CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    status            VARCHAR(20) DEFAULT 'OPEN' CHECK (status IN ('OPEN','IN_PROGRESS','RESOLVED','CLOSED')),
    created_at        TIMESTAMP DEFAULT NOW(),
    resolved_at       TIMESTAMP
);

-- One row per AI analysis run. Structured fields map directly onto the
-- JSON the LLM returns, so the UI can render rich cards without re-parsing.
CREATE TABLE IF NOT EXISTS root_causes (
    id                   SERIAL PRIMARY KEY,
    incident_id          INTEGER REFERENCES incidents(id) ON DELETE CASCADE,
    summary              TEXT,
    root_causes          JSONB,   -- [{cause, confidence, severity, fix, service}]
    five_whys            JSONB,   -- {why1..why5}
    affected_services    JSONB,   -- ["Payment Service", ...]
    category             VARCHAR(100),   -- normalized tag, drives recurrence lookups (no embeddings needed)
    recurrence_count     INTEGER DEFAULT 0,
    historical_solution  TEXT,
    created_at           TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_incidents_user      ON incidents(user_id);
CREATE INDEX IF NOT EXISTS idx_incidents_status     ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_severity   ON incidents(severity);
CREATE INDEX IF NOT EXISTS idx_incidents_created    ON incidents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_root_causes_category ON root_causes(category);

-- Drop legacy semantic-search artifacts if upgrading an existing v1 database.
DROP TABLE IF EXISTS incident_embeddings;
