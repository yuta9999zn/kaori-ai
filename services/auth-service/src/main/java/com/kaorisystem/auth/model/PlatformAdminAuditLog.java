package com.kaorisystem.auth.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.CreationTimestamp;

import java.time.Instant;
import java.util.UUID;

/**
 * Batch 3.1.b — Platform admin audit event.
 *
 * <p>Append-only (DB rules block UPDATE/DELETE — see migration 014). Mirrors
 * the {@link WorkspaceAuditLog} shape, but keyed on {@code admin_id} instead
 * of {@code workspace_id} so events that have no workspace context (MFA
 * lifecycle, session revoke) live here without polluting the workspace
 * audit feed.
 *
 * <p>Event types written today (Batch 3.1.b):
 * <ul>
 *   <li>{@code admin.mfa.initiated}      — {@code POST /security/mfa/enable}</li>
 *   <li>{@code admin.mfa.enabled}        — {@code POST /security/mfa/verify} success</li>
 *   <li>{@code admin.mfa.verified}       — alias of {@code enabled} for the
 *                                            success-after-already-enabled path</li>
 *   <li>{@code admin.mfa.verify_failed}  — wrong code or rate-limit hit</li>
 *   <li>{@code admin.session.revoked}    — manual / logout / idle_timeout /
 *                                            absolute_timeout / password_reset</li>
 * </ul>
 */
@Entity
@Table(name = "platform_admin_audit_log")
@Data
@NoArgsConstructor
public class PlatformAdminAuditLog {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "event_id")
    private UUID eventId;

    @Column(name = "admin_id", nullable = false)
    private UUID adminId;

    @Column(name = "event_type", nullable = false, length = 80)
    private String eventType;

    /** Usually the same as {@code admin_id}; differs when one admin acts on another. */
    @Column(name = "actor_id")
    private UUID actorId;

    @Column(name = "actor_email")
    private String actorEmail;

    @Column(name = "actor_role", length = 40)
    private String actorRole;

    @Column(name = "resource", length = 200)
    private String resource;

    @Column(name = "detail", columnDefinition = "TEXT")
    private String detail;

    @Column(name = "ip_address", length = 64)
    private String ipAddress;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;
}
