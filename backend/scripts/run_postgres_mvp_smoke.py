"""Minimal helper to smoke-check PostgreSQL MVP happy-path."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


_MUTATING_TESTS_GUARD_ENV = "SLICE1_POSTGRES_MVP_SMOKE_ALLOW_MUTATING_TESTS"
_TRUTHY_ENV_VALUES = {"1", "true", "yes"}


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _is_env_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in _TRUTHY_ENV_VALUES


def _require_mutating_tests_opt_in() -> None:
    if _is_env_truthy(os.environ.get(_MUTATING_TESTS_GUARD_ENV)):
        return
    raise RuntimeError(
        f"{_MUTATING_TESTS_GUARD_ENV} must be explicitly set for isolated/dev DB smoke runs"
    )


def _build_child_env() -> dict[str, str]:
    raw_database_url = os.environ.get("DATABASE_URL", "").strip()
    if not raw_database_url:
        raise RuntimeError("DATABASE_URL is required for PostgreSQL MVP smoke run")

    child_env = os.environ.copy()
    child_env["SLICE1_USE_POSTGRES_REPOS"] = "1"
    child_env["BILLING_NORMALIZED_INGEST_ENABLE"] = "1"
    child_env["BILLING_SUBSCRIPTION_APPLY_ENABLE"] = "1"
    child_env["ISSUANCE_OPERATOR_ENABLE"] = "1"
    child_env["TELEGRAM_ACCESS_RESEND_ENABLE"] = "1"
    child_env["ADM02_ENSURE_ACCESS_ENABLE"] = "1"
    if not child_env.get("BOT_TOKEN"):
        child_env["BOT_TOKEN"] = "1234567890tok"
    return child_env


def _operator_billing_subprocess_env(full_child_env: dict[str, str]) -> dict[str, str]:
    """Minimal env for ``check_operator_billing_ingest_apply_e2e`` (matches advisory CI wiring).

    That script only needs ``DATABASE_URL`` plus billing ingest/apply opt-ins; passing
    issuance/ADM-02/Telegram/slice-1 flags is unnecessary and can perturb config-dependent paths.
    """
    passthrough = (
        "PATH",
        "HOME",
        "LANG",
        "LC_ALL",
        "PYTHONUTF8",
        "PYTHONIOENCODING",
        "PYTHONNOUSERSITE",
        "PYTHONPATH",
        "PYTHONHOME",
        "TERM",
        "SSL_CERT_FILE",
        "REQUESTS_CA_BUNDLE",
        "PIP_NO_INPUT",
        "SYSTEMROOT",
        "COMSPEC",
        "PATHEXT",
        "TMPDIR",
        "TEMP",
        "TMP",
    )
    out: dict[str, str] = {}
    for key in passthrough:
        val = full_child_env.get(key) or os.environ.get(key)
        if val:
            out[key] = str(val)
    out["DATABASE_URL"] = str(full_child_env["DATABASE_URL"])
    out["BILLING_NORMALIZED_INGEST_ENABLE"] = "1"
    out["BILLING_SUBSCRIPTION_APPLY_ENABLE"] = "1"
    return out


def main() -> None:
    _require_mutating_tests_opt_in()
    child_env = _build_child_env()
    backend_dir = _backend_dir()

    subprocess.run(
        ["python", "-m", "app.persistence"],
        cwd=backend_dir,
        env=child_env,
        check=True,
    )
    subprocess.run(
        ["python", "scripts/run_slice1_retention_dry_run.py"],
        cwd=backend_dir,
        env=child_env,
        check=True,
    )
    subprocess.run(
        ["python", "scripts/check_operator_billing_ingest_apply_e2e.py"],
        cwd=backend_dir,
        env=_operator_billing_subprocess_env(child_env),
        check=True,
    )
    subprocess.run(
        ["python", "scripts/check_postgres_mvp_access_fulfillment_e2e.py"],
        cwd=backend_dir,
        env=child_env,
        check=True,
    )
    subprocess.run(
        [
            "pytest",
            "-q",
            "tests/test_postgres_slice1_process_env_async.py",
            "tests/test_postgres_migration_ledger_integration.py",
        ],
        cwd=backend_dir,
        env=child_env,
        check=True,
    )


if __name__ == "__main__":
    main()
