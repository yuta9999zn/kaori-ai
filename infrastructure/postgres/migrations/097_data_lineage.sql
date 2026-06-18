-- =====================================================================
-- 097_data_lineage.sql
--
-- P1 of Phase 2.7 (per anh's 2026-05-19 assessment §1B "Add full lineage
-- graph"): single append-only edge table records every transformation
-- across the platform.
--
-- Patterns mirror the existing workflow_events log (mig 094): immutable
-- triggers (no UPDATE / DELETE), per-tenant RLS, monotonic created_at
-- ordering for replay.
--
-- One row per directed edge. Caller writes (from → to) edges via
-- lineage.record_edge(); walkers query forward (downstream) or backward
-- (upstream) to assemble the lineage tree.
--
-- object_kind covers every node-type the platform produces:
--   bronze_file              source PDF/CSV/Image
--   silver_row               cleaned typed row
--   silver_table_row         specific silver table by composite key
--   ontology_entity          customer/transaction/product/...
--   gold_view_row            denormalized view output
--   ai_decision              decision_audit_log row
--   workflow_run             workflow execution
--   workflow_run_node        per-node execution
--   workflow_insight         publish_insight row
--   workflow_alert           publish_alert row
--   workflow_task            create_task row
--   export_file              export_file render result
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS data_lineage_edges (
    edge_id            UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id      UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    from_kind          VARCHAR(64)     NOT NULL,
    from_id            VARCHAR(200)    NOT NULL,
    to_kind            VARCHAR(64)     NOT NULL,
    to_id              VARCHAR(200)    NOT NULL,
    transformation     VARCHAR(128)    NOT NULL,
    run_id             UUID,
    node_id            UUID,
    metadata           JSONB           NOT NULL DEFAULT '{}'::jsonb,
    created_at         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (enterprise_id, from_kind, from_id, to_kind, to_id, transformation)
);

-- Walk indexes — every lookup is "find all edges from X" or "find all
-- edges to Y" within a tenant.
CREATE INDEX IF NOT EXISTS idx_lineage_forward
    ON data_lineage_edges(enterprise_id, from_kind, from_id, created_at);
CREATE INDEX IF NOT EXISTS idx_lineage_backward
    ON data_lineage_edges(enterprise_id, to_kind, to_id, created_at);
CREATE INDEX IF NOT EXISTS idx_lineage_run
    ON data_lineage_edges(run_id, created_at)
    WHERE run_id IS NOT NULL;

-- Immutability — lineage is append-only, never amend.
CREATE OR REPLACE FUNCTION data_lineage_block_mutation()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'data_lineage_edges is append-only (TG_OP=%)', TG_OP;
END;
$$;

DROP TRIGGER IF EXISTS data_lineage_no_update ON data_lineage_edges;
CREATE TRIGGER data_lineage_no_update
    BEFORE UPDATE ON data_lineage_edges
    FOR EACH ROW EXECUTE FUNCTION data_lineage_block_mutation();

DROP TRIGGER IF EXISTS data_lineage_no_delete ON data_lineage_edges;
CREATE TRIGGER data_lineage_no_delete
    BEFORE DELETE ON data_lineage_edges
    FOR EACH ROW EXECUTE FUNCTION data_lineage_block_mutation();

ALTER TABLE data_lineage_edges ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS data_lineage_isolation ON data_lineage_edges;
CREATE POLICY data_lineage_isolation ON data_lineage_edges
    USING (enterprise_id::text = current_setting('app.enterprise_id', true));

COMMIT;
