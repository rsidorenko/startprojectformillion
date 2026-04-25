# Admin/support internal read gate (ADM-01 / ADM-02)

## Purpose

**Advisory operator preflight:** fast, in-process checks that the internal Starlette bridges for **ADM-01** and **ADM-02** still enforce allowlists, principal extraction, and safe JSON shapes. Use after refactors touching `app.admin_support` or internal HTTP wiring.

This gate is **not** a substitute for **network boundary controls** on internal HTTP (private network, mTLS, sidecar identity, etc.) and **not** a replacement for production RBAC/transport policy.

For ADM-01 internal HTTP production boundary and deployment constraints, see the architecture decision record: [`docs/architecture/34-adm01-internal-http-production-boundary-adr.md`](../../docs/architecture/34-adm01-internal-http-production-boundary-adr.md).

## ADM-01 standalone internal HTTP entrypoint

Standalone ADM-01 process entrypoint:

```bash
cd backend
python -m app.internal_admin
```

Default behavior is **disabled** unless `ADM01_INTERNAL_HTTP_ENABLE` is truthy. In disabled mode the process prints:

```text
adm01_internal_http: disabled
```

and exits with code `0`.

Enabled mode requires runtime env plus ADM-01 HTTP env guards:

- `DATABASE_URL=<DATABASE_URL>`
- `BOT_TOKEN=<BOT_TOKEN>` (required when runtime config loading expects bot credentials)
- `ADM01_INTERNAL_HTTP_ENABLE=1`
- `ADM01_INTERNAL_HTTP_BIND_HOST=<bind-host>`
- `ADM01_INTERNAL_HTTP_BIND_PORT=<bind-port>`
- `ADM01_INTERNAL_HTTP_ALLOWLIST=<principal-id>,<principal-id>`
- `ADM01_INTERNAL_HTTP_TRUST_REVERSE_PROXY=1` (when transport trust is provided by a trusted reverse proxy)
- `ADM01_INTERNAL_HTTP_REQUIRE_MTLS=1` (when transport trust is provided by mTLS)
- `ADM01_INTERNAL_HTTP_BIND_INSECURE_ALL_INTERFACES=1` (explicit override for `0.0.0.0` / `::`)

Safety constraints:

- Default bind is loopback; do not expose ADM-01 HTTP on public interfaces by default.
- Do not use `0.0.0.0` / `::` unless explicit insecure-all-interfaces override is set and network controls are documented.
- Allowlist is defense-in-depth and does **not** replace transport trust (private network + trusted reverse proxy and/or mTLS).
- Do not log request bodies, provider references, DSN values, or token material.
- Do not expose this entrypoint to the public internet; run only behind private network controls as defined in ADR 34.

On enabled-mode failure, stderr categories are fixed and intentionally low-detail:

- `adm01_internal_http: config_error`
- `adm01_internal_http: failed`

## What it does / does not do

- **No external database:** does not read `DATABASE_URL`, does not open TCP to PostgreSQL, no Docker, no migrations.
- **No Telegram** or billing/config issuance paths.
- **ADM-02 success path:** uses the real `Adm02DiagnosticsHandler` stack with in-memory repositories; a successful diagnostics call may append a **fact-of-access record to the in-memory audit appender** (same handler semantics as in unit tests). Nothing is written to a real production database by this script.

## Prerequisites

- Run from the `backend` directory (same as other scripts).
- Install the backend package with test dependencies so `httpx` and app imports resolve (`pip install -e .[test]`).

## Run

```bash
cd backend
python scripts/check_admin_support_internal_read_gate.py
```

### ADM-01 entrypoint smoke

```bash
cd backend
python scripts/check_adm01_internal_http_entrypoint_smoke.py
```

This smoke verifies only disabled/config-error behavior for `python -m app.internal_admin`
and is intentionally no-listener/no-DB; it does not prove production network safety.
In CI (`backend-postgres-mvp-smoke-validation`) it is a **blocking gate**: a failed run fails the job (still not a production network or transport guarantee).

Expected stdout on success (single line):

```text
admin_support_internal_read_gate: ok
```

On failure, the process exits non-zero and prints **exactly one fixed line** to stderr (no tracebacks, no exception messages, no request/response dumps):

- `admin_support_internal_read_gate: fail` — gate checks reported an expected violation (e.g. assertion-style `RuntimeError` from the check module).
- `admin_support_internal_read_gate: failed` — unexpected error inside the gate run (any other exception); details are intentionally suppressed so stderr cannot echo secrets from exception text.

## Safety notes

- Keep internal HTTP listeners on private networks only; this script does not replace transport-level controls (mTLS, VPC, etc.).
- Do not paste real `DATABASE_URL`, bot tokens, or customer identifiers into tickets, shell history, or issue reports when sharing script output.

## CI

In workflow `backend-postgres-mvp-smoke-validation` (after backend dependencies install, before blocking PostgreSQL MVP smoke gates): the **admin support internal read gate** still runs as **advisory evidence**; failures are written to `backend-admin-support-internal-read-gate-summary.txt` (`internal_read_gate_outcome=success|failure|unknown` only) and **do not block** the smoke helper regression or the real local isolated PostgreSQL MVP smoke gates.

The **ADM-01 internal HTTP entrypoint smoke** (`check_adm01_internal_http_entrypoint_smoke.py`) runs as a **blocking gate** on the same job; outcome is recorded in `backend-adm01-internal-http-entrypoint-smoke-summary.txt` (`adm01_entrypoint_smoke_outcome=success|failure|unknown`). A failure **blocks** the job (artifact upload still runs on `always()` steps where configured).

## Current delivery checkpoint

Documentation-only marker tying this gate to a **published CI artifact** (no new runtime guarantees).

- **Branch / commit:** `main` @ `2c65a9c` (full SHA `2c65a9ced7c7798f320a3b0eb8ae8bc67f647332`).
- **Workflow:** `backend-postgres-mvp-smoke-validation`; **run id** `24908572883`; **conclusion** `success`.
- **Artifact:** `backend-postgres-mvp-smoke-validation-reports`; file `backend-admin-support-internal-read-gate-summary.txt` includes marker `internal_read_gate_outcome=success`.
- **Reminder:** this remains **advisory** CI evidence for operator preflight semantics; it is **not** a blocking production network boundary, transport policy, or RBAC substitute.

Local command remains:

```bash
cd backend
python scripts/check_admin_support_internal_read_gate.py
```

## Automation

Pytest coverage: `tests/test_internal_read_gate_checks.py` and `tests/test_run_admin_support_internal_read_gate.py`.
