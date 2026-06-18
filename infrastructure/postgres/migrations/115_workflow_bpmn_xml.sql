-- =====================================================================
-- 115_workflow_bpmn_xml.sql
--
-- Builder pivot 2026-05-29 (WORKFLOW_BUILDER_REDESIGN.md §11): the FE
-- workflow builder becomes a real BPMN editor (bpmn-js). The diagram's
-- source of truth is BPMN 2.0 XML; the runtime still executes
-- workflow_nodes/edges (mapped from the XML by bpmn_mapper.py).
--
-- This migration adds the column that stores the authored BPMN XML.
-- Additive + nullable — every existing workflow keeps working untouched
-- (NULL = no BPMN diagram authored yet; FE renders an empty canvas).
-- =====================================================================

BEGIN;

ALTER TABLE workflows
    ADD COLUMN IF NOT EXISTS bpmn_xml TEXT;

COMMENT ON COLUMN workflows.bpmn_xml IS
    'BPMN 2.0 XML authored in the bpmn-js builder (pivot 2026-05-29). '
    'Diagram source-of-truth; runner executes workflow_nodes/edges mapped '
    'from this via workflow_runtime/bpmn_mapper.py. NULL = not authored yet.';

COMMIT;
