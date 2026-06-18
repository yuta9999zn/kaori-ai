package com.kaorisystem.auth.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaorisystem.auth.service.WorkspaceKeyService;
import com.kaorisystem.auth.service.WorkspaceMemberService;
import com.kaorisystem.auth.service.WorkspaceMemberService.LastManagerException;
import com.kaorisystem.auth.service.WorkspaceMemberService.MemberAlreadyExistsException;
import com.kaorisystem.auth.service.WorkspaceMemberService.MemberNotFoundException;
import com.kaorisystem.auth.service.WorkspaceMemberService.MemberView;
import com.kaorisystem.auth.service.WorkspaceService;
import com.kaorisystem.auth.service.WorkspaceService.AuditPage;
import com.kaorisystem.auth.service.WorkspaceService.AuditView;
import com.kaorisystem.auth.service.WorkspaceService.BillingSummary;
import com.kaorisystem.auth.service.WorkspaceService.EnterpriseNotProvisionedException;
import com.kaorisystem.auth.service.WorkspaceService.WorkspaceNotFoundException;
import com.kaorisystem.auth.service.WorkspaceService.WorkspaceView;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

import static org.hamcrest.Matchers.hasSize;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Web-layer slice tests for the F-008 expansion endpoints (detail / members
 * / billing / audit). The original WorkspaceControllerTest covers the base
 * list/create/update/softDelete endpoints.
 */
@WebMvcTest(controllers = WorkspaceController.class,
            excludeAutoConfiguration = {
                org.springframework.boot.autoconfigure.security.servlet.SecurityAutoConfiguration.class
            })
@DisplayName("WorkspaceController deep — REST contract for /{id} + members/billing/audit")
class WorkspaceControllerDeepTest {

    @Autowired private MockMvc       mockMvc;
    @Autowired private ObjectMapper  objectMapper;
    @MockBean  private WorkspaceService       workspaceService;
    @MockBean  private WorkspaceMemberService memberService;
    @MockBean  private WorkspaceKeyService    keyService;

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private static WorkspaceView wsView(UUID id) {
        Instant now = Instant.parse("2026-04-25T10:00:00Z");
        return new WorkspaceView(id, "Acme", "BUSINESS", "Bán lẻ", "active", now, now);
    }

    private static MemberView memberView(UUID id, String email, String role, String status) {
        return new MemberView(id, email, "Test", role, status, null, Instant.parse("2026-04-25T10:00:00Z"));
    }

    // =========================================================================
    // GET /workspaces/{id}
    // =========================================================================

    @Test
    @DisplayName("GET /{id} — returns 200 with workspace fields")
    void getOne_happyPath() throws Exception {
        UUID id = UUID.randomUUID();
        given(workspaceService.get(id)).willReturn(wsView(id));

        mockMvc.perform(get("/api/v1/platform/workspaces/" + id))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.workspace_id").value(id.toString()))
                .andExpect(jsonPath("$.data.name").value("Acme"))
                .andExpect(jsonPath("$.data.industry").value("Bán lẻ"));
    }

    @Test
    @DisplayName("GET /{id} — unknown id returns 404")
    void getOne_notFound() throws Exception {
        UUID id = UUID.randomUUID();
        willThrow(new WorkspaceNotFoundException("not found")).given(workspaceService).get(id);

        mockMvc.perform(get("/api/v1/platform/workspaces/" + id))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.title").value("Workspace not found"));
    }

