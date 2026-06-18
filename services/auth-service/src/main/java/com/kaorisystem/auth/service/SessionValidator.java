package com.kaorisystem.auth.service;

import com.kaorisystem.auth.model.AdminSession;
import com.kaorisystem.auth.repository.AdminSessionRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;
import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

/**
 * Single source of truth for "is this admin session still alive?"
 *
 * <p>Called by {@link com.kaorisystem.auth.security.TrustedGatewayAuthFilter}
 * once per authenticated request. Combines four jobs into one read path:
 *
 * <ol>
 *   <li>Reject revoked sessions.</li>
 *   <li>Enforce <b>idle timeout</b> ({@code kaori.session.idle-timeout-seconds},
 *       default 1800 = 30 minutes since {@code last_active_at}).</li>
 *   <li>Enforce <b>absolute timeout</b>
 *       ({@code kaori.session.absolute-timeout-seconds}, default 86400 = 24h
 *       since {@code created_at}).</li>
 *   <li>Update {@code last_active_at} so the next idle check resets.</li>
 * </ol>
 *
 * <p>Result caching: a successful validation caches "valid" in Redis with
 * a 60-second TTL. While the cache is hot, no DB round-trip happens — at
 * peak that lets the auth filter run in single-digit ms. The cache window
 * is intentionally smaller than the idle/absolute thresholds so a hot
 * cache cannot hide an expiry beyond the cooldown.
 *
 * <p>Auto-revoke: on idle / absolute timeout the row is updated to
 * {@code revoked_at = NOW(), revoke_reason = 'idle_timeout' | 'absolute_timeout'}
 * so the user-facing /platform/security/sessions list reflects the cause.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class SessionValidator {

    public enum Status { VALID, REVOKED, IDLE_EXPIRED, ABSOLUTE_EXPIRED, NOT_FOUND }

    public record Result(Status status, String reason) {
        public static Result valid()              { return new Result(Status.VALID, null); }
        public static Result revoked(String r)    { return new Result(Status.REVOKED, r); }
        public static Result idleExpired()        { return new Result(Status.IDLE_EXPIRED, "idle_timeout"); }
        public static Result absoluteExpired()    { return new Result(Status.ABSOLUTE_EXPIRED, "absolute_timeout"); }
        public static Result notFound()           { return new Result(Status.NOT_FOUND, null); }
    }

    /** ~60-second window where a hot session is short-circuited from DB. */
    private static final Duration CACHE_TTL = Duration.ofSeconds(60);

    private final AdminSessionRepository sessionRepo;
    private final StringRedisTemplate    redis;
    /** Optional — present when the audit service bean is on the classpath. */
    private final ObjectProvider<PlatformAdminAuditService> auditServiceProvider;

    @Value("${kaori.session.idle-timeout-seconds:1800}")
    private long idleTimeoutSeconds;

    @Value("${kaori.session.absolute-timeout-seconds:86400}")
    private long absoluteTimeoutSeconds;

    /**
     * Validate + touch in a single call. Idempotent for repeated requests
     * inside the {@link #CACHE_TTL} window — only the first one hits Postgres.
     *
     * <p>Wrapped in REQUIRES_NEW so the auth filter's call cannot be polluted
     * by the in-flight outer transaction (filters run before MVC handlers).
     */
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public Result validateAndTouch(UUID sessionId) {
        return validateAndTouch(sessionId, null);
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public Result validateAndTouch(UUID sessionId, String ipAddress) {
        if (sessionId == null) return Result.notFound();
        String key = "session_status:" + sessionId;

        // Hot path — cached "valid" verdict from a prior call within the cooldown
        String cached = safeGet(key);
        if ("valid".equals(cached)) return Result.valid();
        if (cached != null) {
            // Cached negative verdict — short-circuit. The cache TTL bounds
            // staleness; if the row was un-revoked manually (we don't expose
            // that today) it would resurface after the TTL.
            return switch (cached) {
                case "revoked"  -> Result.revoked(null);
                case "idle"     -> Result.idleExpired();
                case "absolute" -> Result.absoluteExpired();
                case "missing"  -> Result.notFound();
                default         -> Result.notFound();
            };
        }

        Optional<AdminSession> opt = sessionRepo.findById(sessionId);
        if (opt.isEmpty()) {
            safeSet(key, "missing", Duration.ofSeconds(30));
            return Result.notFound();
        }
        AdminSession s = opt.get();

        if (s.getRevokedAt() != null) {
            safeSet(key, "revoked", Duration.ofSeconds(30));
            return Result.revoked(s.getRevokeReason());
        }

        Instant now = Instant.now();
        if (absoluteTimeoutSeconds > 0
                && s.getCreatedAt().plusSeconds(absoluteTimeoutSeconds).isBefore(now)) {
            sessionRepo.revokeBySessionId(sessionId, now, "absolute_timeout");
            safeSet(key, "absolute", Duration.ofSeconds(30));
            log.info("admin.session.expired session_id={} reason=absolute_timeout", sessionId);
            emitRevokeAudit(s.getAdminId(), sessionId, "absolute_timeout", ipAddress);
            return Result.absoluteExpired();
        }
        if (idleTimeoutSeconds > 0
                && s.getLastActiveAt().plusSeconds(idleTimeoutSeconds).isBefore(now)) {
            sessionRepo.revokeBySessionId(sessionId, now, "idle_timeout");
            safeSet(key, "idle", Duration.ofSeconds(30));
            log.info("admin.session.expired session_id={} reason=idle_timeout", sessionId);
            emitRevokeAudit(s.getAdminId(), sessionId, "idle_timeout", ipAddress);
            return Result.idleExpired();
        }

        // Valid — cheap UPDATE last_active_at and cache "valid" for the cooldown
        sessionRepo.touchLastActive(sessionId, now);
        safeSet(key, "valid", CACHE_TTL);
        return Result.valid();
    }

    /**
     * Best-effort audit row for the auto-revoke path. Identical shape to
     * {@code AdminSecurityService.revokeSession}'s manual-revoke audit, just
     * with a system-supplied reason. Failure is swallowed by
     * {@code PlatformAdminAuditService}, so this never breaks the auth filter.
     */
    private void emitRevokeAudit(UUID adminId, UUID sessionId, String reason, String ipAddress) {
        var audit = auditServiceProvider.getIfAvailable();
        if (audit == null) return;
        audit.recordAudit(adminId, PlatformAdminAuditService.EVT_SESSION_REVOKED,
                null,        // actor_id null — system-driven, not a human action
                null, "SYSTEM",
                sessionId.toString(), "reason=" + reason, ipAddress);
    }

    /**
     * Drop the Redis cache for a session — used when a row is revoked
     * out-of-band (logout, manual revoke, password reset) so the next
     * request reflects the new state immediately rather than waiting for
     * the cooldown to lapse.
     */
    public void invalidateCache(UUID sessionId) {
        if (sessionId == null) return;
        try { redis.delete("session_status:" + sessionId); }
        catch (Exception e) { /* best effort — Redis hiccup must not break logout */ }
    }

    // ---- Redis safety: never let a Redis blip break authentication ----

    private String safeGet(String key) {
        try { return redis.opsForValue().get(key); }
        catch (Exception e) {
            log.debug("redis.get_failed key={} err={}", key, e.toString());
            return null;
        }
    }

    private void safeSet(String key, String value, Duration ttl) {
        try { redis.opsForValue().set(key, value, ttl.getSeconds(), TimeUnit.SECONDS); }
        catch (Exception e) {
            log.debug("redis.set_failed key={} err={}", key, e.toString());
        }
    }
}
