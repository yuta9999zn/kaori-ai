package com.kaorisystem.auth.service;

import com.kaorisystem.auth.model.AdminSession;
import com.kaorisystem.auth.repository.AdminSessionRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for the session validator's expiry policy + cache behaviour.
 * No Spring context — pure mocks. Covers each terminal status and the hot
 * cache path.
 */
@DisplayName("SessionValidator — idle / absolute timeouts + cache")
class SessionValidatorTest {

    private AdminSessionRepository  repo;
    private StringRedisTemplate     redis;
    private ValueOperations<String, String> ops;
    private SessionValidator        underTest;

    @BeforeEach
    void setUp() {
        repo  = mock(AdminSessionRepository.class);
        redis = mock(StringRedisTemplate.class);
        ops   = mock(ValueOperations.class);
        when(redis.opsForValue()).thenReturn(ops);

        // 3.1.b — audit emitter is optional (best-effort). getIfAvailable()
        // returning null exercises the "no audit emitter wired" path.
        @SuppressWarnings("unchecked")
        ObjectProvider<PlatformAdminAuditService> auditProvider = mock(ObjectProvider.class);
        when(auditProvider.getIfAvailable()).thenReturn(null);

        underTest = new SessionValidator(repo, redis, auditProvider);
        ReflectionTestUtils.setField(underTest, "idleTimeoutSeconds",     1800L);
        ReflectionTestUtils.setField(underTest, "absoluteTimeoutSeconds", 86_400L);
    }

    private static AdminSession session(Instant created, Instant lastActive, Instant revoked) {
        AdminSession s = new AdminSession();
        s.setSessionId(UUID.randomUUID());
        s.setAdminId(UUID.randomUUID());
        s.setCreatedAt(created);
        s.setLastActiveAt(lastActive);
        s.setRevokedAt(revoked);
        return s;
    }

    // -------------------------------------------------------------------------
    // Cache hits — short-circuit
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("cache hit 'valid' — no DB read, returns VALID")
    void cacheHit_valid() {
        UUID sid = UUID.randomUUID();
        when(ops.get("session_status:" + sid)).thenReturn("valid");

        var r = underTest.validateAndTouch(sid);
        assertThat(r.status()).isEqualTo(SessionValidator.Status.VALID);
        verify(repo, never()).findById(any());
        verify(repo, never()).touchLastActive(any(), any());
    }

    @Test
    @DisplayName("cache hit 'idle' — surfaces IDLE_EXPIRED without DB read")
    void cacheHit_idle() {
        UUID sid = UUID.randomUUID();
        when(ops.get("session_status:" + sid)).thenReturn("idle");
        var r = underTest.validateAndTouch(sid);
        assertThat(r.status()).isEqualTo(SessionValidator.Status.IDLE_EXPIRED);
        verify(repo, never()).findById(any());
    }

    // -------------------------------------------------------------------------
    // Terminal states
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("missing row → NOT_FOUND, cached as 'missing'")
    void missing() {
        UUID sid = UUID.randomUUID();
        when(ops.get(any())).thenReturn(null);
        when(repo.findById(sid)).thenReturn(Optional.empty());

        var r = underTest.validateAndTouch(sid);
        assertThat(r.status()).isEqualTo(SessionValidator.Status.NOT_FOUND);
        verify(ops).set(eq("session_status:" + sid), eq("missing"), anyLong(), eq(TimeUnit.SECONDS));
    }

    @Test
    @DisplayName("already revoked → REVOKED, no further DB writes")
    void revoked() {
        UUID sid = UUID.randomUUID();
        Instant t = Instant.now();
        AdminSession s = session(t.minusSeconds(3600), t.minusSeconds(60), t.minusSeconds(10));
        s.setSessionId(sid);
        s.setRevokeReason("manual");
        when(ops.get(any())).thenReturn(null);
        when(repo.findById(sid)).thenReturn(Optional.of(s));

        var r = underTest.validateAndTouch(sid);
        assertThat(r.status()).isEqualTo(SessionValidator.Status.REVOKED);
        assertThat(r.reason()).isEqualTo("manual");
        verify(repo, never()).touchLastActive(any(), any());
        verify(repo, never()).revokeBySessionId(any(), any(), anyString());
    }

