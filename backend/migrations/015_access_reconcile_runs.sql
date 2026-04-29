-- Durable runtime evidence for expired access reconcile runs (safe operational heartbeat).
CREATE TABLE IF NOT EXISTS access_reconcile_runs (
    run_id UUID PRIMARY KEY,
    task_name TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ NULL,
    status TEXT NOT NULL,
    reconciled_rows INTEGER NOT NULL DEFAULT 0,
    error_class TEXT NULL,
    error_message TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT access_reconcile_runs_status_check CHECK (status IN ('started', 'completed', 'failed')),
    CONSTRAINT access_reconcile_runs_reconciled_rows_non_negative CHECK (reconciled_rows >= 0)
);

CREATE INDEX IF NOT EXISTS idx_access_reconcile_runs_task_started_at
    ON access_reconcile_runs (task_name, started_at DESC);
