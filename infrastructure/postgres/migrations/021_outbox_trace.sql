-- Migration 021: event_outbox.trace_context — Phase 2 #2/#5 distributed tracing.
--
-- Why
-- ===
-- The outbox publisher reads pending rows + sends to Kafka, then a consumer
-- on a different service picks them up. Today the trace_id created at the
-- HTTP edge dies at the publisher: the consumer creates a fresh trace, so
-- "user uploaded a file → analysis ran" shows up in Tempo as two unrelated
-- traces.
--
-- Storing the W3C ``traceparent`` (and optional ``tracestate``) in the
-- outbox row lets the publisher attach it as a Kafka header AND lets ops
-- query "show me all events from this trace" with a single SQL filter
-- (``WHERE trace_context->>'traceparent' LIKE '00-<trace_id>-%'``).
-- The Phase 2 #5 OutboxReconciliationJob WARN log will be greppable by
-- trace_id once this column is populated.
--
-- Schema
-- ======
-- JSONB so we can extend with span_id / baggage later without a new
-- migration. Nullable because legacy rows produced before this PR
-- have no trace context — consumers must tolerate the NULL case.
--
-- Reversibility
-- =============
--   ALTER TABLE event_outbox DROP COLUMN trace_context;
-- ============================================================

BEGIN;

ALTER TABLE event_outbox
    ADD COLUMN IF NOT EXISTS trace_context JSONB;

COMMENT ON COLUMN event_outbox.trace_context IS
    'W3C trace context captured at enqueue time so the consumer can '
    'continue the trace started at the HTTP edge. '
    '{"traceparent": "00-<trace_id>-<span_id>-<flags>", '
    '"tracestate": "..."}. NULL on legacy rows or rows enqueued '
    'before opentelemetry-instrumentation was wired in.';

-- Operators frequently filter "all outbox rows for this trace" — a
-- functional index on the traceparent extract makes that O(log N).
-- Partial so it costs nothing for the common NULL case.
CREATE INDEX IF NOT EXISTS idx_event_outbox_trace
    ON event_outbox((trace_context->>'traceparent'))
    WHERE trace_context IS NOT NULL;

COMMIT;
