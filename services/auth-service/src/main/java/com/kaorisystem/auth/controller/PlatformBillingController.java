package com.kaorisystem.auth.controller;

import com.kaorisystem.auth.service.BillingAggregationService;
import com.kaorisystem.auth.service.BillingAggregationService.BatchResult;
import com.kaorisystem.auth.service.PlatformBillingService;
import com.kaorisystem.auth.service.PlatformBillingService.EnterpriseNotFoundException;
import com.kaorisystem.auth.service.PlatformBillingService.EnterpriseSummary;
import com.kaorisystem.auth.service.PlatformBillingService.ExportResult;
import com.kaorisystem.auth.service.PlatformBillingService.InvalidCursorException;
import com.kaorisystem.auth.service.PlatformBillingService.InvalidMonthException;
import com.kaorisystem.auth.service.PlatformBillingService.InvalidStatusException;
import com.kaorisystem.auth.service.PlatformBillingService.Overview;
import com.kaorisystem.auth.service.PlatformBillingService.QuotaPage;
import com.kaorisystem.auth.service.PlatformBillingService.QuotaRow;
import com.kaorisystem.auth.service.WorkspaceService.InvalidPlanCodeException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * F-011 — Platform billing dashboard endpoints.
 *
 * <pre>
 *   GET /api/v1/platform/billing/overview
 *   GET /api/v1/platform/billing/enterprises/{id}
 *   GET /api/v1/platform/billing/quota?plan=&status=&cursor=&limit=
 *   GET /api/v1/platform/billing/export?month=&plan=&status=
 * </pre>
 *
 * Reuses the same physical data as F-008's {@code /workspaces/{id}/billing}
 * (enterprise_monthly_billing + subscription_plans). Status classification
 * comes from {@link com.kaorisystem.auth.service.BillingMath}, shared with
 * F-008 — UI badges agree across portals.
 *
 * Errors follow RFC 7807 (K-14) with the same {@code problem()} envelope
 * used elsewhere in this module.
 */
@RestController
@RequestMapping("/api/v1/platform/billing")
@RequiredArgsConstructor
@Slf4j
public class PlatformBillingController {

    private static final int DEFAULT_LIMIT = 50;
    private static final int MAX_LIMIT     = 500;

    /** UTF-8 BOM so Excel on Windows opens Vietnamese names without garbling. */
    private static final byte[] UTF8_BOM = { (byte) 0xEF, (byte) 0xBB, (byte) 0xBF };

    private final PlatformBillingService     billingService;
    private final BillingAggregationService  aggregationService;  // F-031
    private final com.kaorisystem.auth.service.JobLeaseService leaseService;  // B1 PR #2 #8

    // =========================================================================
    // POST /aggregate-now  (F-031 — manual trigger for ops + smoke tests)
    //
    // Same code path as the daily 02:00 ICT cron — useful when a tenant
    // hits a quota wall and ops needs the dashboard to reflect reality
    // before tomorrow morning. SUPER_ADMIN gating happens at the gateway
    // (/api/v1/platform/** matcher in SecurityConfig).
    //
    // Phase 2 #8 — wrapped in the same lease as BillingAggregationJob so
    // a manual click while the 02:00 cron is mid-run can never double-aggregate.
    // The lease's partial unique index makes "two runs concurrently" a DB-
    // enforced impossibility; the loser returns 409 Conflict.
    // =========================================================================
    @PostMapping("/aggregate-now")
    public ResponseEntity<?> aggregateNow() {
        java.util.concurrent.atomic.AtomicReference<BatchResult> resultRef =
                new java.util.concurrent.atomic.AtomicReference<>();
        com.kaorisystem.auth.service.JobLeaseService.AcquireOutcome outcome =
                leaseService.runWithLease(
                        "billing_aggregation",
                        java.time.Duration.ofHours(1),
                        () -> resultRef.set(aggregationService.aggregateCurrentMonth()));

        if (outcome == com.kaorisystem.auth.service.JobLeaseService.AcquireOutcome.SKIPPED) {
            // Cron (or another manual call) is already mid-run. RFC 7807 envelope
            // so the FE error banner reads consistently with our other 4xx paths.
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("type",   "/docs/errors/job-already-running");
            body.put("title",  "Aggregation already in progress");
            body.put("status", 409);
            body.put("code",   com.kaorisystem.auth.common.ErrorCodes.JOB_ALREADY_RUNNING);
            body.put("detail", "billing_aggregation is currently held by another instance "
                            + "or the daily 02:00 ICT cron. Wait for it to finish, then retry.");
            return ResponseEntity.status(409)
                    .header("Content-Type", "application/problem+json")
                    .body(body);
        }

        BatchResult r = resultRef.get();
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("billing_month",     r.billingMonth().toString());
        data.put("enterprise_count",  r.enterpriseCount());
        data.put("success_count",     r.successCount());
        data.put("failure_count",     r.failureCount());
        return ResponseEntity.ok(Map.of("data", data));
    }

