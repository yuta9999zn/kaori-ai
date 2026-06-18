-- =====================================================================
-- 112_node_type_ui_schema.sql
--
-- ADR-0034 (B4) — declarative node schema drives the builder UI.
--
-- node_type_catalog.config_schema_json (mig 068) is already the single
-- source of truth for BE config VALIDATION and is already returned by
-- GET /workflow-node-types. This adds an UI-ONLY companion, ui_schema_json,
-- carrying render hints (per-field Vietnamese labels, widget type, grouping,
-- order) so the FE workflow builder renders config forms generically from the
-- schema — no bespoke per-node FE code.
--
-- ui_schema_json is ADDITIVE and NEVER affects validation: BE keeps validating
-- against config_schema_json. Default '{}' means "no hints → render from the
-- JSONSchema alone", so every existing row works untouched.
-- =====================================================================

BEGIN;

ALTER TABLE node_type_catalog
    ADD COLUMN IF NOT EXISTS ui_schema_json JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN node_type_catalog.ui_schema_json IS
    'ADR-0034 B4 — FE-only render hints (field labels_vi / widget / group / order) for the builder. NEVER affects validation; that stays config_schema_json. Default {} = render from the JSONSchema alone.';

COMMIT;
