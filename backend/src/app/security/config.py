"""Runtime configuration loaded from environment (secrets are never logged here)."""

from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Slice-1 runtime configuration (single boundary for secrets and service settings)."""

    bot_token: str
    database_url: str | None
    app_env: str
    debug_safe: bool


def _require_non_empty(name: str) -> str:
    raw = os.environ.get(name, "").strip()
    if not raw:
        raise ConfigurationError(f"missing or empty configuration: {name}")
    return raw


def _is_local_env(app_env: str) -> bool:
    return app_env.strip().lower() in {"development", "dev", "local", "test"}


def _has_explicit_sslmode(database_url: str) -> bool:
    return "sslmode=" in database_url.lower()


def validate_runtime_config(config: RuntimeConfig) -> None:
    """
    Validate an already-assembled :class:`RuntimeConfig` (no env reads).

    Applies the same rules as :func:`load_runtime_config` for token, DSN shape,
    and non-local PostgreSQL ``sslmode`` policy. Never logs raw DSN values.
    """
    if len(config.bot_token) < 10:
        raise ConfigurationError("invalid configuration: BOT_TOKEN")

    database_url = config.database_url
    if database_url and database_url.strip():
        if not database_url.startswith(("postgresql://", "postgres://")):
            raise ConfigurationError("invalid configuration: DATABASE_URL")
        if not _is_local_env(config.app_env) and not _has_explicit_sslmode(database_url):
            raise ConfigurationError("invalid configuration: DATABASE_URL")


def load_runtime_config() -> RuntimeConfig:
    """
    Load configuration from the process environment.

    Never logs values. On failure raises ConfigurationError with field names only.
    """
    bot_token = _require_non_empty("BOT_TOKEN")

    app_env = os.environ.get("APP_ENV", "development").strip() or "development"
    database_raw = os.environ.get("DATABASE_URL", "").strip()
    database_url: str | None = database_raw if database_raw else None

    debug_raw = os.environ.get("DEBUG", "").strip().lower()
    debug_safe = debug_raw in ("1", "true", "yes")

    config = RuntimeConfig(
        bot_token=bot_token,
        database_url=database_url,
        app_env=app_env,
        debug_safe=debug_safe,
    )
    validate_runtime_config(config)
    return config
