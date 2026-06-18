-- =====================================================================
-- 079_sso_identities.sql
--
-- P2-AUTH-001 SSO via OAuth (Google + Microsoft).
--
-- 3 new tables:
--   sso_identities       — one row per (provider, provider_sub). Links
--                           an external OAuth identity to a Kaori user.
--   sso_oauth_state      — short-lived CSRF state tokens issued at
--                           /start; consumed at /callback. 10-min TTL.
--   sso_exchange_codes   — one-shot codes the callback returns to the
--                           browser; the FE swaps them at auth-service
--                           for a real JWT. 60-second TTL.
--
-- Design choices
-- --------------
-- - sso_identities (provider, provider_sub) is UNIQUE so the same
--   Google account can't be linked to two Kaori users. user_id +
--   enterprise_id are resolved at callback time by matching on the
--   verified email returned by the provider.
--
-- - sso_oauth_state.state_token is a 32-byte URL-safe random string
--   generated client-side at /start. The /callback step verifies the
--   token was issued recently AND matches the redirect query — same
--   defence as a CSRF cookie, but server-stored.
--
-- - sso_exchange_codes carries the matched user_id so the auth-service
--   Java side can mint a JWT WITHOUT trusting the browser. Code is
--   single-use (consumed_at).
--
-- K-rules
-- -------
-- K-1 RLS: enterprise_id on identities + exchange codes. State tokens
--          are pre-auth so they live with no enterprise scope until
--          callback resolves the email.
-- K-13:    state_token + exchange_code both single-use (consumed_at
--          flip); replay returns 410 Gone in the router.
-- =====================================================================

BEGIN;

-- ─── 1. SSO identities ──────────────────────────────────────────────


CREATE TABLE IF NOT EXISTS sso_identities (
    sso_identity_id   UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id     UUID         NOT NULL REFERENCES enterprises(enterprise_id),
    user_id           UUID,
    provider          VARCHAR(16)  NOT NULL,
    provider_sub      VARCHAR(200) NOT NULL,
    email_at_signup   VARCHAR(200) NOT NULL,
    name_at_signup   VARCHAR(200),
    raw_profile       JSONB        NOT NULL DEFAULT '{}'::jsonb,
    first_seen_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_seen_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_sso_provider_sub UNIQUE (provider, provider_sub),
    CONSTRAINT chk_sso_provider CHECK (provider IN ('google', 'microsoft'))
);

CREATE INDEX IF NOT EXISTS idx_sso_email
    ON sso_identities(lower(email_at_signup));
CREATE INDEX IF NOT EXISTS idx_sso_enterprise
    ON sso_identities(enterprise_id, provider);


-- ─── 2. OAuth state (CSRF) ──────────────────────────────────────────


CREATE TABLE IF NOT EXISTS sso_oauth_state (
    state_token   VARCHAR(64)  PRIMARY KEY,
    provider      VARCHAR(16)  NOT NULL,
    return_url    TEXT,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    expires_at    TIMESTAMPTZ  NOT NULL,
    consumed_at   TIMESTAMPTZ,

    CONSTRAINT chk_sso_state_provider CHECK (provider IN ('google', 'microsoft')),
    CONSTRAINT chk_sso_state_expires_after_created
        CHECK (expires_at > created_at)
);

CREATE INDEX IF NOT EXISTS idx_sso_state_active
    ON sso_oauth_state(state_token)
    WHERE consumed_at IS NULL;


-- ─── 3. Exchange codes (one-time JWT mint handoff) ───────────────────


CREATE TABLE IF NOT EXISTS sso_exchange_codes (
    code              VARCHAR(64)  PRIMARY KEY,
    enterprise_id     UUID         NOT NULL REFERENCES enterprises(enterprise_id),
    user_id           UUID         NOT NULL,
    sso_identity_id   UUID         NOT NULL REFERENCES sso_identities(sso_identity_id),
    provider          VARCHAR(16)  NOT NULL,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    expires_at        TIMESTAMPTZ  NOT NULL,
    consumed_at       TIMESTAMPTZ,
    consumed_by_ip    VARCHAR(45),

    CONSTRAINT chk_sso_exchange_provider CHECK (provider IN ('google', 'microsoft')),
    CONSTRAINT chk_sso_exchange_expires_after_created
        CHECK (expires_at > created_at)
);

CREATE INDEX IF NOT EXISTS idx_sso_exchange_active
    ON sso_exchange_codes(code)
    WHERE consumed_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_sso_exchange_enterprise
    ON sso_exchange_codes(enterprise_id, created_at DESC);


COMMENT ON TABLE sso_identities IS
    'P2-AUTH-001 — per-provider identity row. Provider-sub is the '
    'stable identifier from Google/Microsoft; email is informational '
    '(can change). user_id links to enterprise_users matched by email '
    'at first callback.';
COMMENT ON TABLE sso_oauth_state IS
    'P2-AUTH-001 — CSRF state tokens issued at /sso/{provider}/start. '
    'Single-use, 10-min TTL. Replay returns 410 Gone.';
COMMENT ON TABLE sso_exchange_codes IS
    'P2-AUTH-001 — one-shot handoff to auth-service. Callback writes '
    'the matched user_id + enterprise_id under a fresh code; the FE '
    'POSTs to /api/v1/auth/sso/exchange?code=... at auth-service which '
    'reads + marks consumed + mints a real RS256 JWT. 60-sec TTL.';

COMMIT;
