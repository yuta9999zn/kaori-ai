package com.kaorisystem.auth.scheduled;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

/**
 * B1 PR #1 — sweep stale {@code job_leases} (#14 job orphan).
 *
 * <p>Runs at 02:15 ICT — 15 minutes after {@link BillingAggregationJob}
 * fires, so any crash during the billing cron has had time to time out
 * (the heartbeat thread can't push {@code expires_at} forward if the JVM
 * is dead). The sweeper flips
 *
 * <pre>
 *   UPDATE job_leases
 *      SET status='orphaned', finished_at=NOW(),
 *          error='swept by OrphanJobSweeper'
 *    WHERE status='running' AND expires_at &lt; NOW();
 * </pre>
 *
 * <p>Each orphaned lease is logged at WARN level so on-call sees it (a
 * Phase 2 Prometheus rule will alert on
 * {@code log_messages_total{level="warn", logger="OrphanJobSweeper"} &gt; 0}).
 *
 * <p>The sweeper itself is intentionally NOT wrapped in {@link com.kaorisystem.auth.service.JobLeaseService} —
 * we don't want a turtles-all-the-way-down situation where the orphan
 * sweeper itself orphans. The sweep statement is idempotent (UPDATE WHERE
 * status='running'), so two instances running it concurrently is harmless.
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class OrphanJobSweeper {

    private static final String SWEEP_SQL = """
            UPDATE job_leases
               SET status      = 'orphaned',
                   finished_at = NOW(),
                   error       = COALESCE(error, '') || ' [swept by OrphanJobSweeper]'
             WHERE status     = 'running'
               AND expires_at < NOW()
            RETURNING lease_id, job_name, instance_id, started_at, expires_at
            """;

    private final NamedParameterJdbcTemplate jdbc;

    /**
     * cron = "second minute hour dayOfMonth month dayOfWeek".
     * "0 15 2 * * *" → 02:15 every day. 15-minute gap after 02:00 billing
     * is enough for any sub-1h lease to time out cleanly.
     */
    @Scheduled(cron = "0 15 2 * * *", zone = "Asia/Ho_Chi_Minh")
    public void sweep() {
        long start = System.currentTimeMillis();
        try {
            List<Map<String, Object>> orphaned = jdbc.queryForList(SWEEP_SQL, Map.of());
            long elapsed = System.currentTimeMillis() - start;
            if (orphaned.isEmpty()) {
                log.info("orphan_sweeper.done elapsed_ms={} swept=0", elapsed);
                return;
            }
            // Loud at WARN so the alert rule and grep both pick it up.
            log.warn("orphan_sweeper.done elapsed_ms={} swept={}", elapsed, orphaned.size());
            for (Map<String, Object> row : orphaned) {
                log.warn("orphan_sweeper.orphaned job={} lease_id={} instance={} started={} expires={}",
                        row.get("job_name"),
                        row.get("lease_id"),
                        row.get("instance_id"),
                        row.get("started_at"),
                        row.get("expires_at"));
            }
        } catch (Exception e) {
            // Sweeper failure is rare but worth shouting about — if it
            // breaks, orphan detection silently disappears.
            log.error("orphan_sweeper.failed error={}", e.getMessage(), e);
        }
    }
}
