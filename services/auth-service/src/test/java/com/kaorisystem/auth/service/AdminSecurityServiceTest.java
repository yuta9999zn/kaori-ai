package com.kaorisystem.auth.service;

import com.kaorisystem.auth.model.AdminSession;
import com.kaorisystem.auth.model.PlatformAdmin;
import com.kaorisystem.auth.repository.AdminSessionRepository;
import com.kaorisystem.auth.repository.PlatformAdminRepository;
import com.kaorisystem.auth.service.AdminSecurityService.AdminNotFoundException;
import com.kaorisystem.auth.service.AdminSecurityService.InvalidTotpException;
import com.kaorisystem.auth.service.AdminSecurityService.MfaNotInitiatedException;
import com.kaorisystem.auth.service.AdminSecurityService.MfaVerifyLockedException;
import com.kaorisystem.auth.service.AdminSecurityService.SessionNotFoundException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.contains;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.util.ReflectionTestUtils.setField;

/**
 * Mockito-only orchestration tests for the MFA + sessions service.
 *
 * <p>Uses a real {@link TotpService} (no Spring context) so the encrypt/verify
 * path is exercised end-to-end with a deterministic dev key. Redis and the
 * audit service are mocked. Rate-limit and audit-emission behaviour live in
 * dedicated test methods below.
 */
@DisplayName("AdminSecurityService — MFA + sessions + rate-limit + audit")
class AdminSecurityServiceTest {

    private PlatformAdminRepository      adminRepo;
    private AdminSessionRepository       sessionRepo;
    private TotpService                  totp;
    private StringRedisTemplate          redis;
    private ValueOperations<String, String> ops;
    private PlatformAdminAuditService    audit;
    private AdminSecurityService         underTest;

    private static final String IP = "203.0.113.5";

    @BeforeEach
    void setUp() {
        adminRepo   = mock(PlatformAdminRepository.class);
        sessionRepo = mock(AdminSessionRepository.class);
        redis       = mock(StringRedisTemplate.class);
        ops         = mock(ValueOperations.class);
        audit       = mock(PlatformAdminAuditService.class);
        when(redis.opsForValue()).thenReturn(ops);

        totp = new TotpService();
        setField(totp, "mfaKeyB64", "");
        totp.initKey();

        underTest = new AdminSecurityService(adminRepo, sessionRepo, totp, redis, audit);
        setField(underTest, "mfaIssuer",                    "Kaori-Test");
        setField(underTest, "mfaLockoutAttempts",           5);
        setField(underTest, "mfaLockoutDurationSeconds",    900L);
    }

    private static PlatformAdmin admin(UUID id) {
        PlatformAdmin a = new PlatformAdmin();
        a.setAdminId(id);
        a.setEmail("a@kaori.io");
        a.setRole("ADMIN");
        a.setActive(true);
        return a;
    }

    // -------------------------------------------------------------------------
    // enableMfa
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("enableMfa — unknown admin → AdminNotFoundException, no audit row")
    void enable_unknownAdmin() {
        UUID id = UUID.randomUUID();
        given(adminRepo.findById(id)).willReturn(Optional.empty());

        assertThatThrownBy(() -> underTest.enableMfa(id, IP))
                .isInstanceOf(AdminNotFoundException.class);
        verify(audit, never()).recordAudit(any(), anyString(), any(), any(), any(), any(), any(), any());
    }

    @Test
    @DisplayName("enableMfa — happy path: stores enc secret, clears lockout, emits admin.mfa.initiated")
    void enable_savesSecretAndAudits() {
        UUID id = UUID.randomUUID();
        PlatformAdmin a = admin(id);
        a.setMfaEnabled(true);   // simulate rotation from a previously-verified state
        given(adminRepo.findById(id)).willReturn(Optional.of(a));

        var r = underTest.enableMfa(id, IP);

        assertThat(r.secret()).matches("[A-Z2-7]+");
        assertThat(a.getMfaSecretEnc()).isNotBlank();
        assertThat(a.isMfaEnabled()).isFalse();   // reset; needs re-verify

        verify(redis).delete("mfa_attempts:" + id);
        verify(redis).delete("mfa_lockout:"  + id);
        verify(audit).recordAudit(
                eq(id), eq(PlatformAdminAuditService.EVT_MFA_INITIATED),
                eq(id), eq("a@kaori.io"), eq("ADMIN"),
                eq("mfa"), anyString(), eq(IP));
    }

