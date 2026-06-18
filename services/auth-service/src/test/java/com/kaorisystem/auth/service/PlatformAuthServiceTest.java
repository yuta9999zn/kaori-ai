package com.kaorisystem.auth.service;

import com.kaorisystem.auth.dto.AuthDtos.LoginRequest;
import com.kaorisystem.auth.dto.AuthDtos.RefreshRequest;
import com.kaorisystem.auth.model.AdminSession;
import com.kaorisystem.auth.model.PlatformAdmin;
import com.kaorisystem.auth.repository.AdminSessionRepository;
import com.kaorisystem.auth.repository.MfaChallengeRepository;
import com.kaorisystem.auth.repository.PlatformAdminRepository;
import com.kaorisystem.auth.security.JwtUtil;
import com.kaorisystem.auth.service.AuthService.InvalidCredentialsException;
import com.kaorisystem.auth.service.AuthService.LockoutException;
import io.jsonwebtoken.Claims;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.util.ReflectionTestUtils;

import java.security.KeyPair;
import java.security.KeyPairGenerator;
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
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@DisplayName("PlatformAuthService — login + refresh + lockout")
class PlatformAuthServiceTest {

    private PlatformAdminRepository  adminRepo;
    private AdminSessionRepository   sessionRepo;
    private MfaChallengeRepository   challengeRepo;
    private PasswordEncoder          encoder;
    private StringRedisTemplate      redis;
    private ValueOperations<String, String> ops;
    private SessionValidator         sessionValidator;
    private TotpService              totp;
    private PlatformAdminAuditService audit;
    private PlatformAuthService      underTest;

    private static JwtUtil jwtUtil;

    @BeforeAll
    static void buildJwt() throws Exception {
        KeyPairGenerator gen = KeyPairGenerator.getInstance("RSA");
        gen.initialize(2048);
        KeyPair pair = gen.generateKeyPair();
        String pri = Base64.getEncoder().encodeToString(pair.getPrivate().getEncoded());
        String pub = Base64.getEncoder().encodeToString(pair.getPublic().getEncoded());
        jwtUtil = new JwtUtil(pri, pub, 15L, 7L);
    }

    @BeforeEach
    void setUp() {
        adminRepo        = mock(PlatformAdminRepository.class);
        sessionRepo      = mock(AdminSessionRepository.class);
        challengeRepo    = mock(MfaChallengeRepository.class);
        encoder          = mock(PasswordEncoder.class);
        redis            = mock(StringRedisTemplate.class);
        ops              = mock(ValueOperations.class);
        sessionValidator = mock(SessionValidator.class);
        audit            = mock(PlatformAdminAuditService.class);
        when(redis.opsForValue()).thenReturn(ops);

        // B3 PR #8 — TotpService dependency added for MFA verify flow.
        // Real instance with the deterministic dev key (no Spring context).
        totp = new TotpService();
        ReflectionTestUtils.setField(totp, "mfaKeyB64", "");
        totp.initKey();

        underTest = new PlatformAuthService(
                adminRepo, sessionRepo, challengeRepo,
                encoder, jwtUtil, redis, sessionValidator, totp, audit);
        ReflectionTestUtils.setField(underTest, "lockoutAttempts", 5);
        ReflectionTestUtils.setField(underTest, "lockoutDurationSeconds", 900L);
    }

    private static PlatformAdmin admin(String email, boolean active) {
        PlatformAdmin a = new PlatformAdmin();
        a.setAdminId(UUID.randomUUID());
        a.setEmail(email);
        a.setPasswordHash("$bcrypt$hash");
        a.setRole("ADMIN");
        a.setActive(active);
        a.setMfaEnabled(true);
        return a;
    }

    private static LoginRequest loginReq(String email, String password) {
        LoginRequest r = new LoginRequest();
        r.setEmail(email);
        r.setPassword(password);
        return r;
    }

