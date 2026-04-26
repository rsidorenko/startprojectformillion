# PostgreSQL MVP Smoke Runbook

Primary go/no-go operator flow lives in:
- `backend/docs/mvp_release_readiness_runbook.md`
- `backend/docs/mvp_release_artifact_manifest.md`

## Purpose
Quick manual smoke-run verifies that PostgreSQL MVP path is alive before deeper checks. The canonical smoke helper
does not start the Telegram HTTP webhook ASGI app (`app.runtime.telegram_webhook_main`); use long-polling or a
separate webhook process only when you intentionally enable `TELEGRAM_WEBHOOK_HTTP_ENABLE`.

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

## Local Docker smoke gate (preferred)
Use this local developer/operator gate to avoid manual `DATABASE_URL` mistakes and prevent touching shared/production DB.

Prerequisites:
- Docker Engine is installed and running.
- Docker Compose (`docker compose` or `docker-compose`) is available.
- Run from `backend`.
- Use only local disposable Docker PostgreSQL for this gate.

```bash
python scripts/run_postgres_mvp_smoke_local.py
```

What this gate verifies (through canonical helper):
- Fails fast if `docker` / `docker compose` is unavailable.
- Starts an isolated disposable local PostgreSQL container via `docker-compose.postgres-smoke.yml`.
- Builds local-only `DATABASE_URL` automatically (loopback host + ephemeral mapped port).
- Waits for PostgreSQL readiness (`pg_isready`) with bounded retries/timeout before smoke step.
- Forces `SLICE1_POSTGRES_MVP_SMOKE_ALLOW_MUTATING_TESTS=1` in child smoke env.
- Runs canonical `python scripts/run_postgres_mvp_smoke.py` unchanged as smoke source-of-truth:
  1. migrations;
  2. targeted postgres tests;
  3. retention dry-run;
  4. operator billing ingest/apply e2e;
  5. access fulfillment e2e.
- Cleans up container and disposable volume by default.
- Returns exit code `0` on success.

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
CI blocking smoke path runs canonical helper directly against isolated GitHub Actions `services.postgres`.
This path does not require local Docker smoke wrapper execution in CI.
Workflow `backend-postgres-mvp-smoke-validation` now runs automatically on push to `main` when relevant backend/CI paths change.
Manual `workflow_dispatch` is still available as a fallback trigger.

## MVP release preflight (targeted, no Docker)
Use a single lightweight targeted preflight command for production-like release readiness contracts without Docker and
without full-suite runtime:

```bash
python scripts/run_mvp_release_preflight.py
```

What it covers (targeted pytest groups only):
- canonical smoke/contracts (`test_run_postgres_mvp_smoke`, `test_run_postgres_mvp_access_fulfillment_e2e`,
  `test_postgres_mvp_smoke_ci_evidence_contract`);
- Telegram runtime hardening contracts (webhook ingress/main/evidence + dispatcher/bootstrap/rate-limit/dedup);
- admin/support/audit targeted contracts (ADM-01/ADM-02 internal HTTP and audit sink/readback contracts);
- retention/migrations targeted contracts.

Output contract:
- success line: `mvp_release_preflight: ok`;
- failure line: `mvp_release_preflight: fail`.

Intentional non-coverage:
- no real Docker smoke (`run_postgres_mvp_smoke_local.py` is separate);
- no public billing ingress, provider SDK integration, or real credential/config delivery;
- no full project regression suite.

Notes:
- some DB-dependent tests may skip when `DATABASE_URL` is absent, following existing pytest skip patterns;
- for local DB integration confidence, run local Docker smoke separately:
  `python scripts/run_postgres_mvp_smoke_local.py`.

## MVP config doctor (runtime env readiness)
Use config doctor when you need a safe read-only runtime env readiness check (separate from code-contract preflight):

```bash
python scripts/run_mvp_config_doctor.py --profile all
```

Profiles:
- `--profile polling`
- `--profile webhook`
- `--profile internal-admin`
- `--profile retention`
- `--profile all` (default)

Output contract:
- success: `mvp_config_doctor: ok`
- failure: `mvp_config_doctor: fail` plus bounded `issue_code=...` markers

What it checks:
- required/optional env presence and basic shape per profile;
- webhook local/test insecure-secretless opt-in semantics;
- admin allowlist/dependency expectations for enabled internal-admin paths;
- retention env shape (for example `ADM02_AUDIT_RETENTION_DAYS`).

