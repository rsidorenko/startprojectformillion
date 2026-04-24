"""Runnable entrypoint for manual slice-1 postgres migrations from env."""

from __future__ import annotations

import asyncio

from app.persistence.postgres_migrations_runtime import (
    apply_slice1_postgres_migrations_from_runtime_config,
)
from app.security.config import load_runtime_config


async def run_slice1_postgres_migrations_from_env() -> None:
    config = load_runtime_config()
    await apply_slice1_postgres_migrations_from_runtime_config(config)


def main() -> None:
    asyncio.run(run_slice1_postgres_migrations_from_env())


if __name__ == "__main__":
    main()
