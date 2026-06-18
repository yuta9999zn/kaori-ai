-- Migration 020: job_leases — single-execution lease for scheduled jobs.
--
-- Purpose
-- =======
-- Phase 2 error-handling spec, B1 PR #1 (#14 job orphan).
--
-- Current state: `BillingAggregationJob` (auth-service, 02:00 ICT) has no
-- crash-resilience. If the pod dies mid-loop, the partially-aggregated
-- enterprises wear stale numbers until 02:00 the next day, and there's no
-- record that the run started but didn't finish — ops can't tell "no cron
-- ran" from "cron ran but crashed". Phase 2 will add more crons (outbox
-- reconciliation, alert-email retry, retrain trigger), so we need a single
-- pattern they all share.
--
-- This table is the lease primitive. A job acquires a row keyed by
-- `lease_id` (uuid) with a TTL; the partial unique index guarantees AT
-- MOST ONE row per `job_name` is in status='running' at a time, so
-- competing instances either acquire or get a UNIQUE violation. A
-- heartbeat thread renews `expires_at`; on success the row flips to
-- status='done'. If the pod crashes, `expires_at` falls behind real time
-- and the OrphanJobSweeper (scheduled 02:15 ICT) flips status='orphaned'
-- so on-call sees it.
--
-- Why a side table instead of an advisory lock alone:
--   * Advisory locks are session-bound and invisible — you can't query
--     "which job is running on which instance right now". Operators
--     debugging at 03:00 need a row they can SELECT.
--   * The `last_heartbeat` column lets the sweeper distinguish "still
--     running" (recent heartbeat) from "crashed" (heartbeat went stale)
--     without having to ping the instance.
--   * Audit trail: every run leaves a row (running → done/orphaned/failed),
--     so we can compute MTBF / MTTR per job by querying history.
--
-- Why uuid PK + partial unique on (job_name) WHERE status='running':
--   * Lets us keep every historical run. A composite PK (job_name,
--     started_at) would do the same, but the partial unique index makes
--     "exactly one running per job" the database-enforced invariant
--     instead of a service-side convention.
--   * Acquire becomes a single INSERT — if another instance is already
--     running, the unique violation surfaces in the same statement.
--
-- Why no RLS:
--   System-level table. Jobs are not tenant-scoped (cron iterates ALL
--   active tenants inside a single lease). Same shape as processed_events
--   in 009_event_outbox.sql.
--
-- Reversibility:
--   DROP TABLE job_leases;
-- (Plus reverting JobLeaseService callers back to bare @Scheduled methods.)
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS job_leases (
    lease_id        UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    job_name        VARCHAR(100) NOT NULL,
    instance_id     UUID         NOT NULL,
    started_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ  NOT NULL,
    last_heartbeat  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    status          VARCHAR(20)  NOT NULL DEFAULT 'running',
    finished_at     TIMESTAMPTZ,
    error           TEXT,
    CONSTRAINT job_leases_status_check
        CHECK (status IN ('running', 'done', 'orphaned', 'failed'))
);

-- THE invariant of this table — at most one running lease per job at any
-- moment. Acquire = INSERT; if another instance holds the lease, the
-- unique violation tells the caller to back off. When status flips off
-- 'running' (done/orphaned/failed), the constraint releases.
CREATE UNIQUE INDEX IF NOT EXISTS uq_job_leases_one_running
    ON job_leases(job_name)
    WHERE status = 'running';

-- Sweeper query — UPDATE WHERE status='running' AND expires_at < NOW().
-- Partial index keeps the planner cheap even as history grows.
CREATE INDEX IF NOT EXISTS idx_job_leases_running_expired
    ON job_leases(expires_at)
    WHERE status = 'running';

-- Operator query — "show me the last 50 runs of this job".
CREATE INDEX IF NOT EXISTS idx_job_leases_started
    ON job_leases(job_name, started_at DESC);

GRANT SELECT, INSERT, UPDATE ON job_leases TO kaori_app;

COMMIT;
