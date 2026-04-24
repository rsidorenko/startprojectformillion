"""Pure slice-1 runtime wrapper: Telegram-like update mapping → runtime send action (no SDK, no I/O).

Bridges raw updates to :func:`handle_slice1_telegram_update_to_rendered_message`, then applies
send/no-op policy from architecture docs 17/18: eligible private chat target + rendered copy → send;
otherwise no-op. Does not duplicate adapter dispatch, normalization, or application logic.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.application.bootstrap import Slice1Composition
from app.bot_transport.runtime_facade import handle_slice1_telegram_update_to_rendered_message
from app.security.validation import ValidationError, validate_telegram_user_id


class TelegramRuntimeActionKind(str, Enum):
    """Minimal runtime outbound intent for slice 1 (transport-agnostic, no SDK)."""

    SEND_MESSAGE = "send_message"
    NOOP = "noop"


@dataclass(frozen=True, slots=True)
class TelegramRuntimeAction:
    """Single outbound action derived from a rendered package; no raw Telegram payload."""

    kind: TelegramRuntimeActionKind
    correlation_id: str
    chat_id: int | None
    message_text: str | None
    action_keys: tuple[str, ...]
    uc01_idempotency_key: str | None = None


def extract_eligible_private_chat_id_from_telegram_like_update(
    update: Mapping[str, Any],
) -> int | None:
    """
    Fail-closed extraction of an outbound chat id for slice 1.

    Validates only structural/private-chat identity (private ``message.chat``, stable ids,
    ``from.id`` consistent with ``chat.id``). Does not interpret commands or duplicate the
    slice-1 command allowlist; malformed or non-private shapes return ``None``.
    """
    if not isinstance(update, Mapping):
        return None
    message = update.get("message")
    if not isinstance(message, Mapping):
        return None
    chat = message.get("chat")
    if not isinstance(chat, Mapping):
        return None
    if chat.get("type") != "private":
        return None
    from_user = message.get("from")
    if not isinstance(from_user, Mapping):
        return None
    raw_chat_id = chat.get("id")
    raw_user_id = from_user.get("id")
    try:
        chat_id = validate_telegram_user_id(raw_chat_id)
        user_id = validate_telegram_user_id(raw_user_id)
    except (ValidationError, TypeError):
        return None
    if chat_id != user_id:
        return None
    return chat_id


async def handle_slice1_telegram_update_to_runtime_action(
    update: Mapping[str, Any],
    composition: Slice1Composition,
    *,
    correlation_id: str | None = None,
) -> TelegramRuntimeAction:
    """
    Raw Telegram-like update → existing runtime facade → one :class:`TelegramRuntimeAction`.

    Correlation id on the action is always taken from the rendered package (pipeline truth).
    Expected adapter/service paths do not raise; errors are expressed as safe rendered copy.
    """
    rendered = await handle_slice1_telegram_update_to_rendered_message(
        update,
        composition,
        correlation_id=correlation_id,
    )
    cid = rendered.correlation_id
    target = extract_eligible_private_chat_id_from_telegram_like_update(update)
    idem_key = rendered.uc01_idempotency_key
    ledger = composition.outbound_delivery
    if rendered.replay_suppresses_outbound:
        if not idem_key or ledger is None:
            return TelegramRuntimeAction(
                kind=TelegramRuntimeActionKind.NOOP,
                correlation_id=cid,
                chat_id=None,
                message_text=None,
                action_keys=(),
                uc01_idempotency_key=None,
            )
        rec = await ledger.get_status(idem_key)
        if rec is not None and rec.status == "sent" and rec.telegram_message_id is not None:
            return TelegramRuntimeAction(
                kind=TelegramRuntimeActionKind.NOOP,
                correlation_id=cid,
                chat_id=None,
                message_text=None,
                action_keys=(),
                uc01_idempotency_key=None,
            )
        if rec is None or rec.status != "pending":
            return TelegramRuntimeAction(
                kind=TelegramRuntimeActionKind.NOOP,
                correlation_id=cid,
                chat_id=None,
                message_text=None,
                action_keys=(),
                uc01_idempotency_key=None,
            )
    if target is None or not rendered.message_text.strip():
        return TelegramRuntimeAction(
            kind=TelegramRuntimeActionKind.NOOP,
            correlation_id=cid,
            chat_id=None,
            message_text=None,
            action_keys=(),
            uc01_idempotency_key=None,
        )
    return TelegramRuntimeAction(
        kind=TelegramRuntimeActionKind.SEND_MESSAGE,
        correlation_id=cid,
        chat_id=target,
        message_text=rendered.message_text,
        action_keys=rendered.action_keys,
        uc01_idempotency_key=idem_key,
    )


class Slice1TelegramRuntimeWrapper:
    """Holds :class:`Slice1Composition` and delegates to :func:`handle_slice1_telegram_update_to_runtime_action`."""

    __slots__ = ("_composition",)

    def __init__(self, composition: Slice1Composition) -> None:
        self._composition = composition

    async def handle(
        self,
        update: Mapping[str, Any],
        *,
        correlation_id: str | None = None,
    ) -> TelegramRuntimeAction:
        return await handle_slice1_telegram_update_to_runtime_action(
            update,
            self._composition,
            correlation_id=correlation_id,
        )

    async def dispatch(
        self,
        update: Mapping[str, Any],
        *,
        correlation_id: str | None = None,
    ) -> TelegramRuntimeAction:
        return await self.handle(update, correlation_id=correlation_id)
