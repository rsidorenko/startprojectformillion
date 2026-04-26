"""Safe Telegram update dedup guard for dispatcher boundary."""

from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from typing import Callable, Literal, Protocol

TelegramUpdateDedupCommandBucket = Literal["status", "access_resend", "other"]
TELEGRAM_UPDATE_DEDUP_TTL_SECONDS_DEFAULT = 600.0
TELEGRAM_UPDATE_DEDUP_MAX_ENTRIES_DEFAULT = 10_000


class TelegramUpdateDedupGuard(Protocol):
    async def mark_if_first_seen(
        self,
        *,
        command_bucket: TelegramUpdateDedupCommandBucket,
        telegram_update_id: int,
    ) -> bool: ...


def dedup_key_hash_for_update(
    *,
    command_bucket: TelegramUpdateDedupCommandBucket,
    telegram_update_id: int,
) -> str:
    material = f"v1|{command_bucket}|{int(telegram_update_id)}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class InMemoryTelegramUpdateDedupGuard:
    """Bounded in-memory dedup keyed by (command bucket, Telegram update id)."""

    def __init__(
        self,
        *,
        ttl_seconds: float = TELEGRAM_UPDATE_DEDUP_TTL_SECONDS_DEFAULT,
        max_entries: int = TELEGRAM_UPDATE_DEDUP_MAX_ENTRIES_DEFAULT,
        now_seconds: Callable[[], float] = time.time,
    ) -> None:
        self._ttl_seconds = float(ttl_seconds)
        self._max_entries = int(max_entries)
        self._now_seconds = now_seconds
        self._seen: OrderedDict[tuple[str, int], float] = OrderedDict()

    async def mark_if_first_seen(
        self,
        *,
        command_bucket: TelegramUpdateDedupCommandBucket,
        telegram_update_id: int,
    ) -> bool:
        now = float(self._now_seconds())
        self._evict_expired(now)
        key = (command_bucket, int(telegram_update_id))
        if key in self._seen:
            self._seen.move_to_end(key)
            return False
        self._seen[key] = now
        self._evict_overflow()
        return True

    def _evict_expired(self, now: float) -> None:
        if self._ttl_seconds <= 0:
            self._seen.clear()
            return
        expiry_threshold = now - self._ttl_seconds
        while self._seen:
            _, seen_at = next(iter(self._seen.items()))
            if seen_at > expiry_threshold:
                break
            self._seen.popitem(last=False)

    def _evict_overflow(self) -> None:
        while len(self._seen) > self._max_entries:
            self._seen.popitem(last=False)


class NoopTelegramUpdateDedupGuard:
    async def mark_if_first_seen(
        self,
        *,
        command_bucket: TelegramUpdateDedupCommandBucket,
        telegram_update_id: int,
    ) -> bool:
        _ = (command_bucket, telegram_update_id)
        return True
