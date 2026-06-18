package com.kaorisystem.auth.service;

import com.kaorisystem.auth.dto.AuthDtos.LoginRequest;
import com.kaorisystem.auth.dto.AuthDtos.MfaVerifyRequest;
import com.kaorisystem.auth.dto.AuthDtos.RefreshRequest;
import com.kaorisystem.auth.model.AdminSession;
import com.kaorisystem.auth.model.MfaChallenge;
import com.kaorisystem.auth.model.PlatformAdmin;
import com.kaorisystem.auth.repository.AdminSessionRepository;
import com.kaorisystem.auth.repository.MfaChallengeRepository;
import com.kaorisystem.auth.repository.PlatformAdminRepository;
import com.kaorisystem.auth.security.JwtUtil;
import com.kaorisystem.auth.service.AuthService.InvalidCredentialsException;
import com.kaorisystem.auth.service.PlatformAuthService.MfaChallengeExpiredException;
import com.kaorisystem.auth.service.PlatformAuthService.PlatformLoginResult;
import com.kaorisystem.auth.service.PlatformAuthService.TokenReplayException;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.security.crypto.password.PasswordEncoder;

import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.time.Instant;
import java.util.Base64;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.util.ReflectionTestUtils.setField;

/**
 * Mockito-only orchestration tests for the B3 PR #8 MFA-at-login flow + the
 * refresh-token replay guard. Real {@link JwtUtil} (in-memory RSA keys) and
 * real {@link TotpService} (deterministic dev key) so the JWT round-trip and
 * TOTP encrypt/verify paths are exercised end-to-end.
 *
 * <p>Mocked: repos, password encoder, Redis, session validator, audit service.
 * Behaviour pinned: who calls what, in what order, with which arguments.
 *
 * <p>Why a separate test class from the existing PlatformAuthService suite
 * (none today): the MFA flow doubles the LOC of the service; isolating its
 * tests keeps each shape grokkable in one screen.
 */
@DisplayName("PlatformAuthService — MFA 2-step + refresh replay (B3 PR #8)")
class PlatformAuthServiceMfaTest {

    private static JwtUtil jwtUtil;

    private PlatformAdminRepository      adminRepo;
    private AdminSessionRepository       sessionRepo;
    private MfaChallengeRepository       challengeRepo;
    private PasswordEncoder              passwordEncoder;
    private StringRedisTemplate          redis;
    private ValueOperations<String, String> ops;
    private SessionValidator             sessionValidator;
    private TotpService                  totp;
    private PlatformAdminAuditService    audit;
    private PlatformAuthService          underTest;

    private static final String IP = "203.0.113.10";
    private static final String UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/124.0";

    @BeforeAll
    static void buildJwtUtil() throws Exception {
        KeyPairGenerator gen = KeyPairGenerator.getInstance("RSA");
        gen.initialize(2048);
        KeyPair pair = gen.generateKeyPair();
        String priv = Base64.getEncoder().encodeToString(pair.getPrivate().getEncoded());
        String pub  = Base64.getEncoder().encodeToString(pair.getPublic().getEncoded());
        jwtUtil = new JwtUtil(priv, pub, 15L, 7L);
    }

    @BeforeEach
    void setUp() {
        adminRepo        = mock(PlatformAdminRepository.class);
        sessionRepo      = mock(AdminSessionRepository.class);
        challengeRepo    = mock(MfaChallengeRepository.class);
        passwordEncoder  = mock(PasswordEncoder.class);
        redis            = mock(StringRedisTemplate.class);
        ops              = mock(ValueOperations.class);
        sessionValidator = mock(SessionValidator.class);
        audit            = mock(PlatformAdminAuditService.class);
        when(redis.opsForValue()).thenReturn(ops);

        totp = new TotpService();
        setField(totp, "mfaKeyB64", "");
        totp.initKey();

        underTest = new PlatformAuthService(
                adminRepo, sessionRepo, challengeRepo,
                passwordEncoder, jwtUtil, redis, sessionValidator,
                totp, audit);
        setField(underTest, "lockoutAttempts",        5);
        setField(underTest, "lockoutDurationSeconds", 900L);

        // sessionRepo.save echoes the entity with a fresh UUID — the service
        // reads back the assigned session_id to mint the JWT.
        when(sessionRepo.save(any(AdminSession.class))).thenAnswer(inv -> {
            AdminSession s = inv.getArgument(0);
            if (s.getSessionId() == null) s.setSessionId(UUID.randomUUID());
            return s;
        });
    }

    // =========================================================================
    // login — MFA gate
    // =========================================================================

