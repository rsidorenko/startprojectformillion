"""Pure tests: structured logging redaction / allowlist."""

from app.observability.logging_policy import ALLOWED_LOG_FIELDS, sanitize_structured_fields


def test_unknown_keys_dropped() -> None:
    out = sanitize_structured_fields(
        {
            "correlation_id": "a" * 32,
            "message_text": "secret",
            "token": "x",
        }
    )
    assert "message_text" not in out
    assert "token" not in out


def test_correlation_id_validated() -> None:
    good = "a" * 32
    assert sanitize_structured_fields({"correlation_id": good})["correlation_id"] == good
    assert sanitize_structured_fields({"correlation_id": "bad"})["correlation_id"] == "[INVALID]"


def test_non_primitive_redacted() -> None:
    out = sanitize_structured_fields({"intent": {"nested": 1}})
    assert out.get("intent") == "[REDACTED]"


def test_allowlist_is_low_cardinality() -> None:
    assert "user_id" not in ALLOWED_LOG_FIELDS
    assert "chat_id" not in ALLOWED_LOG_FIELDS
