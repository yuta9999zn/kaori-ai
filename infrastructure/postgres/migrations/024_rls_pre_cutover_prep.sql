-- Migration 024: RLS pre-cutover preparation — drop policies on the two
--                 tables that cannot live under tenant-scoped RLS.
--
-- This migration is the FIRST half of a two-step cutover. Today
-- ``kaori_app`` has ``BYPASSRLS=true`` (set in 008), so every existing
-- RLS policy is dormant. The goal of the broader effort is to flip
-- ``ALTER ROLE kaori_app NOBYPASSRLS`` and turn RLS into a real
-- enforcement boundary. That flip lands in a follow-up migration after
-- the prep landed here is smoke-tested.
--
-- Prep work covered here
-- ======================
-- Two tables would break under tenant-scoped RLS regardless of how the
-- application is refactored, so we drop their policies upfront.
-- Removing them now is a no-op behaviour-wise (kaori_app still bypasses
-- everything), but it makes the eventual NOBYPASSRLS flip a one-line
-- change instead of a "and one more migration" surprise.
--
-- 1. ``enterprise_users`` — pre-auth login resolves the user by email
--    alone (``AuthService.findByEmailIgnoreCase``). At that point we
--    don't know the tenant yet, so a tenant-scoped RLS policy would
--    return zero rows and break every login. Every other query on
--    this table already filters by ``enterprise_id`` explicitly (see
--    ``UserRepository.java`` — ``findByEnterpriseId*``,
--    ``countByEnterpriseId*``, ``findByEnterpriseFiltered``,
--    ``countActiveManagersExcluding``), and PR #7's
--    ``scripts/check-tenant-filter.py`` keeps that contract enforced
--    in CI. The defence-in-depth value of RLS on this table is small;
--    the downside (broken login) is total. So we drop RLS here and
--    rely on the application-level filter.
--
-- 2. ``event_outbox`` — the publisher loop in
--    ``services/{data-pipeline,ai-orchestrator}/shared/outbox.py``
--    intentionally reads ALL tenants' pending rows so it can route
--    them to Kafka. It uses bare ``pool.acquire()`` (no
--    ``acquire_for_tenant``) because tenant-iteration IS its job.
--    Adding ``SET row_security = off`` per session would work but
--    requires the publisher to remember the toggle; dropping RLS here
--    is simpler, and the table only carries a short-lived buffer
--    (rows are deleted / marked-published within seconds). The
--    ``enterprise_id`` column stays for forensics + per-tenant queries
--    from the relay's audit surface.
--
-- All OTHER tenant tables keep RLS active. Application code is being
-- refactored alongside this migration to set ``app.enterprise_id`` (or
-- ``row_security = off`` for documented cross-tenant aggregations) in
-- preparation for the NOBYPASSRLS flip.
--
-- What's NOT in this migration (lands later, with smoke test)
-- ===========================================================
-- * ``ALTER ROLE kaori_app NOBYPASSRLS;`` — the actual cutover. A
--   one-line follow-up migration once every per-tenant + cross-tenant
--   call site has been wired through ``acquire_for_tenant`` /
--   ``SET LOCAL row_security = off``. Splitting the work means a
--   broken call site shows up as a CI failure on the cutover PR alone,
--   not as an incident requiring a runtime rollback of multiple
--   pieces.
--
-- Reversibility
-- =============
-- To revert this migration:
--   ALTER TABLE enterprise_users ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE enterprise_users FORCE ROW LEVEL SECURITY;
--   ALTER TABLE event_outbox     ENABLE ROW LEVEL SECURITY;
-- (the policies themselves were not dropped; ALTER ... ENABLE re-arms
-- them.)
--
-- ============================================================

BEGIN;

-- =========================================================================
-- 1. enterprise_users — drop RLS (rationale: pre-auth login by email).
-- =========================================================================
ALTER TABLE enterprise_users NO FORCE ROW LEVEL SECURITY;
ALTER TABLE enterprise_users DISABLE ROW LEVEL SECURITY;

-- =========================================================================
-- 2. event_outbox — drop RLS (rationale: publisher iterates all tenants).
-- =========================================================================
ALTER TABLE event_outbox DISABLE ROW LEVEL SECURITY;

COMMIT;
