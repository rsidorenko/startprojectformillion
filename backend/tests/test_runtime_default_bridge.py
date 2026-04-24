"""Tests for :mod:`app.runtime.default_bridge`."""

from __future__ import annotations

import inspect
from types import MappingProxyType

import app.runtime as rt
from app.runtime.default_bridge import accept_mapping_runtime_update


def test_dict_accepted_as_mapping() -> None:
    d: dict[str, object] = {"a": 1}
    assert accept_mapping_runtime_update(d) is d


def test_non_dict_mapping_accepted() -> None:
    inner = {"k": 1}
    m = MappingProxyType(inner)
    assert accept_mapping_runtime_update(m) is m


def test_non_mapping_returns_none() -> None:
    assert accept_mapping_runtime_update("x") is None
    assert accept_mapping_runtime_update(0) is None
    assert accept_mapping_runtime_update(object()) is None
    assert accept_mapping_runtime_update([]) is None


def test_returns_same_object_no_copy() -> None:
    d: dict[str, object] = {"x": 0}
    out = accept_mapping_runtime_update(d)
    assert out is d


def test_import_from_app_runtime_package() -> None:
    assert rt.accept_mapping_runtime_update is accept_mapping_runtime_update
    assert "accept_mapping_runtime_update" in rt.__all__


def test_default_bridge_source_excludes_forbidden_tokens() -> None:
    import app.runtime.default_bridge as mod

    src = inspect.getsource(mod)
    lower = src.lower()
    for token in ("billing", "issuance", "admin", "webhook", "sdk"):
        assert token not in lower
