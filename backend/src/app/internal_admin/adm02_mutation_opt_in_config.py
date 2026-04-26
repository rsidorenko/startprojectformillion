"""Env-driven ADM-02 ensure-access mutation opt-in (fail-closed)."""

from __future__ import annotations

import os
from collections.abc import Mapping

from app.security.config import ConfigurationError

_ENV_ENABLE = "ADM02_ENSURE_ACCESS_ENABLE"
_TRUE = frozenset({"1", "true", "yes"})
_FALSE = frozenset(("", "0", "false", "no"))


def load_adm02_ensure_access_opt_in_from_env(env: Mapping[str, str] | None = None) -> bool:
    """Return explicit env opt-in flag for ADM-02 mutating ensure-access."""
    m: Mapping[str, str] = os.environ if env is None else env
    raw = m.get(_ENV_ENABLE)
    if raw is None:
        return False
    normalized = raw.strip().lower()
    if normalized in _TRUE:
        return True
    if normalized in _FALSE:
        return False
    raise ConfigurationError(f"invalid boolean configuration: {_ENV_ENABLE}")


__all__ = ["load_adm02_ensure_access_opt_in_from_env"]
