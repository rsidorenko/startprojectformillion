-- Slice-1 UC-01 technical audit (AuditEvent / AuditAppender); append-only inserts.
CREATE TABLE IF NOT EXISTS slice1_audit_events (
    id BIGSERIAL PRIMARY KEY,
    correlation_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    outcome TEXT NOT NULL,
    internal_category TEXT NULL
);
