-- UC-05: durable apply idempotency + append-only apply audit (no raw provider payload, no JSONB).

CREATE TABLE IF NOT EXISTS billing_subscription_apply_records (
    internal_fact_ref TEXT NOT NULL PRIMARY KEY,
    -- When the ledger fact has no internal user, store UC-05 sentinel (see app.domain.billing_apply_rules.UC05_NO_USER_SENTINEL).
    internal_user_id TEXT NOT NULL,
    apply_outcome TEXT NOT NULL CHECK (
        apply_outcome IN ('active_applied', 'no_activation', 'needs_review')
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS billing_subscription_apply_audit_events (
    audit_event_id TEXT NOT NULL PRIMARY KEY,
    internal_fact_ref TEXT NOT NULL,
    internal_user_id TEXT,
    billing_provider_key TEXT NOT NULL,
    external_event_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    billing_event_status TEXT NOT NULL,
    apply_outcome TEXT NOT NULL CHECK (
        apply_outcome IN ('active_applied', 'no_activation', 'needs_review')
    ),
    reason TEXT NOT NULL CHECK (
        reason IN (
            'ok',
            'ledger_status_not_accepted',
            'unknown_event_type',
            'missing_internal_user',
            'no_state_change'
        )
    ),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_billing_sub_apply_audit_user
    ON billing_subscription_apply_audit_events (internal_user_id);
CREATE INDEX IF NOT EXISTS idx_billing_sub_apply_audit_ref
    ON billing_subscription_apply_audit_events (internal_fact_ref);
CREATE INDEX IF NOT EXISTS idx_billing_sub_apply_audit_provider_external
    ON billing_subscription_apply_audit_events (billing_provider_key, external_event_id);
CREATE INDEX IF NOT EXISTS idx_billing_sub_apply_audit_occurred
    ON billing_subscription_apply_audit_events (occurred_at);

CREATE INDEX IF NOT EXISTS idx_billing_sub_apply_records_user
    ON billing_subscription_apply_records (internal_user_id);
