-- =====================================================================
-- 102_customer_workflow_versioning.sql — Phase 2.8 D2 — Customer Config
--                                                       + Workflow Versioning
--                                                       + 3-Mode + CR Link
--
-- Anh's spec 2026-05-20 (Customer Customization layer):
--   "Template chuẩn + Customer Config riêng + Workflow versioning +
--   Change Request cho thay đổi lớn. 3 mode UI: Simple / Advanced /
--   Developer. Mỗi workflow nên có template_id + customer_id + version
--   + status + based_on_template_version + change_reason + approved_by
--   + effective_date."
--
-- Existing baseline:
--   • mig 053 workflows.version INTEGER NOT NULL DEFAULT 1 — there's a
--     version counter on the live row, but no immutable history yet.
--   • mig 094 workflow_events append-only — captures runtime events,
--     NOT structural changes to the workflow itself.
--   • mig 072 workflow_editors/comments/locks — collab presence, not
--     versioning.
--
-- What THIS mig adds:
--   • customer_workflow_versions — immutable snapshot of workflow
--     definition per save. Like git tags for workflows.
--   • workflow_customizations — change log: who changed what, when,
--     why. Lets analyst see "we deviated from template at v3".
--   • enterprise_industry_bootstrap — track when a tenant bootstrapped
--     from an industry template. Idempotent.
--   • enterprise_workflow_mode — per-enterprise (or per-user) UI mode
--     flag (simple/advanced/developer). FE reads to hide/show controls.
--   • workflow_change_requests — lightweight CR row that links to the
--     full BA CR Register entry (4.2 docx). Phase 2 will extend with
--     CR approval workflow.
--
-- K-rule compliance:
--   K-1 RLS: customer_workflow_versions + workflow_customizations +
--           enterprise_industry_bootstrap + enterprise_workflow_mode +
--           workflow_change_requests ARE tenant-scoped. RLS enabled.
--   K-2 immutable: customer_workflow_versions has BEFORE-UPDATE +
--           BEFORE-DELETE triggers refusing mutation.
--   K-19 OpenTelemetry: bootstrap + customize routers emit tenant_id span.
-- =====================================================================

-- ─── 1. customer_workflow_versions (immutable snapshot history) ──────

CREATE TABLE IF NOT EXISTS customer_workflow_versions (
    version_id           UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id        UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,

    workflow_id          UUID            NOT NULL REFERENCES workflows(workflow_id) ON DELETE CASCADE,
    version_number       INTEGER         NOT NULL,                    -- monotonically increasing per workflow

    -- Snapshot of the workflow definition at this version. Full
    -- {nodes:[], edges:[]} JSON. Same shape as workflow_templates.workflow_definition.
    snapshot             JSONB           NOT NULL,

    -- Provenance: where did this version come from?
    -- 'bootstrap'      = first save after industry bootstrap (auto)
    -- 'manual_edit'    = user edited in the FE builder
    -- 'template_sync'  = pulled latest template upstream (rare)
    -- 'cr_apply'       = applied an approved Change Request
    -- 'rollback'       = restored from a prior version
    source               VARCHAR(30)     NOT NULL DEFAULT 'manual_edit',

    based_on_template_version  INTEGER,                                -- template version at fork time
    based_on_template_id UUID            REFERENCES workflow_templates(template_id) ON DELETE SET NULL,

    change_reason        TEXT,                                         -- free text "thêm CFO duyệt > 200M"
    created_by           UUID,
    created_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    -- Approval metadata (filled when source='cr_apply').
    approved_by          UUID,
    approved_at          TIMESTAMPTZ,
    change_request_ref   UUID,                                         -- link to workflow_change_requests below

    -- Effective date — when this version becomes the canonical "active"
    -- one. Bootstrap = same as created_at; CR-driven changes may be
    -- scheduled for future date.
    effective_date       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_workflow_version UNIQUE (workflow_id, version_number),
    CONSTRAINT chk_version_source CHECK (source IN (
        'bootstrap', 'manual_edit', 'template_sync', 'cr_apply', 'rollback'
    ))
);

CREATE INDEX IF NOT EXISTS idx_cwv_workflow_version
    ON customer_workflow_versions (workflow_id, version_number DESC);
CREATE INDEX IF NOT EXISTS idx_cwv_enterprise
    ON customer_workflow_versions (enterprise_id, effective_date DESC);

-- RLS K-1
ALTER TABLE customer_workflow_versions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_cwv_tenant ON customer_workflow_versions;
CREATE POLICY rls_cwv_tenant ON customer_workflow_versions
    USING (enterprise_id = current_setting('app.enterprise_id', TRUE)::UUID)
    WITH CHECK (enterprise_id = current_setting('app.enterprise_id', TRUE)::UUID);

-- K-2 Immutability — refuse UPDATE/DELETE (snapshots are tags).

CREATE OR REPLACE FUNCTION refuse_cwv_mutation() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'customer_workflow_versions is immutable (K-2 snapshot history)';
END;
$$;

