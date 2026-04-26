"""Unit tests for MVP release preflight runner script."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_mvp_release_preflight.py"


def _load_script_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("run_mvp_release_preflight", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_groups_called_in_expected_order_and_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    script = _load_script_module()
    recorded: list[list[str]] = []

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        recorded.append(list(args[0]))
        return subprocess.CompletedProcess(args[0], 0)

    monkeypatch.setattr(script.subprocess, "run", fake_run)

    exit_code = script.run_preflight()

    assert exit_code == 0
    assert len(recorded) == 4
    for command in recorded:
        assert command[:4] == ["python", "-m", "pytest", "-q"]
    assert "tests/test_run_postgres_mvp_smoke.py" in recorded[0]
    assert "tests/test_postgres_mvp_smoke_ci_evidence_contract.py" in recorded[0]
    assert "tests/test_telegram_webhook_ingress.py" in recorded[1]
    assert "tests/test_telegram_command_rate_limit.py" in recorded[1]
    assert "tests/test_adm01_internal_http_main.py" in recorded[2]
    assert "tests/test_adm02_ensure_access_postgres_audit_sink.py" in recorded[2]
    assert "tests/test_run_slice1_retention_dry_run.py" in recorded[3]
    assert "tests/test_postgres_migrations.py" in recorded[3]


def test_failure_in_any_group_returns_non_zero_and_prints_fail(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    calls: list[list[str]] = []

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(list(args[0]))
        return_code = 1 if len(calls) == 2 else 0
        return subprocess.CompletedProcess(args[0], return_code)

    monkeypatch.setattr(script.subprocess, "run", fake_run)

    exit_code = script.main()

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "mvp_release_preflight: fail" in out
    assert len(calls) == 2


def test_success_prints_ok(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script_module()

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args[0], 0)

    monkeypatch.setattr(script.subprocess, "run", fake_run)

    exit_code = script.main()

    out = capsys.readouterr().out
    assert exit_code == 0
    assert out.strip() == "mvp_release_preflight: ok"


def test_wrapper_output_has_no_forbidden_fragments(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args[0], 0)

    monkeypatch.setattr(script.subprocess, "run", fake_run)
    _ = script.main()

    captured = capsys.readouterr()
    output_blob = (captured.out + captured.err).lower()
    for fragment in (
        "database_url",
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
    ):
        assert fragment not in output_blob
