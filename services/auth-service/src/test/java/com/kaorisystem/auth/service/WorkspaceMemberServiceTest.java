package com.kaorisystem.auth.service;

import com.kaorisystem.auth.model.PasswordResetToken;
import com.kaorisystem.auth.model.User;
import com.kaorisystem.auth.model.Workspace;
import com.kaorisystem.auth.repository.PasswordResetTokenRepository;
import com.kaorisystem.auth.repository.UserRepository;
import com.kaorisystem.auth.repository.WorkspaceRepository;
import com.kaorisystem.auth.service.WorkspaceMemberService.InvalidEmailException;
import com.kaorisystem.auth.service.WorkspaceMemberService.InvalidRoleException;
import com.kaorisystem.auth.service.WorkspaceMemberService.LastManagerException;
import com.kaorisystem.auth.service.WorkspaceMemberService.MemberAlreadyExistsException;
import com.kaorisystem.auth.service.WorkspaceMemberService.MemberNotFoundException;
import com.kaorisystem.auth.service.WorkspaceMemberService.MemberView;
import com.kaorisystem.auth.service.WorkspaceService.EnterpriseNotProvisionedException;
import com.kaorisystem.auth.service.WorkspaceService.WorkspaceNotFoundException;
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
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
@DisplayName("WorkspaceMemberService — invite / updateRole / remove unit tests")
class WorkspaceMemberServiceTest {

    @Mock private WorkspaceRepository           workspaceRepository;
    @Mock private UserRepository                userRepository;
    @Mock private PasswordResetTokenRepository  resetTokenRepository;
    @Mock private PasswordEncoder               passwordEncoder;
    @Mock private JavaMailSender                mailSender;
    @Mock private WorkspaceService              workspaceService;

    @InjectMocks
    private WorkspaceMemberService memberService;

