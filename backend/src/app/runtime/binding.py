"""Thin seam: bridge raw updates, then delegate to :class:`Slice1PollingRuntime` batch processing."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.runtime.bridge import RuntimeUpdateBridge, bridge_runtime_updates
from app.runtime.polling import Slice1PollingRuntime


@dataclass(frozen=True, slots=True)
class BoundRuntimeBatchResult:
    """Aggregated bridge + runtime batch counters (no payloads, no exception details)."""

    raw_received_count: int
    bridge_accepted_count: int
    bridge_rejected_count: int
    bridge_exception_count: int
    send_count: int
    noop_count: int
    send_failure_count: int
    processing_failure_count: int


async def process_raw_updates_with_bridge(
    runtime: Slice1PollingRuntime,
    raw_updates: Sequence[object],
    bridge: RuntimeUpdateBridge,
    *,
    correlation_id: str | None = None,
) -> BoundRuntimeBatchResult:
    """Bridge ``raw_updates``, then run ``runtime.process_batch`` on accepted mappings only."""
    raw_received_count = len(raw_updates)
    bridged = bridge_runtime_updates(raw_updates, bridge)
    if not bridged.accepted_updates:
        return BoundRuntimeBatchResult(
            raw_received_count=raw_received_count,
            bridge_accepted_count=bridged.accepted_count,
            bridge_rejected_count=bridged.rejected_count,
            bridge_exception_count=bridged.bridge_exception_count,
            send_count=0,
            noop_count=0,
            send_failure_count=0,
            processing_failure_count=0,
        )
    batch = await runtime.process_batch(
        bridged.accepted_updates,
        correlation_id=correlation_id,
    )
    return BoundRuntimeBatchResult(
        raw_received_count=raw_received_count,
        bridge_accepted_count=bridged.accepted_count,
        bridge_rejected_count=bridged.rejected_count,
        bridge_exception_count=bridged.bridge_exception_count,
        send_count=batch.send_count,
        noop_count=batch.noop_count,
        send_failure_count=batch.send_failure_count,
        processing_failure_count=batch.processing_failure_count,
    )
