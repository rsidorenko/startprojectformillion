"""Tests for reconcile runtime health check script."""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_reconcile_health.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("check_reconcile_health", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakePool:
    async def close(self) -> None:
        return None


def test_health_check_passes_when_last_success_is_fresh(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("ACCESS_RECONCILE_MAX_INTERVAL_SECONDS", "3600")

    class _FakeRepo:
        def __init__(self, pool: object) -> None:
            assert pool is not None

        async def fetch_latest_access_reconcile_run(self, *, task_name: str):
            assert task_name == "expired_access_reconcile"
            now = datetime.now(UTC)
            return (now - timedelta(seconds=30), now - timedelta(seconds=20), "completed", 2, None, None)

    async def _fake_create_pool(*args: object, **kwargs: object) -> _FakePool:
        return _FakePool()

    monkeypatch.setattr(script.asyncpg, "create_pool", _fake_create_pool)
    monkeypatch.setattr(script, "PostgresIssuanceStateRepository", _FakeRepo)
    rc = script.main([])
    out = capsys.readouterr()
    assert rc == 0
    assert "reconcile_health_check: ok" in out.out
    assert "issue_code=none" in out.out
    assert out.err == ""


def test_health_check_fails_when_heartbeat_missing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("ACCESS_RECONCILE_MAX_INTERVAL_SECONDS", "3600")

    class _FakeRepo:
        def __init__(self, pool: object) -> None:
            assert pool is not None

        async def fetch_latest_access_reconcile_run(self, *, task_name: str):
            return None

    async def _fake_create_pool(*args: object, **kwargs: object) -> _FakePool:
        return _FakePool()

    monkeypatch.setattr(script.asyncpg, "create_pool", _fake_create_pool)
    monkeypatch.setattr(script, "PostgresIssuanceStateRepository", _FakeRepo)
    rc = script.main([])
    out = capsys.readouterr()
    assert rc == 1
    assert "reconcile_health_check: failed" in out.err
    assert "issue_code=access_reconcile_heartbeat_missing" in out.err


def test_health_check_fails_when_last_run_is_stale(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("ACCESS_RECONCILE_MAX_INTERVAL_SECONDS", "300")

    class _FakeRepo:
        def __init__(self, pool: object) -> None:
            assert pool is not None

        async def fetch_latest_access_reconcile_run(self, *, task_name: str):
            now = datetime.now(UTC)
            return (now - timedelta(seconds=3600), now - timedelta(seconds=3500), "completed", 1, None, None)

    async def _fake_create_pool(*args: object, **kwargs: object) -> _FakePool:
        return _FakePool()

    monkeypatch.setattr(script.asyncpg, "create_pool", _fake_create_pool)
    monkeypatch.setattr(script, "PostgresIssuanceStateRepository", _FakeRepo)
    rc = script.main([])
    out = capsys.readouterr()
    assert rc == 1
    assert "issue_code=access_reconcile_heartbeat_stale" in out.err


def test_health_check_fails_when_last_run_failed(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("ACCESS_RECONCILE_MAX_INTERVAL_SECONDS", "300")

    class _FakeRepo:
        def __init__(self, pool: object) -> None:
            assert pool is not None

        async def fetch_latest_access_reconcile_run(self, *, task_name: str):
            now = datetime.now(UTC)
            return (
                now - timedelta(seconds=20),
                now - timedelta(seconds=10),
                "failed",
                0,
                "PersistenceDependencyError",
                "reconcile_run_failed",
            )

    async def _fake_create_pool(*args: object, **kwargs: object) -> _FakePool:
        return _FakePool()

    monkeypatch.setattr(script.asyncpg, "create_pool", _fake_create_pool)
    monkeypatch.setattr(script, "PostgresIssuanceStateRepository", _FakeRepo)
    rc = script.main([])
    out = capsys.readouterr()
    assert rc == 1
    assert "issue_code=access_reconcile_last_run_failed" in out.err
    assert "last_run_error_class=PersistenceDependencyError" in out.err


def test_health_check_output_does_not_leak_sensitive_tokens(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = _load_script_module()
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@localhost:5432/db")
    monkeypatch.setenv("ACCESS_RECONCILE_MAX_INTERVAL_SECONDS", "3600")

    class _FakeRepo:
        def __init__(self, pool: object) -> None:
            assert pool is not None

        async def fetch_latest_access_reconcile_run(self, *, task_name: str):
            now = datetime.now(UTC)
            return (now - timedelta(seconds=10), now - timedelta(seconds=5), "completed", 1, None, None)

    async def _fake_create_pool(*args: object, **kwargs: object) -> _FakePool:
        return _FakePool()

    monkeypatch.setattr(script.asyncpg, "create_pool", _fake_create_pool)
    monkeypatch.setattr(script, "PostgresIssuanceStateRepository", _FakeRepo)
    rc = script.main([])
    out = capsys.readouterr()
    blob = (out.out + out.err).lower()
    assert rc == 0
    for forbidden in ("postgresql://", "token=", "secret@", "database_url"):
        assert forbidden not in blob
