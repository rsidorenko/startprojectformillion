"""PostgreSQL adapter for subscription snapshot read + insert-if-missing (asyncpg pool)."""

from __future__ import annotations

import asyncpg

from app.application.interfaces import SubscriptionSnapshot
from app.security.errors import InternalErrorCategory, PersistenceDependencyError


class PostgresSubscriptionSnapshotReader:
    """One row per internal user; read returns ``None`` when missing; ``put_if_absent`` is no-op on conflict."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_for_user(self, internal_user_id: str) -> SubscriptionSnapshot | None:
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT internal_user_id, state_label
                    FROM subscription_snapshots
                    WHERE internal_user_id = $1::text
                    """,
                    internal_user_id,
                )
        except (asyncpg.PostgresError, OSError) as exc:
            raise PersistenceDependencyError(InternalErrorCategory.PERSISTENCE_TRANSIENT) from exc
        if row is None:
            return None
        return SubscriptionSnapshot(
            internal_user_id=row["internal_user_id"],
            state_label=row["state_label"],
        )

    async def put_if_absent(self, snapshot: SubscriptionSnapshot) -> None:
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO subscription_snapshots (internal_user_id, state_label)
                    VALUES ($1::text, $2::text)
                    ON CONFLICT (internal_user_id) DO NOTHING
                    """,
                    snapshot.internal_user_id,
                    snapshot.state_label,
                )
        except (asyncpg.PostgresError, OSError) as exc:
            raise PersistenceDependencyError(InternalErrorCategory.PERSISTENCE_TRANSIENT) from exc
