-- =====================================================================
-- 100_quota_fail_open_knob.sql
--
-- F2 of chaos-matrix.md Phase 3 follow-up: per-quota-type fail-open knob.
--
-- Some quotas SHOULD fail-CLOSED on infra error (workflow_concurrent —
-- losing the lock could let too many concurrent runs through, defeating
-- the throttle). Others SHOULD fail-OPEN (llm_tokens_external — a
-- transient DB blip shouldn't 5xx the LLM call; we'd rather lose a
-- counter increment than break the user-facing path).
--
-- Default = TRUE (fail-open) to keep current behaviour. Operators who
-- want strict enforcement flip per-row.
-- =====================================================================

BEGIN;

ALTER TABLE tenant_quotas
    ADD COLUMN IF NOT EXISTS fail_open BOOLEAN NOT NULL DEFAULT TRUE;

COMMENT ON COLUMN tenant_quotas.fail_open IS
    'F2 chaos-matrix follow-up — when TRUE (default), check_and_consume '
    'returns a sentinel QuotaCheck on infra error (pool/timeout/conn '
    'refused) instead of raising. Set FALSE for quotas where losing '
    'the gate is worse than 5xx-ing the caller (workflow_concurrent).';

-- Flip workflow_concurrent to fail-CLOSED: losing the throttle could
-- allow runaway concurrent workflow_runs (DoS from a single tenant).
-- Better to 5xx the run-start than admit unbounded concurrency.
UPDATE tenant_quotas
SET fail_open = FALSE
WHERE quota_type = 'workflow_concurrent';

-- Pin the default for future seeds in 099 by also updating the seed
-- block — but mig 099 has already run, so this is documentation only.

COMMIT;