    // =========================================================================
    // GET /overview
    // =========================================================================
    @GetMapping("/overview")
    public ResponseEntity<?> overview() {
        Overview o = billingService.getOverview();

        Map<String, Object> byStatus = new LinkedHashMap<>();
        byStatus.put("normal",   o.byStatus().normal());
        byStatus.put("warn",     o.byStatus().warn());
        byStatus.put("critical", o.byStatus().critical());
        byStatus.put("overage",  o.byStatus().overage());

        Map<String, Object> data = new LinkedHashMap<>();
        data.put("billing_month",             o.billingMonth());
        data.put("enterprise_count",          o.enterpriseCount());
        data.put("by_status",                 byStatus);
        data.put("total_unique_customers",    o.totalUniqueCustomers());
        data.put("total_quota",               o.totalQuota());
        data.put("total_overage_units",       o.totalOverageUnits());
        data.put("total_base_amount_vnd",     o.totalBaseAmountVnd());
        data.put("total_overage_amount_vnd",  o.totalOverageAmountVnd());
        data.put("total_revenue_vnd",         o.totalRevenueVnd());
        data.put("next_invoice_date",         o.nextInvoiceDate().toString());

        // Sprint 7 PR C — F-031 cron health surface for SUPER_ADMIN.
        data.put("last_aggregated_at",        o.lastAggregatedAt() == null
                ? null : o.lastAggregatedAt().toString());
        data.put("stale_enterprise_count",    o.staleEnterpriseCount());

        return ResponseEntity.ok(Map.of("data", data));
    }

    // =========================================================================
    // GET /enterprises/{id}
    // =========================================================================
    @GetMapping("/enterprises/{id}")
    public ResponseEntity<?> getEnterprise(@PathVariable("id") String idStr) {
        UUID id;
        try {
            id = UUID.fromString(idStr);
        } catch (IllegalArgumentException e) {
            return problem(400, "/docs/errors/invalid-id", "Invalid enterprise ID",
                    "enterprise_id must be a valid UUID");
        }
        try {
            EnterpriseSummary s = billingService.getEnterprise(id);
            return ResponseEntity.ok(Map.of("data", toEnterpriseJson(s)));
        } catch (EnterpriseNotFoundException e) {
            return problem(404, "/docs/errors/enterprise-not-found",
                    "Enterprise not found", e.getMessage());
        }
    }

    // =========================================================================
    // GET /quota
    // =========================================================================
    @GetMapping("/quota")
    public ResponseEntity<?> listQuota(
            @RequestParam(value = "plan",   required = false) String plan,
            @RequestParam(value = "status", required = false) String status,
            @RequestParam(value = "cursor", required = false) String cursor,
            @RequestParam(value = "limit",  required = false) Integer limit) {

        int effectiveLimit = (limit == null) ? DEFAULT_LIMIT : limit;
        if (effectiveLimit < 1 || effectiveLimit > MAX_LIMIT) {
            return problem(400, "/docs/errors/invalid-request", "Invalid limit",
                    "limit must be between 1 and " + MAX_LIMIT);
        }

        try {
            QuotaPage page = billingService.listQuota(plan, status, cursor, effectiveLimit);

            Map<String, Object> meta = new LinkedHashMap<>();
            meta.put("cursor", page.nextCursor());
            meta.put("total",  page.total());

            return ResponseEntity.ok(Map.of(
                    "data", page.items().stream().map(PlatformBillingController::toQuotaJson).toList(),
                    "meta", meta
            ));
        } catch (InvalidPlanCodeException e) {
            return problem(400, "/docs/errors/invalid-plan-code", "Invalid plan_code", e.getMessage());
        } catch (InvalidStatusException e) {
            return problem(400, "/docs/errors/invalid-status", "Invalid status", e.getMessage());
        } catch (InvalidCursorException e) {
            return problem(400, "/docs/errors/invalid-cursor", "Invalid cursor", e.getMessage());
        }
    }

    // =========================================================================
    // GET /export → text/csv with UTF-8 BOM
    // =========================================================================
    @GetMapping("/export")
    public ResponseEntity<?> export(
            @RequestParam(value = "month",  required = false) String month,
            @RequestParam(value = "plan",   required = false) String plan,
            @RequestParam(value = "status", required = false) String status) {

        ExportResult res;
        try {
            res = billingService.export(month, plan, status);
        } catch (InvalidMonthException e) {
            return problem(400, "/docs/errors/invalid-month", "Invalid month", e.getMessage());
        } catch (InvalidPlanCodeException e) {
            return problem(400, "/docs/errors/invalid-plan-code", "Invalid plan_code", e.getMessage());
        } catch (InvalidStatusException e) {
            return problem(400, "/docs/errors/invalid-status", "Invalid status", e.getMessage());
        }

        String csv = renderCsv(res.rows());
        byte[] body = prependBom(csv);

        HttpHeaders h = new HttpHeaders();
        h.setContentType(new MediaType("text", "csv", StandardCharsets.UTF_8));
        h.setContentDispositionFormData("attachment",
                "kaori-billing-" + res.billingMonth() + ".csv");
        h.setContentLength(body.length);
        if (res.truncated()) {
            // Surface truncation so a client can decide whether to fetch the next slice.
            h.add("X-Truncated", "true");
        }
        return new ResponseEntity<>(body, h, 200);
    }

