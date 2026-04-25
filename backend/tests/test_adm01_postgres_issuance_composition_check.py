"""Unit tests for adm01_postgres_issuance_composition_check (leak guard, opt-in)."""

from __future__ import annotations

import pytest

from app.admin_support.adm01_postgres_issuance_composition_check import (
    adm01_postgres_issuance_composition_check_enabled,
    assert_adm01_composition_http_text_safe,
)


def test_leak_guard_forbidden_substring() -> None:
    with pytest.raises(RuntimeError, match="response text failed leak guard"):
        assert_adm01_composition_http_text_safe('{"x": "postgresql://h"}')


def test_leak_guard_synthetic_marker() -> None:
    secret = "SYNTHETIC_OPAQUE_MARKER_X9Z"
    with pytest.raises(RuntimeError, match="response text failed leak guard"):
        assert_adm01_composition_http_text_safe(f'{{"ok": "{secret}"}}', synthetic_secret_markers=(secret,))


def test_leak_guard_clean_json_ok() -> None:
    assert_adm01_composition_http_text_safe(
        '{"outcome":"success","summary":{"issuance_state":"ok"}}',
        synthetic_secret_markers=("must-not-appear",),
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1", True),
        ("true", True),
        ("yes", True),
        ("0", False),
        ("", False),
    ],
)
def test_enable_flag_parsing(
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
    expected: bool,
) -> None:
    monkeypatch.setenv("ADM01_POSTGRES_ISSUANCE_COMPOSITION_CHECK_ENABLE", raw)
    assert adm01_postgres_issuance_composition_check_enabled() is expected
