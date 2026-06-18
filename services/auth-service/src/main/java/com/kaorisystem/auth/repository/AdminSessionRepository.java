package com.kaorisystem.auth.repository;

import com.kaorisystem.auth.model.AdminSession;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

public interface AdminSessionRepository extends JpaRepository<AdminSession, UUID> {

    /** Active sessions for one admin, newest activity first. */
    List<AdminSession> findByAdminIdAndRevokedAtIsNullOrderByLastActiveAtDesc(UUID adminId);

    /**
     * Caller-driven revoke (UI button). The {@code admin_id} guard prevents a
     * malicious admin from revoking another admin's session via the nested URL.
     */
    @Modifying
    @Query("UPDATE AdminSession s SET s.revokedAt = :now, s.revokeReason = :reason "
         + "WHERE s.sessionId = :sessionId AND s.adminId = :adminId AND s.revokedAt IS NULL")
    int revokeForAdmin(
            @Param("sessionId") UUID sessionId,
            @Param("adminId")   UUID adminId,
            @Param("now")       Instant now,
            @Param("reason")    String reason);

    /**
     * System-driven revoke (logout, idle timeout, absolute timeout, password reset).
     * No admin scope — the writer already knows what session it is revoking.
     */
    @Modifying
    @Query("UPDATE AdminSession s SET s.revokedAt = :now, s.revokeReason = :reason "
         + "WHERE s.sessionId = :sessionId AND s.revokedAt IS NULL")
    int revokeBySessionId(
            @Param("sessionId") UUID sessionId,
            @Param("now")       Instant now,
            @Param("reason")    String reason);

    /** Idempotent throttled touch of last_active_at. Returns 0 if session was already revoked. */
    @Modifying
    @Query("UPDATE AdminSession s SET s.lastActiveAt = :now "
         + "WHERE s.sessionId = :sessionId AND s.revokedAt IS NULL")
    int touchLastActive(
            @Param("sessionId") UUID sessionId,
            @Param("now")       Instant now);

    /**
     * 3.3 — bulk revoke every active session for an admin EXCEPT one. Used by
     * "Revoke all other sessions" on /platform/security/sessions. The
     * {@code keepSessionId} is typically the caller's current session, parsed
     * from the X-Session-Id header. Pass a random UUID (matches no row) to
     * revoke every active session including the caller's.
     */
    @Modifying
    @Query("UPDATE AdminSession s "
         + "  SET s.revokedAt = :now, s.revokeReason = :reason "
         + "WHERE s.adminId = :adminId "
         + "  AND s.sessionId <> :keepSessionId "
         + "  AND s.revokedAt IS NULL")
    int revokeAllExcept(
            @Param("adminId")        UUID adminId,
            @Param("keepSessionId")  UUID keepSessionId,
            @Param("now")            Instant now,
            @Param("reason")         String reason);
}
