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
import com.kaorisystem.auth.service.AuthService.LockoutException;
import io.jsonwebtoken.Claims;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.HexFormat;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

/**
 * Batch 3.1.a + B3 PR #8 — Platform admin login + refresh + MFA enforcement.
 *
 * <p>Distinct from {@link AuthService} (which serves enterprise users):
 *
 * <ul>
 *   <li>Backed by {@code platform_admins} (not {@code enterprise_users}).</li>
 *   <li>Lockout key namespace prefixed with {@code platform_} so an
 *       enumeration attack against an admin email cannot lock out an
 *       enterprise user that shares the same address.</li>
 *   <li>Issues JWTs via {@link JwtUtil#generatePlatformAccessToken} which
 *       carry {@code session_id} + {@code token_kind=platform} claims.</li>
 *   <li>Inserts an {@code admin_sessions} row on success — the surface
 *       {@link com.kaorisystem.auth.controller.PlatformSecurityController}
 *       lists.</li>
 * </ul>
 *
 * <h3>B3 PR #8 — MFA enforcement at login (#10 auth security)</h3>
 *
 * <p>Before B3 PR #8 the {@code mfa_enabled} flag rode along on the response
 * for FE display only — a leaked password was enough to open the platform
 * even when MFA was on. B3 PR #8 closes that gap with the 2-step gate:
 *
 * <ol>
 *   <li>{@link #login} — credentials valid AND {@code admin.mfa_enabled=true}
 *       → create an {@code mfa_challenges} row, mint a short-lived JWT
 *       carrying {@code challenge_id}, return {@code mfaRequired=true} with
 *       NO access/refresh tokens. {@code admin_sessions} is NOT created
 *       because we don't yet know it's the right admin.</li>
 *   <li>{@link #verifyMfaChallenge} — accepts the challenge JWT + a 6-digit
 *       TOTP code, verifies via {@link TotpService}, marks the row used
 *       (one-time-use guard), THEN creates the session + access/refresh.</li>
 * </ol>
 *
 * <p>Refresh-token replay (jti SETNX dedup) is enforced at the gateway
 * through {@code JwtAuthFilter}'s Redis check — this service only handles
 * issuance.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class PlatformAuthService {

    private static final String LOCKOUT_PREFIX = "platform_lockout:";
    private static final String COUNT_PREFIX   = "platform_login_attempts:";
    private static final String REFRESH_PREFIX = "platform_refresh:";

    /** Default 5-minute MFA challenge TTL. Long enough to fish out the phone, short enough to limit replay. */
    private static final long MFA_CHALLENGE_TTL_MS = 5L * 60 * 1000;

    /** Per-challenge attempt cap. Distinct from the per-admin Redis lockout in AdminSecurityService. */
    private static final int  MFA_CHALLENGE_MAX_ATTEMPTS = 5;

    private final PlatformAdminRepository  adminRepo;
    private final AdminSessionRepository   sessionRepo;
    private final MfaChallengeRepository   challengeRepo;
    private final PasswordEncoder          passwordEncoder;
    private final JwtUtil                  jwtUtil;
    private final StringRedisTemplate      redis;
    private final SessionValidator         sessionValidator;
    private final TotpService              totpService;
    private final PlatformAdminAuditService auditService;

    @Value("${kaori.login-lockout-attempts:5}")
    private int lockoutAttempts;

    @Value("${kaori.login-lockout-duration-seconds:900}")
    private long lockoutDurationSeconds;

    // =========================================================================
    // login (first leg)
    // =========================================================================

    @Transactional
    public PlatformLoginResult login(LoginRequest req, String ipAddress, String userAgent) {
        String emailKey  = req.getEmail().toLowerCase();
        String lockoutKey = LOCKOUT_PREFIX + emailKey;
        String countKey   = COUNT_PREFIX   + emailKey;

        // Lockout check — same Redis pattern as AuthService.login
        String locked = redis.opsForValue().get(lockoutKey);
        if (locked != null) {
            Long ttl = redis.getExpire(lockoutKey, TimeUnit.SECONDS);
            throw new LockoutException(
                    "Account locked. Try again in " + ttl + " seconds.", ttl);
        }

        Optional<PlatformAdmin> opt = adminRepo.findByEmailIgnoreCase(req.getEmail());
        if (opt.isEmpty()
                || opt.get().getPasswordHash() == null
                || !passwordEncoder.matches(req.getPassword(), opt.get().getPasswordHash())) {
            registerFailedAttempt(lockoutKey, countKey);
            throw new InvalidCredentialsException("Invalid email or password.");
        }

        PlatformAdmin admin = opt.get();
        if (!admin.isActive()) {
            // Deactivated admin — same generic message to avoid distinguishing
            // "wrong password" from "deactivated" (anti-enumeration).
            throw new InvalidCredentialsException("Invalid email or password.");
        }

        // Success — clear lockout counters
        redis.delete(lockoutKey);
        redis.delete(countKey);

        // B3 PR #8 — MFA gate. mfa_enabled is true only after verifyMfa flipped it.
        // mfa_secret_enc set without mfa_enabled means enrollment-in-progress;
        // we treat that as "no MFA yet" so the admin can finish enrolling.
        if (admin.isMfaEnabled() && admin.getMfaSecretEnc() != null) {
            return issueMfaChallenge(admin, ipAddress, userAgent);
        }

        return completeLogin(admin, ipAddress, userAgent);
    }

    /**
     * B3 PR #8 — short-lived challenge token + DB row. NO admin_session is
     * created at this step (the admin hasn't proven possession of the second
     * factor yet); the session is born inside {@link #verifyMfaChallenge}.
     */
    private PlatformLoginResult issueMfaChallenge(PlatformAdmin admin, String ipAddress, String userAgent) {
        UUID challengeId = UUID.randomUUID();
        String token = jwtUtil.generatePlatformMfaChallengeToken(
                admin.getAdminId(), challengeId, MFA_CHALLENGE_TTL_MS);

        MfaChallenge ch = new MfaChallenge();
        ch.setChallengeId(challengeId);
        ch.setAdminId(admin.getAdminId());
        ch.setChallengeTokenHash(sha256Hex(token));
        ch.setExpiresAt(Instant.now().plusMillis(MFA_CHALLENGE_TTL_MS));
        ch.setIpAddress(truncate(ipAddress, 64));
        ch.setUserAgent(truncate(userAgent, 500));
        challengeRepo.save(ch);

        log.info("platform.auth.mfa_challenge_issued admin_id={} challenge_id={}",
                admin.getAdminId(), challengeId);

        auditService.recordAudit(admin.getAdminId(),
                PlatformAdminAuditService.EVT_MFA_LOGIN_CHALLENGED,
                admin.getAdminId(), admin.getEmail(), admin.getRole(),
                challengeId.toString(), "stage=login_first_leg", ipAddress);

        return PlatformLoginResult.mfaRequired(
                admin.getAdminId(), token, MFA_CHALLENGE_TTL_MS / 1000L);
    }

    // =========================================================================
    // MFA verify (second leg)
    // =========================================================================

    /**
     * B3 PR #8 — completes the 2-step login. The challenge JWT is parsed +
     * its hash looked up; the row's {@code used_at} guard is flipped inside
     * the success transaction so a concurrent second use surfaces as
     * "already used", not as a TOTP race.
     *
     * <p>Per-challenge attempts cap at {@value #MFA_CHALLENGE_MAX_ATTEMPTS} —
     * once a single challenge is exhausted the admin must {@code /login} again
     * to mint a new one. This is on top of the per-admin 15-minute lockout
     * that {@link AdminSecurityService#verifyMfa} enforces (used by the
     * /security/mfa/verify enrollment path).
     */
    @Transactional
    public PlatformLoginResult verifyMfaChallenge(MfaVerifyRequest req, String ipAddress, String userAgent) {
        if (!jwtUtil.isValid(req.getMfaChallengeToken())) {
            throw new InvalidCredentialsException("Invalid or expired MFA challenge.");
        }
        Claims claims;
        try {
            claims = jwtUtil.validateAndParse(req.getMfaChallengeToken());
        } catch (RuntimeException e) {
            throw new InvalidCredentialsException("Invalid MFA challenge token.");
        }
        if (!"mfa_challenge".equals(claims.get("token_kind"))
                || !"mfa_challenge".equals(claims.get("type"))) {
            throw new InvalidCredentialsException("Wrong token kind for MFA verify.");
        }

        UUID adminId      = UUID.fromString(claims.getSubject());
        UUID challengeId  = UUID.fromString(String.valueOf(claims.get("challenge_id")));

        // Look up by HASH (not id) so a forged challenge_id but a valid signature
        // still misses — the row binding is on the token hash, not the JWT body.
        MfaChallenge ch = challengeRepo.findByChallengeTokenHash(sha256Hex(req.getMfaChallengeToken()))
                .orElseThrow(() -> new InvalidCredentialsException("MFA challenge not found."));

        // Defence in depth: ensure the row is the one the JWT claims to be.
        if (!ch.getChallengeId().equals(challengeId) || !ch.getAdminId().equals(adminId)) {
            throw new InvalidCredentialsException("MFA challenge mismatch.");
        }

        Instant now = Instant.now();
        if (ch.isExpired(now)) {
            throw new MfaChallengeExpiredException("MFA challenge has expired. Please sign in again.");
        }
        if (ch.isUsed()) {
            // Either the happy path already burned it (replay), or attempts hit cap (closed).
            throw new InvalidCredentialsException("MFA challenge already used or closed.");
        }
        if (ch.getAttempts() >= MFA_CHALLENGE_MAX_ATTEMPTS) {
            // Belt-and-suspenders: the row should already be marked used when
            // it hit the cap, but if a writer failed to mark it (best-effort
            // audit failures, etc.), reject anyway.
            throw new InvalidCredentialsException("MFA challenge attempts exhausted.");
        }

        PlatformAdmin admin = adminRepo.findById(adminId)
                .orElseThrow(() -> new InvalidCredentialsException("Admin not found."));
        if (!admin.isActive()) {
            throw new InvalidCredentialsException("Admin is inactive.");
        }
        if (admin.getMfaSecretEnc() == null || !admin.isMfaEnabled()) {
            // Defence in depth — admin disabled MFA between login and verify.
            // Treat as a malformed flow: the FE should NOT have surfaced the
            // verify page. Force them to re-login.
            throw new InvalidCredentialsException("MFA is no longer required for this account.");
        }

        byte[] secret = totpService.decrypt(admin.getMfaSecretEnc());
        if (!totpService.verify(secret, req.getCode())) {
            challengeRepo.incrementAttempts(challengeId);
            int newAttempts = ch.getAttempts() + 1;
            boolean exhausted = newAttempts >= MFA_CHALLENGE_MAX_ATTEMPTS;
            if (exhausted) {
                // Burn the row — re-login required to mint a new one.
                challengeRepo.markUsedIfPending(challengeId, now);
            }
            log.info("platform.auth.mfa_login_failed admin_id={} challenge_id={} attempts={}/{} exhausted={}",
                    adminId, challengeId, newAttempts, MFA_CHALLENGE_MAX_ATTEMPTS, exhausted);
            auditService.recordAudit(adminId,
                    PlatformAdminAuditService.EVT_MFA_LOGIN_FAILED,
                    adminId, admin.getEmail(), admin.getRole(),
                    challengeId.toString(),
                    "attempts=" + newAttempts + "/" + MFA_CHALLENGE_MAX_ATTEMPTS
                            + (exhausted ? " exhausted=true" : ""),
                    ipAddress);
            throw new InvalidCredentialsException(
                    exhausted
                        ? "Invalid code. Challenge exhausted; please sign in again."
                        : "Invalid MFA code.");
        }

        // Success — flip used_at first so a concurrent second verify finds
        // it closed (one-time-use guard).
        int flipped = challengeRepo.markUsedIfPending(challengeId, now);
        if (flipped == 0) {
            // A concurrent winner already used this row.
            throw new InvalidCredentialsException("MFA challenge already used.");
        }

        // Clear admin's last-login timestamp + create the real session.
        admin.setLastLoginAt(now);
        adminRepo.save(admin);
        PlatformLoginResult result = completeLogin(admin, ipAddress, userAgent);

        log.info("platform.auth.mfa_login_verified admin_id={} challenge_id={} session_id={}",
                adminId, challengeId, result.sessionId());
        auditService.recordAudit(adminId,
                PlatformAdminAuditService.EVT_MFA_LOGIN_VERIFIED,
                adminId, admin.getEmail(), admin.getRole(),
                challengeId.toString(),
                "session_id=" + result.sessionId(),
                ipAddress);

        return result;
    }

    /**
     * Shared "issue full session + tokens" path used by the no-MFA login path
     * and the post-MFA-verify path. Splits out admin_session creation so MFA
     * users don't get a session row on the first leg.
     */
    private PlatformLoginResult completeLogin(PlatformAdmin admin, String ipAddress, String userAgent) {
        admin.setLastLoginAt(Instant.now());
        adminRepo.save(admin);

        AdminSession session = new AdminSession();
        session.setAdminId(admin.getAdminId());
        session.setIpAddress(truncate(ipAddress, 64));
        session.setUserAgent(truncate(userAgent, 500));
        session.setDeviceLabel(parseDeviceLabel(userAgent));
        AdminSession saved = sessionRepo.save(session);

        String accessToken  = jwtUtil.generatePlatformAccessToken(
                admin.getAdminId(), admin.getRole(), saved.getSessionId());
        String refreshToken = jwtUtil.generatePlatformRefreshToken(
                admin.getAdminId(), saved.getSessionId());
        redis.opsForValue().set(REFRESH_PREFIX + saved.getSessionId(), refreshToken,
                jwtUtil.getRefreshTokenTtlMs(), TimeUnit.MILLISECONDS);

        log.info("platform.auth.login admin_id={} session_id={}",
                admin.getAdminId(), saved.getSessionId());

        return PlatformLoginResult.session(
                accessToken, refreshToken,
                saved.getSessionId(), admin.getAdminId(),
                admin.getRole(), admin.isMfaEnabled(),
                jwtUtil.getAccessTokenTtlMs() / 1000L);
    }

    // =========================================================================
    // refresh
    // =========================================================================

    @Transactional
    public PlatformLoginResult refresh(RefreshRequest req) {
        if (!jwtUtil.isValid(req.getRefreshToken())) {
            throw new InvalidCredentialsException("Invalid or expired refresh token.");
        }
        Claims claims = jwtUtil.validateAndParse(req.getRefreshToken());
        if (!"refresh".equals(claims.get("type"))
                || !"platform".equals(claims.get("token_kind"))) {
            throw new InvalidCredentialsException("Not a platform refresh token.");
        }

        UUID adminId   = UUID.fromString(claims.getSubject());
        UUID sessionId = UUID.fromString(String.valueOf(claims.get("session_id")));

        // Session must still be alive — this also touches last_active_at and
        // enforces idle/absolute timeouts. A revoked session cannot refresh.
        SessionValidator.Result vr = sessionValidator.validateAndTouch(sessionId);
        if (vr.status() != SessionValidator.Status.VALID) {
            throw new InvalidCredentialsException("Session is no longer active.");
        }

        // Refresh-token rotation: the stored token must match the one presented.
        // B3 PR #8 — also burn the presented refresh's jti via Redis SETNX so
        // a parallel second use of the SAME refresh fails (closes the
        // race where the equality check passed but the rotation update
        // hadn't landed yet).
        String stored = redis.opsForValue().get(REFRESH_PREFIX + sessionId);
        if (!req.getRefreshToken().equals(stored)) {
            throw new InvalidCredentialsException("Refresh token has been revoked.");
        }

        String jti = String.valueOf(claims.get("jti"));
        if (jti != null && !"null".equals(jti) && !jti.isBlank()) {
            // Token-bound TTL — at most until the refresh expiry. Burning it
            // for that window is enough; once expired, signature check fails
            // anyway.
            long ttlMs = Math.max(1L, claims.getExpiration().getTime() - System.currentTimeMillis());
            Boolean firstUse = redis.opsForValue().setIfAbsent(
                    "jwt:jti:used:" + jti, "1", ttlMs, TimeUnit.MILLISECONDS);
            if (Boolean.FALSE.equals(firstUse)) {
                throw new TokenReplayException("Refresh token has already been used.");
            }
        }

        PlatformAdmin admin = adminRepo.findById(adminId)
                .orElseThrow(() -> new InvalidCredentialsException("Admin not found."));
        if (!admin.isActive()) {
            throw new InvalidCredentialsException("Admin is inactive.");
        }

        String newAccess  = jwtUtil.generatePlatformAccessToken(
                adminId, admin.getRole(), sessionId);
        String newRefresh = jwtUtil.generatePlatformRefreshToken(adminId, sessionId);
        redis.opsForValue().set(REFRESH_PREFIX + sessionId, newRefresh,
                jwtUtil.getRefreshTokenTtlMs(), TimeUnit.MILLISECONDS);

        return PlatformLoginResult.session(
                newAccess, newRefresh,
                sessionId, adminId,
                admin.getRole(), admin.isMfaEnabled(),
                jwtUtil.getAccessTokenTtlMs() / 1000L);
    }

    // =========================================================================
    // helpers
    // =========================================================================

    private void registerFailedAttempt(String lockoutKey, String countKey) {
        Long attempts = redis.opsForValue().increment(countKey);
        long count = attempts == null ? 1L : attempts;
        if (count == 1L) {
            redis.expire(countKey, lockoutDurationSeconds, TimeUnit.SECONDS);
        }
        if (count >= lockoutAttempts) {
            redis.opsForValue().set(lockoutKey, "1",
                    lockoutDurationSeconds, TimeUnit.SECONDS);
            redis.delete(countKey);
        }
    }

    private static String truncate(String s, int max) {
        if (s == null) return null;
        return s.length() <= max ? s : s.substring(0, max);
    }

    /**
     * Best-effort UA parse — produces a short label like "Chrome on macOS"
     * for the /platform/security/sessions list. Real UA parsing belongs
     * elsewhere; keeping it inline avoids pulling in a 1MB library.
     */
    static String parseDeviceLabel(String ua) {
        if (ua == null || ua.isBlank()) return null;
        String browser = ua.contains("Edg/")     ? "Edge"
                       : ua.contains("Chrome/")  ? "Chrome"
                       : ua.contains("Firefox/") ? "Firefox"
                       : ua.contains("Safari/")  && !ua.contains("Chrome/") ? "Safari"
                       : "Trình duyệt";
        String os = ua.contains("Windows")     ? "Windows"
                  : ua.contains("Mac OS X")    ? "macOS"
                  : ua.contains("Android")     ? "Android"
                  : ua.contains("iPhone")
                    || ua.contains("iPad")
                    || ua.contains("iOS")      ? "iOS"
                  : ua.contains("Linux")       ? "Linux"
                  : "thiết bị khác";
        return browser + " trên " + os;
    }

    /** SHA-256 hex of a UTF-8 string — used to bind the challenge JWT to its DB row. */
    static String sha256Hex(String s) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(s.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (Exception e) {
            throw new IllegalStateException("SHA-256 unavailable on this JVM", e);
        }
    }

    // =========================================================================
    // result + exceptions
    // =========================================================================

    /**
     * Two-shape return type:
     *
     * <ul>
     *   <li>{@code session(...)} — full login. {@code accessToken} and
     *       {@code refreshToken} are non-null, {@code sessionId} is set,
     *       {@code mfaRequired=false}, {@code mfaChallengeToken=null}.</li>
     *   <li>{@code mfaRequired(...)} — first leg only. {@code accessToken}/
     *       {@code refreshToken}/{@code sessionId}/{@code role} are null,
     *       {@code mfaRequired=true}, {@code mfaChallengeToken} carries
     *       the JWT the FE will POST back to /auth/platform/mfa/verify.</li>
     * </ul>
     *
     * The controller emits different envelopes for each shape — see
     * {@link com.kaorisystem.auth.controller.PlatformAuthController#toResponse}.
     */
    public record PlatformLoginResult(
            String accessToken,
            String refreshToken,
            UUID   sessionId,
            UUID   adminId,
            String role,
            boolean mfaEnabled,
            long   expiresInSec,
            boolean mfaRequired,
            String mfaChallengeToken,
            long   mfaChallengeExpiresInSec
    ) {
        public static PlatformLoginResult session(String accessToken, String refreshToken,
                                                  UUID sessionId, UUID adminId,
                                                  String role, boolean mfaEnabled,
                                                  long expiresInSec) {
            return new PlatformLoginResult(
                    accessToken, refreshToken, sessionId, adminId,
                    role, mfaEnabled, expiresInSec,
                    false, null, 0L);
        }

        public static PlatformLoginResult mfaRequired(UUID adminId, String challengeToken, long expiresInSec) {
            return new PlatformLoginResult(
                    null, null, null, adminId,
                    null, true, 0L,
                    true, challengeToken, expiresInSec);
        }
    }

    /** Thrown by the verify-MFA path when the challenge is past its expiry. Distinct from invalid-credentials so the FE can prompt "session timed out, please log in again" rather than "wrong code". */
    public static class MfaChallengeExpiredException extends RuntimeException {
        public MfaChallengeExpiredException(String msg) { super(msg); }
    }

    /** B3 PR #8 — refresh token reuse detected via jti SETNX. Surface as 401 with code=AUTH.TOKEN_REPLAYED so the FE can warn the user that their session was used elsewhere. */
    public static class TokenReplayException extends RuntimeException {
        public TokenReplayException(String msg) { super(msg); }
    }
}