    // -------------------------------------------------------------------------
    // verifyMfa — rate limit
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("verifyMfa — already locked: 423 hint thrown without DB hit, audit row records lockout_active")
    void verify_alreadyLocked() {
        UUID id = UUID.randomUUID();
        when(ops.get("mfa_lockout:" + id)).thenReturn("1");
        when(redis.getExpire("mfa_lockout:" + id, TimeUnit.SECONDS)).thenReturn(420L);
        // Admin lookup happens for audit context only
        given(adminRepo.findById(id)).willReturn(Optional.of(admin(id)));

        assertThatThrownBy(() -> underTest.verifyMfa(id, "123456", IP))
                .isInstanceOf(MfaVerifyLockedException.class)
                .satisfies(ex ->
                        assertThat(((MfaVerifyLockedException) ex).getRemainingSeconds()).isEqualTo(420L));

        verify(audit).recordAudit(
                eq(id), eq(PlatformAdminAuditService.EVT_MFA_VERIFY_FAILED),
                eq(id), any(), any(),
                eq("mfa"), contains("rate_limited=true"), eq(IP));
    }

    @Test
    @DisplayName("verifyMfa — wrong code below threshold: increments attempts, 1st failure sets TTL")
    void verify_wrongCode_firstFailure() {
        UUID id = UUID.randomUUID();
        PlatformAdmin a = admin(id);
        byte[] secret = totp.generateSecret();
        a.setMfaSecretEnc(totp.encrypt(secret));

        when(ops.get("mfa_lockout:" + id)).thenReturn(null);
        given(adminRepo.findById(id)).willReturn(Optional.of(a));
        when(ops.increment("mfa_attempts:" + id)).thenReturn(1L);

        assertThatThrownBy(() -> underTest.verifyMfa(id, "000000", IP))
                .isInstanceOf(InvalidTotpException.class);

        // 1st failure must set the 15-min TTL on the counter
        verify(redis).expire("mfa_attempts:" + id, 900L, TimeUnit.SECONDS);
        // No lockout flag yet
        verify(ops, never()).set(eq("mfa_lockout:" + id), anyString(), anyLong(), any(TimeUnit.class));
        // Audit row reflects the un-locked state
        verify(audit).recordAudit(
                eq(id), eq(PlatformAdminAuditService.EVT_MFA_VERIFY_FAILED),
                eq(id), eq("a@kaori.io"), eq("ADMIN"),
                eq("mfa"), contains("rate_limited=false"), eq(IP));
    }

    @Test
    @DisplayName("verifyMfa — 5th wrong code trips lockout: throws Locked + audit reason=lockout_exceeded")
    void verify_fifthFailureLocks() {
        UUID id = UUID.randomUUID();
        PlatformAdmin a = admin(id);
        byte[] secret = totp.generateSecret();
        a.setMfaSecretEnc(totp.encrypt(secret));

        when(ops.get("mfa_lockout:" + id)).thenReturn(null);
        given(adminRepo.findById(id)).willReturn(Optional.of(a));
        when(ops.increment("mfa_attempts:" + id)).thenReturn(5L);

        assertThatThrownBy(() -> underTest.verifyMfa(id, "000000", IP))
                .isInstanceOf(MfaVerifyLockedException.class)
                .satisfies(ex ->
                        assertThat(((MfaVerifyLockedException) ex).getRemainingSeconds()).isEqualTo(900L));

        verify(ops).set(eq("mfa_lockout:" + id), eq("1"), eq(900L), eq(TimeUnit.SECONDS));
        verify(redis).delete("mfa_attempts:" + id);
        verify(audit).recordAudit(
                eq(id), eq(PlatformAdminAuditService.EVT_MFA_VERIFY_FAILED),
                eq(id), any(), any(),
                eq("mfa"), contains("reason=lockout_exceeded"), eq(IP));
    }

