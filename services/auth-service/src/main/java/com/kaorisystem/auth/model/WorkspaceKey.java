package com.kaorisystem.auth.model;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.Setter;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "workspace_keys")
@Getter
@Setter
public class WorkspaceKey {

    @Id
    @Column(name = "key_id")
    private UUID keyId;

    @Column(name = "workspace_id", nullable = false)
    private UUID workspaceId;

    @Column(name = "key_hash", nullable = false, length = 64)
    private String keyHash;

    @Column(name = "label", length = 100)
    private String label;

    @Column(name = "revoked_at")
    private Instant revokedAt;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @PrePersist
    void prePersist() {
        if (keyId == null) keyId = UUID.randomUUID();
        if (createdAt == null) createdAt = Instant.now();
    }

    public boolean isActive() {
        return revokedAt == null;
    }
}
