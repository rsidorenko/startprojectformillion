"""In-memory slice-1 raw runtime bundle: composition + bridge + raw runtime + runner (wiring only)."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.bootstrap import Slice1Composition, build_slice1_composition
from app.runtime.bridge import RuntimeUpdateBridge
from app.runtime.default_bridge import accept_mapping_runtime_update
from app.runtime.polling import PollingRuntimeConfig
from app.runtime.raw_polling import Slice1RawPollingRuntime, TelegramRawPollingClient
from app.runtime.raw_runner import Slice1RawPollingRunner


@dataclass(frozen=True, slots=True)
class Slice1InMemoryRawRuntimeBundle:
    """Holds slice-1 raw path pieces assembled for tests or local wiring (no loop, no env)."""

    composition: Slice1Composition
    config: PollingRuntimeConfig
    runtime: Slice1RawPollingRuntime
    runner: Slice1RawPollingRunner
    bridge: RuntimeUpdateBridge


def build_slice1_in_memory_raw_runtime_bundle(
    client: TelegramRawPollingClient,
    bridge: RuntimeUpdateBridge,
    *,
    config: PollingRuntimeConfig | None = None,
    composition: Slice1Composition | None = None,
) -> Slice1InMemoryRawRuntimeBundle:
    """Wire raw client and bridge into a single bundle; caller owns transport and bridge behavior."""

    resolved = config or PollingRuntimeConfig()
    resolved_composition = composition or build_slice1_composition()
    runtime = Slice1RawPollingRuntime(resolved_composition, client, bridge, config=resolved)
    runner = Slice1RawPollingRunner(runtime)
    return Slice1InMemoryRawRuntimeBundle(
        composition=resolved_composition,
        config=resolved,
        runtime=runtime,
        runner=runner,
        bridge=bridge,
    )


def build_slice1_in_memory_raw_runtime_bundle_with_default_bridge(
    client: TelegramRawPollingClient,
    *,
    config: PollingRuntimeConfig | None = None,
    composition: Slice1Composition | None = None,
) -> Slice1InMemoryRawRuntimeBundle:
    return build_slice1_in_memory_raw_runtime_bundle(
        client,
        accept_mapping_runtime_update,
        config=config,
        composition=composition,
    )
