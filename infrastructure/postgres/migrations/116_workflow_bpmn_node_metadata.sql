-- =====================================================================
-- 116_workflow_bpmn_node_metadata.sql
--
-- Builder pivot 2026-05-29 (WORKFLOW_BUILDER_REDESIGN.md §11, option 2):
-- give BPMN-authored elements a first-class home on workflow_nodes/edges so
-- `POST /workflows/{id}/bpmn/sync` can project the bpmn-js diagram onto the
-- nodes/edges the tree view + (later) runner read. All additive + nullable —
-- every existing node/edge keeps working untouched.
--
--   workflow_nodes
--     bpmn_element_id   — original BPMN element id (round-trip / DI ref)
--     bpmn_type         — bpmn:ServiceTask | bpmn:ExclusiveGateway | …
--     kaori_node_type   — resolved node_type_catalog_key (executor intent)
--     pool_name         — BPMN participant (organisation / system)
--     lane_name         — BPMN lane (role within the pool)  ← "phân theo role"
--     event_definition  — timer | message | error | escalation | …
--     attached_to_ref   — host element id for boundary events
--   workflow_edges
--     flow_kind         — 'sequence' (in-pool) | 'message' (cross-pool)
--     is_default        — TRUE for a gateway/activity default branch
--
-- NOTE: structural node_type (mig 060 enum) + node_type_catalog_key (runner)
-- stay as-is; pool/lane reuse the existing swimlane concept (mig 076) but as
-- human-readable names so the sync is self-contained (no swimlane FK table yet).
-- =====================================================================

BEGIN;

ALTER TABLE workflow_nodes
    ADD COLUMN IF NOT EXISTS bpmn_element_id  VARCHAR(120),
    ADD COLUMN IF NOT EXISTS bpmn_type        VARCHAR(60),
    ADD COLUMN IF NOT EXISTS kaori_node_type  VARCHAR(60),
    ADD COLUMN IF NOT EXISTS pool_name        VARCHAR(200),
    ADD COLUMN IF NOT EXISTS lane_name        VARCHAR(200),
    ADD COLUMN IF NOT EXISTS event_definition VARCHAR(40),
    ADD COLUMN IF NOT EXISTS attached_to_ref  VARCHAR(120);

CREATE INDEX IF NOT EXISTS idx_workflow_nodes_bpmn_element
    ON workflow_nodes (workflow_id, bpmn_element_id)
    WHERE bpmn_element_id IS NOT NULL;

ALTER TABLE workflow_edges
    ADD COLUMN IF NOT EXISTS flow_kind  VARCHAR(16) NOT NULL DEFAULT 'sequence',
    ADD COLUMN IF NOT EXISTS is_default BOOLEAN     NOT NULL DEFAULT FALSE;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_edge_flow_kind'
    ) THEN
        ALTER TABLE workflow_edges
            ADD CONSTRAINT chk_edge_flow_kind
            CHECK (flow_kind IN ('sequence', 'message'));
    END IF;
END $$;

COMMENT ON COLUMN workflow_nodes.pool_name IS
    'mig 116 — BPMN participant (pool). Organisation/system the node belongs to.';
COMMENT ON COLUMN workflow_nodes.lane_name IS
    'mig 116 — BPMN lane (role) within the pool. The "phân chia theo role" axis.';
COMMENT ON COLUMN workflow_nodes.bpmn_type IS
    'mig 116 — exact BPMN element type (bpmn:ServiceTask …). Preserves fidelity '
    'the coarse node_type enum (mig 060) loses.';
COMMENT ON COLUMN workflow_edges.flow_kind IS
    'mig 116 — sequence (within a pool) | message (between pools, BPMN messageFlow).';

COMMIT;
