-- Subscription lifecycle v1: bounded customer-facing active window storage.
ALTER TABLE subscription_snapshots
    ADD COLUMN IF NOT EXISTS active_until_utc TIMESTAMPTZ NULL;

ALTER TABLE subscription_snapshots
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
