package com.kaorisystem.auth.service;

import com.kaorisystem.auth.model.PlatformAdminAuditLog;
import com.kaorisystem.auth.repository.PlatformAdminAuditLogRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

/**
 * Batch 3.1.b — Audit emitter for platform-admin-scoped events.
 *
 * <p>Best-effort by design: a Postgres hiccup or schema-drift bug while writing
 * an audit row must NEVER break the originating MFA / session flow. The
 * {@code recordAudit} method swallows exceptions and only logs them, mirroring
 * {@link WorkspaceService#recordAudit}.
 *
 * <p>The transaction is {@link Propagation#REQUIRES_NEW} so that any rollback
 * in the calling service (e.g. {@code AdminSecurityService.verifyMfa} throwing
 * after the audit write) does not erase the audit row. Loud silences are
 * worse than partial truth here.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class PlatformAdminAuditService {

    public static final String EVT_MFA_INITIATED        = "admin.mfa.initiated";
    public static final String EVT_MFA_ENABLED          = "admin.mfa.enabled";
    public static final String EVT_MFA_VERIFIED         = "admin.mfa.verified";
    public static final String EVT_MFA_VERIFY_FAILED    = "admin.mfa.verify_failed";
    public static final String EVT_SESSION_REVOKED      = "admin.session.revoked";

    /** B3 PR #8 — login-time MFA challenge issued (admin entered correct password but mfa_enabled=true). */
    public static final String EVT_MFA_LOGIN_CHALLENGED = "admin.mfa.login_challenged";

    /** B3 PR #8 — login-time MFA challenge successfully completed (session issued). */
    public static final String EVT_MFA_LOGIN_VERIFIED   = "admin.mfa.login_verified";

    /** B3 PR #8 — login-time MFA verify failed (invalid code or expired/used challenge). */
    public static final String EVT_MFA_LOGIN_FAILED     = "admin.mfa.login_failed";

    private final PlatformAdminAuditLogRepository repo;

    /**
     * Best-effort audit write. Caller never sees an exception even if the
     * insert fails (DB unreachable, schema drift, etc.). Failures are logged
     * at WARN — operational telemetry, not a control-plane signal.
     *
     * @param adminId     the platform admin the event is about
     * @param eventType   one of {@code EVT_*} constants
     * @param actorId     UUID of the acting principal — usually equals adminId
     * @param actorEmail  acting principal's email if known
     * @param actorRole   acting principal's role if known
     * @param resource    short label (session_id, MFA secret label, etc.)
     * @param detail      free-form metadata, e.g. "rate_limited=true reason=lockout"
     * @param ipAddress   client IP from X-Forwarded-For (truncated to 64 chars)
     */
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void recordAudit(UUID adminId,
                            String eventType,
                            UUID actorId,
                            String actorEmail,
                            String actorRole,
                            String resource,
                            String detail,
                            String ipAddress) {
        try {
            PlatformAdminAuditLog ev = new PlatformAdminAuditLog();
            ev.setAdminId(adminId);
            ev.setEventType(eventType);
            ev.setActorId(actorId);
            ev.setActorEmail(actorEmail);
            ev.setActorRole(actorRole);
            ev.setResource(resource);
            ev.setDetail(detail);
            ev.setIpAddress(ipAddress);
            repo.save(ev);
        } catch (Exception e) {
            log.warn("admin_audit.write_failed admin={} event={} err={}",
                    adminId, eventType, e.toString());
        }
    }
}
