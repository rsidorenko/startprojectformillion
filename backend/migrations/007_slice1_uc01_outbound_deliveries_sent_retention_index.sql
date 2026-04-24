-- Retention-friendly index for UC-01 outbound delivery ledger (sent rows only, time-ordered delete batches).
CREATE INDEX IF NOT EXISTS idx_slice1_uc01_outbound_deliveries_sent_created_at
    ON slice1_uc01_outbound_deliveries (created_at)
    WHERE delivery_status = 'sent';