What it intentionally does not do:
- no DB/network calls, no migrations, no update dispatch, no Docker smoke;
- no public billing ingress, provider SDK, or real credential delivery;
- never prints raw token/secret/DSN/env values.

Operational note:
- use `run_mvp_release_preflight.py` for targeted code contracts;
- use config doctor for operator env readiness;
- use local Docker smoke separately for local DB integration behavior.

A **second blocking job** in the same workflow, `slice1-postgres-retention-integration`, runs opt-in slice-1 retention **integration** tests against an **isolated** GitHub Actions `services.postgres` instance. The job sets a **service-local** `DATABASE_URL` in the test step (disposable in-workflow credentials, not a repository secret). This closes the local gap where those tests are **skipped** when `DATABASE_URL` is unset. The same CI Postgres service model is used by the canonical MVP smoke helper gate in job `slice1-postgres-mvp-smoke`.

## Current delivery checkpoint
- Scope: slice-1 PostgreSQL smoke/CI hardening checkpoint (documentation/release-marker only).
- Current trigger semantics: `push`, `pull_request`, and `workflow_dispatch`.
- Current blocking CI gate remains intentionally narrow:
  - targeted smoke helper regression;
  - canonical PostgreSQL MVP smoke helper (`python scripts/run_postgres_mvp_smoke.py`) against isolated CI Postgres service;
  - slice-1 retention **integration** tests (real `services.postgres` + `DATABASE_URL` in the retention job only; JUnit: `test-reports/backend-postgres-retention-integration.xml`; artifact: `backend-postgres-retention-integration-reports`).
- Full backend regression remains advisory evidence (non-blocking) for this phase.
- Admin/support internal read gate script runs as advisory evidence (non-blocking); see `backend/docs/admin_support_internal_read_gate_runbook.md`.
- Reports artifact path/name: repo-root `backend/test-reports` uploaded as `backend-postgres-mvp-smoke-validation-reports` (MVP smoke job). Retention integration JUnit and related files: same directory layout under `backend/test-reports` in job `slice1-postgres-retention-integration`, uploaded separately as `backend-postgres-retention-integration-reports`.
- Last known green evidence:
  - commit `1a2f797`;
  - auto-triggered run `#9`;
  - conclusion `success`;
  - artifact upload confirmed.
  - Advisory admin/support internal read gate: green at `main@2c65a9c` (workflow run `24908572883`; artifact `backend-postgres-mvp-smoke-validation-reports`; marker file `backend-admin-support-internal-read-gate-summary.txt` with `internal_read_gate_outcome=success`).
- Non-blocking tooling follow-up:
  - residual Node20 warning may still appear for `actions/upload-artifact@v5` even with Node 24 opt-in;
  - treat as upstream/tooling messaging follow-up, not a backend runtime gate regression.

Expected CI commands (from `backend`):

```bash
python -m pip install -e .[test]
python -m pytest -q --junitxml=test-reports/backend-full-regression.xml
python -m pytest -q tests/test_run_postgres_mvp_smoke_local.py tests/test_run_postgres_mvp_smoke.py tests/test_run_slice1_retention_dry_run.py --junitxml=test-reports/backend-smoke-helper-regression.xml
DATABASE_URL=<service-local-ci-postgres-url> SLICE1_POSTGRES_MVP_SMOKE_ALLOW_MUTATING_TESTS=1 python scripts/run_postgres_mvp_smoke.py
```

Notes:
- CI smoke path uses canonical helper directly and a disposable CI Postgres service URL only.
- Local Docker wrapper stays a separate developer/operator gate that sets local-only `DATABASE_URL` and mutating-test opt-in guard automatically.
- Do not require local Docker wrapper as a CI blocking step.
- Full backend regression currently runs as advisory evidence and is non-blocking for downstream smoke gates.
- CI publishes advisory evidence for full regression as:
  - `backend-full-regression.xml` (JUnit);
  - `backend-full-regression-summary.txt` (safe outcome marker with `success`/`failure`/`unknown`).
- Blocking CI gate is intentionally limited to:
  - targeted smoke helper regression;
  - canonical PostgreSQL MVP smoke helper against isolated CI Postgres service.
