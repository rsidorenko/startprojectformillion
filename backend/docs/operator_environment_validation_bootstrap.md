# Operator Environment Validation Bootstrap

Purpose: guide a human operator through provisioning a safe staging/test environment for MVP/operator validation gates. This is not production certification and does not enable real provider integration, public billing ingress, or raw credential delivery.

## Safety warnings

- Never paste secrets into chat, tickets, commit messages, or shell history sharing.
- Use a staging/test Telegram bot, not a production bot.
- Use a staging/test PostgreSQL database, not production. CI uses disposable service containers.
- Do not run `configure_telegram_webhook.py --apply` or `--delete` unless you explicitly intend to change live Telegram webhook state.
- Do not run `reconcile_expired_access.py` against a production database without explicit confirmation.
- Do not enable `OPERATIONAL_RETENTION_DELETE_ENABLE` unless you understand the effect and have run dry-run first.

## Required environment variables

### Secrets (never log, never commit, never share)

| Variable | Used by | Required for gate |
|---|---|---|
| `BOT_TOKEN` | config doctor, launch readiness, webhook tool, release candidate validator, customer journey e2e | 10, 11, 12, 13, 16, 18 |
| `DATABASE_URL` | config doctor, launch readiness, release candidate validator, reconcile health, customer journey e2e, local smoke | 10, 11, 12, 16, 17, 18, 19 |
| `PAYMENT_FULFILLMENT_WEBHOOK_SECRET` | config doctor (webhook profile), launch readiness (strict), release candidate validator | 10, 12, 16 |
| `TELEGRAM_CHECKOUT_REFERENCE_SECRET` | launch readiness (strict), release candidate validator, customer journey e2e | 12, 16, 18 |
| `TELEGRAM_WEBHOOK_SECRET_TOKEN` | config doctor (webhook profile), webhook tool, release candidate validator | 10, 13, 16 |

### Non-secret configuration

| Variable | Purpose | Used by | Required for gate |
|---|---|---|---|
| `TELEGRAM_WEBHOOK_PUBLIC_URL` | Webhook endpoint URL | launch readiness, webhook tool, release candidate validator | 11, 12, 13, 16 |
| `TELEGRAM_WEBHOOK_HTTP_ENABLE` | Enable webhook ASGI entrypoint | config doctor, launch readiness, release candidate validator | 10, 12, 16 |
| `TELEGRAM_WEBHOOK_ALLOWED_UPDATES` | Allowed update types | launch readiness, release candidate validator | 11, 12, 16 |
| `TELEGRAM_ACCESS_RESEND_ENABLE` | Enable access resend commands | launch readiness | 11, 12 |
| `PAYMENT_FULFILLMENT_HTTP_ENABLE` | Enable fulfillment ingress | launch readiness, release candidate validator | 11, 12, 16 |
| `SUBSCRIPTION_DEFAULT_PERIOD_DAYS` | Subscription period in days | launch readiness | 11, 12 |
| `ACCESS_RECONCILE_SCHEDULE_ACK` | Reconcile schedule acknowledgment | launch readiness, release candidate validator | 11, 12, 16 |
| `ACCESS_RECONCILE_MAX_INTERVAL_SECONDS` | Reconcile max interval | launch readiness, release candidate validator | 11, 12, 16 |
| `TELEGRAM_STOREFRONT_CHECKOUT_URL` | Checkout page URL | launch readiness, customer journey e2e | 11, 12, 18 |
| `TELEGRAM_STOREFRONT_RENEWAL_URL` | Renewal page URL | launch readiness, customer journey e2e | 11, 12, 18 |
| `TELEGRAM_STOREFRONT_SUPPORT_URL` | Support page URL | launch readiness | 11, 12 |
| `TELEGRAM_STOREFRONT_SUPPORT_HANDLE` | Support contact handle | launch readiness | 11, 12 |
| `TELEGRAM_STOREFRONT_PLAN_NAME` | Plan display name | launch readiness | 11, 12 |
| `TELEGRAM_STOREFRONT_PLAN_PRICE` | Plan display price | launch readiness | 11, 12 |
| `TELEGRAM_CHECKOUT_REFERENCE_MAX_AGE_SECONDS` | Checkout reference TTL | launch readiness | 11, 12 |