    @BeforeEach
    void setUp() {
        // Wire @Value fields that @InjectMocks cannot reach.
        ReflectionTestUtils.setField(memberService, "resetTokenTtlSeconds", 3600L);
        ReflectionTestUtils.setField(memberService, "frontendUrl", "http://localhost:3000");
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private static Workspace ws(UUID id, String name) {
        Workspace w = new Workspace();
        w.setWorkspaceId(id);
        w.setName(name);
        w.setPlanCode("TRIAL");
        w.setStatus("active");
        Instant t = Instant.parse("2026-04-25T10:00:00Z");
        w.setCreatedAt(t);
        w.setUpdatedAt(t);
        return w;
    }

    private static User user(UUID id, UUID enterpriseId, String email, String role, String status) {
        User u = new User();
        u.setUserId(id);
        u.setEnterpriseId(enterpriseId);
        u.setEmail(email);
        u.setRole(role);
        u.setStatus(status);
        u.setFullName(email);
        u.setPasswordHash("$$");
        u.setCreatedAt(Instant.parse("2026-04-25T10:00:00Z"));
        return u;
    }

    // =========================================================================
    // list()
    // =========================================================================

    @Test
    @DisplayName("list — returns mapped members for the workspace")
    void list_returnsMembers() {
        UUID workspaceId  = UUID.randomUUID();
        UUID enterpriseId = UUID.randomUUID();
        UUID userId       = UUID.randomUUID();
        given(workspaceRepository.existsById(workspaceId)).willReturn(true);
        given(userRepository.findByWorkspaceIdOrderByCreatedAtDesc(workspaceId))
                .willReturn(List.of(user(userId, enterpriseId, "a@x.io", "MANAGER", "active")));

        List<MemberView> members = memberService.list(workspaceId);

        assertThat(members).hasSize(1);
        assertThat(members.get(0).userId()).isEqualTo(userId);
        assertThat(members.get(0).email()).isEqualTo("a@x.io");
        assertThat(members.get(0).role()).isEqualTo("MANAGER");
    }

    @Test
    @DisplayName("list — unknown workspace → WorkspaceNotFoundException")
    void list_unknownWorkspace_throws() {
        UUID id = UUID.randomUUID();
        given(workspaceRepository.existsById(id)).willReturn(false);

        assertThatThrownBy(() -> memberService.list(id))
                .isInstanceOf(WorkspaceNotFoundException.class);
        verify(userRepository, never()).findByWorkspaceIdOrderByCreatedAtDesc(any());
    }

    // =========================================================================
    // invite()
    // =========================================================================

    @Test
    @DisplayName("invite — creates user (status=pending), issues reset token, sends email, audits")
    void invite_happyPath() {
        UUID workspaceId  = UUID.randomUUID();
        UUID enterpriseId = UUID.randomUUID();
        given(workspaceRepository.findById(workspaceId)).willReturn(Optional.of(ws(workspaceId, "Acme")));
        given(workspaceRepository.findEnterpriseIdByWorkspaceId(workspaceId))
                .willReturn(Optional.of(enterpriseId));
        given(userRepository.findByEmailIgnoreCase("new@x.io")).willReturn(Optional.empty());
        given(passwordEncoder.encode(anyString())).willReturn("$bcrypt$");
        given(userRepository.save(any(User.class))).willAnswer(inv -> {
            User u = inv.getArgument(0);
            u.setUserId(UUID.randomUUID());
            u.setCreatedAt(Instant.now());
            return u;
        });
        given(mailSender.createMimeMessage()).willReturn(new MimeMessage((Session) null));

        MemberView m = memberService.invite(workspaceId, "New@X.io", "ANALYST",
                "actor@kaori.io", "ADMIN", "10.0.0.1");

        // Email is normalized to lowercase
        assertThat(m.email()).isEqualTo("new@x.io");
        assertThat(m.role()).isEqualTo("ANALYST");
        assertThat(m.status()).isEqualTo("pending");

        // Side effects: user saved, reset token issued, audit recorded, email sent
        verify(userRepository).save(any(User.class));
        verify(resetTokenRepository).save(any(PasswordResetToken.class));
        verify(workspaceService).recordAudit(eq(workspaceId), eq("member.invited"),
                eq("actor@kaori.io"), eq("ADMIN"), eq("new@x.io"), eq("role=ANALYST"), eq("10.0.0.1"));
        verify(mailSender).send(any(MimeMessage.class));
    }

    @Test
    @DisplayName("invite — invalid role rejected before any DB write")
    void invite_invalidRole_throws() {
        UUID workspaceId = UUID.randomUUID();
        given(workspaceRepository.findById(workspaceId)).willReturn(Optional.of(ws(workspaceId, "X")));

        assertThatThrownBy(() -> memberService.invite(
                workspaceId, "x@y.io", "GHOST", null, null, null))
                .isInstanceOf(InvalidRoleException.class);
        verify(userRepository, never()).save(any(User.class));
        verify(workspaceService, never()).recordAudit(any(), any(), any(), any(), any(), any(), any());
    }

    @Test
    @DisplayName("invite — invalid email rejected (no @)")
    void invite_invalidEmail_throws() {
        UUID workspaceId = UUID.randomUUID();
        given(workspaceRepository.findById(workspaceId)).willReturn(Optional.of(ws(workspaceId, "X")));

        assertThatThrownBy(() -> memberService.invite(
                workspaceId, "not-an-email", "VIEWER", null, null, null))
                .isInstanceOf(InvalidEmailException.class);
    }

    @Test
    @DisplayName("invite — duplicate email in same enterprise → MemberAlreadyExistsException")
    void invite_duplicate_throws() {
        UUID workspaceId  = UUID.randomUUID();
        UUID enterpriseId = UUID.randomUUID();
        given(workspaceRepository.findById(workspaceId)).willReturn(Optional.of(ws(workspaceId, "Acme")));
        given(workspaceRepository.findEnterpriseIdByWorkspaceId(workspaceId))
                .willReturn(Optional.of(enterpriseId));
        given(userRepository.findByEmailIgnoreCase("dup@x.io"))
                .willReturn(Optional.of(user(UUID.randomUUID(), enterpriseId, "dup@x.io", "VIEWER", "active")));

        assertThatThrownBy(() -> memberService.invite(
                workspaceId, "dup@x.io", "VIEWER", null, null, null))
                .isInstanceOf(MemberAlreadyExistsException.class);
        verify(userRepository, never()).save(any(User.class));
    }

    @Test
    @DisplayName("invite — workspace exists but no enterprise → EnterpriseNotProvisionedException")
    void invite_noEnterprise_throws() {
        UUID workspaceId = UUID.randomUUID();
        given(workspaceRepository.findById(workspaceId)).willReturn(Optional.of(ws(workspaceId, "X")));
        given(workspaceRepository.findEnterpriseIdByWorkspaceId(workspaceId))
                .willReturn(Optional.empty());

        assertThatThrownBy(() -> memberService.invite(
                workspaceId, "x@y.io", "VIEWER", null, null, null))
                .isInstanceOf(EnterpriseNotProvisionedException.class);
    }

    @Test
    @DisplayName("invite — unknown workspace → WorkspaceNotFoundException")
    void invite_unknownWorkspace_throws() {
        UUID workspaceId = UUID.randomUUID();
        given(workspaceRepository.findById(workspaceId)).willReturn(Optional.empty());

        assertThatThrownBy(() -> memberService.invite(
                workspaceId, "x@y.io", "VIEWER", null, null, null))
                .isInstanceOf(WorkspaceNotFoundException.class);
    }

    // =========================================================================
    // updateRole()
    // =========================================================================

    @Test
    @DisplayName("updateRole — happy path saves role and audits with old → new label")
    void updateRole_happyPath() {
        UUID workspaceId  = UUID.randomUUID();
        UUID enterpriseId = UUID.randomUUID();
        UUID userId       = UUID.randomUUID();
        given(workspaceRepository.findEnterpriseIdByWorkspaceId(workspaceId))
                .willReturn(Optional.of(enterpriseId));
        given(userRepository.findByUserIdAndEnterpriseId(userId, enterpriseId))
                .willReturn(Optional.of(user(userId, enterpriseId, "u@x.io", "VIEWER", "active")));
        given(userRepository.save(any(User.class))).willAnswer(inv -> inv.getArgument(0));

        MemberView m = memberService.updateRole(workspaceId, userId, "ANALYST",
                "actor@kaori.io", "ADMIN", "10.0.0.1");

        assertThat(m.role()).isEqualTo("ANALYST");
        verify(workspaceService).recordAudit(eq(workspaceId), eq("member.role_changed"),
                eq("actor@kaori.io"), eq("ADMIN"), eq("u@x.io"), eq("VIEWER → ANALYST"), eq("10.0.0.1"));
    }

    @Test
    @DisplayName("updateRole — last MANAGER cannot be demoted")
    void updateRole_lastManager_throws() {
        UUID workspaceId  = UUID.randomUUID();
        UUID enterpriseId = UUID.randomUUID();
        UUID userId       = UUID.randomUUID();
        given(workspaceRepository.findEnterpriseIdByWorkspaceId(workspaceId))
                .willReturn(Optional.of(enterpriseId));
        given(userRepository.findByUserIdAndEnterpriseId(userId, enterpriseId))
                .willReturn(Optional.of(user(userId, enterpriseId, "boss@x.io", "MANAGER", "active")));
        given(userRepository.countByEnterpriseIdAndRoleAndStatus(enterpriseId, "MANAGER", "active"))
                .willReturn(1L);

        assertThatThrownBy(() -> memberService.updateRole(
                workspaceId, userId, "VIEWER", null, null, null))
                .isInstanceOf(LastManagerException.class);
        verify(userRepository, never()).save(any(User.class));
    }

    @Test
    @DisplayName("updateRole — demoting MANAGER allowed when other managers exist")
    void updateRole_demoteManager_allowedWithPeers() {
        UUID workspaceId  = UUID.randomUUID();
        UUID enterpriseId = UUID.randomUUID();
        UUID userId       = UUID.randomUUID();
        given(workspaceRepository.findEnterpriseIdByWorkspaceId(workspaceId))
                .willReturn(Optional.of(enterpriseId));
        given(userRepository.findByUserIdAndEnterpriseId(userId, enterpriseId))
                .willReturn(Optional.of(user(userId, enterpriseId, "m@x.io", "MANAGER", "active")));
        given(userRepository.countByEnterpriseIdAndRoleAndStatus(enterpriseId, "MANAGER", "active"))
                .willReturn(2L);
        given(userRepository.save(any(User.class))).willAnswer(inv -> inv.getArgument(0));

        MemberView m = memberService.updateRole(workspaceId, userId, "OPERATOR", null, null, null);

        assertThat(m.role()).isEqualTo("OPERATOR");
    }

    @Test
    @DisplayName("updateRole — invalid role rejected")
    void updateRole_invalidRole_throws() {
        assertThatThrownBy(() -> memberService.updateRole(
                UUID.randomUUID(), UUID.randomUUID(), "GHOST", null, null, null))
                .isInstanceOf(InvalidRoleException.class);
    }

    @Test
    @DisplayName("updateRole — unknown member → MemberNotFoundException")
    void updateRole_memberNotFound_throws() {
        UUID workspaceId  = UUID.randomUUID();
        UUID enterpriseId = UUID.randomUUID();
        UUID userId       = UUID.randomUUID();
        given(workspaceRepository.findEnterpriseIdByWorkspaceId(workspaceId))
                .willReturn(Optional.of(enterpriseId));
        given(userRepository.findByUserIdAndEnterpriseId(userId, enterpriseId))
                .willReturn(Optional.empty());

        assertThatThrownBy(() -> memberService.updateRole(
                workspaceId, userId, "VIEWER", null, null, null))
                .isInstanceOf(MemberNotFoundException.class);
    }

    // =========================================================================
    // remove()
    // =========================================================================

    @Test
    @DisplayName("remove — happy path deletes user and audits")
    void remove_happyPath() {
        UUID workspaceId  = UUID.randomUUID();
        UUID enterpriseId = UUID.randomUUID();
        UUID userId       = UUID.randomUUID();
        User u = user(userId, enterpriseId, "u@x.io", "VIEWER", "active");
        given(workspaceRepository.findEnterpriseIdByWorkspaceId(workspaceId))
                .willReturn(Optional.of(enterpriseId));
        given(userRepository.findByUserIdAndEnterpriseId(userId, enterpriseId))
                .willReturn(Optional.of(u));

        memberService.remove(workspaceId, userId, "actor@kaori.io", "ADMIN", "10.0.0.1");

        verify(userRepository).delete(u);
        verify(workspaceService).recordAudit(eq(workspaceId), eq("member.removed"),
                eq("actor@kaori.io"), eq("ADMIN"), eq("u@x.io"), eq("role=VIEWER"), eq("10.0.0.1"));
    }

    @Test
    @DisplayName("remove — last MANAGER cannot be removed")
    void remove_lastManager_throws() {
        UUID workspaceId  = UUID.randomUUID();
        UUID enterpriseId = UUID.randomUUID();
        UUID userId       = UUID.randomUUID();
        given(workspaceRepository.findEnterpriseIdByWorkspaceId(workspaceId))
                .willReturn(Optional.of(enterpriseId));
        given(userRepository.findByUserIdAndEnterpriseId(userId, enterpriseId))
                .willReturn(Optional.of(user(userId, enterpriseId, "boss@x.io", "MANAGER", "active")));
        given(userRepository.countByEnterpriseIdAndRoleAndStatus(enterpriseId, "MANAGER", "active"))
                .willReturn(1L);

        assertThatThrownBy(() -> memberService.remove(workspaceId, userId, null, null, null))
                .isInstanceOf(LastManagerException.class);
        verify(userRepository, never()).delete(any(User.class));
    }

    @Test
    @DisplayName("remove — unknown member → MemberNotFoundException")
    void remove_memberNotFound_throws() {
        UUID workspaceId  = UUID.randomUUID();
        UUID enterpriseId = UUID.randomUUID();
        UUID userId       = UUID.randomUUID();
        given(workspaceRepository.findEnterpriseIdByWorkspaceId(workspaceId))
                .willReturn(Optional.of(enterpriseId));
        given(userRepository.findByUserIdAndEnterpriseId(userId, enterpriseId))
                .willReturn(Optional.empty());

        assertThatThrownBy(() -> memberService.remove(workspaceId, userId, null, null, null))
                .isInstanceOf(MemberNotFoundException.class);
    }
}
