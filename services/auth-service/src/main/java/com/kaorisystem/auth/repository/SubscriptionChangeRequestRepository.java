package com.kaorisystem.auth.repository;

import com.kaorisystem.auth.model.SubscriptionChangeRequest;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface SubscriptionChangeRequestRepository
        extends JpaRepository<SubscriptionChangeRequest, UUID> {

    /**
     * F-030 — duplicate-pending guard.
     *
     * Backed by the partial unique index {@code uq_scr_one_pending_per_enterprise}
     * (migration 017). This finder is what the service consults BEFORE
     * insert so a 409 surface is friendlier than the raw constraint violation.
     */
    Optional<SubscriptionChangeRequest>
        findFirstByEnterpriseIdAndStatusOrderByRequestedAtDesc(UUID enterpriseId, String status);
}
