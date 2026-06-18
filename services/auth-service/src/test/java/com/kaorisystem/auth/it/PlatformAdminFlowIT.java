package com.kaorisystem.auth.it;

import com.fasterxml.jackson.databind.JsonNode;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MvcResult;

import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * E2E flow: Platform admin lifecycle against real Postgres.
 * Verifies that {@code platform_admins} + {@code platform_admin_password_resets}
 * tables created by migration 011 are wired correctly through the controller.
 */
@DisplayName("E2E — Platform admin CRUD + reset-password against real Postgres")
class PlatformAdminFlowIT extends AbstractIntegrationIT {

    @Autowired private JdbcTemplate jdbc;

    private String invite(String email, String fullName, String role) throws Exception {
        MvcResult res = mockMvc.perform(post("/api/v1/platform/admins")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"email":"%s","full_name":"%s","role":"%s"}
                                """.formatted(email, fullName, role)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.data.email").value(email))
                .andExpect(jsonPath("$.data.full_name").value(fullName))
                .andExpect(jsonPath("$.data.role").value(role))
                .andExpect(jsonPath("$.data.is_active").value(true))
                .andExpect(jsonPath("$.data.mfa_enabled").value(false))
                .andReturn();
        return objectMapper.readTree(res.getResponse().getContentAsString())
                .get("data").get("id").asText();
    }

    @Test
    @DisplayName("invite → get → update → resetPassword: full lifecycle")
    void admin_fullLifecycle() throws Exception {
        String email = "lifecycle-" + UUID.randomUUID() + "@kaori.io";
        String adminId = invite(email, "Người Mới", "ADMIN");

        // ----- GET by id -----
        mockMvc.perform(get("/api/v1/platform/admins/" + adminId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.id").value(adminId))
                .andExpect(jsonPath("$.data.email").value(email))
                .andExpect(jsonPath("$.data.role").value("ADMIN"));

        // ----- One reset token row was issued at invite time (for email activation) -----
        Long tokensAfterInvite = jdbc.queryForObject(
                "SELECT COUNT(*) FROM platform_admin_password_resets WHERE admin_id = ?::uuid",
                Long.class, adminId);
        assertThat(tokensAfterInvite).isEqualTo(1L);

        // ----- Update role + deactivate -----
        mockMvc.perform(patch("/api/v1/platform/admins/" + adminId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"role":"SUPPORT","is_active":false}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.role").value("SUPPORT"))
                .andExpect(jsonPath("$.data.is_active").value(false));

        // ----- Reset password issues a fresh token + returns email -----
        mockMvc.perform(post("/api/v1/platform/admins/" + adminId + "/reset-password"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.id").value(adminId))
                .andExpect(jsonPath("$.data.reset_token_sent_to").value(email));

        Long tokensAfterReset = jdbc.queryForObject(
                "SELECT COUNT(*) FROM platform_admin_password_resets WHERE admin_id = ?::uuid",
                Long.class, adminId);
        assertThat(tokensAfterReset).isEqualTo(2L);  // invite token + reset token
    }

    @Test
    @DisplayName("list: created admin appears in collection envelope")
    void list_includesNewAdmin() throws Exception {
        String email = "list-" + UUID.randomUUID() + "@kaori.io";
        String adminId = invite(email, "Lister", "SUPPORT");

        MvcResult res = mockMvc.perform(get("/api/v1/platform/admins"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data").isArray())
                .andReturn();

        JsonNode envelope = objectMapper.readTree(res.getResponse().getContentAsString());
        boolean found = false;
        for (JsonNode a : envelope.get("data")) {
            if (adminId.equals(a.get("id").asText())) {
                found = true;
                assertThat(a.get("email").asText()).isEqualTo(email);
                assertThat(a.get("role").asText()).isEqualTo("SUPPORT");
                break;
            }
        }
        assertThat(found).as("just-invited admin must appear in list").isTrue();
    }

    @Test
    @DisplayName("invite: duplicate email returns 409 (DB unique constraint surfaced as Conflict)")
    void invite_duplicate_returns409() throws Exception {
        String email = "dup-" + UUID.randomUUID() + "@kaori.io";
        invite(email, "First", "SUPPORT");

        mockMvc.perform(post("/api/v1/platform/admins")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"email":"%s","full_name":"Second","role":"ADMIN"}
                                """.formatted(email)))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.title").value("Platform admin already exists"));
    }

    @Test
    @DisplayName("invite: chk_platform_role CHECK constraint blocks invalid roles at the bean-validation layer")
    void invite_invalidRole_returns400() throws Exception {
        mockMvc.perform(post("/api/v1/platform/admins")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"email":"bad-%s@kaori.io","full_name":"X","role":"GHOST"}
                                """.formatted(UUID.randomUUID())))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("update: unknown id returns 404 with Problem Details")
    void update_unknownId_returns404() throws Exception {
        UUID ghost = UUID.randomUUID();
        mockMvc.perform(patch("/api/v1/platform/admins/" + ghost)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"role\":\"ADMIN\"}"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.title").value("Platform admin not found"));
    }

    @Test
    @DisplayName("resetPassword: unknown id returns 404; no token row created")
    void resetPassword_unknownId_returns404() throws Exception {
        UUID ghost = UUID.randomUUID();
        mockMvc.perform(post("/api/v1/platform/admins/" + ghost + "/reset-password"))
                .andExpect(status().isNotFound());

        Long tokens = jdbc.queryForObject(
                "SELECT COUNT(*) FROM platform_admin_password_resets WHERE admin_id = ?::uuid",
                Long.class, ghost.toString());
        assertThat(tokens).isZero();
    }
}
