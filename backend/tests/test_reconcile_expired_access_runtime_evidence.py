"""Runtime evidence tests for reconcile heartbeat behavior."""

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


class _FakePool:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def test_run_records_started_and_completed_heartbeat(monkeypatch: pytest.MonkeyPatch) -> None:
    script = _load_script_module()
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    events: list[str] = []
    fake_pool = _FakePool()

    class _FakeRepo:
        def __init__(self, pool: object) -> None:
            assert pool is fake_pool

        async def record_access_reconcile_started(self, **kwargs: object) -> None:
            assert kwargs["task_name"] == "expired_access_reconcile"
            events.append("started")

        async def reconcile_expired_active_subscriptions(self, *, now_utc: object) -> int:
            assert now_utc is not None
            events.append("reconcile")
            return 4

        async def record_access_reconcile_completed(self, **kwargs: object) -> None:
            assert kwargs["task_name"] == "expired_access_reconcile"
            assert kwargs["reconciled_rows"] == 4
            events.append("completed")

    async def _fake_create_pool(*args: object, **kwargs: object) -> _FakePool:
        return fake_pool

    monkeypatch.setattr(script.asyncpg, "create_pool", _fake_create_pool)
    monkeypatch.setattr(script, "PostgresIssuanceStateRepository", _FakeRepo)

    reconciled_rows, heartbeat_recorded = script.asyncio.run(script.run_reconcile_expired_access())
    assert reconciled_rows == 4
    assert heartbeat_recorded is True
    assert events == ["started", "reconcile", "completed"]
    assert fake_pool.closed is True


def test_run_records_failed_heartbeat_when_reconcile_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    script = _load_script_module()
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    events: list[str] = []
    fake_pool = _FakePool()

    class _FakeRepo:
        def __init__(self, pool: object) -> None:
            assert pool is fake_pool

        async def record_access_reconcile_started(self, **kwargs: object) -> None:
            events.append("started")

        async def reconcile_expired_active_subscriptions(self, *, now_utc: object) -> int:
            events.append("reconcile")
            raise RuntimeError("secret-token-value")

        async def record_access_reconcile_failed(self, **kwargs: object) -> None:
            assert kwargs["task_name"] == "expired_access_reconcile"
            assert kwargs["safe_error_message"] == "reconcile_run_failed"
            events.append("failed")

    async def _fake_create_pool(*args: object, **kwargs: object) -> _FakePool:
        return fake_pool

    monkeypatch.setattr(script.asyncpg, "create_pool", _fake_create_pool)
    monkeypatch.setattr(script, "PostgresIssuanceStateRepository", _FakeRepo)

    with pytest.raises(script.ReconcileRunFailed) as exc_info:
        script.asyncio.run(script.run_reconcile_expired_access())
    assert exc_info.value.heartbeat_recorded is True
    assert events == ["started", "reconcile", "failed"]
    assert fake_pool.closed is True


def test_run_failure_heartbeat_is_best_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    script = _load_script_module()
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    fake_pool = _FakePool()

    class _FakeRepo:
        def __init__(self, pool: object) -> None:
            assert pool is fake_pool

        async def record_access_reconcile_started(self, **kwargs: object) -> None:
            return None

        async def reconcile_expired_active_subscriptions(self, *, now_utc: object) -> int:
            raise RuntimeError("db write failed")

        async def record_access_reconcile_failed(self, **kwargs: object) -> None:
            raise RuntimeError("secondary failure")

    async def _fake_create_pool(*args: object, **kwargs: object) -> _FakePool:
        return fake_pool

    monkeypatch.setattr(script.asyncpg, "create_pool", _fake_create_pool)
    monkeypatch.setattr(script, "PostgresIssuanceStateRepository", _FakeRepo)

    with pytest.raises(script.ReconcileRunFailed) as exc_info:
        script.asyncio.run(script.run_reconcile_expired_access())
    assert exc_info.value.heartbeat_recorded is False
    assert fake_pool.closed is True
