"""Unit tests for RuntimeConfig-driven postgres migration apply (no real database)."""

from __future__ import annotations

import asyncio
import inspect
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from app.persistence import postgres_migrations_runtime as pmr
from app.security.config import ConfigurationError, RuntimeConfig


def _cfg() -> RuntimeConfig:
    return RuntimeConfig(
        bot_token="1234567890tok",
        database_url="postgresql://localhost/testdb",
        app_env="development",
        debug_safe=False,
    )


def test_apply_slice1_postgres_migrations_raises_without_database_url_and_does_not_open() -> None:
    open_calls: list[str] = []

    async def fake_open(dsn: str) -> object:
        open_calls.append(dsn)
        raise AssertionError("opener should not run without DATABASE_URL")

    cfg = RuntimeConfig(
        bot_token="1234567890tok",
        database_url=None,
        app_env="development",
        debug_safe=False,
    )

    async def main() -> None:
        with pytest.raises(ConfigurationError, match="DATABASE_URL"):
            await pmr.apply_slice1_postgres_migrations_from_runtime_config(cfg, open_pool=fake_open)

    asyncio.run(main())
    assert open_calls == []


def test_apply_slice1_postgres_migrations_opens_applies_closes() -> None:
    dsn_seen: list[str] = []
    apply_calls: list[tuple[object, Path | None]] = []
    close_calls = 0

    class FakePool:
        async def close(self) -> None:
            nonlocal close_calls
            close_calls += 1

    async def fake_open(dsn: str) -> FakePool:
        dsn_seen.append(dsn)
        return FakePool()

    async def fake_apply(executor: object, *, migrations_directory: Path | None = None) -> None:
        apply_calls.append((executor, migrations_directory))

    cfg = _cfg()

    async def main() -> None:
        with patch.object(pmr, "apply_postgres_migrations", side_effect=fake_apply):
            await pmr.apply_slice1_postgres_migrations_from_runtime_config(cfg, open_pool=fake_open)

    asyncio.run(main())

    assert dsn_seen == [cfg.database_url]
    assert len(apply_calls) == 1
    assert isinstance(apply_calls[0][0], FakePool)
    assert apply_calls[0][1] is None
    assert close_calls == 1


def test_apply_slice1_postgres_migrations_closes_when_apply_raises() -> None:
    close_calls = 0

    class FakePool:
        async def close(self) -> None:
            nonlocal close_calls
            close_calls += 1

    async def fake_open(_dsn: str) -> FakePool:
        return FakePool()

    async def fake_apply(_executor: object, *, migrations_directory: Path | None = None) -> None:
        raise ValueError("apply failed")

    cfg = _cfg()

    async def main() -> None:
        with patch.object(pmr, "apply_postgres_migrations", side_effect=fake_apply):
            with pytest.raises(ValueError, match="apply failed"):
                await pmr.apply_slice1_postgres_migrations_from_runtime_config(cfg, open_pool=fake_open)

    asyncio.run(main())
    assert close_calls == 1


def test_apply_slice1_postgres_migrations_passes_migrations_directory(tmp_path: Path) -> None:
    captured: list[Path | None] = []

    class FakePool:
        async def close(self) -> None:
            return None

    async def fake_open(_dsn: str) -> FakePool:
        return FakePool()

    async def fake_apply(_executor: object, *, migrations_directory: Path | None = None) -> None:
        captured.append(migrations_directory)

    cfg = _cfg()

    async def main() -> None:
        with patch.object(pmr, "apply_postgres_migrations", side_effect=fake_apply):
            await pmr.apply_slice1_postgres_migrations_from_runtime_config(
                cfg,
                open_pool=fake_open,
                migrations_directory=tmp_path,
            )

    asyncio.run(main())
    assert captured == [tmp_path]


def test_postgres_migrations_runtime_avoids_env() -> None:
    source = textwrap.dedent(inspect.getsource(pmr))
    lowered = source.lower()
    assert "os.environ" not in lowered
    assert "getenv" not in lowered
