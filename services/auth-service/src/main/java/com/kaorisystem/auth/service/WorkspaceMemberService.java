package com.kaorisystem.auth.service;

import com.kaorisystem.auth.model.PasswordResetToken;
import com.kaorisystem.auth.model.User;
import com.kaorisystem.auth.model.Workspace;
import com.kaorisystem.auth.repository.PasswordResetTokenRepository;
import com.kaorisystem.auth.repository.UserRepository;
import com.kaorisystem.auth.repository.WorkspaceRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.MimeMessageHelper;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Instant;
import java.util.HexFormat;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/**
 * F-008 expansion — workspace members CRUD.
 *
 * Members are rows in {@code enterprise_users}, scoped to the workspace via
 * the workspace → enterprises → users join. Workspace-level operations on
 * members live here (rather than on {@link WorkspaceService}) because they
 * pull in the heavier auth dependencies — password encoder, mail sender,
 * password-reset tokens for invite activation.
 *
 * Invite flow:
 *   1. Validate workspace + email + role.
 *   2. Resolve workspace_id → enterprise_id via WorkspaceRepository.
 *   3. Create the User row with a random unusable password_hash and
 *      status='pending' so the user cannot log in until they set a password.
 *   4. Generate a SHA-256 hashed reset token (1h TTL) and email it.
 *   5. Audit the event.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class WorkspaceMemberService {

    private static final Set<String> ALLOWED_ROLES = Set.of(
            "MANAGER", "OPERATOR", "ANALYST", "VIEWER");

    private final WorkspaceRepository           workspaceRepository;
    private final UserRepository                userRepository;
    private final PasswordResetTokenRepository  resetTokenRepository;
    private final PasswordEncoder               passwordEncoder;
    private final JavaMailSender                mailSender;
    private final WorkspaceService              workspaceService;   // for audit + get

    @Value("${kaori.password-reset-token-ttl-seconds:3600}")
    private long resetTokenTtlSeconds;

    @Value("${kaori.frontend-url:http://localhost:3000}")
    private String frontendUrl;

    // =========================================================================
    // List members
    // =========================================================================
    @Transactional(readOnly = true)
    public List<MemberView> list(UUID workspaceId) {
        ensureWorkspaceExists(workspaceId);
        return userRepository.findByWorkspaceIdOrderByCreatedAtDesc(workspaceId).stream()
                .map(WorkspaceMemberService::toView)
                .toList();
    }

    // =========================================================================
    // Invite member — creates User + reset token + sends email
    // =========================================================================
    @Transactional
    public MemberView invite(UUID workspaceId, String email, String role,
                              String actorEmail, String actorRole, String ipAddress) {

        Workspace ws = workspaceRepository.findById(workspaceId)
                .orElseThrow(() -> new WorkspaceService.WorkspaceNotFoundException(
                        "Workspace not found: " + workspaceId));

        if (role == null || !ALLOWED_ROLES.contains(role)) {
            throw new InvalidRoleException("role must be one of " + ALLOWED_ROLES);
        }
        String emailNorm = normalizeEmail(email);
        if (emailNorm == null) {
            throw new InvalidEmailException("Invalid email");
        }

        UUID enterpriseId = workspaceRepository.findEnterpriseIdByWorkspaceId(workspaceId)
                .orElseThrow(() -> new WorkspaceService.EnterpriseNotProvisionedException(
                        "Workspace has no provisioned enterprise yet: " + workspaceId));

        // Reject duplicate emails inside the same enterprise (DB constraint
        // uq_user_email_enterprise would also reject — pre-empt with a 409).
        boolean exists = userRepository.findByEmailIgnoreCase(emailNorm)
                .filter(u -> enterpriseId.equals(u.getEnterpriseId()))
                .isPresent();
        if (exists) {
            throw new MemberAlreadyExistsException(
                    "Member already exists in this workspace: " + emailNorm);
        }

        // Random unusable password — user must complete reset to log in.
        String randomPassword = newRandomPassword();
        User u = new User();
        u.setEnterpriseId(enterpriseId);
        u.setEmail(emailNorm);
        u.setPasswordHash(passwordEncoder.encode(randomPassword));
        u.setRole(role);
        u.setStatus("pending");
        u.setFullName(emailNorm.contains("@") ? emailNorm.substring(0, emailNorm.indexOf('@')) : emailNorm);
        User saved = userRepository.save(u);

        // Issue reset token (re-uses enterprise_users-tied table).
        String rawToken = UUID.randomUUID().toString();
        PasswordResetToken token = new PasswordResetToken();
        token.setUserId(saved.getUserId());
        token.setTokenHash(sha256(rawToken));
        token.setExpiresAt(Instant.now().plusSeconds(resetTokenTtlSeconds));
        resetTokenRepository.save(token);

        sendInviteEmail(emailNorm, ws.getName(), rawToken);

        workspaceService.recordAudit(
                workspaceId, "member.invited",
                actorEmail, actorRole,
                emailNorm, "role=" + role, ipAddress);

        return toView(saved);
    }

    // =========================================================================
    // Update role
    // =========================================================================
    @Transactional
    public MemberView updateRole(UUID workspaceId, UUID userId, String role,
                                  String actorEmail, String actorRole, String ipAddress) {

        if (role == null || !ALLOWED_ROLES.contains(role)) {
            throw new InvalidRoleException("role must be one of " + ALLOWED_ROLES);
        }

        UUID enterpriseId = workspaceRepository.findEnterpriseIdByWorkspaceId(workspaceId)
                .orElseThrow(() -> new WorkspaceService.EnterpriseNotProvisionedException(
                        "Workspace has no provisioned enterprise yet: " + workspaceId));

        User u = userRepository.findByUserIdAndEnterpriseId(userId, enterpriseId)
                .orElseThrow(() -> new MemberNotFoundException(
                        "Member " + userId + " not in workspace " + workspaceId));

        // Guard: at least one MANAGER must remain (per F-015 invariant — a
        // workspace cannot exist with zero managers, otherwise it's unmanageable).
        if ("MANAGER".equals(u.getRole()) && !"MANAGER".equals(role)) {
            long activeManagers = userRepository.countByEnterpriseIdAndRoleAndStatus(
                    enterpriseId, "MANAGER", "active");
            // current row counts even if its status != active, so be conservative
            if (activeManagers <= 1) {
                throw new LastManagerException(
                        "Cannot demote the last MANAGER in this workspace.");
            }
        }

        String oldRole = u.getRole();
        u.setRole(role);
        User saved = userRepository.save(u);

        workspaceService.recordAudit(
                workspaceId, "member.role_changed",
                actorEmail, actorRole,
                u.getEmail(), oldRole + " → " + role, ipAddress);

        return toView(saved);
    }

    // =========================================================================
    // Remove member (hard delete — schema lacks a soft-delete flag for users)
    // =========================================================================
    @Transactional
    public void remove(UUID workspaceId, UUID userId,
                       String actorEmail, String actorRole, String ipAddress) {

        UUID enterpriseId = workspaceRepository.findEnterpriseIdByWorkspaceId(workspaceId)
                .orElseThrow(() -> new WorkspaceService.EnterpriseNotProvisionedException(
                        "Workspace has no provisioned enterprise yet: " + workspaceId));

        User u = userRepository.findByUserIdAndEnterpriseId(userId, enterpriseId)
                .orElseThrow(() -> new MemberNotFoundException(
                        "Member " + userId + " not in workspace " + workspaceId));

        if ("MANAGER".equals(u.getRole())) {
            long activeManagers = userRepository.countByEnterpriseIdAndRoleAndStatus(
                    enterpriseId, "MANAGER", "active");
            if (activeManagers <= 1) {
                throw new LastManagerException(
                        "Cannot remove the last MANAGER in this workspace.");
            }
        }

        // Tokens FK to enterprise_users — must clear them before deleting the user.
        // Pending invites or reset requests for a removed user are no longer valid.
        resetTokenRepository.deleteByUserId(u.getUserId());
        userRepository.delete(u);

        workspaceService.recordAudit(
                workspaceId, "member.removed",
                actorEmail, actorRole,
                u.getEmail(), "role=" + u.getRole(), ipAddress);
    }

    // =========================================================================
    // Mappers + helpers
    // =========================================================================

    private static MemberView toView(User u) {
        return new MemberView(
                u.getUserId(),
                u.getEmail(),
                u.getFullName(),
                u.getRole(),
                u.getStatus(),
                u.getLastLoginAt(),
                u.getCreatedAt()
        );
    }

    private void ensureWorkspaceExists(UUID workspaceId) {
        if (!workspaceRepository.existsById(workspaceId)) {
            throw new WorkspaceService.WorkspaceNotFoundException(
                    "Workspace not found: " + workspaceId);
        }
    }

    private static String normalizeEmail(String email) {
        if (email == null) return null;
        String trimmed = email.trim().toLowerCase();
        if (trimmed.isEmpty() || !trimmed.contains("@")) return null;
        return trimmed;
    }

    private static String newRandomPassword() {
        byte[] bytes = new byte[24];
        new SecureRandom().nextBytes(bytes);
        return java.util.Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
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

    private void sendInviteEmail(String email, String workspaceName, String rawToken) {
        try {
            String resetUrl = frontendUrl + "/reset-password?token=" + rawToken;
            String html = """
                <!DOCTYPE html>
                <html lang="vi">
                <head><meta charset="UTF-8"></head>
                <body style="margin:0;padding:0;background:#f5f5f5;font-family:sans-serif">
                  <table width="100%%" cellpadding="0" cellspacing="0">
                    <tr><td align="center" style="padding:40px 0">
                      <table width="560" cellpadding="0" cellspacing="0"
                             style="background:#fff;border-radius:12px;overflow:hidden;
                                    box-shadow:0 2px 8px rgba(0,0,0,.08)">
                        <tr><td style="background:#1d4ed8;padding:28px 40px">
                          <h1 style="margin:0;color:#fff;font-size:20px;font-weight:700">Kaori System</h1>
                        </td></tr>
                        <tr><td style="padding:36px 40px">
                          <p style="margin:0 0 16px;color:#374151;font-size:16px">
                            Bạn đã được mời tham gia workspace <strong>%s</strong>.
                          </p>
                          <p style="margin:0 0 24px;color:#6b7280;font-size:14px;line-height:1.6">
                            Nhấn nút bên dưới để đặt mật khẩu và bắt đầu sử dụng. Liên kết có hiệu lực trong <strong>1 giờ</strong>.
                          </p>
                          <table cellpadding="0" cellspacing="0"><tr>
                            <td style="border-radius:8px;background:#1d4ed8">
                              <a href="%s" style="display:inline-block;padding:14px 28px;color:#fff;font-size:15px;font-weight:600;text-decoration:none">
                                Tham gia workspace →
                              </a>
                            </td>
                          </tr></table>
                          <p style="margin:24px 0 0;color:#9ca3af;font-size:12px">
                            Nếu bạn không chờ đợi lời mời này, hãy bỏ qua email.<br><br>
                            Link không hoạt động? Sao chép URL sau:<br>
                            <span style="color:#1d4ed8;word-break:break-all">%s</span>
                          </p>
                        </td></tr>
                        <tr><td style="background:#f9fafb;padding:20px 40px;border-top:1px solid #e5e7eb">
                          <p style="margin:0;color:#9ca3af;font-size:12px">© 2026 Kaori System</p>
                        </td></tr>
                      </table>
                    </td></tr>
                  </table>
                </body></html>
                """.formatted(workspaceName, resetUrl, resetUrl);

            jakarta.mail.internet.MimeMessage msg = mailSender.createMimeMessage();
            MimeMessageHelper helper = new MimeMessageHelper(msg, false, "UTF-8");
            helper.setTo(email);
            helper.setSubject("Kaori — Bạn được mời tham gia " + workspaceName);
            helper.setText(html, true);
            mailSender.send(msg);
        } catch (Exception e) {
            // Mirror AuthService.sendResetEmail: log and continue. The user was
            // saved + token issued, so an admin can resend by inviting again.
            log.error("Failed to send invite email to {}: {}", email, e.getMessage());
        }
    }

    // =========================================================================
    // Return + exception types
    // =========================================================================

    public record MemberView(
            UUID    userId,
            String  email,
            String  fullName,
            String  role,
            String  status,
            Instant lastLoginAt,
            Instant createdAt
    ) {}

    public static class MemberNotFoundException extends RuntimeException {
        public MemberNotFoundException(String msg) { super(msg); }
    }
    public static class MemberAlreadyExistsException extends RuntimeException {
        public MemberAlreadyExistsException(String msg) { super(msg); }
    }
    public static class InvalidRoleException extends RuntimeException {
        public InvalidRoleException(String msg) { super(msg); }
    }
    public static class InvalidEmailException extends RuntimeException {
        public InvalidEmailException(String msg) { super(msg); }
    }
    public static class LastManagerException extends RuntimeException {
        public LastManagerException(String msg) { super(msg); }
    }
}