DROP TRIGGER IF EXISTS trg_cwv_no_update ON customer_workflow_versions;
CREATE TRIGGER trg_cwv_no_update
    BEFORE UPDATE OR DELETE ON customer_workflow_versions
    FOR EACH ROW EXECUTE FUNCTION refuse_cwv_mutation();


-- ─── 2. workflow_customizations (change log per workflow) ────────────
--
-- Mutable change log — captures "what changed since the parent template"
-- to make audit easy. Each row = one editing session (FE batches micro
-- edits into one row).

CREATE TABLE IF NOT EXISTS workflow_customizations (
    customization_id     UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id        UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    workflow_id          UUID            NOT NULL REFERENCES workflows(workflow_id) ON DELETE CASCADE,

    -- Which version did this customization PRODUCE? FK to immutable
    -- snapshot table (nullable while user is still editing in DRAFT).
    resulting_version_id UUID            REFERENCES customer_workflow_versions(version_id) ON DELETE SET NULL,

    -- Operation type — drives FE rendering of the change log entry.
    operation            VARCHAR(40)     NOT NULL,
    -- 'add_node' | 'remove_node' | 'edit_node' | 'add_edge' |
    -- 'remove_edge' | 'edit_branch' | 'change_sla' | 'change_owner' |
    -- 'add_document_requirement' | 'edit_threshold' | 'rename' | 'reorder'

    -- Free-form payload: {before: {...}, after: {...}} or {added: {...}}.
    diff                 JSONB           NOT NULL DEFAULT '{}'::jsonb,

    -- Mode the editor used. Phase 2 PDP will gate "developer" to admin
    -- role only.
    edit_mode            VARCHAR(20)     NOT NULL DEFAULT 'simple',

    changed_by           UUID,
    changed_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_customization_mode CHECK (
        edit_mode IN ('simple', 'advanced', 'developer')
    ),
    CONSTRAINT chk_customization_op CHECK (operation IN (
        'add_node', 'remove_node', 'edit_node', 'add_edge', 'remove_edge',
        'edit_branch', 'change_sla', 'change_owner', 'add_document_requirement',
        'edit_threshold', 'rename', 'reorder', 'cr_apply'
    ))
);

CREATE INDEX IF NOT EXISTS idx_customization_workflow_time
    ON workflow_customizations (workflow_id, changed_at DESC);

ALTER TABLE workflow_customizations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_customization_tenant ON workflow_customizations;
CREATE POLICY rls_customization_tenant ON workflow_customizations
    USING (enterprise_id = current_setting('app.enterprise_id', TRUE)::UUID)
    WITH CHECK (enterprise_id = current_setting('app.enterprise_id', TRUE)::UUID);


-- ─── 3. enterprise_industry_bootstrap (one-shot bootstrap record) ───
--
-- Idempotent record of "this enterprise was bootstrapped from industry X".
-- Lets re-bootstrap be a no-op (UNIQUE on enterprise_id), or we can
-- explicitly support "re-bootstrap" by deleting the row first.

