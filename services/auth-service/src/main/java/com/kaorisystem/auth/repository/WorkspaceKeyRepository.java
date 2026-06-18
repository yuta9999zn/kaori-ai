package com.kaorisystem.auth.repository;

import com.kaorisystem.auth.model.WorkspaceKey;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface WorkspaceKeyRepository extends JpaRepository<WorkspaceKey, UUID> {

    List<WorkspaceKey> findByWorkspaceIdOrderByCreatedAtDesc(UUID workspaceId);

    Optional<WorkspaceKey> findByKeyHashAndRevokedAtIsNull(String keyHash);

    boolean existsByKeyHashAndRevokedAtIsNull(String keyHash);

    @Modifying
    @Query("UPDATE WorkspaceKey k SET k.revokedAt = :now WHERE k.keyId = :keyId AND k.revokedAt IS NULL")
    int revokeById(@Param("keyId") UUID keyId, @Param("now") Instant now);

    @Modifying
    @Query("UPDATE WorkspaceKey k SET k.revokedAt = :now WHERE k.keyHash = :hash AND k.revokedAt IS NULL")
    int revokeByHash(@Param("hash") String hash, @Param("now") Instant now);

    @Query("SELECT k.workspaceId FROM WorkspaceKey k WHERE k.keyHash = :hash AND k.revokedAt IS NULL")
    Optional<UUID> findWorkspaceIdByActiveHash(@Param("hash") String hash);

    // Joins enterprises table to resolve enterprise_id from a workspace key
    @Query(value = """
        SELECT e.enterprise_id FROM workspace_keys wk
        JOIN enterprises e ON e.workspace_id = wk.workspace_id
        WHERE wk.key_hash = :hash AND wk.revoked_at IS NULL
        LIMIT 1
        """, nativeQuery = true)
    Optional<UUID> findEnterpriseIdByActiveHash(@Param("hash") String hash);
}
