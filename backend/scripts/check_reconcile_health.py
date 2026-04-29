"""Read-only health check for expired access reconcile runtime evidence."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime

import asyncpg

from app.persistence.postgres_issuance_state import PostgresIssuanceStateRepository

_TASK_NAME = "expired_access_reconcile"
_ENV_MAX_INTERVAL_SECONDS = "ACCESS_RECONCILE_MAX_INTERVAL_SECONDS"
_FORBIDDEN = (
    "DATABASE_URL",
    "postgres://",
    "postgresql://",
    "Bearer ",
    "PRIVATE KEY",
    "BEGIN ",
    "token=",
    "provider_issuance_ref",
    "internal_user_id",
    "issue_idempotency_key",
)


def _assert_safe_output(line: str) -> None:
    upper = line.upper()
    for frag in _FORBIDDEN:
        if frag.upper() in upper:
            raise RuntimeError("reconcile health output leak guard failed")


def _print_safe(line: str, *, stderr: bool = False) -> None:
    _assert_safe_output(line)
    if stderr:
        print(line, file=sys.stderr, flush=True)
        return
    print(line, flush=True)


def _required_database_url() -> str:
    dsn = os.environ.get("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("missing database dsn")
    return dsn


def _required_max_interval_seconds() -> int:
    raw = os.environ.get(_ENV_MAX_INTERVAL_SECONDS, "").strip()
    if not raw:
        raise RuntimeError("missing max interval marker")
    return int(raw)


async def run_reconcile_health_check(*, max_interval_seconds: int) -> tuple[bool, tuple[str, ...]]:
    dsn = _required_database_url()
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    try:
        repo = PostgresIssuanceStateRepository(pool)
        latest = await repo.fetch_latest_access_reconcile_run(task_name=_TASK_NAME)
    finally:
        await pool.close()

    if latest is None:
        return False, ("issue_code=access_reconcile_heartbeat_missing",)
    started_at, finished_at, status, _, error_class, _ = latest
    age_seconds = max(0, int((datetime.now(UTC) - started_at).total_seconds()))
    markers = (
        f"last_run_status={status}",
        f"last_run_age_seconds={age_seconds}",
        f"max_interval_seconds={max_interval_seconds}",
    )
    if status == "failed":
        safe_error = error_class if error_class else "UnknownError"
        return False, markers + (
            f"last_run_error_class={safe_error}",
            "issue_code=access_reconcile_last_run_failed",
        )
    if status != "completed":
        return False, markers + ("issue_code=access_reconcile_last_run_not_completed",)
    if finished_at is None:
        return False, markers + ("issue_code=access_reconcile_last_run_missing_finished_at",)
    if age_seconds > max_interval_seconds:
        return False, markers + ("issue_code=access_reconcile_heartbeat_stale",)
    return True, markers + ("issue_code=none",)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    try:
        max_interval_seconds = _required_max_interval_seconds()
        ok, markers = asyncio.run(run_reconcile_health_check(max_interval_seconds=max_interval_seconds))
    except Exception:
        _print_safe("reconcile_health_check: failed", stderr=True)
        _print_safe("issue_code=access_reconcile_health_check_runtime_failure", stderr=True)
        return 1
    stream_is_stderr = not ok
    _print_safe(f"reconcile_health_check: {'ok' if ok else 'failed'}", stderr=stream_is_stderr)
    for marker in markers:
        _print_safe(marker, stderr=stream_is_stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
