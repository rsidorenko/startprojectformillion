"""Telegram Bot API HTTP webhook ingress (secret-gated; no SDK; no raw secrets in responses)."""

from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.runtime.raw_polling import Slice1RawPollingRuntime
from app.runtime.telegram_webhook_ingress_telemetry import (
    NoopTelegramWebhookIngressTelemetry,
    TelegramWebhookIngressDecisionEvent,
    TelegramWebhookIngressTelemetry,
)
from app.security.config import ConfigurationError

# Telegram Bot API: https://core.telegram.org/bots/api#setwebhook
TELEGRAM_WEBHOOK_SECRET_HEADER = "x-telegram-bot-api-secret-token"
ENV_TELEGRAM_WEBHOOK_HTTP_ENABLE = "TELEGRAM_WEBHOOK_HTTP_ENABLE"
ENV_TELEGRAM_WEBHOOK_SECRET_TOKEN = "TELEGRAM_WEBHOOK_SECRET_TOKEN"
ENV_TELEGRAM_WEBHOOK_ALLOW_INSECURE_LOCAL = "TELEGRAM_WEBHOOK_ALLOW_INSECURE_LOCAL"


def _truthy_env(raw: str | None) -> bool:
    if raw is None:
        return False
    return raw.strip().lower() in ("1", "true", "yes")


def _is_local_app_env(app_env: str) -> bool:
    return app_env.strip().lower() in {"development", "dev", "local", "test"}


def _webhook_secret_header_ok(incoming: str, expected: str) -> bool:
    if not incoming:
        return False
    return secrets.compare_digest(incoming, expected)


@dataclass(frozen=True, slots=True)
class TelegramWebhookIngressSettings:
    """Ingress policy for the HTTP webhook route."""

    expected_secret: str | None
    http_path: str = "/telegram/webhook"


def load_telegram_webhook_ingress_settings_from_env(*, app_env: str) -> TelegramWebhookIngressSettings | None:
    """
    Load webhook ingress settings from the process environment.

    When ``TELEGRAM_WEBHOOK_HTTP_ENABLE`` is falsey, returns ``None`` (no HTTP webhook app).
    In local/test ``APP_ENV`` buckets, a missing ``TELEGRAM_WEBHOOK_SECRET_TOKEN`` is allowed
    only when ``TELEGRAM_WEBHOOK_ALLOW_INSECURE_LOCAL`` is truthy (explicit test-only opt-in).
    In production-like ``APP_ENV``, a configured non-empty ``TELEGRAM_WEBHOOK_SECRET_TOKEN`` is
    required whenever webhook HTTP is enabled (fail-closed).
    """
    if not _truthy_env(os.environ.get(ENV_TELEGRAM_WEBHOOK_HTTP_ENABLE)):
        return None
    secret_raw = os.environ.get(ENV_TELEGRAM_WEBHOOK_SECRET_TOKEN, "").strip()
    if _is_local_app_env(app_env):
        if not secret_raw and not _truthy_env(os.environ.get(ENV_TELEGRAM_WEBHOOK_ALLOW_INSECURE_LOCAL)):
            raise ConfigurationError(
                "invalid configuration: "
                f"{ENV_TELEGRAM_WEBHOOK_ALLOW_INSECURE_LOCAL}"
            )
        return TelegramWebhookIngressSettings(expected_secret=secret_raw or None)
    if not secret_raw:
        raise ConfigurationError(f"missing or empty configuration: {ENV_TELEGRAM_WEBHOOK_SECRET_TOKEN}")
    return TelegramWebhookIngressSettings(expected_secret=secret_raw)


def _reject_unauthorized() -> JSONResponse:
    return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)


async def _emit_decision_best_effort(
    telemetry: TelegramWebhookIngressTelemetry,
    event: TelegramWebhookIngressDecisionEvent,
) -> None:
    try:
        await telemetry.emit_decision(event)
    except Exception:
        return


def create_slice1_telegram_webhook_starlette_app(
    runtime: Slice1RawPollingRuntime,
    *,
    settings: TelegramWebhookIngressSettings,
    telemetry: TelegramWebhookIngressTelemetry | None = None,
) -> Starlette:
    """Starlette app with a single POST webhook route wired to ``runtime``."""
    ingress_telemetry = telemetry or NoopTelegramWebhookIngressTelemetry()

    async def telegram_webhook(request: Request) -> JSONResponse:
        expected = settings.expected_secret
        if expected is not None:
            incoming = request.headers.get(TELEGRAM_WEBHOOK_SECRET_HEADER, "").strip()
            if not incoming:
                await _emit_decision_best_effort(
                    ingress_telemetry,
                    TelegramWebhookIngressDecisionEvent(
                        event_type="telegram_webhook_ingress_decision",
                        decision="unauthorized",
                        reason_bucket="missing_secret_header",
                        path_bucket="telegram_webhook",
                        principal_marker="telegram_webhook_redacted",
                    ),
                )
                return _reject_unauthorized()
            if not _webhook_secret_header_ok(incoming, expected):
                await _emit_decision_best_effort(
                    ingress_telemetry,
                    TelegramWebhookIngressDecisionEvent(
                        event_type="telegram_webhook_ingress_decision",
                        decision="unauthorized",
                        reason_bucket="invalid_secret_header",
                        path_bucket="telegram_webhook",
                        principal_marker="telegram_webhook_redacted",
                    ),
                )
                return _reject_unauthorized()

        raw = await request.body()
        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            await _emit_decision_best_effort(
                ingress_telemetry,
                TelegramWebhookIngressDecisionEvent(
                    event_type="telegram_webhook_ingress_decision",
                    decision="invalid_json",
                    reason_bucket="invalid_json",
                    path_bucket="telegram_webhook",
                    principal_marker="telegram_webhook_redacted",
                ),
            )
            return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)
        if not isinstance(data, dict):
            await _emit_decision_best_effort(
                ingress_telemetry,
                TelegramWebhookIngressDecisionEvent(
                    event_type="telegram_webhook_ingress_decision",
                    decision="invalid_json",
                    reason_bucket="invalid_json",
                    path_bucket="telegram_webhook",
                    principal_marker="telegram_webhook_redacted",
                ),
            )
            return JSONResponse({"ok": False, "error": "invalid_body"}, status_code=400)

        await _emit_decision_best_effort(
            ingress_telemetry,
            TelegramWebhookIngressDecisionEvent(
                event_type="telegram_webhook_ingress_decision",
                decision="accepted",
                reason_bucket="valid_secret",
                path_bucket="telegram_webhook",
                principal_marker="telegram_webhook_redacted",
            ),
        )
        await runtime.process_single_mapped_update(data, correlation_id=None)
        return JSONResponse({"ok": True})

    return Starlette(
        routes=[
            Route(settings.http_path, telegram_webhook, methods=["POST"]),
        ],
    )
