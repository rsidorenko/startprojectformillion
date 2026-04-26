"""Unit tests for MVP config doctor script."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_mvp_config_doctor.py"
_TEST_TOKEN = "tok_for_doctor_tests_12345"
_TEST_SECRET = "secret_for_doctor_tests_67890"


def _load_script_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("run_mvp_config_doctor", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _base_env() -> dict[str, str]:
    return {"APP_ENV": "development"}


def test_polling_profile_missing_bot_token_fails_safely(capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script_module()
    code = script.main(["--profile", "polling"], env=_base_env())
    captured = capsys.readouterr()
    assert code == 1
    assert "mvp_config_doctor: fail" in captured.out
    assert _TEST_TOKEN not in captured.out


def test_polling_profile_with_token_passes_without_printing_token(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _base_env()
    env["BOT_TOKEN"] = _TEST_TOKEN
    code = script.main(["--profile", "polling"], env=env)
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.strip() == "mvp_config_doctor: ok"
    assert _TEST_TOKEN not in captured.out


def test_webhook_production_enabled_without_secret_fails_safely(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _base_env()
    env["APP_ENV"] = "production"
    env["TELEGRAM_WEBHOOK_HTTP_ENABLE"] = "1"
    code = script.main(["--profile", "webhook"], env=env)
    captured = capsys.readouterr()
    assert code == 1
    assert "mvp_config_doctor: fail" in captured.out
    assert "issue_code=webhook_secret_required" in captured.out


def test_webhook_local_missing_secret_requires_insecure_opt_in(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _base_env()
    env["TELEGRAM_WEBHOOK_HTTP_ENABLE"] = "yes"
    code = script.main(["--profile", "webhook"], env=env)
    captured = capsys.readouterr()
    assert code == 1
    assert "issue_code=webhook_insecure_local_opt_in_required" in captured.out


def test_webhook_local_with_insecure_opt_in_passes_without_printing_opt_in(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _base_env()
    env["TELEGRAM_WEBHOOK_HTTP_ENABLE"] = "1"
    env["TELEGRAM_WEBHOOK_ALLOW_INSECURE_LOCAL"] = "true"
    code = script.main(["--profile", "webhook"], env=env)
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.strip() == "mvp_config_doctor: ok"
    assert "TELEGRAM_WEBHOOK_ALLOW_INSECURE_LOCAL=" not in captured.out


def test_internal_admin_profile_validates_allowlist_and_adm02_dependencies(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _base_env()
    env["ADM02_ENSURE_ACCESS_ENABLE"] = "1"
    code = script.main(["--profile", "internal-admin"], env=env)
    captured = capsys.readouterr()
    assert code == 1
    assert "issue_code=adm02_mutation_requires_internal_admin_http_enabled" in captured.out
    assert "issue_code=missing_adm01_internal_http_allowlist" in captured.out
    assert "issue_code=missing_database_url" in captured.out


def test_retention_profile_rejects_invalid_audit_retention_days(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _base_env()
    env["ADM02_AUDIT_RETENTION_DAYS"] = "0"
    code = script.main(["--profile", "retention"], env=env)
    captured = capsys.readouterr()
    assert code == 1
    assert "issue_code=invalid_adm02_audit_retention_days" in captured.out


def test_unknown_profile_fails_safely(capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script_module()
    code = script.main(["--profile", "unknown"], env=_base_env())
    captured = capsys.readouterr()
    assert code == 1
    assert "issue_code=unknown_profile" in captured.out


def test_all_profile_aggregates_checks_without_printing_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _base_env()
    env["APP_ENV"] = "production"
    env["TELEGRAM_WEBHOOK_HTTP_ENABLE"] = "1"
    env["BOT_TOKEN"] = _TEST_TOKEN
    env["TELEGRAM_WEBHOOK_SECRET_TOKEN"] = _TEST_SECRET
    env["DATABASE_URL"] = "postgresql://doctor-user:doctor-pass@localhost:5432/doctor_db?sslmode=require"
    env["ADM01_INTERNAL_HTTP_ENABLE"] = "1"
    env["ADM01_INTERNAL_HTTP_ALLOWLIST"] = "principal-1"
    code = script.main(["--profile", "all"], env=env)
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.strip() == "mvp_config_doctor: ok"
    assert _TEST_TOKEN not in captured.out
    assert _TEST_SECRET not in captured.out
    assert "postgresql://" not in captured.out.lower()


def test_output_has_no_forbidden_fragments(capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script_module()
    env = _base_env()
    env["APP_ENV"] = "production"
    env["TELEGRAM_WEBHOOK_HTTP_ENABLE"] = "1"
    _ = script.main(["--profile", "all"], env=env)
    captured = capsys.readouterr()
    output_blob = (captured.out + captured.err).lower()
    for fragment in (
        _TEST_TOKEN.lower(),
        _TEST_SECRET.lower(),
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
        "900011",
        "42",
    ):
        assert fragment not in output_blob
