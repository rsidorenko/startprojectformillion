"""Final static/test-only release gate contract for MVP package closure."""

from __future__ import annotations

from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_DIR.parent

_KEY_FINAL_CONTRACT_TESTS = (
    "tests/test_mvp_release_package_complete_contract.py",
    "tests/test_mvp_release_readiness_workflow_structure_contract.py",
    "tests/test_mvp_release_scripts_output_contract.py",
    "tests/test_mvp_release_artifact_manifest_contract.py",
    "tests/test_mvp_release_staging_manifest_contract.py",
    "tests/test_mvp_release_readiness_runbook_contract.py",
    "tests/test_mvp_release_readiness_ci_evidence_contract.py",
    "tests/test_run_mvp_repo_release_health_check.py",
    "tests/test_release_status_contract.py",
    "tests/test_print_mvp_release_handoff_summary.py",
    "tests/test_postgres_mvp_smoke_ci_evidence_contract.py",
    "tests/test_project_handoff_contract.py",
)
_KEY_FINAL_SCRIPTS = (
    "scripts/run_mvp_release_readiness.py",
    "scripts/run_mvp_repo_release_health_check.py",
    "scripts/run_mvp_final_static_handoff_check.py",
    "scripts/print_mvp_release_handoff_summary.py",
)
_KEY_FINAL_DOCS = (
    "RELEASE_STATUS.md",
    "docs/mvp_release_artifact_manifest.md",
    "docs/mvp_release_readiness_runbook.md",
    "docs/mvp_release_ci_trigger_decision.md",
    "docs/mvp_release_staging_manifest.md",
)
_KEY_FINAL_ROOT_DOCS = ("PROJECT_HANDOFF.md",)
_WORKFLOW_REQUIRED_MARKERS = (
    "python scripts/run_mvp_repo_release_health_check.py",
    "python scripts/run_mvp_release_checklist.py",
    "python scripts/run_mvp_release_preflight.py",
    "python scripts/run_mvp_final_static_handoff_check.py",
    "python -m pytest -q tests/test_run_mvp_config_doctor.py",
)
_WORKFLOW_TRIGGER_PATH_MARKERS = (
    "PROJECT_HANDOFF.md",
    "backend/RELEASE_STATUS.md",
    "backend/docs/mvp_release_artifact_manifest.md",
    "backend/scripts/run_mvp_final_static_handoff_check.py",
    "backend/tests/test_project_handoff_contract.py",
    "backend/tests/test_*release*",
    "backend/tests/test_*handoff*",
)
_FINAL_HANDOFF_SCRIPT_MARKERS = (
    "tests/test_mvp_release_readiness_workflow_structure_contract.py",
    "tests/test_mvp_release_staging_manifest_contract.py",
    "python",
    "-m",
    "pytest",
    "-q",
)
_FINAL_DOCS_SCOPE_MARKERS = (
    "not fully production certified",
    "Known manual gates",
    "Explicit out-of-scope",
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


def test_mvp_final_gate_required_files_exist() -> None:
    for rel_path in (*_KEY_FINAL_CONTRACT_TESTS, *_KEY_FINAL_SCRIPTS, *_KEY_FINAL_DOCS):
        assert (_BACKEND_DIR / rel_path).exists()
    for rel_path in _KEY_FINAL_ROOT_DOCS:
        assert (_REPO_ROOT / rel_path).exists()


def test_mvp_final_gate_workflow_references_static_release_commands() -> None:
    workflow = _read_repo(".github/workflows/backend-mvp-release-readiness.yml")
    for marker in _WORKFLOW_REQUIRED_MARKERS:
        assert marker in workflow


def test_mvp_final_gate_workflow_paths_cover_root_handoff_and_final_markers() -> None:
    workflow = _read_repo(".github/workflows/backend-mvp-release-readiness.yml")
    for marker in _WORKFLOW_TRIGGER_PATH_MARKERS:
        assert marker in workflow


def test_mvp_final_gate_docs_capture_non_full_prod_and_manual_scope() -> None:
    release_status = _read_backend("RELEASE_STATUS.md")
    manifest = _read_backend("docs/mvp_release_artifact_manifest.md")
    runbook = _read_backend("docs/mvp_release_readiness_runbook.md")
    project_handoff = _read_repo("PROJECT_HANDOFF.md")

    assert "tests/test_mvp_final_release_gate_contract.py" in release_status
    assert "tests/test_mvp_final_release_gate_contract.py" in manifest
    assert "backend/RELEASE_STATUS.md" in project_handoff
    assert "backend/tests/test_mvp_final_release_gate_contract.py" in project_handoff
    assert "backend-mvp-release-readiness" in project_handoff
    assert "backend-postgres-mvp-smoke-validation" in project_handoff
    assert "ready for operator validation" in project_handoff
    assert "not full production certification" in project_handoff

    docs_blob = "\n".join((release_status, manifest, runbook))
    for marker in _FINAL_DOCS_SCOPE_MARKERS:
        assert marker in docs_blob


def test_mvp_final_gate_ci_trigger_decision_exists_and_captures_scope() -> None:
    decision = _read_backend("docs/mvp_release_ci_trigger_decision.md")
    required_markers = (
        "PROJECT_HANDOFF.md",
        "backend release/handoff docs/scripts/tests",
        "backend-mvp-release-readiness",
    )
    for marker in required_markers:
        assert marker in decision


def test_mvp_final_gate_handoff_script_runs_workflow_structure_contract() -> None:
    handoff_script = _read_backend("scripts/run_mvp_final_static_handoff_check.py")
    for marker in _FINAL_HANDOFF_SCRIPT_MARKERS:
        assert marker in handoff_script


def test_mvp_final_gate_docs_and_workflow_have_no_unsafe_examples() -> None:
    text_targets = (
        _read_backend("RELEASE_STATUS.md"),
        _read_backend("docs/mvp_release_artifact_manifest.md"),
        _read_backend("docs/mvp_release_readiness_runbook.md"),
        _read_repo("PROJECT_HANDOFF.md"),
        _read_repo(".github/workflows/backend-mvp-release-readiness.yml"),
    )
    lowered_targets = tuple(text.lower() for text in text_targets)

    for fragment in _UNSAFE_EXAMPLE_FRAGMENTS:
        lowered_fragment = fragment.lower()
        for target in lowered_targets:
            assert lowered_fragment not in target