- CI sequencing is explicit: advisory admin/support internal read gate evidence, then advisory full backend regression evidence, then blocking targeted smoke helper regression, then blocking canonical PostgreSQL MVP smoke helper.
- If full backend regression fails, review its artifact separately; once stable/reliable again, this step can be promoted back to blocking.
- Cursor-driven manual dispatch still requires installed/authenticated `gh`, but normal push-triggered CI does not require local `gh`.
- CI writes reports from `backend` working directory using backend-relative `REPORT_DIR=test-reports`, then uploads artifact `backend-postgres-mvp-smoke-validation-reports` from repo-root path `backend/test-reports`.
- Workflow opts JavaScript GitHub Actions into Node 24 via `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` to avoid Node 20 deprecation warnings.
- This Node 24 opt-in affects CI runner behavior for JavaScript actions only, not backend runtime/test semantics.
- CI uses a non-hidden reports directory so artifact collection remains `actions/upload-artifact` friendly.
- Artifact includes:
  - `backend-full-regression.xml` (JUnit for full backend regression suite);
  - `backend-full-regression-summary.txt` (advisory full-regression outcome marker);
  - `backend-admin-support-internal-read-gate-summary.txt` (advisory internal read gate outcome marker);
  - `backend-smoke-helper-regression.xml` (JUnit for helper regression);
  - `backend-postgres-mvp-smoke.log` (raw smoke command output);
  - `backend-postgres-mvp-smoke-summary.txt` (safe tail summary for quick triage).
- Before artifact upload, workflow runs explicit evidence verification and fails if reports directory is missing or contains no files.
- Any warning like `No files were found with the provided path: backend/test-reports` must be treated as CI evidence issue even if the job result is green, because expected diagnostics were not persisted.
- Use the JUnit XML to distinguish outcomes in CI:
  - passed tests are reported as successful test cases;
  - skipped tests are explicitly marked as skipped with reason when provided by pytest;
  - failures/errors are represented as failed test cases with traceback metadata.
- Use advisory full-regression summary/JUnit and smoke summary/log artifacts to diagnose failures without changing the manual external `DATABASE_URL` fallback path.

## Manual DATABASE_URL smoke (fallback path)
Use this only when local isolated path is unavailable and only against explicitly isolated/dev DB.

## Safety warning
- Do not run this smoke gate against production/shared databases.
- Do not use production-like DSNs for local smoke.
- This gate does not introduce public billing ingress, provider SDK integration, or real credential/config delivery.

## What the helper does (5 steps)
1. Runs persistence entrypoint: `python -m app.persistence`.
2. Runs retention helper in dry-run-only path:
   `python scripts/run_slice1_retention_dry_run.py`.
   This retention helper dry-run now includes operational checks for:
   - expired `telegram_update_dedup` rows (`expires_at <= now()`);
   - aged `adm02_ensure_access_audit_events` rows (`created_at` older than configured retention window).
   Canonical smoke still does not perform retention deletes.
3. Runs operator billing ingest/apply e2e smoke with synthetic data:
   `python scripts/check_operator_billing_ingest_apply_e2e.py`.
   This includes duplicate replay and idempotent apply checks.
4. Runs access fulfillment e2e smoke with synthetic data:
   `python scripts/check_postgres_mvp_access_fulfillment_e2e.py`.
   This validates synthetic Telegram identity -> billing ingest/apply activated subscription
   -> Telegram `/status` (active + access not ready) -> ADM-01 support readiness (active + access not ready)
   -> ADM-02 ensure-access remediation (safe successful result; optional idempotent repeat no-op)
   -> Telegram `/status` (active + access ready)
   -> ADM-01 support readiness (active + access ready)
   -> Telegram `/get_access` safe accepted response, followed by cleanup.
5. Runs both opt-in integration test files in one pytest invocation:
   `pytest -q tests/test_postgres_slice1_process_env_async.py tests/test_postgres_migration_ledger_integration.py`.

## Expected side effects
- Helper enables PostgreSQL repos via `SLICE1_USE_POSTGRES_REPOS=1`.
- Helper sets `BILLING_NORMALIZED_INGEST_ENABLE=1` and `BILLING_SUBSCRIPTION_APPLY_ENABLE=1`
  only inside its isolated child process environment.
