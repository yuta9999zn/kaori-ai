package com.kaorisystem.auth.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Service;

import java.sql.Timestamp;
import java.time.Duration;
import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;

/**
 * B1 PR #1 — single-execution lease for scheduled jobs (#14 job orphan).
 *
 * <p>Wraps a {@code Runnable} in three steps:
 * <ol>
 *   <li><b>acquire</b> — INSERT a row into {@code job_leases} with status
 *     {@code running} and an {@code expires_at} ahead of NOW. The partial
 *     unique index {@code uq_job_leases_one_running} guarantees only one
 *     instance acquires; the loser sees a {@link DuplicateKeyException}
 *     and the call returns {@link AcquireOutcome#SKIPPED}.</li>
 *   <li><b>heartbeat</b> — a daemon thread renews {@code last_heartbeat}
 *     and pushes {@code expires_at} forward every {@code ttl/3}. So a
 *     job with TTL=1h heartbeats every 20 min; the OrphanJobSweeper
 *     considers a lease dead once {@code expires_at < NOW()}.</li>
 *   <li><b>release</b> — finally block flips the row to {@code done} (or
 *     {@code failed}) and stops the heartbeat. If the JVM dies between
 *     the work and this UPDATE, the heartbeat thread also dies with it
 *     and {@code expires_at} eventually trips the sweeper — that's the
 *     orphan-detection path.</li>
 * </ol>
 *
 * <p>Designed to be called from any {@code @Scheduled} job. The first
 * caller is {@link com.kaorisystem.auth.scheduled.BillingAggregationJob}
 * (B1 PR #1); future scheduled jobs (outbox reconciliation in B1 PR #2,
 * etc.) reuse the same wrapper.
 */
@Service
@Slf4j
public class JobLeaseService {

    /**
     * Heartbeat at TTL/3 — gives two missed beats before the lease expires.
     * For TTL=1h: heartbeat every 20 min, lease expires at 60 min.
     */
    private static final int HEARTBEAT_DIVISOR = 3;

    private static final String INSERT_SQL = """
            INSERT INTO job_leases
                (lease_id, job_name, instance_id, started_at,
                 expires_at, last_heartbeat, status)
            VALUES
                (:leaseId, :jobName, :instanceId, :startedAt,
                 :expiresAt, :startedAt, 'running')
            """;

    private static final String HEARTBEAT_SQL = """
            UPDATE job_leases
               SET last_heartbeat = :now,
                   expires_at     = :expiresAt
             WHERE lease_id = :leaseId
               AND status   = 'running'
            """;

    private static final String RELEASE_SQL = """
            UPDATE job_leases
               SET status      = :status,
                   finished_at = :now,
                   error       = :error
             WHERE lease_id = :leaseId
               AND status   = 'running'
            """;

    private final NamedParameterJdbcTemplate jdbc;
    private final UUID instanceId = UUID.randomUUID();
    private final ScheduledExecutorService heartbeatExecutor =
            Executors.newScheduledThreadPool(2, r -> {
                Thread t = new Thread(r, "job-lease-heartbeat");
                t.setDaemon(true);
                return t;
            });

