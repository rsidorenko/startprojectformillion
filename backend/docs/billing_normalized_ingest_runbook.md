# Normalized billing operator ingest (internal)

## Purpose

Operator-only entry: read **one** pre-normalized billing fact as JSON, append to `billing_events_ledger` and `billing_ingestion_audit_events` via `IngestNormalizedBillingFactHandler`. **No** public HTTP, **no** raw provider payload, **no** signature verification.

## Prerequisites

- From the `backend` directory, with `PYTHONPATH` set so `app` resolves (e.g. `pip install -e .[test]` or `PYTHONPATH=src`).
- Process environment: `BILLING_NORMALIZED_INGEST_ENABLE=1` (or `true` / `yes`), `BOT_TOKEN` (length ≥ 10, same rules as the rest of the service), and `DATABASE_URL` (PostgreSQL `postgresql://` or `postgres://`).

## Input

JSON file (schema `schema_version: 1`) with normalized fields only—see `NormalizedBillingFactInput` and `app.application.billing_ingestion_main`. Example (fake values):

```json
{
  "schema_version": 1,
  "billing_provider_key": "example_provider",
  "external_event_id": "evt_001",
  "event_type": "payment_succeeded",
  "event_effective_at": "2026-01-20T12:00:00+00:00",
  "event_received_at": "2026-01-20T12:00:05+00:00",
  "status": "accepted",
  "ingestion_correlation_id": "op-run-20260120-1"
}
```

`event_effective_at` and `event_received_at` must include a **timezone** (or `Z`). Unknown extra keys (including any raw provider blob field) are rejected.

## Run

```bash
BILLING_NORMALIZED_INGEST_ENABLE=1 \
python -m app.application.billing_ingestion_main --input-file path/to/fact.json
```

Stdin:

```bash
BILLING_NORMALIZED_INGEST_ENABLE=1 \
python -m app.application.billing_ingestion_main --input-file -
# paste JSON, then EOF (e.g. Ctrl+Z on Windows, Ctrl+D on Unix)
```

## Outcome

- **Success (exit 0)**: one line to stdout, e.g. `billing_normalized_ingest: ok internal_fact_ref=... outcome=... status=... correlation_id=...`
- **Failure (exit 1)**: one line to stderr, `billing_normalized_ingest: failed category=...` (no DSN, no full JSON, no exception strings that could leak user input)

## Security

- Do not commit real `DATABASE_URL`, tokens, or user PII in tickets or runbooks.
- The entrypoint is **not** a public webhook; restrict execution to trusted operators and locked-down automation.
