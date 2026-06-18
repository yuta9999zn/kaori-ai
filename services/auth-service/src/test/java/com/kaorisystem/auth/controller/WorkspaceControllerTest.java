package com.kaorisystem.auth.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaorisystem.auth.service.WorkspaceKeyService;
import com.kaorisystem.auth.service.WorkspaceMemberService;
import com.kaorisystem.auth.service.WorkspaceService;
import com.kaorisystem.auth.service.WorkspaceService.WorkspaceNotFoundException;
import com.kaorisystem.auth.service.WorkspaceService.WorkspacePage;
import com.kaorisystem.auth.service.WorkspaceService.WorkspaceView;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

import static org.hamcrest.Matchers.hasSize;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.willThrow;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Web-layer slice test for WorkspaceController.
 * WorkspaceService is mocked via @MockBean — no DB, no Redis, no JWT.
 *
 * Spring Security auto-configures under @WebMvcTest but SecurityConfig
 * permits /auth/** + /actuator/health and applies default rules elsewhere;
 * gateway-based auth means the service trusts its caller — these tests do
 * not exercise auth, they verify the REST contract of the endpoints.
 */
@WebMvcTest(controllers = WorkspaceController.class,
            excludeAutoConfiguration = {
                org.springframework.boot.autoconfigure.security.servlet.SecurityAutoConfiguration.class
            })
