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
 * B3 PR #8 — one-time MFA challenge issued at /auth/platform/login when
 * {@code admin.mfa_enabled=true}. Exchanged for a real session at
 * /auth/platform/mfa/verify.
 *
 * <p>{@code used_at} is the one-time-use guard; the verify path flips it
 * inside the same transaction as the success path so a concurrent
 * second use of the same challenge_token surfaces as "already used"
 * (not as a TOTP-validation race).
 *
 * <p>{@code attempts} caps invalid-code retries against THIS row at 5.
 * Distinct from the per-admin Redis lockout maintained by
 * {@code AdminSecurityService.verifyMfa}: the admin can always
 * /login again to mint a fresh challenge, but this row is dead the
 * moment its counter trips.
 */
@Entity
@Table(name = "mfa_challenges")
@Getter
@Setter
public class MfaChallenge {

    @Id
    @Column(name = "challenge_id")
    private UUID challengeId;

    @Column(name = "admin_id", nullable = false)
    private UUID adminId;

    /** SHA-256 hex of the JWT sent back to the FE — the verify path looks up by hash. */
    @Column(name = "challenge_token_hash", nullable = false, length = 64, unique = true)
    private String challengeTokenHash;

    @Column(name = "expires_at", nullable = false)
    private Instant expiresAt;

    /** Set on successful verify, OR on attempts-exhaustion with a sentinel. */
    @Column(name = "used_at")
    private Instant usedAt;

    @Column(name = "attempts", nullable = false)
    private int attempts;

    @Column(name = "ip_address", length = 64)
    private String ipAddress;

    @Column(name = "user_agent", length = 500)
    private String userAgent;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @PrePersist
    void prePersist() {
        Instant now = Instant.now();
        if (challengeId == null) challengeId = UUID.randomUUID();
        if (createdAt   == null) createdAt   = now;
    }

    public boolean isExpired(Instant now) {
        return !now.isBefore(expiresAt);
    }

    public boolean isUsed() {
        return usedAt != null;
    }
}
