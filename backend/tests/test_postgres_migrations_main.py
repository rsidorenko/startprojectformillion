"""Unit tests for manual postgres migration entrypoint delegation."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.persistence import postgres_migrations_main as pmm


@pytest.mark.asyncio
async def test_run_slice1_postgres_migrations_from_env_delegates_with_same_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = object()
    apply_mock = AsyncMock()

    monkeypatch.setattr(pmm, "load_runtime_config", lambda: config)
    monkeypatch.setattr(
        pmm,
        "apply_slice1_postgres_migrations_from_runtime_config",
        apply_mock,
    )

    await pmm.run_slice1_postgres_migrations_from_env()

    apply_mock.assert_awaited_once_with(config)


def test_main_delegates_to_asyncio_run(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[object] = []

    def fake_run(awaitable: object) -> None:
        seen.append(awaitable)

    monkeypatch.setattr(pmm.asyncio, "run", fake_run)

    pmm.main()

    assert len(seen) == 1
    seen[0].close()


@pytest.mark.asyncio
async def test_run_slice1_postgres_migrations_from_env_reraises_apply_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = object()

    async def raise_apply(_config: object) -> None:
        raise RuntimeError("migration failed")

    monkeypatch.setattr(pmm, "load_runtime_config", lambda: config)
    monkeypatch.setattr(
        pmm,
        "apply_slice1_postgres_migrations_from_runtime_config",
        raise_apply,
    )

    with pytest.raises(RuntimeError, match="migration failed"):
        await pmm.run_slice1_postgres_migrations_from_env()
