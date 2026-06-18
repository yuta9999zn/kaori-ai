-- =====================================================================
-- 113_node_type_version.sql
--
-- ADR-0034 (B3) — node type_version. K-20 ("no silent vendor upgrade")
-- extended from LLM models to NODE TYPES: a node-type behaviour change
-- bumps its version so existing workflows + run history stay reproducible
-- and auditable, instead of silently changing under them.
--
--   node_type_catalog.type_version — the catalog's current version of a
--     node type (bumped when the executor's behaviour/contract changes).
--   workflow_nodes.type_version — the version a node was BUILT against,
--     snapshotted at creation so a run records what it actually ran.
--
-- Both default 1: every existing row + node is version 1, so nothing
-- changes behaviourally. Full (key, version) executor routing lands when
-- a real v2 executor exists; this migration is the data foundation.
-- =====================================================================

BEGIN;

ALTER TABLE node_type_catalog
    ADD COLUMN IF NOT EXISTS type_version SMALLINT NOT NULL DEFAULT 1;

ALTER TABLE workflow_nodes
    ADD COLUMN IF NOT EXISTS type_version SMALLINT NOT NULL DEFAULT 1;

COMMENT ON COLUMN node_type_catalog.type_version IS
    'ADR-0034 B3 / K-20 — current catalog version of this node type. Bump on a behaviour/contract change so old workflows do not silently shift.';
COMMENT ON COLUMN workflow_nodes.type_version IS
    'ADR-0034 B3 — node-type version this node was built against (snapshot at creation). Run history records what actually ran (reproducibility).';

COMMIT;
