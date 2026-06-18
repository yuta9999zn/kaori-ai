package com.kaorisystem.auth.repository;

import com.kaorisystem.auth.model.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface UserRepository extends JpaRepository<User, UUID> {

    Optional<User> findByEmailIgnoreCase(String email);

    Optional<User> findByUserIdAndEnterpriseId(UUID userId, UUID enterpriseId);

    List<User> findByEnterpriseIdOrderByCreatedAtDesc(UUID enterpriseId);

    long countByEnterpriseIdAndRole(UUID enterpriseId, String role);

    long countByEnterpriseIdAndStatusNot(UUID enterpriseId, String status);

    @Modifying
    @Query("UPDATE User u SET u.lastLoginAt = :at WHERE u.userId = :userId")
    void updateLastLogin(UUID userId, Instant at);

    @Query(value = "SELECT COUNT(*) > 0 FROM workspace_keys WHERE key_hash = :keyHash AND revoked_at IS NULL",
           nativeQuery = true)
    boolean workspaceKeyExists(String keyHash);

    @Query(value = "SELECT enterprise_id::text FROM workspace_keys WHERE key_hash = :keyHash AND revoked_at IS NULL LIMIT 1",
           nativeQuery = true)
    String findEnterpriseByKeyHash(String keyHash);

    @Modifying
    @Query(value = "UPDATE workspace_keys SET revoked_at = NOW() WHERE key_hash = :keyHash",
           nativeQuery = true)
    void revokeWorkspaceKey(String keyHash);

    // -----------------------------------------------------------------------
    // F-008 expansion — workspace member queries
    //
    // enterprise_users is FK'd to enterprises.enterprise_id, not workspaces.
    // To list members of a workspace we go workspace → enterprises → users.
    // -----------------------------------------------------------------------

    @Query(value = """
        SELECT u.* FROM enterprise_users u
        JOIN enterprises e ON e.enterprise_id = u.enterprise_id
        WHERE e.workspace_id = :wid
        ORDER BY u.created_at DESC
        """, nativeQuery = true)
    List<User> findByWorkspaceIdOrderByCreatedAtDesc(@Param("wid") java.util.UUID workspaceId);

    long countByEnterpriseIdAndRoleAndStatus(java.util.UUID enterpriseId, String role, String status);

    // -----------------------------------------------------------------------
    // F-015 — enterprise users CRUD (P2 portal).
    //
    // Native queries with optional role/status filters; offset pagination
    // because the FE list is small (≤a few hundred members per tenant) and
    // existing UI uses page-based DataTable. Cursor pagination is overkill
    // here. Soft-deleted rows (status='deleted') are excluded by default.
    // -----------------------------------------------------------------------

    @Query(value = """
        SELECT * FROM enterprise_users
         WHERE enterprise_id = :eid
           AND status != 'deleted'
           AND (CAST(:role AS varchar)   IS NULL OR role   = :role)
           AND (CAST(:status AS varchar) IS NULL OR status = :status)
         ORDER BY created_at DESC
         LIMIT :lim OFFSET :off
        """, nativeQuery = true)
    List<User> findByEnterpriseFiltered(@Param("eid")    java.util.UUID enterpriseId,
                                         @Param("role")   String role,
                                         @Param("status") String status,
                                         @Param("lim")    int limit,
                                         @Param("off")    int offset);

    @Query(value = """
        SELECT COUNT(*) FROM enterprise_users
         WHERE enterprise_id = :eid
           AND status != 'deleted'
           AND (CAST(:role AS varchar)   IS NULL OR role   = :role)
           AND (CAST(:status AS varchar) IS NULL OR status = :status)
        """, nativeQuery = true)
    long countByEnterpriseFiltered(@Param("eid")    java.util.UUID enterpriseId,
                                    @Param("role")   String role,
                                    @Param("status") String status);

    /**
     * F-015 min-MANAGER guard: how many ACTIVE managers does this enterprise
     * still have, excluding the user we're about to demote/deactivate/delete?
     * The service rejects when this would drop to 0.
     */
    @Query(value = """
        SELECT COUNT(*) FROM enterprise_users
         WHERE enterprise_id = :eid
           AND role = 'MANAGER'
           AND status = 'active'
           AND user_id <> :excludeUserId
        """, nativeQuery = true)
    long countActiveManagersExcluding(@Param("eid") java.util.UUID enterpriseId,
                                       @Param("excludeUserId") java.util.UUID excludeUserId);
}
