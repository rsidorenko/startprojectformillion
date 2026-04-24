"""Tests for check_admin_support_internal_read_gate script (stdout/stderr hygiene)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_admin_support_internal_read_gate.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location(
        "check_admin_support_internal_read_gate",
        _SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_main_ok_and_no_env_secret_echo(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    raw_url = "postgresql://ci_user:SUPER_SECRET_DB_PASS@127.0.0.1:5432/ci_db"
    monkeypatch.setenv("DATABASE_URL", raw_url)
    monkeypatch.setenv("BOT_TOKEN", "bot-secret-token-not-for-logs")

    rc = script.main([])

    assert rc == 0
    out = capsys.readouterr()
    assert out.out.strip() == "admin_support_internal_read_gate: ok"
    assert out.err == ""
    assert "SUPER_SECRET_DB_PASS" not in out.out
    assert "SUPER_SECRET_DB_PASS" not in out.err
    assert "DATABASE_URL" not in out.out
    assert "DATABASE_URL" not in out.err
    assert "bot-secret-token-not-for-logs" not in out.out
    assert "bot-secret-token-not-for-logs" not in out.err
    assert "postgresql://" not in out.out
    assert "postgresql://" not in out.err


def test_script_main_runtime_error_emits_fail_only(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()

    async def _raise_runtime() -> None:
        raise RuntimeError("internal detail must not reach stderr")

    monkeypatch.setattr(script, "run_admin_support_internal_read_gate_checks", _raise_runtime)

    rc = script.main([])

    assert rc == 1
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err.strip() == "admin_support_internal_read_gate: fail"
    assert "internal detail" not in out.err
    assert "Traceback" not in out.err


def test_script_main_unexpected_exception_hides_message_and_traceback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    secret = "LEAKED_SYNTHETIC_SECRET_7xq"
    dsn = f"postgresql://u:{secret}@127.0.0.1:9/db"

    async def _raise_value() -> None:
        raise ValueError(f"boom {dsn}")

    monkeypatch.setattr(script, "run_admin_support_internal_read_gate_checks", _raise_value)

    rc = script.main([])

    assert rc == 1
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err.strip() == "admin_support_internal_read_gate: failed"
    assert secret not in out.err
    assert secret not in out.out
    assert "postgresql://" not in out.err
    assert "postgresql://" not in out.out
    assert "Traceback" not in out.err
    assert "ValueError" not in out.err
