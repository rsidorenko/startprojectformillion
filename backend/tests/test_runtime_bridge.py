"""Tests for runtime bridge (raw update → mapping batch, no SDK/polling)."""

from __future__ import annotations

import pathlib

from app.runtime import (
    BridgeRuntimeBatchResult,
    RuntimeUpdateBridge,
    bridge_runtime_updates,
)


def test_two_valid_updates_two_accepted_mappings() -> None:
    raw_a = object()
    raw_b = object()

    def bridge(raw: object) -> dict[str, object] | None:
        if raw is raw_a:
            return {"update_id": 1}
        if raw is raw_b:
            return {"update_id": 2}
        return None

    r = bridge_runtime_updates([raw_a, raw_b], bridge)
    assert r == BridgeRuntimeBatchResult(
        accepted_updates=[{"update_id": 1}, {"update_id": 2}],
        accepted_count=2,
        rejected_count=0,
        bridge_exception_count=0,
    )


def test_none_increments_rejected_count() -> None:
    def bridge(raw: object) -> dict[str, object] | None:
        return None if raw == "skip" else {"ok": True}

    r = bridge_runtime_updates(["skip", "ok"], bridge)
    assert r.rejected_count == 1
    assert r.accepted_count == 1
    assert r.bridge_exception_count == 0


def test_bridge_exception_does_not_abort_batch() -> None:
    calls: list[str] = []

    def bridge(raw: object) -> dict[str, object] | None:
        calls.append(str(raw))
        if raw == "boom":
            raise ValueError("bad")
        return {"v": raw}

    r = bridge_runtime_updates(["a", "boom", "c"], bridge)
    assert calls == ["a", "boom", "c"]
    assert r.bridge_exception_count == 1
    assert r.accepted_updates == [{"v": "a"}, {"v": "c"}]
    assert r.accepted_count == 2
    assert r.rejected_count == 0


def test_mixed_batch_aggregates_counts() -> None:
    def bridge(raw: object) -> dict[str, object] | None:
        if raw == "n":
            return None
        if raw == "e":
            raise RuntimeError("x")
        return {"k": raw}

    r = bridge_runtime_updates(["ok", "n", "e", "ok2"], bridge)
    assert r.accepted_count == 2
    assert r.rejected_count == 1
    assert r.bridge_exception_count == 1
    assert r.accepted_updates == [{"k": "ok"}, {"k": "ok2"}]


def test_accepted_updates_do_not_echo_raw_objects() -> None:
    sentinel = {"inner": 1}

    def bridge(raw: object) -> dict[str, object] | None:
        return {"wrapped": True} if raw is sentinel else None

    r = bridge_runtime_updates([sentinel], bridge)
    assert len(r.accepted_updates) == 1
    out = r.accepted_updates[0]
    assert sentinel not in out.values()
    assert out == {"wrapped": True}


def test_runtime_update_bridge_protocol_is_callable_contract() -> None:
    def impl(raw: object) -> dict[str, object] | None:
        return {"u": id(raw)}

    b: RuntimeUpdateBridge = impl
    assert bridge_runtime_updates([1], b).accepted_count == 1


def test_bridge_module_has_no_forbidden_substrings() -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    text = (root / "src" / "app" / "runtime" / "bridge.py").read_text(encoding="utf-8").lower()
    for bad in ("billing", "issuance", "admin", "webhook"):
        assert bad not in text
