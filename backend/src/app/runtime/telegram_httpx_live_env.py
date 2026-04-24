"""Slice-1 httpx live app from process env via :func:`load_runtime_config` (delegation only)."""

from __future__ import annotations

import httpx

from app.persistence.slice1_postgres_wiring import slice1_postgres_repos_requested
from app.runtime.polling import PollingRuntimeConfig
from app.runtime.polling_policy import DEFAULT_POLLING_POLICY, PollingPolicy
from app.runtime.telegram_httpx_live_app import Slice1HttpxLiveRuntimeApp
from app.runtime.telegram_httpx_live_configured import (
    build_slice1_httpx_live_runtime_app_from_config,
    build_slice1_httpx_live_runtime_app_from_config_async,
)
from app.security.config import load_runtime_config


def build_slice1_httpx_live_runtime_app_from_env(
    *,
    polling_config: PollingRuntimeConfig | None = None,
    base_url: str | None = None,
    client: httpx.AsyncClient | None = None,
    polling_policy: PollingPolicy = DEFAULT_POLLING_POLICY,
) -> Slice1HttpxLiveRuntimeApp:
    if slice1_postgres_repos_requested():
        raise RuntimeError(
            "SLICE1_USE_POSTGRES_REPOS is enabled, but the synchronous env builder "
            "cannot attach PostgreSQL-backed slice-1 composition. Use "
            "build_slice1_httpx_live_runtime_app_from_env_async (or another async entry "
            "that resolves composition via resolve_slice1_composition_for_runtime) instead."
        )
    config = load_runtime_config()
    return build_slice1_httpx_live_runtime_app_from_config(
        config,
        polling_config=polling_config,
        base_url=base_url,
        client=client,
        polling_policy=polling_policy,
    )


async def build_slice1_httpx_live_runtime_app_from_env_async(
    *,
    polling_config: PollingRuntimeConfig | None = None,
    base_url: str | None = None,
    client: httpx.AsyncClient | None = None,
    polling_policy: PollingPolicy = DEFAULT_POLLING_POLICY,
) -> Slice1HttpxLiveRuntimeApp:
    """Like :func:`build_slice1_httpx_live_runtime_app_from_env` but resolves optional PostgreSQL repos."""
    config = load_runtime_config()
    return await build_slice1_httpx_live_runtime_app_from_config_async(
        config,
        polling_config=polling_config,
        base_url=base_url,
        client=client,
        polling_policy=polling_policy,
    )