CREATE TABLE IF NOT EXISTS enterprise_industry_bootstrap (
    bootstrap_id         UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id        UUID            NOT NULL UNIQUE REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,

    industry_id          UUID            NOT NULL REFERENCES industry_templates(industry_id) ON DELETE RESTRICT,

    -- What did we clone? Counters for audit.
    depts_created        INTEGER         NOT NULL DEFAULT 0,
    workflows_created    INTEGER         NOT NULL DEFAULT 0,
    kpis_created         INTEGER         NOT NULL DEFAULT 0,
    schemas_seeded       INTEGER         NOT NULL DEFAULT 0,
    roles_seeded         INTEGER         NOT NULL DEFAULT 0,

    -- User who triggered + when.
    bootstrapped_by      UUID,
    bootstrapped_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    -- After bootstrap, the wizard may show "let's review" — flag once
-- user clicks "I'm done reviewing".
    review_completed_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_eib_industry
    ON enterprise_industry_bootstrap (industry_id);

ALTER TABLE enterprise_industry_bootstrap ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_eib_tenant ON enterprise_industry_bootstrap;
CREATE POLICY rls_eib_tenant ON enterprise_industry_bootstrap
    USING (enterprise_id = current_setting('app.enterprise_id', TRUE)::UUID)
    WITH CHECK (enterprise_id = current_setting('app.enterprise_id', TRUE)::UUID);


-- ─── 4. enterprise_workflow_mode (per-enterprise UI mode) ────────────
--
-- 3-mode toggle: Simple / Advanced / Developer.
-- - Simple    : SME manager — rename, owner, SLA, threshold only.
-- - Advanced  : analyst/CSM — branch, schema, KPI, approval flows.
-- - Developer : platform admin — connector, node type, API integration.
--
-- One row per enterprise (default) + optional per-user override (Phase
-- 2 user-level customization; v0 = enterprise-level only).

CREATE TABLE IF NOT EXISTS enterprise_workflow_mode (
    enterprise_id        UUID            PRIMARY KEY REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,

    default_mode         VARCHAR(20)     NOT NULL DEFAULT 'simple',

    -- Phase 2: per-user override map {user_id: mode}.
    user_overrides       JSONB           NOT NULL DEFAULT '{}'::jsonb,

    -- Lock advanced/developer behind feature flag? (Some plans don't
-- get developer mode at all — e.g. PILOT plan = simple-only.)
    advanced_unlocked    BOOLEAN         NOT NULL DEFAULT TRUE,
    developer_unlocked   BOOLEAN         NOT NULL DEFAULT FALSE,

    updated_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_mode_default CHECK (
        default_mode IN ('simple', 'advanced', 'developer')
    )
);

ALTER TABLE enterprise_workflow_mode ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_workflow_mode_tenant ON enterprise_workflow_mode;
CREATE POLICY rls_workflow_mode_tenant ON enterprise_workflow_mode
    USING (enterprise_id = current_setting('app.enterprise_id', TRUE)::UUID)
    WITH CHECK (enterprise_id = current_setting('app.enterprise_id', TRUE)::UUID);


-- ─── 5. workflow_change_requests (link table to BA CR Register) ──────
--
-- Lightweight pointer — full CR detail lives in docs/ba/4.2_Change_
-- Request_Register.md. This row is what runtime + audit reference.

CREATE TABLE IF NOT EXISTS workflow_change_requests (
    cr_id                UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id        UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,

    workflow_id          UUID            REFERENCES workflows(workflow_id) ON DELETE SET NULL,

    -- BA CR reference (e.g. 'CR-0001'). Free-form to match docx scheme.
    ba_cr_ref            VARCHAR(20),

    classification       VARCHAR(20)     NOT NULL,        -- 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
    title                VARCHAR(200)    NOT NULL,
    title_vi             VARCHAR(200),
    description          TEXT,

    -- Free text from CR Section 1-4 in 4.2 register; truncated/synced.
    business_context     TEXT,
    proposed_change      TEXT,
    risk_assessment      TEXT,

    status               VARCHAR(30)     NOT NULL DEFAULT 'SUBMITTED',

    -- Approval chain.
    requested_by         UUID,
    requested_at         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    approved_by          UUID,
    approved_at          TIMESTAMPTZ,

    -- Implementation tracking.
    implemented_version_id UUID          REFERENCES customer_workflow_versions(version_id) ON DELETE SET NULL,
    implemented_at       TIMESTAMPTZ,

    CONSTRAINT chk_cr_classification CHECK (
        classification IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')
    ),
    CONSTRAINT chk_cr_status CHECK (status IN (
        'SUBMITTED', 'ESTIMATING', 'ASSESSING', 'APPROVED', 'REJECTED',
        'IMPLEMENTED', 'BASELINED', 'WITHDRAWN'
    ))
);

CREATE INDEX IF NOT EXISTS idx_cr_workflow
    ON workflow_change_requests (workflow_id, status);
CREATE INDEX IF NOT EXISTS idx_cr_enterprise_status
    ON workflow_change_requests (enterprise_id, status, requested_at DESC);

ALTER TABLE workflow_change_requests ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS rls_cr_tenant ON workflow_change_requests;
CREATE POLICY rls_cr_tenant ON workflow_change_requests
    USING (enterprise_id = current_setting('app.enterprise_id', TRUE)::UUID)
    WITH CHECK (enterprise_id = current_setting('app.enterprise_id', TRUE)::UUID);


-- ─── Convenience view: workflow latest version + customization count ─

CREATE OR REPLACE VIEW v_workflow_version_status AS
SELECT
    w.workflow_id,
    w.enterprise_id,
    w.name,
    w.state,
    w.version                                                    AS live_version,
    (
        SELECT MAX(cwv.version_number)
        FROM customer_workflow_versions cwv
        WHERE cwv.workflow_id = w.workflow_id
    )                                                            AS snapshot_count,
    (
        SELECT COUNT(*)
        FROM workflow_customizations c
        WHERE c.workflow_id = w.workflow_id
    )                                                            AS customization_count,
    (
        SELECT COUNT(*)
        FROM workflow_change_requests cr
        WHERE cr.workflow_id = w.workflow_id AND cr.status IN ('SUBMITTED', 'ESTIMATING', 'ASSESSING', 'APPROVED')
    )                                                            AS open_cr_count
FROM workflows w;


COMMENT ON TABLE customer_workflow_versions  IS 'Phase 2.8 — Immutable snapshot history per workflow. K-2 trigger refuses UPDATE/DELETE.';
COMMENT ON TABLE workflow_customizations     IS 'Phase 2.8 — Mutable change log per editing session. RLS K-1.';
COMMENT ON TABLE enterprise_industry_bootstrap IS 'Phase 2.8 — One-shot bootstrap event per enterprise; UNIQUE enforces idempotency.';
COMMENT ON TABLE enterprise_workflow_mode    IS 'Phase 2.8 — Per-enterprise 3-mode UI flag (simple/advanced/developer).';
COMMENT ON TABLE workflow_change_requests    IS 'Phase 2.8 — Runtime CR row linked to BA CR Register 4.2. Full detail in docs/ba/.';
