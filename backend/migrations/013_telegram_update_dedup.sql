-- Durable/shared Telegram update dedup keys for transport boundary replay protection.
-- Stores only hashed dedup key + bounded buckets/timestamps; no raw update/user/chat data.
CREATE TABLE IF NOT EXISTS telegram_update_dedup (
    dedup_key_hash TEXT NOT NULL PRIMARY KEY,
    command_bucket TEXT NOT NULL CHECK (command_bucket IN ('status', 'access_resend', 'other')),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    source_marker TEXT NULL,
    CONSTRAINT ck_telegram_update_dedup_key_hash_len
        CHECK (char_length(dedup_key_hash) = 64),
    CONSTRAINT ck_telegram_update_dedup_expiry_order
        CHECK (expires_at > first_seen_at),
    CONSTRAINT ck_telegram_update_dedup_source_marker_len
        CHECK (source_marker IS NULL OR (char_length(source_marker) >= 1 AND char_length(source_marker) <= 64))
);

CREATE INDEX IF NOT EXISTS idx_telegram_update_dedup_expires_at
    ON telegram_update_dedup (expires_at);
