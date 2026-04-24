"""ADM-01 lookup orchestration (read-only; no transport, audit, or persistence here)."""

from __future__ import annotations

from app.admin_support.contracts import (
    Adm01AuthorizationPort,
    Adm01EntitlementReadPort,
    Adm01IdentityResolvePort,
    Adm01IssuanceReadPort,
    Adm01LookupInput,
    Adm01LookupOutcome,
    Adm01LookupResult,
    Adm01LookupSummary,
    Adm01PolicyReadPort,
    Adm01RedactionPort,
    Adm01SubscriptionReadPort,
    Adm01SubscriptionStatusSummary,
    RedactionMarker,
)
from app.shared.correlation import require_correlation_id


class Adm01LookupHandler:
    """Validate correlation → authorize ADM-01 → resolve identity → read summaries → optional redaction."""

    def __init__(
        self,
        authorization: Adm01AuthorizationPort,
        identity: Adm01IdentityResolvePort,
        subscription: Adm01SubscriptionReadPort,
        entitlement: Adm01EntitlementReadPort,
        issuance: Adm01IssuanceReadPort,
        policy: Adm01PolicyReadPort,
        redaction: Adm01RedactionPort | None = None,
    ) -> None:
        self._authorization = authorization
        self._identity = identity
        self._subscription = subscription
        self._entitlement = entitlement
        self._issuance = issuance
        self._policy = policy
        self._redaction = redaction

    async def handle(self, inp: Adm01LookupInput) -> Adm01LookupResult:
        cid = inp.correlation_id
        try:
            require_correlation_id(cid)
        except ValueError:
            return Adm01LookupResult(
                outcome=Adm01LookupOutcome.INVALID_INPUT,
                correlation_id=cid,
                summary=None,
            )

        try:
            allowed = await self._authorization.check_adm01_lookup_allowed(
                inp.actor,
                correlation_id=cid,
            )
        except Exception:
            return Adm01LookupResult(
                outcome=Adm01LookupOutcome.DEPENDENCY_FAILURE,
                correlation_id=cid,
                summary=None,
            )
        if not allowed:
            return Adm01LookupResult(
                outcome=Adm01LookupOutcome.DENIED,
                correlation_id=cid,
                summary=None,
            )

        try:
            internal_user_id = await self._identity.resolve_internal_user_id(
                inp.target,
                correlation_id=cid,
            )
        except Exception:
            return Adm01LookupResult(
                outcome=Adm01LookupOutcome.DEPENDENCY_FAILURE,
                correlation_id=cid,
                summary=None,
            )
        if internal_user_id is None:
            return Adm01LookupResult(
                outcome=Adm01LookupOutcome.TARGET_NOT_RESOLVED,
                correlation_id=cid,
                summary=None,
            )

        try:
            snapshot = await self._subscription.get_subscription_snapshot(internal_user_id)
            entitlement = await self._entitlement.get_entitlement_summary(internal_user_id)
            issuance = await self._issuance.get_issuance_summary(internal_user_id)
            policy_flag = await self._policy.get_policy_flag(internal_user_id)
        except Exception:
            return Adm01LookupResult(
                outcome=Adm01LookupOutcome.DEPENDENCY_FAILURE,
                correlation_id=cid,
                summary=None,
            )

        summary = Adm01LookupSummary(
            subscription=Adm01SubscriptionStatusSummary(snapshot=snapshot),
            entitlement=entitlement,
            policy_flag=policy_flag,
            issuance=issuance,
            redaction=RedactionMarker.NONE,
        )
        if self._redaction is not None:
            try:
                summary = await self._redaction.redact_lookup_summary(summary)
            except Exception:
                return Adm01LookupResult(
                    outcome=Adm01LookupOutcome.DEPENDENCY_FAILURE,
                    correlation_id=cid,
                    summary=None,
                )

        return Adm01LookupResult(
            outcome=Adm01LookupOutcome.SUCCESS,
            correlation_id=cid,
            summary=summary,
        )
