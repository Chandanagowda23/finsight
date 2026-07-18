-- FinSight Postgres init (Docker)
CREATE TABLE IF NOT EXISTS audit_events (
    id VARCHAR(36) PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor VARCHAR(128) NOT NULL,
    role VARCHAR(32) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    session_id VARCHAR(64),
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hitl_queue (
    id VARCHAR(36) PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    kind VARCHAR(64) NOT NULL,
    actor VARCHAR(128) NOT NULL,
    summary TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    reviewer VARCHAR(128),
    review_notes TEXT
);

-- Append-only enforcement for audit_events
CREATE OR REPLACE RULE audit_events_no_update AS ON UPDATE TO audit_events DO INSTEAD NOTHING;
CREATE OR REPLACE RULE audit_events_no_delete AS ON DELETE TO audit_events DO INSTEAD NOTHING;

CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_hitl_status ON hitl_queue(status, created_at DESC);
