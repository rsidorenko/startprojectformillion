"""In-memory slice-1 live raw bundle: raw bundle + loop control + live loop (wiring only)."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.bootstrap import Slice1Composition
from app.runtime.bridge import RuntimeUpdateBridge
from app.runtime.default_bridge import accept_mapping_runtime_update
from app.runtime.live_loop import LoopControl, Slice1LiveRawPollingLoop
from app.runtime.polling import PollingRuntimeConfig
from app.runtime.raw_polling import Slice1RawPollingRuntime, TelegramRawPollingClient
from app.runtime.raw_runner import Slice1RawPollingRunner
from app.runtime.raw_startup import build_slice1_in_memory_raw_runtime_bundle


@dataclass(frozen=True, slots=True)
class Slice1InMemoryLiveRawRuntimeBundle:
    composition: Slice1Composition
    config: PollingRuntimeConfig
    runtime: Slice1RawPollingRuntime
    runner: Slice1RawPollingRunner
    bridge: RuntimeUpdateBridge
    control: LoopControl
    live_loop: Slice1LiveRawPollingLoop


def build_slice1_in_memory_live_raw_runtime_bundle(
    client: TelegramRawPollingClient,
    bridge: RuntimeUpdateBridge,
    *,
    config: PollingRuntimeConfig | None = None,
    composition: Slice1Composition | None = None,
) -> Slice1InMemoryLiveRawRuntimeBundle:
    raw = build_slice1_in_memory_raw_runtime_bundle(client, bridge, config=config, composition=composition)
    control = LoopControl()
    live_loop = Slice1LiveRawPollingLoop(raw.runtime)
    return Slice1InMemoryLiveRawRuntimeBundle(
        composition=raw.composition,
        config=raw.config,
        runtime=raw.runtime,
        runner=raw.runner,
        bridge=raw.bridge,
        control=control,
        live_loop=live_loop,
    )


def build_slice1_in_memory_live_raw_runtime_bundle_with_default_bridge(
    client: TelegramRawPollingClient,
    *,
    config: PollingRuntimeConfig | None = None,
    composition: Slice1Composition | None = None,
) -> Slice1InMemoryLiveRawRuntimeBundle:
    return build_slice1_in_memory_live_raw_runtime_bundle(
        client,
        accept_mapping_runtime_update,
        config=config,
        composition=composition,
    )
