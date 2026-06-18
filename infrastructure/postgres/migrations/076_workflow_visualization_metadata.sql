-- =====================================================================
-- 076_workflow_visualization_metadata.sql
--
-- Enterprise Workflow Orchestration redesign — BE-side metadata fields
-- that the redesigned Workflow Builder FE needs.
--
-- Per anh 2026-05-17: workflow must visualize branching (if/else/switch),
-- swimlanes, execution state, mandatory vs optional vs conditional. FE
-- redesign defers (FE paused per CLAUDE.md §2), but em ship the BE fields
-- now so the FE picks them up when work resumes.
--
-- 4 ALTERs + 1 new table:
--
-- workflow_nodes:
--   + swimlane_id            UUID — refs department / actor lane (FE renders horizontal swimlane band)
--   + mandatory              VARCHAR(16) — 'mandatory' | 'optional' | 'conditional'
--   + group_id               UUID — subprocess / collapsible group identifier
--
-- workflow_edges:
--   + branch_path            VARCHAR(16) — 'success' | 'fallback' | 'exception' | 'default'
--   + branch_color           VARCHAR(7) — hex color (optional FE override; default per branch_path)
--
-- NEW: workflow_node_execution_state — per-run state separate from designed flow.
--      Lets FE render the SAME workflow definition with different overlays:
--      designed view / running view / completed view / failed view.
--
-- K-rules
-- -------
-- K-1 RLS: enterprise_id denormalized on the new execution_state table.
-- K-2: execution_state is append-only per (workflow_run_id, node_id);
--      state transitions logged, not mutated.
-- K-17: mandatory ≠ side_effect_class — orthogonal concerns. mandatory
--      tells the engine "skip this node if pre-condition fails" vs
--      "always run". side_effect_class tells retry policy.
-- =====================================================================

BEGIN;

-- ─── workflow_nodes — visualization metadata ─────────────────────────


ALTER TABLE workflow_nodes
    ADD COLUMN IF NOT EXISTS swimlane_id UUID,
    ADD COLUMN IF NOT EXISTS mandatory   VARCHAR(16) NOT NULL DEFAULT 'mandatory',
    ADD COLUMN IF NOT EXISTS group_id    UUID;

ALTER TABLE workflow_nodes
    DROP CONSTRAINT IF EXISTS chk_node_mandatory;
ALTER TABLE workflow_nodes
    ADD CONSTRAINT chk_node_mandatory CHECK (mandatory IN (
        'mandatory', 'optional', 'conditional'
    ));

CREATE INDEX IF NOT EXISTS idx_workflow_nodes_swimlane
    ON workflow_nodes(swimlane_id) WHERE swimlane_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_workflow_nodes_group
    ON workflow_nodes(group_id) WHERE group_id IS NOT NULL;


-- ─── workflow_edges — branch path metadata ───────────────────────────


ALTER TABLE workflow_edges
    ADD COLUMN IF NOT EXISTS branch_path  VARCHAR(16) NOT NULL DEFAULT 'default',
    ADD COLUMN IF NOT EXISTS branch_color VARCHAR(7);

ALTER TABLE workflow_edges
    DROP CONSTRAINT IF EXISTS chk_edge_branch_path;
ALTER TABLE workflow_edges
    ADD CONSTRAINT chk_edge_branch_path CHECK (branch_path IN (
        'success', 'fallback', 'exception', 'default', 'true', 'false'
    ));


-- ─── NEW: workflow_node_execution_state ──────────────────────────────


CREATE TABLE IF NOT EXISTS workflow_node_execution_state (
    state_id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id   UUID         NOT NULL,
    workflow_id       UUID         NOT NULL,
    node_id           UUID         NOT NULL,
    enterprise_id     UUID         NOT NULL REFERENCES enterprises(enterprise_id),
    state             VARCHAR(16)  NOT NULL,
    started_at        TIMESTAMPTZ,
    completed_at      TIMESTAMPTZ,
    error_class       VARCHAR(64),
    error_message     TEXT,
    output_summary    TEXT,
    iteration         INTEGER      NOT NULL DEFAULT 1,
    recorded_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_exec_state CHECK (state IN (
        'PENDING', 'WAITING', 'RUNNING', 'COMPLETED', 'FAILED',
        'SKIPPED', 'CANCELLED', 'TIMED_OUT'
    )),
    CONSTRAINT chk_exec_iteration_pos CHECK (iteration > 0)
);

CREATE INDEX IF NOT EXISTS idx_node_exec_state_run
    ON workflow_node_execution_state(workflow_run_id, node_id, iteration);
CREATE INDEX IF NOT EXISTS idx_node_exec_state_workflow
    ON workflow_node_execution_state(workflow_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_node_exec_state_failed
    ON workflow_node_execution_state(enterprise_id, recorded_at DESC)
    WHERE state IN ('FAILED', 'TIMED_OUT');


COMMENT ON COLUMN workflow_nodes.swimlane_id IS
    'mig 076 — refs department or actor lane. FE renders horizontal '
    'swimlane band grouping nodes by owner.';
COMMENT ON COLUMN workflow_nodes.mandatory IS
    'mig 076 — engine skip-policy. mandatory=run always. optional=skip '
    'if precondition fails (no error). conditional=run only when edge '
    'branch_path resolves true.';
COMMENT ON COLUMN workflow_nodes.group_id IS
    'mig 076 — subprocess/collapsible group. FE renders nodes with same '
    'group_id as a single collapsed block. Nested groups via group_id '
    'chains in a future helper table.';
COMMENT ON COLUMN workflow_edges.branch_path IS
    'mig 076 — semantic path identifier for visualization. success/'
    'fallback/exception/default/true/false. FE picks color + arrow '
    'style per path.';
COMMENT ON COLUMN workflow_edges.branch_color IS
    'mig 076 — hex color override (#RRGGBB). NULL = use branch_path '
    'default color from FE theme.';
COMMENT ON TABLE workflow_node_execution_state IS
    'mig 076 — per-run per-node state log. FE overlay renders execution '
    'view over the designed-flow definition. Append-only; iterations '
    'capture retry loops.';

COMMIT;
