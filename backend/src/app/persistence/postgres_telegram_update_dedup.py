"""PostgreSQL-backed Telegram update dedup guard."""

from __future__ import annotations

import asyncpg

from app.application.telegram_update_dedup import (
    TELEGRAM_UPDATE_DEDUP_TTL_SECONDS_DEFAULT,
    TelegramUpdateDedupCommandBucket,
    dedup_key_hash_for_update,
)
from app.security.errors import InternalErrorCategory, PersistenceDependencyError


class PostgresTelegramUpdateDedupGuard:
    """
    Shared/durable dedup keyed by hashed (command bucket, update id).

    Rows are bounded by ``expires_at``; an expired key is treated as first-seen again.
    """

    _UPSERT_FIRST_SEEN = """
        WITH upsert AS (
            INSERT INTO telegram_update_dedup (
                dedup_key_hash,
                command_bucket,
                first_seen_at,
                expires_at,
                source_marker
            )
            VALUES (
                $1::text,
                $2::text,
                now(),
                now() + ($3::double precision * interval '1 second'),
                'telegram_transport'
            )
            ON CONFLICT (dedup_key_hash) DO UPDATE
            SET
                command_bucket = EXCLUDED.command_bucket,
                first_seen_at = EXCLUDED.first_seen_at,
                expires_at = EXCLUDED.expires_at
            WHERE telegram_update_dedup.expires_at <= now()
            RETURNING dedup_key_hash
        )
        SELECT EXISTS(SELECT 1 FROM upsert) AS first_seen
    """

    def __init__(
        self,
        pool: asyncpg.Pool,
        *,
        ttl_seconds: float = TELEGRAM_UPDATE_DEDUP_TTL_SECONDS_DEFAULT,
    ) -> None:
        self._pool = pool
        self._ttl_seconds = float(ttl_seconds)

    async def mark_if_first_seen(
        self,
        *,
        command_bucket: TelegramUpdateDedupCommandBucket,
        telegram_update_id: int,
    ) -> bool:
        key_hash = dedup_key_hash_for_update(
            command_bucket=command_bucket,
            telegram_update_id=telegram_update_id,
        )
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    self._UPSERT_FIRST_SEEN,
                    key_hash,
                    command_bucket,
                    self._ttl_seconds,
                )
        except (asyncpg.PostgresError, OSError) as exc:
            raise PersistenceDependencyError(InternalErrorCategory.PERSISTENCE_TRANSIENT) from exc
        if row is None:
            raise PersistenceDependencyError(InternalErrorCategory.PERSISTENCE_INVARIANT)
        return bool(row["first_seen"])
