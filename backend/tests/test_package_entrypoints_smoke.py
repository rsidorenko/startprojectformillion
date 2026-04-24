"""Smoke tests for package entrypoints executed via ``runpy``."""

from __future__ import annotations

import runpy
import sys

import pytest

import app.persistence.postgres_migrations_main as migrations_main_mod
import app.runtime.telegram_httpx_live_main as live_main_mod


def test_runpy_runtime_package_delegates_to_live_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_main() -> None:
        calls.append("called")

    monkeypatch.setattr(live_main_mod, "main", fake_main)
    sys.modules.pop("app.runtime.__main__", None)

    runpy.run_module("app.runtime", run_name="__main__")

    assert calls == ["called"]


def test_runpy_persistence_package_delegates_to_migrations_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_main() -> None:
        calls.append("called")

    monkeypatch.setattr(migrations_main_mod, "main", fake_main)
    sys.modules.pop("app.persistence.__main__", None)

    runpy.run_module("app.persistence", run_name="__main__")

    assert calls == ["called"]
