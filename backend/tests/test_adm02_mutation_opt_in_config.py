"""Tests for ADM-02 runtime mutation opt-in env loader."""

from __future__ import annotations

import pytest

from app.internal_admin.adm02_mutation_opt_in_config import load_adm02_ensure_access_opt_in_from_env
from app.security.config import ConfigurationError


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, False),
        ("", False),
        ("0", False),
        ("false", False),
        ("no", False),
        ("1", True),
        ("true", True),
        ("yes", True),
        (" YES ", True),
    ],
)
def test_load_adm02_ensure_access_opt_in_from_env_truthy_convention(raw: str | None, expected: bool) -> None:
    env: dict[str, str] = {}
    if raw is not None:
        env["ADM02_ENSURE_ACCESS_ENABLE"] = raw
    assert load_adm02_ensure_access_opt_in_from_env(env) is expected


def test_load_adm02_ensure_access_opt_in_from_env_invalid_raises_configuration_error() -> None:
    with pytest.raises(ConfigurationError):
        load_adm02_ensure_access_opt_in_from_env({"ADM02_ENSURE_ACCESS_ENABLE": "definitely"})
