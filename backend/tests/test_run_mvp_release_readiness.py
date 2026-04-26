"""Unit tests for MVP release readiness orchestrator script."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_mvp_release_readiness.py"


def _load_script_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("run_mvp_release_readiness", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_order_runs_repo_health_check_then_checklist_then_preflight_without_config_doctor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _load_script_module()
    recorded: list[list[str]] = []

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        recorded.append(list(args[0]))
        return subprocess.CompletedProcess(args[0], 0)

    monkeypatch.setattr(script.subprocess, "run", fake_run)
    exit_code = script.main([])

    assert exit_code == 0
    assert recorded == [
        ["python", "scripts/run_mvp_repo_release_health_check.py"],
        ["python", "scripts/run_mvp_release_checklist.py"],
        ["python", "scripts/run_mvp_release_preflight.py"],
    ]


def test_with_config_profile_webhook_runs_doctor_after_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _load_script_module()
    recorded: list[list[str]] = []

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        recorded.append(list(args[0]))
        return subprocess.CompletedProcess(args[0], 0)

    monkeypatch.setattr(script.subprocess, "run", fake_run)
    exit_code = script.main(["--config-profile", "webhook"])

    assert exit_code == 0
    assert recorded == [
        ["python", "scripts/run_mvp_repo_release_health_check.py"],
        ["python", "scripts/run_mvp_release_checklist.py"],
        ["python", "scripts/run_mvp_release_preflight.py"],
        ["python", "scripts/run_mvp_config_doctor.py", "--profile", "webhook"],
    ]


def test_skip_preflight_runs_checklist_and_optional_config_doctor_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _load_script_module()
    recorded: list[list[str]] = []

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        recorded.append(list(args[0]))
        return subprocess.CompletedProcess(args[0], 0)

    monkeypatch.setattr(script.subprocess, "run", fake_run)
    exit_code = script.main(["--skip-preflight", "--config-profile", "polling"])

    assert exit_code == 0
    assert recorded == [
        ["python", "scripts/run_mvp_repo_release_health_check.py"],
        ["python", "scripts/run_mvp_release_checklist.py"],
        ["python", "scripts/run_mvp_config_doctor.py", "--profile", "polling"],
    ]


def test_repo_health_check_failure_stops_following_stages(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    recorded: list[list[str]] = []

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        recorded.append(list(args[0]))
        raise subprocess.CalledProcessError(returncode=3, cmd=args[0])

    monkeypatch.setattr(script.subprocess, "run", fake_run)
    exit_code = script.main(["--config-profile", "webhook"])

    out = capsys.readouterr().out
    assert exit_code == 3
    assert "mvp_release_readiness: fail" in out
    assert "stage=repo_release_health_check" in out
    assert recorded == [["python", "scripts/run_mvp_repo_release_health_check.py"]]


def test_checklist_failure_stops_preflight_and_config_doctor(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    recorded: list[list[str]] = []

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        command = list(args[0])
        recorded.append(command)
        if command[-1] == "scripts/run_mvp_release_checklist.py":
            raise subprocess.CalledProcessError(returncode=5, cmd=args[0])
        return subprocess.CompletedProcess(args[0], 0)

    monkeypatch.setattr(script.subprocess, "run", fake_run)
    exit_code = script.main(["--config-profile", "webhook"])

    out = capsys.readouterr().out
    assert exit_code == 5
    assert "mvp_release_readiness: fail" in out
    assert "stage=checklist" in out
    assert recorded == [
        ["python", "scripts/run_mvp_repo_release_health_check.py"],
        ["python", "scripts/run_mvp_release_checklist.py"],
    ]


def test_preflight_failure_stops_config_doctor(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    recorded: list[list[str]] = []

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        command = list(args[0])
        recorded.append(command)
        if command[-1] == "scripts/run_mvp_release_preflight.py":
            raise subprocess.CalledProcessError(returncode=7, cmd=args[0])
        return subprocess.CompletedProcess(args[0], 0)

    monkeypatch.setattr(script.subprocess, "run", fake_run)
    exit_code = script.main(["--config-profile", "retention"])

    out = capsys.readouterr().out
    assert exit_code == 7
    assert "mvp_release_readiness: fail" in out
    assert "stage=preflight" in out
    assert recorded == [
        ["python", "scripts/run_mvp_repo_release_health_check.py"],
        ["python", "scripts/run_mvp_release_checklist.py"],
        ["python", "scripts/run_mvp_release_preflight.py"],
    ]


def test_unknown_config_profile_fails_before_subprocess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = _load_script_module()
    recorded: list[list[str]] = []

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        recorded.append(list(args[0]))
        return subprocess.CompletedProcess(args[0], 0)

    monkeypatch.setattr(script.subprocess, "run", fake_run)
    with pytest.raises(SystemExit):
        _ = script.main(["--config-profile", "unknown"])
    assert recorded == []


def test_script_never_invokes_local_smoke_or_docker(monkeypatch: pytest.MonkeyPatch) -> None:
    script = _load_script_module()
    recorded: list[list[str]] = []

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        command = list(args[0])
        recorded.append(command)
        return subprocess.CompletedProcess(args[0], 0)

    monkeypatch.setattr(script.subprocess, "run", fake_run)
    _ = script.main(["--config-profile", "internal-admin"])

    flattened = " ".join(" ".join(cmd) for cmd in recorded).lower()
    assert "run_postgres_mvp_smoke_local.py" not in flattened
    assert "docker" not in flattened


def test_output_has_no_forbidden_fragments(capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script_module()
    _ = script.main([])

    captured = capsys.readouterr()
    output_blob = (captured.out + captured.err).lower()
    for fragment in (
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
        assert fragment not in output_blob
