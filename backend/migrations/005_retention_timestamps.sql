-- Retention prep: row age for time-based cleanup (no DELETE in this migration).
ALTER TABLE idempotency_records
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE slice1_audit_events
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_slice1_audit_events_created_at
    ON slice1_audit_events (created_at);

CREATE INDEX IF NOT EXISTS idx_idempotency_records_created_at_completed_true
    ON idempotency_records (created_at)
    WHERE completed = true;
