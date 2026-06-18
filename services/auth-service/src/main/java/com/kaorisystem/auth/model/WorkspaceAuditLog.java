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
 * F-008 expansion — Workspace audit event.
 *
 * Append-only (DB rules block UPDATE/DELETE — see migration 011). Distinct
 * from {@code decision_audit_log} which is AI-decision specific (K-6). This
 * table captures admin/operator actions that have no AI semantics:
 * workspace edits, member invites/removals, billing plan changes, etc.
 */
@Entity
@Table(name = "workspace_audit_log")
@Data
@NoArgsConstructor
public class WorkspaceAuditLog {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "event_id")
    private UUID eventId;

    @Column(name = "workspace_id", nullable = false)
    private UUID workspaceId;

    @Column(name = "event_type", nullable = false, length = 80)
    private String eventType;

    /**
     * UUID of the acting principal — usually the {@code platform_admins.admin_id}
     * for staff actions, or {@code enterprise_users.user_id} for tenant actions.
     * Nullable for system events and for historic rows written before
     * migration 014.
     */
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
