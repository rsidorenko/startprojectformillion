"""Live iteration over :meth:`Slice1PollingRuntime.poll_once` / raw ``poll_once`` (no timing)."""

from __future__ import annotations

from dataclasses import dataclass

from app.runtime.polling import Slice1PollingRuntime
from app.runtime.raw_polling import Slice1RawPollingRuntime
from app.runtime.runner import PollingRunSummary


@dataclass
class LoopControl:
    stop_requested: bool = False


def _empty_live_summary() -> PollingRunSummary:
    return PollingRunSummary(
        iterations_requested=0,
        iterations_completed=0,
        received_count=0,
        send_count=0,
        noop_count=0,
        send_failure_count=0,
        processing_failure_count=0,
        fetch_failure_count=0,
        poll_once_exception_count=0,
    )


def _validate_max_iterations(max_iterations: int | None) -> None:
    if max_iterations is None:
        return
    if type(max_iterations) is not int:
        raise TypeError("max_iterations must be int or None")
    if max_iterations < 0:
        raise ValueError("max_iterations must be non-negative")


class Slice1LivePollingLoop:
    __slots__ = ("_runtime",)

    def __init__(self, runtime: Slice1PollingRuntime) -> None:
        self._runtime = runtime

    async def run_until_stopped(
        self,
        control: LoopControl,
        *,
        correlation_id: str | None = None,
        max_iterations: int | None = None,
    ) -> PollingRunSummary:
        if control.stop_requested:
            return _empty_live_summary()
        _validate_max_iterations(max_iterations)
        if max_iterations == 0:
            return _empty_live_summary()

        received = 0
        send = 0
        noop = 0
        send_fail = 0
        process_fail = 0
        fetch_fail = 0
        completed = 0
        exc_count = 0

        while not control.stop_requested:
            if max_iterations is not None and (completed + exc_count) >= max_iterations:
                break
            try:
                batch = await self._runtime.poll_once(correlation_id=correlation_id)
            except Exception:
                exc_count += 1
                continue
            completed += 1
            received += batch.received_count
            send += batch.send_count
            noop += batch.noop_count
            send_fail += batch.send_failure_count
            process_fail += batch.processing_failure_count
            fetch_fail += batch.fetch_failure_count

        started = completed + exc_count
        return PollingRunSummary(
            iterations_requested=started,
            iterations_completed=completed,
            received_count=received,
            send_count=send,
            noop_count=noop,
            send_failure_count=send_fail,
            processing_failure_count=process_fail,
            fetch_failure_count=fetch_fail,
            poll_once_exception_count=exc_count,
        )


class Slice1LiveRawPollingLoop:
    __slots__ = ("_runtime",)

    def __init__(self, runtime: Slice1RawPollingRuntime) -> None:
        self._runtime = runtime

    async def run_until_stopped(
        self,
        control: LoopControl,
        *,
        correlation_id: str | None = None,
        max_iterations: int | None = None,
    ) -> PollingRunSummary:
        if control.stop_requested:
            return _empty_live_summary()
        _validate_max_iterations(max_iterations)
        if max_iterations == 0:
            return _empty_live_summary()

        received = 0
        send = 0
        noop = 0
        send_fail = 0
        process_fail = 0
        fetch_fail = 0
        completed = 0
        exc_count = 0

        while not control.stop_requested:
            if max_iterations is not None and (completed + exc_count) >= max_iterations:
                break
            try:
                batch = await self._runtime.poll_once(correlation_id=correlation_id)
            except Exception:
                exc_count += 1
                continue
            completed += 1
            received += batch.raw_received_count
            send += batch.send_count
            noop += batch.noop_count
            send_fail += batch.send_failure_count
            process_fail += batch.processing_failure_count
            fetch_fail += batch.fetch_failure_count

        started = completed + exc_count
        return PollingRunSummary(
            iterations_requested=started,
            iterations_completed=completed,
            received_count=received,
            send_count=send,
            noop_count=noop,
            send_failure_count=send_fail,
            processing_failure_count=process_fail,
            fetch_failure_count=fetch_fail,
            poll_once_exception_count=exc_count,
        )


async def run_live_polling_until_stopped(
    runtime: Slice1PollingRuntime,
    control: LoopControl,
    *,
    correlation_id: str | None = None,
    max_iterations: int | None = None,
) -> PollingRunSummary:
    return await Slice1LivePollingLoop(runtime).run_until_stopped(
        control,
        correlation_id=correlation_id,
        max_iterations=max_iterations,
    )


async def run_live_raw_polling_until_stopped(
    runtime: Slice1RawPollingRuntime,
    control: LoopControl,
    *,
    correlation_id: str | None = None,
    max_iterations: int | None = None,
) -> PollingRunSummary:
    return await Slice1LiveRawPollingLoop(runtime).run_until_stopped(
        control,
        correlation_id=correlation_id,
        max_iterations=max_iterations,
    )
