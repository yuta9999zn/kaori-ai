package com.kaorisystem.auth.repository;

import com.kaorisystem.auth.model.WorkspaceAuditLog;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Repository
public interface WorkspaceAuditLogRepository extends JpaRepository<WorkspaceAuditLog, UUID> {

    long countByWorkspaceId(UUID workspaceId);

    /** First page (no cursor) — newest first. */
    @Query(value = """
        SELECT * FROM workspace_audit_log
        WHERE workspace_id = :wid
        ORDER BY created_at DESC, event_id DESC
        LIMIT :lim
        """, nativeQuery = true)
    List<WorkspaceAuditLog> findFirstPage(
            @Param("wid") UUID workspaceId,
            @Param("lim") int limit);

    /**
     * Subsequent pages — keyset on (created_at, event_id) DESC. Tuple compare
     * keeps ordering stable when several rows share a timestamp.
     */
    @Query(value = """
        SELECT * FROM workspace_audit_log
        WHERE workspace_id = :wid
          AND (created_at, event_id) < (:cursorTs, :cursorId)
        ORDER BY created_at DESC, event_id DESC
        LIMIT :lim
        """, nativeQuery = true)
    List<WorkspaceAuditLog> findPageAfter(
            @Param("wid")      UUID    workspaceId,
            @Param("cursorTs") Instant cursorTs,
            @Param("cursorId") UUID    cursorId,
            @Param("lim")      int     limit);
}