    @Test
    @DisplayName("login — mfa_enabled=false: completes session, no challenge issued")
    void login_noMfa_returnsSession() {
        UUID adminId = UUID.randomUUID();
        PlatformAdmin a = admin(adminId);
        a.setMfaEnabled(false);
        given(adminRepo.findByEmailIgnoreCase("a@kaori.io")).willReturn(Optional.of(a));
        given(passwordEncoder.matches("pwd", "hashed-pwd")).willReturn(true);

        PlatformLoginResult r = underTest.login(loginReq("a@kaori.io", "pwd"), IP, UA);

        assertThat(r.mfaRequired()).isFalse();
        assertThat(r.accessToken()).isNotBlank();
        assertThat(r.refreshToken()).isNotBlank();
        assertThat(r.sessionId()).isNotNull();
        verify(challengeRepo, never()).save(any());
        verify(audit, never()).recordAudit(any(), eq(PlatformAdminAuditService.EVT_MFA_LOGIN_CHALLENGED),
                any(), any(), any(), any(), any(), any());
    }

    @Test
    @DisplayName("login — mfa_enabled=true: persists challenge, returns mfaRequired=true with no session")
    void login_mfaEnabled_returnsChallenge() {
        UUID adminId = UUID.randomUUID();
        PlatformAdmin a = adminWithMfa(adminId);
        given(adminRepo.findByEmailIgnoreCase("a@kaori.io")).willReturn(Optional.of(a));
        given(passwordEncoder.matches("pwd", "hashed-pwd")).willReturn(true);

        PlatformLoginResult r = underTest.login(loginReq("a@kaori.io", "pwd"), IP, UA);

        assertThat(r.mfaRequired()).isTrue();
        assertThat(r.mfaChallengeToken()).isNotBlank();
        assertThat(r.accessToken()).isNull();
        assertThat(r.refreshToken()).isNull();
        assertThat(r.sessionId()).isNull();
        verify(challengeRepo).save(any(MfaChallenge.class));
        verify(sessionRepo, never()).save(any());   // no admin_sessions row at first leg
        verify(audit).recordAudit(
                eq(adminId), eq(PlatformAdminAuditService.EVT_MFA_LOGIN_CHALLENGED),
                eq(adminId), eq("a@kaori.io"), eq("ADMIN"),
                anyString(), anyString(), eq(IP));
    }

    @Test
    @DisplayName("login — admin has secret enrolled but mfa_enabled=false: no challenge (enrollment in progress)")
    void login_enrollmentInProgress_noChallenge() {
        UUID adminId = UUID.randomUUID();
        PlatformAdmin a = adminWithMfa(adminId);
        a.setMfaEnabled(false);   // secret saved but verify hasn't flipped enabled
        given(adminRepo.findByEmailIgnoreCase("a@kaori.io")).willReturn(Optional.of(a));
        given(passwordEncoder.matches("pwd", "hashed-pwd")).willReturn(true);

        PlatformLoginResult r = underTest.login(loginReq("a@kaori.io", "pwd"), IP, UA);

        assertThat(r.mfaRequired()).isFalse();
        verify(challengeRepo, never()).save(any());
    }

    // =========================================================================
    // verifyMfaChallenge
    // =========================================================================

    @Test
    @DisplayName("verifyMfaChallenge — happy path: marks used, mints session, audits login_verified")
    void verify_happyPath() {
        UUID adminId     = UUID.randomUUID();
        UUID challengeId = UUID.randomUUID();
        PlatformAdmin a = adminWithMfa(adminId);
        String token  = jwtUtil.generatePlatformMfaChallengeToken(adminId, challengeId, 5L * 60 * 1000);
        MfaChallenge ch = challengeRow(adminId, challengeId, token, Instant.now().plusSeconds(300));

        given(challengeRepo.findByChallengeTokenHash(anyString())).willReturn(Optional.of(ch));
        given(adminRepo.findById(adminId)).willReturn(Optional.of(a));
        given(challengeRepo.markUsedIfPending(eq(challengeId), any())).willReturn(1);

        // Generate the current TOTP code from the same plaintext secret stored
        // on the admin row — encrypted via TotpService.encrypt().
        byte[] secret = totp.decrypt(a.getMfaSecretEnc());
        String code  = totp.generateCode(secret, Instant.now());

        PlatformLoginResult r = underTest.verifyMfaChallenge(
                verifyReq(token, code), IP, UA);

        assertThat(r.mfaRequired()).isFalse();
        assertThat(r.accessToken()).isNotBlank();
        assertThat(r.refreshToken()).isNotBlank();
        verify(challengeRepo).markUsedIfPending(eq(challengeId), any());
        verify(audit).recordAudit(
                eq(adminId), eq(PlatformAdminAuditService.EVT_MFA_LOGIN_VERIFIED),
                eq(adminId), eq("a@kaori.io"), eq("ADMIN"),
                anyString(), anyString(), eq(IP));
    }

