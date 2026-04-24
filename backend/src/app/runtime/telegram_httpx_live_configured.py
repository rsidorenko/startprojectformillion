"""Slice-1 httpx live app from :class:`RuntimeConfig` (delegation only)."""

from __future__ import annotations

import httpx

from app.persistence.postgres_migrations_runtime import (
    apply_slice1_postgres_migrations_from_runtime_config,
)
from app.persistence.slice1_postgres_wiring import (
    resolve_slice1_composition_for_runtime,
    slice1_postgres_repos_requested,
)
from app.runtime.polling import PollingRuntimeConfig
from app.runtime.polling_policy import DEFAULT_POLLING_POLICY, PollingPolicy
from app.runtime.telegram_httpx_live_app import (
    Slice1HttpxLiveRuntimeApp,
    build_slice1_httpx_live_runtime_app,
)
from app.security.config import RuntimeConfig, validate_runtime_config


def build_slice1_httpx_live_runtime_app_from_config(
    config: RuntimeConfig,
    *,
    polling_config: PollingRuntimeConfig | None = None,
    base_url: str | None = None,
    client: httpx.AsyncClient | None = None,
    polling_policy: PollingPolicy = DEFAULT_POLLING_POLICY,
) -> Slice1HttpxLiveRuntimeApp:
    validate_runtime_config(config)
    if slice1_postgres_repos_requested():
        raise RuntimeError(
            "SLICE1_USE_POSTGRES_REPOS is enabled, but the synchronous config builder "
            "cannot attach PostgreSQL-backed slice-1 composition. Use "
            "build_slice1_httpx_live_runtime_app_from_config_async (or another async entry "
            "that resolves composition via resolve_slice1_composition_for_runtime) instead."
        )
    poll = polling_config if polling_config is not None else PollingRuntimeConfig()
    return build_slice1_httpx_live_runtime_app(
        config.bot_token,
        config=poll,
        base_url=base_url,
        client=client,
        polling_policy=polling_policy,
    )


async def build_slice1_httpx_live_runtime_app_from_config_async(
    config: RuntimeConfig,
    *,
    polling_config: PollingRuntimeConfig | None = None,
    base_url: str | None = None,
    client: httpx.AsyncClient | None = None,
    polling_policy: PollingPolicy = DEFAULT_POLLING_POLICY,
) -> Slice1HttpxLiveRuntimeApp:
    validate_runtime_config(config)
    if slice1_postgres_repos_requested():
        await apply_slice1_postgres_migrations_from_runtime_config(config)
    composition, pg_pool = await resolve_slice1_composition_for_runtime(config)
    poll = polling_config if polling_config is not None else PollingRuntimeConfig()
    return build_slice1_httpx_live_runtime_app(
        config.bot_token,
        config=poll,
        base_url=base_url,
        client=client,
        polling_policy=polling_policy,
        composition=composition,
        pg_pool=pg_pool,
    )
