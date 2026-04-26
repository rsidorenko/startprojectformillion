"""Contract checks for final MVP release status handoff document."""

from __future__ import annotations

from pathlib import Path


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _status_path() -> Path:
    return _backend_dir() / "RELEASE_STATUS.md"


def _status_text() -> str:
    return _status_path().read_text(encoding="utf-8")


def test_release_status_exists() -> None:
    assert _status_path().exists()


def test_release_status_contains_required_markers() -> None:
    body = _status_text()
    required_markers = (
        "python scripts/run_mvp_release_readiness.py",
        "python scripts/run_mvp_final_static_handoff_check.py",
        "tests/test_mvp_release_readiness_workflow_structure_contract.py",
        "backend-mvp-release-readiness",
        "PROJECT_HANDOFF.md",
        "backend release/handoff docs/scripts/tests",
        "backend-postgres-mvp-smoke-validation",
        "python scripts/run_mvp_config_doctor.py --profile polling|webhook|internal-admin|retention|all",
        "python scripts/run_postgres_mvp_smoke_local.py",
        "/healthz",
        "/readyz",
        "setWebhook",
        "retention dry-run before any delete opt-in",
        "fail-closed",
        "rate limit and dedup",
        "ADM-02 ensure-access path remains explicit opt-in",
        "durable audit is redacted and supports readback",
        "bounded-output contracts",
        "public billing ingress",
        "real provider SDK",
        "raw credential/config delivery",
        "full production SLO/alerting certification",
        "external observability pipeline validation",
        "docs/mvp_release_artifact_manifest.md",
        "docs/mvp_release_readiness_runbook.md",
        "docs/postgres_mvp_smoke_runbook.md",
        "docs/telegram_access_resend_runbook.md",
        "docs/admin_support_internal_read_gate_runbook.md",
    )
    for marker in required_markers:
        assert marker in body


def test_release_status_has_no_forbidden_fragments() -> None:
    lowered = _status_text().lower()
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