    @Test
    @DisplayName("verifyMfaChallenge — wrong code: bumps attempts, throws InvalidCredentialsException, audits login_failed")
    void verify_wrongCode_bumpsAttempts() {
        UUID adminId     = UUID.randomUUID();
        UUID challengeId = UUID.randomUUID();
        PlatformAdmin a = adminWithMfa(adminId);
        String token  = jwtUtil.generatePlatformMfaChallengeToken(adminId, challengeId, 5L * 60 * 1000);
        MfaChallenge ch = challengeRow(adminId, challengeId, token, Instant.now().plusSeconds(300));

        given(challengeRepo.findByChallengeTokenHash(anyString())).willReturn(Optional.of(ch));
        given(adminRepo.findById(adminId)).willReturn(Optional.of(a));

        assertThatThrownBy(() ->
                underTest.verifyMfaChallenge(verifyReq(token, "000000"), IP, UA))
                .isInstanceOf(InvalidCredentialsException.class)
                .hasMessageContaining("Invalid MFA code");
        verify(challengeRepo).incrementAttempts(challengeId);
        verify(challengeRepo, never()).markUsedIfPending(any(), any());
        verify(audit).recordAudit(
                eq(adminId), eq(PlatformAdminAuditService.EVT_MFA_LOGIN_FAILED),
                any(), any(), any(), any(), anyString(), eq(IP));
    }

    @Test
    @DisplayName("verifyMfaChallenge — attempts already at cap: marks used and rejects without verifying")
    void verify_attemptsExhausted_burnsRow() {
        UUID adminId     = UUID.randomUUID();
        UUID challengeId = UUID.randomUUID();
        PlatformAdmin a = adminWithMfa(adminId);
        String token  = jwtUtil.generatePlatformMfaChallengeToken(adminId, challengeId, 5L * 60 * 1000);
        MfaChallenge ch = challengeRow(adminId, challengeId, token, Instant.now().plusSeconds(300));
        ch.setAttempts(4);   // last allowed try; this call drives it to 5

        given(challengeRepo.findByChallengeTokenHash(anyString())).willReturn(Optional.of(ch));
        given(adminRepo.findById(adminId)).willReturn(Optional.of(a));

        assertThatThrownBy(() ->
                underTest.verifyMfaChallenge(verifyReq(token, "000000"), IP, UA))
                .isInstanceOf(InvalidCredentialsException.class);
        verify(challengeRepo).incrementAttempts(challengeId);
        verify(challengeRepo).markUsedIfPending(eq(challengeId), any());
    }

    @Test
    @DisplayName("verifyMfaChallenge — expired challenge: throws MfaChallengeExpiredException, no attempts bump")
    void verify_expired() {
        UUID adminId     = UUID.randomUUID();
        UUID challengeId = UUID.randomUUID();
        // Issue the JWT with full 5-min TTL so signature validates, but the DB
        // row's expires_at is in the past — mirrors the realistic case where
        // the token still parses but the row has aged out.
        String token  = jwtUtil.generatePlatformMfaChallengeToken(adminId, challengeId, 5L * 60 * 1000);
        MfaChallenge ch = challengeRow(adminId, challengeId, token, Instant.now().minusSeconds(60));

        given(challengeRepo.findByChallengeTokenHash(anyString())).willReturn(Optional.of(ch));

        assertThatThrownBy(() ->
                underTest.verifyMfaChallenge(verifyReq(token, "000000"), IP, UA))
                .isInstanceOf(MfaChallengeExpiredException.class);
        verify(challengeRepo, never()).incrementAttempts(any());
        verify(challengeRepo, never()).markUsedIfPending(any(), any());
    }

    @Test
    @DisplayName("verifyMfaChallenge — already-used challenge: rejects, no attempts bump")
    void verify_alreadyUsed() {
        UUID adminId     = UUID.randomUUID();
        UUID challengeId = UUID.randomUUID();
        String token  = jwtUtil.generatePlatformMfaChallengeToken(adminId, challengeId, 5L * 60 * 1000);
        MfaChallenge ch = challengeRow(adminId, challengeId, token, Instant.now().plusSeconds(300));
        ch.setUsedAt(Instant.now().minusSeconds(5));

        given(challengeRepo.findByChallengeTokenHash(anyString())).willReturn(Optional.of(ch));

        assertThatThrownBy(() ->
                underTest.verifyMfaChallenge(verifyReq(token, "000000"), IP, UA))
                .isInstanceOf(InvalidCredentialsException.class);
        verify(challengeRepo, never()).incrementAttempts(any());
    }

