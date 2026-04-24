"""Fixed-iteration helper: raw httpx app from env via :func:`build_slice1_httpx_raw_runtime_app_from_env`."""

from __future__ import annotations

import httpx

from app.runtime.polling import PollingRuntimeConfig
from app.runtime.polling_policy import DEFAULT_POLLING_POLICY, PollingPolicy
from app.runtime.runner import PollingRunSummary
from app.runtime.telegram_httpx_raw_env import build_slice1_httpx_raw_runtime_app_from_env


async def run_slice1_httpx_raw_iterations_from_env(
    iterations: int,
    *,
    polling_config: PollingRuntimeConfig | None = None,
    polling_policy: PollingPolicy = DEFAULT_POLLING_POLICY,
    base_url: str | None = None,
    client: httpx.AsyncClient | None = None,
    correlation_id: str | None = None,
) -> PollingRunSummary:
    app = build_slice1_httpx_raw_runtime_app_from_env(
        polling_config=polling_config,
        base_url=base_url,
        client=client,
        polling_policy=polling_policy,
    )
    try:
        return await app.run_iterations(iterations, correlation_id=correlation_id)
    finally:
        await app.aclose()
