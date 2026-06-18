package com.kaorisystem.auth.scheduled;

import com.kaorisystem.auth.service.JobLeaseService;
import com.kaorisystem.auth.service.JobLeaseService.AcquireOutcome;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.List;
import java.util.Map;

/**
 * B1 PR #2 — surface stale {@code event_outbox} rows (#8 data inconsistency).
 *
 * <p>Background: the outbox publisher (Python loop in ai-orchestrator and
 * data-pipeline) reads {@code event_outbox WHERE published_at IS NULL ORDER
 * BY created_at FOR UPDATE SKIP LOCKED}, sends to Kafka, then marks
 * published_at. If the publisher process crashes between Kafka send and
 * the marker UPDATE, the row reappears at the next poll and dedupe at the
 * consumer keeps things correct.
 *
 * <p>The failure mode this job catches is different: the publisher itself
 * stops running (pod crashed, restart loop, network partition that the
 * health check missed). Rows pile up under {@code published_at IS NULL}
 * and stay invisible until someone notices the downstream effect.
 *
 * <p>02:30 ICT (15 min after the orphan sweeper, 30 min after the billing
 * cron) — by then any healthy publisher should have drained recent
 * arrivals. Anything still pending older than 15 minutes is an alert.
 *
 * <p>This job intentionally does NOT republish — that's the publisher's
 * job, and trying to do it from a Java cron crosses the language /
 * service boundary. The job's contract is "tell ops something is stuck",
 * not "fix it". A Phase 2 PR (or this one's PR #6 cascading work) will
 * add a Prometheus alert rule that pages on the WARN log this emits.
 *
 * <p>Wrapped in {@link JobLeaseService} so a multi-instance auth-service
 * deploy never has two pods running this concurrently.
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class OutboxReconciliationJob {

    /** Anything stuck unpublished older than this is reported. */
    private static final String STALE_THRESHOLD = "15 minutes";

    /**
     * Soft alert threshold — single-digit pending rows are typical (publisher
     * is between polls). 100+ means the publisher is wedged and ops should
     * investigate immediately.
     */
    private static final int LOUD_THRESHOLD = 100;

    /**
     * Lease TTL — the sweep itself is sub-second; 5 minutes gives slack
     * for a stuck DB query without letting a crashed pod hold the lease
     * past the next 02:30 firing.
     */
    private static final Duration LEASE_TTL = Duration.ofMinutes(5);

    private static final String SCAN_SQL = """
            SELECT outbox_id, enterprise_id, topic, event_type,
                   created_at, attempts, last_error,
                   trace_context->>'traceparent' AS traceparent
              FROM event_outbox
             WHERE published_at IS NULL
               AND created_at < NOW() - INTERVAL '%s'
             ORDER BY created_at
             LIMIT 500
            """.formatted(STALE_THRESHOLD);

    private static final String COUNT_SQL = """
            SELECT COUNT(*) AS c
              FROM event_outbox
             WHERE published_at IS NULL
               AND created_at < NOW() - INTERVAL '%s'
            """.formatted(STALE_THRESHOLD);

    private final NamedParameterJdbcTemplate jdbc;
    private final JobLeaseService leaseService;

    /**
     * cron = "second minute hour dayOfMonth month dayOfWeek".
     * "0 30 2 * * *" → 02:30 every day. Sits between BillingAggregationJob
     * (02:00) and the OrphanJobSweeper (02:15) with enough gap that nothing
     * normally-running pollutes the report.
     */
    @Scheduled(cron = "0 30 2 * * *", zone = "Asia/Ho_Chi_Minh")
    public void runDaily() {
        AcquireOutcome outcome = leaseService.runWithLease(
                "outbox_reconciliation",
                LEASE_TTL,
                this::scan);
        if (outcome == AcquireOutcome.SKIPPED) {
            log.info("outbox.recon.skipped reason=another_instance_running");
        }
    }

    private void scan() {
        long start = System.currentTimeMillis();
        try {
            Integer total = jdbc.queryForObject(COUNT_SQL, Map.of(), Integer.class);
            int count = total == null ? 0 : total;

            if (count == 0) {
                log.info("outbox.recon.done elapsed_ms={} stale_count=0",
                        System.currentTimeMillis() - start);
                return;
            }

            // Sample up to 500 rows for the log so on-call has something to
            // grep — full count is in the metric.
            List<Map<String, Object>> sample = jdbc.queryForList(SCAN_SQL, Map.of());

            String level = count >= LOUD_THRESHOLD ? "ERROR" : "WARN";
            if (count >= LOUD_THRESHOLD) {
                log.error("outbox.recon.done elapsed_ms={} stale_count={} level={} action=page_on_call",
                        System.currentTimeMillis() - start, count, level);
            } else {
                log.warn("outbox.recon.done elapsed_ms={} stale_count={} level={}",
                        System.currentTimeMillis() - start, count, level);
            }

            for (Map<String, Object> row : sample) {
                log.warn("outbox.recon.stale outbox_id={} enterprise_id={} topic={} event_type={} created_at={} attempts={} traceparent={} last_error={}",
                        row.get("outbox_id"),
                        row.get("enterprise_id"),
                        row.get("topic"),
                        row.get("event_type"),
                        row.get("created_at"),
                        row.get("attempts"),
                        row.get("traceparent"),
                        row.get("last_error"));
            }
        } catch (RuntimeException e) {
            // Shout if the recon job itself can't run — losing this signal
            // means orphaned outbox rows go unnoticed.
            log.error("outbox.recon.failed error={}", e.getMessage(), e);
            throw e;  // let JobLeaseService mark the lease 'failed'
        }
    }
}
