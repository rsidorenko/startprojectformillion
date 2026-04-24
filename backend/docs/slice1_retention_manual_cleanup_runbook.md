# Slice-1 manual retention cleanup (CLI)

## Purpose

One-off process that connects to PostgreSQL and either **counts** rows eligible for slice-1 retention (dry-run) or **deletes** them in batches: old rows in `slice1_audit_events`, and **completed** old rows in `idempotency_records`. Implemented in `app.persistence.slice1_retention_manual_cleanup` and started via `slice1_retention_manual_cleanup_main`.

## Prerequisites

- Run from the `backend` directory of this repo.
- Python can import the `app` package (same layout as tests: set `PYTHONPATH=src`, matching `[tool.pytest.ini_options] pythonpath` in `pyproject.toml`).
- Python 3.12+ (project `requires-python`).
- Target PostgreSQL has the expected tables (`slice1_audit_events`, `idempotency_records`).
- Use only an **isolated or dev** database — not production (see Security notes).

## Required environment variables

| Variable | Role |
|----------|------|
| `BOT_TOKEN` | Read by `load_runtime_config()`; must be non-empty and length ≥ 10 (same boundary as the rest of the backend). |
| `DATABASE_URL` | Non-empty after trim; used to open an `asyncpg` pool. Must start with `postgresql://` or `postgres://`. For non-local `APP_ENV`, the URL must include an explicit `sslmode=` query parameter (see `validate_runtime_config` in `app.security.config`). |
| `SLICE1_RETENTION_TTL_SECONDS` | Positive integer; rows older than `now_utc - TTL` are eligible. |
| `SLICE1_RETENTION_BATCH_LIMIT` | Positive integer; max rows deleted **per table per batch round** (each round runs one batch delete on audit and one on idempotency). |
| `SLICE1_RETENTION_MAX_ROUNDS` | Positive integer; upper bound on delete rounds in one process (stops early when both deletes remove zero rows). |

### Optional

| Variable | Role |
|----------|------|
| `SLICE1_RETENTION_DRY_RUN` | If unset or empty: **not** dry-run (deletes run). If set: dry-run when value (trimmed, lowercased) is `1`, `true`, or `yes`; otherwise treated as **not** dry-run. |

Other `load_runtime_config` inputs exist (`APP_ENV`, `DEBUG`) but are not retention-specific; `APP_ENV` defaults to `development` when unset and affects the `DATABASE_URL` / `sslmode` rule above.

## Before delete mode (recommended)

Before you run the manual entrypoint in **delete** mode (i.e. where `SLICE1_RETENTION_DRY_RUN` is not set to a dry-run truthy value; see [Optional](#optional)), run the dry-run helper from `backend` (same [Prerequisites](#prerequisites) as the CLI below):

```bash
python scripts/run_slice1_retention_dry_run.py
```

The helper spawns the same `slice1_retention_manual_cleanup_main` process with **`SLICE1_RETENTION_DRY_RUN=1` in the child environment** (set by the helper, not the operator). That lets you confirm **eligible row counts** and **catch env/config issues** (for example a bad DSN) before any `DELETE`, and **reduces the risk** of an accidental destructive run. For defaults, `DATABASE_URL` requirements, and full helper behavior, see `slice1_retention_dry_run_runbook.md` in this `docs` folder (without repeating that runbook here).

## Run

```bash
python -m app.persistence.slice1_retention_manual_cleanup_main
```

(From `backend`, with `PYTHONPATH` including `src` so `app` resolves.)

## What the command does

1. Calls `load_runtime_config()` (validates `BOT_TOKEN`, `DATABASE_URL` shape, and related rules).
2. Loads retention settings from the `SLICE1_RETENTION_*` environment variables (`load_retention_settings_from_env`).
3. Opens a small `asyncpg` pool (`min_size=1`, `max_size=4`) to `DATABASE_URL`.
4. On one acquired connection, runs `run_slice1_retention_cleanup`:
   - **Dry-run:** runs `COUNT(*)` for eligible audit rows and eligible **completed** idempotency rows; does **not** delete.
   - **Delete:** repeatedly executes batched `DELETE ... FOR UPDATE SKIP LOCKED` for both tables until both batches delete zero rows or `max_rounds` is reached.
5. Closes the pool.
6. Prints **one** summary line to stdout (space-separated tokens).

## Expected stdout

A single line of the form:

```text
slice1_retention_cleanup dry_run=<bool> cutoff=<iso8601> audit_rows=<int> idempotency_rows=<int> rounds=<int>
```

Example shape (values illustrative only):

```text
slice1_retention_cleanup dry_run=True cutoff=2026-04-23T12:00:00+00:00 audit_rows=42 idempotency_rows=7 rounds=0
```

- **Dry-run:** `dry_run=True`, `audit_rows` / `idempotency_rows` are **counts** of rows that would be eligible; `rounds` is always `0`.
- **Delete:** `dry_run=False`, `audit_rows` / `idempotency_rows` are **cumulative deleted row counts** over all rounds; `rounds` is how many loop iterations ran (stops when both deletes return zero or cap hit).

## Success criteria

- Process exits with code `0`.
- The summary line appears on stdout as above.

## Fail-fast troubleshooting

- **`ConfigurationError: missing or empty configuration: BOT_TOKEN`** — set a valid `BOT_TOKEN` (non-empty, length ≥ 10).
- **`ConfigurationError: missing or empty configuration: DATABASE_URL`** — set `DATABASE_URL` after `load_runtime_config` (empty means no DSN for this entrypoint).
- **`ConfigurationError: invalid configuration: DATABASE_URL`** — wrong scheme (must be `postgresql://` or `postgres://`), or non-local `APP_ENV` without `sslmode=` in the URL.
- **Retention env errors** (`missing or empty`, `invalid configuration`, or non-positive int) — fix `SLICE1_RETENTION_TTL_SECONDS`, `SLICE1_RETENTION_BATCH_LIMIT`, or `SLICE1_RETENTION_MAX_ROUNDS` (all required positive integers).
- **Import / module errors** — run from `backend` with `PYTHONPATH=src` (or install the package so `app` is on `PYTHONPATH`).
- **DB connectivity / SQL errors** — fix network, credentials, migrations, or permissions; the CLI does not implement automatic rollback of partial deletes.

## Security notes

- Use **only** an isolated or dev database when experimenting; mistakes are destructive in delete mode.
- **Completed** `idempotency_records` rows older than the cutoff **can be deleted**; too small a TTL can delete data you still rely on.
- **Never** log, paste, or ticket a raw `DATABASE_URL` (credentials inside). Same care for `BOT_TOKEN`.
- This runbook does **not** cover schedulers, cron, systemd, Kubernetes, or future automated retention jobs — only this manual CLI.
