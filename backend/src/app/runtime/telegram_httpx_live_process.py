"""Process-owned env-built httpx live app + :class:`LoopControl` (delegation only)."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.runtime.live_loop import LoopControl
from app.runtime.polling import PollingRuntimeConfig
from app.runtime.polling_policy import DEFAULT_POLLING_POLICY, PollingPolicy
from app.runtime.runner import PollingRunSummary
from app.runtime.telegram_httpx_live_app import Slice1HttpxLiveRuntimeApp
from app.runtime.telegram_httpx_live_configured import (
    build_slice1_httpx_live_runtime_app_from_config_async,
)
from app.runtime.telegram_httpx_live_env import (
    build_slice1_httpx_live_runtime_app_from_env,
    build_slice1_httpx_live_runtime_app_from_env_async,
)
from app.security.config import RuntimeConfig


@dataclass
class Slice1HttpxLiveProcess:
    app: Slice1HttpxLiveRuntimeApp
    control: LoopControl

    async def run_until_stopped(
        self,
        *,
        correlation_id: str | None = None,
        max_iterations: int | None = None,
    ) -> PollingRunSummary:
        return await self.app.run_until_stopped(
            self.control,
            correlation_id=correlation_id,
            max_iterations=max_iterations,
        )

    def request_stop(self) -> None:
        self.control.stop_requested = True

    async def aclose(self) -> None:
        await self.app.aclose()


def build_slice1_httpx_live_process_from_env(
    *,
    polling_config: PollingRuntimeConfig | None = None,
    base_url: str | None = None,
    client: httpx.AsyncClient | None = None,
    polling_policy: PollingPolicy = DEFAULT_POLLING_POLICY,
) -> Slice1HttpxLiveProcess:
    app = build_slice1_httpx_live_runtime_app_from_env(
        polling_config=polling_config,
        base_url=base_url,
        client=client,
        polling_policy=polling_policy,
    )
    return Slice1HttpxLiveProcess(app=app, control=LoopControl())


async def build_slice1_httpx_live_process_from_env_async(
    *,
    polling_config: PollingRuntimeConfig | None = None,
    base_url: str | None = None,
    client: httpx.AsyncClient | None = None,
    polling_policy: PollingPolicy = DEFAULT_POLLING_POLICY,
) -> Slice1HttpxLiveProcess:
    app = await build_slice1_httpx_live_runtime_app_from_env_async(
        polling_config=polling_config,
        base_url=base_url,
        client=client,
        polling_policy=polling_policy,
    )
    return Slice1HttpxLiveProcess(app=app, control=LoopControl())


async def build_slice1_httpx_live_process_from_config_async(
    config: RuntimeConfig,
    *,
    polling_config: PollingRuntimeConfig | None = None,
    base_url: str | None = None,
    client: httpx.AsyncClient | None = None,
    polling_policy: PollingPolicy = DEFAULT_POLLING_POLICY,
) -> Slice1HttpxLiveProcess:
    app = await build_slice1_httpx_live_runtime_app_from_config_async(
        config,
        polling_config=polling_config,
        base_url=base_url,
        client=client,
        polling_policy=polling_policy,
    )
    return Slice1HttpxLiveProcess(app=app, control=LoopControl())
