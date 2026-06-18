package com.kaorisystem.auth.service;

import com.kaorisystem.auth.dto.AuthDtos.*;
import com.kaorisystem.auth.model.PasswordResetToken;
import com.kaorisystem.auth.model.User;
import com.kaorisystem.auth.repository.PasswordResetTokenRepository;
import com.kaorisystem.auth.repository.UserRepository;
import com.kaorisystem.auth.security.JwtUtil;
import com.kaorisystem.auth.service.AuthService.InvalidCredentialsException;
import com.kaorisystem.auth.service.AuthService.LockoutException;
import com.kaorisystem.auth.service.PlatformKeyService;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.*;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.util.ReflectionTestUtils;

import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.time.Instant;
import java.util.Base64;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.BDDMockito.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("AuthService — business logic unit tests")
class AuthServiceTest {

    // -------------------------------------------------------------------------
    // Mocks
    // -------------------------------------------------------------------------
    @Mock private UserRepository               userRepository;
    @Mock private PasswordResetTokenRepository resetTokenRepository;
    @Mock private PasswordEncoder              passwordEncoder;
    @Mock private StringRedisTemplate          redis;
    @Mock private ValueOperations<String, String> valueOps;
    /** Sprint 7 PR B — replaces JavaMailSender. Best-effort by contract;
        we just need the constructor wiring to succeed and forgotPassword
        to call it once. */
    @Mock private NotificationClient           notificationClient;
    @Mock private PlatformKeyService           platformKeyService;
    @Mock private com.kaorisystem.auth.service.RlsBypassHelper rlsBypass;
    /** 3.1.a optional deps — getIfAvailable() returns null on the default mock,
        which matches the production "no platform-token kind, do nothing" path. */
    @Mock private org.springframework.beans.factory.ObjectProvider<com.kaorisystem.auth.repository.AdminSessionRepository> adminSessionRepoProvider;
    @Mock private org.springframework.beans.factory.ObjectProvider<SessionValidator> sessionValidatorProvider;
    /** 3.1.b — additional optional deps for the audit emit path on logout. */
    @Mock private org.springframework.beans.factory.ObjectProvider<PlatformAdminAuditService> auditServiceProvider;
    @Mock private org.springframework.beans.factory.ObjectProvider<com.kaorisystem.auth.repository.PlatformAdminRepository> adminRepoProvider;

    @InjectMocks
    private AuthService authService;

    // A real JwtUtil (with generated RSA keys) so token round-trips work
    private static JwtUtil jwtUtil;

    // Shared identifiers
    private static final UUID USER_ID       = UUID.randomUUID();
    private static final UUID ENTERPRISE_ID = UUID.randomUUID();
    private static final String ROLE        = "MANAGER";

    // -------------------------------------------------------------------------
    // Setup
    // -------------------------------------------------------------------------

    @BeforeAll
    static void buildRealJwtUtil() throws Exception {
        KeyPairGenerator gen = KeyPairGenerator.getInstance("RSA");
        gen.initialize(2048);
        KeyPair pair = gen.generateKeyPair();
        String privB64 = Base64.getEncoder().encodeToString(pair.getPrivate().getEncoded());
        String pubB64  = Base64.getEncoder().encodeToString(pair.getPublic().getEncoded());
        jwtUtil = new JwtUtil(privB64, pubB64, 15L, 7L);
    }

