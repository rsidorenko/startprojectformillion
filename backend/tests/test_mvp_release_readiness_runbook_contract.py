"""Contract checks for MVP release readiness runbook coverage and safety."""

from __future__ import annotations

from pathlib import Path


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_text(rel_path: str) -> str:
    return (_backend_dir() / rel_path).read_text(encoding="utf-8")


def test_release_readiness_runbook_documents_required_commands_and_policies() -> None:
    body = _read_text("docs/mvp_release_readiness_runbook.md")

    assert "python scripts/validate_release_candidate.py" in body
    assert "python scripts/configure_telegram_webhook.py" in body
    assert "python scripts/configure_telegram_webhook.py --apply" in body
    assert "python scripts/configure_telegram_webhook.py --verify" in body
    assert "python scripts/run_mvp_release_readiness.py" in body
    assert "python scripts/run_mvp_repo_release_health_check.py" in body
    assert "--config-profile polling" in body
    assert "--config-profile webhook" in body
    assert "--config-profile internal-admin" in body
    assert "--config-profile retention" in body
    assert "--config-profile all" in body
    assert "python scripts/run_mvp_release_preflight.py" in body
    assert "python scripts/run_mvp_config_doctor.py --profile polling" in body
    assert "python scripts/run_mvp_config_doctor.py --profile webhook" in body
    assert "python scripts/run_mvp_config_doctor.py --profile internal-admin" in body
    assert "python scripts/run_mvp_config_doctor.py --profile retention" in body
    assert "python scripts/run_postgres_mvp_smoke_local.py" in body
    assert "/healthz" in body
    assert "/readyz" in body
    assert "ADM-01" in body
    assert "ADM-02" in body
    assert "dry-run" in body.lower()
    assert "OPERATIONAL_RETENTION_DELETE_ENABLE" in body
    assert "public billing ingress" in body.lower()
    assert "provider sdk" in body.lower()
    assert "real credential/config delivery" in body.lower()
    assert "mvp_release_preflight: ok" in body
    assert "mvp_config_doctor: ok" in body
    assert "release_candidate_validation: ok" in body
    assert "release_candidate_validation: failed" in body
    assert "TELEGRAM_WEBHOOK_PUBLIC_URL" in body
    assert "TELEGRAM_WEBHOOK_ALLOWED_UPDATES" in body
    assert "secret_token_status_match=unknown" in body
    assert "allowed_updates_match=unknown" in body
    assert "never runs `configure_telegram_webhook.py --verify`" in body
    assert ".github/workflows/backend-postgres-mvp-smoke-validation.yml" in body
    assert "slice1-postgres-mvp-smoke" in body
    assert "Run release candidate validator (blocking final gate)" in body


def test_release_readiness_runbook_has_no_raw_secret_or_dsn_examples() -> None:
    body = _read_text("docs/mvp_release_readiness_runbook.md").lower()
    for forbidden in (
        "database_url=",
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
        "telegram_webhook_secret_token=",
        "telegram_webhook_allow_insecure_local=",
    ):
        assert forbidden not in body


def test_existing_runbooks_cross_reference_release_readiness_runbook() -> None:
    marker = "backend/docs/mvp_release_readiness_runbook.md"
    assert marker in _read_text("docs/postgres_mvp_smoke_runbook.md")
    assert marker in _read_text("docs/telegram_access_resend_runbook.md")
    assert marker in _read_text("docs/admin_support_internal_read_gate_runbook.md")
