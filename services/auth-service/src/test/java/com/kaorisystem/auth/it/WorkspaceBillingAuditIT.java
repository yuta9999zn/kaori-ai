package com.kaorisystem.auth.it;

import com.fasterxml.jackson.databind.JsonNode;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MvcResult;

import java.sql.Date;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * E2E flow: billing summary + audit log against real Postgres.
 *
 * Uses JdbcTemplate to seed an enterprise_monthly_billing row directly,
 * then exercises the GET /billing endpoint and verifies money + status
 * derivations. Audit assertions verify that side-effect rows from
 * mutations (create / update / member.invite) land in workspace_audit_log
 * and surface through GET /audit.
 */
@DisplayName("E2E — Workspace billing summary + audit log against real Postgres")
class WorkspaceBillingAuditIT extends AbstractIntegrationIT {

    @Autowired private JdbcTemplate jdbc;

    private String createWorkspaceWithEnterprise(String planCode) throws Exception {
        String body = """
                {"name":"%s","plan_code":"%s","industry":"Bán lẻ"}
                """.formatted("IT-Billing-" + UUID.randomUUID(), planCode);
        MvcResult res = mockMvc.perform(post("/api/v1/platform/workspaces")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isCreated())
                .andReturn();
        return objectMapper.readTree(res.getResponse().getContentAsString())
                .get("data").get("workspace_id").asText();
    }

    private UUID enterpriseIdOf(String workspaceId) {
        return jdbc.queryForObject(
                "SELECT enterprise_id FROM enterprises WHERE workspace_id = ?::uuid LIMIT 1",
                UUID.class, workspaceId);
    }

    // =========================================================================
    // Billing summary
    // =========================================================================

