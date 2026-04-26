"""ADM-01 / ADM-02 authorization: fail-closed exact-match principal allowlists (no transport/config)."""

from __future__ import annotations

from collections.abc import Iterable

from app.admin_support.contracts import AdminActorRef


class AllowlistAdm01Authorization:
    """`Adm01AuthorizationPort` implementation: membership in a fixed allowlist only."""

    __slots__ = ("_allowed_ids",)

    def __init__(self, admin_principal_ids: Iterable[str]) -> None:
        self._allowed_ids = frozenset(admin_principal_ids)

    async def check_adm01_lookup_allowed(
        self,
        actor: AdminActorRef,
        *,
        correlation_id: str,
    ) -> bool:
        return actor.internal_admin_principal_id in self._allowed_ids


class AllowlistAdm02Authorization:
    """`Adm02AuthorizationPort` implementation: membership in a fixed allowlist only."""

    __slots__ = ("_allowed_ids",)

    def __init__(self, admin_principal_ids: Iterable[str]) -> None:
        self._allowed_ids = frozenset(admin_principal_ids)

    async def check_adm02_diagnostics_allowed(
        self,
        actor: AdminActorRef,
        *,
        correlation_id: str,
    ) -> bool:
        return actor.internal_admin_principal_id in self._allowed_ids

    async def check_adm02_ensure_access_allowed(
        self,
        actor: AdminActorRef,
        *,
        correlation_id: str,
    ) -> bool:
        return actor.internal_admin_principal_id in self._allowed_ids
