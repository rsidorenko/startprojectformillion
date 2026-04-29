"""Contract tests for expired access reconcile script output guards."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "reconcile_expired_access.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("reconcile_expired_access", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_success_main_outputs_safe_markers(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script_module()

    async def ok_run() -> tuple[int, bool]:
        return 2, True

    monkeypatch.setattr(script, "run_reconcile_expired_access", ok_run)
    rc = script.main([])
    out = capsys.readouterr()
    assert rc == 0
    assert out.out.strip().splitlines() == [
        "expired_access_reconcile: ok",
        "reconciled_rows=2",
        "heartbeat_recorded=yes",
    ]
    assert out.err == ""


def test_runtime_error_maps_to_failed_line_with_heartbeat_marker_without_leak(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    script = _load_script_module()

    async def fail_run() -> tuple[int, bool]:
        raise script.ReconcileRunFailed(heartbeat_recorded=True)

    monkeypatch.setattr(script, "run_reconcile_expired_access", fail_run)
    rc = script.main([])
    out = capsys.readouterr()
    assert rc == 1
    assert out.out == ""
    assert out.err.strip().splitlines() == [
        "expired_access_reconcile: failed",
        "heartbeat_recorded=yes",
    ]
    assert "postgresql://" not in out.err.lower()


def test_unexpected_error_maps_to_failed_line_without_leak(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    script = _load_script_module()

    async def boom_run() -> int:
        raise ValueError("provider_issuance_ref leaked")

    monkeypatch.setattr(script, "run_reconcile_expired_access", boom_run)
    rc = script.main([])
    out = capsys.readouterr()
    assert rc == 1
    assert out.out == ""
    assert out.err.strip().splitlines() == [
        "expired_access_reconcile: failed",
        "heartbeat_recorded=no",
    ]
    assert "provider_issuance_ref" not in out.err.lower()
