-- Append-only internal UC-04 billing ingestion audit (normalized path only; no provider payload/headers).
CREATE TABLE IF NOT EXISTS billing_ingestion_audit_events (
    audit_event_id TEXT PRIMARY KEY,
    internal_fact_ref TEXT NOT NULL,
    billing_provider_key TEXT NOT NULL,
    external_event_id TEXT NOT NULL,
    ingestion_correlation_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    outcome TEXT NOT NULL,
    billing_event_status TEXT NOT NULL,
    is_idempotent_replay BOOLEAN NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT billing_ingestion_audit_operation_check CHECK (operation = 'billing_fact_ingested'),
    CONSTRAINT billing_ingestion_audit_outcome_check CHECK (outcome IN ('accepted', 'idempotent_replay')),
    CONSTRAINT billing_ingestion_audit_status_check CHECK (
        billing_event_status IN ('accepted', 'duplicate', 'ignored')
    )
);

CREATE INDEX IF NOT EXISTS idx_billing_ingestion_audit_internal_fact_ref
    ON billing_ingestion_audit_events (internal_fact_ref);

CREATE INDEX IF NOT EXISTS idx_billing_ingestion_audit_provider_external
    ON billing_ingestion_audit_events (billing_provider_key, external_event_id);

CREATE INDEX IF NOT EXISTS idx_billing_ingestion_audit_occurred_at
    ON billing_ingestion_audit_events (occurred_at);