    @Test
    @DisplayName("created_at older than absolute window → ABSOLUTE_EXPIRED, auto-revokes")
    void absoluteTimeout() {
        UUID sid = UUID.randomUUID();
        Instant now = Instant.now();
        AdminSession s = session(
                now.minus(25, ChronoUnit.HOURS),    // > 24h
                now.minusSeconds(30),                // active recently — still expired
                null);
        s.setSessionId(sid);
        when(ops.get(any())).thenReturn(null);
        when(repo.findById(sid)).thenReturn(Optional.of(s));

        var r = underTest.validateAndTouch(sid);
        assertThat(r.status()).isEqualTo(SessionValidator.Status.ABSOLUTE_EXPIRED);
        assertThat(r.reason()).isEqualTo("absolute_timeout");
        verify(repo).revokeBySessionId(eq(sid), any(), eq("absolute_timeout"));
        verify(repo, never()).touchLastActive(any(), any());
    }

    @Test
    @DisplayName("last_active older than idle window → IDLE_EXPIRED, auto-revokes")
    void idleTimeout() {
        UUID sid = UUID.randomUUID();
        Instant now = Instant.now();
        AdminSession s = session(
                now.minus(2, ChronoUnit.HOURS),       // within absolute window
                now.minus(31, ChronoUnit.MINUTES),    // > 30 min idle
                null);
        s.setSessionId(sid);
        when(ops.get(any())).thenReturn(null);
        when(repo.findById(sid)).thenReturn(Optional.of(s));

        var r = underTest.validateAndTouch(sid);
        assertThat(r.status()).isEqualTo(SessionValidator.Status.IDLE_EXPIRED);
        assertThat(r.reason()).isEqualTo("idle_timeout");
        verify(repo).revokeBySessionId(eq(sid), any(), eq("idle_timeout"));
    }

    @Test
    @DisplayName("absolute precedence over idle — both expired → reports ABSOLUTE")
    void absoluteWinsOverIdle() {
        UUID sid = UUID.randomUUID();
        Instant now = Instant.now();
        AdminSession s = session(
                now.minus(25, ChronoUnit.HOURS),
                now.minus(2, ChronoUnit.HOURS),
                null);
        s.setSessionId(sid);
        when(ops.get(any())).thenReturn(null);
        when(repo.findById(sid)).thenReturn(Optional.of(s));

        var r = underTest.validateAndTouch(sid);
        assertThat(r.status()).isEqualTo(SessionValidator.Status.ABSOLUTE_EXPIRED);
        verify(repo).revokeBySessionId(eq(sid), any(), eq("absolute_timeout"));
        verify(repo, never()).revokeBySessionId(any(), any(), eq("idle_timeout"));
    }

    @Test
    @DisplayName("valid session → touches last_active_at, caches 'valid'")
    void valid() {
        UUID sid = UUID.randomUUID();
        Instant now = Instant.now();
        AdminSession s = session(
                now.minus(1, ChronoUnit.HOURS),
                now.minusSeconds(120),
                null);
        s.setSessionId(sid);
        when(ops.get(any())).thenReturn(null);
        when(repo.findById(sid)).thenReturn(Optional.of(s));

        var r = underTest.validateAndTouch(sid);
        assertThat(r.status()).isEqualTo(SessionValidator.Status.VALID);
        verify(repo, times(1)).touchLastActive(eq(sid), any());
        verify(ops).set(eq("session_status:" + sid), eq("valid"), eq(60L), eq(TimeUnit.SECONDS));
    }

    // -------------------------------------------------------------------------
    // null safety
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("null sessionId → NOT_FOUND, no Redis or DB calls")
    void nullId() {
        var r = underTest.validateAndTouch(null);
        assertThat(r.status()).isEqualTo(SessionValidator.Status.NOT_FOUND);
        verify(ops, never()).get(any());
        verify(repo, never()).findById(any());
    }

    @Test
    @DisplayName("invalidateCache — best effort, swallows Redis errors")
    void invalidateCache_swallowsErrors() {
        UUID sid = UUID.randomUUID();
        when(redis.delete(anyString())).thenThrow(new RuntimeException("Redis down"));
        // Must not propagate — would break logout otherwise
        underTest.invalidateCache(sid);
    }
}
