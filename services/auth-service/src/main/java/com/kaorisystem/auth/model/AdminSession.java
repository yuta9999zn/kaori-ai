package com.kaorisystem.auth.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.Setter;

import java.time.Instant;
import java.util.UUID;

/**
 * Active P1 sign-in. One row per (admin × device); soft-revoked via
 * {@code revoked_at}. Distinct from short-lived JWTs — this is the
 * inventory the {@code /platform/security/sessions} UI shows.
 *
 * <p>Created on platform admin login (future wiring) or seeded by tests
 * via {@code AdminSessionRepository.save}.
 */
@Entity
@Table(name = "admin_sessions")
@Getter
@Setter
public class AdminSession {

    @Id
    @Column(name = "session_id")
    private UUID sessionId;

    @Column(name = "admin_id", nullable = false)
    private UUID adminId;

    @Column(name = "ip_address", length = 64)
    private String ipAddress;

    @Column(name = "user_agent", length = 500)
    private String userAgent;

    @Column(name = "device_label", length = 120)
    private String deviceLabel;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "last_active_at", nullable = false)
    private Instant lastActiveAt;

    @Column(name = "revoked_at")
    private Instant revokedAt;

    /**
     * Populated together with {@code revoked_at}. One of:
     * {@code logout}, {@code manual}, {@code idle_timeout},
     * {@code absolute_timeout}, {@code password_reset}.
     * Null while the session is active.
     */
    @Column(name = "revoke_reason", length = 40)
    private String revokeReason;

    @PrePersist
    void prePersist() {
        Instant now = Instant.now();
        if (sessionId    == null) sessionId    = UUID.randomUUID();
        if (createdAt    == null) createdAt    = now;
        if (lastActiveAt == null) lastActiveAt = now;
    }

    public boolean isActive() {
        return revokedAt == null;
    }
}
