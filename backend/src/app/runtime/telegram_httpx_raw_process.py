"""Process-owned env-built httpx raw app (delegation only)."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.runtime.polling import PollingRuntimeConfig
from app.runtime.polling_policy import DEFAULT_POLLING_POLICY, PollingPolicy
from app.runtime.raw_polling import RawPollingBatchResult
from app.runtime.runner import PollingRunSummary
from app.runtime.telegram_httpx_raw_app import Slice1HttpxRawRuntimeApp
from app.runtime.telegram_httpx_raw_env import build_slice1_httpx_raw_runtime_app_from_env


@dataclass
class Slice1HttpxRawProcess:
    app: Slice1HttpxRawRuntimeApp

    async def run_iterations(
        self,
        iterations: int,
        *,
        correlation_id: str | None = None,
    ) -> PollingRunSummary:
        return await self.app.run_iterations(iterations, correlation_id=correlation_id)

    async def poll_once(self, *, correlation_id: str | None = None) -> RawPollingBatchResult:
        return await self.app.poll_once(correlation_id=correlation_id)

    async def aclose(self) -> None:
        await self.app.aclose()


def build_slice1_httpx_raw_process_from_env(
    *,
    polling_config: PollingRuntimeConfig | None = None,
    base_url: str | None = None,
    client: httpx.AsyncClient | None = None,
    polling_policy: PollingPolicy = DEFAULT_POLLING_POLICY,
) -> Slice1HttpxRawProcess:
    app = build_slice1_httpx_raw_runtime_app_from_env(
        polling_config=polling_config,
        base_url=base_url,
        client=client,
        polling_policy=polling_policy,
    )
    return Slice1HttpxRawProcess(app=app)
