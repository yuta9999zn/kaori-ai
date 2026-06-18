-- Migration 017: subscription_change_requests
--                 (F-030 — Subscription & Quota, Phase 1 close-out)
--
-- Phase 1 ships an "upgrade request" workflow without auto-provisioning:
-- the MANAGER clicks Upgrade, we record the intent here, and a Kaori
-- staff member processes it manually (changes workspaces.plan_code +
-- emails confirmation). Phase 2 wires payment + automatic provisioning
-- against this same table — F-030 is the entry point, the audit trail,
-- and the "do we already have a pending request?" guard.
--
-- The unique partial index is what gives us idempotency on the FE: clicking
-- "Upgrade" twice quickly does not create two pending rows. The "WHERE
-- status='PENDING'" predicate keeps APPROVED/REJECTED rows around for
-- audit without blocking new requests after the previous one was
-- processed.

BEGIN;

CREATE TABLE IF NOT EXISTS subscription_change_requests (
    request_id      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id   UUID            NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    current_plan    VARCHAR(20)     NOT NULL,
    requested_plan  VARCHAR(20)     NOT NULL REFERENCES subscription_plans(plan_code),
    status          VARCHAR(20)     NOT NULL DEFAULT 'PENDING',
    requested_by    UUID            REFERENCES enterprise_users(user_id),
    requested_at    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    processed_at    TIMESTAMPTZ,
    processed_by    UUID,
    notes           TEXT,
    CONSTRAINT chk_change_request_status CHECK (
        status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')
    ),
    CONSTRAINT chk_change_request_different_plan CHECK (
        current_plan <> requested_plan
    )
);

-- Index for the per-tenant history view + the FE "is there an open request?" check.
CREATE INDEX IF NOT EXISTS idx_scr_enterprise_requested
    ON subscription_change_requests(enterprise_id, requested_at DESC);

-- Partial uniqueness: at most ONE pending request per tenant.
-- Approved / rejected rows stay around for audit and don't block new requests.
CREATE UNIQUE INDEX IF NOT EXISTS uq_scr_one_pending_per_enterprise
    ON subscription_change_requests(enterprise_id)
    WHERE status = 'PENDING';

COMMENT ON TABLE subscription_change_requests IS
    'F-030 — MANAGER-initiated upgrade requests. Phase 1: status set to PENDING; '
    'Kaori staff processes manually (no auto-provisioning yet). Phase 2 ties payment + '
    'workspaces.plan_code change to APPROVED transitions on this table.';

COMMENT ON COLUMN subscription_change_requests.current_plan IS
    'Snapshot of workspaces.plan_code at the time of the request — protects against '
    'races if the plan changes between request and processing.';

COMMIT;
