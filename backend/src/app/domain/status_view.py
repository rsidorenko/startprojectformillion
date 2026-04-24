"""Read-only fail-closed status mapping for UC-02 (no billing / issuance)."""

from __future__ import annotations

from app.shared.types import SafeUserStatusCategory, SubscriptionSnapshotState

# UC-05 v1: only explicit enum values may surface as subscription active in safe status.
_BILLING_BACKED_ACTIVE: frozenset[SubscriptionSnapshotState] = frozenset(
    {SubscriptionSnapshotState.ACTIVE}
)


def map_subscription_status_view(
    user_known: bool,
    snapshot: SubscriptionSnapshotState | None,
) -> SafeUserStatusCategory:
    """
    Map identity + subscription snapshot to a safe user-facing category.

    Fail-closed: unknown user => needs bootstrap; missing/unknown snapshot => inactive style;
    no paid/active without an explicit billing-backed state (none in this slice).
    """
    if not user_known:
        return SafeUserStatusCategory.NEEDS_BOOTSTRAP

    if snapshot is None:
        return SafeUserStatusCategory.INACTIVE_OR_NOT_ELIGIBLE

    if snapshot is SubscriptionSnapshotState.ABSENT:
        return SafeUserStatusCategory.INACTIVE_OR_NOT_ELIGIBLE

    if snapshot in _BILLING_BACKED_ACTIVE:
        return SafeUserStatusCategory.SUBSCRIPTION_ACTIVE

    if snapshot is SubscriptionSnapshotState.NEEDS_REVIEW:
        return SafeUserStatusCategory.NEEDS_REVIEW

    return SafeUserStatusCategory.INACTIVE_OR_NOT_ELIGIBLE
