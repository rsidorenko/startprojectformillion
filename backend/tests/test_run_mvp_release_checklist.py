"""Unit tests for static MVP release checklist script."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_mvp_release_checklist.py"


def _load_script_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("run_mvp_release_checklist", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_required_tree(base_dir: Path) -> None:
    (base_dir / "scripts").mkdir(parents=True, exist_ok=True)
    (base_dir / "docs").mkdir(parents=True, exist_ok=True)
    (base_dir / "scripts" / "run_mvp_release_preflight.py").write_text("pass\n", encoding="utf-8")
    (base_dir / "scripts" / "run_mvp_config_doctor.py").write_text("pass\n", encoding="utf-8")
    (base_dir / "scripts" / "run_postgres_mvp_smoke_local.py").write_text("pass\n", encoding="utf-8")
    (base_dir / "docs" / "mvp_release_readiness_runbook.md").write_text(
        "\n".join(
            (
                "mvp_release_preflight: ok",
                "mvp_config_doctor: ok",
                "/healthz",
                "/readyz",
                "ADM-01",
                "ADM-02",
                "dry-run",
                "OPERATIONAL_RETENTION_DELETE_ENABLE",
                "public billing ingress",
                "provider SDK",
                "real credential/config delivery",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    (base_dir / "docs" / "telegram_access_resend_runbook.md").write_text(
        "TELEGRAM_WEBHOOK_SECRET_TOKEN\nTELEGRAM_WEBHOOK_ALLOW_INSECURE_LOCAL\n",
        encoding="utf-8",
    )
    (base_dir / "docs" / "admin_support_internal_read_gate_runbook.md").write_text(
        "ADM02_ENSURE_ACCESS_ENABLE\naudit\nreadback\n",
        encoding="utf-8",
    )
    (base_dir / "docs" / "postgres_mvp_smoke_runbook.md").write_text(
        "python scripts/run_mvp_release_preflight.py\n"
        "python scripts/run_postgres_mvp_smoke_local.py\n"
        "no real Docker smoke\n",
        encoding="utf-8",
    )


def test_success_path_with_temp_fixture(tmp_path: Path) -> None:
    script = _load_script_module()
    _write_required_tree(tmp_path)

    ok, issues = script.run_release_checklist(base_dir=tmp_path)

    assert ok is True
    assert issues == ()


def test_missing_script_or_doc_produces_safe_failure_issue_code(tmp_path: Path) -> None:
    script = _load_script_module()
    _write_required_tree(tmp_path)
    (tmp_path / "scripts" / "run_mvp_config_doctor.py").unlink()

    ok, issues = script.run_release_checklist(base_dir=tmp_path)

    assert ok is False
    assert "missing_config_doctor_script" in issues


def test_missing_marker_produces_safe_failure_issue_code(tmp_path: Path) -> None:
    script = _load_script_module()
    _write_required_tree(tmp_path)
    (tmp_path / "docs" / "mvp_release_readiness_runbook.md").write_text(
        "mvp_release_preflight: ok\n",
        encoding="utf-8",
    )

    ok, issues = script.run_release_checklist(base_dir=tmp_path)

    assert ok is False
    assert "missing_release_runbook_marker" in issues


def test_script_does_not_execute_referenced_scripts(monkeypatch: pytest.MonkeyPatch) -> None:
    script = _load_script_module()
    calls: list[str] = []

    def _should_not_run(*args: object, **kwargs: object) -> None:
        calls.append("called")
        raise AssertionError("subprocess/network should not be used")

    monkeypatch.setattr("subprocess.run", _should_not_run)
    monkeypatch.setattr("socket.create_connection", _should_not_run)

    _ = script.run_release_checklist(base_dir=Path(__file__).resolve().parents[1])
    assert calls == []


def test_output_has_no_forbidden_fragments(capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script_module()
    _ = script.main()

    blob = (capsys.readouterr().out + capsys.readouterr().err).lower()
    for forbidden in (
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
        assert forbidden not in blob
