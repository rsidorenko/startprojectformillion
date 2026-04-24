"""Tests for :mod:`app.runtime.telegram_httpx_raw_env` (no network, no real env reads)."""

from __future__ import annotations

import asyncio
import inspect
from unittest.mock import patch

import httpx

import app.runtime as rt
import app.runtime.telegram_httpx_raw_env as env_mod
from app.runtime.polling import PollingRuntimeConfig
from app.runtime.polling_policy import (
    DEFAULT_POLLING_POLICY,
    NoopBackoffPolicy,
    NoopRetryPolicy,
    NoopTimeoutPolicy,
    PollingPolicy,
)
from app.runtime.telegram_httpx_raw_app import Slice1HttpxRawRuntimeApp
from app.runtime.telegram_httpx_raw_env import build_slice1_httpx_raw_runtime_app_from_env
from app.security.config import RuntimeConfig
from app.shared.correlation import new_correlation_id


def _minimal_runtime_config(*, bot_token: str = "1234567890tok") -> RuntimeConfig:
    return RuntimeConfig(
        bot_token=bot_token,
        database_url="postgresql://localhost/db",
        app_env="development",
        debug_safe=False,
    )


def _start_update(*, update_id: int = 1, user_id: int = 42) -> dict:
    return {
        "update_id": update_id,
        "message": {
            "message_id": 1,
            "from": {"id": user_id, "is_bot": False, "first_name": "U"},
            "chat": {"id": user_id, "type": "private"},
            "text": "/start",
        },
    }


def test_factory_returns_app_and_uses_load_runtime_config() -> None:
    cfg = _minimal_runtime_config()

    async def main() -> None:
        transport = httpx.MockTransport(
            lambda r: httpx.Response(200, json={"ok": True, "result": []}),
        )
        async with httpx.AsyncClient(transport=transport) as ac:
            with patch.object(env_mod, "load_runtime_config", return_value=cfg) as load_mock:
                app = build_slice1_httpx_raw_runtime_app_from_env(client=ac)
            load_mock.assert_called_once_with()
            assert isinstance(app, Slice1HttpxRawRuntimeApp)
            assert isinstance(cfg, RuntimeConfig)
            await app.aclose()

    asyncio.run(main())


def test_default_polling_runtime_config() -> None:
    cfg = _minimal_runtime_config()

    async def main() -> None:
        transport = httpx.MockTransport(
            lambda r: httpx.Response(200, json={"ok": True, "result": []}),
        )
        async with httpx.AsyncClient(transport=transport) as ac:
            with patch.object(env_mod, "load_runtime_config", return_value=cfg):
                app = build_slice1_httpx_raw_runtime_app_from_env(client=ac)
            assert app.bundle.bundle.config == PollingRuntimeConfig()
            await app.aclose()

    asyncio.run(main())


def test_default_polling_policy_passed_through() -> None:
    cfg = _minimal_runtime_config()

    async def main() -> None:
        transport = httpx.MockTransport(
            lambda r: httpx.Response(200, json={"ok": True, "result": []}),
        )
        async with httpx.AsyncClient(transport=transport) as ac:
            with patch.object(env_mod, "load_runtime_config", return_value=cfg):
                app = build_slice1_httpx_raw_runtime_app_from_env(client=ac)
            assert app.bundle.client.polling_policy is DEFAULT_POLLING_POLICY
            await app.aclose()

    asyncio.run(main())


def test_custom_polling_policy_passed_through_by_identity() -> None:
    cfg = _minimal_runtime_config()
    custom = PollingPolicy(
        timeout=NoopTimeoutPolicy(),
        backoff=NoopBackoffPolicy(),
        retry=NoopRetryPolicy(),
    )

    async def main() -> None:
        transport = httpx.MockTransport(
            lambda r: httpx.Response(200, json={"ok": True, "result": []}),
        )
        async with httpx.AsyncClient(transport=transport) as ac:
            with patch.object(env_mod, "load_runtime_config", return_value=cfg):
                app = build_slice1_httpx_raw_runtime_app_from_env(
                    client=ac,
                    polling_policy=custom,
                )
            assert app.bundle.client.polling_policy is custom
            await app.aclose()

    asyncio.run(main())


def test_optional_polling_config_passed_through() -> None:
    cfg = _minimal_runtime_config()
    custom = PollingRuntimeConfig(max_updates_per_batch=7)

    async def main() -> None:
        transport = httpx.MockTransport(
            lambda r: httpx.Response(200, json={"ok": True, "result": []}),
        )
        async with httpx.AsyncClient(transport=transport) as ac:
            with patch.object(env_mod, "load_runtime_config", return_value=cfg):
                app = build_slice1_httpx_raw_runtime_app_from_env(
                    polling_config=custom,
                    client=ac,
                )
            assert app.bundle.bundle.config == custom
            await app.aclose()

    asyncio.run(main())


def test_run_iterations_one_start_one_send() -> None:
    send_posts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal send_posts
        if request.url.path.endswith("/getUpdates"):
            return httpx.Response(200, json={"ok": True, "result": [_start_update()]})
        if request.url.path.endswith("/sendMessage"):
            send_posts += 1
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
        return httpx.Response(404)

    cfg = _minimal_runtime_config()

    async def main() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as ac:
            with patch.object(env_mod, "load_runtime_config", return_value=cfg):
                app = build_slice1_httpx_raw_runtime_app_from_env(client=ac)
            summary = await app.run_iterations(1, correlation_id=new_correlation_id())
            assert summary.send_count == 1
            assert send_posts == 1
            await app.aclose()

    asyncio.run(main())


def test_runtime_package_exports() -> None:
    assert rt.build_slice1_httpx_raw_runtime_app_from_env is build_slice1_httpx_raw_runtime_app_from_env
    assert "build_slice1_httpx_raw_runtime_app_from_env" in rt.__all__


def test_module_source_excludes_forbidden_tokens() -> None:
    src = inspect.getsource(env_mod)
    lower = src.lower()
    for token in ("billing", "issuance", "admin", "webhook"):
        assert token not in lower


def test_module_source_no_manual_env_cli_signal_sleep_backoff() -> None:
    src = inspect.getsource(env_mod)
    lower = src.lower()
    for token in ("environ", "getenv", "dotenv", "argparse", "click", "signal", "sleep", "backoff"):
        assert token not in lower
