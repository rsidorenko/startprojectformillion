"""Provider-neutral config issuance v1 contracts (no persistence, no real provider)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import Protocol

from app.shared.types import SubscriptionSnapshotState


class IssuanceOperationType(StrEnum):
    """Normalized issuance operation (design UC-06 / UC-08 / UC-07 intent)."""

    ISSUE = "issue"
    RESEND = "resend"
    REVOKE = "revoke"


class IssuanceOutcomeCategory(StrEnum):
    """
    Failure taxonomy and outcomes aligned with design doc §J (and explicit success classes).
    No secret payload classes.
    """

    NOT_ENTITLED = "not_entitled"
    NEEDS_REVIEW = "needs_review"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_REJECTED = "provider_rejected"
    ALREADY_ISSUED = "already_issued"
    REVOKED = "revoked"
    UNSAFE_TO_DELIVER = "unsafe_to_deliver"
    INTERNAL_ERROR = "internal_error"
    ISSUED = "issued"
    DELIVERY_READY = "delivery_ready"


@dataclass(frozen=True, slots=True)
class IssuanceRequest:
    """
    In-process issuance intent.

    * ``idempotency_key`` scopes *this* operation (issue / a single resend / a revoke).
    * For :attr:`REVOKE` and :attr:`RESEND`, ``link_issue_idempotency_key`` must be the
      ``idempotency_key`` used for the original successful :attr:`ISSUE` (same process).
    """

    internal_user_id: str
    subscription_state: SubscriptionSnapshotState | None
    operation: IssuanceOperationType
    idempotency_key: str
    correlation_id: str
    link_issue_idempotency_key: str | None = None


@dataclass(frozen=True, slots=True)
class IssuanceServiceResult:
    """Normalized outcome; ``safe_ref`` is an opaque, non-secret handle (when present)."""

    category: IssuanceOutcomeCategory
    safe_ref: str | None = None


@dataclass(frozen=True, slots=True)
class IssuanceAuditRecord:
    """Category-only in-memory seam for tests; no config/secret/payload content."""

    operation: IssuanceOperationType
    outcome: IssuanceOutcomeCategory
    internal_user_id: str
    correlation_id: str
    idempotency_key: str
    link_issue_idempotency_key: str | None

    def redacted_summary(self) -> str:
        """String form used for secret-substring assertions (no secret material by design)."""
        return (
            f"op={self.operation} outcome={self.outcome} user={self.internal_user_id} "
            f"cid={self.correlation_id} idem={self.idempotency_key} "
            f"link={self.link_issue_idempotency_key!s}"
        )


# --- provider boundary (fake or real in future) ---


class CreateAccessOutcome(StrEnum):
    """Normalized provider result for create/ensure (fail-closed at service layer for unknown)."""

    SUCCESS = "success"
    UNAVAILABLE = "unavailable"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


class RevokeAccessOutcome(StrEnum):
    REVOKED = "revoked"
    ALREADY_REVOKED = "already_revoked"
    UNAVAILABLE = "unavailable"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


class GetSafeInstructionOutcome(StrEnum):
    """Normalized provider result for safe (non-secret) instruction delivery."""

    READY = "ready"
    UNAVAILABLE = "unavailable"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ProviderCreateResult:
    outcome: CreateAccessOutcome
    issuance_ref: str | None


@dataclass(frozen=True, slots=True)
class ProviderGetSafeResult:
    outcome: GetSafeInstructionOutcome
    instruction_ref: str | None


@dataclass(frozen=True, slots=True)
class ProviderRevokeResult:
    outcome: RevokeAccessOutcome


class IssuanceProviderPort(Protocol):
    """Pluggable access/config provider; in-memory fake only in this slice."""

    async def create_or_ensure_access(
        self,
        *,
        internal_user_id: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> ProviderCreateResult:
        """Establish access at the provider; returns normalized outcome and optional opaque ref."""
        ...

    async def revoke_access(
        self,
        *,
        internal_user_id: str,
        issuance_ref: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> ProviderRevokeResult: ...

    async def get_safe_delivery_instructions(
        self,
        *,
        internal_user_id: str,
        issuance_ref: str,
        correlation_id: str,
    ) -> ProviderGetSafeResult: ...

