-- 057_workflow_cross_links.sql — P15-S11 Tuần 8 cross-workflow linkage.
--
-- Per anh's directive 2026-05-15 (Vingroup-class follow-up):
--
--   "1 phòng ban có thể có nhiều workflow nhé, và workflow phòng ban a
--   của công ty có thể liên quan đến workflow phòng ban b của công ty
--   khác chẳng hạn, xa hơn nữa là chi nhánh khác hoặc mảng khác."
--
-- Verified about the EXISTING schema:
--   - 1 dept can already host N workflows (mig 053 — no unique on dept).
--   - workflow_edges links node → node WITHIN a single workflow only.
--   - There's no cross-workflow primitive yet.
--
-- This migration adds workflow_cross_links: an edge between TWO different
-- workflows (or even two nodes in two different workflows). The link
-- itself is static metadata for Phase 1 — FE tree viewer renders the
-- "depends on / triggers" relationship as a badge. Phase 2 Temporal will
-- consume the link to actually fire trigger_workflow activities per
-- docx PART V Phần 2 node catalog.
--
-- Allowed cross dimensions (all valid by construction — only the
-- workspace_id check is enforced; the rest are denormalised for query
-- ergonomics):
--
--   same enterprise, different dept       (Sales → CS)
--   different enterprise, same division   (VinMart Sales → VinMart+ Sales)
--   different division, same group        (Vingroup BĐS Sales → Vingroup Bán lẻ CS)
--   different branch                       (HN Sales → HCM Warehouse)
--   any combination thereof
--
-- The cross_link is workspace-scoped — links cannot escape the SaaS
-- tenant. Within a workspace, the link is permissive.
--
-- Phase 2 (DEFERRED):
--   - Actually trigger target workflow when source step completes
--   - Cross-workspace links (consulting firm coordinating two clients)
--   - Cycle detection across cross-links (Phase 1 only blocks self-loops
--     within one workflow via mig 053 chk_edge_no_self_loop)

-- ─── 1. workflow_cross_links ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS workflow_cross_links (
    link_id                 UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id            UUID            NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,

    -- Source: the workflow + (optional) node that triggers the link.
    -- node_id NULL means "when source workflow completes (any final node)".
    source_workflow_id      UUID            NOT NULL REFERENCES workflows(workflow_id) ON DELETE CASCADE,
    source_node_id          UUID            REFERENCES workflow_nodes(node_id)         ON DELETE SET NULL,

    -- Target: the workflow + (optional) entry node.
    -- target_node_id NULL means "trigger target workflow at its first node".
    target_workflow_id      UUID            NOT NULL REFERENCES workflows(workflow_id) ON DELETE CASCADE,
    target_node_id          UUID            REFERENCES workflow_nodes(node_id)         ON DELETE SET NULL,

    -- Link semantics.
    link_type               VARCHAR(30)     NOT NULL DEFAULT 'triggers',
    -- 'triggers'      = source completes → target fires (one-shot)
    -- 'depends_on'    = target must wait for source to finish
    -- 'notifies'      = source sends a notification to target (no exec)
    -- 'data_handoff'  = source outputs feed target inputs

    -- Optional gating condition + label for FE.
    condition               TEXT,
    label                   VARCHAR(200),

    -- Denormalised attribution columns so the FE tree viewer can render
    -- "links across (group, division, enterprise, dept)" badges without
    -- multi-table joins on every render. Updated via app-layer trigger
    -- on workflow updates (Phase 2 — for now FE re-derives from joins).
    source_enterprise_id    UUID,
    source_department_id    UUID,
    target_enterprise_id    UUID,
    target_department_id    UUID,

    is_active               BOOLEAN         NOT NULL DEFAULT TRUE,

    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_by              UUID,

    CONSTRAINT chk_cross_link_type CHECK (link_type IN (
        'triggers', 'depends_on', 'notifies', 'data_handoff'
    )),
    -- A workflow can't link to itself. Different workflows in the same
    -- enterprise are fine; same workflow in same enterprise is not.
    CONSTRAINT chk_cross_link_no_self_loop CHECK (source_workflow_id <> target_workflow_id)
);

CREATE INDEX IF NOT EXISTS idx_cross_links_source
    ON workflow_cross_links (source_workflow_id, is_active);
CREATE INDEX IF NOT EXISTS idx_cross_links_target
    ON workflow_cross_links (target_workflow_id, is_active);
CREATE INDEX IF NOT EXISTS idx_cross_links_workspace
    ON workflow_cross_links (workspace_id, is_active);

-- Avoid duplicate link declarations between the same (source, target)
-- workflow pair.
CREATE UNIQUE INDEX IF NOT EXISTS uq_cross_link_pair
    ON workflow_cross_links (source_workflow_id, target_workflow_id, link_type)
    WHERE is_active = TRUE;