@DisplayName("WorkspaceController — REST endpoint contract tests")
class WorkspaceControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private WorkspaceService workspaceService;

    /** Required to satisfy WorkspaceController's constructor dependency added by F-008 expansion. */
    @MockBean
    private WorkspaceMemberService workspaceMemberService;

    /** Required to satisfy WorkspaceController's constructor dependency added by F-009. */
    @MockBean
    private WorkspaceKeyService workspaceKeyService;

    @Autowired
    private ObjectMapper objectMapper;

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private static WorkspaceView sampleView(UUID id, String name, String status) {
        Instant now = Instant.parse("2026-04-25T10:00:00Z");
        return new WorkspaceView(id, name, "ENT_MID", "Retail", status, now, now);
    }

    // =========================================================================
    // GET /api/v1/platform/workspaces  (list + pagination)
    // =========================================================================

    @Test
    @DisplayName("GET /workspaces — returns 200 with data[] and meta.cursor/meta.total")
    void list_happyPath_returns200() throws Exception {
        UUID id1 = UUID.randomUUID();
        UUID id2 = UUID.randomUUID();
        WorkspacePage page = new WorkspacePage(
                List.of(sampleView(id1, "Acme", "active"), sampleView(id2, "Beta", "active")),
                "next-cursor-abc",
                2L
        );
        given(workspaceService.list(isNull(), eq(50))).willReturn(page);

        mockMvc.perform(get("/api/v1/platform/workspaces"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(2)))
                .andExpect(jsonPath("$.data[0].workspace_id").value(id1.toString()))
                .andExpect(jsonPath("$.data[0].name").value("Acme"))
                .andExpect(jsonPath("$.data[0].status").value("active"))
                .andExpect(jsonPath("$.data[0].plan_code").value("ENT_MID"))
                .andExpect(jsonPath("$.meta.cursor").value("next-cursor-abc"))
                .andExpect(jsonPath("$.meta.total").value(2));
    }

    @Test
    @DisplayName("GET /workspaces — empty result returns 200 with data:[] and total=0")
    void list_emptyResult_returns200EmptyArray() throws Exception {
        given(workspaceService.list(any(), anyInt()))
                .willReturn(new WorkspacePage(List.of(), null, 0L));

        mockMvc.perform(get("/api/v1/platform/workspaces"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(0)))
                .andExpect(jsonPath("$.meta.total").value(0));
    }

    @Test
    @DisplayName("GET /workspaces?cursor=X&limit=10 — forwards pagination params to service")
    void list_withCursorAndLimit_forwardsToService() throws Exception {
        given(workspaceService.list(eq("cursor-xyz"), eq(10)))
                .willReturn(new WorkspacePage(List.of(), "next", 0L));

        mockMvc.perform(get("/api/v1/platform/workspaces")
                        .param("cursor", "cursor-xyz")
                        .param("limit",  "10"))
                .andExpect(status().isOk());
    }

    @Test
    @DisplayName("GET /workspaces?limit=0 — returns 400 invalid limit")
    void list_limitZero_returns400() throws Exception {
        mockMvc.perform(get("/api/v1/platform/workspaces").param("limit", "0"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.title").value("Invalid limit"));
    }

    @Test
    @DisplayName("GET /workspaces?limit=1000 — returns 400 (exceeds max 500)")
    void list_limitTooLarge_returns400() throws Exception {
        mockMvc.perform(get("/api/v1/platform/workspaces").param("limit", "1000"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400));
    }

    // =========================================================================
    // POST /api/v1/platform/workspaces
    // =========================================================================

    @Test
    @DisplayName("POST /workspaces — valid body returns 201 with workspace_id, plan_code, status")
    void create_validBody_returns201() throws Exception {
        UUID id = UUID.randomUUID();
        given(workspaceService.create(eq("Acme Ltd"), eq("ENT_MID"), eq("Retail")))
                .willReturn(sampleView(id, "Acme Ltd", "active"));

        String body = """
                {"name":"Acme Ltd","plan_code":"ENT_MID","industry":"Retail"}
                """;

        mockMvc.perform(post("/api/v1/platform/workspaces")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.data.workspace_id").value(id.toString()))
                .andExpect(jsonPath("$.data.name").value("Acme Ltd"))
                .andExpect(jsonPath("$.data.plan_code").value("ENT_MID"))
                .andExpect(jsonPath("$.data.status").value("active"));
    }

    @Test
    @DisplayName("POST /workspaces — industry is optional (omitted body still 201)")
    void create_industryOmitted_returns201() throws Exception {
        UUID id = UUID.randomUUID();
        given(workspaceService.create(eq("NoIndustry"), eq("PILOT"), isNull()))
                .willReturn(new WorkspaceView(id, "NoIndustry", "PILOT", null, "active",
                        Instant.now(), Instant.now()));

        String body = """
                {"name":"NoIndustry","plan_code":"PILOT"}
                """;

        mockMvc.perform(post("/api/v1/platform/workspaces")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isCreated());
    }

    @Test
    @DisplayName("POST /workspaces — missing name returns 400 (Bean Validation)")
    void create_missingName_returns400() throws Exception {
        String body = """
                {"plan_code":"ENT_MID"}
                """;
        mockMvc.perform(post("/api/v1/platform/workspaces")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("POST /workspaces — missing plan_code returns 400")
    void create_missingPlanCode_returns400() throws Exception {
        String body = """
                {"name":"Acme"}
                """;
        mockMvc.perform(post("/api/v1/platform/workspaces")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("POST /workspaces — name too short (1 char) returns 400")
    void create_nameTooShort_returns400() throws Exception {
        String body = """
                {"name":"A","plan_code":"ENT_MID"}
                """;
        mockMvc.perform(post("/api/v1/platform/workspaces")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("POST /workspaces — plan_code with illegal chars returns 400")
    void create_invalidPlanCode_returns400() throws Exception {
        String body = """
                {"name":"Acme","plan_code":"BAD PLAN!"}
                """;
        mockMvc.perform(post("/api/v1/platform/workspaces")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("POST /workspaces — malformed JSON returns 400")
    void create_malformedJson_returns400() throws Exception {
        mockMvc.perform(post("/api/v1/platform/workspaces")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{not-json"))
                .andExpect(status().isBadRequest());
    }

    // =========================================================================
    // PATCH /api/v1/platform/workspaces/{id}
    // =========================================================================

    @Test
    @DisplayName("PATCH /workspaces/{id} — valid plan update returns 200 with new data")
    void update_planCode_returns200() throws Exception {
        UUID id = UUID.randomUUID();
        given(workspaceService.update(eq(id), isNull(), eq("ENT_MAX"), isNull()))
                .willReturn(new WorkspaceView(id, "Acme", "ENT_MAX", "Retail", "active",
                        Instant.now(), Instant.now()));

        String body = """
                {"plan_code":"ENT_MAX"}
                """;

        mockMvc.perform(patch("/api/v1/platform/workspaces/" + id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.plan_code").value("ENT_MAX"));
    }

    @Test
    @DisplayName("PATCH /workspaces/{id} — unknown id returns 404")
    void update_notFound_returns404() throws Exception {
        UUID id = UUID.randomUUID();
        willThrow(new WorkspaceNotFoundException("Workspace " + id + " not found"))
                .given(workspaceService).update(eq(id), any(), any(), any());

        String body = """
                {"name":"NewName"}
                """;

        mockMvc.perform(patch("/api/v1/platform/workspaces/" + id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.title").value("Workspace not found"));
    }

    @Test
    @DisplayName("PATCH /workspaces/{id} — invalid UUID returns 400")
    void update_invalidUuid_returns400() throws Exception {
        String body = """
                {"name":"Anything"}
                """;
        mockMvc.perform(patch("/api/v1/platform/workspaces/not-a-uuid")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.title").value("Invalid workspace ID"));
    }

    @Test
    @DisplayName("PATCH /workspaces/{id} — empty body (all fields null) returns 400")
    void update_emptyBody_returns400() throws Exception {
        UUID id = UUID.randomUUID();
        mockMvc.perform(patch("/api/v1/platform/workspaces/" + id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.title").value("Empty update"));
    }

    @Test
    @DisplayName("PATCH /workspaces/{id} — invalid status value returns 400")
    void update_invalidStatus_returns400() throws Exception {
        UUID id = UUID.randomUUID();
        String body = """
                {"status":"banana"}
                """;
        mockMvc.perform(patch("/api/v1/platform/workspaces/" + id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest());
    }

    // =========================================================================
    // DELETE /api/v1/platform/workspaces/{id}
    // =========================================================================

    @Test
    @DisplayName("DELETE /workspaces/{id} — soft delete returns 200 with status=inactive")
    void softDelete_happyPath_returns200() throws Exception {
        UUID id = UUID.randomUUID();
        given(workspaceService.softDelete(eq(id)))
                .willReturn(sampleView(id, "Acme", "inactive"));

        mockMvc.perform(delete("/api/v1/platform/workspaces/" + id))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.workspace_id").value(id.toString()))
                .andExpect(jsonPath("$.data.status").value("inactive"));
    }

    @Test
    @DisplayName("DELETE /workspaces/{id} — unknown id returns 404")
    void softDelete_notFound_returns404() throws Exception {
        UUID id = UUID.randomUUID();
        willThrow(new WorkspaceNotFoundException("Workspace " + id + " not found"))
                .given(workspaceService).softDelete(eq(id));

        mockMvc.perform(delete("/api/v1/platform/workspaces/" + id))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.title").value("Workspace not found"));
    }

    @Test
    @DisplayName("DELETE /workspaces/{id} — invalid UUID returns 400")
    void softDelete_invalidUuid_returns400() throws Exception {
        mockMvc.perform(delete("/api/v1/platform/workspaces/not-a-uuid"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.title").value("Invalid workspace ID"));
    }
}
