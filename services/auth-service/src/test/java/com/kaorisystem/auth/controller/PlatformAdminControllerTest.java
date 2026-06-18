package com.kaorisystem.auth.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaorisystem.auth.service.PlatformAdminService;
import com.kaorisystem.auth.service.PlatformAdminService.AdminAlreadyExistsException;
import com.kaorisystem.auth.service.PlatformAdminService.AdminNotFoundException;
import com.kaorisystem.auth.service.PlatformAdminService.AdminView;
import com.kaorisystem.auth.service.PlatformAdminService.ResetResult;
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
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.willThrow;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(controllers = PlatformAdminController.class,
            excludeAutoConfiguration = {
                org.springframework.boot.autoconfigure.security.servlet.SecurityAutoConfiguration.class
            })
@DisplayName("PlatformAdminController — REST endpoint contract tests")
class PlatformAdminControllerTest {

    @Autowired private MockMvc       mockMvc;
    @Autowired private ObjectMapper  objectMapper;
    @MockBean  private PlatformAdminService adminService;

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private static AdminView view(UUID id, String email, String role, boolean active) {
        return new AdminView(id, email, "Test", role, active, false, null,
                Instant.parse("2026-04-25T10:00:00Z"));
    }

    // =========================================================================
    // GET /admins
    // =========================================================================

    @Test
    @DisplayName("GET /admins — returns 200 with admin list")
    void list_returns200() throws Exception {
        UUID id1 = UUID.randomUUID();
        UUID id2 = UUID.randomUUID();
        given(adminService.list()).willReturn(List.of(
                view(id1, "a@k.io", "ADMIN", true),
                view(id2, "b@k.io", "SUPPORT", true)));

        mockMvc.perform(get("/api/v1/platform/admins"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(2)))
                .andExpect(jsonPath("$.data[0].id").value(id1.toString()))
                .andExpect(jsonPath("$.data[0].email").value("a@k.io"))
                .andExpect(jsonPath("$.data[0].role").value("ADMIN"))
                .andExpect(jsonPath("$.data[0].is_active").value(true))
                .andExpect(jsonPath("$.data[0].mfa_enabled").value(false));
    }

    // =========================================================================
    // GET /admins/{id}
    // =========================================================================

    @Test
    @DisplayName("GET /admins/{id} — returns 200 with admin detail")
    void get_returns200() throws Exception {
        UUID id = UUID.randomUUID();
        given(adminService.get(id)).willReturn(view(id, "x@k.io", "SUPER_ADMIN", true));

        mockMvc.perform(get("/api/v1/platform/admins/" + id))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.id").value(id.toString()))
                .andExpect(jsonPath("$.data.role").value("SUPER_ADMIN"));
    }

    @Test
    @DisplayName("GET /admins/{id} — unknown id returns 404")
    void get_notFound() throws Exception {
        UUID id = UUID.randomUUID();
        willThrow(new AdminNotFoundException("not found")).given(adminService).get(id);

        mockMvc.perform(get("/api/v1/platform/admins/" + id))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.title").value("Platform admin not found"));
    }

    @Test
    @DisplayName("GET /admins/{id} — invalid UUID returns 400")
    void get_invalidUuid() throws Exception {
        mockMvc.perform(get("/api/v1/platform/admins/not-a-uuid"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.title").value("Invalid ID"));
    }

    // =========================================================================
    // POST /admins
    // =========================================================================

    @Test
    @DisplayName("POST /admins — valid invite returns 201 with admin fields")
    void invite_happyPath() throws Exception {
        UUID id = UUID.randomUUID();
        given(adminService.invite(eq("new@k.io"), eq("Người Mới"), eq("ADMIN"), any()))
                .willReturn(view(id, "new@k.io", "ADMIN", true));

        String body = """
                {"email":"new@k.io","full_name":"Người Mới","role":"ADMIN"}
                """;

        mockMvc.perform(post("/api/v1/platform/admins")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.data.id").value(id.toString()))
                .andExpect(jsonPath("$.data.email").value("new@k.io"))
                .andExpect(jsonPath("$.data.role").value("ADMIN"));
    }

    @Test
    @DisplayName("POST /admins — duplicate email returns 409")
    void invite_duplicate_returns409() throws Exception {
        willThrow(new AdminAlreadyExistsException("dup"))
                .given(adminService).invite(anyString(), anyString(), anyString(), any());

        String body = """
                {"email":"dup@k.io","full_name":"Dup","role":"ADMIN"}
                """;

        mockMvc.perform(post("/api/v1/platform/admins")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.title").value("Platform admin already exists"));
    }

    @Test
    @DisplayName("POST /admins — bean validation rejects invalid role")
    void invite_invalidRole_returns400() throws Exception {
        String body = """
                {"email":"x@k.io","full_name":"X","role":"GHOST"}
                """;

        mockMvc.perform(post("/api/v1/platform/admins")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("POST /admins — missing full_name returns 400")
    void invite_missingFullName_returns400() throws Exception {
        String body = """
                {"email":"x@k.io","role":"ADMIN"}
                """;

        mockMvc.perform(post("/api/v1/platform/admins")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest());
    }

    // =========================================================================
    // PATCH /admins/{id}
    // =========================================================================

    @Test
    @DisplayName("PATCH /admins/{id} — valid update returns 200 with new fields")
    void update_happyPath() throws Exception {
        UUID id = UUID.randomUUID();
        given(adminService.update(eq(id), isNull(), eq("ADMIN"), eq(false)))
                .willReturn(view(id, "x@k.io", "ADMIN", false));

        String body = """
                {"role":"ADMIN","is_active":false}
                """;

        mockMvc.perform(patch("/api/v1/platform/admins/" + id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.role").value("ADMIN"))
                .andExpect(jsonPath("$.data.is_active").value(false));
    }

    @Test
    @DisplayName("PATCH /admins/{id} — empty body returns 400")
    void update_emptyBody_returns400() throws Exception {
        UUID id = UUID.randomUUID();
        mockMvc.perform(patch("/api/v1/platform/admins/" + id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.title").value("Empty update"));
    }

    @Test
    @DisplayName("PATCH /admins/{id} — unknown id returns 404")
    void update_notFound_returns404() throws Exception {
        UUID id = UUID.randomUUID();
        willThrow(new AdminNotFoundException("nope"))
                .given(adminService).update(eq(id), any(), any(), any());

        String body = """
                {"role":"ADMIN"}
                """;

        mockMvc.perform(patch("/api/v1/platform/admins/" + id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isNotFound());
    }

    // =========================================================================
    // POST /admins/{id}/reset-password
    // =========================================================================

    @Test
    @DisplayName("POST /admins/{id}/reset-password — returns 200 with email it was sent to")
    void resetPassword_returns200() throws Exception {
        UUID id = UUID.randomUUID();
        given(adminService.resetPassword(id))
                .willReturn(new ResetResult(id, "boss@k.io"));

        mockMvc.perform(post("/api/v1/platform/admins/" + id + "/reset-password"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.id").value(id.toString()))
                .andExpect(jsonPath("$.data.reset_token_sent_to").value("boss@k.io"));
    }

    @Test
    @DisplayName("POST /admins/{id}/reset-password — unknown id returns 404")
    void resetPassword_notFound_returns404() throws Exception {
        UUID id = UUID.randomUUID();
        willThrow(new AdminNotFoundException("nope")).given(adminService).resetPassword(id);

        mockMvc.perform(post("/api/v1/platform/admins/" + id + "/reset-password"))
                .andExpect(status().isNotFound());
    }
}
