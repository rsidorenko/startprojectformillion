"""Tests for package-level persistence migration entrypoint."""

from __future__ import annotations

import runpy
import sys

import pytest

import app.persistence.__main__ as persistence_package_main
import app.persistence.postgres_migrations_main as migrations_main_mod


def test_package_main_delegates_to_migrations_entrypoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_migrations_main() -> None:
        calls.append("called")

    monkeypatch.setattr(
        persistence_package_main,
        "_postgres_migrations_main",
        fake_migrations_main,
    )

    persistence_package_main.main()

    assert calls == ["called"]


def test_running_persistence_package_as_main_uses_same_delegate_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_migrations_main() -> None:
        calls.append("called")

    monkeypatch.setattr(migrations_main_mod, "main", fake_migrations_main)
    sys.modules.pop("app.persistence.__main__", None)

    runpy.run_module("app.persistence.__main__", run_name="__main__")

    assert calls == ["called"]
