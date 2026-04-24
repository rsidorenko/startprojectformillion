"""SDK-agnostic bridge from raw transport updates to mapping-shaped pipeline input."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol


class RuntimeUpdateBridge(Protocol):
    """Maps one raw update into pipeline input, or None if the update must be skipped."""

    def __call__(self, raw_update: object) -> Mapping[str, object] | None: ...


@dataclass(frozen=True, slots=True)
class BridgeRuntimeBatchResult:
    """Outcome of bridging a batch of raw updates (no logging, no side effects)."""

    accepted_updates: list[Mapping[str, object]]
    accepted_count: int
    rejected_count: int
    bridge_exception_count: int


def bridge_runtime_updates(
    raw_updates: Sequence[object],
    bridge: Callable[[object], Mapping[str, object] | None],
) -> BridgeRuntimeBatchResult:
    """Bridge each raw update; failures in one item do not abort the batch."""
    accepted: list[Mapping[str, object]] = []
    rejected_count = 0
    bridge_exception_count = 0
    for raw in raw_updates:
        try:
            mapped = bridge(raw)
        except Exception:
            bridge_exception_count += 1
            continue
        if mapped is None:
            rejected_count += 1
        else:
            accepted.append(mapped)
    return BridgeRuntimeBatchResult(
        accepted_updates=accepted,
        accepted_count=len(accepted),
        rejected_count=rejected_count,
        bridge_exception_count=bridge_exception_count,
    )