    public JobLeaseService(NamedParameterJdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /** Stable per-JVM identifier so operators can correlate "which pod owned that lease". */
    public UUID getInstanceId() {
        return instanceId;
    }

    /**
     * Run {@code work} under a lease named {@code jobName} with the given TTL.
     * Returns {@link AcquireOutcome#RAN} if this instance held the lease and
     * the work completed (success or business-side exception caught upstream
     * — we still flip status='done' as long as no Throwable escaped); returns
     * {@link AcquireOutcome#SKIPPED} if another instance already held it.
     *
     * <p>If {@code work} throws, the lease is flipped to status='failed' with
     * the exception message stored in {@code error}, then the throwable is
     * rethrown so the caller's existing try/catch / scheduled-error logging
     * still fires.
     */
    public AcquireOutcome runWithLease(String jobName, Duration ttl, Runnable work) {
        Optional<UUID> leaseIdOpt = acquire(jobName, ttl);
        if (leaseIdOpt.isEmpty()) {
            log.info("job_lease.skip job={} reason=already_running instance={}",
                    jobName, instanceId);
            return AcquireOutcome.SKIPPED;
        }
        UUID leaseId = leaseIdOpt.get();
        ScheduledFuture<?> heartbeat = startHeartbeat(leaseId, ttl);
        try {
            work.run();
            release(leaseId, "done", null);
            return AcquireOutcome.RAN;
        } catch (RuntimeException e) {
            release(leaseId, "failed", trimError(e));
            throw e;
        } finally {
            heartbeat.cancel(false);
        }
    }

    /**
     * INSERT a lease row. Returns the lease_id on success, empty on contention
     * (another instance holds the running lease for this job_name). Any other
     * SQL error propagates so we don't silently lose visibility into DB
     * problems.
     */
    Optional<UUID> acquire(String jobName, Duration ttl) {
        UUID    leaseId  = UUID.randomUUID();
        Instant now      = Instant.now();
        Instant expires  = now.plus(ttl);
        try {
            jdbc.update(INSERT_SQL, new MapSqlParameterSource()
                    .addValue("leaseId",    leaseId)
                    .addValue("jobName",    jobName)
                    .addValue("instanceId", instanceId)
                    .addValue("startedAt",  Timestamp.from(now))
                    .addValue("expiresAt",  Timestamp.from(expires)));
            log.info("job_lease.acquire job={} lease_id={} instance={} expires_at={}",
                    jobName, leaseId, instanceId, expires);
            return Optional.of(leaseId);
        } catch (DuplicateKeyException e) {
            // Partial unique index uq_job_leases_one_running tripped — another
            // instance is mid-run. Caller decides what to do (cron usually skips).
            return Optional.empty();
        }
    }

    /**
     * Release a lease — flip status off 'running' and stop heartbeats. Safe
     * to call multiple times: the WHERE clause requires status='running' so
     * a second call no-ops.
     */
    void release(UUID leaseId, String status, String error) {
        int rows = jdbc.update(RELEASE_SQL, new MapSqlParameterSource()
                .addValue("leaseId", leaseId)
                .addValue("status",  status)
                .addValue("now",     Timestamp.from(Instant.now()))
                .addValue("error",   error));
        if (rows == 0) {
            // Lease was already released (orphaned by sweeper, manual UPDATE,
            // or double-release). Not an error per se, but worth a WARN so
            // it's visible.
            log.warn("job_lease.release.no_op lease_id={} attempted_status={}",
                    leaseId, status);
        }
    }

    private ScheduledFuture<?> startHeartbeat(UUID leaseId, Duration ttl) {
        long periodMs = Math.max(1_000L, ttl.toMillis() / HEARTBEAT_DIVISOR);
        return heartbeatExecutor.scheduleAtFixedRate(
                () -> {
                    try {
                        Instant now      = Instant.now();
                        Instant expires  = now.plus(ttl);
                        int rows = jdbc.update(HEARTBEAT_SQL, new MapSqlParameterSource()
                                .addValue("leaseId",   leaseId)
                                .addValue("now",       Timestamp.from(now))
                                .addValue("expiresAt", Timestamp.from(expires)));
                        if (rows == 0) {
                            // Lease no longer 'running' — sweeper marked it
                            // orphaned, or release already ran. Nothing to
                            // refresh; the scheduled task will still get
                            // cancelled by the runWithLease finally block.
                            log.warn("job_lease.heartbeat.no_op lease_id={}", leaseId);
                        }
                    } catch (RuntimeException e) {
                        // Don't kill the heartbeat thread on a transient DB
                        // blip — log and let the next tick try again. If the
                        // outage outlasts the TTL, the sweeper will mark the
                        // lease orphaned and operators will see it.
                        log.error("job_lease.heartbeat.failed lease_id={} error={}",
                                leaseId, e.getMessage());
                    }
                },
                periodMs, periodMs, TimeUnit.MILLISECONDS);
    }

    private static String trimError(Throwable t) {
        String msg = t.getMessage();
        if (msg == null) msg = t.getClass().getSimpleName();
        return msg.length() > 1000 ? msg.substring(0, 1000) : msg;
    }

    /** Outcome of {@link #runWithLease}. */
    public enum AcquireOutcome {
        /** This instance acquired the lease and ran the work. */
        RAN,
        /** Another instance was already running the job; this call did nothing. */
        SKIPPED
    }
}
