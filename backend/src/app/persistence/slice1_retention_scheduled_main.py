"""Scheduled entrypoint: ``python -m app.persistence.slice1_retention_scheduled_main``."""

from __future__ import annotations

import asyncio
import os
from dataclasses import replace
from datetime import UTC, datetime

from app.persistence.slice1_retention_manual_cleanup import RetentionSettings, run_slice1_retention_cleanup
from app.persistence.slice1_retention_manual_cleanup_main import _default_open_pool, load_retention_settings_from_env
from app.security.config import ConfigurationError, load_runtime_config

# Explicit scheduled-only opt-in: without this truthy, destructive retention from env is never applied.
SLICE1_RETENTION_SCHEDULED_ENABLE_DELETE = "SLICE1_RETENTION_SCHEDULED_ENABLE_DELETE"


def _scheduled_destructive_opted_in() -> bool:
    raw = os.environ.get(SLICE1_RETENTION_SCHEDULED_ENABLE_DELETE, "").strip()
    if not raw:
        return False
    return raw.lower() in ("1", "true", "yes")


def _effective_settings(loaded: RetentionSettings) -> RetentionSettings:
    if not _scheduled_destructive_opted_in():
        return replace(loaded, dry_run=True)
    return loaded


async def run_slice1_retention_scheduled_from_env() -> None:
    config = load_runtime_config()
    dsn = (config.database_url or "").strip()
    if not dsn:
        raise ConfigurationError("missing or empty configuration: DATABASE_URL")

    settings = load_retention_settings_from_env()
    effective = _effective_settings(settings)
    pool = await _default_open_pool(dsn)
    try:
        async with pool.acquire() as conn:
            result = await run_slice1_retention_cleanup(
                conn,
                now_utc=datetime.now(UTC),
                settings=effective,
            )
    finally:
        await pool.close()

    print(
        "slice1_retention_scheduled_cleanup",
        f"dry_run={result.dry_run}",
        f"cutoff={result.cutoff_iso}",
        f"audit_rows={result.audit_rows}",
        f"idempotency_rows={result.idempotency_rows}",
        f"rounds={result.rounds}",
        sep=" ",
    )


def main() -> None:
    asyncio.run(run_slice1_retention_scheduled_from_env())


if __name__ == "__main__":
    main()