    @Test
    @DisplayName("GET /{id} — invalid UUID returns 400 with title=Invalid ID")
    void getOne_invalidUuid() throws Exception {
        mockMvc.perform(get("/api/v1/platform/workspaces/not-a-uuid"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.title").value("Invalid ID"));
    }

    // =========================================================================
    // GET /workspaces/{id}/members
    // =========================================================================

    @Test
    @DisplayName("GET /{id}/members — returns 200 with mapped members")
    void listMembers_happyPath() throws Exception {
        UUID workspaceId = UUID.randomUUID();
        UUID userId      = UUID.randomUUID();
        given(memberService.list(workspaceId))
                .willReturn(List.of(memberView(userId, "u@x.io", "VIEWER", "active")));

        mockMvc.perform(get("/api/v1/platform/workspaces/" + workspaceId + "/members"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(1)))
                .andExpect(jsonPath("$.data[0].user_id").value(userId.toString()))
                .andExpect(jsonPath("$.data[0].email").value("u@x.io"))
                .andExpect(jsonPath("$.data[0].role").value("VIEWER"));
    }

    @Test
    @DisplayName("GET /{id}/members — unknown workspace returns 404")
    void listMembers_notFound() throws Exception {
        UUID workspaceId = UUID.randomUUID();
        willThrow(new WorkspaceNotFoundException("nope")).given(memberService).list(workspaceId);

        mockMvc.perform(get("/api/v1/platform/workspaces/" + workspaceId + "/members"))
                .andExpect(status().isNotFound());
    }

    // =========================================================================
    // POST /workspaces/{id}/members  (invite)
    // =========================================================================

    @Test
    @DisplayName("POST /{id}/members — valid body returns 201 with invited member")
    void inviteMember_happyPath() throws Exception {
        UUID workspaceId = UUID.randomUUID();
        UUID userId      = UUID.randomUUID();
        given(memberService.invite(eq(workspaceId), eq("new@x.io"), eq("ANALYST"),
                isNull(), isNull(), anyString()))
                .willReturn(memberView(userId, "new@x.io", "ANALYST", "pending"));

        String body = """
                {"email":"new@x.io","role":"ANALYST"}
                """;

        mockMvc.perform(post("/api/v1/platform/workspaces/" + workspaceId + "/members")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.data.user_id").value(userId.toString()))
                .andExpect(jsonPath("$.data.email").value("new@x.io"))
                .andExpect(jsonPath("$.data.status").value("pending"));
    }

    @Test
    @DisplayName("POST /{id}/members — duplicate email returns 409")
    void inviteMember_duplicate_returns409() throws Exception {
        UUID workspaceId = UUID.randomUUID();
        willThrow(new MemberAlreadyExistsException("dup"))
                .given(memberService).invite(eq(workspaceId), anyString(), anyString(),
                        any(), any(), any());

        String body = """
                {"email":"dup@x.io","role":"VIEWER"}
                """;

        mockMvc.perform(post("/api/v1/platform/workspaces/" + workspaceId + "/members")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.title").value("Member already exists"));
    }

    @Test
    @DisplayName("POST /{id}/members — no enterprise yet returns 409 (not 500)")
    void inviteMember_noEnterprise_returns409() throws Exception {
        UUID workspaceId = UUID.randomUUID();
        willThrow(new EnterpriseNotProvisionedException("none"))
                .given(memberService).invite(eq(workspaceId), anyString(), anyString(),
                        any(), any(), any());

        String body = """
                {"email":"x@y.io","role":"VIEWER"}
                """;

        mockMvc.perform(post("/api/v1/platform/workspaces/" + workspaceId + "/members")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.title").value("Enterprise not provisioned"));
    }

    @Test
    @DisplayName("POST /{id}/members — bean validation rejects invalid role")
    void inviteMember_invalidRole_returns400() throws Exception {
        UUID workspaceId = UUID.randomUUID();
        String body = """
                {"email":"x@y.io","role":"GHOST"}
                """;

        mockMvc.perform(post("/api/v1/platform/workspaces/" + workspaceId + "/members")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("POST /{id}/members — bean validation rejects missing email")
    void inviteMember_missingEmail_returns400() throws Exception {
        UUID workspaceId = UUID.randomUUID();
        String body = """
                {"role":"VIEWER"}
                """;

        mockMvc.perform(post("/api/v1/platform/workspaces/" + workspaceId + "/members")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest());
    }

    // =========================================================================
    // PATCH /workspaces/{id}/members/{userId}
    // =========================================================================

    @Test
    @DisplayName("PATCH /{id}/members/{userId} — happy path returns 200 with new role")
    void updateMember_happyPath() throws Exception {
        UUID workspaceId = UUID.randomUUID();
        UUID userId      = UUID.randomUUID();
        given(memberService.updateRole(eq(workspaceId), eq(userId), eq("MANAGER"),
                isNull(), isNull(), anyString()))
                .willReturn(memberView(userId, "u@x.io", "MANAGER", "active"));

        String body = """
                {"role":"MANAGER"}
                """;

        mockMvc.perform(patch("/api/v1/platform/workspaces/" + workspaceId + "/members/" + userId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.role").value("MANAGER"));
    }

    @Test
    @DisplayName("PATCH /{id}/members/{userId} — last MANAGER demotion returns 409")
    void updateMember_lastManager_returns409() throws Exception {
        UUID workspaceId = UUID.randomUUID();
        UUID userId      = UUID.randomUUID();
        willThrow(new LastManagerException("only one"))
                .given(memberService).updateRole(eq(workspaceId), eq(userId), anyString(),
                        any(), any(), any());

        String body = """
                {"role":"VIEWER"}
                """;

        mockMvc.perform(patch("/api/v1/platform/workspaces/" + workspaceId + "/members/" + userId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.title").value("Cannot demote last manager"));
    }

    @Test
    @DisplayName("PATCH /{id}/members/{userId} — unknown member returns 404")
    void updateMember_notFound_returns404() throws Exception {
        UUID workspaceId = UUID.randomUUID();
        UUID userId      = UUID.randomUUID();
        willThrow(new MemberNotFoundException("nope"))
                .given(memberService).updateRole(eq(workspaceId), eq(userId), anyString(),
                        any(), any(), any());

        String body = """
                {"role":"VIEWER"}
                """;

        mockMvc.perform(patch("/api/v1/platform/workspaces/" + workspaceId + "/members/" + userId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isNotFound());
    }

    // =========================================================================
    // DELETE /workspaces/{id}/members/{userId}
    // =========================================================================

    @Test
    @DisplayName("DELETE /{id}/members/{userId} — happy path returns 200 with user_id")
    void removeMember_happyPath() throws Exception {
        UUID workspaceId = UUID.randomUUID();
        UUID userId      = UUID.randomUUID();

        mockMvc.perform(delete("/api/v1/platform/workspaces/" + workspaceId + "/members/" + userId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.user_id").value(userId.toString()));
        verify(memberService).remove(eq(workspaceId), eq(userId), isNull(), isNull(), anyString());
    }

    @Test
    @DisplayName("DELETE /{id}/members/{userId} — last MANAGER returns 409")
    void removeMember_lastManager_returns409() throws Exception {
        UUID workspaceId = UUID.randomUUID();
        UUID userId      = UUID.randomUUID();
        willThrow(new LastManagerException("only one"))
                .given(memberService).remove(eq(workspaceId), eq(userId),
                        any(), any(), any());

        mockMvc.perform(delete("/api/v1/platform/workspaces/" + workspaceId + "/members/" + userId))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.title").value("Cannot remove last manager"));
    }

    // =========================================================================
    // GET /workspaces/{id}/billing
    // =========================================================================

    @Test
    @DisplayName("GET /{id}/billing — returns 200 with money + status fields")
    void getBilling_happyPath() throws Exception {
        UUID workspaceId = UUID.randomUUID();
        BillingSummary b = new BillingSummary(
                workspaceId, "BUSINESS", "2026-04",
                800, 2000, 0,
                1_490_000.0, 0.0, 1_490_000.0,
                80, "normal",
                LocalDate.parse("2026-05-01")
        );
        given(workspaceService.getBillingSummary(workspaceId)).willReturn(b);

        mockMvc.perform(get("/api/v1/platform/workspaces/" + workspaceId + "/billing"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.workspace_id").value(workspaceId.toString()))
                .andExpect(jsonPath("$.data.plan_code").value("BUSINESS"))
                .andExpect(jsonPath("$.data.unique_customers").value(800))
                .andExpect(jsonPath("$.data.quota").value(2000))
                .andExpect(jsonPath("$.data.total_amount_vnd").value(1_490_000.0))
                .andExpect(jsonPath("$.data.status").value("normal"))
                .andExpect(jsonPath("$.data.next_invoice_date").value("2026-05-01"));
    }

    @Test
    @DisplayName("GET /{id}/billing — workspace exists but no enterprise returns 409")
    void getBilling_noEnterprise_returns409() throws Exception {
        UUID workspaceId = UUID.randomUUID();
        willThrow(new EnterpriseNotProvisionedException("nope"))
                .given(workspaceService).getBillingSummary(workspaceId);

        mockMvc.perform(get("/api/v1/platform/workspaces/" + workspaceId + "/billing"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.title").value("Enterprise not provisioned"));
    }

    // =========================================================================
    // GET /workspaces/{id}/audit
    // =========================================================================

    @Test
    @DisplayName("GET /{id}/audit — returns 200 with events + cursor + total")
    void listAudit_happyPath() throws Exception {
        UUID workspaceId = UUID.randomUUID();
        UUID eventId     = UUID.randomUUID();
        AuditView ev = new AuditView(eventId, "workspace.updated",
                "admin@k.io", "ADMIN", "plan_code", "TRIAL → BUSINESS",
                "10.0.0.1", Instant.parse("2026-04-25T10:00:00Z"));
        AuditPage page = new AuditPage(List.of(ev), "next-cursor", 1L);
        given(workspaceService.listAudit(eq(workspaceId), isNull(), eq(50))).willReturn(page);

        mockMvc.perform(get("/api/v1/platform/workspaces/" + workspaceId + "/audit"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(1)))
                .andExpect(jsonPath("$.data[0].event_id").value(eventId.toString()))
                .andExpect(jsonPath("$.data[0].event_type").value("workspace.updated"))
                .andExpect(jsonPath("$.data[0].actor_email").value("admin@k.io"))
                .andExpect(jsonPath("$.meta.cursor").value("next-cursor"))
                .andExpect(jsonPath("$.meta.total").value(1));
    }

    @Test
    @DisplayName("GET /{id}/audit?limit=0 returns 400 invalid limit")
    void listAudit_limitZero_returns400() throws Exception {
        UUID workspaceId = UUID.randomUUID();
        mockMvc.perform(get("/api/v1/platform/workspaces/" + workspaceId + "/audit")
                        .param("limit", "0"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.title").value("Invalid limit"));
    }

    @Test
    @DisplayName("GET /{id}/audit — unknown workspace returns 404")
    void listAudit_unknownWorkspace_returns404() throws Exception {
        UUID workspaceId = UUID.randomUUID();
        willThrow(new WorkspaceNotFoundException("nope"))
                .given(workspaceService).listAudit(eq(workspaceId), any(), any(Integer.class));

        mockMvc.perform(get("/api/v1/platform/workspaces/" + workspaceId + "/audit"))
                .andExpect(status().isNotFound());
    }
}
