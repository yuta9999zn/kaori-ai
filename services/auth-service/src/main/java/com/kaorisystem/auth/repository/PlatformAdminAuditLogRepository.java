package com.kaorisystem.auth.repository;

import com.kaorisystem.auth.model.PlatformAdminAuditLog;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Repository
public interface PlatformAdminAuditLogRepository extends JpaRepository<PlatformAdminAuditLog, UUID> {

    long countByAdminId(UUID adminId);

    /** Newest first, used by tests + (future) /platform/admins/{id}/audit feed. */
    @Query(value = """
        SELECT * FROM platform_admin_audit_log
         WHERE admin_id = :aid
         ORDER BY created_at DESC, event_id DESC
         LIMIT :lim
        """, nativeQuery = true)
    List<PlatformAdminAuditLog> findFirstPage(
            @Param("aid") UUID adminId,
            @Param("lim") int limit);

    @Query(value = """
        SELECT * FROM platform_admin_audit_log
         WHERE admin_id = :aid
           AND (created_at, event_id) < (:cursorTs, :cursorId)
         ORDER BY created_at DESC, event_id DESC
         LIMIT :lim
        """, nativeQuery = true)
    List<PlatformAdminAuditLog> findPageAfter(
            @Param("aid")      UUID    adminId,
            @Param("cursorTs") Instant cursorTs,
            @Param("cursorId") UUID    cursorId,
            @Param("lim")      int     limit);
}
