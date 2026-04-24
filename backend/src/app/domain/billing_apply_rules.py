"""UC-05 v1: narrow allowlist and sentinels (no provider parsing, no raw payloads)."""

from __future__ import annotations

# Only this normalized event type may set subscription to active in v1. Product may extend.
UC05_ALLOWLISTED_EVENT_TYPE_SUBSCRIPTION_ACTIVATED = "subscription_activated"

UC05_ALLOWLISTED_EVENT_TYPES: frozenset[str] = frozenset(
    {UC05_ALLOWLISTED_EVENT_TYPE_SUBSCRIPTION_ACTIVATED}
)

# Stored in billing_subscription_apply_records.internal_user_id when the ledger fact has no user;
# not a real internal user id (UUID-style ids do not use this pattern).
UC05_NO_USER_SENTINEL = "_uc05_no_internal_user_"
