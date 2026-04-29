"""Focused tests for customer-facing launch readiness preflight."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_launch_readiness.py"
_TEST_TOKEN = "1234567890:AAAbbbCCCdddEEEfffGGG"
_TEST_WEBHOOK_SECRET = "Whk_Secret_Value_1234567890"
_TEST_FULFILLMENT_SECRET = "Pay_Secret_Value_1234567890"
_TEST_CHECKOUT_REFERENCE_SECRET = "CheckoutRef_Secret_Value_1234567890"
_TEST_DSN = "postgresql://user:password@db.example.com:5432/app?sslmode=require&password=raw"


def _load_script_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_launch_readiness", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _strict_env() -> dict[str, str]:
    return {
        "APP_ENV": "production",
        "BOT_TOKEN": _TEST_TOKEN,
        "DATABASE_URL": "postgresql://user:password@db.example.com:5432/app?sslmode=require",
        "TELEGRAM_STOREFRONT_PLAN_NAME": "VPN Pro",
        "TELEGRAM_STOREFRONT_PLAN_PRICE": "$9.99 / month",
        "TELEGRAM_STOREFRONT_CHECKOUT_URL": "https://example.com/checkout",
        "TELEGRAM_STOREFRONT_RENEWAL_URL": "https://example.com/renew",
        "TELEGRAM_STOREFRONT_SUPPORT_URL": "https://example.com/support",
        "PAYMENT_FULFILLMENT_HTTP_ENABLE": "1",
        "PAYMENT_FULFILLMENT_WEBHOOK_SECRET": _TEST_FULFILLMENT_SECRET,
        "TELEGRAM_CHECKOUT_REFERENCE_SECRET": _TEST_CHECKOUT_REFERENCE_SECRET,
        "TELEGRAM_CHECKOUT_REFERENCE_MAX_AGE_SECONDS": str(7 * 24 * 60 * 60),
        "TELEGRAM_WEBHOOK_HTTP_ENABLE": "1",
        "TELEGRAM_WEBHOOK_SECRET_TOKEN": _TEST_WEBHOOK_SECRET,
        "TELEGRAM_WEBHOOK_PUBLIC_URL": "https://webhook.example.com/telegram/webhook",
        "TELEGRAM_ACCESS_RESEND_ENABLE": "1",
        "ACCESS_RECONCILE_SCHEDULE_ACK": "1",
        "ACCESS_RECONCILE_MAX_INTERVAL_SECONDS": "3600",
        "SUBSCRIPTION_DEFAULT_PERIOD_DAYS": "30",
    }


def test_strict_mode_passes_with_complete_safe_env(capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script_module()
    code = script.main(["--strict"], env=_strict_env())
    captured = capsys.readouterr()
    assert code == 0
    assert "launch_readiness_preflight: ok" in captured.out
    assert "mode=strict" in captured.out
    assert "telegram_webhook_allowed_updates_items=message" in captured.out


def test_strict_mode_fails_when_webhook_allowed_updates_invalid(capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script_module()
    env = _strict_env()
    env["TELEGRAM_WEBHOOK_ALLOWED_UPDATES"] = "message,bad!"
    code = script.main(["--strict"], env=env)
    captured = capsys.readouterr()
    assert code == 1
    assert "issue_code=telegram_webhook_allowed_updates_invalid" in captured.out


def test_strict_mode_fails_when_webhook_allowed_updates_unsupported(capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script_module()
    env = _strict_env()
    env["TELEGRAM_WEBHOOK_ALLOWED_UPDATES"] = "inline_query"
    code = script.main(["--strict"], env=env)
    captured = capsys.readouterr()
    assert code == 1
    assert "issue_code=telegram_webhook_allowed_updates_unsupported_for_command_bot" in captured.out


def test_strict_mode_fails_missing_checkout_url(capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script_module()
    env = _strict_env()
    env.pop("TELEGRAM_STOREFRONT_CHECKOUT_URL")
    code = script.main(["--strict"], env=env)
    captured = capsys.readouterr()
    assert code == 1
    assert "issue_code=storefront_checkout_url_missing" in captured.out


def test_strict_mode_fails_missing_fulfillment_secret(capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script_module()
    env = _strict_env()
    env.pop("PAYMENT_FULFILLMENT_WEBHOOK_SECRET")
    code = script.main(["--strict"], env=env)
    captured = capsys.readouterr()
    assert code == 1
    assert "issue_code=payment_fulfillment_secret_missing" in captured.out


def test_strict_mode_fails_when_webhook_secret_too_weak(capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script_module()
    env = _strict_env()
    env["TELEGRAM_WEBHOOK_SECRET_TOKEN"] = "weakweakweakweakweakweak"
    code = script.main(["--strict"], env=env)
    captured = capsys.readouterr()
    assert code == 1
    assert "issue_code=telegram_webhook_secret_too_weak" in captured.out


def test_strict_mode_fails_when_webhook_public_url_missing(capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script_module()
    env = _strict_env()
    env.pop("TELEGRAM_WEBHOOK_PUBLIC_URL")
    code = script.main(["--strict"], env=env)
    captured = capsys.readouterr()
    assert code == 1
    assert "issue_code=telegram_webhook_public_url_missing" in captured.out


def test_default_mode_with_webhook_disabled_does_not_require_webhook_secret(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _strict_env()
    env.pop("TELEGRAM_WEBHOOK_SECRET_TOKEN")
    env["TELEGRAM_WEBHOOK_HTTP_ENABLE"] = "0"
    code = script.main([], env=env)
    captured = capsys.readouterr()
    assert code == 0
    assert "issue_code=telegram_webhook_secret_missing" not in captured.out


def test_strict_mode_fails_missing_checkout_reference_secret(capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script_module()
    env = _strict_env()
    env.pop("TELEGRAM_CHECKOUT_REFERENCE_SECRET")
    code = script.main(["--strict"], env=env)
    captured = capsys.readouterr()
    assert code == 1
    assert "issue_code=checkout_reference_secret_missing" in captured.out


def test_invalid_or_suspicious_urls_fail(capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script_module()
    env = _strict_env()
    env["TELEGRAM_STOREFRONT_CHECKOUT_URL"] = "http://example.com/checkout"
    env["TELEGRAM_STOREFRONT_SUPPORT_URL"] = "https://example.com/support?token=secret"
    code = script.main(["--strict"], env=env)
    captured = capsys.readouterr()
    assert code == 1
    assert "issue_code=storefront_checkout_url_invalid" in captured.out
    assert "issue_code=storefront_support_url_invalid" in captured.out
    assert "issue_code=storefront_url_contains_suspicious_query_pattern" in captured.out


def test_default_mode_allows_safe_fallback_with_warning(capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script_module()
    env = _strict_env()
    env.pop("TELEGRAM_STOREFRONT_PLAN_NAME")
    env.pop("TELEGRAM_STOREFRONT_PLAN_PRICE")
    code = script.main([], env=env)
    captured = capsys.readouterr()
    assert code == 0
    assert "warn_code=storefront_plan_name_missing" in captured.out
    assert "warn_code=storefront_plan_price_missing" in captured.out


def test_strict_mode_fails_when_checkout_reference_ttl_uses_default_without_ack(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _strict_env()
    env.pop("TELEGRAM_CHECKOUT_REFERENCE_MAX_AGE_SECONDS")
    code = script.main(["--strict"], env=env)
    captured = capsys.readouterr()
    assert code == 1
    assert "issue_code=checkout_reference_ttl_default_not_explicitly_accepted" in captured.out


def test_strict_mode_accepts_default_checkout_reference_ttl_with_ack(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _strict_env()
    env.pop("TELEGRAM_CHECKOUT_REFERENCE_MAX_AGE_SECONDS")
    env["TELEGRAM_CHECKOUT_REFERENCE_DEFAULT_TTL_ACCEPTED"] = "1"
    code = script.main(["--strict"], env=env)
    captured = capsys.readouterr()
    assert code == 0
    assert "checkout_reference_ttl_classification=recommended" in captured.out


def test_strict_mode_fails_when_checkout_reference_ttl_too_small(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _strict_env()
    env["TELEGRAM_CHECKOUT_REFERENCE_MAX_AGE_SECONDS"] = "120"
    code = script.main(["--strict"], env=env)
    captured = capsys.readouterr()
    assert code == 1
    assert "issue_code=checkout_reference_ttl_too_small_for_checkout_flow" in captured.out


def test_strict_mode_fails_when_checkout_reference_ttl_too_large(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _strict_env()
    env["TELEGRAM_CHECKOUT_REFERENCE_MAX_AGE_SECONDS"] = str((30 * 24 * 60 * 60) + 1)
    code = script.main(["--strict"], env=env)
    captured = capsys.readouterr()
    assert code == 1
    assert "issue_code=checkout_reference_ttl_too_large_for_replay_safety" in captured.out


def test_strict_mode_fails_without_access_reconcile_schedule_ack(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _strict_env()
    env.pop("ACCESS_RECONCILE_SCHEDULE_ACK")
    code = script.main(["--strict"], env=env)
    captured = capsys.readouterr()
    assert code == 1
    assert "issue_code=access_reconcile_schedule_ack_missing" in captured.out


def test_strict_mode_fails_with_access_reconcile_interval_too_small(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _strict_env()
    env["ACCESS_RECONCILE_MAX_INTERVAL_SECONDS"] = "299"
    code = script.main(["--strict"], env=env)
    captured = capsys.readouterr()
    assert code == 1
    assert "issue_code=access_reconcile_max_interval_seconds_too_small" in captured.out


def test_strict_mode_fails_with_access_reconcile_interval_too_large(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _strict_env()
    env["ACCESS_RECONCILE_MAX_INTERVAL_SECONDS"] = "86401"
    code = script.main(["--strict"], env=env)
    captured = capsys.readouterr()
    assert code == 1
    assert "issue_code=access_reconcile_max_interval_seconds_too_large" in captured.out


def test_strict_mode_passes_with_safe_access_reconcile_schedule(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _strict_env()
    env["ACCESS_RECONCILE_SCHEDULE_ACK"] = "1"
    env["ACCESS_RECONCILE_MAX_INTERVAL_SECONDS"] = "3600"
    code = script.main(["--strict"], env=env)
    captured = capsys.readouterr()
    assert code == 0
    assert "access_reconcile_schedule_ack=acknowledged" in captured.out
    assert "access_reconcile_max_interval_seconds=3600" in captured.out
    assert "access_reconcile_interval_classification=recommended" in captured.out
    assert "access_reconcile_operator_command=python scripts/reconcile_expired_access.py" in captured.out


def test_default_mode_warns_for_missing_access_reconcile_schedule_but_does_not_fail(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _strict_env()
    env.pop("ACCESS_RECONCILE_SCHEDULE_ACK")
    env.pop("ACCESS_RECONCILE_MAX_INTERVAL_SECONDS")
    code = script.main([], env=env)
    captured = capsys.readouterr()
    assert code == 0
    assert "warn_code=access_reconcile_schedule_ack_missing" in captured.out
    assert "warn_code=access_reconcile_max_interval_seconds_missing" in captured.out


def test_output_redacts_sensitive_values_and_query_fragments(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _strict_env()
    env["DATABASE_URL"] = _TEST_DSN
    env["TELEGRAM_STOREFRONT_CHECKOUT_URL"] = "https://example.com/checkout?signature=abc"
    _ = script.main(["--strict"], env=env)
    captured = capsys.readouterr()
    output_blob = (captured.out + captured.err).lower()
    assert "database=postgresql://db.example.com:5432/<redacted>" in output_blob
    assert "checkout=https://example.com/<redacted>" in output_blob
    assert "checkout_reference_ttl_seconds=604800" in output_blob
    assert "checkout_reference_ttl_classification=recommended" in output_blob
    assert "access_reconcile_schedule_ack=acknowledged" in output_blob
    assert "access_reconcile_max_interval_seconds=3600" in output_blob
    assert "access_reconcile_interval_classification=recommended" in output_blob
    assert "subscription_default_period_days=30" in output_blob
    assert "subscription_default_period_classification=recommended" in output_blob
    for fragment in (
        _TEST_TOKEN.lower(),
        _TEST_WEBHOOK_SECRET.lower(),
        _TEST_FULFILLMENT_SECRET.lower(),
        _TEST_CHECKOUT_REFERENCE_SECRET.lower(),
        "password@",
        "signature=abc",
        "token=",
        "secret=",
        "postgresql://user:password",
    ):
        assert fragment not in output_blob


def test_strict_mode_from_env_flag(capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script_module()
    env = _strict_env()
    env["LAUNCH_PREFLIGHT_STRICT"] = "1"
    env.pop("TELEGRAM_STOREFRONT_CHECKOUT_URL")
    code = script.main([], env=env)
    captured = capsys.readouterr()
    assert code == 1
    assert "mode=strict" in captured.out
    assert "issue_code=storefront_checkout_url_missing" in captured.out


def test_strict_mode_fails_when_subscription_period_too_small(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _strict_env()
    env["SUBSCRIPTION_DEFAULT_PERIOD_DAYS"] = "0"
    code = script.main(["--strict"], env=env)
    captured = capsys.readouterr()
    assert code == 1
    assert "issue_code=subscription_default_period_days_too_small" in captured.out


def test_strict_mode_fails_when_subscription_period_too_large(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _strict_env()
    env["SUBSCRIPTION_DEFAULT_PERIOD_DAYS"] = "3661"
    code = script.main(["--strict"], env=env)
    captured = capsys.readouterr()
    assert code == 1
    assert "issue_code=subscription_default_period_days_too_large" in captured.out
