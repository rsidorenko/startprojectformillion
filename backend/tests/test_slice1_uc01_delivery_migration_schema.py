"""Static checks on UC-01 outbound delivery migration (no sensitive columns)."""

from __future__ import annotations

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
_MIGRATION = BACKEND_ROOT / "migrations" / "006_slice1_uc01_outbound_deliveries.sql"


def test_uc01_delivery_migration_has_no_message_or_raw_payload_columns() -> None:
    text = _MIGRATION.read_text(encoding="utf-8").lower()
    for forbidden in (
        "message_text",
        "correlation_id",
        "bot_token",
        "dsn",
        "database_url",
    ):
        assert forbidden not in text, f"unexpected token in migration SQL: {forbidden!r}"
