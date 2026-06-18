package com.kaorisystem.auth.service;

import com.kaorisystem.auth.repository.BillingAggregationRepository;
import com.kaorisystem.auth.repository.BillingAggregationRepository.OverviewRow;
import com.kaorisystem.auth.repository.EnterpriseBillingProjection;
import com.kaorisystem.auth.repository.WorkspaceRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.ZoneOffset;
import java.time.format.DateTimeParseException;
import java.util.Base64;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/**
 * F-011 — platform-level billing aggregation.
 *
 * <p>Reads the same physical data as F-008 (enterprise_monthly_billing +
 * subscription_plans). Status classification is centralised in
 * {@link BillingMath} so dashboard colours match per-workspace tabs.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class PlatformBillingService {

    /** Hard ceiling so /export and /quota cannot run away on us. */
    private static final int EXPORT_MAX_ROWS = 5_000;

    private static final Set<String> ALLOWED_STATUSES =
            Set.of("normal", "warn", "critical", "overage");

    private final BillingAggregationRepository billingRepo;
    private final WorkspaceRepository          workspaceRepo;   // for plan_code existence check
    /** Migration 024 prep — disable RLS for this service's cross-tenant aggregation reads. */
    private final RlsBypassHelper              rlsBypass;

    // =========================================================================
    // /overview
    // =========================================================================

    @Transactional(readOnly = true)
    public Overview getOverview() {
        // Migration 024 prep — every method on this service aggregates across
        // every tenant's enterprise_monthly_billing row. Once kaori_app loses
        // BYPASSRLS, RLS would silently filter the JOIN to zero rows. Flipping
        // row_security off for this transaction keeps the platform admin view
        // working without forcing a per-tenant loop.
        rlsBypass.disableForTx();
        YearMonth ym = currentMonth();
        OverviewRow p = billingRepo.findOverview(toSqlDate(ym));

        long base = Math.round(p.totalBaseAmountVnd());
        // v1: per-unit overage rate is 0 until F-059 lands.
        long overageAmt = 0L;

        return new Overview(
                ym.toString(),
                p.enterpriseCount(),
                new StatusCounts(
                        p.normalCount(), p.warnCount(),
                        p.criticalCount(), p.overageCount()
                ),
                p.totalUniqueCustomers(),
                p.totalQuota(),
                p.totalOverageUnits(),
                base,
                overageAmt,
                base + overageAmt,
                ym.atDay(1).plusMonths(1),        // next_invoice_date
                p.lastAggregatedAt(),
                p.staleCount()
        );
    }

    // =========================================================================
    // /enterprises/{id}
    // =========================================================================

    @Transactional(readOnly = true)
    public EnterpriseSummary getEnterprise(UUID enterpriseId) {
        rlsBypass.disableForTx();   // platform admin path — see getOverview() for rationale
        YearMonth ym = currentMonth();
        EnterpriseBillingProjection row = billingRepo.findOne(enterpriseId, toSqlDate(ym))
                .orElseThrow(() -> new EnterpriseNotFoundException(
                        "Enterprise not found: " + enterpriseId));
        return toSummary(row, ym);
    }

    // =========================================================================
    // /quota — paginated + filterable
    // =========================================================================

    @Transactional(readOnly = true)
    public QuotaPage listQuota(String planFilter, String statusFilter,
                                String cursor, int limit) {
        rlsBypass.disableForTx();   // platform admin path — see getOverview() for rationale
        String plan   = normalisePlan(planFilter);     // null on blank
        String status = normaliseStatus(statusFilter); // null on blank
        Cursor c      = Cursor.decode(cursor);
        YearMonth ym  = currentMonth();
        java.sql.Date month = toSqlDate(ym);

        List<EnterpriseBillingProjection> rows = billingRepo.findPage(
                month, plan, status,
                c == null ? null : c.ts(),
                c == null ? null : c.id(),
                limit);

        List<QuotaRow> items = rows.stream().map(r -> toQuotaRow(r, ym)).toList();

        String nextCursor = null;
        if (!items.isEmpty() && items.size() == limit) {
            EnterpriseBillingProjection tail = rows.get(rows.size() - 1);
            nextCursor = Cursor.encode(tail.getCreatedAt(), tail.getEnterpriseId());
        }

        long total = billingRepo.countMatching(month, plan, status);
        return new QuotaPage(items, nextCursor, total);
    }

    // =========================================================================
    // /export — full rows, capped, for CSV download
    // =========================================================================

    @Transactional(readOnly = true)
    public ExportResult export(String monthFilter, String planFilter, String statusFilter) {
        rlsBypass.disableForTx();   // platform admin path — see getOverview() for rationale
        YearMonth ym  = parseMonth(monthFilter);  // throws InvalidMonthException on bad input
        String plan   = normalisePlan(planFilter);
        String status = normaliseStatus(statusFilter);

        List<EnterpriseBillingProjection> rows = billingRepo.findPage(
                toSqlDate(ym), plan, status,
                null, null, EXPORT_MAX_ROWS);

        List<QuotaRow> items = rows.stream().map(r -> toQuotaRow(r, ym)).toList();
        return new ExportResult(ym.toString(), items, rows.size() == EXPORT_MAX_ROWS);
    }

    // =========================================================================
    // Filter normalisation — exposed for unit-test reach
    // =========================================================================

    private String normalisePlan(String plan) {
        if (plan == null || plan.isBlank()) return null;
        String trimmed = plan.trim().toUpperCase();
        if (workspaceRepo.findPlanCode(trimmed).isEmpty()) {
            throw new WorkspaceService.InvalidPlanCodeException(
                    "Unknown plan_code: " + trimmed);
        }
        return trimmed;
    }

    private String normaliseStatus(String status) {
        if (status == null || status.isBlank()) return null;
        String trimmed = status.trim().toLowerCase();
        if (!ALLOWED_STATUSES.contains(trimmed)) {
            throw new InvalidStatusException(
                    "status must be one of " + ALLOWED_STATUSES + ", got: " + trimmed);
        }
        return trimmed;
    }

    /** Empty / null → current month. {@code YYYY-MM} only — no day allowed. */
    private static YearMonth parseMonth(String month) {
        if (month == null || month.isBlank()) return currentMonth();
        try {
            return YearMonth.parse(month.trim());
        } catch (DateTimeParseException e) {
            throw new InvalidMonthException(
                    "month must be in YYYY-MM format, got: " + month);
        }
    }

    private static YearMonth currentMonth() {
        return YearMonth.from(LocalDate.now(ZoneOffset.UTC));
    }

    private static java.sql.Date toSqlDate(YearMonth ym) {
        return java.sql.Date.valueOf(ym.atDay(1));
    }

    // =========================================================================
    // Mapping helpers
    // =========================================================================

    private static EnterpriseSummary toSummary(EnterpriseBillingProjection r, YearMonth ym) {
        int used    = nz(r.getUniqueCustomers());
        int quota   = nz(r.getQuota());
        int overage = nz(r.getOverageUnits());
        double base = r.getBasePriceVnd() == null ? 0.0 : r.getBasePriceVnd();
        double overageAmt = 0.0;
        return new EnterpriseSummary(
                r.getEnterpriseId(),
                r.getEnterpriseName(),
                r.getWorkspaceId(),
                r.getPlanCode(),
                ym.toString(),
                used,
                quota,
                overage,
                base,
                overageAmt,
                base + overageAmt,
                BillingMath.WARN_PCT,
                BillingMath.computeStatus(used, quota, overage),
                ym.atDay(1).plusMonths(1)
        );
    }

    private static QuotaRow toQuotaRow(EnterpriseBillingProjection r, YearMonth ym) {
        int used    = nz(r.getUniqueCustomers());
        int quota   = nz(r.getQuota());
        int overage = nz(r.getOverageUnits());
        double base = r.getBasePriceVnd() == null ? 0.0 : r.getBasePriceVnd();
        double pct  = quota > 0 ? Math.round(used * 10000.0 / quota) / 100.0 : 0.0;
        return new QuotaRow(
                r.getEnterpriseId(),
                r.getEnterpriseName(),
                r.getWorkspaceId(),
                r.getPlanCode(),
                ym.toString(),
                used,
                quota,
                pct,
                overage,
                base,
                BillingMath.computeStatus(used, quota, overage)
        );
    }

    private static int nz(Integer i) { return i == null ? 0 : i; }

    // =========================================================================
    // Cursor — same encoding as WorkspaceService.Cursor (kept inline so the
    // F-008 service is not touched by F-011).
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
            } catch (IllegalArgumentException | DateTimeParseException e) {
                throw new InvalidCursorException("Malformed cursor: " + e.getMessage());
            }
        }
    }

    // =========================================================================
    // Return + exception types
    // =========================================================================

    public record StatusCounts(long normal, long warn, long critical, long overage) {}

    public record Overview(
            String       billingMonth,
            long         enterpriseCount,
            StatusCounts byStatus,
            long         totalUniqueCustomers,
            long         totalQuota,
            long         totalOverageUnits,
            long         totalBaseAmountVnd,
            long         totalOverageAmountVnd,
            long         totalRevenueVnd,
            LocalDate    nextInvoiceDate,
            /** Sprint 7 PR C — F-031 cron health surfacing. */
            Instant      lastAggregatedAt,
            long         staleEnterpriseCount
    ) {}

    public record EnterpriseSummary(
            UUID      enterpriseId,
            String    enterpriseName,
            UUID      workspaceId,
            String    planCode,
            String    billingMonth,
            int       uniqueCustomers,
            int       quota,
            int       overageUnits,
            double    baseAmountVnd,
            double    overageAmountVnd,
            double    totalAmountVnd,
            int       quotaWarnAtPct,
            String    status,
            LocalDate nextInvoiceDate
    ) {}

    public record QuotaRow(
            UUID    enterpriseId,
            String  enterpriseName,
            UUID    workspaceId,
            String  planCode,
            String  billingMonth,
            int     uniqueCustomers,
            int     quota,
            double  usagePct,
            int     overageUnits,
            double  totalAmountVnd,
            String  status
    ) {}

    public record QuotaPage(List<QuotaRow> items, String nextCursor, long total) {}

    public record ExportResult(String billingMonth, List<QuotaRow> rows, boolean truncated) {}

    public static class EnterpriseNotFoundException extends RuntimeException {
        public EnterpriseNotFoundException(String msg) { super(msg); }
    }
    public static class InvalidStatusException extends RuntimeException {
        public InvalidStatusException(String msg) { super(msg); }
    }
    public static class InvalidMonthException extends RuntimeException {
        public InvalidMonthException(String msg) { super(msg); }
    }
    public static class InvalidCursorException extends RuntimeException {
        public InvalidCursorException(String msg) { super(msg); }
    }
}
