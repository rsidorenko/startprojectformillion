"""Thin slice-1 live wiring: :class:`HttpxTelegramRawPollingClient` + in-memory live raw bundle."""

from __future__ import annotations

from dataclasses import dataclass

import asyncpg
import httpx

from app.application.bootstrap import Slice1Composition
from app.runtime.live_startup import (
    Slice1InMemoryLiveRawRuntimeBundle,
    build_slice1_in_memory_live_raw_runtime_bundle_with_default_bridge,
)
from app.runtime.polling import PollingRuntimeConfig
from app.runtime.polling_policy import DEFAULT_POLLING_POLICY, PollingPolicy
from app.runtime.telegram_httpx_raw_client import HttpxTelegramRawPollingClient


@dataclass(frozen=True, slots=True)
class Slice1HttpxLiveRuntimeBundle:
    client: HttpxTelegramRawPollingClient
    bundle: Slice1InMemoryLiveRawRuntimeBundle
    pg_pool: asyncpg.Pool | None = None

    async def aclose(self) -> None:
        if self.pg_pool is not None:
            await self.pg_pool.close()
        await self.client.aclose()


def build_slice1_httpx_live_runtime_bundle(
    bot_token: str,
    *,
    config: PollingRuntimeConfig | None = None,
    base_url: str | None = None,
    client: httpx.AsyncClient | None = None,
    polling_policy: PollingPolicy = DEFAULT_POLLING_POLICY,
    composition: Slice1Composition | None = None,
    pg_pool: asyncpg.Pool | None = None,
) -> Slice1HttpxLiveRuntimeBundle:
    httpx_telegram = HttpxTelegramRawPollingClient(
        bot_token,
        base_url=base_url,
        client=client,
        polling_policy=polling_policy,
    )
    inner = build_slice1_in_memory_live_raw_runtime_bundle_with_default_bridge(
        httpx_telegram,
        config=config,
        composition=composition,
    )
    return Slice1HttpxLiveRuntimeBundle(client=httpx_telegram, bundle=inner, pg_pool=pg_pool)
