"""Tests for standalone ADM-01 internal HTTP entry (no real listener, no Postgres)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.admin_support.adm01_postgres_subscription_read_adapter import (
    Adm01PostgresSubscriptionReadAdapter,
)
from app.internal_admin import adm01_http_main as main_mod
from app.security.config import RuntimeConfig


class _FakePool:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def _runtime_with_dsn() -> RuntimeConfig:
    return RuntimeConfig(
        bot_token="x" * 12,
        database_url="postgresql://localhost/testdb",
        app_env="development",
        debug_safe=False,
    )


@pytest.mark.asyncio
async def test_disabled_by_default_returns_zero_no_side_effects(monkeypatch, capsys) -> None:
    monkeypatch.delenv("ADM01_INTERNAL_HTTP_ENABLE", raising=False)
    monkeypatch.delenv("ADM01_INTERNAL_HTTP_ALLOWLIST", raising=False)

    def boom_runtime() -> RuntimeConfig:
        raise AssertionError("load_runtime_config must not be called when ADM-01 HTTP disabled")

    monkeypatch.setattr(main_mod, "load_runtime_config", boom_runtime)

    r = await main_mod.async_run_adm01_internal_http_from_env(load_runtime=boom_runtime)
    assert r == 0
    out, err = capsys.readouterr()
    assert out.strip() == main_mod._STDOUT_DISABLED
    assert err == ""


@pytest.mark.asyncio
async def test_config_error_invalid_boolean_no_secret_echo(monkeypatch, capsys) -> None:
    secret = "SECRET_VALUE_XYZ_992"
    monkeypatch.setenv("ADM01_INTERNAL_HTTP_ENABLE", secret)

    r = await main_mod.async_run_adm01_internal_http_from_env()
    assert r == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert err.strip() == main_mod._STDERR_CONFIG
    assert secret not in err
    assert secret not in out


@pytest.mark.asyncio
async def test_enabled_happy_path_order_and_pool_closed(monkeypatch, capsys) -> None:
    monkeypatch.setenv("ADM01_INTERNAL_HTTP_ENABLE", "1")
    monkeypatch.setenv("ADM01_INTERNAL_HTTP_ALLOWLIST", " adm-principal-a , adm-principal-b ")
    monkeypatch.setenv("BOT_TOKEN", "y" * 15)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/testdb")

    calls: list[str] = []
    fake = _FakePool()
    asgi_app = MagicMock(name="asgi_app")

    async def track_migrations(rt: RuntimeConfig) -> None:
        calls.append("migrations")

    async def track_pool(dsn: str) -> object:
        calls.append(f"pool:{dsn}")
        return fake

    uv_calls: list[tuple[str, int]] = []

    async def track_uvicorn(app: object, *, host: str, port: int) -> None:
        uv_calls.append((host, port))
        assert app is asgi_app
        calls.append("uvicorn")

    def track_build(deps: object) -> MagicMock:
        calls.append("build_app")
        assert isinstance(
            deps.subscription,
            Adm01PostgresSubscriptionReadAdapter,
        )
        assert isinstance(deps.entitlement, main_mod._EntitlementReadMinimal)
        assert isinstance(deps.policy, main_mod._PolicyReadMinimal)
        return asgi_app

    r = await main_mod.async_run_adm01_internal_http_from_env(
        apply_migrations=track_migrations,
        create_pool=track_pool,
        build_app=track_build,
        run_uvicorn=track_uvicorn,
    )
    assert r == 0
    assert calls == ["migrations", "pool:postgresql://localhost/testdb", "build_app", "uvicorn"]
    assert uv_calls == [("127.0.0.1", 18081)]
    assert fake.closed is True
    out, err = capsys.readouterr()
    assert out == "" and err == ""


@pytest.mark.asyncio
async def test_startup_failure_after_pool_closes_pool(monkeypatch, capsys) -> None:
    monkeypatch.setenv("ADM01_INTERNAL_HTTP_ENABLE", "1")
    monkeypatch.setenv("ADM01_INTERNAL_HTTP_ALLOWLIST", "p1")
    monkeypatch.setenv("BOT_TOKEN", "z" * 14)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/testdb")

    fake = _FakePool()

    async def ok_migrations(rt: RuntimeConfig) -> None:
        return None

    async def open_pool(dsn: str) -> object:
        return fake

    async def boom_uvicorn(app: object, *, host: str, port: int) -> None:
        raise RuntimeError("simulated uvicorn failure")

    r = await main_mod.async_run_adm01_internal_http_from_env(
        load_runtime=lambda: _runtime_with_dsn(),
        apply_migrations=ok_migrations,
        create_pool=open_pool,
        run_uvicorn=boom_uvicorn,
    )
    assert r == 1
    assert fake.closed is True
    out, err = capsys.readouterr()
    assert out == ""
    assert err.strip() == main_mod._STDERR_FAILED
    assert "simulated" not in err
    assert "Traceback" not in err


@pytest.mark.asyncio
async def test_bind_all_interfaces_without_override_config_error_no_uvicorn(monkeypatch, capsys) -> None:
    monkeypatch.setenv("ADM01_INTERNAL_HTTP_ENABLE", "1")
    monkeypatch.setenv("ADM01_INTERNAL_HTTP_BIND_HOST", "0.0.0.0")
    monkeypatch.setenv("ADM01_INTERNAL_HTTP_ALLOWLIST", "p1")

    async def boom_uvicorn(app: object, *, host: str, port: int) -> None:
        raise AssertionError("uvicorn must not run when bind config is rejected")

    r = await main_mod.async_run_adm01_internal_http_from_env(run_uvicorn=boom_uvicorn)
    assert r == 1
    out, err = capsys.readouterr()
    assert err.strip() == main_mod._STDERR_CONFIG


@pytest.mark.asyncio
async def test_missing_allowlist_when_enabled_config_error(monkeypatch, capsys) -> None:
    monkeypatch.setenv("ADM01_INTERNAL_HTTP_ENABLE", "1")
    monkeypatch.delenv("ADM01_INTERNAL_HTTP_ALLOWLIST", raising=False)
    monkeypatch.setenv("BOT_TOKEN", "a" * 20)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/x")

    async def no_migrations(rt: RuntimeConfig) -> None:
        raise AssertionError("migrations must not run without allowlist")

    async def boom_uvicorn(app: object, *, host: str, port: int) -> None:
        raise AssertionError("uvicorn must not run without allowlist")

    r = await main_mod.async_run_adm01_internal_http_from_env(
        apply_migrations=no_migrations,
        run_uvicorn=boom_uvicorn,
    )
    assert r == 1
    _, err = capsys.readouterr()
    assert err.strip() == main_mod._STDERR_CONFIG


@pytest.mark.asyncio
async def test_output_leak_guard_disabled_path(capsys) -> None:
    await main_mod.async_run_adm01_internal_http_from_env()
    out, err = capsys.readouterr()
    combined = out + err
    for frag in (
        "DATABASE_URL",
        "postgres://",
        "postgresql://",
        "Bearer ",
        "provider_issuance_ref",
        "issue_idempotency_key",
    ):
        assert frag not in combined


@pytest.mark.asyncio
async def test_output_leak_guard_config_error_path(monkeypatch, capsys) -> None:
    monkeypatch.setenv("ADM01_INTERNAL_HTTP_ENABLE", "not-a-bool")

    await main_mod.async_run_adm01_internal_http_from_env()
    combined = capsys.readouterr().out + capsys.readouterr().err
    for frag in (
        "DATABASE_URL",
        "postgres://",
        "postgresql://",
        "Bearer ",
        "provider_issuance_ref",
        "issue_idempotency_key",
    ):
        assert frag not in combined


def test_main_disabled_integration(monkeypatch, capsys) -> None:
    monkeypatch.delenv("ADM01_INTERNAL_HTTP_ENABLE", raising=False)
    assert main_mod.main() == 0
    out, err = capsys.readouterr()
    assert out.strip() == main_mod._STDOUT_DISABLED
    assert err == ""


@pytest.mark.asyncio
async def test_apply_migrations_failure_returns_failed(monkeypatch, capsys) -> None:
    monkeypatch.setenv("ADM01_INTERNAL_HTTP_ENABLE", "1")
    monkeypatch.setenv("ADM01_INTERNAL_HTTP_ALLOWLIST", "p1")
    monkeypatch.setenv("BOT_TOKEN", "b" * 18)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/x")

    async def boom_migrations(rt: RuntimeConfig) -> None:
        raise RuntimeError("migration failure")

    r = await main_mod.async_run_adm01_internal_http_from_env(apply_migrations=boom_migrations)
    assert r == 1
    assert capsys.readouterr().err.strip() == main_mod._STDERR_FAILED


@pytest.mark.asyncio
async def test_build_app_failure_closes_pool(monkeypatch, capsys) -> None:
    monkeypatch.setenv("ADM01_INTERNAL_HTTP_ENABLE", "1")
    monkeypatch.setenv("ADM01_INTERNAL_HTTP_ALLOWLIST", "p1")
    fake = _FakePool()

    async def ok_migrations(rt: RuntimeConfig) -> None:
        return None

    async def open_pool(dsn: str) -> object:
        return fake

    def boom_build(deps: object) -> MagicMock:
        raise RuntimeError("build failure")

    async def boom_uvicorn(app: object, *, host: str, port: int) -> None:
        raise AssertionError("uvicorn must not run if build fails")

    r = await main_mod.async_run_adm01_internal_http_from_env(
        load_runtime=lambda: _runtime_with_dsn(),
        apply_migrations=ok_migrations,
        create_pool=open_pool,
        build_app=boom_build,
        run_uvicorn=boom_uvicorn,
    )
    assert r == 1
    assert fake.closed is True
    assert capsys.readouterr().err.strip() == main_mod._STDERR_FAILED
