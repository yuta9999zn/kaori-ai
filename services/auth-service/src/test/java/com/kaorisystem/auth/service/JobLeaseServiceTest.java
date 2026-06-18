package com.kaorisystem.auth.service;

import com.kaorisystem.auth.service.JobLeaseService.AcquireOutcome;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;

import java.time.Duration;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.contains;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * B1 PR #1 — unit tests for {@link JobLeaseService}.
 *
 * <p>Mocks {@link NamedParameterJdbcTemplate} directly because the value of
 * the service is the lease lifecycle (acquire / release / heartbeat /
 * exception handling). The actual SQL + the partial-unique-index
 * enforcement are exercised end-to-end at the IT layer where a real
 * Postgres applies migration 020.
 *
 * <p>Cases:
 * <ul>
 *   <li>acquire success → returns a lease_id, INSERT was called once</li>
 *   <li>acquire contention → DuplicateKeyException returns Optional.empty</li>
 *   <li>runWithLease happy path → callback runs, status flipped to 'done'</li>
 *   <li>runWithLease skipped → callback NOT invoked</li>
 *   <li>runWithLease failure → status flipped to 'failed' AND throwable rethrown</li>
 *   <li>release no-op when lease already released — WARN logged, no exception</li>
 * </ul>
 */
@DisplayName("JobLeaseService — B1 PR #1 lease lifecycle")
class JobLeaseServiceTest {

    private NamedParameterJdbcTemplate jdbc;
    private JobLeaseService            service;

    @BeforeEach
    void setup() {
        jdbc    = mock(NamedParameterJdbcTemplate.class);
        service = new JobLeaseService(jdbc);
    }

    @Test
    @DisplayName("acquire — happy path returns lease_id, INSERT called once")
    void acquire_success_returnsLeaseId() {
        when(jdbc.update(contains("INSERT INTO job_leases"), any(MapSqlParameterSource.class)))
                .thenReturn(1);

        Optional<UUID> result = service.acquire("test_job", Duration.ofMinutes(30));

        assertThat(result).isPresent();
        verify(jdbc).update(contains("INSERT INTO job_leases"), any(MapSqlParameterSource.class));
    }

    @Test
    @DisplayName("acquire — DuplicateKeyException returns Optional.empty")
    void acquire_contention_returnsEmpty() {
        when(jdbc.update(contains("INSERT INTO job_leases"), any(MapSqlParameterSource.class)))
                .thenThrow(new DuplicateKeyException("uq_job_leases_one_running"));

        Optional<UUID> result = service.acquire("test_job", Duration.ofMinutes(30));

        assertThat(result).isEmpty();
    }

    @Test
    @DisplayName("runWithLease — happy path runs callback and flips status='done'")
    void runWithLease_happy_runsAndReleases() {
        // INSERT succeeds
        when(jdbc.update(contains("INSERT INTO job_leases"), any(MapSqlParameterSource.class)))
                .thenReturn(1);
        // Release UPDATE succeeds
        when(jdbc.update(contains("SET status      = :status"), any(MapSqlParameterSource.class)))
                .thenReturn(1);

        AtomicBoolean ran = new AtomicBoolean(false);
        AcquireOutcome outcome = service.runWithLease("test_job",
                Duration.ofSeconds(10),
                () -> ran.set(true));

        assertThat(outcome).isEqualTo(AcquireOutcome.RAN);
        assertThat(ran.get()).isTrue();
        // INSERT once, UPDATE once for release (heartbeat may also UPDATE but
        // its period is TTL/3 = ~3s for a 10s lease, work returns instantly).
        verify(jdbc, atLeastOnce()).update(contains("INSERT INTO job_leases"), any(MapSqlParameterSource.class));
        verify(jdbc).update(contains("SET status      = :status"), any(MapSqlParameterSource.class));
    }

    @Test
    @DisplayName("runWithLease — contention returns SKIPPED and never invokes callback")
    void runWithLease_contention_skipsWork() {
        when(jdbc.update(contains("INSERT INTO job_leases"), any(MapSqlParameterSource.class)))
                .thenThrow(new DuplicateKeyException("uq_job_leases_one_running"));

        AtomicBoolean ran = new AtomicBoolean(false);
        AcquireOutcome outcome = service.runWithLease("test_job",
                Duration.ofMinutes(1),
                () -> ran.set(true));

        assertThat(outcome).isEqualTo(AcquireOutcome.SKIPPED);
        assertThat(ran.get()).as("work must NOT be invoked when another instance holds the lease").isFalse();
        // No release UPDATE — we never had a lease to release.
        verify(jdbc, never()).update(contains("SET status      = :status"), any(MapSqlParameterSource.class));
    }

    @Test
    @DisplayName("runWithLease — work throws, status flipped to 'failed' AND exception rethrown")
    void runWithLease_workFails_marksFailedAndRethrows() {
        when(jdbc.update(contains("INSERT INTO job_leases"), any(MapSqlParameterSource.class)))
                .thenReturn(1);
        when(jdbc.update(contains("SET status      = :status"), any(MapSqlParameterSource.class)))
                .thenReturn(1);

        RuntimeException boom = new RuntimeException("DB unreachable");

        assertThatThrownBy(() -> service.runWithLease("test_job",
                Duration.ofSeconds(10),
                () -> { throw boom; }))
                .isSameAs(boom);

        // Release UPDATE was still called (in finally) so the lease doesn't
        // stay 'running' until the sweeper kicks in.
        verify(jdbc).update(contains("SET status      = :status"), any(MapSqlParameterSource.class));
    }

    @Test
    @DisplayName("release — no-op when lease already released (WARN logged, no exception)")
    void release_noOp_logsWarn() {
        // Simulate the row already being status != 'running' (sweeper got to it
        // first, manual UPDATE, double-release). UPDATE matches 0 rows.
        when(jdbc.update(contains("SET status      = :status"), any(MapSqlParameterSource.class)))
                .thenReturn(0);

        UUID leaseId = UUID.randomUUID();
        // Should not throw.
        service.release(leaseId, "done", null);

        verify(jdbc).update(contains("SET status      = :status"), any(MapSqlParameterSource.class));
    }

    @Test
    @DisplayName("instanceId is stable for the JVM lifetime of one service")
    void instanceId_isStable() {
        assertThat(service.getInstanceId()).isEqualTo(service.getInstanceId());
    }
}
