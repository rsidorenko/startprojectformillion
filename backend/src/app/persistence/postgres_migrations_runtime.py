"""Manual async entrypoint: pool from RuntimeConfig, apply slice-1 SQL migrations, close pool."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

import asyncpg

from app.persistence.postgres_migrations import apply_postgres_migrations
from app.security.config import ConfigurationError, RuntimeConfig

RuntimePostgresPoolOpener = Callable[[str], Awaitable[asyncpg.Pool]]


async def _default_open_pool(dsn: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn, min_size=1, max_size=4)


async def apply_slice1_postgres_migrations_from_runtime_config(
    config: RuntimeConfig,
    *,
    open_pool: RuntimePostgresPoolOpener | None = None,
    migrations_directory: Path | None = None,
) -> None:
    dsn = (config.database_url or "").strip()
    if not dsn:
        raise ConfigurationError("missing or empty configuration: DATABASE_URL")

    opener = open_pool or _default_open_pool
    pool = await opener(dsn)
    try:
        await apply_postgres_migrations(pool, migrations_directory=migrations_directory)
    finally:
        await pool.close()
