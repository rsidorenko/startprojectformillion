"""Run slice-1 retention cleanup entrypoint in dry-run only (child env forced)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _backend_dir() -> Path:
    """Return ``backend`` root (parent of ``scripts``)."""
    return Path(__file__).resolve().parents[1]


def _build_child_env() -> dict[str, str]:
    """Copy process env, validate ``DATABASE_URL``, set dry-run defaults."""
    if not os.environ.get("DATABASE_URL", "").strip():
        raise RuntimeError("DATABASE_URL is required for slice-1 retention dry-run smoke")

    child_env = os.environ.copy()
    child_env["SLICE1_RETENTION_DRY_RUN"] = "1"

    if not child_env.get("BOT_TOKEN", "").strip():
        child_env["BOT_TOKEN"] = "1234567890tok"
    if not child_env.get("SLICE1_RETENTION_TTL_SECONDS", "").strip():
        child_env["SLICE1_RETENTION_TTL_SECONDS"] = "86400"
    if not child_env.get("SLICE1_RETENTION_BATCH_LIMIT", "").strip():
        child_env["SLICE1_RETENTION_BATCH_LIMIT"] = "100"
    if not child_env.get("SLICE1_RETENTION_MAX_ROUNDS", "").strip():
        child_env["SLICE1_RETENTION_MAX_ROUNDS"] = "5"

    return child_env


def main() -> None:
    """Run retention cleanup module once with ``SLICE1_RETENTION_DRY_RUN=1``."""
    child_env = _build_child_env()
    backend_dir = _backend_dir()
    subprocess.run(
        ["python", "-m", "app.persistence.slice1_retention_manual_cleanup_main"],
        cwd=backend_dir,
        env=child_env,
        check=True,
    )


if __name__ == "__main__":
    main()
