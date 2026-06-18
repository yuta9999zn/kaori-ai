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

@Entity
@Table(name = "subscription_change_requests")
@Getter
@Setter
public class SubscriptionChangeRequest {

    @Id
    @Column(name = "request_id")
    private UUID requestId;

    @Column(name = "enterprise_id", nullable = false)
    private UUID enterpriseId;

    @Column(name = "current_plan", nullable = false, length = 20)
    private String currentPlan;

    @Column(name = "requested_plan", nullable = false, length = 20)
    private String requestedPlan;

    @Column(name = "status", nullable = false, length = 20)
    private String status;

    @Column(name = "requested_by")
    private UUID requestedBy;

    @Column(name = "requested_at", nullable = false, updatable = false)
    private Instant requestedAt;

    @Column(name = "processed_at")
    private Instant processedAt;

    @Column(name = "processed_by")
    private UUID processedBy;

    @Column(name = "notes")
    private String notes;

    @PrePersist
    void prePersist() {
        if (requestId == null)   requestId = UUID.randomUUID();
        if (status == null)      status = "PENDING";
        if (requestedAt == null) requestedAt = Instant.now();
    }
}
