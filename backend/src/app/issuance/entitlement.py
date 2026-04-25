"""
Issuance entitlement gate for issue/resend: must not be more permissive than UC-02 /status.

Only ``SubscriptionSnapshotState.ACTIVE`` may pass; same interpretation as
``map_subscription_status_view`` for a known user (``user_known=True``):
subscription active iff snapshot is :attr:`~SubscriptionSnapshotState.ACTIVE`.
"""

from __future__ import annotations

from app.domain.status_view import map_subscription_status_view
from app.issuance.contracts import IssuanceOutcomeCategory
from app.shared.types import SafeUserStatusCategory, SubscriptionSnapshotState


def subscription_allows_issue_resend(snapshot: SubscriptionSnapshotState | None) -> bool:
    """True iff the same user would see ``SUBSCRIPTION_ACTIVE`` for this snapshot (known user)."""
    return map_subscription_status_view(True, snapshot) is SafeUserStatusCategory.SUBSCRIPTION_ACTIVE


def issue_resend_denial_category(
    snapshot: SubscriptionSnapshotState | None,
) -> IssuanceOutcomeCategory:
    """
    When :func:`subscription_allows_issue_resend` is False, return a stable v1 category.

    Aligns with :func:`app.domain.status_view.map_subscription_status_view` for ``user_known``:
    ``NEEDS_REVIEW`` snapshot => ``NEEDS_REVIEW`` outcome; otherwise ``NOT_ENTITLED``.
    """
    if snapshot is SubscriptionSnapshotState.NEEDS_REVIEW:
        return IssuanceOutcomeCategory.NEEDS_REVIEW
    return IssuanceOutcomeCategory.NOT_ENTITLED
