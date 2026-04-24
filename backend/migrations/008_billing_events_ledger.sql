-- Append-only billing events ledger (BillingEventsLedgerRepository / BillingEventLedgerRecord).
-- Normalized scalars only: no raw provider payload, no secrets, no JSONB.
CREATE TABLE IF NOT EXISTS billing_events_ledger (
    internal_fact_ref TEXT NOT NULL,
    billing_provider_key TEXT NOT NULL,
    external_event_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_effective_at TIMESTAMPTZ NOT NULL,
    event_received_at TIMESTAMPTZ NOT NULL,
    internal_user_id TEXT,
    checkout_attempt_id TEXT,
    amount_minor_units BIGINT,
    currency_code TEXT,
    status TEXT NOT NULL CHECK (status IN ('accepted', 'duplicate', 'ignored')),
    ingestion_correlation_id TEXT NOT NULL,
    PRIMARY KEY (internal_fact_ref),
    CONSTRAINT billing_events_ledger_provider_external_uniq UNIQUE (billing_provider_key, external_event_id)
);

CREATE INDEX IF NOT EXISTS idx_billing_events_ledger_user_accepted
    ON billing_events_ledger (internal_user_id, event_received_at, internal_fact_ref)
    WHERE status = 'accepted' AND internal_user_id IS NOT NULL;
