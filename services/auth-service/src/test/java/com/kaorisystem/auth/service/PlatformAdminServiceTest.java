package com.kaorisystem.auth.service;

import com.kaorisystem.auth.model.PlatformAdmin;
import com.kaorisystem.auth.model.PlatformAdminPasswordReset;
import com.kaorisystem.auth.repository.PlatformAdminPasswordResetRepository;
import com.kaorisystem.auth.repository.PlatformAdminRepository;
import com.kaorisystem.auth.service.PlatformAdminService.AdminAlreadyExistsException;
import com.kaorisystem.auth.service.PlatformAdminService.AdminNotFoundException;
import com.kaorisystem.auth.service.PlatformAdminService.AdminView;
import com.kaorisystem.auth.service.PlatformAdminService.InvalidEmailException;
import com.kaorisystem.auth.service.PlatformAdminService.InvalidFullNameException;
import com.kaorisystem.auth.service.PlatformAdminService.InvalidRoleException;
import com.kaorisystem.auth.service.PlatformAdminService.ResetResult;
import jakarta.mail.Session;
import jakarta.mail.internet.MimeMessage;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
@DisplayName("PlatformAdminService — list / get / invite / update / resetPassword unit tests")
class PlatformAdminServiceTest {

    @Mock private PlatformAdminRepository              adminRepository;
    @Mock private PlatformAdminPasswordResetRepository resetRepository;
    @Mock private PasswordEncoder                      passwordEncoder;
    @Mock private JavaMailSender                       mailSender;

    @InjectMocks
    private PlatformAdminService adminService;

