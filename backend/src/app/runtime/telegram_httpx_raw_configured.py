"""Slice-1 httpx raw app from :class:`RuntimeConfig` (delegation only)."""

from __future__ import annotations

import httpx

from app.runtime.polling import PollingRuntimeConfig
from app.runtime.polling_policy import DEFAULT_POLLING_POLICY, PollingPolicy
from app.runtime.telegram_httpx_raw_app import (
    Slice1HttpxRawRuntimeApp,
    build_slice1_httpx_raw_runtime_app,
)
from app.security.config import RuntimeConfig


def build_slice1_httpx_raw_runtime_app_from_config(
    config: RuntimeConfig,
    *,
    polling_config: PollingRuntimeConfig | None = None,
    base_url: str | None = None,
    client: httpx.AsyncClient | None = None,
    polling_policy: PollingPolicy = DEFAULT_POLLING_POLICY,
) -> Slice1HttpxRawRuntimeApp:
    poll = polling_config if polling_config is not None else PollingRuntimeConfig()
    return build_slice1_httpx_raw_runtime_app(
        config.bot_token,
        config=poll,
        base_url=base_url,
        client=client,
        polling_policy=polling_policy,
    )
