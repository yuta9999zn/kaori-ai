package com.kaorisystem.auth.service;

import com.kaorisystem.auth.model.PlatformAdmin;
import com.kaorisystem.auth.model.PlatformAdminPasswordReset;
import com.kaorisystem.auth.repository.PlatformAdminPasswordResetRepository;
import com.kaorisystem.auth.repository.PlatformAdminRepository;
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
 * F-010 — Platform admin user management (P1 portal).
 *
 * Owns the lifecycle for {@link PlatformAdmin}: list / get / invite /
 * update (role + active flag) / reset password. Keeps the platform-admin
 * concern fully separate from {@link AuthService} (enterprise users) — the
 * data model is a different table with a different role enum.
 *
 * Invite flow mirrors {@link WorkspaceMemberService#invite}: create the
 * admin row with an unusable random password, generate a SHA-256 hashed
 * reset token in {@code platform_admin_password_resets}, send a localized
 * email with the activation link.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class PlatformAdminService {

    private static final Set<String> ALLOWED_ROLES = Set.of("SUPER_ADMIN", "ADMIN", "SUPPORT");

    private final PlatformAdminRepository              adminRepository;
    private final PlatformAdminPasswordResetRepository resetRepository;
    private final PasswordEncoder                      passwordEncoder;
    private final JavaMailSender                       mailSender;

    @Value("${kaori.password-reset-token-ttl-seconds:3600}")
    private long resetTokenTtlSeconds;

    @Value("${kaori.frontend-url:http://localhost:3000}")
    private String frontendUrl;

    // =========================================================================
    // Read
    // =========================================================================
    @Transactional(readOnly = true)
    public List<AdminView> list() {
        return adminRepository.findAllByOrderByCreatedAtDesc().stream()
                .map(PlatformAdminService::toView)
                .toList();
    }

    @Transactional(readOnly = true)
    public AdminView get(UUID id) {
        return toView(adminRepository.findById(id)
                .orElseThrow(() -> new AdminNotFoundException("Platform admin not found: " + id)));
    }

    // =========================================================================
    // Invite
    // =========================================================================
    @Transactional
    public AdminView invite(String email, String fullName, String role, UUID invitedBy) {
        String emailNorm = normalizeEmail(email);
        if (emailNorm == null)              throw new InvalidEmailException("Invalid email");
        if (fullName == null || fullName.isBlank())
                                            throw new InvalidFullNameException("full_name is required");
        if (!ALLOWED_ROLES.contains(role))  throw new InvalidRoleException("role must be one of " + ALLOWED_ROLES);

        if (adminRepository.existsByEmailIgnoreCase(emailNorm)) {
            throw new AdminAlreadyExistsException("Platform admin already exists: " + emailNorm);
        }

        PlatformAdmin a = new PlatformAdmin();
        a.setEmail(emailNorm);
        a.setFullName(fullName.trim());
        a.setRole(role);
        a.setActive(true);
        // SUPER_ADMIN is documented as MFA-required (CLAUDE.md §9). We default
        // mfaEnabled to false at invite time — UI prompts the user to set it
        // up on first login. A separate F-007 PR will gate login on MFA for
        // SUPER_ADMIN. Tracking the flag here lets the UI surface state.
        a.setMfaEnabled(false);
        a.setPasswordHash(passwordEncoder.encode(newRandomPassword()));
        a.setInvitedBy(invitedBy);
        a.setInvitedAt(Instant.now());
        PlatformAdmin saved = adminRepository.save(a);

        String rawToken = issueResetToken(saved.getAdminId());
        sendInviteEmail(emailNorm, fullName.trim(), rawToken);

        return toView(saved);
    }

    // =========================================================================
    // Update (role / is_active / full_name)
    // =========================================================================
    @Transactional
    public AdminView update(UUID id, String fullName, String role, Boolean isActive) {
        PlatformAdmin a = adminRepository.findById(id)
                .orElseThrow(() -> new AdminNotFoundException("Platform admin not found: " + id));

        if (fullName != null) {
            if (fullName.isBlank()) throw new InvalidFullNameException("full_name cannot be blank");
            a.setFullName(fullName.trim());
        }
        if (role != null) {
            if (!ALLOWED_ROLES.contains(role)) {
                throw new InvalidRoleException("role must be one of " + ALLOWED_ROLES);
            }
            a.setRole(role);
        }
        if (isActive != null) {
            a.setActive(isActive);
        }
        return toView(adminRepository.save(a));
    }

    // =========================================================================
    // Reset password
    // =========================================================================
    @Transactional
    public ResetResult resetPassword(UUID id) {
        PlatformAdmin a = adminRepository.findById(id)
                .orElseThrow(() -> new AdminNotFoundException("Platform admin not found: " + id));

        String rawToken = issueResetToken(a.getAdminId());
        sendResetEmail(a.getEmail(), a.getFullName(), rawToken);
        return new ResetResult(a.getAdminId(), a.getEmail());
    }

    // =========================================================================
    // Helpers
    // =========================================================================

    private String issueResetToken(UUID adminId) {
        String rawToken = UUID.randomUUID().toString();
        PlatformAdminPasswordReset t = new PlatformAdminPasswordReset();
        t.setAdminId(adminId);
        t.setTokenHash(sha256(rawToken));
        t.setExpiresAt(Instant.now().plusSeconds(resetTokenTtlSeconds));
        resetRepository.save(t);
        return rawToken;
    }

    private void sendInviteEmail(String email, String fullName, String rawToken) {
        String resetUrl = frontendUrl + "/reset-password?token=" + rawToken + "&platform=1";
        sendMail(email,
                "Kaori — Bạn được mời làm quản trị viên Platform",
                buildHtml(
                        "Bạn được mời làm quản trị viên Platform Kaori.",
                        fullName,
                        "Nhấn nút bên dưới để đặt mật khẩu và bắt đầu quản trị nền tảng. "
                                + "Liên kết có hiệu lực trong <strong>1 giờ</strong>.",
                        "Kích hoạt tài khoản →",
                        resetUrl));
    }

    private void sendResetEmail(String email, String fullName, String rawToken) {
        String resetUrl = frontendUrl + "/reset-password?token=" + rawToken + "&platform=1";
        sendMail(email,
                "Kaori — Đặt lại mật khẩu Platform",
                buildHtml(
                        "Đặt lại mật khẩu Platform Kaori",
                        fullName,
                        "Nhấn nút bên dưới để đặt mật khẩu mới. Tất cả các phiên đăng nhập "
                                + "hiện tại sẽ bị vô hiệu hóa. Liên kết có hiệu lực trong <strong>1 giờ</strong>.",
                        "Đặt lại mật khẩu →",
                        resetUrl));
    }

    private void sendMail(String to, String subject, String html) {
        try {
            jakarta.mail.internet.MimeMessage msg = mailSender.createMimeMessage();
            MimeMessageHelper helper = new MimeMessageHelper(msg, false, "UTF-8");
            helper.setTo(to);
            helper.setSubject(subject);
            helper.setText(html, true);
            mailSender.send(msg);
        } catch (Exception e) {
            log.error("platform_admin.mail_failed to={} subject={} err={}", to, subject, e.getMessage());
        }
    }

    private static String buildHtml(String headline, String name, String body, String cta, String url) {
        String displayName = (name != null && !name.isBlank()) ? name : "bạn";
        return """
            <!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8"></head>
            <body style="margin:0;padding:0;background:#f5f5f5;font-family:sans-serif">
              <table width="100%%" cellpadding="0" cellspacing="0">
                <tr><td align="center" style="padding:40px 0">
                  <table width="560" cellpadding="0" cellspacing="0"
                         style="background:#fff;border-radius:12px;overflow:hidden;
                                box-shadow:0 2px 8px rgba(0,0,0,.08)">
                    <tr><td style="background:#1d4ed8;padding:28px 40px">
                      <h1 style="margin:0;color:#fff;font-size:20px;font-weight:700">Kaori Platform</h1>
                    </td></tr>
                    <tr><td style="padding:36px 40px">
                      <p style="margin:0 0 8px;color:#111827;font-size:18px;font-weight:600">%s</p>
                      <p style="margin:0 0 16px;color:#374151;font-size:16px">Xin chào <strong>%s</strong>,</p>
                      <p style="margin:0 0 24px;color:#6b7280;font-size:14px;line-height:1.6">%s</p>
                      <table cellpadding="0" cellspacing="0"><tr>
                        <td style="border-radius:8px;background:#1d4ed8">
                          <a href="%s" style="display:inline-block;padding:14px 28px;color:#fff;
                                              font-size:15px;font-weight:600;text-decoration:none">%s</a>
                        </td>
                      </tr></table>
                      <p style="margin:24px 0 0;color:#9ca3af;font-size:12px">
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
            """.formatted(headline, displayName, body, url, cta, url);
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

    private static AdminView toView(PlatformAdmin a) {
        return new AdminView(
                a.getAdminId(),
                a.getEmail(),
                a.getFullName(),
                a.getRole(),
                a.isActive(),
                a.isMfaEnabled(),
                a.getLastLoginAt(),
                a.getCreatedAt()
        );
    }

    // =========================================================================
    // Return + exception types
    // =========================================================================

    public record AdminView(
            UUID    adminId,
            String  email,
            String  fullName,
            String  role,
            boolean isActive,
            boolean mfaEnabled,
            Instant lastLoginAt,
            Instant createdAt
    ) {}

    public record ResetResult(UUID adminId, String emailSentTo) {}

    public static class AdminNotFoundException extends RuntimeException {
        public AdminNotFoundException(String msg) { super(msg); }
    }
    public static class AdminAlreadyExistsException extends RuntimeException {
        public AdminAlreadyExistsException(String msg) { super(msg); }
    }
    public static class InvalidRoleException extends RuntimeException {
        public InvalidRoleException(String msg) { super(msg); }
    }
    public static class InvalidEmailException extends RuntimeException {
        public InvalidEmailException(String msg) { super(msg); }
    }
    public static class InvalidFullNameException extends RuntimeException {
        public InvalidFullNameException(String msg) { super(msg); }
    }
}
