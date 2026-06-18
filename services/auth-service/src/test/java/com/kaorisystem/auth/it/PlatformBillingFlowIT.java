package com.kaorisystem.auth.it;

import com.fasterxml.jackson.databind.JsonNode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MvcResult;

import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.ZoneOffset;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * E2E flow against real Postgres for the F-011 platform billing endpoints.
 *
 * <p>Strategy: seed three workspaces (TRIAL/BUSINESS/ENTERPRISE) with unique
 * names so their enterprises can be picked out of any pre-existing test data,
 * then upsert {@code enterprise_monthly_billing} rows that put each one into
 * a different status bucket (normal / warn / overage). Lookups by enterprise_id
 * give a clean assertion target; aggregate endpoints are checked with
 * lower-bound asserts so other ITs running in the same DB don't break us.
 */
@DisplayName("E2E — Platform billing /overview /enterprises/{id} /quota /export")
class PlatformBillingFlowIT extends AbstractIntegrationIT {

    @Autowired private JdbcTemplate jdbc;

    private final String runId = UUID.randomUUID().toString().substring(0, 8);

    private String entA, entB, entC; // enterprise_ids
    private String wsA,  wsB,  wsC;  // workspace_ids

    @BeforeEach
    void seedFixture() throws Exception {
        wsA = createWorkspaceWithEnterprise("IT-Bill-Trial-"     + runId, "TRIAL");
        wsB = createWorkspaceWithEnterprise("IT-Bill-Business-"  + runId, "BUSINESS");
        wsC = createWorkspaceWithEnterprise("IT-Bill-Enterprise-"+ runId, "ENTERPRISE");

        entA = enterpriseFor(wsA);
        entB = enterpriseFor(wsB);
        entC = enterpriseFor(wsC);

        java.sql.Date month = java.sql.Date.valueOf(currentMonth().atDay(1));
        // A: TRIAL quota=100, used 30 → 30% → normal, no overage
        upsertBilling(entA, month, 30, 100, 0);
        // B: BUSINESS quota=2000, used 1700 → 85% → warn
        upsertBilling(entB, month, 1700, 2000, 0);
        // C: ENTERPRISE quota=10000, used 11000, overage 1000 → overage
        upsertBilling(entC, month, 11000, 10000, 1000);
    }

    private String createWorkspaceWithEnterprise(String name, String plan) throws Exception {
        String body = """
                {"name":"%s","plan_code":"%s","industry":"Bán lẻ"}
                """.formatted(name, plan);
        MvcResult res = mockMvc.perform(post("/api/v1/platform/workspaces")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isCreated())
                .andReturn();
        return objectMapper.readTree(res.getResponse().getContentAsString())
                .get("data").get("workspace_id").asText();
    }

    private String enterpriseFor(String workspaceId) {
        return jdbc.queryForObject(
                "SELECT enterprise_id::text FROM enterprises WHERE workspace_id = ?::uuid LIMIT 1",
                String.class, workspaceId);
    }

    private void upsertBilling(String entId, java.sql.Date month, int used, int quota, int overage) {
        jdbc.update("""
                INSERT INTO enterprise_monthly_billing
                    (enterprise_id, billing_month, unique_customers, quota, overage_count)
                VALUES (?::uuid, ?, ?, ?, ?)
                ON CONFLICT (enterprise_id, billing_month) DO UPDATE SET
                    unique_customers = EXCLUDED.unique_customers,
                    quota            = EXCLUDED.quota,
                    overage_count    = EXCLUDED.overage_count,
                    updated_at       = NOW()
                """, entId, month, used, quota, overage);
    }

    private static YearMonth currentMonth() {
        return YearMonth.from(LocalDate.now(ZoneOffset.UTC));
    }

    // =========================================================================
    // /overview
    // =========================================================================

