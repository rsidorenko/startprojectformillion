"""Shared test-only assertions for retention boundary leak guards."""

from __future__ import annotations

from collections.abc import Iterable

RETENTION_FORBIDDEN_OUTPUT_FRAGMENTS = (
    "postgres://",
    "postgresql://",
    "Bearer ",
    "PRIVATE KEY",
    "TOP_SECRET",
    "SECRET",
    "TOKEN",
)

_DEFAULT_RETENTION_SUMMARY_MARKERS = (
    "slice1_retention_cleanup",
    "slice1_retention_scheduled_cleanup",
)


def assert_no_retention_secret_fragments(text: str) -> None:
    lowered = text.lower()
    for forbidden in RETENTION_FORBIDDEN_OUTPUT_FRAGMENTS:
        assert forbidden.lower() not in lowered


def assert_no_retention_success_summary(
    stdout: str,
    stderr: str = "",
    *,
    markers: Iterable[str] = _DEFAULT_RETENTION_SUMMARY_MARKERS,
) -> None:
    for marker in markers:
        assert marker not in stdout
        assert marker not in stderr


def assert_retention_failure_output_safe(
    *parts: object,
    summary_stdout: str = "",
    summary_stderr: str = "",
    summary_markers: Iterable[str] = _DEFAULT_RETENTION_SUMMARY_MARKERS,
) -> None:
    for part in parts:
        if part is None:
            continue
        assert_no_retention_secret_fragments(str(part))
    assert_no_retention_success_summary(
        summary_stdout,
        summary_stderr,
        markers=summary_markers,
    )
