-- ADM-02 ensure-access durable redacted audit trail.
-- Stores bounded operational buckets only; no raw identifiers, refs, payloads, or secret material.
CREATE TABLE IF NOT EXISTS adm02_ensure_access_audit_events (
    audit_event_id TEXT NOT NULL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    event_type TEXT NOT NULL CHECK (event_type IN ('ensure_access')),
    outcome_bucket TEXT NOT NULL CHECK (
        outcome_bucket IN (
            'denied_unauthorized',
            'denied_mutation_opt_in_disabled',
            'noop_identity_unknown',
            'noop_no_active_subscription',
            'noop_access_already_ready',
            'issued_access',
            'failed_safe',
            'dependency_failure',
            'invalid_input'
        )
    ),
    remediation_result TEXT NULL CHECK (
        remediation_result IS NULL OR remediation_result IN (
            'noop_identity_unknown',
            'noop_no_active_subscription',
            'noop_access_already_ready',
            'issued_access',
            'failed_safe'
        )
    ),
    readiness_bucket TEXT NULL CHECK (
        readiness_bucket IS NULL OR readiness_bucket IN (
            'not_applicable_no_active_subscription',
            'active_access_not_ready',
            'active_access_ready',
            'unknown_due_to_internal_error'
        )
    ),
    principal_marker TEXT NOT NULL CHECK (principal_marker IN ('internal_admin_redacted')),
    correlation_id TEXT NOT NULL,
    source_marker TEXT NULL,
    CONSTRAINT ck_adm02_ensure_access_audit_event_id_len
        CHECK (char_length(audit_event_id) >= 1 AND char_length(audit_event_id) <= 64),
    CONSTRAINT ck_adm02_ensure_access_audit_correlation_len
        CHECK (char_length(correlation_id) >= 1 AND char_length(correlation_id) <= 128),
    CONSTRAINT ck_adm02_ensure_access_audit_source_len
        CHECK (source_marker IS NULL OR (char_length(source_marker) >= 1 AND char_length(source_marker) <= 64))
);

CREATE INDEX IF NOT EXISTS idx_adm02_ensure_access_audit_created_at
    ON adm02_ensure_access_audit_events (created_at);

CREATE INDEX IF NOT EXISTS idx_adm02_ensure_access_audit_outcome_created
    ON adm02_ensure_access_audit_events (outcome_bucket, created_at);
