package com.kaorisystem.auth.service;

import com.kaorisystem.auth.model.AdminSession;
import com.kaorisystem.auth.model.PlatformAdmin;
import com.kaorisystem.auth.repository.AdminSessionRepository;
import com.kaorisystem.auth.repository.PlatformAdminRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

/**
 * Module 3 + 3.1.b — TOTP MFA + active-session management for platform admins.
 *
 * <p>Identity always comes from the calling admin's id (resolved via
 * {@code X-User-ID} by the controller). Session revoke goes through
 * {@link AdminSessionRepository#revokeForAdmin} so a malicious admin
 * cannot kick another admin's session — the WHERE clause IDs both rows.
 *
 * <h3>3.1.b additions</h3>
 * <ul>
 *   <li>Per-admin rate limit on {@code verifyMfa} — 5 failures per 15 min,
 *       Redis-backed. Throws {@link MfaVerifyLockedException} once the
 *       lockout flag is set, controller turns that into 423 + RFC 7807.</li>
 *   <li>Audit emission to {@code platform_admin_audit_log} for every MFA
 *       lifecycle step (initiated / enabled / verified / verify_failed) and
 *       for manual session revoke (other revoke paths emit from their own
 *       writers — see {@code AuthService.logout} and {@code SessionValidator}).</li>
 *   <li>Every audit row includes the client IP from the controller, so the
 *       audit feed is consistent across MFA + session events.</li>
 * </ul>
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class AdminSecurityService {

    private static final String MFA_ATTEMPTS_PREFIX = "mfa_attempts:";
    private static final String MFA_LOCKOUT_PREFIX  = "mfa_lockout:";

    private final PlatformAdminRepository      adminRepo;
    private final AdminSessionRepository       sessionRepo;
    private final TotpService                  totpService;
    private final StringRedisTemplate          redis;
    private final PlatformAdminAuditService    auditService;

    @Value("${kaori.mfa-issuer:Kaori}")
    private String mfaIssuer;

    @Value("${kaori.mfa-verify-lockout-attempts:5}")
    private int mfaLockoutAttempts;

    @Value("${kaori.mfa-verify-lockout-duration-seconds:900}")
    private long mfaLockoutDurationSeconds;

    // =========================================================================
    // MFA
    // =========================================================================

    /**
     * Generate a fresh TOTP secret and stash its encrypted form on the admin
     * row. {@code mfa_enabled} stays false — the admin must complete a verify
     * step to flip it. Re-calling discards the previous unverified secret.
     *
     * <p>Also clears any pre-existing MFA verify lockout for this admin —
     * rotating the secret is a legitimate way to recover from being locked
     * out (the new secret needs a fresh verify).
     */
    @Transactional
    public EnableResult enableMfa(UUID adminId, String ipAddress) {
        PlatformAdmin admin = requireAdmin(adminId);

        byte[] secret = totpService.generateSecret();
        admin.setMfaSecretEnc(totpService.encrypt(secret));
        // Keep mfa_enabled untouched until verify succeeds; if a previously
        // verified MFA is being rotated, the admin must verify the new code
        // before the new secret takes effect — but since we replaced the
        // secret on disk, the old codes stop working immediately. That's
        // intentional: any rotation requires re-verify within the next 30s.
        admin.setMfaEnabled(false);
        adminRepo.save(admin);

        // Clear lockout — a fresh enrolment shouldn't be blocked by stale
        // failed attempts against the previous secret.
        redis.delete(MFA_ATTEMPTS_PREFIX + adminId);
        redis.delete(MFA_LOCKOUT_PREFIX  + adminId);

        String otpauthUrl = totpService.otpauthUrl(mfaIssuer, admin.getEmail(), secret);
        String secretB32  = totpService.base32(secret);
        log.info("platform.mfa.initiated admin_id={}", adminId);

        auditService.recordAudit(adminId, PlatformAdminAuditService.EVT_MFA_INITIATED,
                adminId, admin.getEmail(), admin.getRole(),
                "mfa", "issuer=" + mfaIssuer, ipAddress);

        return new EnableResult(secretB32, otpauthUrl, mfaIssuer, admin.getEmail());
    }

    /**
     * Verify a 6-digit code against the stored secret and flip {@code mfa_enabled}.
     *
     * <p>Rate limited per admin: after {@code mfaLockoutAttempts} failed
     * attempts in {@code mfaLockoutDurationSeconds}, all verify calls return
     * {@link MfaVerifyLockedException} until the window expires. Successful
     * verifies clear both the counter and any active lockout.
     */
    @Transactional
    public VerifyResult verifyMfa(UUID adminId, String code, String ipAddress) {
        // Pre-check lockout BEFORE the admin lookup — a flooded attacker
        // shouldn't get to drag the DB into the request path either.
        String lockoutKey  = MFA_LOCKOUT_PREFIX  + adminId;
        String attemptsKey = MFA_ATTEMPTS_PREFIX + adminId;

        String locked = redis.opsForValue().get(lockoutKey);
        if (locked != null) {
            Long ttl = redis.getExpire(lockoutKey, TimeUnit.SECONDS);
            long remaining = ttl == null ? mfaLockoutDurationSeconds : ttl;
            // Audit the rate-limited attempt — it's load-bearing for any
            // brute-force forensics later.
            PlatformAdmin admin = adminRepo.findById(adminId).orElse(null);
            auditService.recordAudit(adminId, PlatformAdminAuditService.EVT_MFA_VERIFY_FAILED,
                    adminId,
                    admin == null ? null : admin.getEmail(),
                    admin == null ? null : admin.getRole(),
                    "mfa",
                    "rate_limited=true reason=lockout_active remaining_seconds=" + remaining,
                    ipAddress);
            throw new MfaVerifyLockedException(
                    "Too many invalid MFA codes. Try again in " + remaining + " seconds.",
                    remaining);
        }

        PlatformAdmin admin = requireAdmin(adminId);
        if (admin.getMfaSecretEnc() == null || admin.getMfaSecretEnc().isBlank()) {
            throw new MfaNotInitiatedException("Call /security/mfa/enable first.");
        }

        byte[] secret = totpService.decrypt(admin.getMfaSecretEnc());
        if (!totpService.verify(secret, code)) {
            // Failure — bump counter and possibly trip lockout
            Long attempts = redis.opsForValue().increment(attemptsKey);
            long count = attempts == null ? 1L : attempts;
            if (count == 1L) {
                redis.expire(attemptsKey, mfaLockoutDurationSeconds, TimeUnit.SECONDS);
            }
            boolean justLocked = false;
            long remaining = 0L;
            if (count >= mfaLockoutAttempts) {
                redis.opsForValue().set(lockoutKey, "1",
                        mfaLockoutDurationSeconds, TimeUnit.SECONDS);
                redis.delete(attemptsKey);
                justLocked = true;
                remaining = mfaLockoutDurationSeconds;
            }

            String detail = justLocked
                    ? "rate_limited=true reason=lockout_exceeded attempts=" + count
                          + " remaining_seconds=" + remaining
                    : "rate_limited=false attempts=" + count + "/" + mfaLockoutAttempts;
            auditService.recordAudit(adminId, PlatformAdminAuditService.EVT_MFA_VERIFY_FAILED,
                    adminId, admin.getEmail(), admin.getRole(),
                    "mfa", detail, ipAddress);

            if (justLocked) {
                throw new MfaVerifyLockedException(
                        "Too many invalid MFA codes. Try again in " + remaining + " seconds.",
                        remaining);
            }
            throw new InvalidTotpException("Invalid or expired code.");
        }

        // Success
        boolean wasFreshlyEnabled = !admin.isMfaEnabled();
        admin.setMfaEnabled(true);
        adminRepo.save(admin);
        redis.delete(attemptsKey);
        redis.delete(lockoutKey);
        log.info("platform.mfa.verified admin_id={}", adminId);

        // Two events: first verify after enable → admin.mfa.enabled (the
        // "MFA is now active" milestone). Subsequent verifies → admin.mfa.verified
        // (the "user re-confirmed identity" event, useful for high-value steps
        // we may add later). Either way, one audit row.
        String successType = wasFreshlyEnabled
                ? PlatformAdminAuditService.EVT_MFA_ENABLED
                : PlatformAdminAuditService.EVT_MFA_VERIFIED;
        auditService.recordAudit(adminId, successType,
                adminId, admin.getEmail(), admin.getRole(),
                "mfa", "rate_limited=false", ipAddress);

        return new VerifyResult(true, Instant.now());
    }

    // =========================================================================
    // Sessions
    // =========================================================================

    @Transactional(readOnly = true)
    public List<AdminSession> listActiveSessions(UUID adminId) {
        requireAdmin(adminId);
        return sessionRepo.findByAdminIdAndRevokedAtIsNullOrderByLastActiveAtDesc(adminId);
    }

    /**
     * 3.3 — bulk-revoke every active session for the calling admin EXCEPT the
     * one passed in {@code keepSessionId} (typically their current session
     * resolved from {@code X-Session-Id}).
     *
     * <p>Single audit row with a count + reason='manual_bulk' rather than
     * per-session rows — the action is a single operator intent, the audit
     * feed should reflect that. Reason still distinguishes from per-row
     * 'manual' revoke.
     */
    @Transactional
    public RevokeOthersResult revokeOtherSessions(UUID adminId, UUID keepSessionId, String ipAddress) {
        PlatformAdmin admin = requireAdmin(adminId);
        // null keep → caller doesn't have a known current session; treat as
        // "revoke everything for this admin". Use a random UUID as the WHERE
        // sentinel so the SQL keeps the same shape (no NULL handling branch).
        UUID keep = (keepSessionId == null) ? new UUID(0L, 0L) : keepSessionId;
        Instant now = Instant.now();
        int revoked = sessionRepo.revokeAllExcept(adminId, keep, now, "manual_bulk");

        log.info("platform.session.revoked_bulk admin_id={} kept={} count={}", adminId, keep, revoked);

        // One audit row summarising the bulk action — the per-session rows are
        // findable via revoke_reason='manual_bulk' + revoked_at=now if needed.
        if (revoked > 0) {
            auditService.recordAudit(adminId, PlatformAdminAuditService.EVT_SESSION_REVOKED,
                    adminId, admin.getEmail(), admin.getRole(),
                    "all-others",
                    "reason=manual_bulk count=" + revoked + " kept_session_id=" + keep,
                    ipAddress);
        }

        return new RevokeOthersResult(revoked, now);
    }

    /**
     * Soft-revoke. Cross-admin attempts return {@link SessionNotFoundException}
     * (404) — the WHERE clause matches both session_id AND admin_id.
     */
    @Transactional
    public RevokeResult revokeSession(UUID adminId, UUID sessionId, String ipAddress) {
        PlatformAdmin admin = requireAdmin(adminId);
        Instant now = Instant.now();
        // 'manual' reason — UI-driven revoke from /platform/security/sessions.
        // Distinct from the automated reasons emitted by SessionValidator
        // (idle_timeout / absolute_timeout) and AuthService.logout ('logout').
        int updated = sessionRepo.revokeForAdmin(sessionId, adminId, now, "manual");
        if (updated == 0) {
            throw new SessionNotFoundException(
                    "Session not found or already revoked: " + sessionId);
        }
        log.info("platform.session.revoked admin_id={} session_id={}", adminId, sessionId);

        auditService.recordAudit(adminId, PlatformAdminAuditService.EVT_SESSION_REVOKED,
                adminId, admin.getEmail(), admin.getRole(),
                sessionId.toString(), "reason=manual", ipAddress);

        return new RevokeResult(sessionId, now);
    }

    // =========================================================================
    // Helpers
    // =========================================================================

    private PlatformAdmin requireAdmin(UUID adminId) {
        return adminRepo.findById(adminId)
                .orElseThrow(() -> new AdminNotFoundException("Admin not found: " + adminId));
    }

    // =========================================================================
    // Return + exception types
    // =========================================================================

    public record EnableResult(String secret, String otpauthUrl, String issuer, String account) {}
    public record VerifyResult(boolean mfaEnabled, Instant verifiedAt) {}
    public record RevokeResult(UUID sessionId, Instant revokedAt) {}
    /** 3.3 — return for {@link #revokeOtherSessions}. */
    public record RevokeOthersResult(int revokedCount, Instant revokedAt) {}

    public static class AdminNotFoundException     extends RuntimeException { public AdminNotFoundException(String m)     { super(m); } }
    public static class MfaNotInitiatedException   extends RuntimeException { public MfaNotInitiatedException(String m)   { super(m); } }
    public static class InvalidTotpException       extends RuntimeException { public InvalidTotpException(String m)       { super(m); } }
    public static class SessionNotFoundException   extends RuntimeException { public SessionNotFoundException(String m)   { super(m); } }

    /** 3.1.b — thrown when MFA verify rate limit fires. Controller maps to 423. */
    public static class MfaVerifyLockedException extends RuntimeException {
        private final long remainingSeconds;
        public MfaVerifyLockedException(String msg, long remainingSeconds) {
            super(msg);
            this.remainingSeconds = remainingSeconds;
        }
        public long getRemainingSeconds() { return remainingSeconds; }
    }
}