    @Test
    @DisplayName("verifyMfaChallenge — challenge_id in JWT mismatches DB row: rejects (defence in depth)")
    void verify_challengeIdMismatch() {
        UUID adminId       = UUID.randomUUID();
        UUID jwtChallenge  = UUID.randomUUID();
        UUID dbChallenge   = UUID.randomUUID();   // different — possible forge attempt
        String token  = jwtUtil.generatePlatformMfaChallengeToken(adminId, jwtChallenge, 5L * 60 * 1000);
        MfaChallenge ch = challengeRow(adminId, dbChallenge, token, Instant.now().plusSeconds(300));

        given(challengeRepo.findByChallengeTokenHash(anyString())).willReturn(Optional.of(ch));

        assertThatThrownBy(() ->
                underTest.verifyMfaChallenge(verifyReq(token, "000000"), IP, UA))
                .isInstanceOf(InvalidCredentialsException.class);
    }

    // =========================================================================
    // refresh — jti SETNX replay
    // =========================================================================

    @Test
    @DisplayName("refresh — second use of same refresh JWT: SETNX returns false → TokenReplayException")
    void refresh_replayed() {
        UUID adminId   = UUID.randomUUID();
        UUID sessionId = UUID.randomUUID();
        String refresh = jwtUtil.generatePlatformRefreshToken(adminId, sessionId);

        // Stored refresh matches; session is alive; SETNX returns false → already-used.
        given(ops.get("platform_refresh:" + sessionId)).willReturn(refresh);
        given(sessionValidator.validateAndTouch(sessionId))
                .willReturn(SessionValidator.Result.valid());
        given(ops.setIfAbsent(anyString(), eq("1"), anyLong(), eq(TimeUnit.MILLISECONDS)))
                .willReturn(false);
        given(adminRepo.findById(adminId)).willReturn(Optional.of(admin(adminId)));

        RefreshRequest req = new RefreshRequest();
        req.setRefreshToken(refresh);

        assertThatThrownBy(() -> underTest.refresh(req))
                .isInstanceOf(TokenReplayException.class);
    }

    @Test
    @DisplayName("refresh — first use of refresh JWT: SETNX returns true → tokens rotated")
    void refresh_firstUse_succeeds() {
        UUID adminId   = UUID.randomUUID();
        UUID sessionId = UUID.randomUUID();
        String refresh = jwtUtil.generatePlatformRefreshToken(adminId, sessionId);

        given(ops.get("platform_refresh:" + sessionId)).willReturn(refresh);
        given(sessionValidator.validateAndTouch(sessionId))
                .willReturn(SessionValidator.Result.valid());
        given(ops.setIfAbsent(anyString(), eq("1"), anyLong(), eq(TimeUnit.MILLISECONDS)))
                .willReturn(true);
        given(adminRepo.findById(adminId)).willReturn(Optional.of(admin(adminId)));

        RefreshRequest req = new RefreshRequest();
        req.setRefreshToken(refresh);

        PlatformLoginResult r = underTest.refresh(req);

        assertThat(r.accessToken()).isNotBlank();
        assertThat(r.refreshToken()).isNotBlank();
        assertThat(r.refreshToken()).isNotEqualTo(refresh);   // rotated
        verify(ops, atLeastOnce()).set(eq("platform_refresh:" + sessionId),
                anyString(), anyLong(), eq(TimeUnit.MILLISECONDS));
    }

    // =========================================================================
    // helpers
    // =========================================================================

    private static LoginRequest loginReq(String email, String pwd) {
        LoginRequest r = new LoginRequest();
        r.setEmail(email);
        r.setPassword(pwd);
        return r;
    }

    private static MfaVerifyRequest verifyReq(String challengeToken, String code) {
        MfaVerifyRequest r = new MfaVerifyRequest();
        r.setMfaChallengeToken(challengeToken);
        r.setCode(code);
        return r;
    }

    private static PlatformAdmin admin(UUID id) {
        PlatformAdmin a = new PlatformAdmin();
        a.setAdminId(id);
        a.setEmail("a@kaori.io");
        a.setRole("ADMIN");
        a.setActive(true);
        a.setPasswordHash("hashed-pwd");
        return a;
    }

    private PlatformAdmin adminWithMfa(UUID id) {
        PlatformAdmin a = admin(id);
        a.setMfaEnabled(true);
        a.setMfaSecretEnc(totp.encrypt(totp.generateSecret()));
        return a;
    }

    private static MfaChallenge challengeRow(UUID adminId, UUID challengeId,
                                             String token, Instant expiresAt) {
        MfaChallenge ch = new MfaChallenge();
        ch.setChallengeId(challengeId);
        ch.setAdminId(adminId);
        ch.setChallengeTokenHash(PlatformAuthService.sha256Hex(token));
        ch.setExpiresAt(expiresAt);
        ch.setAttempts(0);
        return ch;
    }
}
