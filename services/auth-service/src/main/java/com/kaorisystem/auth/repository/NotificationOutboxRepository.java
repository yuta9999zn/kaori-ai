package com.kaorisystem.auth.repository;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.UUID;

/**
 * Issue #6 outbox writer — auth-service inserts a row into
 * {@code notification_outbox} in the SAME DB transaction as the trigger
 * event (password-reset row creation, user invitation, etc.). After
 * commit, the notification is durable. The notification-service poller
 * picks up pending rows and attempts SMTP delivery with retries.
 *
 * <p>Why a JdbcTemplate component (not a Spring Data {@code @Repository}):
 * matches the {@link BillingAggregationRepository} pattern in this
 * service — the outbox row never needs to be loaded as an entity by
 * auth-service (only the poller cares about reads), and JdbcTemplate
 * keeps INSERT control explicit (JSONB cast for ``context``, default
 * ``status='pending'`` from migration 026).
 *
 * <p>Best-effort by design: this method swallows exceptions and logs
 * them rather than propagating. Two reasons:
 * <ul>
 *   <li>The caller (e.g., {@code AuthService.forgotPassword}) is already
 *       inside an {@code @Transactional} method that committed the
 *       trigger row; rolling that back because the outbox INSERT bumped
 *       a constraint would punish the user for an internal infra
 *       glitch.</li>
 *   <li>Anti-enumeration (forgot-password) demands 200 every time, so
 *       a throw here would be surfaced via the global exception handler
 *       and leak signal to attackers.</li>
 * </ul>
 * Trade-off: a failed enqueue means the email never reaches the user.
 * Counter that with the {@code notification.enqueue.failed} log line +
 * Prometheus counter (added in a follow-up audit-spec task — Issue #1
 * "audit-write-failure counter" in the same audit doc).
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class NotificationOutboxRepository {

    private final NamedParameterJdbcTemplate jdbc;

    /**
     * Jackson is reused across calls — instance creation is non-trivial
     * and the {@link ObjectMapper} is documented thread-safe for
     * read/write of value types.
     */
    private static final ObjectMapper JSON = new ObjectMapper();

    /**
     * Insert a pending notification row. Returns the assigned outbox_id
     * so callers can stash it (e.g., as a correlation ref in a sibling
     * audit row) — null when the insert failed.
     *
     * @param enterpriseId tenant scope; nullable for system-wide
     *                     notifications (rarely used today)
     * @param template     matches {@code TemplateType} in
     *                     notification-service's {@code models.py}
     *                     ({@code "reset-password"}, {@code "invite"},
     *                     {@code "quota-alert"})
     * @param recipient    user email (RFC 5321; max 320 chars enforced
     *                     by column type)
     * @param context      template render variables (serialised to JSONB)
     * @param sourceRef    optional opaque correlation id (e.g., the
     *                     password_reset row id) for forensics
     */
    public UUID enqueue(UUID enterpriseId, String template, String recipient,
                        Map<String, Object> context, String sourceRef) {
        UUID outboxId = UUID.randomUUID();
        String contextJson;
        try {
            contextJson = JSON.writeValueAsString(context == null ? Map.of() : context);
        } catch (JsonProcessingException e) {
            // A non-serialisable context is a programmer bug, not a
            // transient infra issue. Log loudly + drop the enqueue.
            log.error("notification.enqueue.serialise_failed template={} to={} error={}",
                    template, recipient, e.getMessage());
            return null;
        }

        String sql = """
            INSERT INTO notification_outbox
                (outbox_id, enterprise_id, template, recipient_email,
                 context, source_ref)
            VALUES
                (:outboxId, :enterpriseId, :template, :recipient,
                 CAST(:context AS JSONB), :sourceRef)
            """;
        MapSqlParameterSource params = new MapSqlParameterSource()
                .addValue("outboxId",     outboxId)
                .addValue("enterpriseId", enterpriseId)
                .addValue("template",     template)
                .addValue("recipient",    recipient)
                .addValue("context",      contextJson)
                .addValue("sourceRef",    sourceRef);
        try {
            jdbc.update(sql, params);
            log.info("notification.enqueue.ok template={} to={} outbox_id={}",
                    template, recipient, outboxId);
            return outboxId;
        } catch (Exception e) {
            // Best-effort. See class Javadoc for rationale.
            log.error("notification.enqueue.failed template={} to={} error={}",
                    template, recipient, e.getMessage());
            return null;
        }
    }
}
