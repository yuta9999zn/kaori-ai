package com.kaorisystem.auth.service;

import com.kaorisystem.auth.model.Workspace;
import com.kaorisystem.auth.model.WorkspaceAuditLog;
import com.kaorisystem.auth.repository.WorkspaceAuditLogRepository;
import com.kaorisystem.auth.repository.WorkspaceRepository;
import com.kaorisystem.auth.repository.WorkspaceRepository.BillingRow;
import com.kaorisystem.auth.repository.WorkspaceRepository.WorkspaceListRow;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.Base64;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/**
 * F-008 — Workspace Management service (T-F008-02).
 *
 * Backed by Spring Data JPA via WorkspaceRepository. Cursor pagination is
 * keyset-based on (created_at, workspace_id) DESC; the cursor is a base64
 * blob of "{iso-instant}|{uuid}" so we never leak DB internals to clients
 * but still get a stable resume point even when timestamps tie.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class WorkspaceService {

    private static final Set<String> ALLOWED_STATUSES = Set.of("active", "inactive", "suspended");

    private final WorkspaceRepository       workspaceRepository;
    private final WorkspaceAuditLogRepository auditLogRepository;
    /** Migration 024 prep — disable RLS for cross-tenant platform admin reads. */
    private final RlsBypassHelper           rlsBypass;

    @Transactional(readOnly = true)
    public WorkspaceView get(UUID id) {
        Workspace w = workspaceRepository.findById(id)
                .orElseThrow(() -> new WorkspaceNotFoundException("Workspace not found: " + id));
        String industry = workspaceRepository.findIndustryByWorkspaceId(id).orElse(null);
        return new WorkspaceView(
                w.getWorkspaceId(),
                w.getName(),
                w.getPlanCode(),
                industry,
                w.getStatus(),
                w.getCreatedAt(),
                w.getUpdatedAt()
        );
    }

    @Transactional(readOnly = true)
    public WorkspacePage list(String cursor, int limit) {
        Cursor c = Cursor.decode(cursor);
        List<WorkspaceListRow> rows = (c == null)
                ? workspaceRepository.findFirstPage(limit)
                : workspaceRepository.findPageAfter(c.ts(), c.id(), limit);

        List<WorkspaceView> items = rows.stream().map(WorkspaceService::toView).toList();

        // Cursor for the next page = the keyset of the last row, or null when
        // we returned fewer rows than asked for (= reached the end).
        String nextCursor = null;
        if (!items.isEmpty() && items.size() == limit) {
            WorkspaceView tail = items.get(items.size() - 1);
            nextCursor = Cursor.encode(tail.createdAt(), tail.workspaceId());
        }

        long total = workspaceRepository.count();
        return new WorkspacePage(items, nextCursor, total);
    }

    @Transactional
    public WorkspaceView create(String name, String planCode, String industry) {
        if (workspaceRepository.findPlanCode(planCode).isEmpty()) {
            throw new InvalidPlanCodeException("Unknown plan_code: " + planCode);
        }

        Workspace w = new Workspace();
        w.setName(name);
        w.setPlanCode(planCode);
        w.setStatus("active");
        Workspace saved = workspaceRepository.save(w);

        // Industry lives on enterprises, not workspaces — seed the row so the
        // PATCH/GET round-trip surfaces it. F-013 onboarding may later rewrite
        // the enterprise name when an activation key is consumed.
        //
        // Platform admin has no tenant context (no app.current_enterprise_id /
        // app.current_workspace_id) so the isolation_enterprises RLS policy
        // would deny the INSERT. Authorise via admin_bypass_enterprises
        // (added in mig 105) before seeding.
        String returnedIndustry = null;
        if (industry != null && !industry.isBlank()) {
            rlsBypass.disableForTx();
            workspaceRepository.seedEnterprise(saved.getWorkspaceId(), saved.getName(), industry);
            returnedIndustry = industry;
        }

        return new WorkspaceView(
                saved.getWorkspaceId(),
                saved.getName(),
                saved.getPlanCode(),
                returnedIndustry,
                saved.getStatus(),
                saved.getCreatedAt(),
                saved.getUpdatedAt()
        );
    }

    @Transactional
    public WorkspaceView update(UUID id, String name, String planCode, String status) {
        Workspace w = workspaceRepository.findById(id)
                .orElseThrow(() -> new WorkspaceNotFoundException("Workspace not found: " + id));

        if (planCode != null && workspaceRepository.findPlanCode(planCode).isEmpty()) {
            throw new InvalidPlanCodeException("Unknown plan_code: " + planCode);
        }
        if (status != null && !ALLOWED_STATUSES.contains(status)) {
            throw new InvalidStatusException(
                    "status must be one of " + ALLOWED_STATUSES + ", got: " + status);
        }

        if (name      != null) w.setName(name);
        if (planCode  != null) w.setPlanCode(planCode);
        if (status    != null) w.setStatus(status);

        Workspace saved = workspaceRepository.save(w);
        String industry = workspaceRepository.findIndustryByWorkspaceId(id).orElse(null);

        return new WorkspaceView(
                saved.getWorkspaceId(),
                saved.getName(),
                saved.getPlanCode(),
                industry,
                saved.getStatus(),
                saved.getCreatedAt(),
                saved.getUpdatedAt()
        );
    }

    @Transactional
    public WorkspaceView softDelete(UUID id) {
        Workspace w = workspaceRepository.findById(id)
                .orElseThrow(() -> new WorkspaceNotFoundException("Workspace not found: " + id));

        if (!"inactive".equals(w.getStatus())) {
            w.setStatus("inactive");
            workspaceRepository.save(w);
        }
        String industry = workspaceRepository.findIndustryByWorkspaceId(id).orElse(null);

        return new WorkspaceView(
                w.getWorkspaceId(),
                w.getName(),
                w.getPlanCode(),
                industry,
                w.getStatus(),
                w.getCreatedAt(),
                w.getUpdatedAt()
        );
    }

    // =========================================================================
    // Billing summary (F-008)
    //
    // Source of truth = enterprise_monthly_billing (one row per enterprise per
    // billing month, upserted by the unique-billing cron — F-031, not yet
    // wired). When no row exists for the current month yet, we synthesize an
    // empty summary so the UI shows "0/quota" rather than 404.
    //
    // Money columns are NOT in enterprise_monthly_billing (only counts), so
    // we compute base from subscription_plans.price_vnd. Overage cost stays
    // 0 in v1; tiered overage rates land with F-059 (ROI Hybrid Billing).
    // =========================================================================
    @Transactional(readOnly = true)
    public BillingSummary getBillingSummary(UUID workspaceId) {
        // Migration 024 prep — platform admin path that reads
        // enterprise_monthly_billing for the resolved tenant. The query has
        // an explicit WHERE enterprise_id = :eid, but RLS would still kick
        // in once kaori_app loses BYPASSRLS because no app.enterprise_id GUC
        // is set on the platform admin session. Same pattern as
        // PlatformBillingService — disable row_security for this read-only tx.
        rlsBypass.disableForTx();

        Workspace w = workspaceRepository.findById(workspaceId)
                .orElseThrow(() -> new WorkspaceNotFoundException("Workspace not found: " + workspaceId));

        UUID enterpriseId = workspaceRepository.findEnterpriseIdByWorkspaceId(workspaceId)
                .orElseThrow(() -> new EnterpriseNotProvisionedException(
                        "Workspace has no provisioned enterprise yet: " + workspaceId));

        LocalDate today           = LocalDate.now(ZoneOffset.UTC);
        LocalDate billingMonth    = today.withDayOfMonth(1);
        java.sql.Date monthDate   = java.sql.Date.valueOf(billingMonth);

        BillingRow row = workspaceRepository.findBillingForMonth(enterpriseId, monthDate).orElse(null);

        int planQuota = workspaceRepository.findPlanQuota(w.getPlanCode()).orElse(0);
        int uniqueCustomers = row != null && row.getUniqueCustomers() != null ? row.getUniqueCustomers() : 0;
        int quota           = row != null && row.getQuota()           != null ? row.getQuota()           : planQuota;
        int overageUnits    = row != null && row.getOverageCount()    != null ? row.getOverageCount()    : 0;

        double basePriceVnd = workspaceRepository.findPlanPriceVnd(w.getPlanCode()).orElse(0.0);
        // v1: no per-unit overage rate yet — F-059 will add tiered rates by plan.
        double overagePriceVnd = 0.0;
        double totalPriceVnd   = basePriceVnd + overagePriceVnd;

        String status = BillingMath.computeStatus(uniqueCustomers, quota, overageUnits);
        LocalDate nextInvoice = billingMonth.plusMonths(1);

        return new BillingSummary(
                workspaceId,
                w.getPlanCode(),
                billingMonth.toString().substring(0, 7),  // 'YYYY-MM'
                uniqueCustomers,
                quota,
                overageUnits,
                basePriceVnd,
                overagePriceVnd,
                totalPriceVnd,
                BillingMath.WARN_PCT,
                status,
                nextInvoice
        );
    }

    // =========================================================================
    // Audit log (F-008) — append-only via DB rules (migration 011)
    // =========================================================================

    @Transactional(readOnly = true)
    public AuditPage listAudit(UUID workspaceId, String cursor, int limit) {
        // Confirm workspace exists so the FE shows 404 instead of an empty page
        // for typo'd ids.
        if (!workspaceRepository.existsById(workspaceId)) {
            throw new WorkspaceNotFoundException("Workspace not found: " + workspaceId);
        }

        Cursor c = Cursor.decode(cursor);
        List<WorkspaceAuditLog> rows = (c == null)
                ? auditLogRepository.findFirstPage(workspaceId, limit)
                : auditLogRepository.findPageAfter(workspaceId, c.ts(), c.id(), limit);

        List<AuditView> items = rows.stream().map(WorkspaceService::toAuditView).toList();

        String nextCursor = null;
        if (!items.isEmpty() && items.size() == limit) {
            AuditView tail = items.get(items.size() - 1);
            nextCursor = Cursor.encode(tail.createdAt(), tail.eventId());
        }

        long total = auditLogRepository.countByWorkspaceId(workspaceId);
        return new AuditPage(items, nextCursor, total);
    }

    /**
     * Best-effort audit write. Caller is decoupled — failure here is logged
     * but does NOT abort the originating mutation. Callers should pass a
     * fresh transaction context (i.e. invoke from a non-@Transactional path
     * or wrap with @Transactional(propagation = REQUIRES_NEW) if needed).
     */
    public void recordAudit(UUID workspaceId, String eventType,
                            String actorEmail, String actorRole,
                            String resource, String detail, String ipAddress) {
        // Backward-compatible delegate — pre-3.1.b callers (F-008/F-009) don't
        // know the actor UUID, so we record actor_email only and leave
        // actor_id null. New callers use the 8-arg overload below.
        recordAudit(workspaceId, eventType, null,
                actorEmail, actorRole, resource, detail, ipAddress);
    }

    public void recordAudit(UUID workspaceId, String eventType,
                            UUID actorId,
                            String actorEmail, String actorRole,
                            String resource, String detail, String ipAddress) {
        try {
            WorkspaceAuditLog ev = new WorkspaceAuditLog();
            ev.setWorkspaceId(workspaceId);
            ev.setEventType(eventType);
            ev.setActorId(actorId);
            ev.setActorEmail(actorEmail);
            ev.setActorRole(actorRole);
            ev.setResource(resource);
            ev.setDetail(detail);
            ev.setIpAddress(ipAddress);
            auditLogRepository.save(ev);
        } catch (Exception e) {
            log.warn("audit.write_failed workspace={} event={} err={}",
                    workspaceId, eventType, e.getMessage());
        }
    }

    // =========================================================================
    // Mappers
    // =========================================================================

    private static WorkspaceView toView(WorkspaceListRow r) {
        return new WorkspaceView(
                r.getWorkspaceId(),
                r.getName(),
                r.getPlanCode(),
                r.getIndustry(),
                r.getStatus(),
                r.getCreatedAt(),
                r.getUpdatedAt()
        );
    }

    private static AuditView toAuditView(WorkspaceAuditLog ev) {
        return new AuditView(
                ev.getEventId(),
                ev.getEventType(),
                ev.getActorEmail(),
                ev.getActorRole(),
                ev.getResource(),
                ev.getDetail(),
                ev.getIpAddress(),
                ev.getCreatedAt()
        );
    }

    // =========================================================================
    // Cursor codec
    // =========================================================================

    private record Cursor(Instant ts, UUID id) {
        static String encode(Instant ts, UUID id) {
            String raw = ts.toString() + "|" + id.toString();
            return Base64.getUrlEncoder().withoutPadding()
                    .encodeToString(raw.getBytes(StandardCharsets.UTF_8));
        }

        static Cursor decode(String cursor) {
            if (cursor == null || cursor.isBlank()) return null;
            try {
                String raw = new String(
                        Base64.getUrlDecoder().decode(cursor), StandardCharsets.UTF_8);
                int pipe = raw.indexOf('|');
                if (pipe <= 0 || pipe == raw.length() - 1) {
                    throw new InvalidCursorException("Malformed cursor");
                }
                return new Cursor(
                        Instant.parse(raw.substring(0, pipe)),
                        UUID.fromString(raw.substring(pipe + 1))
                );
            } catch (IllegalArgumentException | java.time.format.DateTimeParseException e) {
                throw new InvalidCursorException("Malformed cursor: " + e.getMessage());
            }
        }
    }

    // =========================================================================
    // Return / value types — kept identical to T-F008-01 stub so the controller
    // contract is unchanged.
    // =========================================================================

    public record WorkspaceView(
            UUID    workspaceId,
            String  name,
            String  planCode,
            String  industry,
            String  status,
            Instant createdAt,
            Instant updatedAt
    ) {}

    public record WorkspacePage(
            List<WorkspaceView> items,
            String              nextCursor,
            long                total
    ) {}

    public record BillingSummary(
            UUID      workspaceId,
            String    planCode,
            String    billingMonth,         // 'YYYY-MM'
            int       uniqueCustomers,
            int       quota,
            int       overageUnits,
            double    baseAmountVnd,
            double    overageAmountVnd,
            double    totalAmountVnd,
            int       quotaWarnAtPct,
            String    status,               // normal | warn | critical | overage
            LocalDate nextInvoiceDate
    ) {}

    public record AuditView(
            UUID    eventId,
            String  eventType,
            String  actorEmail,
            String  actorRole,
            String  resource,
            String  detail,
            String  ipAddress,
            Instant createdAt
    ) {}

    public record AuditPage(
            List<AuditView> items,
            String          nextCursor,
            long            total
    ) {}

    // =========================================================================
    // Exceptions
    // =========================================================================

    public static class WorkspaceNotFoundException extends RuntimeException {
        public WorkspaceNotFoundException(String msg) { super(msg); }
    }

    public static class InvalidPlanCodeException extends RuntimeException {
        public InvalidPlanCodeException(String msg) { super(msg); }
    }

    public static class InvalidStatusException extends RuntimeException {
        public InvalidStatusException(String msg) { super(msg); }
    }

    public static class InvalidCursorException extends RuntimeException {
        public InvalidCursorException(String msg) { super(msg); }
    }

    public static class EnterpriseNotProvisionedException extends RuntimeException {
        public EnterpriseNotProvisionedException(String msg) { super(msg); }
    }
}
