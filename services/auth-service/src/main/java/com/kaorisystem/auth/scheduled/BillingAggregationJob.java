package com.kaorisystem.auth.scheduled;

import com.kaorisystem.auth.service.BillingAggregationService;
import com.kaorisystem.auth.service.BillingAggregationService.BatchResult;
import com.kaorisystem.auth.service.JobLeaseService;
import com.kaorisystem.auth.service.JobLeaseService.AcquireOutcome;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.Duration;

/**
 * F-031 — daily billing aggregation cron.
 *
 * <p>Fires at 02:00 ICT every day. The choice of 02:00 follows the F-011
 * dashboard refresh contract: the dashboard renders with yesterday's numbers
 * up to that hour, then the cron writes today's snapshot before users start
 * the workday.
 *
 * <p>{@code @EnableScheduling} is set on {@link com.kaorisystem.auth.AuthServiceApplication}.
 *
 * <p>B1 PR #1 — wrapped in {@link JobLeaseService} so multi-instance
 * Phase 2 deploys won't double-aggregate (each instance's @Scheduled
 * fires; the lease ensures only one wins) and so a JVM crash mid-run
 * leaves a queryable {@code job_leases} row that the OrphanJobSweeper
 * (02:15 ICT) flips to {@code orphaned} for on-call visibility.
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class BillingAggregationJob {

    /** Long enough that the cron has slack (typical run is seconds), short
     *  enough that the OrphanJobSweeper (02:15 ICT) catches a crashed pod.
     *  Heartbeat thread renews this every TTL/3 = 20 min. */
    private static final Duration LEASE_TTL = Duration.ofHours(1);

    private final BillingAggregationService aggregationService;
    private final JobLeaseService leaseService;

    /**
     * cron = "second minute hour dayOfMonth month dayOfWeek".
     * "0 0 2 * * *" → at 02:00:00 every day.
     * Zone is Asia/Ho_Chi_Minh per CLAUDE.md §10 and the existing F-011 timezone.
     */
    @Scheduled(cron = "0 0 2 * * *", zone = "Asia/Ho_Chi_Minh")
    public void runDaily() {
        long start = System.currentTimeMillis();
        log.info("billing.cron.start instance={}", leaseService.getInstanceId());

        AcquireOutcome outcome = leaseService.runWithLease(
                "billing_aggregation",
                LEASE_TTL,
                () -> {
                    try {
                        BatchResult r = aggregationService.aggregateCurrentMonth();
                        long elapsed = System.currentTimeMillis() - start;
                        log.info("billing.cron.done elapsed_ms={} month={} total={} ok={} failed={}",
                                elapsed, r.billingMonth(), r.enterpriseCount(),
                                r.successCount(), r.failureCount());
                    } catch (RuntimeException e) {
                        // The service catches per-enterprise errors already, so reaching
                        // here means a top-level failure (DB unreachable on the active-
                        // enterprises query). Loud log for on-call; rethrow so the lease
                        // wrapper marks the row status='failed' with this message.
                        log.error("billing.cron.failed error={}", e.getMessage(), e);
                        throw e;
                    }
                });

        if (outcome == AcquireOutcome.SKIPPED) {
            log.info("billing.cron.skipped reason=another_instance_running");
        }
    }
}
