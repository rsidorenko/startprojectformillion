"""DTOs for persisted issuance *operational* state (opaque refs; no config/secrets)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class IssuanceStatePersistence(StrEnum):
    """Stored operational state: aligned with in-memory v1 ledger issued/revoked."""

    ISSUED = "issued"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class IssuanceStateRow:
    """Row from ``issuance_state`` (provider ref is an opaque, non-secret handle)."""

    internal_user_id: str
    issue_idempotency_key: str
    state: IssuanceStatePersistence
    provider_issuance_ref: str
    created_at: datetime
    updated_at: datetime
    revoked_at: datetime | None
