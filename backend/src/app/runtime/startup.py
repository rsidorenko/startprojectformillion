"""In-memory slice-1 runtime bundle assembly (not production startup, not SDK binding).

This module only wires existing :func:`build_slice1_composition`, :class:`Slice1PollingRuntime`,
and :class:`Slice1PollingRunner` into one object. It does not load env, open the network, or run
a polling loop.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.bootstrap import Slice1Composition, build_slice1_composition
from app.runtime.polling import PollingRuntimeConfig, Slice1PollingRuntime, TelegramPollingClient
from app.runtime.runner import Slice1PollingRunner


@dataclass(frozen=True, slots=True)
class Slice1InMemoryRuntimeBundle:
    """Single object holding slice-1 composition, polling config, runtime, and runner (in-memory wiring)."""

    composition: Slice1Composition
    config: PollingRuntimeConfig
    runtime: Slice1PollingRuntime
    runner: Slice1PollingRunner


def build_slice1_in_memory_runtime_bundle(
    client: TelegramPollingClient,
    *,
    config: PollingRuntimeConfig | None = None,
) -> Slice1InMemoryRuntimeBundle:
    """Build an in-memory slice-1 bundle around ``client`` (caller supplies transport double or adapter)."""

    resolved = config or PollingRuntimeConfig()
    composition = build_slice1_composition()
    runtime = Slice1PollingRuntime(composition, client, config=resolved)
    runner = Slice1PollingRunner(runtime)
    return Slice1InMemoryRuntimeBundle(
        composition=composition,
        config=resolved,
        runtime=runtime,
        runner=runner,
    )
