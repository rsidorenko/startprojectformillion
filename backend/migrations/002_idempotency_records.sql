-- Idempotency key state (IdempotencyRepository / IdempotencyRecord).
CREATE TABLE IF NOT EXISTS idempotency_records (
    idempotency_key TEXT NOT NULL PRIMARY KEY,
    completed BOOLEAN NOT NULL
);
