"""Package entrypoint for running the live runtime via ``python -m``."""

from __future__ import annotations

from app.runtime.telegram_httpx_live_main import main as _live_runtime_main


def main() -> None:
    _live_runtime_main()


if __name__ == "__main__":
    main()
