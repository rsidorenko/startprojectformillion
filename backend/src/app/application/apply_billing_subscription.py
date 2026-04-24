"""UC-05: apply accepted billing fact to subscription (no transport, no public HTTP)."""

from __future__ import annotations

from dataclasses import dataclass

from app.persistence.billing_subscription_apply_contracts import BillingSubscriptionApplyOutcome
from app.persistence.postgres_billing_subscription_apply import (
    PostgresAtomicUC05SubscriptionApply,
    UC05PostgresApplyResult,
)
from app.shared.types import OperationOutcomeCategory


@dataclass(frozen=True, slots=True)
class ApplyAcceptedBillingFactInput:
    """Normalized UC-05 input: stable ledger key."""

    internal_fact_ref: str


@dataclass(frozen=True, slots=True)
class ApplyAcceptedBillingFactResult:
    """Outcome of :meth:`ApplyAcceptedBillingFactHandler.handle`."""

    operation_outcome: OperationOutcomeCategory
    idempotent_replay: bool
    apply_outcome: BillingSubscriptionApplyOutcome | None


def _outcome_to_result(pg: UC05PostgresApplyResult) -> ApplyAcceptedBillingFactResult:
    return ApplyAcceptedBillingFactResult(
        operation_outcome=pg.operation_outcome,
        idempotent_replay=pg.idempotent_replay,
        apply_outcome=pg.apply_outcome,
    )


class ApplyAcceptedBillingFactHandler:
    """UC-05: delegates to :class:`PostgresAtomicUC05SubscriptionApply` (one PG transaction)."""

    def __init__(self, apply_pg: PostgresAtomicUC05SubscriptionApply) -> None:
        self._apply = apply_pg

    async def handle(self, inp: ApplyAcceptedBillingFactInput) -> ApplyAcceptedBillingFactResult:
        res = await self._apply.apply_by_internal_fact_ref(inp.internal_fact_ref)
        return _outcome_to_result(res)
