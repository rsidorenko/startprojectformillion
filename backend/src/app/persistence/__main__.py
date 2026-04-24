"""Package entrypoint for running postgres migrations via ``python -m``."""

from __future__ import annotations

from app.persistence.postgres_migrations_main import main as _postgres_migrations_main


def main() -> None:
    _postgres_migrations_main()


if __name__ == "__main__":
    main()
