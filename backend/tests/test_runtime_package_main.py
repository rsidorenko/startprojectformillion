"""Tests for package-level runtime entrypoint."""

from __future__ import annotations

import runpy
import sys

import pytest

import app.runtime.__main__ as runtime_package_main
import app.runtime.telegram_httpx_live_main as live_main_mod


def test_package_main_delegates_to_live_entrypoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_live_main() -> None:
        calls.append("called")

    monkeypatch.setattr(runtime_package_main, "_live_runtime_main", fake_live_main)

    runtime_package_main.main()

    assert calls == ["called"]


def test_running_runtime_package_as_main_uses_same_delegate_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_live_main() -> None:
        calls.append("called")

    monkeypatch.setattr(live_main_mod, "main", fake_live_main)
    sys.modules.pop("app.runtime.__main__", None)

    runpy.run_module("app.runtime.__main__", run_name="__main__")

    assert calls == ["called"]
