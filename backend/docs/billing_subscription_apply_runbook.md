# UC-05 billing subscription apply (operator)

Operator-only: runs UC-05 against a **single** fact that already exists in `billing_events_ledger` (after normalized ingest or an equivalent path). This is not a public webhook, has no provider signature step, and does not issue VPN configuration.

## Preconditions

- `BILLING_SUBSCRIPTION_APPLY_ENABLE=1` (explicit opt-in; without it the process exits non-zero without opening the database).
- `DATABASE_URL` set to a valid PostgreSQL DSN (same pattern as other backend operator tools).
- `BOT_TOKEN` and other `load_runtime_config` requirements satisfied (see project env conventions).
- `internal_fact_ref` is the stable key from the ledger row you intend to apply (for example a value that was returned or stored from billing ingest). Use only allowlisted, bounded ref strings (alphanumeric, `_`, `.`, `-`, `:`; max length 256).

## Run (from `backend/`)

```bash
set BILLING_SUBSCRIPTION_APPLY_ENABLE=1
set DATABASE_URL=postgresql://user:password@127.0.0.1:5432/yourdb
set BOT_TOKEN=00000000000000000000
python -m app.application.billing_subscription_apply_main --internal-fact-ref t_pbapply_example-fact-1
```

- Success or idempotent replay: one line on stdout starting with `billing_subscription_apply: ok` and including `outcome=` and `state=`.
- Failure: one line on stderr starting with `billing_subscription_apply: failed` and a `category=` token (for example `not_found` if the fact is missing from the ledger). No raw exception text, no DSN, no env dump.

## Scope limits

- No public HTTP surface; no Telegram chat UX change.
- Input is `internal_fact_ref` only, not raw provider JSON and not a free-form payload.
- Fake DSNs and example refs in documentation only; do not commit real credentials.
