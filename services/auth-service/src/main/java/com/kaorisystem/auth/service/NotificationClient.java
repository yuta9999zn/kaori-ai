package com.kaorisystem.auth.service;

import com.kaorisystem.auth.repository.NotificationOutboxRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.UUID;

/**
 * Thin façade over {@link NotificationOutboxRepository} — builds the
 * template + context map for each notification kind, then hands the
 * row to the outbox.
 *
 * <p>Issue #6 outbox cutover history. Before this change, sends went out
 * over HTTP to {@code notification-service:/internal/notifications/send}
 * and the call was best-effort log+swallow — a transient SMTP failure
 * meant the email was permanently lost. The outbox flips that: the
 * caller's existing {@code @Transactional} method now writes a durable
 * row alongside its trigger event (password reset row, user invitation
 * row), and notification-service's poller picks it up with retries.
 *
 * <p>Caller surface unchanged on purpose. {@link AuthService} and
 * {@link EnterpriseUserService} keep calling
 * {@code sendResetPassword(...)} / {@code sendInvite(...)} the same way;
 * only the implementation switched. Test mocks of {@code NotificationClient}
 * stay valid.
 *
 * <p>Why no circuit breaker here anymore: the previous version wrapped
 * the HTTP call in Resilience4j because notification-service could be
 * down. After the switch, the only failure mode is a local DB INSERT,
 * which Postgres handles via the connection pool's own circuit
 * (HikariCP timeout → exception → log+swallow in the repository).
 * Layering Resilience4j on top of that would add config to maintain
 * with no benefit.
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class NotificationClient {

    private final NotificationOutboxRepository outbox;

    /**
     * Password-reset email — context matches the template
     * {@code services/notification-service/templates/reset_password.html}.
     *
     * <p>Tenant scope is currently best-effort: F-007 forgot-password
     * doesn't carry tenant context (anti-enumeration), so {@code enterpriseId}
     * is null. Future per-tenant notification quotas will need a
     * resolution step here.
     */
    public void sendResetPassword(String email, String fullName, String resetUrl) {
        Map<String, Object> context = Map.of(
                "full_name", fullName == null || fullName.isBlank() ? "bạn" : fullName,
                "reset_url", resetUrl
        );
        outbox.enqueue(null, "reset-password", email, context, "password_reset");
    }

    /**
     * Invite email — context matches
     * {@code services/notification-service/templates/invite.html}.
     */
    public void sendInvite(String email, String invitedBy, String enterpriseName,
                           String inviteUrl, String role) {
        Map<String, Object> context = Map.of(
                "invited_by",      invitedBy      == null ? ""    : invitedBy,
                "enterprise_name", enterpriseName == null ? ""    : enterpriseName,
                "invite_url",      inviteUrl,
                "role",            role           == null ? "USER": role
        );
        // Invite is the only flow today where we already know the
        // tenant — pass it through. Once F-007 grows tenant context
        // (sister case), the reset-password call above can stop
        // passing null.
        outbox.enqueue(resolveEnterpriseFromInvite(), "invite", email, context, "user_invite");
    }

    /**
     * Invitation flow runs as a tenant-scoped admin (MANAGER+ on the
     * inviting enterprise). The caller {@code EnterpriseUserService}
     * already has the {@code enterpriseId} — but threading it through
     * the method signature would touch every test mock. Compromise:
     * pull it from {@code SecurityContextHolder} via a helper. Until
     * that helper exists, leave null and let support trace via
     * {@code source_ref='user_invite'}.
     *
     * <p>TODO(notify-outbox-tenant): swap to context-based lookup once
     * we add a {@code TenantContextHolder} util.
     */
    private UUID resolveEnterpriseFromInvite() {
        return null;
    }
}
