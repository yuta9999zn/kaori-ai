-- =====================================================================
-- 073_session_replay.sql
--
-- P2-S18 OBS-023 — User session replay (opt-in).
--
-- 2 tables:
--   user_session_consent     — per-user opt-in consent (timestamped)
--   user_session_recordings  — captured DOM/event stream + redacted PII
--
-- Design choices
-- --------------
-- - Consent is per-user, not per-tenant: even if enterprise_id allows
--   replay, each user must explicitly opt-in (GDPR/Vietnamese PDPL).
-- - recording_events JSONB stores a compressed event stream
--   (rrweb-style snapshot+mutation events). PII fields masked BEFORE
--   write per K-5; never stored raw.
-- - 30-day TTL via `expires_at` so the recording auto-prunes — caller
--   cron deletes rows past expiry. Avoids storage growth.
-- - duration_seconds is denormalized for query speed (replay UI lists
--   sessions by duration).
--
-- K-rules
-- -------
-- K-1 RLS: enterprise_id required on both tables.
-- K-5: recording_events stores ONLY PII-masked content; raw events
--      MUST be redacted before INSERT (router enforces).
-- K-6: consent grant/revoke is logged via separate audit row (NOT
--      this table — that's decision_audit_log).
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS user_session_consent (
    consent_id      UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id   UUID         NOT NULL REFERENCES enterprises(enterprise_id),
    user_id         UUID         NOT NULL,
    granted         BOOLEAN      NOT NULL DEFAULT FALSE,
    granted_at      TIMESTAMPTZ,
    revoked_at      TIMESTAMPTZ,
    notes           TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_user_consent UNIQUE (enterprise_id, user_id),
    CONSTRAINT chk_consent_grant_revoke CHECK (
        (granted = TRUE  AND granted_at IS NOT NULL  AND revoked_at IS NULL) OR
        (granted = FALSE AND (revoked_at IS NOT NULL OR granted_at IS NULL))
    )
);

CREATE INDEX IF NOT EXISTS idx_session_consent_user
    ON user_session_consent(user_id, enterprise_id)
    WHERE granted = TRUE;


CREATE TABLE IF NOT EXISTS user_session_recordings (
    recording_id     UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id    UUID         NOT NULL REFERENCES enterprises(enterprise_id),
    user_id          UUID         NOT NULL,
    session_id       UUID         NOT NULL,
    started_at       TIMESTAMPTZ  NOT NULL,
    ended_at         TIMESTAMPTZ,
    duration_seconds INTEGER      NOT NULL DEFAULT 0,
    recording_events JSONB        NOT NULL DEFAULT '[]'::jsonb,
    page_url         TEXT,
    user_agent       VARCHAR(500),
    expires_at       TIMESTAMPTZ  NOT NULL,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_recording_duration_nonneg CHECK (duration_seconds >= 0),
    CONSTRAINT chk_recording_expiry_future CHECK (expires_at > started_at)
);

CREATE INDEX IF NOT EXISTS idx_session_recordings_enterprise
    ON user_session_recordings(enterprise_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_session_recordings_user
    ON user_session_recordings(user_id, started_at DESC);
-- Index supports the cron prune query "DELETE WHERE expires_at < now()".
-- Original was partial WHERE expires_at > NOW(), but PG rejects NOW() in
-- index predicates (STABLE, not IMMUTABLE — PG ERROR 42P17). Dropping the
-- WHERE makes it a full B-tree, which is what the prune query actually
-- needs anyway (it sorts by expires_at ascending and reads only old rows).
CREATE INDEX IF NOT EXISTS idx_session_recordings_expiry
    ON user_session_recordings(expires_at);


COMMENT ON TABLE user_session_consent IS
    'P2-S18 OBS-023 — per-user opt-in consent for session replay. '
    'UNIQUE(enterprise, user) so each user has one row that flips state.';
COMMENT ON TABLE user_session_recordings IS
    'P2-S18 OBS-023 — rrweb-style event stream. PII redacted before write '
    'per K-5. 30-day default TTL via expires_at; cron prunes past expiry.';

COMMIT;
