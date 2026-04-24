-- Slice-1 user identity mapping (UserIdentityRepository / IdentityRecord).
CREATE TABLE IF NOT EXISTS user_identities (
    telegram_user_id BIGINT NOT NULL PRIMARY KEY,
    internal_user_id TEXT NOT NULL UNIQUE
);
