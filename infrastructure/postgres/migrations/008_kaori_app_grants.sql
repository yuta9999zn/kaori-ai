-- Migration 008: Prepare kaori_app role for DSN cutover (G4b, step 1).
--
-- Goal: services switch their DATABASE_URL from `kaori` (superuser) to
-- `kaori_app`, but observable behavior stays identical. RLS enforcement
-- happens later, in migration 009.
--
-- Why BYPASSRLS=true here:
--   With BYPASSRLS the row-level policies in 005_rls.sql are silently
--   skipped exactly as they are for the superuser today. So once the
--   DSNs flip, every existing query keeps returning the same rows.
--   009 flips this off and turns RLS into a real enforcement boundary.
--
-- Why DEFAULT PRIVILEGES:
--   006/007 added explicit per-table GRANTs because no defaults were
--   set. Future migrations would have to remember the same. Setting
--   defaults now means new tables created by `kaori` (the migration
--   runner / POSTGRES_USER) are auto-granted to kaori_app.
--
-- Why a one-off DELETE grant on silver_rows:
--   data-pipeline/routers/clean.py:196 issues
--     "DELETE FROM silver_rows WHERE run_id=$1 AND enterprise_id=$2"
--   to drop prior-run silver data when re-cleaning. kaori_app today
--   has SELECT/INSERT/UPDATE only (from 005_rls.sql:22), so the DSN
--   swap would break that path. This catches up the missing privilege
--   without broadening DELETE to other tables (silver is the only
--   place we delete in the python services).
--
-- Reversibility — to roll back this migration:
--   ALTER ROLE kaori_app NOBYPASSRLS;
--   REVOKE DELETE ON silver_rows FROM kaori_app;
--   ALTER DEFAULT PRIVILEGES FOR ROLE kaori IN SCHEMA public
--       REVOKE SELECT, INSERT, UPDATE ON TABLES FROM kaori_app;
--   ALTER DEFAULT PRIVILEGES FOR ROLE kaori IN SCHEMA public
--       REVOKE USAGE, SELECT ON SEQUENCES FROM kaori_app;
-- (Reverting role grants does not drop the role; existing per-table
--  grants from 001/005/006/007 remain so legacy queries still work.)

-- 1. Keep RLS bypassed for now. Behavior-preserving.
ALTER ROLE kaori_app BYPASSRLS;

-- 2. Catch up the one missing privilege the DSN swap would expose.
GRANT DELETE ON silver_rows TO kaori_app;

-- 3. Auto-grant future tables/sequences to kaori_app.
--    FOR ROLE kaori — defaults attach to objects created by that role.
--    Migrations run as POSTGRES_USER=kaori (see docker-compose.yml:12),
--    so this covers anything 009+ creates.
ALTER DEFAULT PRIVILEGES FOR ROLE kaori IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE ON TABLES TO kaori_app;

ALTER DEFAULT PRIVILEGES FOR ROLE kaori IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO kaori_app;
