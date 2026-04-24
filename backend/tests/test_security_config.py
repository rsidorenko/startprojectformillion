"""Narrow tests for :func:`load_runtime_config` (no real services)."""

from __future__ import annotations

import pytest

from app.security.config import (
    ConfigurationError,
    RuntimeConfig,
    load_runtime_config,
    validate_runtime_config,
)


def test_validate_runtime_config_rejects_production_postgres_without_sslmode() -> None:
    cfg = RuntimeConfig(
        bot_token="1234567890tok",
        database_url="postgresql://db.example.internal/app",
        app_env="production",
        debug_safe=False,
    )
    with pytest.raises(ConfigurationError, match="DATABASE_URL"):
        validate_runtime_config(cfg)


def test_validate_runtime_config_accepts_production_postgres_with_sslmode_require() -> None:
    cfg = RuntimeConfig(
        bot_token="1234567890tok",
        database_url="postgresql://db.example.internal/app?sslmode=require",
        app_env="production",
        debug_safe=False,
    )
    validate_runtime_config(cfg)


def test_load_runtime_config_allows_missing_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "1234567890tok")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    cfg = load_runtime_config()
    assert cfg.database_url is None
    assert cfg.bot_token == "1234567890tok"


def test_load_runtime_config_treats_blank_database_url_as_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "1234567890tok")
    monkeypatch.setenv("DATABASE_URL", "   ")
    cfg = load_runtime_config()
    assert cfg.database_url is None


def test_load_runtime_config_rejects_non_postgres_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "1234567890tok")
    monkeypatch.setenv("DATABASE_URL", "mysql://localhost/db")
    with pytest.raises(ConfigurationError, match="DATABASE_URL"):
        load_runtime_config()


def test_load_runtime_config_rejects_non_local_postgres_database_url_without_sslmode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BOT_TOKEN", "1234567890tok")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://db.example.internal/app")
    with pytest.raises(ConfigurationError, match="DATABASE_URL"):
        load_runtime_config()


def test_load_runtime_config_accepts_non_local_postgres_database_url_with_sslmode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BOT_TOKEN", "1234567890tok")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://db.example.internal/app?sslmode=require")
    cfg = load_runtime_config()
    assert cfg.database_url is not None


@pytest.mark.parametrize("env_value", ["local", "dev", "development", "test"])
def test_load_runtime_config_allows_local_dev_test_postgres_database_url_without_sslmode(
    monkeypatch: pytest.MonkeyPatch,
    env_value: str,
) -> None:
    monkeypatch.setenv("BOT_TOKEN", "1234567890tok")
    monkeypatch.setenv("APP_ENV", env_value)
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/testdb")
    cfg = load_runtime_config()
    assert cfg.database_url is not None
