"""Boundary surface: ADM-01 contracts import and construction (no I/O)."""

from app.admin_support import (
    AdminActorRef,
    AdminPolicyFlag,
    Adm01LookupInput,
    Adm01LookupSummary,
    Adm01SubscriptionStatusSummary,
    EntitlementSummary,
    EntitlementSummaryCategory,
    InternalUserTarget,
    IssuanceOperationalState,
    IssuanceOperationalSummary,
    RedactionMarker,
)
from app.shared.correlation import new_correlation_id


def test_adm01_contracts_construct() -> None:
    inp = Adm01LookupInput(
        actor=AdminActorRef(internal_admin_principal_id="adm-x"),
        target=InternalUserTarget(internal_user_id="user-y"),
        correlation_id=new_correlation_id(),
    )
    out = Adm01LookupSummary(
        subscription=Adm01SubscriptionStatusSummary(snapshot=None),
        entitlement=EntitlementSummary(category=EntitlementSummaryCategory.UNKNOWN),
        policy_flag=AdminPolicyFlag.DEFAULT,
        issuance=IssuanceOperationalSummary(state=IssuanceOperationalState.UNKNOWN),
        redaction=RedactionMarker.NONE,
    )
    assert inp.target.internal_user_id == "user-y"
    assert out.redaction is RedactionMarker.NONE
