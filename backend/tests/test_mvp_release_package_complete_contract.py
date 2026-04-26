"""Final bounded completeness contract for MVP release package."""

from __future__ import annotations

from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_DIR.parent

_RELEASE_SCRIPTS = (
    "scripts/run_mvp_release_readiness.py",
    "scripts/run_mvp_repo_release_health_check.py",
    "scripts/run_mvp_final_static_handoff_check.py",
    "scripts/run_mvp_release_checklist.py",
    "scripts/run_mvp_release_preflight.py",
    "scripts/run_mvp_config_doctor.py",
    "scripts/print_mvp_release_handoff_summary.py",
    "scripts/run_postgres_mvp_smoke.py",
    "scripts/run_postgres_mvp_smoke_local.py",
)
_WORKFLOWS = (
    ".github/workflows/backend-mvp-release-readiness.yml",
    ".github/workflows/backend-postgres-mvp-smoke-validation.yml",
)
_DOCS = (
    "RELEASE_STATUS.md",
    "docs/mvp_release_readiness_runbook.md",
    "docs/mvp_release_artifact_manifest.md",
    "docs/mvp_release_ci_trigger_decision.md",
    "docs/mvp_release_staging_manifest.md",
    "docs/postgres_mvp_smoke_runbook.md",
    "docs/telegram_access_resend_runbook.md",
    "docs/admin_support_internal_read_gate_runbook.md",
)
_ROOT_DOCS = ("PROJECT_HANDOFF.md",)
_KEY_CONTRACT_TESTS = (
    "tests/test_mvp_final_release_gate_contract.py",
    "tests/test_mvp_release_readiness_workflow_structure_contract.py",
    "tests/test_release_status_contract.py",
    "tests/test_mvp_release_scripts_output_contract.py",
    "tests/test_mvp_release_artifact_manifest_contract.py",
    "tests/test_mvp_release_staging_manifest_contract.py",
    "tests/test_mvp_release_readiness_runbook_contract.py",
    "tests/test_mvp_release_readiness_ci_evidence_contract.py",
    "tests/test_mvp_release_ci_trigger_decision_contract.py",
    "tests/test_run_mvp_config_doctor.py",
    "tests/test_run_mvp_final_static_handoff_check.py",
    "tests/test_run_mvp_release_checklist.py",
    "tests/test_run_mvp_release_preflight.py",
    "tests/test_run_mvp_release_readiness.py",
    "tests/test_run_mvp_repo_release_health_check.py",
    "tests/test_print_mvp_release_handoff_summary.py",
    "tests/test_postgres_mvp_smoke_ci_evidence_contract.py",
)
_UNSAFE_EXAMPLE_FRAGMENTS = (
    "DATABASE_URL=",
    "BOT_TOKEN=",
    "TELEGRAM_WEBHOOK_SECRET_TOKEN=",
    "ADM02_ENSURE_ACCESS_ENABLE=",
    "OPERATIONAL_RETENTION_DELETE_ENABLE=",
    "postgres://",
    "postgresql://",
    "Bearer ",
    "PRIVATE KEY",
    "BEGIN ",
    "token=",
    "vpn://",
    "provider_issuance_ref",
    "issue_idempotency_key",
    "schema_version",
    "customer_ref",
    "provider_ref",
    "checkout_attempt_id",
    "internal_user_id",
)


def _read_backend(rel_path: str) -> str:
    return (_BACKEND_DIR / rel_path).read_text(encoding="utf-8")


