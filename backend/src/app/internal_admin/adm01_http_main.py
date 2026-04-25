"""Standalone ADM-01 internal HTTP process entry (optional uvicorn listener; Telegram polling unchanged)."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Awaitable, Callable
from typing import Any

import asyncpg
import uvicorn

from app.admin_support.contracts import (
    AdminPolicyFlag,
    EntitlementSummary,
    EntitlementSummaryCategory,
    InternalUserTarget,
)
from app.admin_support.adm01_wiring import (
    build_adm01_subscription_read_from_postgres_snapshots,
)
from app.internal_admin.adm01_bundle import (
    Adm01InternalLookupWithPostgresIssuanceStateDependencies,
    build_adm01_internal_lookup_starlette_app_with_postgres_issuance_state,
)
from app.internal_admin.adm01_http_config import (
    Adm01InternalHttpConfig,
    load_adm01_internal_http_config_from_env,
)
from app.persistence.postgres_issuance_state import PostgresIssuanceStateRepository
from app.persistence.postgres_subscription_snapshot import PostgresSubscriptionSnapshotReader
from app.persistence.postgres_migrations_runtime import apply_slice1_postgres_migrations_from_runtime_config
from app.security.config import ConfigurationError, RuntimeConfig, load_runtime_config

_ENV_ALLOWLIST = "ADM01_INTERNAL_HTTP_ALLOWLIST"

_STDOUT_DISABLED = "adm01_internal_http: disabled"
_STDERR_CONFIG = "adm01_internal_http: config_error"
_STDERR_FAILED = "adm01_internal_http: failed"


class _IdentityEchoInternalUserId:
    async def resolve_internal_user_id(self, target: object, *, correlation_id: str) -> str | None:
        if isinstance(target, InternalUserTarget):
            return target.internal_user_id
        return None


class _EntitlementReadMinimal:
    async def get_entitlement_summary(self, internal_user_id: str) -> EntitlementSummary:
        return EntitlementSummary(category=EntitlementSummaryCategory.UNKNOWN)


class _PolicyReadMinimal:
    async def get_policy_flag(self, internal_user_id: str) -> AdminPolicyFlag:
        return AdminPolicyFlag.DEFAULT


def _load_allowlist_principal_ids_from_env() -> tuple[str, ...]:
    raw = os.environ.get(_ENV_ALLOWLIST, "").strip()
    if not raw:
        msg = f"missing or empty configuration: {_ENV_ALLOWLIST}"
        raise ConfigurationError(msg)
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        msg = f"missing or empty configuration: {_ENV_ALLOWLIST}"
        raise ConfigurationError(msg)
    return tuple(parts)


async def _default_create_pool(dsn: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn, min_size=1, max_size=4)


async def _run_uvicorn_app(app: object, *, host: str, port: int) -> None:
    """Run uvicorn until stopped. Intended to be monkeypatched in tests (no real socket when patched)."""
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
        use_colors=False,
    )
    server = uvicorn.Server(config)
    await server.serve()


async def async_run_adm01_internal_http_from_env(
    *,
    load_adm01_config: Callable[[], Adm01InternalHttpConfig] = load_adm01_internal_http_config_from_env,
    load_runtime: Callable[[], RuntimeConfig] = load_runtime_config,
    apply_migrations: Callable[..., Awaitable[None]] = apply_slice1_postgres_migrations_from_runtime_config,
    create_pool: Callable[[str], Awaitable[asyncpg.Pool]] | None = None,
    build_app: Callable[
        [Adm01InternalLookupWithPostgresIssuanceStateDependencies],
        Any,
    ] = build_adm01_internal_lookup_starlette_app_with_postgres_issuance_state,
    run_uvicorn: Callable[..., Awaitable[None]] | None = None,
) -> int:
    """
    Load config from the process environment, optionally run migrations, pool, and uvicorn.

    Returns ``0`` on success or disabled; ``1`` on configuration or startup failure.
    """
    try:
        http_cfg = load_adm01_config()
    except ConfigurationError:
        print(_STDERR_CONFIG, file=sys.stderr, flush=True)
        return 1

    if not http_cfg.enabled:
        print(_STDOUT_DISABLED, flush=True)
        return 0

    pool_opener = create_pool if create_pool is not None else _default_create_pool
    uvicorn_runner = run_uvicorn if run_uvicorn is not None else _run_uvicorn_app

    try:
        rt = load_runtime()
    except ConfigurationError:
        print(_STDERR_CONFIG, file=sys.stderr, flush=True)
        return 1

    try:
        allowlist = _load_allowlist_principal_ids_from_env()
    except ConfigurationError:
        print(_STDERR_CONFIG, file=sys.stderr, flush=True)
        return 1

    try:
        await apply_migrations(rt)
    except ConfigurationError:
        print(_STDERR_CONFIG, file=sys.stderr, flush=True)
        return 1
    except Exception:
        print(_STDERR_FAILED, file=sys.stderr, flush=True)
        return 1

    dsn = (rt.database_url or "").strip()
    if not dsn:
        print(_STDERR_CONFIG, file=sys.stderr, flush=True)
        return 1

    pool: asyncpg.Pool | None = None
    try:
        try:
            pool = await pool_opener(dsn)
        except Exception:
            print(_STDERR_FAILED, file=sys.stderr, flush=True)
            return 1

        repo = PostgresIssuanceStateRepository(pool)
        snapshots = PostgresSubscriptionSnapshotReader(pool)
        deps = Adm01InternalLookupWithPostgresIssuanceStateDependencies(
            identity=_IdentityEchoInternalUserId(),
            subscription=build_adm01_subscription_read_from_postgres_snapshots(snapshots),
            entitlement=_EntitlementReadMinimal(),
            postgres_issuance_state=repo,
            policy=_PolicyReadMinimal(),
            redaction=None,
            adm01_allowlisted_internal_admin_principal_ids=allowlist,
        )
        app = build_app(deps)
        await uvicorn_runner(
            app,
            host=http_cfg.bind_host,
            port=http_cfg.bind_port,
        )
    except ConfigurationError:
        print(_STDERR_CONFIG, file=sys.stderr, flush=True)
        return 1
    except Exception:
        print(_STDERR_FAILED, file=sys.stderr, flush=True)
        return 1
    finally:
        if pool is not None:
            try:
                await pool.close()
            except Exception:
                pass

    return 0


def main(argv: list[str] | None = None) -> int:
    _ = argv
    try:
        return asyncio.run(async_run_adm01_internal_http_from_env())
    except ConfigurationError:
        print(_STDERR_CONFIG, file=sys.stderr, flush=True)
        return 1
    except Exception:
        print(_STDERR_FAILED, file=sys.stderr, flush=True)
        return 1


__all__ = [
    "async_run_adm01_internal_http_from_env",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
