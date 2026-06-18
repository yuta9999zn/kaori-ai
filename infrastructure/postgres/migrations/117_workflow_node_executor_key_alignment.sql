-- =====================================================================
-- 117_workflow_node_executor_key_alignment.sql
--
-- "Làm rõ — không hardcode mơ hồ" (anh 2026-05-29). Fixes a latent
-- schema↔runtime mismatch found while wiring the BPMN sync to the runner:
--
--   The runner / state_store / reconciler all read
--       workflow_nodes.node_type_catalog_key   (executor key)
--       workflow_nodes.config_json              (node config)
--       workflow_edges.condition_expr           (edge condition)
--   but NO migration ever created those columns — the real columns are
--   `config` (mig 053) and `condition` (mig 053), and the executor-key
--   column was simply missing. The run path only ever passed because tests
--   mock the DB; against a migrated Postgres it would error on the
--   non-existent columns.
--
-- Resolution — ONE canonical column per concept (no drift):
--   • node_type_catalog_key  — the executor key the catalog (mig 068),
--       templates (mig 069) and runner already name. mig 116 added this
--       concept as `kaori_node_type`; rename it to the canonical name so
--       there is a single source of truth. The runner reads it directly.
--   • config / condition stay as-is; the runner aliases them
--       (`config AS config_json`, `condition AS condition_expr`) in its
--       SELECTs — no duplicate columns to keep in sync.
--
-- Additive/rename only; data preserved.
-- =====================================================================

BEGIN;

-- Consolidate the executor-key column onto the system-wide canonical name.
DO $$ BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'workflow_nodes' AND column_name = 'kaori_node_type'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'workflow_nodes' AND column_name = 'node_type_catalog_key'
    ) THEN
        ALTER TABLE workflow_nodes RENAME COLUMN kaori_node_type TO node_type_catalog_key;
    END IF;
END $$;

-- Safety net for DBs that never ran mig 116 (column simply absent).
ALTER TABLE workflow_nodes
    ADD COLUMN IF NOT EXISTS node_type_catalog_key VARCHAR(60);

CREATE INDEX IF NOT EXISTS idx_workflow_nodes_catalog_key
    ON workflow_nodes (node_type_catalog_key)
    WHERE node_type_catalog_key IS NOT NULL;

COMMENT ON COLUMN workflow_nodes.node_type_catalog_key IS
    'mig 117 — executor key (references node_type_catalog.node_type_key, mig 068). '
    'The runner routes on this. Populated by BPMN sync (resolved key), '
    'template clone, and the builder. NULL = design-only node (no executor).';

COMMIT;
