package com.kaorisystem.auth.model;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "enterprise_users")
@Data
@NoArgsConstructor
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "user_id")
    private UUID userId;

    @Column(name = "enterprise_id", nullable = false)
    private UUID enterpriseId;

    @Column(name = "email", nullable = false)
    private String email;

    @Column(name = "password_hash", nullable = false)
    private String passwordHash;

    @Column(name = "full_name")
    private String fullName;

    @Column(name = "role", nullable = false)
    private String role = "VIEWER";

    @Column(name = "status", nullable = false)
    private String status = "active";

    @Column(name = "last_login_at")
    private Instant lastLoginAt;

    /**
     * P1-S1 (P2-M20-007) — first-login force-change-password flag.
     * Set TRUE when {@code EnterpriseUserService.invite()} creates the row;
     * flipped to FALSE on first successful password change (either via
     * {@code /auth/reset-password} email-token flow, or via the
     * logged-in {@code /auth/users/me/change-password} endpoint).
     * Migration: {@code 039_must_change_password.sql}.
     */
    @Column(name = "must_change_password", nullable = false)
    private Boolean mustChangePassword = false;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;
}
