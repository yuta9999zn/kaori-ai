package com.kaorisystem.auth.service;

import com.kaorisystem.auth.dto.AuthDtos.*;
import com.kaorisystem.auth.model.PasswordResetToken;
import com.kaorisystem.auth.model.User;
import com.kaorisystem.auth.repository.PasswordResetTokenRepository;
import com.kaorisystem.auth.repository.UserRepository;
import com.kaorisystem.auth.security.JwtUtil;
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

@Service
@RequiredArgsConstructor
@Slf4j
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordResetTokenRepository resetTokenRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtUtil jwtUtil;
    private final StringRedisTemplate redis;
    private final NotificationClient notificationClient;
    private final PlatformKeyService platformKeyService;
    private final RlsBypassHelper rlsBypass;
    /** Optional — only called when a platform token is being logged out. */
    private final org.springframework.beans.factory.ObjectProvider<com.kaorisystem.auth.repository.AdminSessionRepository> adminSessionRepoProvider;
    private final org.springframework.beans.factory.ObjectProvider<SessionValidator> sessionValidatorProvider;
    /** 3.1.b — best-effort audit emitter for platform session revoke. Optional. */
    private final org.springframework.beans.factory.ObjectProvider<PlatformAdminAuditService> auditServiceProvider;
    /** 3.1.b — fetch admin email/role for the audit row when present. Optional. */
    private final org.springframework.beans.factory.ObjectProvider<com.kaorisystem.auth.repository.PlatformAdminRepository> adminRepoProvider;

    @Value("${kaori.login-lockout-attempts:5}")
    private int lockoutAttempts;

    @Value("${kaori.login-lockout-duration-seconds:900}")
    private long lockoutDurationSeconds;

    @Value("${kaori.password-reset-token-ttl-seconds:3600}")
    private long resetTokenTtlSeconds;

    @Value("${kaori.frontend-url:http://localhost:3000}")
    private String frontendUrl;

    // ---- Login ----

    /**
     * Login flow needs an active transaction because {@link UserRepository#updateLastLogin}
     * is a {@code @Modifying} JPA query — Spring requires an open tx for it to commit.
     * MSW dev mode never hit this path so the missing annotation went unnoticed; first
     * real BE login (pilot UAT seed PR, 2026-05-04) surfaced
     * {@code TransactionRequiredException}.
     */
    @Transactional
    public LoginResponse login(LoginRequest req) {
        String lockoutKey = "lockout:" + req.getEmail().toLowerCase();
        String countKey = "login_attempts:" + req.getEmail().toLowerCase();

        // Check lockout
        String locked = redis.opsForValue().get(lockoutKey);
        if (locked != null) {
            Long ttl = redis.getExpire(lockoutKey, TimeUnit.SECONDS);
            throw new LockoutException("Account locked. Try again in " + ttl + " seconds.", ttl);
        }

        Optional<User> userOpt = userRepository.findByEmailIgnoreCase(req.getEmail());

        if (userOpt.isEmpty() || !passwordEncoder.matches(req.getPassword(), userOpt.get().getPasswordHash())) {
            // Atomically increment and use the returned post-increment value
            // (a separate GET would race with concurrent failed attempts).
            // INCR on a missing key creates it with value 1, so a result of 1
            // marks the FIRST failure of a fresh window.
            Long attempts = redis.opsForValue().increment(countKey);
            long count = attempts != null ? attempts : 1L;

            // Set the window TTL exactly once — when the counter is first
            // created. Refreshing it on every failure (the previous behaviour)
            // turned the fixed 15-min lockout window into a sliding one that
            // could keep the counter alive indefinitely as long as the
            // attacker kept probing within the TTL.
            if (count == 1L) {
                redis.expire(countKey, lockoutDurationSeconds, TimeUnit.SECONDS);
            }

            if (count >= lockoutAttempts) {
                redis.opsForValue().set(lockoutKey, "1", lockoutDurationSeconds, TimeUnit.SECONDS);
                redis.delete(countKey);
            }

            throw new InvalidCredentialsException("Invalid email or password.");
        }

        User user = userOpt.get();
        if (!"active".equals(user.getStatus())) {
            throw new InvalidCredentialsException("Account is inactive.");
        }

        // Clear lockout counters on success
        redis.delete(lockoutKey);
        redis.delete(countKey);
        userRepository.updateLastLogin(user.getUserId(), Instant.now());

        String accessToken = jwtUtil.generateAccessToken(user.getUserId(), user.getEnterpriseId(), user.getRole());
        String refreshToken = jwtUtil.generateRefreshToken(user.getUserId(), user.getEnterpriseId());

        // Store refresh token in Redis
        String refreshKey = "refresh:" + user.getUserId();
        redis.opsForValue().set(refreshKey, refreshToken,
                jwtUtil.getRefreshTokenTtlMs(), TimeUnit.MILLISECONDS);

        LoginResponse resp = new LoginResponse();
        resp.setAccessToken(accessToken);
        resp.setRefreshToken(refreshToken);
        resp.setRole(user.getRole());
        resp.setEnterpriseId(user.getEnterpriseId().toString());
        resp.setUserId(user.getUserId().toString());
        // P1-S1 (P2-M20-007) — surface the must_change_password flag so the
        // FE can route to a forced-change screen on first login. We always
        // emit a non-null value (defaulting to false) so callers don't have
        // to special-case JSON null vs missing field.
        Boolean mustChange = user.getMustChangePassword();
        resp.setMustChangePassword(Boolean.TRUE.equals(mustChange));
        return resp;
    }

    // ---- Logout ----

    public void logout(String accessToken) {
        logout(accessToken, null);
    }

    public void logout(String accessToken, String ipAddress) {
        if (jwtUtil.isValid(accessToken)) {
            Claims claims = jwtUtil.validateAndParse(accessToken);
            // Blacklist access token until its expiry
            long ttl = claims.getExpiration().toInstant().toEpochMilli() - System.currentTimeMillis();
            if (ttl > 0) {
                redis.opsForValue().set("blacklist:" + accessToken, "1", ttl, TimeUnit.MILLISECONDS);
            }

            // Branch on token_kind: platform tokens revoke the admin_sessions
            // row + drop the per-session refresh; enterprise tokens keep the
            // legacy "refresh:{userId}" key (pre-3.1.a behaviour, unchanged).
            if ("platform".equals(claims.get("token_kind"))) {
                Object sid = claims.get("session_id");
                if (sid != null) {
                    UUID sessionId = UUID.fromString(sid.toString());
                    UUID adminId   = UUID.fromString(claims.getSubject());
                    var repo = adminSessionRepoProvider.getIfAvailable();
                    if (repo != null) {
                        repo.revokeBySessionId(sessionId, Instant.now(), "logout");
                    }
                    var validator = sessionValidatorProvider.getIfAvailable();
                    if (validator != null) validator.invalidateCache(sessionId);
                    redis.delete("platform_refresh:" + sessionId);

                    // 3.1.b — best-effort audit row. AuditService swallows
                    // exceptions internally so a logging failure can't break
                    // logout.
                    var audit = auditServiceProvider.getIfAvailable();
                    if (audit != null) {
                        var adminRepo = adminRepoProvider.getIfAvailable();
                        String email = null, role = null;
                        if (adminRepo != null) {
                            var found = adminRepo.findById(adminId);
                            if (found.isPresent()) {
                                email = found.get().getEmail();
                                role  = found.get().getRole();
                            }
                        }
                        audit.recordAudit(adminId,
                                PlatformAdminAuditService.EVT_SESSION_REVOKED,
                                adminId, email, role,
                                sessionId.toString(), "reason=logout", ipAddress);
                    }
                }
            } else {
                // Enterprise users — legacy single-key refresh storage
                redis.delete("refresh:" + claims.getSubject());
            }
        }
    }

    // ---- Refresh token ----

    public LoginResponse refresh(RefreshRequest req) {
        if (!jwtUtil.isValid(req.getRefreshToken())) {
            throw new InvalidCredentialsException("Invalid or expired refresh token.");
        }
        Claims claims = jwtUtil.validateAndParse(req.getRefreshToken());
        if (!"refresh".equals(claims.get("type"))) {
            throw new InvalidCredentialsException("Not a refresh token.");
        }

        UUID userId = UUID.fromString(claims.getSubject());
        String storedToken = redis.opsForValue().get("refresh:" + userId);
        if (!req.getRefreshToken().equals(storedToken)) {
            throw new InvalidCredentialsException("Refresh token has been revoked.");
        }

        // B3 PR #8 — burn the presented refresh's jti via Redis SETNX so a
        // parallel second use of the same refresh token fails. Closes the
        // race where the equality check above passed twice before the
        // rotation update below landed (would otherwise mint two valid
        // session pairs from one refresh).
        String jti = String.valueOf(claims.get("jti"));
        if (jti != null && !"null".equals(jti) && !jti.isBlank()) {
            long ttlMs = Math.max(1L, claims.getExpiration().getTime() - System.currentTimeMillis());
            Boolean firstUse = redis.opsForValue().setIfAbsent(
                    "jwt:jti:used:" + jti, "1", ttlMs, TimeUnit.MILLISECONDS);
            if (Boolean.FALSE.equals(firstUse)) {
                throw new InvalidCredentialsException("Refresh token has already been used.");
            }
        }

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new InvalidCredentialsException("User not found."));

        String newAccess = jwtUtil.generateAccessToken(user.getUserId(), user.getEnterpriseId(), user.getRole());
        String newRefresh = jwtUtil.generateRefreshToken(user.getUserId(), user.getEnterpriseId());

        redis.opsForValue().set("refresh:" + userId, newRefresh,
                jwtUtil.getRefreshTokenTtlMs(), TimeUnit.MILLISECONDS);

        LoginResponse resp = new LoginResponse();
        resp.setAccessToken(newAccess);
        resp.setRefreshToken(newRefresh);
        resp.setRole(user.getRole());
        resp.setEnterpriseId(user.getEnterpriseId().toString());
        resp.setUserId(user.getUserId().toString());
        return resp;
    }

    // ---- Forgot password (anti-enumeration: always returns 200) ----

    @Transactional
    public void forgotPassword(ForgotPasswordRequest req) {
        userRepository.findByEmailIgnoreCase(req.getEmail()).ifPresent(user -> {
            String rawToken = UUID.randomUUID().toString();
            String tokenHash = sha256(rawToken);

            PasswordResetToken token = new PasswordResetToken();
            token.setUserId(user.getUserId());
            token.setTokenHash(tokenHash);
            token.setExpiresAt(Instant.now().plusSeconds(resetTokenTtlSeconds));
            resetTokenRepository.save(token);

            sendResetEmail(user.getEmail(), rawToken, user.getFullName());
        });
        // Always return normally — do not reveal if email exists
    }

    // ---- Reset password ----

    @Transactional
    public void resetPassword(ResetPasswordRequest req) {
        String tokenHash = sha256(req.getToken());
        PasswordResetToken token = resetTokenRepository
                .findByTokenHashAndUsedAtIsNullAndExpiresAtAfter(tokenHash, Instant.now())
                .orElseThrow(() -> new InvalidCredentialsException("Invalid or expired reset token."));

        User user = userRepository.findById(token.getUserId())
                .orElseThrow(() -> new InvalidCredentialsException("User not found."));

        user.setPasswordHash(passwordEncoder.encode(req.getNewPassword()));
        // P1-S1 (P2-M20-007) — close the loop on the invite flow. An invited
        // user reaches /reset-password via the email token; once they pick a
        // new password, the flag flips off so subsequent logins skip the
        // forced-change screen.
        user.setMustChangePassword(false);
        userRepository.save(user);
        resetTokenRepository.markUsed(token.getTokenId(), Instant.now());

        // Invalidate all existing sessions
        redis.delete("refresh:" + user.getUserId());
    }

    // ---- Logged-in change password (P1-S1 / P2-M20-007) ----

    /**
     * Change the password while logged in. Re-verifies the current password
     * before persisting the new hash so a hijacked session can't silently
     * rotate credentials. Clears {@code must_change_password} on success.
     *
     * <p>Distinct from {@link #resetPassword(ResetPasswordRequest)}: that
     * one consumes a one-shot email token and is used by the invite +
     * forgot-password flows; this one trusts an active JWT and re-checks
     * the password the holder already knows.
     *
     * @param userId           caller's user_id from validated JWT
     * @param currentPassword  the password the caller is already using
     * @param newPassword      the replacement
     * @throws InvalidCredentialsException if the current password is wrong
     *                                      or the user is not found
     */
    @Transactional
    public void changeOwnPassword(UUID userId, String currentPassword, String newPassword) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new InvalidCredentialsException("User not found."));

        if (!passwordEncoder.matches(currentPassword, user.getPasswordHash())) {
            throw new InvalidCredentialsException("Current password is incorrect.");
        }

        user.setPasswordHash(passwordEncoder.encode(newPassword));
        user.setMustChangePassword(false);
        userRepository.save(user);

        // Mirror reset-password behaviour: invalidate refresh tokens so any
        // stale session on another device must re-auth with the new password.
        redis.delete("refresh:" + user.getUserId());
    }

    // ---- Workspace activation (first-time setup) ----

    @Transactional
    public LoginResponse activateWorkspace(ActivateKeyRequest req) {
        // Cross-tenant lookup: workspace_keys → enterprises JOIN filters via
        // RLS on `enterprises` (mig 105 admin_bypass policy). The activation
        // caller has no tenant context yet (no JWT), so we authorise the
        // current tx as admin to let the JOIN see the row.
        rlsBypass.disableForTx();

        // Validate key via PlatformKeyService (fixes the workspace_id→enterprise_id join)
        if (!platformKeyService.isActiveKey(req.getWorkspaceKey())) {
            throw new InvalidCredentialsException("Invalid or revoked workspace key.");
        }

        UUID enterpriseId = platformKeyService.findEnterpriseIdByKey(req.getWorkspaceKey());

        User admin = new User();
        admin.setUserId(UUID.randomUUID());
        admin.setEnterpriseId(enterpriseId);
        admin.setEmail(req.getAdminEmail());
        admin.setFullName(req.getAdminName() != null ? req.getAdminName() : "Admin");
        admin.setPasswordHash(passwordEncoder.encode(req.getAdminPassword()));
        admin.setRole("MANAGER");
        admin.setStatus("active");
        userRepository.save(admin);

        // One-time use: revoke the key after successful activation
        platformKeyService.consumeKey(req.getWorkspaceKey());

        String accessToken = jwtUtil.generateAccessToken(admin.getUserId(), admin.getEnterpriseId(), admin.getRole());
        String refreshToken = jwtUtil.generateRefreshToken(admin.getUserId(), admin.getEnterpriseId());
        redis.opsForValue().set("refresh:" + admin.getUserId(), refreshToken,
                jwtUtil.getRefreshTokenTtlMs(), java.util.concurrent.TimeUnit.MILLISECONDS);

        LoginResponse resp = new LoginResponse();
        resp.setAccessToken(accessToken);
        resp.setRefreshToken(refreshToken);
        resp.setRole(admin.getRole());
        resp.setEnterpriseId(admin.getEnterpriseId().toString());
        resp.setUserId(admin.getUserId().toString());
        return resp;
    }

    // ---- Helpers ----

    private void sendResetEmail(String email, String rawToken, String name) {
        // Sprint 7 PR B — delegate to notification-service. Best-effort:
        // never throws — preserves anti-enumeration on /forgot-password.
        String resetUrl = frontendUrl + "/reset-password?token=" + rawToken;
        notificationClient.sendResetPassword(email, name, resetUrl);
    }

    private String sha256(String input) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(input.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(hash);
        } catch (Exception e) {
            throw new RuntimeException("SHA-256 failed", e);
        }
    }

    // ---- Exceptions ----

    public static class InvalidCredentialsException extends RuntimeException {
        public InvalidCredentialsException(String msg) { super(msg); }
    }

    public static class LockoutException extends RuntimeException {
        private final Long remainingSeconds;
        public LockoutException(String msg, Long remainingSeconds) {
            super(msg);
            this.remainingSeconds = remainingSeconds;
        }
        public Long getRemainingSeconds() { return remainingSeconds; }
    }
}
