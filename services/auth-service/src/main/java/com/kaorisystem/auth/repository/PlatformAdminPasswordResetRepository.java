package com.kaorisystem.auth.repository;

import com.kaorisystem.auth.model.PlatformAdminPasswordReset;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface PlatformAdminPasswordResetRepository
        extends JpaRepository<PlatformAdminPasswordReset, UUID> {

    Optional<PlatformAdminPasswordReset>
        findByTokenHashAndUsedAtIsNullAndExpiresAtAfter(String tokenHash, Instant now);

    @Modifying
    @Query("UPDATE PlatformAdminPasswordReset t SET t.usedAt = :now WHERE t.tokenId = :id")
    void markUsed(@Param("id") UUID tokenId, @Param("now") Instant now);
}