    // =========================================================================
    // CSV
    // =========================================================================

    private static final String CSV_HEADER =
            "enterprise_id,enterprise_name,plan_code,billing_month,"
          + "unique_customers,quota,usage_pct,overage_units,"
          + "base_amount_vnd,overage_amount_vnd,total_amount_vnd,status";

    private static String renderCsv(List<QuotaRow> rows) {
        StringBuilder sb = new StringBuilder(64 + rows.size() * 128);
        sb.append(CSV_HEADER).append("\r\n");           // CRLF — matches RFC 4180 + Excel
        for (QuotaRow r : rows) {
            // overage_amount_vnd stays 0 in v1 (matches /enterprises/{id} contract).
            double overageAmt = 0.0;
            sb.append(r.enterpriseId()).append(',')
              .append(csvEscape(r.enterpriseName())).append(',')
              .append(r.planCode()).append(',')
              .append(r.billingMonth()).append(',')
              .append(r.uniqueCustomers()).append(',')
              .append(r.quota()).append(',')
              .append(r.usagePct()).append(',')
              .append(r.overageUnits()).append(',')
              .append(money(r.totalAmountVnd() - overageAmt)).append(',')
              .append(money(overageAmt)).append(',')
              .append(money(r.totalAmountVnd())).append(',')
              .append(r.status())
              .append("\r\n");
        }
        return sb.toString();
    }

    /** RFC 4180: wrap in quotes if contains comma / quote / CR / LF; double up internal quotes. */
    private static String csvEscape(String s) {
        if (s == null) return "";
        boolean needs = s.indexOf(',') >= 0 || s.indexOf('"') >= 0
                     || s.indexOf('\n') >= 0 || s.indexOf('\r') >= 0;
        if (!needs) return s;
        return "\"" + s.replace("\"", "\"\"") + "\"";
    }

    private static String money(double v) {
        // Whole VND with .00 for spreadsheet sanity; locale-independent (no thousands sep).
        return String.format(java.util.Locale.ROOT, "%.2f", v);
    }

    private static byte[] prependBom(String csv) {
        byte[] body = csv.getBytes(StandardCharsets.UTF_8);
        byte[] out  = new byte[UTF8_BOM.length + body.length];
        System.arraycopy(UTF8_BOM, 0, out, 0, UTF8_BOM.length);
        System.arraycopy(body,    0, out, UTF8_BOM.length, body.length);
        return out;
    }

    // =========================================================================
    // JSON mappers + RFC 7807 helper
    // =========================================================================

    private static Map<String, Object> toEnterpriseJson(EnterpriseSummary s) {
        Map<String, Object> j = new LinkedHashMap<>();
        j.put("enterprise_id",      s.enterpriseId());
        j.put("enterprise_name",    s.enterpriseName());
        j.put("workspace_id",       s.workspaceId());
        j.put("plan_code",          s.planCode());
        j.put("billing_month",      s.billingMonth());
        j.put("unique_customers",   s.uniqueCustomers());
        j.put("quota",              s.quota());
        j.put("overage_units",      s.overageUnits());
        j.put("base_amount_vnd",    s.baseAmountVnd());
        j.put("overage_amount_vnd", s.overageAmountVnd());
        j.put("total_amount_vnd",   s.totalAmountVnd());
        j.put("quota_warn_at_pct",  s.quotaWarnAtPct());
        j.put("status",             s.status());
        j.put("next_invoice_date",  s.nextInvoiceDate() == null ? null : s.nextInvoiceDate().toString());
        return j;
    }

    private static Map<String, Object> toQuotaJson(QuotaRow r) {
        Map<String, Object> j = new LinkedHashMap<>();
        j.put("enterprise_id",     r.enterpriseId());
        j.put("enterprise_name",   r.enterpriseName());
        j.put("workspace_id",      r.workspaceId());
        j.put("plan_code",         r.planCode());
        j.put("unique_customers",  r.uniqueCustomers());
        j.put("quota",             r.quota());
        j.put("usage_pct",         r.usagePct());
        j.put("overage_units",     r.overageUnits());
        j.put("status",            r.status());
        j.put("total_amount_vnd",  r.totalAmountVnd());
        return j;
    }

    private static ResponseEntity<Map<String, Object>> problem(
            int status, String type, String title, String detail) {
        return ResponseEntity.status(status).body(Map.of(
                "type",   type,
                "title",  title,
                "status", status,
                "detail", detail
        ));
    }
}
