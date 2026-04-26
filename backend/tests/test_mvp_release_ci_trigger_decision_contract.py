"""Contract checks for MVP release CI trigger decision note."""

from __future__ import annotations

from pathlib import Path


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _decision_path() -> Path:
    return _backend_dir() / "docs" / "mvp_release_ci_trigger_decision.md"


def _decision_text() -> str:
    return _decision_path().read_text(encoding="utf-8")


def test_ci_trigger_decision_doc_exists() -> None:
    assert _decision_path().exists()


def test_ci_trigger_decision_doc_contains_required_markers() -> None:
    body = _decision_text()
    required_markers = (
        "PROJECT_HANDOFF.md",
        "backend release/handoff docs/scripts/tests",
        "backend-mvp-release-readiness",
        "no Docker/local smoke",
        "no DB service",
        "DATABASE_URL",
        "no `${{ secrets.* }}`",
        "no live Telegram/provider checks",
        "no real `run_mvp_config_doctor.py --profile all` gate",
        "tests/test_mvp_release_readiness_ci_evidence_contract.py",
        "tests/test_run_mvp_repo_release_health_check.py",
        "tests/test_mvp_final_release_gate_contract.py",
        "tests/test_mvp_release_package_complete_contract.py",
        "python scripts/run_mvp_final_static_handoff_check.py",
    )
    for marker in required_markers:
        assert marker in body


def test_ci_trigger_decision_doc_has_no_forbidden_fragments() -> None:
    lowered = _decision_text().lower()
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
