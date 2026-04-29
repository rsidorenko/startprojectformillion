# Project Handoff Index

## Status
- Telegram subscription MVP backend release package is ready for operator validation, not full production certification.
- Current main HEAD: `9dcd6b6` (includes PRs #4–#8).

## Primary Status and Commands
- Primary backend status doc: `backend/RELEASE_STATUS.md`
- Primary local backend command: `cd backend && python scripts/run_mvp_release_readiness.py`
- Static repo health command: `cd backend && python scripts/run_mvp_repo_release_health_check.py`
- Final static handoff check command: `cd backend && python scripts/run_mvp_final_static_handoff_check.py`
  - Includes lightweight CI workflow structure contract: `tests/test_mvp_release_readiness_workflow_structure_contract.py`.
  - Static/handoff-only guard; does not run Docker/DB/runtime checks.
- Final gate contract: `backend/tests/test_mvp_final_release_gate_contract.py`
  - Static/handoff-only guard; does not replace readiness/preflight/config doctor/local smoke.
- Release candidate validator (final blocking gate): `cd backend && python scripts/validate_release_candidate.py`
  - Exit code `0` = all required checks passed; non-zero = launch blocked.
  - Runs: preflight, launch readiness preflight (--strict), webhook dry-run, canonical PostgreSQL smoke, reconcile health.
  - Does not call Telegram Bot API `setWebhook`; webhook apply remains explicit operator action only.
  - Requires `DATABASE_URL` and full operator environment for complete validation.

## CI Gates
- `backend-mvp-release-readiness`
  - Trigger scope: starts on root `PROJECT_HANDOFF.md` and backend release/handoff docs/scripts/tests changes.
  - Runs: repo health check, release checklist, preflight, final static handoff check, config doctor unit tests.
  - Static/contracts-only; does not require real operator environment values.
- `backend-postgres-mvp-smoke-validation`
  - Trigger scope: `backend/src/**`, `backend/tests/**`, `backend/migrations/**`, smoke scripts, relevant runbooks.
  - Runs: admin support internal read gate (advisory), ADM-01 entrypoint smoke (blocking), issuance operator smoke (blocking), full regression (advisory), smoke helper regression (blocking), release candidate validator (blocking final gate), retention integration tests (blocking).
  - Requires PostgreSQL service (CI provides isolated `services.postgres`).

## Key Docs
- `backend/docs/mvp_release_artifact_manifest.md`
- `backend/docs/mvp_release_staging_manifest.md`
- `backend/docs/mvp_release_readiness_runbook.md`
- `backend/docs/postgres_mvp_smoke_runbook.md`
- `backend/docs/telegram_access_resend_runbook.md`
- `backend/docs/admin_support_internal_read_gate_runbook.md`
- `backend/docs/issuance_operator_runbook.md`
- `backend/docs/billing_operator_ingest_apply_runbook.md`

## Implemented Features (MVP/operator validation scope)
- **Subscription lifecycle expiry** (PR #5): `active_until_utc` field, `SUBSCRIPTION_EXPIRED` status, `SUBSCRIPTION_DEFAULT_PERIOD_DAYS` config. Migration: `014_subscription_lifecycle_v1.sql`.
- **Telegram storefront commands** (PR #6): `/plans`, `/buy`/`/checkout`, `/support`, `/my_subscription`, `/renew`. Safe informational/rendering layer with signed checkout URLs via HMAC checkout reference. Feature-gated storefront config env vars. No real payment provider SDK.
- **Runtime operator tooling** (PR #7): payment fulfillment ingress (provider-agnostic, signed HTTP, feature-gated), customer journey e2e smoke, access reconcile, launch readiness preflight, webhook configuration tool, release candidate validator, subscription lifecycle smoke.
- **Test alignment** (PR #8): fixed stale runtime fake client signatures and ADM-01 response schema assertions.

## Key Scripts (operator/validation)
- `backend/scripts/run_mvp_release_readiness.py` — safe default release readiness wrapper
- `backend/scripts/run_mvp_repo_release_health_check.py` — static repo health check
- `backend/scripts/run_mvp_final_static_handoff_check.py` — final static handoff check
- `backend/scripts/validate_release_candidate.py` — release candidate go/no-go boundary
- `backend/scripts/check_launch_readiness.py` — launch readiness preflight (default/strict modes)
- `backend/scripts/configure_telegram_webhook.py` — webhook dry-run/apply/verify/delete
- `backend/scripts/check_customer_journey_e2e.py` — customer journey e2e smoke
- `backend/scripts/run_postgres_mvp_smoke.py` — canonical PostgreSQL MVP smoke
- `backend/scripts/run_postgres_mvp_smoke_local.py` — local Docker smoke wrapper
- `backend/scripts/reconcile_expired_access.py` — expired access reconcile
- `backend/scripts/check_reconcile_health.py` — reconcile health/freshness check
- `backend/scripts/run_mvp_config_doctor.py` — config doctor per profile
- `backend/scripts/run_mvp_release_preflight.py` — targeted release preflight

## Known Manual Gates
- config doctor with real operator env
- local Docker smoke
- deployed webhook `/healthz` and `/readyz`
- Telegram `setWebhook` and secret rotation
- retention delete approval
- reconcile production scheduling

## Explicit Out-of-Scope
- public billing ingress (design-only per ADR-31/32/37)
- real provider SDK
- raw credential/config delivery
- full production SLO/alerting certification
- external observability pipeline validation
