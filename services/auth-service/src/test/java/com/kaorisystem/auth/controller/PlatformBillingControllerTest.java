package com.kaorisystem.auth.controller;

import com.kaorisystem.auth.service.PlatformBillingService;
import com.kaorisystem.auth.service.PlatformBillingService.EnterpriseNotFoundException;
import com.kaorisystem.auth.service.PlatformBillingService.EnterpriseSummary;
import com.kaorisystem.auth.service.PlatformBillingService.ExportResult;
import com.kaorisystem.auth.service.PlatformBillingService.InvalidMonthException;
import com.kaorisystem.auth.service.PlatformBillingService.InvalidStatusException;
import com.kaorisystem.auth.service.PlatformBillingService.Overview;
import com.kaorisystem.auth.service.PlatformBillingService.QuotaPage;
import com.kaorisystem.auth.service.PlatformBillingService.QuotaRow;
import com.kaorisystem.auth.service.PlatformBillingService.StatusCounts;
import com.kaorisystem.auth.service.WorkspaceService.InvalidPlanCodeException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.web.servlet.MockMvc;

import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.hasSize;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.willThrow;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Web-layer slice for the F-011 platform-billing endpoints. Verifies HTTP
 * shape, RFC 7807 errors, and that the CSV export is prefixed with a
 * UTF-8 BOM (per the Vietnamese Excel-compat tweak).
 */
@WebMvcTest(controllers = PlatformBillingController.class,
            excludeAutoConfiguration = {
                org.springframework.boot.autoconfigure.security.servlet.SecurityAutoConfiguration.class
            })
@DisplayName("PlatformBillingController — REST contract")
class PlatformBillingControllerTest {

    @Autowired private MockMvc mockMvc;
    @MockBean  private PlatformBillingService billingService;
    /** F-031 — added as a constructor dependency on PlatformBillingController. */
    @MockBean  private com.kaorisystem.auth.service.BillingAggregationService aggregationService;
    /** B1 PR #2 — POST /aggregate-now wraps aggregationService in a job-lease
     *  guard so manual ops triggers can't race the 02:00 cron. The controller
     *  now takes JobLeaseService as a constructor dep. */
    @MockBean  private com.kaorisystem.auth.service.JobLeaseService leaseService;

