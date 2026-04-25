"""Tests for check_adm01_postgres_issuance_composition script (stdout/stderr hygiene)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_adm01_postgres_issuance_composition.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location(
        "check_adm01_postgres_issuance_composition",
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
    monkeypatch.setenv("ADM01_POSTGRES_ISSUANCE_COMPOSITION_CHECK_ENABLE", "1")

    async def _ok() -> None:
        return None

    monkeypatch.setattr(script, "run_adm01_postgres_issuance_composition_check", _ok)

    rc = script.main([])

    assert rc == 0
    out = capsys.readouterr()
    assert out.out.strip() == "adm01_postgres_issuance_composition: ok"
    assert out.err == ""
    assert "SUPER_SECRET_DB_PASS" not in out.out
    assert "SUPER_SECRET_DB_PASS" not in out.err
    assert "DATABASE_URL" not in out.out
    assert "DATABASE_URL" not in out.err
    assert "postgresql://" not in out.out
    assert "postgresql://" not in out.err


def test_script_main_opt_in_missing_emits_fail_and_no_dsn(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Without opt-in, check fails before using DATABASE_URL; output must not echo configuration names."""
    script = _load_script_module()

    rc = script.main([])

    assert rc == 1
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err.strip() == "adm01_postgres_issuance_composition: fail"
    assert "Traceback" not in out.err
    assert "DATABASE_URL" not in out.err
    assert "opt-in" not in out.err


def test_script_main_runtime_error_emits_fail_only(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    monkeypatch.setenv("ADM01_POSTGRES_ISSUANCE_COMPOSITION_CHECK_ENABLE", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:y@127.0.0.1:1/db")

    async def _raise_runtime() -> None:
        raise RuntimeError("internal detail must not reach stderr")

    monkeypatch.setattr(script, "run_adm01_postgres_issuance_composition_check", _raise_runtime)

    rc = script.main([])

    assert rc == 1
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err.strip() == "adm01_postgres_issuance_composition: fail"
    assert "internal detail" not in out.err
    assert "Traceback" not in out.err
    assert "127.0.0.1" not in out.err
    assert "postgresql://" not in out.err


def test_script_main_unexpected_exception_hides_message_and_traceback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    monkeypatch.setenv("ADM01_POSTGRES_ISSUANCE_COMPOSITION_CHECK_ENABLE", "1")
    secret = "LEAKED_SYNTHETIC_SECRET_7xq"
    dsn = f"postgresql://u:{secret}@127.0.0.1:9/db"
    monkeypatch.setenv("DATABASE_URL", dsn)

    async def _raise_value() -> None:
        raise ValueError(f"boom {dsn}")

    monkeypatch.setattr(script, "run_adm01_postgres_issuance_composition_check", _raise_value)

    rc = script.main([])

    assert rc == 1
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err.strip() == "adm01_postgres_issuance_composition: failed"
    assert secret not in out.err
    assert secret not in out.out
    assert "postgresql://" not in out.err
    assert "postgresql://" not in out.out
    assert "Traceback" not in out.err
    assert "ValueError" not in out.err
