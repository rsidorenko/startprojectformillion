-- UC-02 subscription snapshot read model (SubscriptionSnapshotReader / SubscriptionSnapshot).
CREATE TABLE IF NOT EXISTS subscription_snapshots (
    internal_user_id TEXT NOT NULL PRIMARY KEY,
    state_label TEXT NOT NULL
);