    @BeforeEach
    void setUp() {
        ReflectionTestUtils.setField(adminService, "resetTokenTtlSeconds", 3600L);
        ReflectionTestUtils.setField(adminService, "frontendUrl", "http://localhost:3000");
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private static PlatformAdmin admin(UUID id, String email, String role) {
        PlatformAdmin a = new PlatformAdmin();
        a.setAdminId(id);
        a.setEmail(email);
        a.setFullName("Test User");
        a.setRole(role);
        a.setActive(true);
        a.setMfaEnabled(false);
        a.setInvitedAt(Instant.parse("2026-04-25T10:00:00Z"));
        a.setCreatedAt(Instant.parse("2026-04-25T10:00:00Z"));
        return a;
    }

    // =========================================================================
    // list / get
    // =========================================================================

    @Test
    @DisplayName("list — returns mapped admin views ordered by repo")
    void list_returnsMappedViews() {
        UUID id1 = UUID.randomUUID();
        UUID id2 = UUID.randomUUID();
        given(adminRepository.findAllByOrderByCreatedAtDesc())
                .willReturn(List.of(admin(id1, "a@k.io", "ADMIN"), admin(id2, "b@k.io", "SUPPORT")));

        List<AdminView> views = adminService.list();

        assertThat(views).hasSize(2);
        assertThat(views.get(0).adminId()).isEqualTo(id1);
        assertThat(views.get(0).role()).isEqualTo("ADMIN");
        assertThat(views.get(1).role()).isEqualTo("SUPPORT");
    }

    @Test
    @DisplayName("get — returns view for known id")
    void get_known() {
        UUID id = UUID.randomUUID();
        given(adminRepository.findById(id)).willReturn(Optional.of(admin(id, "x@k.io", "ADMIN")));

        AdminView v = adminService.get(id);

        assertThat(v.adminId()).isEqualTo(id);
        assertThat(v.email()).isEqualTo("x@k.io");
    }

    @Test
    @DisplayName("get — unknown id raises AdminNotFoundException")
    void get_unknown_throws() {
        UUID id = UUID.randomUUID();
        given(adminRepository.findById(id)).willReturn(Optional.empty());

        assertThatThrownBy(() -> adminService.get(id))
                .isInstanceOf(AdminNotFoundException.class);
    }

    // =========================================================================
    // invite
    // =========================================================================

    @Test
    @DisplayName("invite — creates admin (active, mfa=false), issues reset token, sends email")
    void invite_happyPath() {
        given(adminRepository.existsByEmailIgnoreCase("new@k.io")).willReturn(false);
        given(passwordEncoder.encode(anyString())).willReturn("$bcrypt$");
        given(adminRepository.save(any(PlatformAdmin.class))).willAnswer(inv -> {
            PlatformAdmin a = inv.getArgument(0);
            a.setAdminId(UUID.randomUUID());
            a.setCreatedAt(Instant.now());
            return a;
        });
        given(mailSender.createMimeMessage()).willReturn(new MimeMessage((Session) null));

        UUID inviter = UUID.randomUUID();
        AdminView v = adminService.invite("New@K.io", "Người Mới", "ADMIN", inviter);

        assertThat(v.email()).isEqualTo("new@k.io");          // normalized
        assertThat(v.fullName()).isEqualTo("Người Mới");
        assertThat(v.role()).isEqualTo("ADMIN");
        assertThat(v.isActive()).isTrue();
        assertThat(v.mfaEnabled()).isFalse();

        // Side effects: persisted, reset token issued, email sent
        ArgumentCaptor<PlatformAdmin> adminCap = ArgumentCaptor.forClass(PlatformAdmin.class);
        verify(adminRepository).save(adminCap.capture());
        assertThat(adminCap.getValue().getInvitedBy()).isEqualTo(inviter);

        verify(resetRepository).save(any(PlatformAdminPasswordReset.class));
        verify(mailSender).send(any(MimeMessage.class));
    }

    @Test
    @DisplayName("invite — duplicate email → AdminAlreadyExistsException, no save")
    void invite_duplicate_throws() {
        given(adminRepository.existsByEmailIgnoreCase("dup@k.io")).willReturn(true);

        assertThatThrownBy(() -> adminService.invite("dup@k.io", "X", "ADMIN", null))
                .isInstanceOf(AdminAlreadyExistsException.class);
        verify(adminRepository, never()).save(any(PlatformAdmin.class));
        verify(resetRepository, never()).save(any(PlatformAdminPasswordReset.class));
    }

    @Test
    @DisplayName("invite — invalid role rejected")
    void invite_invalidRole_throws() {
        assertThatThrownBy(() -> adminService.invite("x@k.io", "X", "GHOST", null))
                .isInstanceOf(InvalidRoleException.class);
        verify(adminRepository, never()).save(any(PlatformAdmin.class));
    }

    @Test
    @DisplayName("invite — invalid email (no @) rejected")
    void invite_invalidEmail_throws() {
        assertThatThrownBy(() -> adminService.invite("not-an-email", "X", "ADMIN", null))
                .isInstanceOf(InvalidEmailException.class);
    }

    @Test
    @DisplayName("invite — blank full_name rejected")
    void invite_blankFullName_throws() {
        assertThatThrownBy(() -> adminService.invite("x@k.io", "  ", "ADMIN", null))
                .isInstanceOf(InvalidFullNameException.class);
    }

    // =========================================================================
    // update
    // =========================================================================

    @Test
    @DisplayName("update — partial: only is_active flag changes")
    void update_isActiveOnly() {
        UUID id = UUID.randomUUID();
        PlatformAdmin a = admin(id, "x@k.io", "SUPPORT");
        given(adminRepository.findById(id)).willReturn(Optional.of(a));
        given(adminRepository.save(any(PlatformAdmin.class))).willAnswer(inv -> inv.getArgument(0));

        AdminView v = adminService.update(id, null, null, false);

        assertThat(v.isActive()).isFalse();
        assertThat(v.role()).isEqualTo("SUPPORT");           // unchanged
        assertThat(v.fullName()).isEqualTo("Test User");      // unchanged
    }

    @Test
    @DisplayName("update — role change to ADMIN persists")
    void update_roleChange() {
        UUID id = UUID.randomUUID();
        given(adminRepository.findById(id)).willReturn(Optional.of(admin(id, "x@k.io", "SUPPORT")));
        given(adminRepository.save(any(PlatformAdmin.class))).willAnswer(inv -> inv.getArgument(0));

        AdminView v = adminService.update(id, null, "ADMIN", null);

        assertThat(v.role()).isEqualTo("ADMIN");
    }

    @Test
    @DisplayName("update — invalid role rejected")
    void update_invalidRole_throws() {
        UUID id = UUID.randomUUID();
        given(adminRepository.findById(id)).willReturn(Optional.of(admin(id, "x@k.io", "ADMIN")));

        assertThatThrownBy(() -> adminService.update(id, null, "GHOST", null))
                .isInstanceOf(InvalidRoleException.class);
        verify(adminRepository, never()).save(any(PlatformAdmin.class));
    }

    @Test
    @DisplayName("update — blank full_name rejected")
    void update_blankFullName_throws() {
        UUID id = UUID.randomUUID();
        given(adminRepository.findById(id)).willReturn(Optional.of(admin(id, "x@k.io", "ADMIN")));

        assertThatThrownBy(() -> adminService.update(id, "   ", null, null))
                .isInstanceOf(InvalidFullNameException.class);
    }

    @Test
    @DisplayName("update — unknown id → AdminNotFoundException")
    void update_unknown_throws() {
        UUID id = UUID.randomUUID();
        given(adminRepository.findById(id)).willReturn(Optional.empty());

        assertThatThrownBy(() -> adminService.update(id, "Z", "ADMIN", true))
                .isInstanceOf(AdminNotFoundException.class);
    }

    // =========================================================================
    // resetPassword
    // =========================================================================

    @Test
    @DisplayName("resetPassword — issues token, sends email, returns email it was sent to")
    void resetPassword_happyPath() {
        UUID id = UUID.randomUUID();
        given(adminRepository.findById(id)).willReturn(Optional.of(admin(id, "boss@k.io", "SUPER_ADMIN")));
        given(mailSender.createMimeMessage()).willReturn(new MimeMessage((Session) null));

        ResetResult r = adminService.resetPassword(id);

        assertThat(r.adminId()).isEqualTo(id);
        assertThat(r.emailSentTo()).isEqualTo("boss@k.io");
        verify(resetRepository).save(any(PlatformAdminPasswordReset.class));
        verify(mailSender).send(any(MimeMessage.class));
    }

    @Test
    @DisplayName("resetPassword — unknown id → AdminNotFoundException, no token issued")
    void resetPassword_unknown_throws() {
        UUID id = UUID.randomUUID();
        given(adminRepository.findById(id)).willReturn(Optional.empty());

        assertThatThrownBy(() -> adminService.resetPassword(id))
                .isInstanceOf(AdminNotFoundException.class);
        verify(resetRepository, never()).save(any(PlatformAdminPasswordReset.class));
    }
}
