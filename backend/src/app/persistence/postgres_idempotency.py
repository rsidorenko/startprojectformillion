"""PostgreSQL adapter for IdempotencyRepository (asyncpg pool injected by composition/tests)."""

from __future__ import annotations

import asyncpg

from app.application.interfaces import IdempotencyRecord
from app.security.errors import InternalErrorCategory, PersistenceDependencyError


class PostgresIdempotencyRepository:
    """Key → completed flag; begin_or_get is concurrency-safe at the row level."""

    _BEGIN_OR_GET = """
        WITH ins AS (
            INSERT INTO idempotency_records (idempotency_key, completed)
            VALUES ($1::text, false)
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING idempotency_key, completed
        )
        SELECT idempotency_key, completed FROM ins
        UNION ALL
        SELECT r.idempotency_key, r.completed
        FROM idempotency_records r
        WHERE r.idempotency_key = $1::text
        LIMIT 1
    """

    _COMPLETE = """
        INSERT INTO idempotency_records (idempotency_key, completed)
        VALUES ($1::text, true)
        ON CONFLICT (idempotency_key) DO UPDATE SET completed = true
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get(self, key: str) -> IdempotencyRecord | None:
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT idempotency_key, completed
                    FROM idempotency_records
                    WHERE idempotency_key = $1::text
                    """,
                    key,
                )
        except (asyncpg.PostgresError, OSError) as exc:
            raise PersistenceDependencyError(InternalErrorCategory.PERSISTENCE_TRANSIENT) from exc
        if row is None:
            return None
        return IdempotencyRecord(key=row["idempotency_key"], completed=bool(row["completed"]))

    async def begin_or_get(self, key: str) -> IdempotencyRecord:
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(self._BEGIN_OR_GET, key)
        except (asyncpg.PostgresError, OSError) as exc:
            raise PersistenceDependencyError(InternalErrorCategory.PERSISTENCE_TRANSIENT) from exc
        if row is None:
            raise PersistenceDependencyError(InternalErrorCategory.PERSISTENCE_INVARIANT)
        return IdempotencyRecord(key=row["idempotency_key"], completed=bool(row["completed"]))

    async def complete(self, key: str) -> None:
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(self._COMPLETE, key)
        except (asyncpg.PostgresError, OSError) as exc:
            raise PersistenceDependencyError(InternalErrorCategory.PERSISTENCE_TRANSIENT) from exc
