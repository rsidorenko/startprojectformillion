"""Pure tests: UC-01 idempotency key construction."""

import pytest

from app.security.idempotency import build_bootstrap_idempotency_key
from app.security.validation import ValidationError


def test_deterministic_key() -> None:
    a = build_bootstrap_idempotency_key(42, 100)
    b = build_bootstrap_idempotency_key(42, 100)
    assert a == b
    assert len(a) == 64


def test_different_inputs_differ() -> None:
    assert build_bootstrap_idempotency_key(42, 100) != build_bootstrap_idempotency_key(42, 101)


def test_invalid_user_rejected() -> None:
    with pytest.raises(ValidationError):
        build_bootstrap_idempotency_key(0, 1)


def test_update_id_zero_rejected() -> None:
    with pytest.raises(ValidationError):
        build_bootstrap_idempotency_key(1, 0)
