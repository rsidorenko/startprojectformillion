"""Unit tests for release candidate validation gate script."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_release_candidate.py"


def _load_script_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_release_candidate", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _safe_env() -> dict[str, str]:
    return {
        "BOT_TOKEN": "1234567890:ABCdef",
        "DATABASE_URL": "postgresql://db.example.local/app",
        "TELEGRAM_STOREFRONT_CHECKOUT_URL": "https://checkout.example.local/pay",
        "TELEGRAM_STOREFRONT_SUPPORT_URL": "https://support.example.local/help",
        "TELEGRAM_STOREFRONT_PLAN_NAME": "VPN Pro",
        "TELEGRAM_STOREFRONT_PLAN_PRICE": "$9.99",
        "PAYMENT_FULFILLMENT_HTTP_ENABLE": "1",
        "PAYMENT_FULFILLMENT_WEBHOOK_SECRET": "safe_test_secret",
        "TELEGRAM_CHECKOUT_REFERENCE_SECRET": "safe_checkout_ref_secret",
        "TELEGRAM_CHECKOUT_REFERENCE_MAX_AGE_SECONDS": "604800",
        "SUBSCRIPTION_DEFAULT_PERIOD_DAYS": "30",
        "TELEGRAM_ACCESS_RESEND_ENABLE": "1",
        "ACCESS_RECONCILE_SCHEDULE_ACK": "1",
        "ACCESS_RECONCILE_MAX_INTERVAL_SECONDS": "3600",
        "TELEGRAM_WEBHOOK_PUBLIC_URL": "https://webhook.example.com/telegram/webhook",
        "TELEGRAM_WEBHOOK_SECRET_TOKEN": "Webhook_Strong_Secret_1234567890",
        "TELEGRAM_WEBHOOK_HTTP_ENABLE": "1",
        "TELEGRAM_WEBHOOK_ALLOWED_UPDATES": "message",
    }


def test_release_validator_success_path_with_safe_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    calls: list[list[str]] = []

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(list(args[0]))
        return subprocess.CompletedProcess(args[0], 0, stdout="child-ok", stderr="")

    monkeypatch.setattr(script.subprocess, "run", fake_run)
    rc = script.run_release_candidate_validation(env=_safe_env())
    out = capsys.readouterr()

    assert rc == 0
    assert calls == [
        ["python", "scripts/run_mvp_release_preflight.py"],
        ["python", "scripts/check_launch_readiness.py", "--strict"],
        ["python", "scripts/configure_telegram_webhook.py", "--dry-run"],
        ["python", "scripts/run_postgres_mvp_smoke.py"],
        ["python", "scripts/check_reconcile_health.py"],
    ]
    assert "release_candidate_validation: ok" in out.out
    assert "check=migration_readiness_contract status=pass" in out.out
    assert "check=strict_launch_preflight status=pass" in out.out
    assert "check=telegram_webhook_config_dry_run status=pass" in out.out
    assert "check=canonical_postgres_mvp_smoke status=pass" in out.out
    assert "check=reconcile_health_check status=pass" in out.out
    assert "child-ok" not in out.out
    assert out.err == ""


def test_preflight_failure_stops_and_fails_safely(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    calls: list[list[str]] = []

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        command = list(args[0])
        calls.append(command)
        if command[-1] == "scripts/run_mvp_release_preflight.py":
            return subprocess.CompletedProcess(args[0], 1, stdout="db=postgres://unsafe", stderr="traceback")
        return subprocess.CompletedProcess(args[0], 0, stdout="", stderr="")

    monkeypatch.setattr(script.subprocess, "run", fake_run)
    rc = script.run_release_candidate_validation(env=_safe_env())
    out = capsys.readouterr()

    assert rc == 1
    assert calls == [["python", "scripts/run_mvp_release_preflight.py"]]
    assert "check=migration_readiness_contract status=fail" in out.out
    assert "check=migration_readiness_contract child_exit_code=1" in out.out
    assert "release_candidate_validation: failed" in out.out
    assert "traceback" not in (out.out + out.err).lower()
    assert "postgres://" not in (out.out + out.err).lower()


def test_smoke_failure_stops_and_fails_safely(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    calls: list[list[str]] = []

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        command = list(args[0])
        calls.append(command)
        if command[-1] == "scripts/run_postgres_mvp_smoke.py":
            return subprocess.CompletedProcess(args[0], 2, stdout="token=bad", stderr="stack trace")
        return subprocess.CompletedProcess(args[0], 0, stdout="", stderr="")

    monkeypatch.setattr(script.subprocess, "run", fake_run)
    rc = script.run_release_candidate_validation(env=_safe_env())
    out = capsys.readouterr()

    assert rc == 1
    assert calls == [
        ["python", "scripts/run_mvp_release_preflight.py"],
        ["python", "scripts/check_launch_readiness.py", "--strict"],
        ["python", "scripts/configure_telegram_webhook.py", "--dry-run"],
        ["python", "scripts/run_postgres_mvp_smoke.py"],
    ]
    blob = (out.out + out.err).lower()
    assert "check=canonical_postgres_mvp_smoke status=fail" in blob
    assert "check=canonical_postgres_mvp_smoke child_exit_code=2" in blob
    assert "release_candidate_validation: failed" in blob
    assert "token=" not in blob
    assert "stack trace" not in blob


def test_reconcile_health_failure_fails_safely(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        command = list(args[0])
        if command[-1] == "scripts/check_reconcile_health.py":
            return subprocess.CompletedProcess(args[0], 3, stdout="", stderr="DATABASE_URL=unsafe")
        return subprocess.CompletedProcess(args[0], 0, stdout="", stderr="")

    monkeypatch.setattr(script.subprocess, "run", fake_run)
    rc = script.run_release_candidate_validation(env=_safe_env())
    out = capsys.readouterr()

    assert rc == 1
    blob = (out.out + out.err).lower()
    assert "check=reconcile_health_check status=fail" in blob
    assert "check=reconcile_health_check child_exit_code=3" in blob
    assert "release_candidate_validation: failed" in blob
    assert "database_url=" not in blob


def test_invocation_order_and_env_contract_markers(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    seen_envs: list[dict[str, str]] = []

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen_envs.append(kwargs["env"])
        return subprocess.CompletedProcess(args[0], 0, stdout="", stderr="")

    monkeypatch.setattr(script.subprocess, "run", fake_run)
    rc = script.run_release_candidate_validation(env=_safe_env())
    out = capsys.readouterr()

    assert rc == 0
    assert len(seen_envs) == 5
    for child_env in seen_envs:
        assert child_env["SLICE1_POSTGRES_MVP_SMOKE_ALLOW_MUTATING_TESTS"] == "1"
    assert "required_env=PAYMENT_FULFILLMENT_WEBHOOK_SECRET" in out.out
    assert "required_env=TELEGRAM_CHECKOUT_REFERENCE_SECRET" in out.out
    assert "required_env=ACCESS_RECONCILE_SCHEDULE_ACK=1" in out.out
    assert "required_env=TELEGRAM_WEBHOOK_PUBLIC_URL_IF_WEBHOOK_MODE_ENABLED" in out.out
    assert "required_env=TELEGRAM_WEBHOOK_SECRET_TOKEN_IF_WEBHOOK_MODE_ENABLED" in out.out


def test_stdout_stderr_leak_guard_on_child_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args[0],
            1,
            stdout="telegram payload: {'token': 'abc'}",
            stderr="Traceback: secret=xyz DATABASE_URL=postgresql://unsafe",
        )

    monkeypatch.setattr(script.subprocess, "run", fake_run)
    rc = script.run_release_candidate_validation(env=_safe_env())
    out = capsys.readouterr()

    assert rc == 1
    blob = (out.out + out.err).lower()
    for forbidden in ("traceback", "token=", "database_url=", "postgresql://", "secret="):
        assert forbidden not in blob
