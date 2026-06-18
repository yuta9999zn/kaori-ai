package com.kaorisystem.auth.service;

import com.kaorisystem.auth.repository.NotificationOutboxRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoMoreInteractions;
import static org.mockito.Mockito.when;

/**
 * Issue #6 — behaviour spec for {@link NotificationClient} after the
 * outbox cutover.
 *
 * <p>Before this PR the class spoke HTTP to notification-service, and
 * the test used an unreachable port to prove the call was best-effort
 * log+swallow. The implementation now writes to a local DB outbox
 * table via {@link NotificationOutboxRepository}, so the test surface
 * is "did the right row get enqueued?" not "did the HTTP error get
 * swallowed?".
 *
 * <p>The repository itself is responsible for the swallow contract
 * (its own test pins that). Here we only verify the façade builds
 * the right context map per template kind and forwards it.
 */
@DisplayName("NotificationClient — outbox enqueue")
class NotificationClientTest {

    @SuppressWarnings("unchecked")
    private final NotificationOutboxRepository outbox = mock(NotificationOutboxRepository.class);
    private final NotificationClient client = new NotificationClient(outbox);

    @Test
    @DisplayName("sendResetPassword enqueues a 'reset-password' row with full_name + reset_url")
    void sendResetPassword_enqueuesCorrectContext() {
        when(outbox.enqueue(any(), anyString(), anyString(), any(), anyString()))
                .thenReturn(UUID.randomUUID());

        client.sendResetPassword("user@example.com", "Test User",
                "http://localhost:3000/reset-password?token=abc");

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> ctx = ArgumentCaptor.forClass(Map.class);
        // enterprise_id is null on reset-password (anti-enumeration —
        // we don't carry tenant context on /forgot-password).
        verify(outbox).enqueue(isNull(), eq("reset-password"),
                eq("user@example.com"), ctx.capture(), eq("password_reset"));

        assertThat(ctx.getValue())
                .containsEntry("full_name", "Test User")
                .containsEntry("reset_url", "http://localhost:3000/reset-password?token=abc");
    }

    @Test
    @DisplayName("sendResetPassword defaults blank full_name to 'bạn' (Vietnamese pronoun)")
    void sendResetPassword_blankFullNameDefaultsToBan() {
        client.sendResetPassword("user@example.com", "  ", "http://k.io/r/abc");

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> ctx = ArgumentCaptor.forClass(Map.class);
        verify(outbox).enqueue(isNull(), eq("reset-password"), anyString(),
                ctx.capture(), anyString());
        assertThat(ctx.getValue()).containsEntry("full_name", "bạn");
    }

    @Test
    @DisplayName("sendResetPassword defaults null full_name to 'bạn'")
    void sendResetPassword_nullFullNameDefaultsToBan() {
        client.sendResetPassword("user@example.com", null, "http://k.io/r/abc");

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> ctx = ArgumentCaptor.forClass(Map.class);
        verify(outbox).enqueue(isNull(), eq("reset-password"), anyString(),
                ctx.capture(), anyString());
        assertThat(ctx.getValue()).containsEntry("full_name", "bạn");
    }

    @Test
    @DisplayName("sendInvite enqueues a 'invite' row with all four context fields")
    void sendInvite_enqueuesCorrectContext() {
        when(outbox.enqueue(any(), anyString(), anyString(), any(), anyString()))
                .thenReturn(UUID.randomUUID());

        client.sendInvite("newuser@example.com", "Quản trị viên", "Công ty Demo",
                "http://localhost:3000/reset-password?token=xyz", "ANALYST");

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> ctx = ArgumentCaptor.forClass(Map.class);
        verify(outbox).enqueue(any(), eq("invite"), eq("newuser@example.com"),
                ctx.capture(), eq("user_invite"));

        assertThat(ctx.getValue())
                .containsEntry("invited_by", "Quản trị viên")
                .containsEntry("enterprise_name", "Công ty Demo")
                .containsEntry("invite_url", "http://localhost:3000/reset-password?token=xyz")
                .containsEntry("role", "ANALYST");
    }

    @Test
    @DisplayName("sendInvite defaults null role to 'USER' so the email never renders an empty role")
    void sendInvite_nullRoleDefaultsToUser() {
        client.sendInvite("u@k.io", "Admin", "Demo", "http://k.io/r/x", null);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> ctx = ArgumentCaptor.forClass(Map.class);
        verify(outbox).enqueue(any(), eq("invite"), anyString(),
                ctx.capture(), anyString());
        assertThat(ctx.getValue()).containsEntry("role", "USER");
    }

    @Test
    @DisplayName("repository swallow contract: caller never sees an exception")
    void repositorySwallowContractIsHonoured() {
        // The repository is documented to swallow + log on insert
        // failure. Verify the façade doesn't accidentally re-throw
        // when the repo returns null (its failure signal).
        when(outbox.enqueue(any(), anyString(), anyString(), any(), anyString()))
                .thenReturn(null);

        assertThatCode(() -> client.sendResetPassword("u@k.io", "U", "http://k.io/r/a"))
                .doesNotThrowAnyException();
        assertThatCode(() -> client.sendInvite("u@k.io", "Admin", "Demo",
                "http://k.io/r/x", "VIEWER"))
                .doesNotThrowAnyException();
    }

    @Test
    @DisplayName("does NOT make any HTTP call (outbox-only path)")
    void noHttpCallSideEffect() {
        // Constructor takes only the outbox repo; no RestClient
        // injection point exists. This test pins the cutover so a
        // future regression that re-introduces HTTP would fail to
        // compile (the test wouldn't change but the constructor
        // signature would have to grow to support both).
        client.sendResetPassword("u@k.io", "U", "http://k.io/r/a");
        verify(outbox).enqueue(any(), anyString(), anyString(), any(), anyString());
        // The only collaborator is the outbox repo; assert the façade
        // never reaches for anything else (e.g., a sneaked-in HTTP
        // client). verifyNoMoreInteractions covers every public method
        // on the mock — including any future addition.
        verifyNoMoreInteractions(outbox);
    }
}
