# MVP Release Status

## MVP status
Release package is ready for operator validation, not fully production certified.
Current main HEAD: `9dcd6b6` (includes PRs #4–#8).

## Primary local command
- `python scripts/run_mvp_release_readiness.py`
- `python scripts/run_mvp_final_static_handoff_check.py` (static/handoff-only; does not replace readiness/preflight/config doctor/local smoke)
  - Includes lightweight CI workflow structure contract: `tests/test_mvp_release_readiness_workflow_structure_contract.py`.
  - Remains static/handoff-only and does not run Docker/DB/runtime checks.
- `python scripts/validate_release_candidate.py` — final blocking release-candidate go/no-go boundary.
  - Runs: preflight, launch readiness preflight (--strict), webhook dry-run, canonical PostgreSQL smoke, reconcile health.
  - Exit code `0` = all required checks passed; non-zero = launch blocked.
  - Requires `DATABASE_URL` and full operator environment for complete validation.
  - CI evidence: workflow `backend-postgres-mvp-smoke-validation`, job `slice1-postgres-mvp-smoke`, step "Run release candidate validator (blocking final gate)".

## CI gates
- `backend-mvp-release-readiness`
  - Trigger scope includes root `PROJECT_HANDOFF.md` and backend release/handoff docs/scripts/tests.
  - Runs: repo health check, release checklist, preflight, final static handoff check, config doctor unit tests.
  - Static/contracts-only; does not require real operator environment values.
- `backend-postgres-mvp-smoke-validation`
  - Runs: blocking ADM-01 entrypoint smoke, blocking issuance operator smoke, blocking smoke helper regression, blocking release candidate validator, blocking retention integration.
  - Full backend regression is advisory (non-blocking).

## Manual go/no-go gates
- Run `python scripts/run_mvp_config_doctor.py --profile polling|webhook|internal-admin|retention|all` with actual operator environment.
- Run `python scripts/run_postgres_mvp_smoke_local.py` when Docker and PostgreSQL are available.
- Run `python scripts/validate_release_candidate.py` with full operator environment.
- Run `python scripts/check_launch_readiness.py --strict` for customer-facing launch gate.
- Run `python scripts/configure_telegram_webhook.py --dry-run` to validate webhook config; `--apply` to set webhook (explicit operator action).
- Run `python scripts/reconcile_expired_access.py` on production schedule; validate freshness with `python scripts/check_reconcile_health.py`.
- Verify deployed webhook `/healthz` and `/readyz`.
- Perform Telegram `setWebhook` and webhook secret rotation operational step.
- Execute retention dry-run before any delete opt-in.

## Security posture
- Webhook secret is fail-closed.
- Telegram command handling enforces rate limit and dedup.
- ADM-02 ensure-access path remains explicit opt-in.
- ADM-02 durable audit is redacted and supports readback.
- Release scripts are covered by bounded-output contracts.
- Payment fulfillment ingress is provider-agnostic, signed HTTP, feature-gated (`PAYMENT_FULFILLMENT_HTTP_ENABLE`), distinct from public billing ingress and provider webhook.
- Telegram access resend (`/status`, `/get_access`, `/resend_access`) remains disabled by default (`TELEGRAM_ACCESS_RESEND_ENABLE`).
- Fake provider only; no real provider SDK integration.
- Raw credential/config delivery forbidden.
- Access reconcile is operator-controlled and bounded (`ACCESS_RECONCILE_SCHEDULE_ACK`, `ACCESS_RECONCILE_MAX_INTERVAL_SECONDS`).
- Storefront commands are safe informational/rendering layer; signed checkout URLs use HMAC reference with TTL.

## Implemented features (MVP/operator validation)
- Subscription lifecycle expiry: `active_until_utc`, `SUBSCRIPTION_EXPIRED`, configurable period.
- Telegram storefront commands: `/plans`, `/buy`/`/checkout`, `/support`, `/my_subscription`, `/renew`.
- Payment fulfillment ingress: provider-agnostic signed HTTP path with HMAC verification and checkout reference TTL.
- Customer journey e2e smoke: full storefront-to-fulfillment-to-access lifecycle validation.
- Access reconcile: expired access revocation with heartbeat health check.
- Launch readiness preflight: strict and default modes for operator validation.
- Webhook configuration tool: dry-run, apply, verify, delete modes.
- Release candidate validator: comprehensive blocking go/no-go boundary.
- Runtime operator tooling: polling, webhook ASGI, raw httpx runners.

## Known limitations (out-of-scope)
- public billing ingress (design-only per ADR-31/32/37)
- real provider SDK
- raw credential/config delivery
- full production SLO/alerting certification
- external observability pipeline validation
- multi-tenant or public admin UI

## Pointers
- `docs/mvp_release_artifact_manifest.md`
- `docs/mvp_release_staging_manifest.md`
- `docs/mvp_release_readiness_runbook.md`
- `docs/postgres_mvp_smoke_runbook.md`
- `docs/telegram_access_resend_runbook.md`
- `docs/admin_support_internal_read_gate_runbook.md`
- `docs/issuance_operator_runbook.md`
- `docs/billing_operator_ingest_apply_runbook.md`
- `docs/operator_environment_validation_bootstrap.md`
- final static handoff check script: `scripts/run_mvp_final_static_handoff_check.py`
- final release gate contract: `tests/test_mvp_final_release_gate_contract.py`
- release candidate validator: `scripts/validate_release_candidate.py`
- launch readiness preflight: `scripts/check_launch_readiness.py`
- webhook configuration: `scripts/configure_telegram_webhook.py`
- customer journey e2e: `scripts/check_customer_journey_e2e.py`
- access reconcile: `scripts/reconcile_expired_access.py`
- reconcile health: `scripts/check_reconcile_health.py`
