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
 * F-010 — Password reset token for {@link PlatformAdmin}.
 *
 * Mirrors {@link PasswordResetToken} but FK-tied to platform_admins instead
 * of enterprise_users. Backed by table {@code platform_admin_password_resets}
 * (migration 011). Same SHA-256 hash + 1h TTL convention as the enterprise flow.
 */
@Entity
@Table(name = "platform_admin_password_resets")
@Data
@NoArgsConstructor
public class PlatformAdminPasswordReset {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "token_id")
    private UUID tokenId;

    @Column(name = "admin_id", nullable = false)
    private UUID adminId;

    @Column(name = "token_hash", nullable = false, unique = true, length = 64)
    private String tokenHash;

    @Column(name = "expires_at", nullable = false)
    private Instant expiresAt;

    @Column(name = "used_at")
    private Instant usedAt;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;
}
