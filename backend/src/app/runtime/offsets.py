"""Pure helpers for long-polling offset from raw update mappings."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def _valid_update_ids(raw_updates: Sequence[Mapping[str, object]]) -> list[int]:
    out: list[int] = []
    for m in raw_updates:
        if "update_id" not in m:
            continue
        v = m["update_id"]
        if type(v) is not int or v <= 0:
            continue
        out.append(v)
    return out


def extract_next_offset_from_raw_updates(
    raw_updates: Sequence[Mapping[str, object]],
) -> int | None:
    """Next offset after the batch (``max(update_id) + 1``), or ``None`` if no valid ids."""
    ids = _valid_update_ids(raw_updates)
    if not ids:
        return None
    return max(ids) + 1


def advance_polling_offset(
    current_offset: int | None,
    raw_updates: Sequence[Mapping[str, object]],
) -> int | None:
    """Combine ``current_offset`` with batch-derived offset; offset never decreases."""
    if current_offset is not None:
        if type(current_offset) is not int:
            raise TypeError("current_offset must be int or None")
        if current_offset <= 0:
            raise ValueError("current_offset must be positive")
    derived = extract_next_offset_from_raw_updates(raw_updates)
    if derived is None:
        return current_offset
    if current_offset is None:
        return derived
    return max(current_offset, derived)
