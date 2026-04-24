"""Thin process-owned wrapper over :class:`Slice1HttpxLiveRuntimeBundle` (reuse only)."""

from __future__ import annotations

from dataclasses import dataclass

import asyncpg
import httpx

from app.application.bootstrap import Slice1Composition
from app.runtime.live_loop import LoopControl
from app.runtime.polling import PollingRuntimeConfig
from app.runtime.polling_policy import DEFAULT_POLLING_POLICY, PollingPolicy
from app.runtime.runner import PollingRunSummary
from app.runtime.telegram_httpx_live_startup import (
    Slice1HttpxLiveRuntimeBundle,
    build_slice1_httpx_live_runtime_bundle,
)


@dataclass
class Slice1HttpxLiveRuntimeApp:
    bundle: Slice1HttpxLiveRuntimeBundle

    async def run_iterations(
        self,
        iterations: int,
        *,
        correlation_id: str | None = None,
    ) -> PollingRunSummary:
        return await self.bundle.bundle.live_loop.run_until_stopped(
            LoopControl(),
            correlation_id=correlation_id,
            max_iterations=iterations,
        )

    async def run_until_stopped(
        self,
        control: LoopControl,
        *,
        correlation_id: str | None = None,
        max_iterations: int | None = None,
    ) -> PollingRunSummary:
        return await self.bundle.bundle.live_loop.run_until_stopped(
            control,
            correlation_id=correlation_id,
            max_iterations=max_iterations,
        )

    async def aclose(self) -> None:
        await self.bundle.aclose()


def build_slice1_httpx_live_runtime_app(
    bot_token: str,
    *,
    config: PollingRuntimeConfig | None = None,
    base_url: str | None = None,
    client: httpx.AsyncClient | None = None,
    polling_policy: PollingPolicy = DEFAULT_POLLING_POLICY,
    composition: Slice1Composition | None = None,
    pg_pool: asyncpg.Pool | None = None,
) -> Slice1HttpxLiveRuntimeApp:
    return Slice1HttpxLiveRuntimeApp(
        bundle=build_slice1_httpx_live_runtime_bundle(
            bot_token,
            config=config,
            base_url=base_url,
            client=client,
            polling_policy=polling_policy,
            composition=composition,
            pg_pool=pg_pool,
        ),
    )
