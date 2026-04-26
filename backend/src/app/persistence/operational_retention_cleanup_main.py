"""Entry-point for operational retention cleanup (dry-run default, delete opt-in)."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

from app.persistence.operational_retention_cleanup import (
    ENV_ADM02_AUDIT_RETENTION_DAYS,
    ENV_OPERATIONAL_RETENTION_DELETE_ENABLE,
    OperationalRetentionSettings,
    run_operational_retention_cleanup,
)
from app.persistence.slice1_retention_manual_cleanup_main import _default_open_pool
from app.security.config import ConfigurationError, load_runtime_config

_TRUTHY_VALUES = ("1", "true", "yes")
_DEFAULT_ADM02_AUDIT_RETENTION_DAYS = 365


def _parse_truthy(raw: str | None) -> bool:
    if raw is None:
        return False
    return raw.strip().lower() in _TRUTHY_VALUES


def _load_adm02_retention_days() -> int:
    raw = os.environ.get(ENV_ADM02_AUDIT_RETENTION_DAYS, "").strip()
    if not raw:
        return _DEFAULT_ADM02_AUDIT_RETENTION_DAYS
    try:
        days = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"invalid configuration: {ENV_ADM02_AUDIT_RETENTION_DAYS}") from exc
    if days <= 0:
        raise ConfigurationError(f"invalid configuration: {ENV_ADM02_AUDIT_RETENTION_DAYS}")
    return days


def load_operational_retention_settings_from_env() -> OperationalRetentionSettings:
    delete_enabled = _parse_truthy(os.environ.get(ENV_OPERATIONAL_RETENTION_DELETE_ENABLE))
    return OperationalRetentionSettings(
        dry_run=not delete_enabled,
        adm02_audit_retention_days=_load_adm02_retention_days(),
    )


async def run_operational_retention_cleanup_from_env() -> None:
    config = load_runtime_config()
    dsn = (config.database_url or "").strip()
    if not dsn:
        raise ConfigurationError("missing or empty configuration: DATABASE_URL")

    settings = load_operational_retention_settings_from_env()
    pool = await _default_open_pool(dsn)
    try:
        async with pool.acquire() as conn:
            result = await run_operational_retention_cleanup(
                conn,
                now_utc=datetime.now(UTC),
                settings=settings,
            )
    finally:
        await pool.close()

    print(
        "operational_retention_cleanup",
        f"dry_run={result.dry_run}",
        f"telegram_update_dedup_expired_rows={result.telegram_update_dedup_expired_rows}",
        f"telegram_update_dedup_deleted_rows={result.telegram_update_dedup_deleted_rows}",
        f"adm02_audit_expired_rows={result.adm02_audit_expired_rows}",
        f"adm02_audit_deleted_rows={result.adm02_audit_deleted_rows}",
        f"adm02_audit_retention_days={result.adm02_audit_retention_days}",
        sep=" ",
    )


def main() -> None:
    asyncio.run(run_operational_retention_cleanup_from_env())


if __name__ == "__main__":
    main()
