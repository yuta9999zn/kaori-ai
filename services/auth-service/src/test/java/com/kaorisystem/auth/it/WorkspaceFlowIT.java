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
 * End-to-end flow: workspace lifecycle through the HTTP API against a real
 * PostgreSQL container. Each test creates its own workspace with a unique
 * name so tests can run in any order without colliding.
 */
@DisplayName("E2E — Workspace CRUD lifecycle against real Postgres")
class WorkspaceFlowIT extends AbstractIntegrationIT {

    @Test
    @DisplayName("create → get → update → softDelete: full workspace lifecycle persists correctly")
    void workspace_fullLifecycle() throws Exception {
        String name = "IT-Workspace-" + UUID.randomUUID();

        // ----- 1. create -----
        String createBody = """
                {"name":"%s","plan_code":"TRIAL","industry":"Bán lẻ"}
                """.formatted(name);

        MvcResult created = mockMvc.perform(post("/api/v1/platform/workspaces")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(createBody))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.data.workspace_id").exists())
                .andExpect(jsonPath("$.data.name").value(name))
                .andExpect(jsonPath("$.data.plan_code").value("TRIAL"))
                .andExpect(jsonPath("$.data.status").value("active"))
                .andExpect(jsonPath("$.data.industry").value("Bán lẻ"))
                .andReturn();

        String workspaceId = readJson(created).get("data").get("workspace_id").asText();
        UUID.fromString(workspaceId);  // sanity — must be a UUID

        // ----- 2. get-by-id -----
        mockMvc.perform(get("/api/v1/platform/workspaces/" + workspaceId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.workspace_id").value(workspaceId))
                .andExpect(jsonPath("$.data.industry").value("Bán lẻ"));

        // ----- 3. update -----
        String updateBody = """
                {"plan_code":"BUSINESS","status":"suspended"}
                """;
        mockMvc.perform(patch("/api/v1/platform/workspaces/" + workspaceId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(updateBody))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.plan_code").value("BUSINESS"))
                .andExpect(jsonPath("$.data.status").value("suspended"));

        // ----- 4. get reflects update -----
        mockMvc.perform(get("/api/v1/platform/workspaces/" + workspaceId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.plan_code").value("BUSINESS"))
                .andExpect(jsonPath("$.data.status").value("suspended"));

        // ----- 5. softDelete -----
        mockMvc.perform(delete("/api/v1/platform/workspaces/" + workspaceId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.status").value("inactive"));

        // ----- 6. softDelete persisted -----
        mockMvc.perform(get("/api/v1/platform/workspaces/" + workspaceId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.status").value("inactive"));
    }

    @Test
    @DisplayName("list pagination: created workspace is reachable via cursor pagination")
    void workspace_appearsInList() throws Exception {
        String name = "IT-List-" + UUID.randomUUID();

        MvcResult created = mockMvc.perform(post("/api/v1/platform/workspaces")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"%s","plan_code":"TRIAL"}
                                """.formatted(name)))
                .andExpect(status().isCreated())
                .andReturn();
        String createdId = readJson(created).get("data").get("workspace_id").asText();

        MvcResult list = mockMvc.perform(get("/api/v1/platform/workspaces?limit=500"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data").isArray())
                .andExpect(jsonPath("$.meta.total").exists())
                .andReturn();

        JsonNode envelope = readJson(list);
        boolean found = false;
        for (JsonNode w : envelope.get("data")) {
            if (createdId.equals(w.get("workspace_id").asText())) { found = true; break; }
        }
        assertThat(found).as("just-created workspace must appear in list").isTrue();
        assertThat(envelope.get("meta").get("total").asLong()).isPositive();
    }

    @Test
    @DisplayName("update: unknown UUID returns 404 with Problem Details envelope")
    void update_unknownId_returns404() throws Exception {
        UUID ghost = UUID.randomUUID();
        mockMvc.perform(patch("/api/v1/platform/workspaces/" + ghost)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"name\":\"Whatever\"}"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.title").value("Workspace not found"))
                .andExpect(jsonPath("$.status").value(404));
    }

    @Test
    @DisplayName("create: rejects unknown plan_code with 400 (FK pre-check)")
    void create_unknownPlan_returns400() throws Exception {
        // The plan_code passes the regex but is not a real subscription_plans row.
        mockMvc.perform(post("/api/v1/platform/workspaces")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"name":"%s","plan_code":"BOGUS"}
                                """.formatted("IT-" + UUID.randomUUID())))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.title").value("Invalid plan_code"));
    }

    private JsonNode readJson(MvcResult result) throws Exception {
        return objectMapper.readTree(result.getResponse().getContentAsString());
    }
}