    @Test
    @DisplayName("GET /overview — counts include our 3 fixtures with correct statuses")
    void overview_includesFixtures() throws Exception {
        MvcResult res = mockMvc.perform(get("/api/v1/platform/billing/overview"))
                .andExpect(status().isOk())
                .andReturn();
        JsonNode data = objectMapper.readTree(res.getResponse().getContentAsString())
                .get("data");

        assertThat(data.get("billing_month").asText()).isEqualTo(currentMonth().toString());
        assertThat(data.get("enterprise_count").asLong()).isGreaterThanOrEqualTo(3);
        // by_status sums must equal enterprise_count
        long sum = data.get("by_status").get("normal").asLong()
                 + data.get("by_status").get("warn").asLong()
                 + data.get("by_status").get("critical").asLong()
                 + data.get("by_status").get("overage").asLong();
        assertThat(sum).isEqualTo(data.get("enterprise_count").asLong());
        // We seeded ≥1 normal, ≥1 warn, ≥1 overage
        assertThat(data.get("by_status").get("normal").asLong()).isGreaterThanOrEqualTo(1);
        assertThat(data.get("by_status").get("warn").asLong()).isGreaterThanOrEqualTo(1);
        assertThat(data.get("by_status").get("overage").asLong()).isGreaterThanOrEqualTo(1);
        // Revenue = total_base + total_overage; in v1 overage stays 0
        assertThat(data.get("total_overage_amount_vnd").asLong()).isEqualTo(0L);
        assertThat(data.get("total_revenue_vnd").asLong())
                .isEqualTo(data.get("total_base_amount_vnd").asLong());
    }

    // =========================================================================
    // /enterprises/{id}
    // =========================================================================

    @Test
    @DisplayName("GET /enterprises/{id} — TRIAL workspace returns normal status")
    void enterprise_trial_normal() throws Exception {
        mockMvc.perform(get("/api/v1/platform/billing/enterprises/" + entA))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.enterprise_id").value(entA))
                .andExpect(jsonPath("$.data.workspace_id").value(wsA))
                .andExpect(jsonPath("$.data.plan_code").value("TRIAL"))
                .andExpect(jsonPath("$.data.unique_customers").value(30))
                .andExpect(jsonPath("$.data.quota").value(100))
                .andExpect(jsonPath("$.data.status").value("normal"))
                .andExpect(jsonPath("$.data.quota_warn_at_pct").value(80));
    }

    @Test
    @DisplayName("GET /enterprises/{id} — BUSINESS workspace 85% returns warn")
    void enterprise_business_warn() throws Exception {
        mockMvc.perform(get("/api/v1/platform/billing/enterprises/" + entB))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.unique_customers").value(1700))
                .andExpect(jsonPath("$.data.status").value("warn"));
    }

    @Test
    @DisplayName("GET /enterprises/{id} — overage_count > 0 wins over utilisation")
    void enterprise_overage() throws Exception {
        mockMvc.perform(get("/api/v1/platform/billing/enterprises/" + entC))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.overage_units").value(1000))
                .andExpect(jsonPath("$.data.status").value("overage"));
    }

    @Test
    @DisplayName("GET /enterprises/{id} — unknown id returns 404")
    void enterprise_notFound() throws Exception {
        mockMvc.perform(get("/api/v1/platform/billing/enterprises/" + UUID.randomUUID()))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.title").value("Enterprise not found"));
    }

    // =========================================================================
    // /quota
    // =========================================================================

    @Test
    @DisplayName("GET /quota?status=warn — returns our BUSINESS enterprise")
    void quota_filterByStatus_warn() throws Exception {
        MvcResult res = mockMvc.perform(get("/api/v1/platform/billing/quota")
                        .param("status", "warn")
                        .param("limit", "500"))
                .andExpect(status().isOk())
                .andReturn();
        List<String> ids = collectIds(res, "enterprise_id");
        assertThat(ids).contains(entB);
        // must NOT contain our overage / normal seeds
        assertThat(ids).doesNotContain(entA).doesNotContain(entC);
    }

