"""Slice-1 httpx raw app from process env via :func:`load_runtime_config` (delegation only)."""

from __future__ import annotations

import httpx

from app.runtime.polling import PollingRuntimeConfig
from app.runtime.polling_policy import DEFAULT_POLLING_POLICY, PollingPolicy
from app.runtime.telegram_httpx_raw_app import Slice1HttpxRawRuntimeApp
from app.runtime.telegram_httpx_raw_configured import (
    build_slice1_httpx_raw_runtime_app_from_config,
)
from app.security.config import load_runtime_config


def build_slice1_httpx_raw_runtime_app_from_env(
    *,
    polling_config: PollingRuntimeConfig | None = None,
    base_url: str | None = None,
    client: httpx.AsyncClient | None = None,
    polling_policy: PollingPolicy = DEFAULT_POLLING_POLICY,
) -> Slice1HttpxRawRuntimeApp:
    config = load_runtime_config()
    return build_slice1_httpx_raw_runtime_app_from_config(
        config,
        polling_config=polling_config,
        base_url=base_url,
        client=client,
        polling_policy=polling_policy,
    )
