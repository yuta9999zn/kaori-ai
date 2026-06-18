package com.kaorisystem.auth.scheduled;

import com.kaorisystem.auth.service.JobLeaseService;
import com.kaorisystem.auth.service.JobLeaseService.AcquireOutcome;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;

import java.time.Duration;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.contains;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * B1 PR #2 — unit tests for {@link OutboxReconciliationJob}.
 *
 * <p>Mocks {@link NamedParameterJdbcTemplate} + {@link JobLeaseService}.
 * The SQL is exercised end-to-end at the IT layer (real Postgres with
 * migration 009 applied). Cases here cover the lease/scan branch logic
 * and threshold escalation.
 */
@DisplayName("OutboxReconciliationJob — B1 PR #2 stale-outbox sweep")
class OutboxReconciliationJobTest {

    private NamedParameterJdbcTemplate jdbc;
    private JobLeaseService            lease;
    private OutboxReconciliationJob    job;

    @BeforeEach
    void setup() {
        jdbc  = mock(NamedParameterJdbcTemplate.class);
        lease = mock(JobLeaseService.class);
        job   = new OutboxReconciliationJob(jdbc, lease);

        // Default — lease grants and runs the work synchronously, mirroring
        // the real service's contract. runWithLease returns AcquireOutcome
        // (non-void) so when().thenAnswer() is the correct stubbing form.
        when(lease.runWithLease(eq("outbox_reconciliation"), any(Duration.class), any(Runnable.class)))
                .thenAnswer(inv -> {
                    Runnable work = inv.getArgument(2);
                    work.run();
                    return AcquireOutcome.RAN;
                });
    }

    @Test
    @DisplayName("happy path — zero stale rows logs done and returns")
    void scan_zeroStale_logsDoneAndReturns() {
        when(jdbc.queryForObject(contains("COUNT(*)"), any(Map.class), eq(Integer.class)))
                .thenReturn(0);

        job.runDaily();

        // SCAN_SQL never runs when count = 0 (avoids loading 0 rows).
        verify(jdbc, never()).queryForList(anyString(), any(Map.class));
    }

    @Test
    @DisplayName("warn path — count between 1 and 99 logs WARN, scans sample")
    void scan_smallCount_warns() {
        when(jdbc.queryForObject(contains("COUNT(*)"), any(Map.class), eq(Integer.class)))
                .thenReturn(5);
        // Use HashMap (not Map.of) — Map.of rejects null values, and
        // last_error is nullable in the real schema.
        java.util.Map<String, Object> r1 = new java.util.HashMap<>();
        r1.put("outbox_id", "00000000-0000-0000-0000-000000000001");
        r1.put("enterprise_id", "ent-1");
        r1.put("topic", "kaori.x");
        r1.put("event_type", "evt");
        r1.put("created_at", "2026-04-30T01:00:00Z");
        r1.put("attempts", 0);
        r1.put("last_error", null);
        java.util.Map<String, Object> r2 = new java.util.HashMap<>(r1);
        r2.put("outbox_id", "00000000-0000-0000-0000-000000000002");
        when(jdbc.queryForList(contains("SELECT outbox_id"), any(Map.class)))
                .thenReturn(List.of(r1, r2));

        job.runDaily();

        // Sample WAS pulled at this severity so on-call has greppable rows.
        verify(jdbc).queryForList(contains("SELECT outbox_id"), any(Map.class));
    }

    @Test
    @DisplayName("error path — count >= 100 logs ERROR + still scans sample")
    void scan_loudThreshold_errorsAndScans() {
        when(jdbc.queryForObject(contains("COUNT(*)"), any(Map.class), eq(Integer.class)))
                .thenReturn(150);
        when(jdbc.queryForList(contains("SELECT outbox_id"), any(Map.class)))
                .thenReturn(List.of());

        job.runDaily();

        verify(jdbc).queryForList(contains("SELECT outbox_id"), any(Map.class));
    }

    @Test
    @DisplayName("lease skipped — count query never runs")
    void runDaily_leaseSkipped_doesNothing() {
        // Override the default — lease refuses, work callback never invoked.
        when(lease.runWithLease(eq("outbox_reconciliation"), any(Duration.class), any(Runnable.class)))
                .thenReturn(AcquireOutcome.SKIPPED);

        job.runDaily();

        verify(jdbc, never()).queryForObject(anyString(), any(Map.class), any(Class.class));
    }

    @Test
    @DisplayName("scan throws — exception propagates so lease marks 'failed'")
    void scan_dbFails_propagates() {
        when(jdbc.queryForObject(contains("COUNT(*)"), any(Map.class), eq(Integer.class)))
                .thenThrow(new org.springframework.dao.DataAccessResourceFailureException("DB down"));

        // The lease wrapper rethrows so its finally block can mark the lease
        // 'failed' instead of leaving it 'running' until the orphan sweeper.
        assertThatThrownBy(() -> job.runDaily())
                .isInstanceOf(org.springframework.dao.DataAccessResourceFailureException.class);
    }
}