    @BeforeEach
    void injectRealJwtUtilAndSpringValues() {
        // @InjectMocks creates AuthService via constructor (all final fields) but
        // @Value-annotated non-final fields get Java defaults (0 / null).
        // We replicate the Spring defaults here so business logic behaves correctly.
        ReflectionTestUtils.setField(authService, "jwtUtil", jwtUtil);
        ReflectionTestUtils.setField(authService, "lockoutAttempts", 5);
        ReflectionTestUtils.setField(authService, "lockoutDurationSeconds", 900L);
        ReflectionTestUtils.setField(authService, "resetTokenTtlSeconds", 3600L);
        ReflectionTestUtils.setField(authService, "frontendUrl", "http://localhost:3000");

        // redis.opsForValue() is called in almost every path; lenient() suppresses
        // strict-stub warnings for the few tests that don't reach Redis at all
        // (e.g. logout_invalidToken_noOp where isValid() returns false early).
        lenient().when(redis.opsForValue()).thenReturn(valueOps);
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private User activeUser() {
        User u = new User();
        u.setUserId(USER_ID);
        u.setEnterpriseId(ENTERPRISE_ID);
        u.setEmail("test@kaori.vn");
        u.setPasswordHash("$hashed$");
        u.setFullName("Test User");
        u.setRole(ROLE);
        u.setStatus("active");
        return u;
    }

    // =========================================================================
    // LOGIN
    // =========================================================================

    @Test
    @DisplayName("login: valid credentials return accessToken and refreshToken")
    void login_success_returnsTokens() {
        // given
        LoginRequest req = new LoginRequest();
        req.setEmail("test@kaori.vn");
        req.setPassword("correct-password");

        given(valueOps.get("lockout:test@kaori.vn")).willReturn(null);
        given(userRepository.findByEmailIgnoreCase("test@kaori.vn"))
                .willReturn(Optional.of(activeUser()));
        given(passwordEncoder.matches("correct-password", "$hashed$")).willReturn(true);

        // when
        LoginResponse resp = authService.login(req);

        // then
        assertThat(resp.getAccessToken()).isNotBlank();
        assertThat(resp.getRefreshToken()).isNotBlank();
        assertThat(resp.getRole()).isEqualTo(ROLE);
        assertThat(resp.getUserId()).isEqualTo(USER_ID.toString());
        assertThat(resp.getEnterpriseId()).isEqualTo(ENTERPRISE_ID.toString());
        // refresh token must be stored in Redis
        then(valueOps).should().set(eq("refresh:" + USER_ID), anyString(), anyLong(), eq(TimeUnit.MILLISECONDS));
    }

    @Test
    @DisplayName("login: wrong password throws InvalidCredentialsException")
    void login_wrongPassword_throwsInvalidCredentials() {
        // given
        LoginRequest req = new LoginRequest();
        req.setEmail("test@kaori.vn");
        req.setPassword("wrong");

        given(valueOps.get("lockout:test@kaori.vn")).willReturn(null);
        given(userRepository.findByEmailIgnoreCase("test@kaori.vn"))
                .willReturn(Optional.of(activeUser()));
        given(passwordEncoder.matches("wrong", "$hashed$")).willReturn(false);
        given(valueOps.increment("login_attempts:test@kaori.vn")).willReturn(1L);

        // when / then
        assertThatThrownBy(() -> authService.login(req))
                .isInstanceOf(InvalidCredentialsException.class)
                .hasMessageContaining("Invalid email or password");
    }

    @Test
    @DisplayName("login: unknown email throws InvalidCredentialsException")
    void login_userNotFound_throwsInvalidCredentials() {
        // given
        LoginRequest req = new LoginRequest();
        req.setEmail("nobody@kaori.vn");
        req.setPassword("pass");

        given(valueOps.get("lockout:nobody@kaori.vn")).willReturn(null);
        given(userRepository.findByEmailIgnoreCase("nobody@kaori.vn")).willReturn(Optional.empty());
        given(valueOps.increment("login_attempts:nobody@kaori.vn")).willReturn(1L);

        // when / then
        assertThatThrownBy(() -> authService.login(req))
                .isInstanceOf(InvalidCredentialsException.class);
    }

    @Test
    @DisplayName("login: locked account (lockout key in Redis) throws LockoutException with remaining seconds")
    void login_lockedAccount_throwsLockoutException() {
        // given
        LoginRequest req = new LoginRequest();
        req.setEmail("locked@kaori.vn");
        req.setPassword("any");

        given(valueOps.get("lockout:locked@kaori.vn")).willReturn("1");
        given(redis.getExpire("lockout:locked@kaori.vn", TimeUnit.SECONDS)).willReturn(750L);

        // when / then
        assertThatThrownBy(() -> authService.login(req))
                .isInstanceOf(LockoutException.class)
                .satisfies(ex -> {
                    LockoutException le = (LockoutException) ex;
                    assertThat(le.getRemainingSeconds()).isEqualTo(750L);
                });
    }

    @Test
    @DisplayName("login: inactive user status throws InvalidCredentialsException")
    void login_inactiveUser_throwsInvalidCredentials() {
        // given
        LoginRequest req = new LoginRequest();
        req.setEmail("test@kaori.vn");
        req.setPassword("correct-password");

        User inactive = activeUser();
        inactive.setStatus("inactive");

        given(valueOps.get("lockout:test@kaori.vn")).willReturn(null);
        given(userRepository.findByEmailIgnoreCase("test@kaori.vn"))
                .willReturn(Optional.of(inactive));
        given(passwordEncoder.matches("correct-password", "$hashed$")).willReturn(true);

        // when / then
        assertThatThrownBy(() -> authService.login(req))
                .isInstanceOf(InvalidCredentialsException.class)
                .hasMessageContaining("inactive");
    }

    @Test
    @DisplayName("login: 5th failed attempt triggers lockout key in Redis")
    void login_afterMaxAttempts_setsLockoutKey() {
        // given
        LoginRequest req = new LoginRequest();
        req.setEmail("victim@kaori.vn");
        req.setPassword("bad");

        given(valueOps.get("lockout:victim@kaori.vn")).willReturn(null);
        given(userRepository.findByEmailIgnoreCase("victim@kaori.vn")).willReturn(Optional.empty());
        given(valueOps.increment("login_attempts:victim@kaori.vn")).willReturn(5L);

        // when
        assertThatThrownBy(() -> authService.login(req))
                .isInstanceOf(InvalidCredentialsException.class);

        // then — lockout key must be written
        then(valueOps).should().set(
                eq("lockout:victim@kaori.vn"),
                eq("1"),
                anyLong(),
                eq(TimeUnit.SECONDS));
    }

    // -------------------------------------------------------------------------
    // LOCKOUT — timer-reset bug regression suite
    //
    // The original code called redis.expire(countKey, …) on EVERY failed
    // attempt, refreshing the TTL each time. That made the fixed-window
    // lockout effectively sliding: a counter would never roll over while
    // the attacker kept probing inside the previous TTL. The fix uses
    // INCR's atomic return value and only sets the TTL when the counter
    // is first created (count == 1).
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("lockout: TTL is set on the FIRST failed attempt with the configured duration")
    void login_firstFailedAttempt_setsCounterTtlOnce() {
        // given
        LoginRequest req = new LoginRequest();
        req.setEmail("attacker@kaori.vn");
        req.setPassword("bad");
        given(valueOps.get("lockout:attacker@kaori.vn")).willReturn(null);
        given(userRepository.findByEmailIgnoreCase("attacker@kaori.vn"))
                .willReturn(Optional.empty());
        // INCR on a missing key creates it with value 1 → this is a fresh window
        given(valueOps.increment("login_attempts:attacker@kaori.vn")).willReturn(1L);

        // when
        assertThatThrownBy(() -> authService.login(req))
                .isInstanceOf(InvalidCredentialsException.class);

        // then — TTL set exactly once with the configured 900s duration
        then(redis).should()
                .expire("login_attempts:attacker@kaori.vn", 900L, TimeUnit.SECONDS);
    }

    @Test
    @DisplayName("lockout: subsequent failed attempts (count > 1) MUST NOT refresh the counter TTL")
    void login_subsequentFailedAttempts_doNotRefreshTtl() {
        // This is the regression guard for the timer-reset bug. INCR returning
        // any value other than 1 means the key already existed (and therefore
        // already has a TTL). Refreshing it would be the bug.
        LoginRequest req = new LoginRequest();
        req.setEmail("victim@kaori.vn");
        req.setPassword("bad");
        given(valueOps.get("lockout:victim@kaori.vn")).willReturn(null);
        given(userRepository.findByEmailIgnoreCase("victim@kaori.vn"))
                .willReturn(Optional.empty());
        given(valueOps.increment("login_attempts:victim@kaori.vn")).willReturn(2L);

        assertThatThrownBy(() -> authService.login(req))
                .isInstanceOf(InvalidCredentialsException.class);

        // EXPIRE must NOT be called — the existing TTL stays untouched.
        then(redis).should(never())
                .expire(eq("login_attempts:victim@kaori.vn"), anyLong(), any());
    }

    @Test
    @DisplayName("lockout: when triggered, the lockout key's TTL equals the configured duration (900s)")
    void login_lockoutKey_usesConfiguredDuration() {
        LoginRequest req = new LoginRequest();
        req.setEmail("victim@kaori.vn");
        req.setPassword("bad");
        given(valueOps.get("lockout:victim@kaori.vn")).willReturn(null);
        given(userRepository.findByEmailIgnoreCase("victim@kaori.vn"))
                .willReturn(Optional.empty());
        given(valueOps.increment("login_attempts:victim@kaori.vn")).willReturn(5L);

        assertThatThrownBy(() -> authService.login(req))
                .isInstanceOf(InvalidCredentialsException.class);

        // exact TTL — was anyLong() in the looser test above
        then(valueOps).should().set(
                eq("lockout:victim@kaori.vn"),
                eq("1"),
                eq(900L),
                eq(TimeUnit.SECONDS));
    }

    @Test
    @DisplayName("lockout: triggering deletes the failure-count key so the next window starts fresh")
    void login_lockoutTriggers_deletesCounterKey() {
        LoginRequest req = new LoginRequest();
        req.setEmail("victim@kaori.vn");
        req.setPassword("bad");
        given(valueOps.get("lockout:victim@kaori.vn")).willReturn(null);
        given(userRepository.findByEmailIgnoreCase("victim@kaori.vn"))
                .willReturn(Optional.empty());
        given(valueOps.increment("login_attempts:victim@kaori.vn")).willReturn(5L);

        assertThatThrownBy(() -> authService.login(req))
                .isInstanceOf(InvalidCredentialsException.class);

        then(redis).should().delete("login_attempts:victim@kaori.vn");
    }

    @Test
    @DisplayName("lockout: failed attempts BEFORE threshold do NOT set the lockout key")
    void login_failedAttemptsBelowThreshold_doNotSetLockoutKey() {
        // attempts 1..4 just bump the counter; only attempt 5 locks.
        LoginRequest req = new LoginRequest();
        req.setEmail("victim@kaori.vn");
        req.setPassword("bad");
        given(valueOps.get("lockout:victim@kaori.vn")).willReturn(null);
        given(userRepository.findByEmailIgnoreCase("victim@kaori.vn"))
                .willReturn(Optional.empty());
        given(valueOps.increment("login_attempts:victim@kaori.vn")).willReturn(4L);

        assertThatThrownBy(() -> authService.login(req))
                .isInstanceOf(InvalidCredentialsException.class);

        // No lockout write at attempt 4
        then(valueOps).should(never())
                .set(eq("lockout:victim@kaori.vn"), eq("1"), anyLong(), any());
        // Counter not deleted either — it must persist for the next attempt
        then(redis).should(never()).delete("login_attempts:victim@kaori.vn");
    }

    @Test
    @DisplayName("lockout: paced attacker — attempts in separate windows each start a new counter (no accumulation)")
    void login_pacedAttempts_doNotAccumulateAcrossExpiredWindows() {
        // When the counter key has expired between attempts, INCR creates a
        // fresh key returning 1 each time. Both attempts therefore look like
        // "first failure" of their respective windows, EXPIRE is called in
        // both, and the lockout never triggers from these two paced attempts.
        // This is the correct fixed-window behaviour — exactly what the
        // timer-reset bug used to break.
        LoginRequest req = new LoginRequest();
        req.setEmail("paced@kaori.vn");
        req.setPassword("bad");
        given(valueOps.get("lockout:paced@kaori.vn")).willReturn(null);
        given(userRepository.findByEmailIgnoreCase("paced@kaori.vn"))
                .willReturn(Optional.empty());
        given(valueOps.increment("login_attempts:paced@kaori.vn")).willReturn(1L);

        assertThatThrownBy(() -> authService.login(req))
                .isInstanceOf(InvalidCredentialsException.class);
        assertThatThrownBy(() -> authService.login(req))
                .isInstanceOf(InvalidCredentialsException.class);

        // Each attempt was a "first attempt" of its window → EXPIRE called twice
        then(redis).should(org.mockito.Mockito.times(2))
                .expire("login_attempts:paced@kaori.vn", 900L, TimeUnit.SECONDS);
        // No lockout fired from these paced attempts
        then(valueOps).should(never())
                .set(eq("lockout:paced@kaori.vn"), eq("1"), anyLong(), any());
    }

    @Test
    @DisplayName("login success: clears BOTH the lockout and the failure-count key (reset behaviour)")
    void login_success_clearsLockoutAndCounterKeys() {
        LoginRequest req = new LoginRequest();
        req.setEmail("test@kaori.vn");
        req.setPassword("correct-password");
        given(valueOps.get("lockout:test@kaori.vn")).willReturn(null);
        given(userRepository.findByEmailIgnoreCase("test@kaori.vn"))
                .willReturn(Optional.of(activeUser()));
        given(passwordEncoder.matches("correct-password", "$hashed$")).willReturn(true);

        authService.login(req);

        then(redis).should().delete("lockout:test@kaori.vn");
        then(redis).should().delete("login_attempts:test@kaori.vn");
    }

    // =========================================================================
    // LOGOUT
    // =========================================================================

    @Test
    @DisplayName("logout: valid access token is blacklisted in Redis with positive TTL")
    void logout_validToken_blacklistsInRedis() {
        // given
        String token = jwtUtil.generateAccessToken(USER_ID, ENTERPRISE_ID, ROLE);

        // when
        authService.logout(token);

        // then — blacklist key is written
        then(valueOps).should().set(
                eq("blacklist:" + token),
                eq("1"),
                longThat(ttl -> ttl > 0),
                eq(TimeUnit.MILLISECONDS));
        // refresh key is also deleted
        then(redis).should().delete("refresh:" + USER_ID);
    }

    @Test
    @DisplayName("logout: invalid/malformed token results in no Redis write")
    void logout_invalidToken_noOp() {
        // given
        String badToken = "not.a.real.jwt";

        // when
        authService.logout(badToken);

        // then — isValid returned false, so no Redis operations at all
        then(valueOps).shouldHaveNoInteractions();
        then(redis).should(never()).delete(anyString());
    }

    // =========================================================================
    // REFRESH
    // =========================================================================

    @Test
    @DisplayName("refresh: valid refresh token stored in Redis issues a new token pair")
    void refresh_validToken_returnsNewPair() {
        // given
        String refreshToken = jwtUtil.generateRefreshToken(USER_ID, ENTERPRISE_ID);
        RefreshRequest req  = new RefreshRequest();
        req.setRefreshToken(refreshToken);

        given(valueOps.get("refresh:" + USER_ID)).willReturn(refreshToken);
        given(userRepository.findById(USER_ID)).willReturn(Optional.of(activeUser()));
        // B3 PR #8 — jti SETNX dedup. First use of a refresh JWT returns
        // true (no prior key); rotation then proceeds normally.
        given(valueOps.setIfAbsent(anyString(), eq("1"), anyLong(), eq(TimeUnit.MILLISECONDS)))
                .willReturn(true);

        // when
        LoginResponse resp = authService.refresh(req);

        // then
        assertThat(resp.getAccessToken()).isNotBlank();
        assertThat(resp.getRefreshToken()).isNotBlank();
        assertThat(resp.getUserId()).isEqualTo(USER_ID.toString());
    }

    @Test
    @DisplayName("refresh: refresh token not matching stored value (revoked) throws InvalidCredentials")
    void refresh_tokenRevoked_throws() {
        // given
        String refreshToken = jwtUtil.generateRefreshToken(USER_ID, ENTERPRISE_ID);
        RefreshRequest req  = new RefreshRequest();
        req.setRefreshToken(refreshToken);

        given(valueOps.get("refresh:" + USER_ID)).willReturn("DIFFERENT_STORED_TOKEN");

        // when / then
        assertThatThrownBy(() -> authService.refresh(req))
                .isInstanceOf(InvalidCredentialsException.class)
                .hasMessageContaining("revoked");
    }

    @Test
    @DisplayName("refresh: submitting an access token (type='access') throws InvalidCredentials")
    void refresh_notRefreshType_throws() {
        // given — access token instead of refresh token
        String accessToken = jwtUtil.generateAccessToken(USER_ID, ENTERPRISE_ID, ROLE);
        RefreshRequest req = new RefreshRequest();
        req.setRefreshToken(accessToken);

        // when / then
        assertThatThrownBy(() -> authService.refresh(req))
                .isInstanceOf(InvalidCredentialsException.class)
                .hasMessageContaining("Not a refresh token");
    }

    // =========================================================================
    // FORGOT PASSWORD
    // =========================================================================

    @Test
    @DisplayName("forgotPassword: existing email triggers exactly one email send")
    void forgotPassword_existingEmail_sendsEmail() {
        // given
        ForgotPasswordRequest req = new ForgotPasswordRequest();
        req.setEmail("known@kaori.vn");

        given(userRepository.findByEmailIgnoreCase("known@kaori.vn"))
                .willReturn(Optional.of(activeUser()));

        // when
        authService.forgotPassword(req);

        // then — Sprint 7 PR B: NotificationClient replaces JavaMailSender.
        // forgotPassword uses user.email (from DB lookup), not request.email,
        // so the actual recipient is whatever activeUser() returns.
        then(notificationClient).should(times(1))
                .sendResetPassword(eq("test@kaori.vn"), anyString(), anyString());
        then(resetTokenRepository).should(times(1)).save(any(PasswordResetToken.class));
    }

    @Test
    @DisplayName("forgotPassword: non-existent email does not throw and does not send email (anti-enumeration)")
    void forgotPassword_nonExistentEmail_noException() {
        // given
        ForgotPasswordRequest req = new ForgotPasswordRequest();
        req.setEmail("ghost@kaori.vn");

        given(userRepository.findByEmailIgnoreCase("ghost@kaori.vn")).willReturn(Optional.empty());

        // when / then — must NOT throw, must NOT send anything
        assertThatCode(() -> authService.forgotPassword(req))
                .doesNotThrowAnyException();
        then(notificationClient).shouldHaveNoInteractions();
    }

    // =========================================================================
    // RESET PASSWORD
    // =========================================================================

    @Test
    @DisplayName("resetPassword: valid (non-expired) token updates the user's password hash")
    void resetPassword_validToken_updatesPassword() {
        // given
        String rawToken = "raw-reset-token";
        ResetPasswordRequest req = new ResetPasswordRequest();
        req.setToken(rawToken);
        req.setNewPassword("NewSecureP@ss1");

        PasswordResetToken prt = new PasswordResetToken();
        prt.setTokenId(UUID.randomUUID());
        prt.setUserId(USER_ID);
        prt.setExpiresAt(Instant.now().plusSeconds(3600));

        // The service sha256s the raw token before querying — match any hash string
        given(resetTokenRepository.findByTokenHashAndUsedAtIsNullAndExpiresAtAfter(
                anyString(), any(Instant.class)))
                .willReturn(Optional.of(prt));
        given(userRepository.findById(USER_ID)).willReturn(Optional.of(activeUser()));
        given(passwordEncoder.encode("NewSecureP@ss1")).willReturn("$newHash$");

        // when
        authService.resetPassword(req);

        // then — user saved with new hash
        ArgumentCaptor<User> userCaptor = ArgumentCaptor.forClass(User.class);
        then(userRepository).should().save(userCaptor.capture());
        assertThat(userCaptor.getValue().getPasswordHash()).isEqualTo("$newHash$");

        // token marked as used
        then(resetTokenRepository).should().markUsed(eq(prt.getTokenId()), any(Instant.class));
    }

    @Test
    @DisplayName("resetPassword: expired/non-existent token throws InvalidCredentialsException")
    void resetPassword_expiredToken_throws() {
        // given
        ResetPasswordRequest req = new ResetPasswordRequest();
        req.setToken("expired-token");
        req.setNewPassword("NewP@ss1234");

        given(resetTokenRepository.findByTokenHashAndUsedAtIsNullAndExpiresAtAfter(
                anyString(), any(Instant.class)))
                .willReturn(Optional.empty());

        // when / then
        assertThatThrownBy(() -> authService.resetPassword(req))
                .isInstanceOf(InvalidCredentialsException.class)
                .hasMessageContaining("Invalid or expired reset token");
    }

    @Test
    @DisplayName("resetPassword: after success, refresh token in Redis is deleted to invalidate all sessions")
    void resetPassword_invalidatesRefreshToken() {
        // given
        ResetPasswordRequest req = new ResetPasswordRequest();
        req.setToken("valid-token");
        req.setNewPassword("AnotherP@ss99");

        PasswordResetToken prt = new PasswordResetToken();
        prt.setTokenId(UUID.randomUUID());
        prt.setUserId(USER_ID);
        prt.setExpiresAt(Instant.now().plusSeconds(3600));

        given(resetTokenRepository.findByTokenHashAndUsedAtIsNullAndExpiresAtAfter(
                anyString(), any(Instant.class)))
                .willReturn(Optional.of(prt));
        given(userRepository.findById(USER_ID)).willReturn(Optional.of(activeUser()));
        given(passwordEncoder.encode("AnotherP@ss99")).willReturn("$anotherHash$");

        // when
        authService.resetPassword(req);

        // then — refresh key for this user must be deleted
        then(redis).should().delete("refresh:" + USER_ID);
    }

    // =========================================================================
    // ACTIVATE WORKSPACE
    // =========================================================================

    @Test
    @DisplayName("activateWorkspace: valid key creates MANAGER user, revokes key, and returns tokens")
    void activateWorkspace_validKey_createsAdminAndReturnsTokens() {
        // given
        ActivateKeyRequest req = new ActivateKeyRequest();
        req.setWorkspaceKey("raw-workspace-key");
        req.setAdminEmail("admin@kaori.vn");
        req.setAdminPassword("Admin@P@ss1");
        req.setAdminName("First Admin");

        // Key validation is delegated to PlatformKeyService (post F-009 refactor).
        given(platformKeyService.isActiveKey("raw-workspace-key")).willReturn(true);
        given(platformKeyService.findEnterpriseIdByKey("raw-workspace-key"))
                .willReturn(ENTERPRISE_ID);
        given(passwordEncoder.encode("Admin@P@ss1")).willReturn("$adminHash$");

        // when
        LoginResponse resp = authService.activateWorkspace(req);

        // then
        assertThat(resp.getAccessToken()).isNotBlank();
        assertThat(resp.getRefreshToken()).isNotBlank();
        assertThat(resp.getRole()).isEqualTo("MANAGER");

        ArgumentCaptor<User> cap = ArgumentCaptor.forClass(User.class);
        then(userRepository).should().save(cap.capture());
        assertThat(cap.getValue().getRole()).isEqualTo("MANAGER");
        assertThat(cap.getValue().getStatus()).isEqualTo("active");
        assertThat(cap.getValue().getEmail()).isEqualTo("admin@kaori.vn");

        // Consumption of the one-time key now happens on PlatformKeyService, not UserRepository.
        then(platformKeyService).should().consumeKey("raw-workspace-key");
    }

    @Test
    @DisplayName("activateWorkspace: invalid or revoked key throws InvalidCredentialsException")
    void activateWorkspace_invalidKey_throws() {
        // given
        ActivateKeyRequest req = new ActivateKeyRequest();
        req.setWorkspaceKey("bad-key");
        req.setAdminEmail("admin@kaori.vn");
        req.setAdminPassword("Admin@P@ss1");

        given(platformKeyService.isActiveKey("bad-key")).willReturn(false);

        // when / then
        assertThatThrownBy(() -> authService.activateWorkspace(req))
                .isInstanceOf(InvalidCredentialsException.class)
                .hasMessageContaining("Invalid or revoked workspace key");
    }

    // =========================================================================
    // P1-S1 (P2-M20-007) — first-login force-change-password flow
    // =========================================================================

    @Test
    @DisplayName("login: must_change_password=true on user surfaces in LoginResponse")
    void login_invitedUser_surfacesMustChangePassword() {
        LoginRequest req = new LoginRequest();
        req.setEmail("invited@kaori.vn");
        req.setPassword("temp-pass");

        User u = activeUser();
        u.setEmail("invited@kaori.vn");
        u.setMustChangePassword(true);

        given(valueOps.get("lockout:invited@kaori.vn")).willReturn(null);
        given(userRepository.findByEmailIgnoreCase("invited@kaori.vn"))
                .willReturn(Optional.of(u));
        given(passwordEncoder.matches("temp-pass", "$hashed$")).willReturn(true);

        LoginResponse resp = authService.login(req);

        assertThat(resp.getMustChangePassword()).isTrue();
    }

    @Test
    @DisplayName("login: must_change_password=null/false on user emits FALSE (never null)")
    void login_normalUser_mustChangePasswordIsFalse() {
        LoginRequest req = new LoginRequest();
        req.setEmail("test@kaori.vn");
        req.setPassword("correct-password");

        User u = activeUser();
        u.setMustChangePassword(null);  // legacy users from before migration 039

        given(valueOps.get("lockout:test@kaori.vn")).willReturn(null);
        given(userRepository.findByEmailIgnoreCase("test@kaori.vn"))
                .willReturn(Optional.of(u));
        given(passwordEncoder.matches("correct-password", "$hashed$")).willReturn(true);

        LoginResponse resp = authService.login(req);

        // Defensive default: never serialise null. FE expects boolean, not absence.
        assertThat(resp.getMustChangePassword()).isFalse();
    }

    @Test
    @DisplayName("resetPassword: clears must_change_password (closes invite loop)")
    void resetPassword_clearsMustChangePassword() {
        ResetPasswordRequest req = new ResetPasswordRequest();
        req.setToken("invite-token");
        req.setNewPassword("FinalP@ss1");

        PasswordResetToken prt = new PasswordResetToken();
        prt.setTokenId(UUID.randomUUID());
        prt.setUserId(USER_ID);
        prt.setExpiresAt(Instant.now().plusSeconds(3600));

        User invited = activeUser();
        invited.setMustChangePassword(true);

        given(resetTokenRepository.findByTokenHashAndUsedAtIsNullAndExpiresAtAfter(
                anyString(), any(Instant.class)))
                .willReturn(Optional.of(prt));
        given(userRepository.findById(USER_ID)).willReturn(Optional.of(invited));
        given(passwordEncoder.encode("FinalP@ss1")).willReturn("$finalHash$");

        authService.resetPassword(req);

        ArgumentCaptor<User> userCaptor = ArgumentCaptor.forClass(User.class);
        then(userRepository).should().save(userCaptor.capture());
        assertThat(userCaptor.getValue().getMustChangePassword()).isFalse();
    }

    @Test
    @DisplayName("changeOwnPassword: valid current password rotates hash and clears must_change_password")
    void changeOwnPassword_validCurrent_rotates() {
        User u = activeUser();
        u.setMustChangePassword(true);
        u.setPasswordHash("$current$");

        given(userRepository.findById(USER_ID)).willReturn(Optional.of(u));
        given(passwordEncoder.matches("current", "$current$")).willReturn(true);
        given(passwordEncoder.encode("New@Pass1")).willReturn("$newHash$");

        authService.changeOwnPassword(USER_ID, "current", "New@Pass1");

        ArgumentCaptor<User> captor = ArgumentCaptor.forClass(User.class);
        then(userRepository).should().save(captor.capture());
        assertThat(captor.getValue().getPasswordHash()).isEqualTo("$newHash$");
        assertThat(captor.getValue().getMustChangePassword()).isFalse();
        // Refresh tokens for this user must be wiped so other devices re-auth.
        then(redis).should().delete("refresh:" + USER_ID);
    }

    @Test
    @DisplayName("changeOwnPassword: wrong current password throws InvalidCredentials and never persists")
    void changeOwnPassword_wrongCurrent_throws() {
        User u = activeUser();
        u.setPasswordHash("$current$");

        given(userRepository.findById(USER_ID)).willReturn(Optional.of(u));
        given(passwordEncoder.matches("wrong", "$current$")).willReturn(false);

        assertThatThrownBy(() ->
                authService.changeOwnPassword(USER_ID, "wrong", "New@Pass1"))
                .isInstanceOf(InvalidCredentialsException.class)
                .hasMessageContaining("Current password is incorrect");

        then(userRepository).should(never()).save(any());
        then(redis).should(never()).delete(anyString());
    }

    @Test
    @DisplayName("changeOwnPassword: unknown user throws InvalidCredentials")
    void changeOwnPassword_unknownUser_throws() {
        UUID ghost = UUID.randomUUID();
        given(userRepository.findById(ghost)).willReturn(Optional.empty());

        assertThatThrownBy(() ->
                authService.changeOwnPassword(ghost, "anything", "New@Pass1"))
                .isInstanceOf(InvalidCredentialsException.class)
                .hasMessageContaining("User not found");

        then(userRepository).should(never()).save(any());
    }
}