### Internal admin (only needed for ADM-01/ADM-02 validation)

| Variable | Purpose |
|---|---|
| `ADM01_INTERNAL_HTTP_ENABLE` | Enable ADM-01 internal HTTP |
| `ADM01_INTERNAL_HTTP_BIND_HOST` | ADM-01 bind host |
| `ADM01_INTERNAL_HTTP_BIND_PORT` | ADM-01 bind port |
| `ADM01_INTERNAL_HTTP_ALLOWLIST` | ADM-01 principal allowlist |
| `ADM02_ENSURE_ACCESS_ENABLE` | Enable ADM-02 ensure-access |

### Retention (only needed for retention validation)

| Variable | Purpose |
|---|---|
| `OPERATIONAL_RETENTION_DELETE_ENABLE` | Enable retention delete path |
| `ADM02_AUDIT_RETENTION_DAYS` | Audit retention period |

## Feature flags and defaults

All feature flags are **disabled by default** (missing/falsey). This is the safe posture.

| Flag | Default | Safe to enable for staging? | Notes |
|---|---|---|---|
| `TELEGRAM_ACCESS_RESEND_ENABLE` | disabled | yes | Enables `/status`, `/get_access`, `/resend_access` |
| `PAYMENT_FULFILLMENT_HTTP_ENABLE` | disabled | yes | Enables payment fulfillment ingress endpoint |
| `TELEGRAM_WEBHOOK_HTTP_ENABLE` | disabled | yes | Enables webhook ASGI entrypoint |
| `ISSUANCE_OPERATOR_ENABLE` | disabled | yes | Enables issuance operator entrypoint |
| `ADM02_ENSURE_ACCESS_ENABLE` | disabled | yes | Enables ADM-02 ensure-access remediation |
| `OPERATIONAL_RETENTION_DELETE_ENABLE` | disabled | caution | Enables destructive retention delete; run dry-run first |

For staging validation, enable the ones needed for the gates you want to test. Set each to `1`.

## Recommended staging validation order

### Phase 1: Static (no env required)

```bash
cd backend
python scripts/run_mvp_repo_release_health_check.py
python scripts/run_mvp_final_static_handoff_check.py
python scripts/run_mvp_release_readiness.py
python -m pytest -q
```

### Phase 2: Config and preflight (requires env vars)

```bash
cd backend
python scripts/run_mvp_config_doctor.py --profile all
python scripts/check_launch_readiness.py
python scripts/check_launch_readiness.py --strict
```

### Phase 3: Release candidate (requires full env + DATABASE_URL)

```bash
cd backend
python scripts/validate_release_candidate.py
```

### Phase 4: Local PostgreSQL smoke (requires Docker)

```bash
cd backend
python scripts/run_postgres_mvp_smoke_local.py
```

If Docker is not available, use CI evidence from the latest green `backend-postgres-mvp-smoke-validation` run.

### Phase 5: Webhook (requires deployed endpoint for verify/apply)

```bash
cd backend
# Safe, non-mutating:
python scripts/configure_telegram_webhook.py --dry-run

# After deployment, read-only:
python scripts/configure_telegram_webhook.py --verify

# Explicit operator action only:
python scripts/configure_telegram_webhook.py --apply
```

### Phase 6: Reconcile

```bash
cd backend
# Read-only health check:
python scripts/check_reconcile_health.py

# Mutation — requires explicit staging/test DB confirmation:
python scripts/reconcile_expired_access.py
```

### Phase 7: Post-deployment

```bash
# Requires deployed runtime:
curl -sf http://localhost:<port>/healthz
curl -sf http://localhost:<port>/readyz
```

## Gate mapping