    // -------------------------------------------------------------------------
    // GET /overview
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("GET /overview — happy path")
    void overview_happyPath() throws Exception {
        java.time.Instant now = java.time.Instant.parse("2026-04-27T02:01:23Z");
        given(billingService.getOverview()).willReturn(new Overview(
                "2026-04", 5,
                new StatusCounts(2, 1, 1, 1),
                3500, 8000, 120,
                10_000_000, 0, 10_000_000,
                LocalDate.parse("2026-05-01"),
                now, 0L));

        mockMvc.perform(get("/api/v1/platform/billing/overview"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.billing_month").value("2026-04"))
                .andExpect(jsonPath("$.data.enterprise_count").value(5))
                .andExpect(jsonPath("$.data.by_status.normal").value(2))
                .andExpect(jsonPath("$.data.by_status.overage").value(1))
                .andExpect(jsonPath("$.data.total_revenue_vnd").value(10_000_000))
                .andExpect(jsonPath("$.data.next_invoice_date").value("2026-05-01"))
                .andExpect(jsonPath("$.data.last_aggregated_at").value(now.toString()))
                .andExpect(jsonPath("$.data.stale_enterprise_count").value(0));
    }

    // -------------------------------------------------------------------------
    // GET /enterprises/{id}
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("GET /enterprises/{id} — happy path")
    void getEnterprise_happyPath() throws Exception {
        UUID eid = UUID.randomUUID();
        UUID wid = UUID.randomUUID();
        given(billingService.getEnterprise(eid)).willReturn(new EnterpriseSummary(
                eid, "ABC Corp", wid, "BUSINESS", "2026-04",
                1820, 2000, 0, 1_490_000.0, 0.0, 1_490_000.0,
                80, "warn", LocalDate.parse("2026-05-01")));

        mockMvc.perform(get("/api/v1/platform/billing/enterprises/" + eid))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.enterprise_id").value(eid.toString()))
                .andExpect(jsonPath("$.data.workspace_id").value(wid.toString()))
                .andExpect(jsonPath("$.data.plan_code").value("BUSINESS"))
                .andExpect(jsonPath("$.data.status").value("warn"))
                .andExpect(jsonPath("$.data.quota_warn_at_pct").value(80))
                .andExpect(jsonPath("$.data.next_invoice_date").value("2026-05-01"));
    }

    @Test
    @DisplayName("GET /enterprises/{id} — invalid UUID returns 400")
    void getEnterprise_invalidUuid() throws Exception {
        mockMvc.perform(get("/api/v1/platform/billing/enterprises/not-a-uuid"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.title").value("Invalid enterprise ID"));
    }

    @Test
    @DisplayName("GET /enterprises/{id} — unknown id returns 404 with RFC 7807")
    void getEnterprise_notFound() throws Exception {
        UUID eid = UUID.randomUUID();
        willThrow(new EnterpriseNotFoundException("not found"))
                .given(billingService).getEnterprise(eid);

        mockMvc.perform(get("/api/v1/platform/billing/enterprises/" + eid))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.title").value("Enterprise not found"))
                .andExpect(jsonPath("$.status").value(404));
    }

    // -------------------------------------------------------------------------
    // GET /quota
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("GET /quota — happy path with filters and meta")
    void listQuota_happyPath() throws Exception {
        UUID eid = UUID.randomUUID();
        UUID wid = UUID.randomUUID();
        QuotaRow row = new QuotaRow(eid, "ABC", wid, "BUSINESS", "2026-04",
                1820, 2000, 91.0, 0, 1_490_000.0, "warn");
        given(billingService.listQuota(eq("BUSINESS"), eq("warn"), isNull(), anyInt()))
                .willReturn(new QuotaPage(List.of(row), null, 1L));

        mockMvc.perform(get("/api/v1/platform/billing/quota")
                        .param("plan",   "BUSINESS")
                        .param("status", "warn"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(1)))
                .andExpect(jsonPath("$.data[0].enterprise_name").value("ABC"))
                .andExpect(jsonPath("$.data[0].usage_pct").value(91.0))
                .andExpect(jsonPath("$.data[0].status").value("warn"))
                .andExpect(jsonPath("$.meta.total").value(1));
    }

    @Test
    @DisplayName("GET /quota — bad limit returns 400")
    void listQuota_badLimit() throws Exception {
        mockMvc.perform(get("/api/v1/platform/billing/quota").param("limit", "0"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.title").value("Invalid limit"));
    }

    @Test
    @DisplayName("GET /quota — unknown plan filter returns 400")
    void listQuota_unknownPlan() throws Exception {
        willThrow(new InvalidPlanCodeException("Unknown plan_code: NOPE"))
                .given(billingService).listQuota(anyString(), any(), any(), anyInt());
        mockMvc.perform(get("/api/v1/platform/billing/quota").param("plan", "NOPE"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.title").value("Invalid plan_code"));
    }

    @Test
    @DisplayName("GET /quota — bad status filter returns 400")
    void listQuota_badStatus() throws Exception {
        willThrow(new InvalidStatusException("status must be one of [normal, warn, critical, overage]"))
                .given(billingService).listQuota(any(), anyString(), any(), anyInt());
        mockMvc.perform(get("/api/v1/platform/billing/quota").param("status", "wrong"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.title").value("Invalid status"));
    }

    // -------------------------------------------------------------------------
    // GET /export — UTF-8 BOM, CSV body, attachment header
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("GET /export — CSV body has UTF-8 BOM + Content-Disposition")
    void export_csvWithBom() throws Exception {
        UUID eid = UUID.randomUUID();
        UUID wid = UUID.randomUUID();
        QuotaRow row = new QuotaRow(eid, "Công ty TNHH ABC", wid, "BUSINESS",
                "2026-04", 100, 1000, 10.0, 0, 1_490_000.0, "normal");
        given(billingService.export(any(), any(), any()))
                .willReturn(new ExportResult("2026-04", List.of(row), false));

        byte[] body = mockMvc.perform(get("/api/v1/platform/billing/export"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith("text/csv"))
                .andExpect(header().string("Content-Disposition",
                        org.hamcrest.Matchers.containsString("kaori-billing-2026-04.csv")))
                .andReturn().getResponse().getContentAsByteArray();

        // Bytes 0-2 must be the UTF-8 BOM
        assertThat(body[0]).isEqualTo((byte) 0xEF);
        assertThat(body[1]).isEqualTo((byte) 0xBB);
        assertThat(body[2]).isEqualTo((byte) 0xBF);

        // Body (after BOM) must include the CSV header row + data row
        String csv = new String(body, 3, body.length - 3, java.nio.charset.StandardCharsets.UTF_8);
        assertThat(csv)
                .startsWith("enterprise_id,enterprise_name,plan_code,billing_month,")
                .contains("Công ty TNHH ABC")
                .contains("BUSINESS")
                .contains("normal");
    }

    @Test
    @DisplayName("GET /export — invalid month returns 400 RFC 7807")
    void export_invalidMonth() throws Exception {
        willThrow(new InvalidMonthException("month must be in YYYY-MM format, got: 2026"))
                .given(billingService).export(eq("2026"), any(), any());
        mockMvc.perform(get("/api/v1/platform/billing/export").param("month", "2026"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.title").value("Invalid month"));
    }

    @Test
    @DisplayName("GET /export — truncation surfaces X-Truncated header")
    void export_truncated() throws Exception {
        given(billingService.export(any(), any(), any()))
                .willReturn(new ExportResult("2026-04", List.of(), true));
        mockMvc.perform(get("/api/v1/platform/billing/export"))
                .andExpect(status().isOk())
                .andExpect(header().string("X-Truncated", "true"));
    }
}