    // -------------------------------------------------------------------------
    // login
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("login — happy path creates session row + returns platform-token JWT with session_id claim")
    void login_happyPath() {
        PlatformAdmin a = admin("admin@kaori.io", true);
        when(adminRepo.findByEmailIgnoreCase("admin@kaori.io")).thenReturn(Optional.of(a));
        when(encoder.matches("pw", a.getPasswordHash())).thenReturn(true);
        when(sessionRepo.save(any(AdminSession.class))).thenAnswer(i -> {
            AdminSession s = i.getArgument(0);
            // Mimic the @PrePersist lifecycle which only fires under JPA
            if (s.getSessionId() == null) s.setSessionId(UUID.randomUUID());
            java.time.Instant now = java.time.Instant.now();
            if (s.getCreatedAt()    == null) s.setCreatedAt(now);
            if (s.getLastActiveAt() == null) s.setLastActiveAt(now);
            return s;
        });

        var r = underTest.login(loginReq("admin@kaori.io", "pw"), "1.2.3.4", "Mozilla/5.0 Chrome/120.0");

        assertThat(r.adminId()).isEqualTo(a.getAdminId());
        assertThat(r.role()).isEqualTo("ADMIN");
        assertThat(r.mfaEnabled()).isTrue();   // info-only; does not gate
        assertThat(r.sessionId()).isNotNull();
        assertThat(r.expiresInSec()).isGreaterThan(0);

        // JWT claims must reflect the platform token shape
        Claims claims = jwtUtil.validateAndParse(r.accessToken());
        assertThat(claims.get("token_kind")).isEqualTo("platform");
        assertThat(claims.get("session_id")).isEqualTo(r.sessionId().toString());
        assertThat(claims.get("role")).isEqualTo("ADMIN");
        assertThat(claims.getSubject()).isEqualTo(a.getAdminId().toString());

        // last_login_at touched + lockout cleared
        verify(adminRepo, times(1)).save(a);
        verify(redis).delete("platform_lockout:admin@kaori.io");

        // Refresh stored under platform_refresh:{session_id}
        verify(ops).set(eq("platform_refresh:" + r.sessionId()), eq(r.refreshToken()),
                anyLong(), eq(TimeUnit.MILLISECONDS));
    }

    @Test
    @DisplayName("login — wrong password → InvalidCredentials, increments lockout counter")
    void login_wrongPassword() {
        PlatformAdmin a = admin("admin@kaori.io", true);
        when(adminRepo.findByEmailIgnoreCase("admin@kaori.io")).thenReturn(Optional.of(a));
        when(encoder.matches("bad", a.getPasswordHash())).thenReturn(false);
        when(ops.increment("platform_login_attempts:admin@kaori.io")).thenReturn(1L);

        assertThatThrownBy(() -> underTest.login(loginReq("admin@kaori.io", "bad"), "1.2.3.4", "ua"))
                .isInstanceOf(InvalidCredentialsException.class);

        verify(ops).increment("platform_login_attempts:admin@kaori.io");
        verify(redis).expire(eq("platform_login_attempts:admin@kaori.io"), eq(900L), eq(TimeUnit.SECONDS));
        verify(sessionRepo, never()).save(any());
    }

    @Test
    @DisplayName("login — locked account → LockoutException with seconds remaining")
    void login_locked() {
        when(ops.get("platform_lockout:locked@kaori.io")).thenReturn("1");
        when(redis.getExpire("platform_lockout:locked@kaori.io", TimeUnit.SECONDS)).thenReturn(420L);

        assertThatThrownBy(() -> underTest.login(loginReq("locked@kaori.io", "x"), "1.1.1.1", "ua"))
                .isInstanceOf(LockoutException.class);

        verify(adminRepo, never()).findByEmailIgnoreCase(any());
    }

    @Test
    @DisplayName("login — 5th failure → sets lockout, drops counter")
    void login_lockoutTrip() {
        PlatformAdmin a = admin("admin@kaori.io", true);
        when(adminRepo.findByEmailIgnoreCase("admin@kaori.io")).thenReturn(Optional.of(a));
        when(encoder.matches("bad", a.getPasswordHash())).thenReturn(false);
        when(ops.increment("platform_login_attempts:admin@kaori.io")).thenReturn(5L);

        assertThatThrownBy(() -> underTest.login(loginReq("admin@kaori.io", "bad"), "1.1.1.1", "ua"))
                .isInstanceOf(InvalidCredentialsException.class);

        verify(ops).set(eq("platform_lockout:admin@kaori.io"), eq("1"), eq(900L), eq(TimeUnit.SECONDS));
        verify(redis).delete("platform_login_attempts:admin@kaori.io");
    }

    @Test
    @DisplayName("login — deactivated admin returns generic invalid-credentials (no enumeration)")
    void login_deactivated() {
        PlatformAdmin a = admin("admin@kaori.io", false);
        when(adminRepo.findByEmailIgnoreCase("admin@kaori.io")).thenReturn(Optional.of(a));
        when(encoder.matches("pw", a.getPasswordHash())).thenReturn(true);

        assertThatThrownBy(() -> underTest.login(loginReq("admin@kaori.io", "pw"), "1.1.1.1", "ua"))
                .isInstanceOf(InvalidCredentialsException.class);
    }

