"""Reconcile durable issuance state for expired subscriptions (idempotent, no secret output)."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime

import asyncpg

from app.persistence.postgres_issuance_state import PostgresIssuanceStateRepository

_STDOUT_OK = "expired_access_reconcile: ok"
_STDERR_FAILED = "expired_access_reconcile: failed"
_TASK_NAME = "expired_access_reconcile"

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


class ReconcileRunFailed(RuntimeError):
    def __init__(self, *, heartbeat_recorded: bool) -> None:
        super().__init__("reconcile run failed")
        self.heartbeat_recorded = heartbeat_recorded


def _assert_safe_output(line: str) -> None:
    upper = line.upper()
    for frag in _FORBIDDEN:
        if frag.upper() in upper:
            raise RuntimeError("reconcile output leak guard failed")


def _print_stdout_safe(line: str) -> None:
    _assert_safe_output(line)
    print(line, flush=True)


def _print_stderr_safe(line: str) -> None:
    _assert_safe_output(line)
    print(line, file=sys.stderr, flush=True)


def _required_database_url() -> str:
    dsn = os.environ.get("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("missing database dsn")
    return dsn


def _safe_error_markers(exc: Exception) -> tuple[str, str]:
    error_class = exc.__class__.__name__.strip() or "UnknownError"
    safe_message = "reconcile_run_failed"
    return error_class, safe_message


async def run_reconcile_expired_access() -> tuple[int, bool]:
    dsn = _required_database_url()
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    heartbeat_recorded = False
    try:
        repo = PostgresIssuanceStateRepository(pool)
        run_id = str(uuid.uuid4())
        started_at = datetime.now(UTC)
        await repo.record_access_reconcile_started(
            run_id=run_id,
            task_name=_TASK_NAME,
            started_at=started_at,
        )
        heartbeat_recorded = True
        try:
            reconciled_rows = await repo.reconcile_expired_active_subscriptions(now_utc=datetime.now(UTC))
        except Exception as exc:
            safe_error_class, safe_error_message = _safe_error_markers(exc)
            try:
                await repo.record_access_reconcile_failed(
                    run_id=run_id,
                    task_name=_TASK_NAME,
                    finished_at=datetime.now(UTC),
                    safe_error_class=safe_error_class,
                    safe_error_message=safe_error_message,
                )
                heartbeat_recorded = True
            except Exception:
                heartbeat_recorded = False
            raise ReconcileRunFailed(heartbeat_recorded=heartbeat_recorded) from exc
        await repo.record_access_reconcile_completed(
            run_id=run_id,
            task_name=_TASK_NAME,
            finished_at=datetime.now(UTC),
            reconciled_rows=reconciled_rows,
        )
        heartbeat_recorded = True
        return reconciled_rows, heartbeat_recorded
    finally:
        await pool.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    heartbeat_recorded = False
    try:
        updated, heartbeat_recorded = asyncio.run(run_reconcile_expired_access())
    except ReconcileRunFailed as exc:
        _print_stderr_safe(_STDERR_FAILED)
        _print_stderr_safe(f"heartbeat_recorded={'yes' if exc.heartbeat_recorded else 'no'}")
        return 1
    except Exception:
        _print_stderr_safe(_STDERR_FAILED)
        _print_stderr_safe(f"heartbeat_recorded={'yes' if heartbeat_recorded else 'no'}")
        return 1
    _print_stdout_safe(_STDOUT_OK)
    _print_stdout_safe(f"reconciled_rows={updated}")
    _print_stdout_safe(f"heartbeat_recorded={'yes' if heartbeat_recorded else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
