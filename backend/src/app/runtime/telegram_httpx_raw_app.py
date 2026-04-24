"""Thin process-owned wrapper over :class:`Slice1HttpxRawRuntimeBundle` (reuse only)."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.runtime.polling import PollingRuntimeConfig
from app.runtime.polling_policy import DEFAULT_POLLING_POLICY, PollingPolicy
from app.runtime.raw_polling import RawPollingBatchResult
from app.runtime.runner import PollingRunSummary
from app.runtime.telegram_httpx_raw_startup import (
    Slice1HttpxRawRuntimeBundle,
    build_slice1_httpx_raw_runtime_bundle,
)


@dataclass
class Slice1HttpxRawRuntimeApp:
    bundle: Slice1HttpxRawRuntimeBundle

    async def run_iterations(
        self,
        iterations: int,
        *,
        correlation_id: str | None = None,
    ) -> PollingRunSummary:
        return await self.bundle.bundle.runner.run_iterations(
            iterations,
            correlation_id=correlation_id,
        )

    async def poll_once(self, *, correlation_id: str | None = None) -> RawPollingBatchResult:
        return await self.bundle.bundle.runtime.poll_once(correlation_id=correlation_id)

    async def aclose(self) -> None:
        await self.bundle.aclose()


def build_slice1_httpx_raw_runtime_app(
    bot_token: str,
    *,
    config: PollingRuntimeConfig | None = None,
    base_url: str | None = None,
    client: httpx.AsyncClient | None = None,
    polling_policy: PollingPolicy = DEFAULT_POLLING_POLICY,
) -> Slice1HttpxRawRuntimeApp:
    return Slice1HttpxRawRuntimeApp(
        bundle=build_slice1_httpx_raw_runtime_bundle(
            bot_token,
            config=config,
            base_url=base_url,
            client=client,
            polling_policy=polling_policy,
        ),
    )
