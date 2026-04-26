"""Contract checks for MVP release artifact manifest coverage and safety."""

from __future__ import annotations

from pathlib import Path


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _manifest_path() -> Path:
    return _backend_dir() / "docs" / "mvp_release_artifact_manifest.md"


def _manifest_text() -> str:
    return _manifest_path().read_text(encoding="utf-8")


def test_manifest_exists() -> None:
    assert _manifest_path().exists()


def test_manifest_contains_required_scripts_workflows_surfaces_and_gates() -> None:
    body = _manifest_text()

    required_markers = (
        "python scripts/run_mvp_release_readiness.py",
        "python scripts/run_mvp_final_static_handoff_check.py",
        "python scripts/run_mvp_release_checklist.py",
        "python scripts/run_mvp_repo_release_health_check.py",
        "python scripts/print_mvp_release_handoff_summary.py",
        "python scripts/run_mvp_release_preflight.py",
        "python scripts/run_mvp_config_doctor.py --profile polling|webhook|internal-admin|retention|all",
        "python scripts/run_postgres_mvp_smoke_local.py",
        "python scripts/run_postgres_mvp_smoke.py",
        "backend-mvp-release-readiness",
        "PROJECT_HANDOFF.md",
        "backend release/handoff docs/scripts/tests",
        "backend-postgres-mvp-smoke-validation",
        "Telegram polling",
        "Telegram webhook ASGI entrypoint",
        "/healthz",
        "/readyz",
        "ADM-01 diagnostics",
        "ADM-02 ensure-access remediation",
        "ADM-02 audit readback",
        "TELEGRAM_WEBHOOK_SECRET_TOKEN",
        "TELEGRAM_WEBHOOK_ALLOW_INSECURE_LOCAL",
        "ADM02_ENSURE_ACCESS_ENABLE",
        "OPERATIONAL_RETENTION_DELETE_ENABLE",
        "ADM02_AUDIT_RETENTION_DAYS",
        "DATABASE_URL",
        "BOT_TOKEN",
        "Real operator config doctor run with actual environment",
        "Local Docker smoke execution",
        "Live deployment `/healthz` and `/readyz` verification",
        "setWebhook",
        "Retention delete approval gate",
        "public billing ingress",
        "real provider SDK",
        "raw credential/config delivery",
        "full production SLO/alerting certification",
        "read-only and informational",
        "does not replace readiness/preflight/config doctor/local smoke",
        "backend/docs/mvp_release_ci_trigger_decision.md",
        "tests/test_mvp_release_readiness_workflow_structure_contract.py",
        "does not run Docker/DB/runtime",
    )
    for marker in required_markers:
        assert marker in body


def test_manifest_has_no_sensitive_examples_or_raw_identifier_fragments() -> None:
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
        "raw telegram update id",
        "raw telegram user id",
    ):
        assert forbidden not in lowered
