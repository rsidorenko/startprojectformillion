"""Thin slice-1 runtime facade: raw Telegram-like update → rendered message package (no SDK, no server).

Orchestrates existing adapter → service/dispatch → outbound keys → message catalog render.
Raw updates do not cross the adapter boundary; this module does not accept Telegram SDK types.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.application.bootstrap import Slice1Composition
from app.bot_transport.message_catalog import RenderedMessagePackage, render_telegram_outbound_plan
from app.bot_transport.outbound import map_transport_safe_to_outbound_plan
from app.bot_transport.service import handle_slice1_telegram_update


async def handle_slice1_telegram_update_to_rendered_message(
    update: Mapping[str, Any],
    composition: Slice1Composition,
    *,
    correlation_id: str | None = None,
) -> RenderedMessagePackage:
    """
    Full slice-1 pipeline to user-facing copy: extract → dispatch → outbound plan → catalog render.

    Adapter rejection and handler-level safe errors yield a stable :class:`RenderedMessagePackage`
    (no exceptions for expected failure classes).
    """
    transport = await handle_slice1_telegram_update(
        update,
        composition,
        correlation_id=correlation_id,
    )
    plan = map_transport_safe_to_outbound_plan(transport)
    return render_telegram_outbound_plan(plan)


class Slice1TelegramRuntimeFacade:
    """Callable wrapper for :func:`handle_slice1_telegram_update_to_rendered_message`."""

    __slots__ = ()

    async def handle_update_to_rendered_message(
        self,
        update: Mapping[str, Any],
        composition: Slice1Composition,
        *,
        correlation_id: str | None = None,
    ) -> RenderedMessagePackage:
        return await handle_slice1_telegram_update_to_rendered_message(
            update,
            composition,
            correlation_id=correlation_id,
        )
