# MVP Release Staging Manifest

Purpose: manual staging guide for the release/handoff package only.

Warning: do not run blanket `git add .` for this commit.

## Include (stage exactly these files)
- `PROJECT_HANDOFF.md`
- `.github/workflows/backend-mvp-release-readiness.yml`
- `backend/RELEASE_STATUS.md`
- `backend/docs/mvp_release_artifact_manifest.md`
- `backend/docs/mvp_release_ci_trigger_decision.md`
- `backend/docs/mvp_release_readiness_runbook.md`
- `backend/docs/mvp_release_staging_manifest.md`
- `backend/scripts/run_mvp_release_readiness.py`
- `backend/scripts/run_mvp_release_checklist.py`
- `backend/scripts/run_mvp_release_preflight.py`
- `backend/scripts/run_mvp_config_doctor.py`
- `backend/scripts/run_mvp_repo_release_health_check.py`
- `backend/scripts/run_mvp_final_static_handoff_check.py`
- `backend/scripts/print_mvp_release_handoff_summary.py`
- `backend/tests/test_mvp_final_release_gate_contract.py`
- `backend/tests/test_mvp_release_package_complete_contract.py`
- `backend/tests/test_mvp_release_readiness_workflow_structure_contract.py`
- `backend/tests/test_release_status_contract.py`
- `backend/tests/test_mvp_release_scripts_output_contract.py`
- `backend/tests/test_mvp_release_artifact_manifest_contract.py`
- `backend/tests/test_mvp_release_readiness_runbook_contract.py`
- `backend/tests/test_mvp_release_readiness_ci_evidence_contract.py`
- `backend/tests/test_mvp_release_ci_trigger_decision_contract.py`
- `backend/tests/test_mvp_release_staging_manifest_contract.py`
- `backend/tests/test_run_mvp_config_doctor.py`
- `backend/tests/test_run_mvp_final_static_handoff_check.py`
- `backend/tests/test_run_mvp_release_checklist.py`
- `backend/tests/test_run_mvp_release_preflight.py`
- `backend/tests/test_run_mvp_release_readiness.py`
- `backend/tests/test_run_mvp_repo_release_health_check.py`
- `backend/tests/test_print_mvp_release_handoff_summary.py`
- `backend/tests/test_postgres_mvp_smoke_ci_evidence_contract.py`
- `backend/tests/test_project_handoff_contract.py`

## Exclude (do not stage in this release-package commit)
- `.cursor/plans/**`
- `backend/src/app/**` (runtime/domain code paths)
- `backend/migrations/**`
- `backend/tests/test_adm*`
- `backend/tests/test_application_*`
- `backend/tests/test_bot_transport_*`
- `backend/tests/test_postgres_*` (except `backend/tests/test_postgres_mvp_smoke_ci_evidence_contract.py` in include list)
- `backend/tests/test_run_postgres_*`
- `backend/tests/test_run_operator_*`
- `backend/tests/test_run_slice1_*`
- `backend/tests/test_telegram_*`
- `.github/workflows/backend-postgres-mvp-smoke-validation.yml` (exclude unless intentionally bundled in a separate decision)

## Suggested manual staging commands (example, do not execute blindly)
```bash
git add -- PROJECT_HANDOFF.md .github/workflows/backend-mvp-release-readiness.yml
git add -- backend/RELEASE_STATUS.md backend/docs/mvp_release_artifact_manifest.md backend/docs/mvp_release_ci_trigger_decision.md backend/docs/mvp_release_readiness_runbook.md backend/docs/mvp_release_staging_manifest.md
git add -- backend/scripts/run_mvp_release_readiness.py backend/scripts/run_mvp_release_checklist.py backend/scripts/run_mvp_release_preflight.py backend/scripts/run_mvp_config_doctor.py backend/scripts/run_mvp_repo_release_health_check.py backend/scripts/run_mvp_final_static_handoff_check.py backend/scripts/print_mvp_release_handoff_summary.py
git add -- backend/tests/test_mvp_final_release_gate_contract.py backend/tests/test_mvp_release_package_complete_contract.py backend/tests/test_mvp_release_readiness_workflow_structure_contract.py backend/tests/test_release_status_contract.py backend/tests/test_mvp_release_scripts_output_contract.py backend/tests/test_mvp_release_artifact_manifest_contract.py backend/tests/test_mvp_release_readiness_runbook_contract.py backend/tests/test_mvp_release_readiness_ci_evidence_contract.py backend/tests/test_mvp_release_ci_trigger_decision_contract.py backend/tests/test_mvp_release_staging_manifest_contract.py backend/tests/test_run_mvp_config_doctor.py backend/tests/test_run_mvp_final_static_handoff_check.py backend/tests/test_run_mvp_release_checklist.py backend/tests/test_run_mvp_release_preflight.py backend/tests/test_run_mvp_release_readiness.py backend/tests/test_run_mvp_repo_release_health_check.py backend/tests/test_print_mvp_release_handoff_summary.py backend/tests/test_postgres_mvp_smoke_ci_evidence_contract.py backend/tests/test_project_handoff_contract.py
git status --short --untracked-files=all
```

## Verification note
- `python scripts/run_mvp_final_static_handoff_check.py` includes `tests/test_mvp_release_staging_manifest_contract.py`.
