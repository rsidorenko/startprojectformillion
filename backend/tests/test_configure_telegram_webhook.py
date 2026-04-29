"""Focused tests for Telegram webhook operator configure tooling."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from app.security.telegram_webhook_policy import normalize_webhook_url_for_compare

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "configure_telegram_webhook.py"


def _load_script_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("configure_telegram_webhook", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _safe_env() -> dict[str, str]:
    return {
        "BOT_TOKEN": "1234567890:SAFE_TEST_TOKEN",
        "TELEGRAM_WEBHOOK_PUBLIC_URL": "https://webhook.test.local/telegram/webhook",
        "TELEGRAM_WEBHOOK_SECRET_TOKEN": "Webhook_Strong_Secret_1234567890",
        "TELEGRAM_WEBHOOK_ALLOWED_UPDATES": "message",
    }


def test_normalize_webhook_url_trailing_slash_equivalence() -> None:
    a = normalize_webhook_url_for_compare("https://webhook.example.com/path")
    b = normalize_webhook_url_for_compare("https://webhook.example.com/path/")
    assert a == b


def test_dry_run_success_with_safe_https_url_and_no_network_call(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    called = False

    def fake_api_post(**kwargs: Any) -> dict[str, Any]:
        nonlocal called
        called = True
        return {"ok": True}

    rc = script.run_configure_telegram_webhook(
        action="dry_run",
        env=_safe_env(),
        api_post=fake_api_post,
    )
    out = capsys.readouterr()
    assert rc == 0
    assert called is False
    assert "telegram_webhook_configure: dry_run" in out.out
    assert "action=set" in out.out
    assert "secret_token_configured=yes" in out.out
    assert "expected_allowed_updates_items=message" in out.out


def test_dry_run_fails_unsupported_allowed_updates(capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script_module()
    env = _safe_env()
    env["TELEGRAM_WEBHOOK_ALLOWED_UPDATES"] = "inline_query"
    rc = script.run_configure_telegram_webhook(action="dry_run", env=env, api_post=lambda **kwargs: {"ok": True})
    out = capsys.readouterr()
    assert rc == 1
    assert "issue_code=telegram_webhook_allowed_updates_unsupported_for_command_bot" in out.err


@pytest.mark.parametrize("missing_key", ("BOT_TOKEN", "TELEGRAM_WEBHOOK_PUBLIC_URL", "TELEGRAM_WEBHOOK_SECRET_TOKEN"))
def test_apply_rejects_missing_required_markers(
    missing_key: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _safe_env()
    env.pop(missing_key)
    rc = script.run_configure_telegram_webhook(action="apply", env=env, api_post=lambda **kwargs: {"ok": True})
    out = capsys.readouterr()
    assert rc == 1
    assert "telegram_webhook_configure: failed" in out.err


@pytest.mark.parametrize(
    "bad_url",
    (
        "http://example.com/telegram/webhook",
        "https://localhost/telegram/webhook",
        "https://127.0.0.1/telegram/webhook",
        "https://10.0.0.5/telegram/webhook",
        "https://webhook.test.local/telegram/webhook",
    ),
)
def test_apply_rejects_non_public_or_non_https_url(
    bad_url: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _safe_env()
    env["TELEGRAM_WEBHOOK_PUBLIC_URL"] = bad_url
    rc = script.run_configure_telegram_webhook(action="apply", env=env, api_post=lambda **kwargs: {"ok": True})
    out = capsys.readouterr()
    assert rc == 1
    assert "issue_code=telegram_webhook_public_url_invalid" in out.err


def test_apply_calls_set_webhook_with_desired_allowed_updates(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _safe_env()
    env["TELEGRAM_WEBHOOK_PUBLIC_URL"] = "https://webhook.example.com/telegram/webhook"
    env["TELEGRAM_WEBHOOK_ALLOWED_UPDATES"] = "message"
    calls: list[dict[str, Any]] = []

    def fake_api_post(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {"ok": True, "result": True}

    rc = script.run_configure_telegram_webhook(action="apply", env=env, api_post=fake_api_post)
    out = capsys.readouterr()
    assert rc == 0
    assert len(calls) == 1
    assert calls[0]["method"] == "setWebhook"
    assert calls[0]["payload"]["secret_token"] == env["TELEGRAM_WEBHOOK_SECRET_TOKEN"]
    assert calls[0]["payload"]["allowed_updates"] == ["message"]
    blob = (out.out + out.err).lower()
    assert "telegram_webhook_configure: ok" in blob
    assert env["BOT_TOKEN"].lower() not in blob
    assert env["TELEGRAM_WEBHOOK_SECRET_TOKEN"].lower() not in blob
    assert "action=set" in blob
    assert "secret_token_configured=yes" in blob


def test_verify_passes_when_url_and_allowed_updates_match(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _safe_env()
    env["TELEGRAM_WEBHOOK_PUBLIC_URL"] = "https://webhook.example.com/telegram/webhook"
    calls: list[dict[str, Any]] = []

    def fake_api_post(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "ok": True,
            "result": {
                "url": "https://webhook.example.com/telegram/webhook",
                "allowed_updates": ["message"],
                "pending_update_count": 2,
            },
        }

    rc = script.run_configure_telegram_webhook(action="verify", env=env, api_post=fake_api_post)
    out = capsys.readouterr()
    assert rc == 0
    assert len(calls) == 1
    assert calls[0]["method"] == "getWebhookInfo"
    blob = out.out.lower()
    assert "telegram_webhook_configure: ok" in blob
    assert "action=verify" in blob
    assert "url_match=yes" in blob
    assert "allowed_updates_match=yes" in blob
    assert "pending_update_count=2" in blob
    assert "secret_token_status_match=unknown" in blob
    assert "last_error_active=no" in blob
    assert env["BOT_TOKEN"].lower() not in blob.lower()
    assert env["TELEGRAM_WEBHOOK_SECRET_TOKEN"].lower() not in blob.lower()


def test_verify_passes_when_url_trailing_slash_differs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _safe_env()
    env["TELEGRAM_WEBHOOK_PUBLIC_URL"] = "https://webhook.example.com/telegram/webhook/"
    calls: list[dict[str, Any]] = []

    def fake_api_post(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "ok": True,
            "result": {
                "url": "https://webhook.example.com/telegram/webhook",
                "allowed_updates": ["message"],
                "pending_update_count": 0,
            },
        }

    rc = script.run_configure_telegram_webhook(action="verify", env=env, api_post=fake_api_post)
    assert rc == 0
    assert calls[0]["method"] == "getWebhookInfo"


def test_verify_fails_on_url_mismatch(capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script_module()
    env = _safe_env()
    env["TELEGRAM_WEBHOOK_PUBLIC_URL"] = "https://webhook.example.com/telegram/webhook"

    def fake_api_post(**kwargs: Any) -> dict[str, Any]:
        return {
            "ok": True,
            "result": {
                "url": "https://wrong.example.com/hook",
                "allowed_updates": ["message"],
                "pending_update_count": 0,
            },
        }

    rc = script.run_configure_telegram_webhook(action="verify", env=env, api_post=fake_api_post)
    out = capsys.readouterr()
    assert rc == 1
    assert "reason=telegram_webhook_verify_url_mismatch" in out.err
    assert "wrong.example.com/hook" not in (out.out + out.err).lower()


def test_verify_fails_on_allowed_updates_mismatch_when_actual_is_list(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _safe_env()
    env["TELEGRAM_WEBHOOK_PUBLIC_URL"] = "https://webhook.example.com/telegram/webhook"

    def fake_api_post(**kwargs: Any) -> dict[str, Any]:
        return {
            "ok": True,
            "result": {
                "url": "https://webhook.example.com/telegram/webhook",
                "allowed_updates": ["message", "edited_message"],
                "pending_update_count": 0,
            },
        }

    rc = script.run_configure_telegram_webhook(action="verify", env=env, api_post=fake_api_post)
    out = capsys.readouterr()
    assert rc == 1
    assert "reason=telegram_webhook_verify_allowed_updates_mismatch" in out.err


def test_verify_allowed_updates_unknown_when_field_absent(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _safe_env()
    env["TELEGRAM_WEBHOOK_PUBLIC_URL"] = "https://webhook.example.com/telegram/webhook"

    def fake_api_post(**kwargs: Any) -> dict[str, Any]:
        return {
            "ok": True,
            "result": {
                "url": "https://webhook.example.com/telegram/webhook",
                "pending_update_count": 0,
            },
        }

    rc = script.run_configure_telegram_webhook(action="verify", env=env, api_post=fake_api_post)
    out = capsys.readouterr()
    assert rc == 0
    assert "allowed_updates_match=unknown" in out.out


def test_verify_fails_on_last_error_without_printing_raw_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    env = _safe_env()
    env["TELEGRAM_WEBHOOK_PUBLIC_URL"] = "https://webhook.example.com/telegram/webhook"

    def fake_api_post(**kwargs: Any) -> dict[str, Any]:
        return {
            "ok": True,
            "result": {
                "url": "https://webhook.example.com/telegram/webhook",
                "allowed_updates": ["message"],
                "pending_update_count": 1,
                "last_error_message": "secret_value_leak_attempt_x",
                "last_error_date": 1710000000,
            },
        }

    rc = script.run_configure_telegram_webhook(action="verify", env=env, api_post=fake_api_post)
    out = capsys.readouterr()
    assert rc == 1
    assert "reason=telegram_webhook_verify_last_error_present" in out.err
    blob = (out.out + out.err).lower()
    assert "secret_value_leak_attempt_x" not in blob
    assert '"ok"' not in blob
    assert '"result"' not in blob
