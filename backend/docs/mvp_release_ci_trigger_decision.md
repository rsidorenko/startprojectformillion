# MVP Release CI Trigger Decision

## Problem
GitHub Actions did not run when only root/final release handoff artifacts changed because workflow `paths` were too narrow.

## Decision
`backend-mvp-release-readiness` must trigger on root `PROJECT_HANDOFF.md` and backend release/handoff docs/scripts/tests.

## Lightweight CI scope
- `python scripts/run_mvp_repo_release_health_check.py`
- `python scripts/run_mvp_release_checklist.py`
- `python scripts/run_mvp_release_preflight.py`
- `python scripts/run_mvp_final_static_handoff_check.py`
- `python -m pytest -q tests/test_run_mvp_config_doctor.py`

## Explicit non-goals
- no Docker/local smoke
- no DB service and no `DATABASE_URL` gate
- no `${{ secrets.* }}`
- no live Telegram/provider checks
- no real `run_mvp_config_doctor.py --profile all` gate

## Related guards
- `tests/test_mvp_release_readiness_ci_evidence_contract.py`
- `tests/test_mvp_release_readiness_workflow_structure_contract.py`
- `tests/test_run_mvp_repo_release_health_check.py`
- `tests/test_mvp_final_release_gate_contract.py`
- `tests/test_mvp_release_package_complete_contract.py`

Trigger scope is protected by both evidence and workflow-structure contracts.
