# PostgreSQL MVP Smoke Runbook

## Purpose
Quick manual smoke-run verifies that PostgreSQL MVP path is alive before deeper checks.

## Prerequisites
- Run from `backend` directory.
- `DATABASE_URL` must be set.
- Set `SLICE1_POSTGRES_MVP_SMOKE_ALLOW_MUTATING_TESTS` to explicit opt-in value: `1`, `true`, or `yes`.
- Use only isolated/dev database (never production or shared DB).

## Run
Minimal safe sequence (example values only, do not use real secrets in docs/history):

```bash
export DATABASE_URL="postgresql://dev_user:dev_password@localhost:5432/dev_db"
export SLICE1_POSTGRES_MVP_SMOKE_ALLOW_MUTATING_TESTS=1
python scripts/run_postgres_mvp_smoke.py
```

## Local isolated smoke (preferred for real validation)
Use this path to avoid manual `DATABASE_URL` mistakes and prevent any chance of touching shared/prod DB.

```bash
python scripts/run_postgres_mvp_smoke_local.py
```

What local runner does:
- Fails fast if `docker` / `docker compose` is unavailable.
- Starts an isolated disposable local PostgreSQL container via `docker-compose.postgres-smoke.yml`.
- Builds local-only `DATABASE_URL` automatically (loopback host + ephemeral mapped port).
- Waits for PostgreSQL readiness (`pg_isready`) with bounded retries/timeout before smoke step.
- Forces `SLICE1_POSTGRES_MVP_SMOKE_ALLOW_MUTATING_TESTS=1` in child smoke env.
- Runs existing `python scripts/run_postgres_mvp_smoke.py` unchanged as smoke source-of-truth.
- Cleans up container and disposable volume by default.

Optional debugging mode (retain container/volume only when run fails):

```bash
python scripts/run_postgres_mvp_smoke_local.py --keep-on-failure
```

Or set env flag:

```bash
export SLICE1_POSTGRES_MVP_SMOKE_LOCAL_KEEP_ON_FAILURE=1
python scripts/run_postgres_mvp_smoke_local.py
```

After investigation, remove retained local resources:

```bash
docker compose -p <project-name> -f docker-compose.postgres-smoke.yml down --volumes --remove-orphans
```

## CI validation
Use this path to verify reproducibility in Docker-enabled CI without any manual external `DATABASE_URL`.
Workflow expects Docker Engine + Docker Compose to be available on the selected CI runner image.
Workflow `backend-postgres-mvp-smoke-validation` now runs automatically on push to `main` when relevant backend/CI paths change.
Manual `workflow_dispatch` is still available as a fallback trigger.

Expected CI commands (from `backend`):

```bash
python -m pip install -e .[test]
docker --version
docker compose version
python -m pytest -q tests/test_run_postgres_mvp_smoke_local.py tests/test_run_postgres_mvp_smoke.py tests/test_run_slice1_retention_dry_run.py --junitxml=.test-reports/backend-smoke-helper-regression.xml
python scripts/run_postgres_mvp_smoke_local.py
```

Notes:
- CI path uses disposable local Docker PostgreSQL through `scripts/run_postgres_mvp_smoke_local.py`.
- Local runner sets local-only `DATABASE_URL` and mutating-test opt-in guard automatically for child smoke.
- Do not replace this with manual external `DATABASE_URL` smoke in CI.
- Cursor-driven manual dispatch still requires installed/authenticated `gh`, but normal push-triggered CI does not require local `gh`.
- Workflow publishes artifact `backend-postgres-mvp-smoke-validation-reports` from `backend/.test-reports`.
- Artifact includes:
  - `backend-smoke-helper-regression.xml` (JUnit for helper regression);
  - `backend-postgres-mvp-smoke-local.log` (raw smoke command output);
  - `backend-postgres-mvp-smoke-local-summary.txt` (safe tail summary for quick triage).
- Use the JUnit XML to distinguish outcomes in CI:
  - passed tests are reported as successful test cases;
  - skipped tests are explicitly marked as skipped with reason when provided by pytest;
  - failures/errors are represented as failed test cases with traceback metadata.
- Use smoke summary/log artifact to diagnose local-runner smoke failures when workflow red, without changing the manual external `DATABASE_URL` fallback path.

## Manual DATABASE_URL smoke (fallback path)
Use this only when local isolated path is unavailable and only against explicitly isolated/dev DB.

## What the helper does (3 steps)
1. Runs persistence entrypoint: `python -m app.persistence`.
2. Runs both opt-in integration test files in one pytest invocation:
   `pytest -q tests/test_postgres_slice1_process_env_async.py tests/test_postgres_migration_ledger_integration.py`.
3. Runs retention helper in dry-run-only path:
   `python scripts/run_slice1_retention_dry_run.py`.

## Expected side effects
- Helper enables PostgreSQL repos via `SLICE1_USE_POSTGRES_REPOS=1`.
- Opt-in is required because the pytest step may perform targeted insert/delete or ledger checks against the database pointed to by `DATABASE_URL`.
- Retention helper step is dry-run only and is intended to validate retention wiring without deleting data.

## Success criteria
- Command exits with code `0`.
- All three subprocess steps complete without error.

## Fail-fast troubleshooting
- No `DATABASE_URL`: set it and rerun (helper fails fast by design).
- Missing/falsey `SLICE1_POSTGRES_MVP_SMOKE_ALLOW_MUTATING_TESTS`: set `1`, `true`, or `yes` and rerun only on isolated/dev DB.
- Subprocess/test failure: inspect failing subprocess output and fix that error first.
- Wrong/shared/production DB risk: stop run, switch `DATABASE_URL` to isolated/dev DB, rerun.
- Retention dry-run step failure: inspect `scripts/run_slice1_retention_dry_run.py` subprocess output and fix env/config issue first.

## Security notes
- Do not log or paste raw `DATABASE_URL`.
- Prefer `python scripts/run_postgres_mvp_smoke_local.py` for real validation.
- Use only isolated/dev DB; never production/shared DB.
- `SLICE1_POSTGRES_MVP_SMOKE_ALLOW_MUTATING_TESTS` is a mandatory operator guard for mutating smoke tests.
- Helper performs targeted insert/delete in integration test path.
- Retention helper in this flow is dry-run only and must not be treated as destructive cleanup.
