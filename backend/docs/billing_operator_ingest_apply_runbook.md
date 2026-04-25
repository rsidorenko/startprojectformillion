# Operator: normalized billing ingest → subscription apply (end-to-end)

## Purpose

Manual, operator-only sequence: **one** normalized fact → ledger/audit **ingest** (`billing_ingestion_main`), then **UC-05 apply** by stable `internal_fact_ref` (`billing_subscription_apply_main`). This is not a public webhook, not a provider parser, not a background worker, and not an automatic chain between the two entrypoints in application code.

**Public billing HTTP ingress** remains **out of scope** here and **blocked** for production until the decision checklist in [32 — Public billing ingress decisions ADR §N](../../docs/architecture/32-public-billing-ingress-decisions-adr.md#n-production-implementation-decision-checklist) is complete (or ingress is provably disabled in prod); this runbook is the current **operator-only** safe path.

## Prerequisites

- Shell from the `backend/` directory with `PYTHONPATH=src` or an editable install so `app` imports resolve.
- **Test/prod-safe** `DATABASE_URL` (same conventions as other backend operator tools; never commit or paste a real DSN in tickets or logs).
- `BOT_TOKEN` is required by `load_runtime_config` (minimum length as elsewhere). Do not paste a production token into logs, terminal scrollback in shared spaces, or screenshots.
- **Explicit opt-in** (all required for the two steps to touch the database):
  - `BILLING_NORMALIZED_INGEST_ENABLE=1`
  - `BILLING_SUBSCRIPTION_APPLY_ENABLE=1`
- A stable `internal_fact_ref` you control for this run (bounded ref format: alphanumeric and `_` `.` `-` `:`, per UC-05 validation).

## Step 1 — Build normalized JSON (fake values only)

- Write **one** file, e.g. `fact.json`, using **synthetic** IDs only. **No** raw provider payload, **no** unknown top-level keys (rejected at parse).
- Required shape: `schema_version: 1` (only supported version).
- **Allowlisted** UC-05 event type: `subscription_activated` (see `app.domain.billing_apply_rules.UC05_ALLOWLISTED_EVENT_TYPE_SUBSCRIPTION_ACTIVATED` and `first_time_decision` tests).
- Set `internal_fact_ref` to a non-empty string you will pass to apply (deterministic end-to-end key).
- Set `internal_user_id` to a synthetic internal user the subscription snapshot should attach to (same as other normalized fields—fake IDs only).
- `event_effective_at` and `event_received_at` must be ISO-8601 with a **timezone** (or `Z`).

Example (all values fictional):

```json
{
  "schema_version": 1,
  "billing_provider_key": "example_operator_provider",
  "external_event_id": "ext_evt_ingest_apply_demo_1",
  "event_type": "subscription_activated",
  "event_effective_at": "2026-04-25T10:00:00+00:00",
  "event_received_at": "2026-04-25T10:00:01+00:00",
  "status": "accepted",
  "ingestion_correlation_id": "opcorr-ingest-apply-demo-1",
  "internal_fact_ref": "op.fact.ref.demo-1",
  "internal_user_id": "u_internal_demo_1"
}
```

## Step 2 — Ingest (ledger + audit)

Unix-style:

```bash
export BILLING_NORMALIZED_INGEST_ENABLE=1
# plus DATABASE_URL, BOT_TOKEN, APP_ENV as for other operator CLIs
python -m app.application.billing_ingestion_main --input-file ./fact.json
```

Windows (PowerShell), set env vars then the same `python -m` line.

**Expected success (exit 0)**, one line on stdout (shape from `billing_ingestion_main`):

```text
billing_normalized_ingest: ok internal_fact_ref=<ref> outcome=<accepted|idempotent_replay> status=accepted correlation_id=...
```

On failure (exit 1), stderr is one line: `billing_normalized_ingest: failed category=...` (no DSN, no full JSON, no exception dumps).

## Step 3 — Apply (UC-05) by the same `internal_fact_ref`

Use the **same** `internal_fact_ref` string as in the JSON (after any trimming the CLI applies).

```bash
export BILLING_SUBSCRIPTION_APPLY_ENABLE=1
python -m app.application.billing_subscription_apply_main --internal-fact-ref "op.fact.ref.demo-1"
```

**Expected success (exit 0)**, one line on stdout:

```text
billing_subscription_apply: ok internal_fact_ref=... outcome=success state=active_applied
```

A **second** run with the same ref should exit 0 with `outcome=idempotent_noop` and the same `state=active_applied` (idempotent no-op; see `test_billing_subscription_apply_main` / `test_postgres_billing_subscription_apply_main`).

On failure, stderr: `billing_subscription_apply: failed category=...` (e.g. `not_found` if the fact is not in the ledger, `validation` for bad ref, `persistence` for DB errors). No raw exception text, no env dump.

## Step 4 — Verification

**Data plane (anchored in repo tests):**

- Subscription apply stdout should show `state=active_applied` on first success, then idempotent replay as above. Integration coverage: `backend/tests/test_postgres_billing_subscription_apply_main.py` (Postgres + snapshot assertions).
- DB read-model: `PostgresSubscriptionSnapshotReader.get_for_user(internal_user_id)` should report snapshot `state_label` `active` (enum value `SubscriptionSnapshotState.ACTIVE`).

**User-facing /status (safe mapping, no new rules):**

- UC-02 maps identity + subscription snapshot to `SafeUserStatusCategory` via `map_subscription_status_view` in `app.domain.status_view`: an explicit `ACTIVE` snapshot becomes `SafeUserStatusCategory.SUBSCRIPTION_ACTIVE` (the only “billing-backed active” path in v1 for this read model). Unit coverage: `backend/tests/test_status_view.py`.
- The bot/transport layer maps that category to transport status codes; operators should not expect raw internal snapshot strings in end-user text—only the **safe** mapped outcome.

**Do not** re-run live smoke against production in this runbook; use a dedicated test database when validating.

## Failure handling (operator cheat sheet)

| Symptom | Likely `category` | Note |
|--------|---------------------|------|
| Opt-in env missing / false | `opt_in` on stderr | Set both `BILLING_*_ENABLE=1` as required per step. |
| Bad JSON, schema, timestamps, or extra fields | `validation` | Fix input; no DB change on ingest parse failure. |
| `DATABASE_URL` / config missing | `config` | Fix env before retrying. |
| Apply: fact not in ledger | `not_found` (apply) | Ingest first; check `internal_fact_ref` matches. |
| Postgres / timeout / I/O | `persistence` | Investigate DB connectivity and health; do not log DSN. |

## Safety

- **Never** use a shared or production database for ad-hoc experiments unless that is an explicit, approved change window.
- **Never** commit or paste real `DATABASE_URL`, tokens, PII, or provider raw payloads.
- **No** public HTTP surface for this flow; run only from trusted operator environments.
- **No** automatic invocation of apply from ingest in the codebase; this runbook is the **manual** sequence.

## Automated operator e2e smoke

Use the bounded smoke helper to validate ingest -> **duplicate ingest (idempotent replay)** -> apply -> second apply idempotency -> readiness with synthetic data only. Public billing HTTP ingress remains blocked by [ADR-32 §N](../../docs/architecture/32-public-billing-ingress-decisions-adr.md#n-production-implementation-decision-checklist).

```bash
python scripts/check_operator_billing_ingest_apply_e2e.py
```

Required environment:

- `DATABASE_URL` pointing to a disposable/local Postgres database.
- `BOT_TOKEN` may be set to a fake/safe token if your local runtime config policy requires it.
- Operator opt-in flags for the entrypoints:
  - `BILLING_NORMALIZED_INGEST_ENABLE=1`
  - `BILLING_SUBSCRIPTION_APPLY_ENABLE=1`

Expected fixed stdout on success:

```text
operator_billing_ingest_apply_e2e: ok
```

Safety guarantees:

- Uses synthetic IDs only with `operator-e2e-` prefix.
- Cleans up only exact synthetic rows created by this script instance.
- Exercises duplicate normalized ingest replay (`idempotent_replay`) before apply; does not open a public webhook surface.
- Does not invoke Telegram runtime/polling behavior.
- Does not use or require a real issuance provider.
- Do not print or copy production DSN/tokens into logs or docs.

## See also

- `billing_normalized_ingest_runbook.md` — ingest-only details.
- `billing_subscription_apply_runbook.md` — apply-only preconditions and scope limits.
