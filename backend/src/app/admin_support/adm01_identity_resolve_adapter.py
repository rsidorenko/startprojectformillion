"""ADM-01 identity resolve adapter backed by user identity repository."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.admin_support.contracts import Adm01IdentityResolvePort, InternalUserTarget, TelegramUserTarget


@runtime_checkable
class _UserIdentityReader(Protocol):
    async def find_by_telegram_user_id(self, telegram_user_id: int): ...


class Adm01IdentityResolveAdapter(Adm01IdentityResolvePort):
    """Resolve allowlisted ADM-01 lookup target to internal user id."""

    def __init__(self, identities: _UserIdentityReader) -> None:
        self._identities = identities

    async def resolve_internal_user_id(self, target, *, correlation_id: str) -> str | None:
        del correlation_id
        if isinstance(target, InternalUserTarget):
            return target.internal_user_id
        if isinstance(target, TelegramUserTarget):
            rec = await self._identities.find_by_telegram_user_id(target.telegram_user_id)
            if rec is None:
                return None
            return rec.internal_user_id
        return None