    @Test
    @DisplayName("login — admin without password_hash (invited but never activated) cannot log in")
    void login_noPasswordSet() {
        PlatformAdmin a = admin("admin@kaori.io", true);
        a.setPasswordHash(null);   // pre-activation
        when(adminRepo.findByEmailIgnoreCase("admin@kaori.io")).thenReturn(Optional.of(a));
        when(ops.increment("platform_login_attempts:admin@kaori.io")).thenReturn(1L);

        assertThatThrownBy(() -> underTest.login(loginReq("admin@kaori.io", "pw"), "1.1.1.1", "ua"))
                .isInstanceOf(InvalidCredentialsException.class);
    }

    // -------------------------------------------------------------------------
    // refresh
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("refresh — happy path issues new tokens reusing the same session_id")
    void refresh_happyPath() {
        PlatformAdmin a = admin("admin@kaori.io", true);
        UUID sid = UUID.randomUUID();
        String oldRefresh = jwtUtil.generatePlatformRefreshToken(a.getAdminId(), sid);

        when(sessionValidator.validateAndTouch(sid))
                .thenReturn(SessionValidator.Result.valid());
        when(ops.get("platform_refresh:" + sid)).thenReturn(oldRefresh);
        when(adminRepo.findById(a.getAdminId())).thenReturn(Optional.of(a));
        // B3 PR #8 — jti SETNX dedup. First use of a refresh JWT returns true
        // (no prior key); the rotation then writes the new refresh as usual.
        when(ops.setIfAbsent(anyString(), eq("1"), anyLong(), eq(TimeUnit.MILLISECONDS)))
                .thenReturn(true);

        RefreshRequest req = new RefreshRequest();
        req.setRefreshToken(oldRefresh);

        var r = underTest.refresh(req);
        assertThat(r.sessionId()).isEqualTo(sid);
        assertThat(r.adminId()).isEqualTo(a.getAdminId());

        Claims claims = jwtUtil.validateAndParse(r.accessToken());
        assertThat(claims.get("session_id")).isEqualTo(sid.toString());
        assertThat(claims.get("token_kind")).isEqualTo("platform");
    }

    @Test
    @DisplayName("refresh — session no longer valid → InvalidCredentials")
    void refresh_sessionExpired() {
        PlatformAdmin a = admin("admin@kaori.io", true);
        UUID sid = UUID.randomUUID();
        String tok = jwtUtil.generatePlatformRefreshToken(a.getAdminId(), sid);
        when(sessionValidator.validateAndTouch(sid))
                .thenReturn(SessionValidator.Result.idleExpired());

        RefreshRequest req = new RefreshRequest();
        req.setRefreshToken(tok);

        assertThatThrownBy(() -> underTest.refresh(req))
                .isInstanceOf(InvalidCredentialsException.class);
        verify(adminRepo, never()).findById(any());
    }

    @Test
    @DisplayName("refresh — enterprise-kind token rejected")
    void refresh_wrongTokenKind() {
        // Generate an enterprise refresh token using the same JwtUtil — has
        // token_kind=enterprise so the platform refresh endpoint must reject.
        String enterpriseRefresh = jwtUtil.generateRefreshToken(UUID.randomUUID(), UUID.randomUUID());
        RefreshRequest req = new RefreshRequest();
        req.setRefreshToken(enterpriseRefresh);

        assertThatThrownBy(() -> underTest.refresh(req))
                .isInstanceOf(InvalidCredentialsException.class);
    }

    @Test
    @DisplayName("refresh — token does not match the one stored in Redis (rotation guard)")
    void refresh_rotationGuard() {
        PlatformAdmin a = admin("admin@kaori.io", true);
        UUID sid = UUID.randomUUID();
        String stale = jwtUtil.generatePlatformRefreshToken(a.getAdminId(), sid);
        String fresh = jwtUtil.generatePlatformRefreshToken(a.getAdminId(), sid);
        when(sessionValidator.validateAndTouch(sid))
                .thenReturn(SessionValidator.Result.valid());
        // Redis has the fresh token, caller presents stale
        when(ops.get("platform_refresh:" + sid)).thenReturn(fresh);

        RefreshRequest req = new RefreshRequest();
        req.setRefreshToken(stale);
        assertThatThrownBy(() -> underTest.refresh(req))
                .isInstanceOf(InvalidCredentialsException.class);
    }

    // -------------------------------------------------------------------------
    // UA parser
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("parseDeviceLabel — well-known UAs produce readable labels")
    void parseUa() {
        assertThat(PlatformAuthService.parseDeviceLabel(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) Chrome/120.0"))
                .isEqualTo("Chrome trên macOS");
        assertThat(PlatformAuthService.parseDeviceLabel(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Safari/605"))
                .isEqualTo("Safari trên iOS");
        assertThat(PlatformAuthService.parseDeviceLabel(null)).isNull();
    }
}