    @Test
    @DisplayName("GET /quota?status=overage — returns our ENTERPRISE seed")
    void quota_filterByStatus_overage() throws Exception {
        MvcResult res = mockMvc.perform(get("/api/v1/platform/billing/quota")
                        .param("status", "overage")
                        .param("limit", "500"))
                .andExpect(status().isOk())
                .andReturn();
        assertThat(collectIds(res, "enterprise_id")).contains(entC);
    }

    @Test
    @DisplayName("GET /quota?plan=TRIAL — filters to plan, finds our normal seed")
    void quota_filterByPlan() throws Exception {
        MvcResult res = mockMvc.perform(get("/api/v1/platform/billing/quota")
                        .param("plan", "TRIAL")
                        .param("limit", "500"))
                .andExpect(status().isOk())
                .andReturn();
        JsonNode root = objectMapper.readTree(res.getResponse().getContentAsString());
        assertThat(collectIds(res, "enterprise_id")).contains(entA);
        // every row must be TRIAL
        for (JsonNode r : root.get("data")) {
            assertThat(r.get("plan_code").asText()).isEqualTo("TRIAL");
        }
    }

    @Test
    @DisplayName("GET /quota?plan=NOPE → 400 RFC 7807")
    void quota_unknownPlan() throws Exception {
        mockMvc.perform(get("/api/v1/platform/billing/quota").param("plan", "NOPE"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.title").value("Invalid plan_code"));
    }

    @Test
    @DisplayName("GET /quota — limit > 500 returns 400")
    void quota_limitTooBig() throws Exception {
        mockMvc.perform(get("/api/v1/platform/billing/quota").param("limit", "501"))
                .andExpect(status().isBadRequest());
    }

    // =========================================================================
    // /export
    // =========================================================================

    @Test
    @DisplayName("GET /export — CSV body has UTF-8 BOM, contains seeded enterprise + Vietnamese name")
    void export_bomAndContent() throws Exception {
        byte[] body = mockMvc.perform(get("/api/v1/platform/billing/export"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith("text/csv"))
                .andExpect(header().string("Content-Disposition",
                        org.hamcrest.Matchers.containsString("kaori-billing-")))
                .andReturn().getResponse().getContentAsByteArray();

        assertThat(body[0]).isEqualTo((byte) 0xEF);
        assertThat(body[1]).isEqualTo((byte) 0xBB);
        assertThat(body[2]).isEqualTo((byte) 0xBF);

        String csv = new String(body, 3, body.length - 3, StandardCharsets.UTF_8);
        assertThat(csv).startsWith("enterprise_id,enterprise_name,plan_code,billing_month,");
        assertThat(csv).contains(entA).contains(entB).contains(entC);
        assertThat(csv).contains("IT-Bill-Trial-"      + runId);
        assertThat(csv).contains("IT-Bill-Business-"   + runId);
        assertThat(csv).contains("IT-Bill-Enterprise-" + runId);
        // status column reflects seeding
        assertThat(csv).contains(",overage").contains(",warn").contains(",normal");
    }

    @Test
    @DisplayName("GET /export?plan=TRIAL — CSV contains only TRIAL rows")
    void export_filterPlan() throws Exception {
        byte[] body = mockMvc.perform(get("/api/v1/platform/billing/export").param("plan", "TRIAL"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsByteArray();
        String csv = new String(body, 3, body.length - 3, StandardCharsets.UTF_8);

        assertThat(csv).contains(entA);
        assertThat(csv).doesNotContain(entB);
        assertThat(csv).doesNotContain(entC);
    }

    @Test
    @DisplayName("GET /export?month=2026-13 → 400 invalid-month")
    void export_invalidMonth() throws Exception {
        mockMvc.perform(get("/api/v1/platform/billing/export").param("month", "2026-13"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.title").value("Invalid month"));
    }

    // =========================================================================
    // helpers
    // =========================================================================

    private List<String> collectIds(MvcResult res, String field) throws Exception {
        JsonNode root = objectMapper.readTree(res.getResponse().getContentAsString());
        java.util.ArrayList<String> ids = new java.util.ArrayList<>();
        for (JsonNode r : root.get("data")) ids.add(r.get(field).asText());
        return ids;
    }
}
