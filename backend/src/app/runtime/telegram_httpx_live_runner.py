"""Fixed-iteration helper over httpx live raw bundle (no process entry)."""

from __future__ import annotations

import httpx

from app.runtime.polling import PollingRuntimeConfig
from app.runtime.polling_policy import DEFAULT_POLLING_POLICY, PollingPolicy
from app.runtime.runner import PollingRunSummary
from app.runtime.telegram_httpx_live_startup import build_slice1_httpx_live_runtime_bundle


async def run_slice1_httpx_live_iterations(
    bot_token: str,
    iterations: int,
    *,
    config: PollingRuntimeConfig | None = None,
    base_url: str | None = None,
    client: httpx.AsyncClient | None = None,
    correlation_id: str | None = None,
    polling_policy: PollingPolicy = DEFAULT_POLLING_POLICY,
) -> PollingRunSummary:
    bundle = build_slice1_httpx_live_runtime_bundle(
        bot_token,
        config=config,
        base_url=base_url,
        client=client,
        polling_policy=polling_policy,
    )
    try:
        return await bundle.bundle.live_loop.run_until_stopped(
            bundle.bundle.control,
            correlation_id=correlation_id,
            max_iterations=iterations,
        )
    finally:
        await bundle.aclose()
