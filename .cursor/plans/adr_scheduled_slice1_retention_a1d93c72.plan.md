---
name: ADR scheduled slice1 retention
overview: "План: добавить один design-only ADR в `backend/docs/adr_slice1_retention_scheduled_job.md` — границы, reuse ядра `run_slice1_retention_cleanup`, guardrails, config/observability, rollout и acceptance criteria; без кода, без CI/scheduler."
todos:
  - id: add-adr-md
    content: "Add backend/docs/adr_slice1_retention_scheduled_job.md (full ADR: scope, reuse, guardrails, config, observability, rollout, acceptance criteria, out-of-scope)"
    status: pending
isProject: false
---

# ADR: future scheduled slice-1 retention (docs-only)

## Deliverable

- **One new file:** [backend/docs/adr_slice1_retention_scheduled_job.md](backend/docs/adr_slice1_retention_scheduled_job.md)  
- **No other changes** (per request: no `backend/src/`, no scripts, tests, migrations, CI).

## Grounding in current code (reuse contract)

- **Core business logic to keep as single source of truth:** `run_slice1_retention_cleanup` in [backend/src/app/persistence/slice1_retention_manual_cleanup.py](backend/src/app/persistence/slice1_retention_manual_cleanup.py) (already implements dry-run `COUNT` vs batched `DELETE`, `RetentionSettings`, validation).
- **Env/DSN loading today:** [backend/src/app/persistence/slice1_retention_manual_cleanup_main.py](backend/src/app/persistence/slice1_retention_manual_cleanup_main.py) uses `load_runtime_config()` + `SLICE1_RETENTION_*`; scheduled job design should **not** reimplement SQL; may eventually add a *thin* entrypoint that calls the same `run_slice1_retention_cleanup` with the same settings model — that is *future* implementation, only described in the ADR.
- **Operator dry-run path (unchanged by this doc):** [backend/scripts/run_slice1_retention_dry_run.py](backend/scripts/run_slice1_retention_dry_run.py) and [backend/docs/slice1_retention_dry_run_runbook.md](backend/docs/slice1_retention_dry_run_runbook.md).

## Document sections to include (checklist for the markdown body)

1. **Status / scope** — design-only; this repository step does not change production code; out of scope: cron/k8s/systemd/CI, new workers, new helper scripts.
2. **Scope and boundaries** — what tables/policies (audit + completed idempotency by age); what is *not* in scope (billing, issuance, admin data, non-slice-1 stores).
3. **Reuse vs non-reuse** — **reuse:** `run_slice1_retention_cleanup` + `RetentionSettings` + validation; **do not duplicate** embedded SQL from the same module. **Not reused as-is for scheduling:** CLI `print`, subprocess wrapper, ad-hoc operator defaults from `run_slice1_retention_dry_run.py` in production.
4. **Safety guardrails** — mandatory separation of **dry-run** (counts only) vs **delete**; opt-in for destructive mode (e.g. explicit flag/env gate beyond today’s `SLICE1_RETENTION_DRY_RUN` semantics — described as requirement, not implemented); cap `max_rounds` + batch size; **TTL policy for idempotency** documented as separate from other product SLAs; avoid parallel overlapping runs (design note).
5. **Config / env** — `DATABASE_URL` / `BOT_TOKEN` / `load_runtime_config` rules as in existing runbooks; `SLICE1_RETENTION_TTL_SECONDS`, `SLICE1_RETENTION_BATCH_LIMIT`, `SLICE1_RETENTION_MAX_ROUNDS`, `SLICE1_RETENTION_DRY_RUN`; no hardcoded secrets; any future scheduler should inject config through the same boundaries.
6. **Observability & audit** — one structured **summary** line (compatible with current stdout shape); **do not** log raw `DATABASE_URL`; **do not** log idempotency keys or correlation ids as bulk lists; counts/sums only; optional mention of run identity (e.g. job name) without PII.
7. **Policy separation** — slice-1 retention (audit + completed idempotency) remains a **distinct** operational policy from billing, issuance, and admin retention.
8. **Rollout** — path from manual-only → dry-run in staging/scheduled → narrow production schedule → full schedule; pre-prod dry-run before delete in each environment.
9. **Smallest safe first implementation (acceptance criteria)** — e.g. explicit/manual-or-narrow trigger first, dry-run as default in automation until approved, observable exit code + summary, reuse core function, no new SQL.
10. **Risks & open questions** — e.g. overlapping job instances, TTL vs replay window, incident response if partial delete.

## Implementation note (after plan approval)

- Apply as a **single add-file** commit adding only the markdown under `backend/docs/`.
