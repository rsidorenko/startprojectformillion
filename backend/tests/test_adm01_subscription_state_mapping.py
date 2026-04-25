"""Unit tests for ADM-01 internal snapshot classification helper."""

from __future__ import annotations

import pytest

from app.admin_support.adm01_subscription_state_mapping import (
    Adm01SnapshotStateKind,
    classify_adm01_subscription_snapshot,
)
from app.admin_support.contracts import AdminPolicyFlag, EntitlementSummaryCategory
from app.application.interfaces import SubscriptionSnapshot


@pytest.mark.parametrize(
    ("snapshot", "expected_kind"),
    [
        (None, Adm01SnapshotStateKind.MISSING_OR_UNKNOWN),
        (
            SubscriptionSnapshot(internal_user_id="u-1", state_label="active"),
            Adm01SnapshotStateKind.ACTIVE,
        ),
        (
            SubscriptionSnapshot(internal_user_id="u-1", state_label="inactive"),
            Adm01SnapshotStateKind.OTHER_NON_ACTIVE,
        ),
        (
            SubscriptionSnapshot(internal_user_id="u-1", state_label="absent"),
            Adm01SnapshotStateKind.OTHER_NON_ACTIVE,
        ),
        (
            SubscriptionSnapshot(internal_user_id="u-1", state_label="not_eligible"),
            Adm01SnapshotStateKind.OTHER_NON_ACTIVE,
        ),
        (
            SubscriptionSnapshot(internal_user_id="u-1", state_label="needs_review"),
            Adm01SnapshotStateKind.NEEDS_REVIEW,
        ),
        (
            SubscriptionSnapshot(internal_user_id="u-1", state_label="unexpected_state"),
            Adm01SnapshotStateKind.MISSING_OR_UNKNOWN,
        ),
    ],
)
def test_classify_adm01_subscription_snapshot_matrix(
    snapshot: SubscriptionSnapshot | None,
    expected_kind: Adm01SnapshotStateKind,
) -> None:
    assert classify_adm01_subscription_snapshot(snapshot) is expected_kind


@pytest.mark.parametrize(
    ("state_kind", "expected_entitlement", "expected_policy"),
    [
        (
            Adm01SnapshotStateKind.MISSING_OR_UNKNOWN,
            EntitlementSummaryCategory.UNKNOWN,
            AdminPolicyFlag.UNKNOWN,
        ),
        (
            Adm01SnapshotStateKind.ACTIVE,
            EntitlementSummaryCategory.ACTIVE,
            AdminPolicyFlag.DEFAULT,
        ),
        (
            Adm01SnapshotStateKind.NEEDS_REVIEW,
            EntitlementSummaryCategory.INACTIVE,
            AdminPolicyFlag.ENFORCE_MANUAL_REVIEW,
        ),
        (
            Adm01SnapshotStateKind.OTHER_NON_ACTIVE,
            EntitlementSummaryCategory.INACTIVE,
            AdminPolicyFlag.DEFAULT,
        ),
    ],
)
def test_state_kind_to_adapter_output_contract(
    state_kind: Adm01SnapshotStateKind,
    expected_entitlement: EntitlementSummaryCategory,
    expected_policy: AdminPolicyFlag,
) -> None:
    if state_kind is Adm01SnapshotStateKind.MISSING_OR_UNKNOWN:
        got_entitlement = EntitlementSummaryCategory.UNKNOWN
        got_policy = AdminPolicyFlag.UNKNOWN
    elif state_kind is Adm01SnapshotStateKind.ACTIVE:
        got_entitlement = EntitlementSummaryCategory.ACTIVE
        got_policy = AdminPolicyFlag.DEFAULT
    elif state_kind is Adm01SnapshotStateKind.NEEDS_REVIEW:
        got_entitlement = EntitlementSummaryCategory.INACTIVE
        got_policy = AdminPolicyFlag.ENFORCE_MANUAL_REVIEW
    else:
        got_entitlement = EntitlementSummaryCategory.INACTIVE
        got_policy = AdminPolicyFlag.DEFAULT

    assert got_entitlement is expected_entitlement
    assert got_policy is expected_policy
