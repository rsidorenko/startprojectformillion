"""Manual entrypoint: ``python -m app.persistence.slice1_retention_manual_cleanup_main``."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

import asyncpg

from app.persistence.slice1_retention_manual_cleanup import (
    ENV_BATCH,
    ENV_DRY_RUN,
    ENV_MAX_ROUNDS,
    ENV_TTL,
    RetentionSettings,
    run_slice1_retention_cleanup,
    validate_retention_settings,
)
from app.security.config import ConfigurationError, load_runtime_config


def _parse_bool_env(raw: str) -> bool:
    v = raw.strip().lower()
    return v in ("1", "true", "yes")


def _require_positive_int(name: str) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        raise ConfigurationError(f"missing or empty configuration: {name}")
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"invalid configuration: {name}") from exc
    if value <= 0:
        raise ConfigurationError(f"invalid configuration: {name}")
    return value


def load_retention_settings_from_env() -> RetentionSettings:
    ttl = _require_positive_int(ENV_TTL)
    batch = _require_positive_int(ENV_BATCH)
    max_rounds = _require_positive_int(ENV_MAX_ROUNDS)
    dry_raw = os.environ.get(ENV_DRY_RUN, "").strip()
    dry_run = _parse_bool_env(dry_raw) if dry_raw else False
    settings = RetentionSettings(
        ttl_seconds=ttl,
        batch_limit=batch,
        dry_run=dry_run,
        max_rounds=max_rounds,
    )
    validate_retention_settings(settings)
    return settings


async def _default_open_pool(dsn: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn, min_size=1, max_size=4)


async def run_slice1_retention_cleanup_from_env() -> None:
    config = load_runtime_config()
    dsn = (config.database_url or "").strip()
    if not dsn:
        raise ConfigurationError("missing or empty configuration: DATABASE_URL")

    settings = load_retention_settings_from_env()
    pool = await _default_open_pool(dsn)
    try:
        async with pool.acquire() as conn:
            result = await run_slice1_retention_cleanup(
                conn,
                now_utc=datetime.now(UTC),
                settings=settings,
            )
    finally:
        await pool.close()

    print(
        "slice1_retention_cleanup",
        f"dry_run={result.dry_run}",
        f"cutoff={result.cutoff_iso}",
        f"audit_rows={result.audit_rows}",
        f"idempotency_rows={result.idempotency_rows}",
        f"outbound_delivery_rows_matched={result.outbound_delivery_rows_matched}",
        f"outbound_delivery_rows_deleted={result.outbound_delivery_rows_deleted}",
        f"rounds={result.rounds}",
        sep=" ",
    )


def main() -> None:
    asyncio.run(run_slice1_retention_cleanup_from_env())


if __name__ == "__main__":
    main()
