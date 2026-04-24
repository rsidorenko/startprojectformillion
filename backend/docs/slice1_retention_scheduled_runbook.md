# Slice-1 scheduled retention (wrapper)

## Purpose

This is the **scheduled entrypoint** module `app.persistence.slice1_retention_scheduled_main`: a thin wrapper around the same slice-1 retention **core** as the manual CLI (`run_slice1_retention_cleanup`, `RetentionSettings`, and `load_retention_settings_from_env` from the manual path). It is meant for **automation-style** invocation (e.g. future cron, worker, or platform job), not a replacement for one-off operator tooling.

**Default posture is dry-run-first:** unless an explicit **scheduled-only** opt-in is set, the wrapper **forces** `dry_run=True` regardless of other environment settings. Details: [Relationship with `SLICE1_RETENTION_DRY_RUN`](#relationship-with-slice1_retention_dry_run). For the manual CLI, dry-run helper, and full SQL/stdout semantics of the shared core, see the existing runbooks in this folder (`slice1_retention_manual_cleanup_runbook.md`, `slice1_retention_dry_run_runbook.md`) without duplicating them here.

## Prerequisites

- Run from the **`backend`** directory of this repository.
- Python can import the `app` package (align with the manual runbook: e.g. `PYTHONPATH=src` as in `pyproject` / tests).
- Python 3.12+ (`requires-python` in the project).
- Use an **isolated or dev** database for first runs and experiments — not production until policy and opt-in are intentional (see Security notes).
- The database must have the expected slice-1 tables and migrations applied (same as manual retention).

## Required environment variables

| Variable | Role |
|----------|------|
| `BOT_TOKEN` | Read by `load_runtime_config()`; must satisfy the same validation as the rest of the backend (non-empty, length ≥ 10). |
| `DATABASE_URL` | After trim, non-empty; `postgresql://` or `postgres://`. Non-local `APP_ENV` may require `sslmode=` in the URL (see `app.security.config`). |
| `SLICE1_RETENTION_TTL_SECONDS` | Positive integer; age cutoff for eligible rows. |
| `SLICE1_RETENTION_BATCH_LIMIT` | Positive integer; cap per table per batch round. |
| `SLICE1_RETENTION_MAX_ROUNDS` | Positive integer; max rounds in one process. |
| `SLICE1_RETENTION_SCHEDULED_ENABLE_DELETE` | **Scheduled-only** explicit opt-in for passing through loaded retention settings (see below). If unset, empty, or not truthy, the wrapper **always** runs in dry-run. Truthy: `1`, `true`, `yes` (trimmed, case-insensitive). |

Other `load_runtime_config` inputs (`APP_ENV`, `DEBUG`, etc.) follow global backend rules; they are not slice-1-specific. Do not put secrets in logs (see [Security notes](#security-notes)).

## Relationship with `SLICE1_RETENTION_DRY_RUN`

- **Without** a truthy `SLICE1_RETENTION_SCHEDULED_ENABLE_DELETE`, the wrapper **forces** `dry_run=True` on the settings passed to the core, **even if** the parent environment has `SLICE1_RETENTION_DRY_RUN=0` or unset in a way that would otherwise imply delete in the manual entrypoint.
- **With** a truthy scheduled opt-in, the wrapper uses **loaded** settings from `load_retention_settings_from_env()` as-is. **Delete** in that case is only possible when those loaded settings are **not** dry-run (i.e. `SLICE1_RETENTION_DRY_RUN` is unset/empty, or not one of `1` / `true` / `yes` per the manual loader). If the loaded settings are dry-run, the run remains a count-only dry run even with opt-in.

## Run

```bash
python -m app.persistence.slice1_retention_scheduled_main
```

From `backend`, with `PYTHONPATH` including `src` so `app` resolves (same as the manual runbook command pattern).

## What the wrapper does

- Loads runtime config and retention settings via the same paths as the manual entrypoint (no second SQL layer).
- Calls **`run_slice1_retention_cleanup`** with **effective** settings: forced dry-run when scheduled delete is not opted in; otherwise the loaded `RetentionSettings`.
- **No duplicate retention SQL** — all batching and queries stay in `slice1_retention_manual_cleanup`.
- Prints **one** space-separated summary line to stdout (see [Expected stdout](#expected-stdout)).

## Expected stdout

A single line, prefix and low-cardinality fields only:

```text
slice1_retention_scheduled_cleanup dry_run=<bool> cutoff=<iso8601> audit_rows=<int> idempotency_rows=<int> outbound_delivery_rows_matched=<int> outbound_delivery_rows_deleted=<int> rounds=<int>
```

Field meanings match the shared core: dry-run = counts (including `outbound_delivery_rows_matched` for eligible **`sent`** ledger rows; `pending` excluded); delete = cumulative deleted row counts and rounds (`outbound_delivery_rows_deleted` for ledger **`sent`** rows only). Example shape (values illustrative):

```text
slice1_retention_scheduled_cleanup dry_run=True cutoff=2026-04-24T12:00:00+00:00 audit_rows=10 idempotency_rows=2 outbound_delivery_rows_matched=0 outbound_delivery_rows_deleted=0 rounds=0
```

## Safe usage guidance

1. Prefer **dry-run path first** (no truthy `SLICE1_RETENTION_SCHEDULED_ENABLE_DELETE`, or explicit `SLICE1_RETENTION_DRY_RUN=1`) on a non-prod database to confirm counts, config, and connectivity.
2. Enable **destructive** behavior only with **both** explicit scheduled opt-in and a deliberate `SLICE1_RETENTION_DRY_RUN` posture that does not request dry-run in loaded settings, after the above validation.

## Fail-fast troubleshooting

| Symptom / error | What to check |
|-----------------|---------------|
| `ConfigurationError: missing or empty configuration: DATABASE_URL` | Blank or missing `DATABASE_URL` after `load_runtime_config` trim. |
| `ConfigurationError: invalid configuration: DATABASE_URL` / `BOT_TOKEN` / retention ints | DSN shape, `sslmode` for non-local env, or non-positive `SLICE1_RETENTION_*` integers. |
| Import / `ModuleNotFoundError: app` | Run from `backend` with `PYTHONPATH=src` (or install so `app` is importable). |
| DB connectivity, auth, or SQL errors | Network, credentials, migrations, permissions; partial deletes are not auto-rolled back. |

## CI (GitHub Actions)

- Workflow `backend-postgres-mvp-smoke-validation` includes job `slice1-postgres-retention-integration`: an isolated GitHub `services.postgres` database with a **service-local** `DATABASE_URL` in that job only (not a stored secret) so opt-in **integration** tests in `tests/test_postgres_retention_*_integration.py` run in CI instead of skipping. Locally, those tests still **skip** without a real `DATABASE_URL` — set one only for isolated/dev DBs. Destructive scheduled **delete** behavior remains explicitly test-scoped (e.g. env + `SLICE1_RETENTION_SCHEDULED_ENABLE_DELETE` as used in the scheduled delete integration test, not a blind prod trigger).

## Security notes

- **Never** log, paste, or commit raw `DATABASE_URL` or `BOT_TOKEN`; they carry credentials and access.
- **Delete** mode (when opt-in and loaded non-dry-run) is **destructive** — wrong DB or TTL can remove data you still need.
- **Completed** `idempotency_records` older than the cutoff can be deleted; an overly small TTL is an **operational and replay** risk; tune conservatively.

## Out of scope

This runbook does **not** define or supply: cron, systemd, Kubernetes, CI, or other **scheduler manifests**; generic automation platform setup; or guarantees about rollback or run overlap control. Those are operational choices outside this file. Design background: `adr_slice1_retention_scheduled_job.md` and `plan_slice1_retention_scheduled_minimal_impl.md`.

---

**Assumptions (this document):** Operators run the module from `backend` with a working `app` import path; the implementation matches the current `slice1_retention_scheduled_main` module; secret handling follows the same rules as the manual runbook. **Security risks (summary):** exposure of DSN or tokens; accidental destructive runs against the wrong environment; aggressive TTL for completed idempotency rows; overlap of multiple concurrent delete jobs (not mitigated in code here).