    @Test
    @DisplayName("verifyMfa — correct code: clears counters, flips mfa_enabled, emits admin.mfa.enabled")
    void verify_happyFreshEnable() {
        UUID id = UUID.randomUUID();
        PlatformAdmin a = admin(id);
        a.setMfaEnabled(false);   // first verify after enable
        byte[] secret = totp.generateSecret();
        a.setMfaSecretEnc(totp.encrypt(secret));

        when(ops.get("mfa_lockout:" + id)).thenReturn(null);
        given(adminRepo.findById(id)).willReturn(Optional.of(a));
        String code = totp.generateCode(secret, Instant.now());

        var r = underTest.verifyMfa(id, code, IP);
        assertThat(r.mfaEnabled()).isTrue();
        assertThat(a.isMfaEnabled()).isTrue();

        verify(redis).delete("mfa_attempts:" + id);
        verify(redis).delete("mfa_lockout:"  + id);
        verify(audit).recordAudit(
                eq(id), eq(PlatformAdminAuditService.EVT_MFA_ENABLED),
                eq(id), eq("a@kaori.io"), eq("ADMIN"),
                eq("mfa"), anyString(), eq(IP));
    }

    @Test
    @DisplayName("verifyMfa — re-verify when already enabled emits admin.mfa.verified (not enabled)")
    void verify_happyAlreadyEnabled() {
        UUID id = UUID.randomUUID();
        PlatformAdmin a = admin(id);
        a.setMfaEnabled(true);   // already on
        byte[] secret = totp.generateSecret();
        a.setMfaSecretEnc(totp.encrypt(secret));

        when(ops.get("mfa_lockout:" + id)).thenReturn(null);
        given(adminRepo.findById(id)).willReturn(Optional.of(a));
        String code = totp.generateCode(secret, Instant.now());

        underTest.verifyMfa(id, code, IP);

        verify(audit).recordAudit(
                eq(id), eq(PlatformAdminAuditService.EVT_MFA_VERIFIED),
                eq(id), any(), any(),
                eq("mfa"), anyString(), eq(IP));
    }

    @Test
    @DisplayName("verifyMfa — secret not stashed: 409, no audit row")
    void verify_notInitiated() {
        UUID id = UUID.randomUUID();
        when(ops.get("mfa_lockout:" + id)).thenReturn(null);
        given(adminRepo.findById(id)).willReturn(Optional.of(admin(id)));   // no secret on row

        assertThatThrownBy(() -> underTest.verifyMfa(id, "123456", IP))
                .isInstanceOf(MfaNotInitiatedException.class);
        verify(audit, never()).recordAudit(any(), anyString(), any(), any(), any(), any(), any(), any());
    }

    // -------------------------------------------------------------------------
    // revokeSession (manual)
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("revokeSession — happy path: emits admin.session.revoked with reason=manual + IP")
    void revoke_happyPath() {
        UUID adminId = UUID.randomUUID();
        UUID sid     = UUID.randomUUID();
        given(adminRepo.findById(adminId)).willReturn(Optional.of(admin(adminId)));
        given(sessionRepo.revokeForAdmin(eq(sid), eq(adminId), any(), eq("manual"))).willReturn(1);

        var r = underTest.revokeSession(adminId, sid, IP);
        assertThat(r.sessionId()).isEqualTo(sid);

        verify(audit).recordAudit(
                eq(adminId), eq(PlatformAdminAuditService.EVT_SESSION_REVOKED),
                eq(adminId), eq("a@kaori.io"), eq("ADMIN"),
                eq(sid.toString()), eq("reason=manual"), eq(IP));
    }

    // -------------------------------------------------------------------------
    // 3.3 — revokeOtherSessions
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("revokeOtherSessions — 0 revoked: no audit row, returns count=0")
    void revokeOthers_noActiveSessions() {
        UUID adminId = UUID.randomUUID();
        UUID keep    = UUID.randomUUID();
        given(adminRepo.findById(adminId)).willReturn(Optional.of(admin(adminId)));
        when(sessionRepo.revokeAllExcept(eq(adminId), eq(keep), any(), eq("manual_bulk")))
                .thenReturn(0);

        var r = underTest.revokeOtherSessions(adminId, keep, IP);
        assertThat(r.revokedCount()).isZero();
        verify(audit, never()).recordAudit(any(), anyString(), any(), any(), any(), any(), any(), any());
    }