- Helper sets `ISSUANCE_OPERATOR_ENABLE=1` and `TELEGRAM_ACCESS_RESEND_ENABLE=1`
  only inside its isolated child process environment.
- Helper sets `ADM02_ENSURE_ACCESS_ENABLE=1` only inside its isolated child process
  environment.
- Opt-in is required because the pytest step may perform targeted insert/delete or ledger checks against the database pointed to by `DATABASE_URL`.
- Retention helper step is dry-run only and is intended to validate retention wiring without deleting data.
- Operator billing e2e step validates internal operator ingest/apply path only; public billing ingress remains out of scope.
- For operator e2e details, see `backend/docs/billing_operator_ingest_apply_runbook.md`.
- Access fulfillment e2e now uses ADM-02 ensure-access internal remediation as the canonical operator-visible
  transition from not-ready to ready (no direct fake issuance phase as the main smoke remediation step).
- `/status` in this smoke remains readiness-only and does not expose raw config/credentials/provider refs.
- Canonical access fulfillment e2e aligns `/status`, ADM-01 diagnostics, ADM-02 remediation, and `/get_access`
  in one lifecycle.
- Canonical access fulfillment e2e also validates ADM-02 redacted audit evidence for
  `issued_access` followed by idempotent `noop_access_already_ready`.
- Canonical access fulfillment e2e verifies durable ADM-02 audit persistence/readback
  through internal read-only audit lookup by smoke correlation id (issued + already-ready
  outcomes, bounded safe fields only, leak-guard enforced).
- ADM-01 check is safe-summary only (no raw config/credentials/provider refs/billing refs/internal ids in stringified output).
- Access fulfillment e2e entitlement is sourced from the existing operator billing ingest/apply lifecycle
  (no direct seeded ACTIVE snapshot shortcut for the smoke assertion path).
- No public billing ingress, provider SDK integration, or real credential/config delivery is added by this smoke flow.

## Success criteria
- Command exits with code `0`.
- All five subprocess steps complete without error.

## Fail-fast troubleshooting
- Docker unavailable: start Docker Desktop/Engine and confirm `docker --version` and compose command are available.
- Port conflict or local container startup issue: stop conflicting local PostgreSQL/docker resources and rerun.
- Canonical smoke failure: inspect failing canonical step and fix that subsystem first, then rerun local gate.
- No `DATABASE_URL`: set it and rerun (helper fails fast by design).
- Missing/falsey `SLICE1_POSTGRES_MVP_SMOKE_ALLOW_MUTATING_TESTS`: set `1`, `true`, or `yes` and rerun only on isolated/dev DB.
- Subprocess/test failure: inspect failing subprocess output and fix that error first.
- Wrong/shared/production DB risk: stop run, switch `DATABASE_URL` to isolated/dev DB, rerun.
- Retention dry-run step failure: inspect `scripts/run_slice1_retention_dry_run.py` subprocess output and fix env/config issue first.
- Operator billing e2e step failure: inspect `scripts/check_operator_billing_ingest_apply_e2e.py` output and fix internal billing ingest/apply wiring first.
- Access fulfillment e2e step failure: inspect `scripts/check_postgres_mvp_access_fulfillment_e2e.py` output and fix internal issuance/access resend wiring first.
- Access fulfillment e2e command sequence uses distinct synthetic Telegram `update_id` values; do not reuse
  the same update id for different smoke steps when reproducing manually.

## Security notes
- Do not log or paste raw `DATABASE_URL`.
- Prefer `python scripts/run_postgres_mvp_smoke_local.py` for real validation.
- Use only isolated/dev DB; never production/shared DB.
- `SLICE1_POSTGRES_MVP_SMOKE_ALLOW_MUTATING_TESTS` is a mandatory operator guard for mutating smoke tests.
- Smoke helper billing opt-ins are scoped to child env for this isolated smoke path only; they are not default feature enablement.
- Smoke helper issuance/telegram opt-ins are scoped to child env for this isolated smoke path only; they are not default feature enablement.
- Smoke helper ADM-02 ensure-access opt-in is scoped to child env for this isolated smoke path only; it is not default feature enablement.
- Helper performs targeted insert/delete in integration test path.
- Retention helper in this flow is dry-run only and must not be treated as destructive cleanup.
- This runbook does not imply production DB smoke is safe.
- No public billing ingress is introduced in this smoke flow.