-- ─── 2. RLS — workspace-scoped (K-1 layered above enterprise) ────────
--
-- Cross-workflow links span TWO workflows that may belong to different
-- enterprises but always the same workspace. Hence we scope RLS by
-- workspace_id, not enterprise_id. This is intentionally a wider scope:
-- enterprise-scoped RLS would prevent legitimate cross-subsidiary links
-- from being read by a Vingroup HQ user who has workspace-wide access.

ALTER TABLE workflow_cross_links ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS isolation_workflow_cross_links ON workflow_cross_links;
CREATE POLICY isolation_workflow_cross_links ON workflow_cross_links
    USING      (workspace_id::text = current_setting('app.current_workspace_id', true))
    WITH CHECK (workspace_id::text = current_setting('app.current_workspace_id', true));

-- ─── 3. Convenience view — links enriched with display names ─────────
--
-- The FE tree viewer joins this to label cross-links readably:
-- "VinMart Sales::Order intake → VinEco Production::Reorder trigger".

CREATE OR REPLACE VIEW v_workflow_cross_links_enriched AS
SELECT
    cl.link_id,
    cl.workspace_id,
    cl.link_type,
    cl.condition,
    cl.label,
    cl.is_active,
    cl.created_at,

    -- Source side
    cl.source_workflow_id,
    sw.name                                  AS source_workflow_name,
    sw.name_vi                               AS source_workflow_name_vi,
    se.name                                  AS source_enterprise_name,
    cl.source_node_id,
    sn.title                                 AS source_node_title,
    sn.title_vi                              AS source_node_title_vi,
    sd.name                                  AS source_department_name,
    sd.dept_type                             AS source_dept_type,

    -- Target side
    cl.target_workflow_id,
    tw.name                                  AS target_workflow_name,
    tw.name_vi                               AS target_workflow_name_vi,
    te.name                                  AS target_enterprise_name,
    cl.target_node_id,
    tn.title                                 AS target_node_title,
    tn.title_vi                              AS target_node_title_vi,
    td.name                                  AS target_department_name,
    td.dept_type                             AS target_dept_type,

    -- Cross-dimension flags for FE badges
    (sw.enterprise_id    <> tw.enterprise_id) AS crosses_enterprise,
    (sw.department_id    <> tw.department_id) AS crosses_department,
    (sw.branch_id        IS DISTINCT FROM tw.branch_id) AS crosses_branch,
    (se.business_division_id IS DISTINCT FROM te.business_division_id) AS crosses_division,
    (se.corporate_group_id   IS DISTINCT FROM te.corporate_group_id)   AS crosses_corporate_group
FROM workflow_cross_links cl
LEFT JOIN workflows   sw ON sw.workflow_id = cl.source_workflow_id
LEFT JOIN workflows   tw ON tw.workflow_id = cl.target_workflow_id
LEFT JOIN workflow_nodes sn ON sn.node_id = cl.source_node_id
LEFT JOIN workflow_nodes tn ON tn.node_id = cl.target_node_id
LEFT JOIN enterprises se ON se.enterprise_id = sw.enterprise_id
LEFT JOIN enterprises te ON te.enterprise_id = tw.enterprise_id
LEFT JOIN departments sd ON sd.department_id = sw.department_id
LEFT JOIN departments td ON td.department_id = tw.department_id;

COMMENT ON VIEW v_workflow_cross_links_enriched IS
    'P15-S11 mig 057 — cross-workflow links with display names + cross-dimension '
    'flags (crosses_enterprise/department/branch/division/corporate_group). FE tree '
    'viewer joins here to render "VinMart Sales → VinEco Production" badges with '
    'tooltips showing which org boundary the link crosses.';

-- ─── 4. Grants ───────────────────────────────────────────────────────

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_app') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON workflow_cross_links            TO kaori_app';
        EXECUTE 'GRANT SELECT                          ON v_workflow_cross_links_enriched TO kaori_app';
    END IF;
END $$;

-- ─── 5. Comments ─────────────────────────────────────────────────────

COMMENT ON TABLE workflow_cross_links IS
    'P15-S11 mig 057 — cross-workflow linkage per anh''s directive 2026-05-15. Workflow A '
    'in dept X of company Y can trigger / depend on / notify / hand data to workflow B '
    'in dept P of company Q, as long as both are in the same workspace. Phase 1 = static '
    'metadata (FE renders); Phase 2 = Temporal runtime fires on link_type=triggers.';
COMMENT ON COLUMN workflow_cross_links.source_node_id IS
    'Optional. NULL means "when source workflow completes (any final node)". When set, '
    'fires only when that specific step finishes.';
COMMENT ON COLUMN workflow_cross_links.target_node_id IS
    'Optional. NULL means "start target workflow at its first node". When set, jump-starts '
    'at that specific step (Phase 2 runtime feature).';
COMMENT ON COLUMN workflow_cross_links.link_type IS
    'triggers = source done → target fires; depends_on = target waits for source; '
    'notifies = source pings target (no exec); data_handoff = source outputs feed target inputs.';
