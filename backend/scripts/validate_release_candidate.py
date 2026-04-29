"""Blocking release-candidate validator for customer-facing launch readiness."""

from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
import os
from pathlib import Path

_MUTATING_TESTS_GUARD_ENV = "SLICE1_POSTGRES_MVP_SMOKE_ALLOW_MUTATING_TESTS"


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _required_env_markers() -> tuple[str, ...]:
    return (
        "BOT_TOKEN",
        "DATABASE_URL",
        "TELEGRAM_STOREFRONT_CHECKOUT_URL",
        "TELEGRAM_STOREFRONT_SUPPORT_URL_OR_HANDLE_OR_FALLBACK_ACK",
        "TELEGRAM_STOREFRONT_PLAN_NAME_OR_FALLBACK_ACK",
        "TELEGRAM_STOREFRONT_PLAN_PRICE_OR_FALLBACK_ACK",
        "PAYMENT_FULFILLMENT_HTTP_ENABLE=1",
        "PAYMENT_FULFILLMENT_WEBHOOK_SECRET",
        "TELEGRAM_CHECKOUT_REFERENCE_SECRET",
        "TELEGRAM_CHECKOUT_REFERENCE_MAX_AGE_SECONDS_OR_DEFAULT_TTL_ACK",
        "SUBSCRIPTION_DEFAULT_PERIOD_DAYS",
        "TELEGRAM_ACCESS_RESEND_ENABLE=1",
        "ACCESS_RECONCILE_SCHEDULE_ACK=1",
        "ACCESS_RECONCILE_MAX_INTERVAL_SECONDS",
        "TELEGRAM_WEBHOOK_PUBLIC_URL_IF_WEBHOOK_MODE_ENABLED",
        "TELEGRAM_WEBHOOK_SECRET_TOKEN_IF_WEBHOOK_MODE_ENABLED",
    )


def _release_candidate_checks() -> tuple[tuple[str, tuple[str, ...]], ...]:
    return (
        (
            "migration_readiness_contract",
            ("python", "scripts/run_mvp_release_preflight.py"),
        ),
        (
            "strict_launch_preflight",
            ("python", "scripts/check_launch_readiness.py", "--strict"),
        ),
        (
            "telegram_webhook_config_dry_run",
            ("python", "scripts/configure_telegram_webhook.py", "--dry-run"),
        ),
        (
            "canonical_postgres_mvp_smoke",
            ("python", "scripts/run_postgres_mvp_smoke.py"),
        ),
        (
            "reconcile_health_check",
            ("python", "scripts/check_reconcile_health.py"),
        ),
    )


def _build_child_env(env: Mapping[str, str]) -> dict[str, str]:
    child_env = {str(key): str(value) for key, value in env.items()}
    child_env.setdefault(_MUTATING_TESTS_GUARD_ENV, "1")
    return child_env


def _run_check(
    *,
    check_name: str,
    command: Sequence[str],
    child_env: Mapping[str, str],
    backend_dir: Path,
) -> bool:
    completed = subprocess.run(
        list(command),
        cwd=backend_dir,
        env=dict(child_env),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode == 0:
        print(f"check={check_name} status=pass")
        return True
    print(f"check={check_name} status=fail")
    return False


def run_release_candidate_validation(*, env: Mapping[str, str]) -> int:
    print("release_candidate_validation: start")
    for marker in _required_env_markers():
        print(f"required_env={marker}")

    child_env = _build_child_env(env)
    backend_dir = _backend_dir()
    for check_name, command in _release_candidate_checks():
        if not _run_check(
            check_name=check_name,
            command=command,
            child_env=child_env,
            backend_dir=backend_dir,
        ):
            print("release_candidate_validation: failed")
            return 1

    print("release_candidate_validation: ok")
    return 0


def main() -> int:
    return run_release_candidate_validation(env=dict(os.environ))


if __name__ == "__main__":
    raise SystemExit(main())
