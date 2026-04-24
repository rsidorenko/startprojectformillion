# Admin/support internal read gate (ADM-01 / ADM-02)

## Purpose

**Advisory operator preflight:** fast, in-process checks that the internal Starlette bridges for **ADM-01** and **ADM-02** still enforce allowlists, principal extraction, and safe JSON shapes. Use after refactors touching `app.admin_support` or internal HTTP wiring.

This gate is **not** a substitute for **network boundary controls** on internal HTTP (private network, mTLS, sidecar identity, etc.) and **not** a replacement for production RBAC/transport policy.

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

The gate runs as **advisory evidence** in workflow `backend-postgres-mvp-smoke-validation` (after backend dependencies install, before blocking PostgreSQL MVP smoke gates). Failures are written to the published reports artifact as `backend-admin-support-internal-read-gate-summary.txt` (`internal_read_gate_outcome=success|failure|unknown` only); review failures but they **do not block** the targeted smoke helper regression or the real local isolated PostgreSQL MVP smoke gates.

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
