-- UC-01 outbound delivery ledger: idempotency_key-aligned send state (no message body, no update payload).
CREATE TABLE IF NOT EXISTS slice1_uc01_outbound_deliveries (
    idempotency_key TEXT NOT NULL PRIMARY KEY,
    delivery_status TEXT NOT NULL CHECK (delivery_status IN ('pending', 'sent')),
    telegram_message_id BIGINT NULL,
    last_attempt_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
