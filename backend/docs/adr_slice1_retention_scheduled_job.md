# ADR: Scheduled slice-1 PostgreSQL retention (future work)

## Status

- **Design / documentation only.** This step does **not** change production code under `backend/src/`, and does **not** introduce a scheduler, CI wiring, or runtime automation.
- **Not implemented:** a future scheduled job is **only specified here** for alignment before any coding or ops manifests.

## Context

Manual retention exists today: core logic in `app.persistence.slice1_retention_manual_cleanup`, CLI entry in `app.persistence.slice1_retention_manual_cleanup_main`, dry-run script `backend/scripts/run_slice1_retention_dry_run.py`, and runbooks `slice1_retention_manual_cleanup_runbook.md` / `slice1_retention_dry_run_runbook.md`. A future **scheduled** job should align with the same data model and the same business rules without duplicating SQL or bypassing config boundaries.

## Scope and boundaries

**In scope (slice-1 retention only):**

- `slice1_audit_events` by row age (cutoff from TTL).
- `idempotency_records` where `completed = true`, by row age (same cutoff semantics as today’s core).

**Out of scope for this ADR and for slice-1 retention in general:**

- Billing, issuance, and admin data stores or their retention policies.
- Cron, systemd, Kubernetes, CI, background workers, or new helper scripts (no implementation in this document).
- Any change to how slice-1 application code writes audit or idempotency rows (not part of this ADR step).

## Reuse contract (future scheduled implementation)

- The scheduled job **must** reuse the existing core: `run_slice1_retention_cleanup` and `RetentionSettings` from `backend/src/app/persistence/slice1_retention_manual_cleanup.py`.
- The scheduled path **must not** duplicate the retention SQL (same queries and batching behavior should remain in that module only).
- **Not** the scheduler by themselves: the manual CLI, stdout `print` summary, and the subprocess-based dry-run helper are operator tooling; a future wrapper should call the same **core** function with production-appropriate I/O, not re-encode SQL elsewhere.

## Safety guardrails

- **Dry-run vs delete** must stay explicitly distinct: dry-run performs counts only; delete mode runs batched deletes (as in core logic today).
- **Destructive mode** must be a separate **explicit opt-in** for automation (stricter than “forgot to set dry-run”); the exact mechanism is left to a later implementation, but the requirement is fixed here.
- **Batch limit** and **max rounds** remain mandatory upper bounds in configuration (align with `SLICE1_RETENTION_BATCH_LIMIT` and `SLICE1_RETENTION_MAX_ROUNDS` semantics).
- **Overlapping runs** (e.g. two job instances) are an **operational risk**: double load, partial progress harder to reason about, and should be mitigated in ops design (lock/lease, single instance, or equivalent — **open question** below, not specified as code here).
- **Completed idempotency** must not be pruned with an aggressive TTL: TTL must be **conservative** relative to acceptable replay and operational windows; this policy is **independent** of billing, issuance, and admin lifecycles.

## Config / env surface

- Reuse existing boundaries: **`load_runtime_config()`** for DSN and shared rules (e.g. `BOT_TOKEN`, `DATABASE_URL` validation) as the manual entrypoint does today.
- Relevant **environment family** (names as in code today; values supplied via env/secret store, not hardcoded):
  - `DATABASE_URL`
  - `BOT_TOKEN`
  - `SLICE1_RETENTION_TTL_SECONDS`
  - `SLICE1_RETENTION_BATCH_LIMIT`
  - `SLICE1_RETENTION_MAX_ROUNDS`
  - `SLICE1_RETENTION_DRY_RUN`
- **No hardcoded secrets** in code or in job definitions introduced by this design note.

## Observability / audit expectations

- **One** low-cardinality **summary** per run (compatible with a single line of aggregate metrics: dry-run flag, cutoff, total counts, rounds) — not bulk row dumps.
- **Do not** log raw `DATABASE_URL` (or equivalent connection secrets).
- **Do not** log idempotency keys or correlation ids **as lists** (or in bulk); prefer **counts and aggregates** only.
- A future need for a **durable audit trail of job runs** (who/when/result) is acknowledged as an open design point; it must not leak sensitive payloads (see open questions).

## Rollout strategy

1. **Manual-only** baseline: operators use existing CLI and runbooks; no schedule.
2. **Scheduled dry-run** in non-production: periodic counts-only runs to validate config, connectivity, and expected volumes.
3. **Narrow scheduled delete** in production only after non-prod validation and explicit opt-in for that environment.
4. **Gradual expansion** of frequency or scope only after repeated observable safe runs.

## Acceptance criteria (smallest safe first implementation, when built)

- Calls **`run_slice1_retention_cleanup`**; uses **`RetentionSettings`**; **no** duplicated retention SQL in the new path.
- **Explicit trigger** or a **very narrow** schedule; default posture **dry-run-first** where automation is enabled.
- **Observable** process exit and a **single summary** outcome suitable for external monitoring/alerting.
- **No** changes to billing, issuance, or admin domains for the sake of this job.

## Risks / open questions

- **Overlap control:** how to ensure at most one destructive retention run at a time per environment (or acceptable concurrency model).
- **TTL vs replay window:** choosing `SLICE1_RETENTION_TTL_SECONDS` for completed idempotency relative to product risk of replay.
- **Incidents:** partial delete rounds or mid-run failure — how to triage and whether back-off / freeze is required before retry.
- **Job audit trail** without logging secrets, keys, or correlation id bulk lists; may be metrics plus structured, redacted run metadata only.
