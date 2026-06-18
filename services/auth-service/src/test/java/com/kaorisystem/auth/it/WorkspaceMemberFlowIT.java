package com.kaorisystem.auth.it;

import com.fasterxml.jackson.databind.JsonNode;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MvcResult;

import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * End-to-end flow: workspace member CRUD against real Postgres.
 *
 * Member endpoints depend on the workspace having a seeded enterprise
 * (the workspace → enterprise → enterprise_users join). Workspace creation
 * with a non-blank `industry` triggers the seed (see WorkspaceService.create).
 */
@DisplayName("E2E — Workspace member CRUD + last-MANAGER guard")
class WorkspaceMemberFlowIT extends AbstractIntegrationIT {

    private String createWorkspaceWithEnterprise() throws Exception {
        String body = """
                {"name":"%s","plan_code":"TRIAL","industry":"Bán lẻ"}
                """.formatted("IT-Members-" + UUID.randomUUID());
        MvcResult res = mockMvc.perform(post("/api/v1/platform/workspaces")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isCreated())
                .andReturn();
        return objectMapper.readTree(res.getResponse().getContentAsString())
                .get("data").get("workspace_id").asText();
    }

    private String inviteMember(String workspaceId, String email, String role) throws Exception {
        MvcResult res = mockMvc.perform(post("/api/v1/platform/workspaces/" + workspaceId + "/members")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"email":"%s","role":"%s"}
                                """.formatted(email, role)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.data.email").value(email))
                .andExpect(jsonPath("$.data.role").value(role))
                .andExpect(jsonPath("$.data.status").value("pending"))
                .andReturn();
        return objectMapper.readTree(res.getResponse().getContentAsString())
                .get("data").get("user_id").asText();
    }

    @Test
    @DisplayName("invite → list → updateRole → remove: full member lifecycle")
    void member_fullLifecycle() throws Exception {
        String workspaceId = createWorkspaceWithEnterprise();
        String email = "lifecycle-" + UUID.randomUUID() + "@kaori.io";

        // ----- 1. invite -----
        String userId = inviteMember(workspaceId, email, "VIEWER");

        // ----- 2. list shows the new member -----
        mockMvc.perform(get("/api/v1/platform/workspaces/" + workspaceId + "/members"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data[?(@.email=='" + email + "')].role").value("VIEWER"))
                .andExpect(jsonPath("$.data[?(@.email=='" + email + "')].status").value("pending"));

        // ----- 3. updateRole -----
        mockMvc.perform(patch("/api/v1/platform/workspaces/" + workspaceId + "/members/" + userId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"role\":\"ANALYST\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.role").value("ANALYST"));

        // ----- 4. remove -----
        mockMvc.perform(delete("/api/v1/platform/workspaces/" + workspaceId + "/members/" + userId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.user_id").value(userId));

        // ----- 5. removed member no longer in list -----
        MvcResult list = mockMvc.perform(get("/api/v1/platform/workspaces/" + workspaceId + "/members"))
                .andExpect(status().isOk())
                .andReturn();
        JsonNode envelope = objectMapper.readTree(list.getResponse().getContentAsString());
        for (JsonNode m : envelope.get("data")) {
            assertThat(m.get("email").asText()).isNotEqualTo(email);
        }
    }

    @Test
    @DisplayName("invite duplicate email in same enterprise → 409 Conflict")
    void invite_duplicate_returns409() throws Exception {
        String workspaceId = createWorkspaceWithEnterprise();
        String email = "dup-" + UUID.randomUUID() + "@kaori.io";

        inviteMember(workspaceId, email, "VIEWER");

        // Second invite of same email → 409
        mockMvc.perform(post("/api/v1/platform/workspaces/" + workspaceId + "/members")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"email":"%s","role":"VIEWER"}
                                """.formatted(email)))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.title").value("Member already exists"));
    }

    @Test
    @DisplayName("last-MANAGER guard: cannot demote the only MANAGER (returns 409)")
    void updateRole_lastManager_returns409() throws Exception {
        String workspaceId = createWorkspaceWithEnterprise();
        String email = "boss-" + UUID.randomUUID() + "@kaori.io";

        // Invite as MANAGER — this is the only MANAGER in the enterprise.
        // Note: invited members have status=pending, but the count guard
        // counts only status='active' MANAGERs, so initially there are ZERO
        // active MANAGERs. The guard fires when active count <= 1, so
        // demoting a pending MANAGER is also blocked (since that would
        // leave 0 MANAGERs of any status). This is intentional — a
        // workspace must always have at least one MANAGER.
        String userId = inviteMember(workspaceId, email, "MANAGER");

        mockMvc.perform(patch("/api/v1/platform/workspaces/" + workspaceId + "/members/" + userId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"role\":\"VIEWER\"}"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.title").value("Cannot demote last manager"));
    }

    @Test
    @DisplayName("invite into workspace without enterprise (no industry on create) → 409")
    void invite_noEnterprise_returns409() throws Exception {
        // Create WITHOUT industry — the seedEnterprise path is skipped.
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

        mockMvc.perform(post("/api/v1/platform/workspaces/" + workspaceId + "/members")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"email":"x-%s@kaori.io","role":"VIEWER"}
                                """.formatted(UUID.randomUUID())))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.title").value("Enterprise not provisioned"));
    }
}