def _read_repo(rel_path: str) -> str:
    return (_REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_mvp_release_package_complete_artifacts_exist() -> None:
    for rel_path in (*_RELEASE_SCRIPTS, *_DOCS, *_KEY_CONTRACT_TESTS):
        assert (_BACKEND_DIR / rel_path).exists()
    for rel_path in _WORKFLOWS:
        assert (_REPO_ROOT / rel_path).exists()
    for rel_path in _ROOT_DOCS:
        assert (_REPO_ROOT / rel_path).exists()


def test_manifest_includes_release_package_cross_references() -> None:
    body = _read_backend("docs/mvp_release_artifact_manifest.md")
    required_markers = (
        "backend/RELEASE_STATUS.md",
        "python scripts/run_mvp_release_readiness.py",
        "python scripts/run_mvp_repo_release_health_check.py",
        "python scripts/run_mvp_final_static_handoff_check.py",
        "python scripts/print_mvp_release_handoff_summary.py",
        "backend-mvp-release-readiness",
        "backend-postgres-mvp-smoke-validation",
        "Local Docker wrapper command remains separate",
        "python scripts/run_postgres_mvp_smoke_local.py",
        "python scripts/run_mvp_config_doctor.py --profile polling|webhook|internal-admin|retention|all",
        "tests/test_mvp_release_package_complete_contract.py",
        "tests/test_mvp_final_release_gate_contract.py",
        "tests/test_mvp_release_readiness_workflow_structure_contract.py",
        "docs/mvp_release_ci_trigger_decision.md",
    )
    for marker in required_markers:
        assert marker in body


def test_release_status_references_key_runbooks() -> None:
    body = _read_backend("RELEASE_STATUS.md")
    required_markers = (
        "docs/mvp_release_artifact_manifest.md",
        "docs/mvp_release_readiness_runbook.md",
        "tests/test_mvp_final_release_gate_contract.py",
        "python scripts/run_mvp_final_static_handoff_check.py",
    )
    for marker in required_markers:
        assert marker in body


def test_root_project_handoff_references_backend_release_status() -> None:
    body = _read_repo("PROJECT_HANDOFF.md")
    assert "backend/RELEASE_STATUS.md" in body


def test_lightweight_workflow_paths_include_root_project_handoff_marker() -> None:
    workflow = _read_repo(".github/workflows/backend-mvp-release-readiness.yml")
    assert "PROJECT_HANDOFF.md" in workflow


def test_readiness_runbook_references_release_flow_and_runtime_surfaces() -> None:
    body = _read_backend("docs/mvp_release_readiness_runbook.md")
    required_markers = (
        "backend/docs/mvp_release_artifact_manifest.md",
        "python scripts/run_mvp_release_checklist.py",
        "python scripts/run_mvp_release_preflight.py",
        "python scripts/run_mvp_config_doctor.py --profile polling",
        "python scripts/run_postgres_mvp_smoke_local.py",
        "/healthz",
        "/readyz",
        "ADM-01",
        "ADM-02",
    )
    for marker in required_markers:
        assert marker in body


def test_release_readiness_workflow_remains_static_and_bounded() -> None:
    workflow = _read_repo(".github/workflows/backend-mvp-release-readiness.yml")
    lowered = workflow.lower()
    assert "python scripts/run_mvp_repo_release_health_check.py" in workflow
    assert "python scripts/run_mvp_release_checklist.py" in workflow
    assert "python scripts/run_mvp_release_preflight.py" in workflow
    assert "python -m pytest -q tests/test_run_mvp_config_doctor.py" in workflow
    assert "docker compose" not in lowered
    assert "docker-compose" not in lowered
    assert "services:" not in lowered
    assert "${{ secrets." not in lowered
    assert "run_mvp_config_doctor.py --profile all" not in lowered


def test_final_static_handoff_script_references_workflow_structure_contract() -> None:
    handoff_script = _read_backend("scripts/run_mvp_final_static_handoff_check.py")
    assert "tests/test_mvp_release_readiness_workflow_structure_contract.py" in handoff_script
    assert "tests/test_mvp_release_staging_manifest_contract.py" in handoff_script
    assert "python" in handoff_script
    assert "-m" in handoff_script
    assert "pytest" in handoff_script
    assert "-q" in handoff_script


def test_final_release_docs_and_workflow_have_no_unsafe_examples() -> None:
    text_targets = (
        _read_backend("docs/mvp_release_artifact_manifest.md"),
        _read_backend("docs/mvp_release_readiness_runbook.md"),
        _read_repo(".github/workflows/backend-mvp-release-readiness.yml"),
    )
    lowered_targets = tuple(text.lower() for text in text_targets)
    for fragment in _UNSAFE_EXAMPLE_FRAGMENTS:
        lowered_fragment = fragment.lower()
        for target in lowered_targets:
            assert lowered_fragment not in target
