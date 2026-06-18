-- =====================================================================
-- 072_workflow_collaboration.sql
--
-- P2-S16 Multi-user collab — 3 tables enabling many-users-per-workflow:
--   workflow_editors  — assignment + role (owner/editor/reviewer/viewer)
--   workflow_comments — threaded comments anchored to workflow or node
--   workflow_locks    — soft optimistic-lock to prevent edit conflicts
--
-- Design choices
-- --------------
-- - workflow_editors role enum mirrors P2 RBAC (MANAGER / OPERATOR /
--   ANALYST / VIEWER) but lives at the WORKFLOW grain, not the
--   department grain. A user can be VIEWER on most workflows but
--   EDITOR on one. (department_id role from JWT remains the default.)
-- - workflow_comments are threaded via parent_comment_id (NULL for
--   top-level). Anchored at workflow_id OR node_id (mutually exclusive
--   via CHECK) — node-level keeps card-level discussion separate.
-- - workflow_locks uses optimistic pattern: acquire returns lock_token;
--   subsequent PATCH calls MUST send lock_token; expired locks
--   auto-release (acquired_at + ttl_seconds). No DB triggers — router
--   checks staleness on read.
--
-- K-rules
-- -------
-- K-1 RLS: enterprise_id denormalized on all 3 tables.
-- K-12 / K-13: lock_token is UUID issued by the server; client never
--             supplies it from outside (anti-IDOR).
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS workflow_editors (
    editor_id       UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id     UUID         NOT NULL,
    enterprise_id   UUID         NOT NULL REFERENCES enterprises(enterprise_id),
    user_id         UUID         NOT NULL,
    role            VARCHAR(16)  NOT NULL DEFAULT 'EDITOR',
    invited_by      UUID,
    accepted        BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    accepted_at     TIMESTAMPTZ,

    CONSTRAINT chk_editor_role CHECK (role IN (
        'OWNER', 'EDITOR', 'REVIEWER', 'VIEWER'
    )),
    CONSTRAINT uq_workflow_editor UNIQUE (workflow_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_workflow_editors_workflow
    ON workflow_editors(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_editors_user
    ON workflow_editors(user_id, enterprise_id);


CREATE TABLE IF NOT EXISTS workflow_comments (
    comment_id        UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id       UUID         NOT NULL,
    node_id           UUID,
    enterprise_id     UUID         NOT NULL REFERENCES enterprises(enterprise_id),
    parent_comment_id UUID         REFERENCES workflow_comments(comment_id) ON DELETE CASCADE,
    author_user_id    UUID         NOT NULL,
    body              TEXT         NOT NULL,
    resolved          BOOLEAN      NOT NULL DEFAULT FALSE,
    resolved_at       TIMESTAMPTZ,
    resolved_by       UUID,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    edited_at         TIMESTAMPTZ,

    CONSTRAINT chk_comment_body_nonempty CHECK (length(trim(body)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_workflow_comments_workflow
    ON workflow_comments(workflow_id, created_at);
CREATE INDEX IF NOT EXISTS idx_workflow_comments_node
    ON workflow_comments(node_id) WHERE node_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_workflow_comments_thread
    ON workflow_comments(parent_comment_id)
    WHERE parent_comment_id IS NOT NULL;


CREATE TABLE IF NOT EXISTS workflow_locks (
    lock_id         UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id     UUID         NOT NULL UNIQUE,
    enterprise_id   UUID         NOT NULL REFERENCES enterprises(enterprise_id),
    held_by_user_id UUID         NOT NULL,
    lock_token      UUID         NOT NULL DEFAULT gen_random_uuid(),
    acquired_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    ttl_seconds     INTEGER      NOT NULL DEFAULT 600,
    intent          VARCHAR(32)  NOT NULL DEFAULT 'edit',

    CONSTRAINT chk_lock_ttl_range CHECK (ttl_seconds BETWEEN 30 AND 3600),
    CONSTRAINT chk_lock_intent CHECK (intent IN ('edit', 'approve', 'rebuild'))
);

CREATE INDEX IF NOT EXISTS idx_workflow_locks_user
    ON workflow_locks(held_by_user_id);

COMMENT ON TABLE workflow_editors IS
    'P2-S16 — assignment table. role overrides JWT-derived dept role on '
    'this specific workflow. Composite uniqueness on (workflow_id, user_id).';
COMMENT ON TABLE workflow_comments IS
    'P2-S16 — threaded comments. Anchor to workflow_id alone (workflow-level) '
    'OR workflow_id + node_id (node-level). Body soft-deletes via resolved=true.';
COMMENT ON COLUMN workflow_locks.lock_token IS
    'K-13 anti-IDOR: opaque UUID. Client gets it from acquire(), echoes on '
    'subsequent edits. Server checks token + (acquired_at + ttl_seconds > now).';

COMMIT;
