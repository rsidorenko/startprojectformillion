"""Fixed-iteration helper: live httpx app from env via :func:`build_slice1_httpx_live_runtime_app_from_env_async`."""

from __future__ import annotations

import httpx

from app.runtime.polling import PollingRuntimeConfig
from app.runtime.polling_policy import DEFAULT_POLLING_POLICY, PollingPolicy
from app.runtime.runner import PollingRunSummary
from app.runtime.telegram_httpx_live_env import build_slice1_httpx_live_runtime_app_from_env_async


async def run_slice1_httpx_live_iterations_from_env(
    iterations: int,
    *,
    polling_config: PollingRuntimeConfig | None = None,
    base_url: str | None = None,
    client: httpx.AsyncClient | None = None,
    correlation_id: str | None = None,
    polling_policy: PollingPolicy = DEFAULT_POLLING_POLICY,
) -> PollingRunSummary:
    app = await build_slice1_httpx_live_runtime_app_from_env_async(
        polling_config=polling_config,
        base_url=base_url,
        client=client,
        polling_policy=polling_policy,
    )
    try:
        return await app.run_iterations(iterations, correlation_id=correlation_id)
    finally:
        await app.aclose()
