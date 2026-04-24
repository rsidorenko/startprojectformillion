"""Regression tests for ADM-01/ADM-02 internal read gate checks (no script subprocess)."""

from __future__ import annotations

import asyncio

import pytest

from app.admin_support.internal_read_gate_checks import run_admin_support_internal_read_gate_checks


def _run(coro):
    return asyncio.run(coro)


def test_internal_read_gate_checks_passes() -> None:
    _run(run_admin_support_internal_read_gate_checks())


@pytest.mark.anyio
async def test_internal_read_gate_checks_passes_anyio() -> None:
    await run_admin_support_internal_read_gate_checks()