| # | Gate | Env vars required | Expected transition after provisioning |
|---|---|---|---|
| 1 | Clean tracked tree | none | PASS (already) |
| 2 | Main equals origin/main | none | PASS (already) |
| 3 | No stash | none | PASS (already) |
| 4 | No open PRs | none | PASS (already) |
| 5 | Main CI green | none | PASS (already) |
| 6 | Repo release health check | none | PASS (already) |
| 7 | Final static handoff check | none | PASS (already) |
| 8 | MVP release readiness | none | PASS (already) |
| 9 | Full pytest suite | none | PASS (already) |
| 10 | Config doctor | BOT_TOKEN, DATABASE_URL, + profile-specific | SKIP-ENV → PASS/FAIL |
| 11 | Launch readiness default | BOT_TOKEN, DATABASE_URL, storefront vars, reconcile vars | SKIP-ENV → PASS/FAIL |
| 12 | Launch readiness strict | same as 11 + PAYMENT_FULFILLMENT_WEBHOOK_SECRET, TELEGRAM_CHECKOUT_REFERENCE_SECRET | SKIP-ENV → PASS/FAIL |
| 13 | Webhook dry-run | BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET_TOKEN, TELEGRAM_WEBHOOK_PUBLIC_URL | SKIP-ENV → PASS/FAIL |
| 14 | Webhook verify | same as 13 + deployed endpoint | REQUIRES-OPERATOR |
| 15 | Webhook apply | same as 13 + explicit operator intent | REQUIRES-OPERATOR |
| 16 | Release candidate validator | all above + DATABASE_URL | SKIP-ENV → PASS/FAIL |
| 17 | Local PostgreSQL smoke | Docker + DATABASE_URL | SKIP-DOCKER → PASS/FAIL (or use CI) |
| 18 | Customer journey e2e | BOT_TOKEN, DATABASE_URL, storefront vars, secrets | SKIP-ENV → PASS/FAIL |
| 19 | Access reconcile health | DATABASE_URL | SKIP-ENV → PASS/FAIL |
| 20 | Access reconcile execution | DATABASE_URL + explicit staging confirmation | REQUIRES-OPERATOR |
| 21 | Retention dry-run | Docker + DATABASE_URL | SKIP-DOCKER → PASS/FAIL (or use CI) |
| 22 | Live /healthz / /readyz | deployed runtime | REQUIRES-OPERATOR |
| 23 | Telegram access resend gate | none | PASS (confirmed disabled) |
| 24 | Payment fulfillment HTTP gate | none | PASS (confirmed disabled) |
| 25 | Provider/issuance fake-provider | none | PASS (confirmed safe) |
| 26 | Secrets handling / no-value logging | none | PASS (confirmed safe) |

## Failure interpretation

- **`issue_code=*_missing`**: provisioning issue, not code failure. Set the named env var and rerun.
- **`issue_code=*_not_enabled`**: feature flag not set. Intentionally enable for staging if needed.
- **Docker unavailable**: local infra issue, not code failure. CI provides equivalent evidence from disposable PostgreSQL service containers.
- **`reconcile_health_check_runtime_failure`**: DATABASE_URL not pointing to an accessible PostgreSQL instance.

## CI evidence reference

If Docker or PostgreSQL is not available locally, the latest green `backend-postgres-mvp-smoke-validation` workflow run provides:

- Full backend regression (1770+ tests)
- ADM-01 internal HTTP entrypoint smoke (blocking)
- Issuance operator entrypoint smoke (blocking)
- Release candidate validator with all gates (blocking)
- PostgreSQL retention integration (blocking)
- Operator billing ingest/apply e2e (advisory)
- Admin support internal read gate (advisory)

CI uses disposable `postgres:16-alpine` service containers with test-only credentials. This is equivalent to local Docker smoke for validation purposes.

## Next operator action

1. Set all required env vars in your shell session (not in a file that could be committed).
2. Run the validation rerun batch or individual commands from Phase 2 onward.
3. Share only the redacted gate report (issue codes, PASS/FAIL status), never raw env values.
