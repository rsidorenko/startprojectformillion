# Issuance Operator Runbook

Operator entrypoint for config issuance actions (`issue`, `resend`, `revoke`) using existing `IssuanceService`, fake provider, and durable Postgres issuance state.

## Scope and safety boundary

- Disabled by default. You must explicitly opt in with `ISSUANCE_OPERATOR_ENABLE=1`.
- Uses fake provider only (`FakeIssuanceProvider`), no real external provider/network integration.
- Uses durable state in `issuance_state` via `PostgresIssuanceStateRepository`.
- Fails closed on missing/invalid configuration.
- Output is fixed and redacted; no DSN, secret token, raw payload, or full delivery instructions.

## CI smoke gate

- Workflow `backend-postgres-mvp-smoke-validation` includes `python scripts/check_issuance_operator_entrypoint_smoke.py` as a **blocking** gate.
- The smoke checks disabled/config-error fail-closed paths only; it intentionally runs without `DATABASE_URL` and without `BOT_TOKEN`.
- The smoke does not require DB connectivity, does not call real providers, and does not introduce network dependency.
- CI writes marker `backend-issuance-operator-entrypoint-smoke-summary.txt` with `issuance_operator_entrypoint_smoke_outcome=<success|failure|unknown>`.

## Required environment

- `ISSUANCE_OPERATOR_ENABLE`: opt-in flag (`1`, `true`, `yes`).
- `BOT_TOKEN`: required by shared runtime config loader.
- `DATABASE_URL`: required Postgres DSN.
- Optional: `ISSUANCE_OPERATOR_FAKE_PROVIDER_MODE` in `{success, unavailable, rejected, unknown}`.
  - default: `success`.

## Commands

Run from `backend/`:

```bash
python -m app.application.issuance_operator_main issue --internal-user-id user-123 --access-profile-key ap-basic --issue-idempotency-key issue-key-123
python -m app.application.issuance_operator_main resend --internal-user-id user-123 --access-profile-key ap-basic --issue-idempotency-key issue-key-123
python -m app.application.issuance_operator_main revoke --internal-user-id user-123 --access-profile-key ap-basic --issue-idempotency-key issue-key-123
```

Optional:

```bash
--correlation-id <32-lowercase-hex>
```

If omitted, a correlation id is generated automatically.

## Output contract

- Success (`stdout`, single line):
  - `issuance_operator: ok action=<issue|resend|revoke> outcome=<category> state=<issued|revoked|none> delivery=<redacted|none>`
- Failure (`stderr`, single line):
  - `issuance_operator: failed category=<opt_in|config|validation|dependency|unexpected>`

## Action semantics

- `issue`:
  - uses `issue_idempotency_key` as issuance idempotency key.
  - repeated runs resolve through existing service + durable state behavior.
- `resend`:
  - links to prior issue via `issue_idempotency_key`.
  - durable eligibility hydration is supported.
  - resend call-dedup remains process-local by current service design.
- `revoke`:
  - links to prior issue via `issue_idempotency_key`.
  - idempotent/safe via current service semantics and durable state.

## Troubleshooting

- `category=opt_in`: set `ISSUANCE_OPERATOR_ENABLE=1`.
- `category=config`: provide valid `BOT_TOKEN` and `DATABASE_URL`; keep `APP_ENV=test` or local env if DSN has no `sslmode`.
- `category=validation`: fix CLI arguments (`internal-user-id`, `access-profile-key`, `issue-idempotency-key`, optional `correlation-id` format).
- `category=dependency`: database connectivity/transient persistence issue.
