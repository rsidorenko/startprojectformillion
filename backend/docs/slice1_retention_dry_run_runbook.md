# Slice-1 retention dry-run helper

## Purpose

Operator shortcut to run manual retention cleanup **in dry-run only**: the helper sets child environment and spawns a single `python -m app.persistence.slice1_retention_manual_cleanup_main` (counts eligible rows, no `DELETE`).

## Prerequisites

- Run from the `backend` directory (where `pyproject.toml` and `src/` live).
- Python 3.12+ and installed backend dependencies.
- The child `python -m app....` process must be able to import `app` (e.g. `PYTHONPATH` includes `src`, same as pytest in `pyproject.toml`).
- Non-empty `DATABASE_URL` after trim in the **current** process environment before invoking the helper (see fail-fast).
- Prefer an isolated or dev database, not production.

## Run

```bash
python scripts/run_slice1_retention_dry_run.py
```

## Environment

- **Required before helper:** `DATABASE_URL` (non-empty after `trim`). If missing or whitespace-only, the helper raises `RuntimeError` immediately; it does **not** print the URL value.
- **Always in child env:** `SLICE1_RETENTION_DRY_RUN=1` (forced by the helper).
- **Defaults (only if the variable is missing or empty after `trim`):** `BOT_TOKEN=1234567890tok`, `SLICE1_RETENTION_TTL_SECONDS=86400`, `SLICE1_RETENTION_BATCH_LIMIT=100`, `SLICE1_RETENTION_MAX_ROUNDS=5`.

If you already set `BOT_TOKEN` or those `SLICE1_RETENTION_*` values (non-blank), the helper leaves them unchanged. All other keys from `os.environ.copy()` are passed through unchanged.

## What the helper does

1. `RuntimeError` if `DATABASE_URL` is missing/blank after `trim` (no subprocess).
2. Builds `child_env` from `os.environ.copy()`; sets `SLICE1_RETENTION_DRY_RUN=1`; applies defaults above only when needed.
3. One `subprocess.run` with `check=True`, `cwd` = `backend`, argv: `python -m app.persistence.slice1_retention_manual_cleanup_main`.

## Expected stdout / success

- Process exit code `0` when the child exit code is `0` (non-zero from the child raises `CalledProcessError` with `check=True`).
- The child prints **one** summary line on stdout, same shape as the manual cleanup entrypoint, for example:

`slice1_retention_cleanup dry_run=True cutoff=<iso8601> audit_rows=<n> idempotency_rows=<n> rounds=0`

(Exact numbers and timestamp depend on data; in dry-run, `dry_run=True` and `rounds=0` per current code.)

## Fail-fast troubleshooting

- **Helper `RuntimeError` about `DATABASE_URL`:** set a non-empty `DATABASE_URL` after trim; never paste the raw URL into public channels.
- **`ConfigurationError` or other failure from the child** (subprocess): inspect stderr from `python -m app.persistence.slice1_retention_manual_cleanup_main` (common causes: invalid DSN shape, `sslmode` policy for non-local `APP_ENV`, invalid integer retention values, etc.).
- **`app` not importable in child:** fix `PYTHONPATH` / install as for local `backend` runs.
- This runbook does not cover schedulers, cron, systemd, Kubernetes, or CI.

## Security notes

- Do not log or paste raw `DATABASE_URL` (credentials).
- The default `BOT_TOKEN` placeholder is for local smoke only; use a real secret from your vault for sensitive databases.
- Dry-run still connects to the database; use only appropriate environments.

There is no automatic rollback or additional automation beyond what the helper and child module already do.