    @Test
    @DisplayName("billing: 80% usage on STARTER plan → status=warn, base=490_000 VND")
    void billing_warnThreshold() throws Exception {
        String workspaceId = createWorkspaceWithEnterprise("STARTER");
        UUID enterpriseId = enterpriseIdOf(workspaceId);

        // Seed enterprise_monthly_billing for the current month at 80% usage.
        LocalDate firstOfMonth = LocalDate.now(ZoneOffset.UTC).withDayOfMonth(1);
        jdbc.update("""
                INSERT INTO enterprise_monthly_billing
                    (enterprise_id, billing_month, unique_customers, quota, overage_count)
                VALUES (?, ?, ?, ?, ?)
                """,
                enterpriseId, Date.valueOf(firstOfMonth), 400, 500, 0);   // 80%

        mockMvc.perform(get("/api/v1/platform/workspaces/" + workspaceId + "/billing"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.workspace_id").value(workspaceId))
                .andExpect(jsonPath("$.data.plan_code").value("STARTER"))
                .andExpect(jsonPath("$.data.unique_customers").value(400))
                .andExpect(jsonPath("$.data.quota").value(500))
                .andExpect(jsonPath("$.data.status").value("warn"))
                .andExpect(jsonPath("$.data.quota_warn_at_pct").value(80))
                .andExpect(jsonPath("$.data.base_amount_vnd").value(490_000.0))
                .andExpect(jsonPath("$.data.overage_amount_vnd").value(0.0))
                .andExpect(jsonPath("$.data.total_amount_vnd").value(490_000.0));
    }

    @Test
    @DisplayName("billing: overage_count>0 forces status=overage regardless of usage%")
    void billing_overageStatus() throws Exception {
        String workspaceId = createWorkspaceWithEnterprise("BUSINESS");
        UUID enterpriseId = enterpriseIdOf(workspaceId);

        LocalDate firstOfMonth = LocalDate.now(ZoneOffset.UTC).withDayOfMonth(1);
        jdbc.update("""
                INSERT INTO enterprise_monthly_billing
                    (enterprise_id, billing_month, unique_customers, quota, overage_count)
                VALUES (?, ?, ?, ?, ?)
                """,
                enterpriseId, Date.valueOf(firstOfMonth), 2100, 2000, 100);

        mockMvc.perform(get("/api/v1/platform/workspaces/" + workspaceId + "/billing"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.overage_units").value(100))
                .andExpect(jsonPath("$.data.status").value("overage"));
    }

    @Test
    @DisplayName("billing: no row for current month → synthesizes 0/quota with status=normal")
    void billing_noRow_synthesizes() throws Exception {
        String workspaceId = createWorkspaceWithEnterprise("TRIAL");
        // Intentionally do NOT insert into enterprise_monthly_billing.

        mockMvc.perform(get("/api/v1/platform/workspaces/" + workspaceId + "/billing"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.unique_customers").value(0))
                .andExpect(jsonPath("$.data.quota").value(100))   // TRIAL plan quota
                .andExpect(jsonPath("$.data.status").value("normal"));
    }

    @Test
    @DisplayName("billing: workspace exists but no enterprise yet → 409 Conflict")
    void billing_noEnterprise_returns409() throws Exception {
        // Create WITHOUT industry → no seedEnterprise call → no enterprise row.
        String body = """
                {"name":"%s","plan_code":"TRIAL"}
                """.formatted("IT-NoEnt-" + UUID.randomUUID());
        MvcResult res = mockMvc.perform(post("/api/v1/platform/workspaces")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isCreated())
                .andReturn();
        String workspaceId = objectMapper.readTree(res.getResponse().getContentAsString())
                .get("data").get("workspace_id").asText();

        mockMvc.perform(get("/api/v1/platform/workspaces/" + workspaceId + "/billing"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.title").value("Enterprise not provisioned"));
    }

    // =========================================================================
    // Audit log
    // =========================================================================

    @Test
    @DisplayName("audit: member invite + remove emit audit events surfaced via GET /audit")
    void audit_memberLifecycleEmitsEvents() throws Exception {
        String workspaceId = createWorkspaceWithEnterprise("TRIAL");
        String email = "audit-" + UUID.randomUUID() + "@kaori.io";

        // Invite a member — should emit member.invited
        MvcResult invite = mockMvc.perform(post("/api/v1/platform/workspaces/" + workspaceId + "/members")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"email":"%s","role":"VIEWER"}
                                """.formatted(email)))
                .andExpect(status().isCreated())
                .andReturn();
        String userId = objectMapper.readTree(invite.getResponse().getContentAsString())
                .get("data").get("user_id").asText();

        // Remove the member — should emit member.removed
        mockMvc.perform(delete("/api/v1/platform/workspaces/" + workspaceId + "/members/" + userId))
                .andExpect(status().isOk());

        // Verify both events surface via GET /audit (pagination defaults to limit=50 newest-first)
        MvcResult auditRes = mockMvc.perform(get("/api/v1/platform/workspaces/" + workspaceId + "/audit"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data").isArray())
                .andExpect(jsonPath("$.meta.total").exists())
                .andReturn();

        JsonNode envelope = objectMapper.readTree(auditRes.getResponse().getContentAsString());
        boolean sawInvited = false;
        boolean sawRemoved = false;
        for (JsonNode ev : envelope.get("data")) {
            if ("member.invited".equals(ev.get("event_type").asText())
                    && email.equals(ev.get("resource").asText())) {
                sawInvited = true;
                assertThat(ev.get("detail").asText()).contains("role=VIEWER");
            }
            if ("member.removed".equals(ev.get("event_type").asText())
                    && email.equals(ev.get("resource").asText())) {
                sawRemoved = true;
            }
        }
        assertThat(sawInvited).as("member.invited event must be recorded").isTrue();
        assertThat(sawRemoved).as("member.removed event must be recorded").isTrue();
        assertThat(envelope.get("meta").get("total").asLong()).isGreaterThanOrEqualTo(2);
    }

    @Test
    @DisplayName("audit: append-only — direct UPDATE/DELETE on workspace_audit_log are no-ops (PG rules)")
    void audit_appendOnlyEnforcedByDb() throws Exception {
        String workspaceId = createWorkspaceWithEnterprise("TRIAL");

        // Generate one audit row via member invite
        mockMvc.perform(post("/api/v1/platform/workspaces/" + workspaceId + "/members")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"email":"x-%s@kaori.io","role":"VIEWER"}
                                """.formatted(UUID.randomUUID())))
                .andExpect(status().isCreated());

        Long before = jdbc.queryForObject(
                "SELECT COUNT(*) FROM workspace_audit_log WHERE workspace_id = ?::uuid",
                Long.class, workspaceId);
        assertThat(before).as("at least 1 audit row from invite").isGreaterThanOrEqualTo(1);

        // Try to mutate / delete — DB rules turn these into NO-OPs (no error, no effect)
        int updated = jdbc.update(
                "UPDATE workspace_audit_log SET event_type = 'tampered' WHERE workspace_id = ?::uuid",
                workspaceId);
        int deleted = jdbc.update(
                "DELETE FROM workspace_audit_log WHERE workspace_id = ?::uuid",
                workspaceId);

        // Both rules are ON ... DO INSTEAD NOTHING so JDBC reports 0 rows affected.
        assertThat(updated).as("UPDATE blocked by rule").isZero();
        assertThat(deleted).as("DELETE blocked by rule").isZero();

        // Row count + content unchanged
        Long after = jdbc.queryForObject(
                "SELECT COUNT(*) FROM workspace_audit_log WHERE workspace_id = ?::uuid",
                Long.class, workspaceId);
        assertThat(after).isEqualTo(before);

        List<Map<String, Object>> rows = jdbc.queryForList(
                "SELECT event_type FROM workspace_audit_log WHERE workspace_id = ?::uuid",
                workspaceId);
        for (Map<String, Object> row : rows) {
            assertThat(row.get("event_type")).isNotEqualTo("tampered");
        }
    }

    @Test
    @DisplayName("audit: cursor pagination yields stable ordering when many events present")
    void audit_cursorPagination() throws Exception {
        String workspaceId = createWorkspaceWithEnterprise("TRIAL");

        // Generate 5 audit events via member invites
        for (int i = 0; i < 5; i++) {
            mockMvc.perform(post("/api/v1/platform/workspaces/" + workspaceId + "/members")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content("""
                                    {"email":"page-%d-%s@kaori.io","role":"VIEWER"}
                                    """.formatted(i, UUID.randomUUID())))
                    .andExpect(status().isCreated());
        }

        // First page with limit=2 → 2 items + nextCursor
        MvcResult page1 = mockMvc.perform(get("/api/v1/platform/workspaces/" + workspaceId + "/audit")
                        .param("limit", "2"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.length()").value(2))
                .andExpect(jsonPath("$.meta.cursor").exists())
                .andReturn();

        JsonNode env1 = objectMapper.readTree(page1.getResponse().getContentAsString());
        String cursor = env1.get("meta").get("cursor").asText();
        assertThat(cursor).isNotBlank();

        // Page 2 — should not repeat any event_id from page 1
        MvcResult page2 = mockMvc.perform(get("/api/v1/platform/workspaces/" + workspaceId + "/audit")
                        .param("limit", "2")
                        .param("cursor", cursor))
                .andExpect(status().isOk())
                .andReturn();
        JsonNode env2 = objectMapper.readTree(page2.getResponse().getContentAsString());

        for (JsonNode a : env1.get("data")) {
            String id1 = a.get("event_id").asText();
            for (JsonNode b : env2.get("data")) {
                assertThat(b.get("event_id").asText())
                        .as("page 2 must not repeat page 1 event " + id1)
                        .isNotEqualTo(id1);
            }
        }
    }
}
