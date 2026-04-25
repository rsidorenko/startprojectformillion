-- Durable config issuance *operational* state (UC-06 / UC-07 slice): opaque provider refs
-- and issued/revoked only. No raw config, no PEM, no access credentials, no JSONB/BYTEA
-- of arbitrary payloads. `provider_issuance_ref` must be an opaque, non-secret handle
-- (never raw VPN config or secret material).

CREATE TABLE IF NOT EXISTS issuance_state (
    internal_user_id TEXT NOT NULL,
    issue_idempotency_key TEXT NOT NULL,
    issuance_state TEXT NOT NULL CHECK (issuance_state IN ('issued', 'revoked')),
    provider_issuance_ref TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ NULL,
    CONSTRAINT pk_issuance_state PRIMARY KEY (internal_user_id, issue_idempotency_key),
    CONSTRAINT ck_issuance_state_ref_len
        CHECK (char_length(provider_issuance_ref) >= 1 AND char_length(provider_issuance_ref) <= 1024),
    CONSTRAINT ck_issuance_state_idem_len
        CHECK (char_length(issue_idempotency_key) >= 1 AND char_length(issue_idempotency_key) <= 512),
    CONSTRAINT ck_issuance_state_user_len
        CHECK (char_length(internal_user_id) >= 1 AND char_length(internal_user_id) <= 256)
);

CREATE INDEX IF NOT EXISTS idx_issuance_state_internal_user_id
    ON issuance_state (internal_user_id);

CREATE INDEX IF NOT EXISTS idx_issuance_state_issuance_state
    ON issuance_state (issuance_state);

CREATE INDEX IF NOT EXISTS idx_issuance_state_updated_at
    ON issuance_state (updated_at);
