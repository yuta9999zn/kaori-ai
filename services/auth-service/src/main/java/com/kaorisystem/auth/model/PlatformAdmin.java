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
import org.hibernate.annotations.UpdateTimestamp;

import java.time.Instant;
import java.util.UUID;

/**
 * F-010 — Platform admin user (P1 portal).
 *
 * Distinct from {@link User} (enterprise_users): no enterprise scope,
 * different role enum (SUPER_ADMIN/ADMIN/SUPPORT), supports MFA + invite
 * lifecycle. Backed by table {@code platform_admins} (migration 011).
 */
@Entity
@Table(name = "platform_admins")
@Data
@NoArgsConstructor
public class PlatformAdmin {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "admin_id")
    private UUID adminId;

    @Column(name = "email", nullable = false, unique = true)
    private String email;

    /** Null until the admin completes invite activation (sets a password via reset link). */
    @Column(name = "password_hash")
    private String passwordHash;

    @Column(name = "full_name", nullable = false)
    private String fullName;

    /** SUPER_ADMIN | ADMIN | SUPPORT — enforced by DB CHECK constraint. */
    @Column(name = "role", nullable = false)
    private String role;

    @Column(name = "is_active", nullable = false)
    private boolean isActive = true;

    @Column(name = "mfa_enabled", nullable = false)
    private boolean mfaEnabled = false;

    /**
     * Base64 of (12-byte IV || AES-256-GCM ciphertext of the TOTP secret).
     * Null until {@code POST /security/mfa/enable}; cleared on disable.
     * Never returned to clients — verification always happens server-side.
     */
    @Column(name = "mfa_secret_enc", length = 400)
    private String mfaSecretEnc;

    @Column(name = "last_login_at")
    private Instant lastLoginAt;

    @Column(name = "invited_by")
    private UUID invitedBy;

    @Column(name = "invited_at", nullable = false, updatable = false)
    private Instant invitedAt;

    @Column(name = "activated_at")
    private Instant activatedAt;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;
}
