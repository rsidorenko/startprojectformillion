# Project Handoff Index

## Status
- Telegram subscription MVP backend release package is ready for operator validation, not full production certification.

## Primary Status and Commands
- Primary backend status doc: `backend/RELEASE_STATUS.md`
- Primary local backend command: `cd backend && python scripts/run_mvp_release_readiness.py`
- Static repo health command: `cd backend && python scripts/run_mvp_repo_release_health_check.py`
- Final static handoff check command: `cd backend && python scripts/run_mvp_final_static_handoff_check.py`
  - Includes lightweight CI workflow structure contract: `tests/test_mvp_release_readiness_workflow_structure_contract.py`.
  - Static/handoff-only guard; does not run Docker/DB/runtime checks.
- Final gate contract: `backend/tests/test_mvp_final_release_gate_contract.py`
  - Static/handoff-only guard; does not replace readiness/preflight/config doctor/local smoke.

## CI Gates
- `backend-mvp-release-readiness`
  - Trigger scope: starts on root `PROJECT_HANDOFF.md` and backend release/handoff docs/scripts/tests changes.
- `backend-postgres-mvp-smoke-validation`

## Key Docs
- `backend/docs/mvp_release_artifact_manifest.md`
- `backend/docs/mvp_release_readiness_runbook.md`
- `backend/docs/postgres_mvp_smoke_runbook.md`
- `backend/docs/telegram_access_resend_runbook.md`
- `backend/docs/admin_support_internal_read_gate_runbook.md`

## Known Manual Gates
- config doctor with real operator env
- local Docker smoke
- deployed webhook `/healthz` and `/readyz`
- Telegram `setWebhook` and secret rotation
- retention delete approval

## Explicit Out-of-Scope
- public billing ingress
- real provider SDK
- raw credential/config delivery
- full production SLO/alerting certification