    @Test
    @DisplayName("revokeOtherSessions — N revoked: emits one summary audit row with count + reason")
    void revokeOthers_happyPath() {
        UUID adminId = UUID.randomUUID();
        UUID keep    = UUID.randomUUID();
        given(adminRepo.findById(adminId)).willReturn(Optional.of(admin(adminId)));
        when(sessionRepo.revokeAllExcept(eq(adminId), eq(keep), any(), eq("manual_bulk")))
                .thenReturn(3);

        var r = underTest.revokeOtherSessions(adminId, keep, IP);
        assertThat(r.revokedCount()).isEqualTo(3);

        verify(audit, times(1)).recordAudit(
                eq(adminId), eq(PlatformAdminAuditService.EVT_SESSION_REVOKED),
                eq(adminId), eq("a@kaori.io"), eq("ADMIN"),
                eq("all-others"),
                contains("reason=manual_bulk count=3"),
                eq(IP));
    }

    @Test
    @DisplayName("revokeOtherSessions — null keepSessionId: SQL gets sentinel UUID, callers don't crash")
    void revokeOthers_nullKeep() {
        UUID adminId = UUID.randomUUID();
        given(adminRepo.findById(adminId)).willReturn(Optional.of(admin(adminId)));
        when(sessionRepo.revokeAllExcept(eq(adminId), any(UUID.class), any(), eq("manual_bulk")))
                .thenReturn(2);

        var r = underTest.revokeOtherSessions(adminId, null, IP);
        assertThat(r.revokedCount()).isEqualTo(2);
    }

    @Test
    @DisplayName("revokeOtherSessions — unknown admin: AdminNotFoundException, no DB write")
    void revokeOthers_unknownAdmin() {
        UUID adminId = UUID.randomUUID();
        given(adminRepo.findById(adminId)).willReturn(Optional.empty());
        assertThatThrownBy(() -> underTest.revokeOtherSessions(adminId, UUID.randomUUID(), IP))
                .isInstanceOf(AdminNotFoundException.class);
        verify(sessionRepo, never()).revokeAllExcept(any(), any(), any(), anyString());
    }

    @Test
    @DisplayName("revokeSession — IDOR / already revoked: 404, no audit row")
    void revoke_idor() {
        UUID adminId = UUID.randomUUID();
        UUID sid     = UUID.randomUUID();
        given(adminRepo.findById(adminId)).willReturn(Optional.of(admin(adminId)));
        given(sessionRepo.revokeForAdmin(eq(sid), eq(adminId), any(), eq("manual"))).willReturn(0);

        assertThatThrownBy(() -> underTest.revokeSession(adminId, sid, IP))
                .isInstanceOf(SessionNotFoundException.class);
        verify(audit, never()).recordAudit(any(), anyString(), any(), any(), any(), any(), any(), any());
    }

    // -------------------------------------------------------------------------
    // listActiveSessions — unchanged
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("listActiveSessions — unknown admin → AdminNotFoundException")
    void list_unknown() {
        UUID id = UUID.randomUUID();
        given(adminRepo.findById(id)).willReturn(Optional.empty());
        assertThatThrownBy(() -> underTest.listActiveSessions(id))
                .isInstanceOf(AdminNotFoundException.class);
    }

    @Test
    @DisplayName("listActiveSessions — happy path delegates to repo")
    void list_happy() {
        UUID id = UUID.randomUUID();
        AdminSession s = new AdminSession();
        s.setSessionId(UUID.randomUUID());
        s.setAdminId(id);
        s.setLastActiveAt(Instant.now());
        s.setCreatedAt(Instant.now());
        given(adminRepo.findById(id)).willReturn(Optional.of(admin(id)));
        given(sessionRepo.findByAdminIdAndRevokedAtIsNullOrderByLastActiveAtDesc(id))
                .willReturn(List.of(s));

        assertThat(underTest.listActiveSessions(id)).containsExactly(s);
    }
}
