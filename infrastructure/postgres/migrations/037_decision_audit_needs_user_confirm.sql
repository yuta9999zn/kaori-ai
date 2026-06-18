-- Migration 037: reconcile decision_audit_log.needs_user_confirm.
--
-- Why this exists
-- ===============
-- decision_audit_log is defined in BOTH 001_init.sql (line 218) and
-- 002_pipeline.sql (line 117) under different schemas — both use
-- CREATE TABLE IF NOT EXISTS. On a cold-boot via the Postgres
-- docker-entrypoint-initdb.d path, 001 wins, so the resulting table
-- carries 001's columns (including ``llm_provider``) but MISSES
-- ``needs_user_confirm`` — the column 002 added that the schema-review
-- flow needs (used by data-pipeline router to flag low-confidence
-- column mappings that require user confirmation before silver
-- promotion).
--
-- The pilot UAT seed surfaced this when /api/v1/schema/{run_id}/confirm
-- failed with "column needs_user_confirm does not exist". Patched live
-- on the seed DB; this migration makes it durable for every fresh
-- spin-up going forward.
--
-- Why a new migration instead of editing 002
-- ==========================================
-- Per CLAUDE.md §14 Phase 3 close-out, Flyway baselines existing
-- schema at v14. Migrations 001-014 are no longer re-applied on
-- existing databases — they exist only for the cold-boot
-- /docker-entrypoint-initdb.d path. Adding the ALTER here (037 >
-- baseline) means BOTH paths converge:
--
--   1. Cold-boot: 001 creates table without column, 002 skips
--      (IF NOT EXISTS), 037 adds column.
--   2. Existing baselined DB: Flyway picks up 037 on next auth-service
--      startup and adds column if missing.
--
-- Idempotency
-- ===========
-- ``ADD COLUMN IF NOT EXISTS`` is safe to re-run on any DB that
-- already applied the patch (e.g. the pilot seed DB where it landed
-- via live ALTER on 2026-05-05).
--
-- Reversibility
-- =============
--   ALTER TABLE decision_audit_log DROP COLUMN needs_user_confirm;
-- ============================================================

BEGIN;

ALTER TABLE decision_audit_log
    ADD COLUMN IF NOT EXISTS needs_user_confirm BOOLEAN NOT NULL DEFAULT FALSE;

COMMIT;
