# MVP Release Status

## MVP status
Release package is ready for operator validation, not fully production certified.

## Primary local command
- `python scripts/run_mvp_release_readiness.py`
- `python scripts/run_mvp_final_static_handoff_check.py` (static/handoff-only; does not replace readiness/preflight/config doctor/local smoke)
  - Includes lightweight CI workflow structure contract: `tests/test_mvp_release_readiness_workflow_structure_contract.py`.
  - Remains static/handoff-only and does not run Docker/DB/runtime checks.

## CI gates
- `backend-mvp-release-readiness`
  - Trigger scope includes root `PROJECT_HANDOFF.md` and backend release/handoff docs/scripts/tests.
- `backend-postgres-mvp-smoke-validation`

## Manual go/no-go gates
- Run `python scripts/run_mvp_config_doctor.py --profile polling|webhook|internal-admin|retention|all` with actual operator environment.
- Run `python scripts/run_postgres_mvp_smoke_local.py` when Docker and PostgreSQL are available.
- Verify deployed webhook `/healthz` and `/readyz`.
- Perform Telegram `setWebhook` and webhook secret rotation operational step.
- Execute retention dry-run before any delete opt-in.

## Security posture
- Webhook secret is fail-closed.
- Telegram command handling enforces rate limit and dedup.
- ADM-02 ensure-access path remains explicit opt-in.
- ADM-02 durable audit is redacted and supports readback.
- Release scripts are covered by bounded-output contracts.

## Known limitations (out-of-scope)
- public billing ingress
- real provider SDK
- raw credential/config delivery
- full production SLO/alerting certification
- external observability pipeline validation

## Pointers
- `docs/mvp_release_artifact_manifest.md`
- `docs/mvp_release_readiness_runbook.md`
- `docs/postgres_mvp_smoke_runbook.md`
- `docs/telegram_access_resend_runbook.md`
- `docs/admin_support_internal_read_gate_runbook.md`
- final static handoff check script: `scripts/run_mvp_final_static_handoff_check.py`
- final release gate contract: `tests/test_mvp_final_release_gate_contract.py`
