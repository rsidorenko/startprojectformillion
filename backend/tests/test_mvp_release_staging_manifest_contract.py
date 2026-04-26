"""Contract checks for MVP release staging manifest safety and coverage."""

from __future__ import annotations

from pathlib import Path


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _manifest_path() -> Path:
    return _backend_dir() / "docs" / "mvp_release_staging_manifest.md"


def _manifest_text() -> str:
    return _manifest_path().read_text(encoding="utf-8")


def test_staging_manifest_exists() -> None:
    assert _manifest_path().exists()


def test_staging_manifest_contains_required_warning_include_and_exclude_markers() -> None:
    body = _manifest_text()
    required_markers = (
        "do not run blanket `git add .`",
        "PROJECT_HANDOFF.md",
        ".github/workflows/backend-mvp-release-readiness.yml",
        "backend/RELEASE_STATUS.md",
        "backend/docs/mvp_release_artifact_manifest.md",
        "backend/docs/mvp_release_ci_trigger_decision.md",
        "backend/docs/mvp_release_readiness_runbook.md",
        "backend/scripts/run_mvp_release_readiness.py",
        "backend/scripts/run_mvp_release_checklist.py",
        "backend/scripts/run_mvp_release_preflight.py",
        "backend/scripts/run_mvp_config_doctor.py",
        "backend/scripts/run_mvp_repo_release_health_check.py",
        "backend/scripts/run_mvp_final_static_handoff_check.py",
        "backend/scripts/print_mvp_release_handoff_summary.py",
        "python scripts/run_mvp_final_static_handoff_check.py",
        "tests/test_mvp_release_staging_manifest_contract.py",
        ".cursor/plans/**",
        "backend/src/app/**",
        "backend/migrations/**",
        ".github/workflows/backend-postgres-mvp-smoke-validation.yml",
        "do not stage in this release-package commit",
    )
    for marker in required_markers:
        assert marker in body


def test_staging_manifest_has_no_forbidden_fragments() -> None:
    lowered = _manifest_text().lower()
    for forbidden in (
        "database_url=",
        "bot_token=",
        "telegram_webhook_secret_token=",
        "adm02_ensure_access_enable=",
        "operational_retention_delete_enable=",
        "postgres://",
        "postgresql://",
        "bearer ",
        "private key",
        "begin ",
        "token=",
        "vpn://",
        "provider_issuance_ref",
        "issue_idempotency_key",
        "schema_version",
        "customer_ref",
        "provider_ref",
        "checkout_attempt_id",
        "internal_user_id",
    ):
        assert forbidden not in lowered
