package com.kaorisystem.auth.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.Setter;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "tenant_settings")
@Getter
@Setter
public class TenantSettings {

    @Id
    @Column(name = "enterprise_id")
    private UUID enterpriseId;

    @Column(name = "theme", nullable = false, length = 20)
    private String theme;

    @Column(name = "consent_external_ai", nullable = false)
    private boolean consentExternalAi;

    @Column(name = "notification_email", nullable = false)
    private boolean notificationEmail;

    @Column(name = "branding_logo_url")
    private String brandingLogoUrl;

    @Column(name = "branding_accent_color", length = 20)
    private String brandingAccentColor;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @PrePersist
    void prePersist() {
        Instant now = Instant.now();
        if (createdAt == null) createdAt = now;
        if (updatedAt == null) updatedAt = now;
        if (theme == null) theme = "light";
    }

    @PreUpdate
    void preUpdate() {
        updatedAt = Instant.now();
    }
}
