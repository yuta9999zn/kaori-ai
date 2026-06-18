package com.kaorisystem.auth.service;

import com.kaorisystem.auth.model.PasswordResetToken;
import com.kaorisystem.auth.model.User;
import com.kaorisystem.auth.repository.PasswordResetTokenRepository;
import com.kaorisystem.auth.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Instant;
import java.util.Base64;
import java.util.HexFormat;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/**
 * F-015 — Enterprise User & Role Management (P2 portal, Phase 1 close-out).
 *
 * Reuses the existing {@link User} entity (mapped to {@code enterprise_users})
 * + {@link UserRepository}. The service owns the "min-1-MANAGER" invariant
 * across role changes, deactivations, and deletions — without that guard, a
 * tenant's last MANAGER could lock everyone out of admin operations.
 *
 * Phase 1 simplifications (tracked, not blockers):
 *   * Sprint 7 PR B (2026-04-27) — invite email NOW SHIPS. After we save
 *     the user with a random unusable password, we mint a password-reset
 *     token (same plumbing as F-007 forgot-password) and route it through
 *     {@link NotificationClient} using the {@code invite} template. Send
 *     is best-effort: a transient SMTP outage won't roll back the
 *     user-creation transaction; the MANAGER can resend by toggling the
 *     user inactive→active later.
 *   * No idempotency-key middleware on POST/PATCH/DELETE — auth-service has
 *     no cross-cutting Idempotency service yet (same call as F-016).
 *   * Soft delete writes {@code status='deleted'} instead of adding a
 *     {@code deleted_at} column → no migration needed.
 *
 * K-12 enforced at the controller: every method here takes
 * {@code enterpriseId} as the first parameter, never accepts it from a
 * request body.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class EnterpriseUserService {

    private static final Set<String> ALLOWED_ROLES =
            Set.of("MANAGER", "OPERATOR", "ANALYST", "VIEWER");
    private static final Set<String> ALLOWED_PATCH_STATUSES =
            Set.of("active", "inactive");
    private static final int DEFAULT_PAGE_SIZE = 20;
    private static final int MAX_PAGE_SIZE     = 200;

    private final UserRepository                userRepository;
    private final PasswordEncoder               passwordEncoder;
    private final SecureRandom                  random = new SecureRandom();
    /** Sprint 7 PR B — invite email plumbing (best-effort send). */
    private final PasswordResetTokenRepository  resetTokenRepository;
    private final NotificationClient            notificationClient;
    private final JdbcTemplate                  jdbc;

    @Value("${kaori.frontend-url:http://localhost:3000}")
    private String frontendUrl;

    /** Same TTL as F-007 forgot-password. Invite is just a reset link in disguise. */
    @Value("${kaori.password-reset-token-ttl-seconds:3600}")
    private long resetTokenTtlSeconds;

    // =========================================================================
    // List (page-based — small per-tenant cardinality)
    // =========================================================================
    @Transactional(readOnly = true)
    public UserPage list(UUID enterpriseId, String role, String status,
                          int page, int limit) {
        if (page < 1) page = 1;
        if (limit < 1)            limit = DEFAULT_PAGE_SIZE;
        if (limit > MAX_PAGE_SIZE) limit = MAX_PAGE_SIZE;

        if (role != null && !ALLOWED_ROLES.contains(role)) {
            throw new InvalidRoleException("role must be one of " + ALLOWED_ROLES);
        }

        int offset = (page - 1) * limit;
        List<UserView> items = userRepository
                .findByEnterpriseFiltered(enterpriseId, role, status, limit, offset).stream()
                .map(EnterpriseUserService::toView)
                .toList();
        long total = userRepository.countByEnterpriseFiltered(enterpriseId, role, status);

        return new UserPage(items, total, page, limit);
    }

    // =========================================================================
    // Invite (random unusable password — F-007 reset flow handles activation)
    // =========================================================================
    @Transactional
    public UserView invite(UUID enterpriseId, String email, String fullName, String role) {
        String emailNorm = normalizeEmail(email);
        if (emailNorm == null) throw new InvalidEmailException("Invalid email");
        if (role == null || !ALLOWED_ROLES.contains(role)) {
            throw new InvalidRoleException("role must be one of " + ALLOWED_ROLES);
        }

        // uq_user_email_enterprise rejects duplicates at the DB layer; pre-empt
        // with a 409 so the caller doesn't see a generic 500.
        userRepository.findByEmailIgnoreCase(emailNorm).ifPresent(existing -> {
            if (enterpriseId.equals(existing.getEnterpriseId())) {
                throw new UserAlreadyExistsException("User already exists: " + emailNorm);
            }
        });

        User u = new User();
        u.setEnterpriseId(enterpriseId);
        u.setEmail(emailNorm);
        u.setFullName(fullName == null ? null : fullName.trim());
        u.setRole(role);
        u.setStatus("active");
        u.setPasswordHash(passwordEncoder.encode(newRandomPassword()));
        // P1-S1 (P2-M20-007) — invited users start with the forced-change
        // flag on so their first login lands on the change-password screen,
        // not the dashboard. Cleared once they pick a real password (via
        // /auth/reset-password using the email token, or
        // /auth/users/me/change-password while logged in).
        u.setMustChangePassword(true);
        User saved = userRepository.save(u);

        // Sprint 7 PR B — mint a password-reset token + send the invite
        // email. Same flow as F-007 forgot-password; the email template
        // wraps the reset URL in invite-flavoured copy ("X invited you to
        // join Y"). Send is best-effort so SMTP failures don't roll back
        // the user-creation transaction.
        String rawToken = UUID.randomUUID().toString();
        PasswordResetToken token = new PasswordResetToken();
        token.setUserId(saved.getUserId());
        token.setTokenHash(sha256(rawToken));
        token.setExpiresAt(Instant.now().plusSeconds(resetTokenTtlSeconds));
        resetTokenRepository.save(token);

        String inviteUrl     = frontendUrl + "/reset-password?token=" + rawToken;
        String enterpriseName = lookupEnterpriseName(enterpriseId);
        notificationClient.sendInvite(emailNorm, "Quản trị viên", enterpriseName,
                                      inviteUrl, role);

        log.info("enterprise.user.invited enterprise_id={} user_id={} role={}",
                enterpriseId, saved.getUserId(), role);
        return toView(saved);
    }

    /** Best-effort: returns "" so the email template doesn't render an empty bold tag. */
    private String lookupEnterpriseName(UUID enterpriseId) {
        try {
            return jdbc.queryForObject(
                    "SELECT name FROM enterprises WHERE enterprise_id = ?",
                    String.class, enterpriseId);
        } catch (Exception e) {
            log.debug("enterprise.name.lookup.failed enterprise_id={} err={}",
                    enterpriseId, e.getMessage());
            return "";
        }
    }

    private static String sha256(String input) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(input.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(hash);
        } catch (Exception e) {
            throw new RuntimeException("SHA-256 failed", e);
        }
    }

    // =========================================================================
    // Update role / status (with min-MANAGER guard)
    // =========================================================================
    @Transactional
    public UserView update(UUID enterpriseId, UUID userId,
                            String newRole, String newStatus) {
        if (newRole == null && newStatus == null) {
            throw new EmptyUpdateException("At least one of role / status must be provided");
        }
        User u = userRepository.findByUserIdAndEnterpriseId(userId, enterpriseId)
                .orElseThrow(() -> new UserNotFoundException("User not found: " + userId));
        if ("deleted".equals(u.getStatus())) {
            throw new UserNotFoundException("User not found: " + userId);
        }

        if (newRole != null) {
            if (!ALLOWED_ROLES.contains(newRole)) {
                throw new InvalidRoleException("role must be one of " + ALLOWED_ROLES);
            }
            // Demoting the last active MANAGER would lock out admin ops.
            if ("MANAGER".equals(u.getRole()) && !"MANAGER".equals(newRole)
                    && "active".equals(u.getStatus())) {
                ensureNotLastManager(enterpriseId, userId);
            }
            u.setRole(newRole);
        }

        if (newStatus != null) {
            if (!ALLOWED_PATCH_STATUSES.contains(newStatus)) {
                throw new InvalidStatusException(
                        "status must be one of " + ALLOWED_PATCH_STATUSES);
            }
            // Deactivating the last active MANAGER → same guard.
            if ("MANAGER".equals(u.getRole()) && "active".equals(u.getStatus())
                    && !"active".equals(newStatus)) {
                ensureNotLastManager(enterpriseId, userId);
            }
            u.setStatus(newStatus);
        }

        User saved = userRepository.save(u);
        log.info("enterprise.user.updated enterprise_id={} user_id={} role={} status={}",
                enterpriseId, userId, saved.getRole(), saved.getStatus());
        return toView(saved);
    }

    // =========================================================================
    // Soft delete
    // =========================================================================
    @Transactional
    public void softDelete(UUID enterpriseId, UUID userId) {
        User u = userRepository.findByUserIdAndEnterpriseId(userId, enterpriseId)
                .orElseThrow(() -> new UserNotFoundException("User not found: " + userId));
        if ("deleted".equals(u.getStatus())) {
            return;  // already deleted — idempotent
        }

        if ("MANAGER".equals(u.getRole()) && "active".equals(u.getStatus())) {
            ensureNotLastManager(enterpriseId, userId);
        }

        u.setStatus("deleted");
        userRepository.save(u);
        log.info("enterprise.user.deleted enterprise_id={} user_id={}", enterpriseId, userId);
    }

    // =========================================================================
    // Helpers
    // =========================================================================

    private void ensureNotLastManager(UUID enterpriseId, UUID excludeUserId) {
        long others = userRepository.countActiveManagersExcluding(enterpriseId, excludeUserId);
        if (others == 0) {
            throw new LastManagerException(
                    "Operation would leave the enterprise with zero active MANAGERs");
        }
    }

    private static String normalizeEmail(String email) {
        if (email == null) return null;
        String norm = email.trim().toLowerCase();
        if (norm.isEmpty() || !norm.contains("@") || norm.length() > 254) return null;
        return norm;
    }

    private String newRandomPassword() {
        byte[] buf = new byte[24];
        random.nextBytes(buf);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(buf);
    }

    private static UserView toView(User u) {
        return new UserView(
                u.getUserId(),
                u.getEmail(),
                u.getFullName(),
                u.getRole(),
                u.getStatus(),
                u.getLastLoginAt() == null ? null : u.getLastLoginAt().toString(),
                u.getCreatedAt() == null   ? null : u.getCreatedAt().toString()
        );
    }

    // =========================================================================
    // DTOs + exceptions
    // =========================================================================

    public record UserView(
            UUID   userId,
            String email,
            String fullName,
            String role,
            String status,
            String lastLoginAt,
            String createdAt
    ) {}

    public record UserPage(
            List<UserView> items,
            long total,
            int  page,
            int  limit
    ) {}

    public static class UserNotFoundException      extends RuntimeException { public UserNotFoundException(String m){super(m);} }
    public static class UserAlreadyExistsException extends RuntimeException { public UserAlreadyExistsException(String m){super(m);} }
    public static class InvalidRoleException       extends RuntimeException { public InvalidRoleException(String m){super(m);} }
    public static class InvalidEmailException      extends RuntimeException { public InvalidEmailException(String m){super(m);} }
    public static class InvalidStatusException     extends RuntimeException { public InvalidStatusException(String m){super(m);} }
    public static class EmptyUpdateException       extends RuntimeException { public EmptyUpdateException(String m){super(m);} }
    public static class LastManagerException       extends RuntimeException { public LastManagerException(String m){super(m);} }
}
