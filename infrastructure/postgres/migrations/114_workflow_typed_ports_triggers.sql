-- =====================================================================
-- 114_workflow_typed_ports_triggers.sql
--
-- ADR-0035 — typed connection ports (B5) + trigger nodes (B6), borrowed
-- from n8n. Both additive; defaults leave every existing workflow + run
-- behaving identically.
--
--   workflow_edges.port_type — 'main' (data flow, the only kind the runner
--     topo-sorts) vs ai_tool / ai_memory / ai_model (SIDE connections that
--     wire an agent to its tools/memory/model, never flow steps).
--   node_type_catalog.is_trigger — marks event/entry node types so the
--     builder shows them as trigger blocks and a workflow's entry is explicit.
-- =====================================================================

BEGIN;

ALTER TABLE workflow_edges
    ADD COLUMN IF NOT EXISTS port_type VARCHAR(16) NOT NULL DEFAULT 'main';

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_edge_port_type'
    ) THEN
        ALTER TABLE workflow_edges
            ADD CONSTRAINT chk_edge_port_type
            CHECK (port_type IN ('main', 'ai_tool', 'ai_memory', 'ai_model'));
    END IF;
END $$;

ALTER TABLE node_type_catalog
    ADD COLUMN IF NOT EXISTS is_trigger BOOLEAN NOT NULL DEFAULT FALSE;

-- Flag the event / entry node types as triggers (B6). Conservative set: the
-- clear event-driven / inbound entry points. Others stay plain data_input.
UPDATE node_type_catalog
   SET is_trigger = TRUE
 WHERE node_type_key IN (
     'scheduled_trigger', 'read_webhook', 'read_form_submission', 'read_email'
 );

COMMENT ON COLUMN workflow_edges.port_type IS
    'ADR-0035 B5 — main (data flow, runner topo-sorts these) | ai_tool/ai_memory/ai_model (side connections wiring an agent; NOT flow steps).';
COMMENT ON COLUMN node_type_catalog.is_trigger IS
    'ADR-0035 B6 — TRUE for event/entry node types (workflow trigger blocks). No runtime effect; builder + ingestion read it.';

COMMIT;
