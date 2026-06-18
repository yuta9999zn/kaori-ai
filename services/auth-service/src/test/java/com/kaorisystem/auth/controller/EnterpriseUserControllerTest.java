package com.kaorisystem.auth.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaorisystem.auth.service.EnterpriseUserService;
import com.kaorisystem.auth.service.EnterpriseUserService.LastManagerException;
import com.kaorisystem.auth.service.EnterpriseUserService.UserAlreadyExistsException;
import com.kaorisystem.auth.service.EnterpriseUserService.UserNotFoundException;
import com.kaorisystem.auth.service.EnterpriseUserService.UserPage;
import com.kaorisystem.auth.service.EnterpriseUserService.UserView;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * F-015 — REST contract tests for EnterpriseUserController.
 *
 * Same WebMvcTest slice pattern as EnterpriseSettingsControllerTest /
 * WorkspaceControllerTest. The min-MANAGER edge is exercised via the
 * service throwing LastManagerException — the actual count query runs
 * in EnterpriseUserServiceTest (one DB layer down).
 */
@WebMvcTest(controllers = EnterpriseUserController.class,
            excludeAutoConfiguration = {
                org.springframework.boot.autoconfigure.security.servlet.SecurityAutoConfiguration.class
            })
@DisplayName("EnterpriseUserController — F-015 REST contract")
class EnterpriseUserControllerTest {

    @Autowired private MockMvc mockMvc;
    @Autowired private ObjectMapper objectMapper;

    @MockBean private EnterpriseUserService userService;

    private static final UUID ENTERPRISE = UUID.fromString("11111111-1111-1111-1111-111111111111");
    private static final UUID USER       = UUID.fromString("22222222-2222-2222-2222-222222222222");

    private static UserView sampleView(String email, String role, String status) {
        return new UserView(USER, email, "Demo User", role, status,
                            null, "2026-04-27T00:00:00Z");
    }

    // =========================================================================
    // GET /api/v1/enterprises/users
    // =========================================================================

    @Test
    @DisplayName("GET — returns 200 with data + meta when X-Enterprise-ID is present")
    void get_happyPath_returns200() throws Exception {
        given(userService.list(eq(ENTERPRISE), isNull(), isNull(), eq(1), eq(20)))
                .willReturn(new UserPage(List.of(
                        sampleView("a@kaori.io", "MANAGER",  "active"),
                        sampleView("b@kaori.io", "ANALYST",  "active")
                ), 2L, 1, 20));

        mockMvc.perform(get("/api/v1/enterprises/users")
                        .header("X-Enterprise-ID", ENTERPRISE.toString()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data[0].email").value("a@kaori.io"))
                .andExpect(jsonPath("$.data[0].is_active").value(true))
                .andExpect(jsonPath("$.meta.total").value(2))
                .andExpect(jsonPath("$.meta.page").value(1))
                .andExpect(jsonPath("$.meta.limit").value(20));
    }

    @Test
    @DisplayName("GET — missing X-Enterprise-ID returns 401")
    void get_missingHeader_returns401() throws Exception {
        mockMvc.perform(get("/api/v1/enterprises/users"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.type").value("/docs/errors/missing-enterprise-id"));
        verify(userService, never()).list(any(), any(), any(), anyInt(), anyInt());
    }

    @Test
    @DisplayName("GET — role + status filter forwarded to service")
    void get_filtersForwarded() throws Exception {
        given(userService.list(eq(ENTERPRISE), eq("ANALYST"), eq("active"), eq(1), eq(20)))
                .willReturn(new UserPage(List.of(), 0L, 1, 20));
        mockMvc.perform(get("/api/v1/enterprises/users?role=ANALYST&status=active")
                        .header("X-Enterprise-ID", ENTERPRISE.toString()))
                .andExpect(status().isOk());
        verify(userService).list(ENTERPRISE, "ANALYST", "active", 1, 20);
    }

    // =========================================================================
    // POST /api/v1/enterprises/users
    // =========================================================================

    @Test
    @DisplayName("POST — MANAGER inviting a new ANALYST returns 201 with the new user")
    void post_managerInvite_returns201() throws Exception {
        given(userService.invite(eq(ENTERPRISE), eq("new@kaori.io"), eq("New User"), eq("ANALYST")))
                .willReturn(sampleView("new@kaori.io", "ANALYST", "active"));

        mockMvc.perform(post("/api/v1/enterprises/users")
                        .header("X-Enterprise-ID", ENTERPRISE.toString())
                        .header("X-User-Role", "MANAGER")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of(
                                "email",     "new@kaori.io",
                                "full_name", "New User",
                                "role",      "ANALYST"))))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.data.email").value("new@kaori.io"))
                .andExpect(jsonPath("$.data.role").value("ANALYST"));
    }

    @Test
    @DisplayName("POST — VIEWER role returns 403 (only MANAGER can invite)")
    void post_viewer_returns403() throws Exception {
        mockMvc.perform(post("/api/v1/enterprises/users")
                        .header("X-Enterprise-ID", ENTERPRISE.toString())
                        .header("X-User-Role", "VIEWER")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of(
                                "email", "x@kaori.io", "role", "ANALYST"))))
                .andExpect(status().isForbidden());
        verify(userService, never()).invite(any(), any(), any(), any());
    }

    @Test
    @DisplayName("POST — duplicate email returns 409")
    void post_duplicate_returns409() throws Exception {
        willThrow(new UserAlreadyExistsException("User already exists: x@kaori.io"))
                .given(userService).invite(any(), any(), any(), any());

        mockMvc.perform(post("/api/v1/enterprises/users")
                        .header("X-Enterprise-ID", ENTERPRISE.toString())
                        .header("X-User-Role", "MANAGER")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of(
                                "email", "x@kaori.io", "full_name", "X", "role", "VIEWER"))))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.type").value("/docs/errors/user-already-exists"));
    }

    // =========================================================================
    // PATCH /api/v1/enterprises/users/{userId}
    // =========================================================================

    @Test
    @DisplayName("PATCH — MANAGER changing another user's role to VIEWER returns 200")
    void patch_changeRole_returns200() throws Exception {
        given(userService.update(eq(ENTERPRISE), eq(USER), eq("VIEWER"), isNull()))
                .willReturn(sampleView("a@kaori.io", "VIEWER", "active"));

        mockMvc.perform(patch("/api/v1/enterprises/users/" + USER)
                        .header("X-Enterprise-ID", ENTERPRISE.toString())
                        .header("X-User-Role", "MANAGER")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of("role", "VIEWER"))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.role").value("VIEWER"));
    }

    @Test
    @DisplayName("PATCH — demoting last MANAGER returns 409 LastManager")
    void patch_lastManager_returns409() throws Exception {
        willThrow(new LastManagerException(
                "Operation would leave the enterprise with zero active MANAGERs"))
                .given(userService).update(eq(ENTERPRISE), eq(USER), eq("VIEWER"), isNull());

        mockMvc.perform(patch("/api/v1/enterprises/users/" + USER)
                        .header("X-Enterprise-ID", ENTERPRISE.toString())
                        .header("X-User-Role", "MANAGER")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of("role", "VIEWER"))))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.type").value("/docs/errors/last-manager"));
    }

    @Test
    @DisplayName("PATCH — VIEWER role returns 403")
    void patch_viewer_returns403() throws Exception {
        mockMvc.perform(patch("/api/v1/enterprises/users/" + USER)
                        .header("X-Enterprise-ID", ENTERPRISE.toString())
                        .header("X-User-Role", "VIEWER")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of("status", "inactive"))))
                .andExpect(status().isForbidden());
        verify(userService, never()).update(any(), any(), any(), any());
    }

    // =========================================================================
    // DELETE /api/v1/enterprises/users/{userId}
    // =========================================================================

    @Test
    @DisplayName("DELETE — soft delete returns 200 with status=deleted")
    void delete_softDelete_returns200() throws Exception {
        mockMvc.perform(delete("/api/v1/enterprises/users/" + USER)
                        .header("X-Enterprise-ID", ENTERPRISE.toString())
                        .header("X-User-Role", "MANAGER"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.status").value("deleted"));
        verify(userService).softDelete(ENTERPRISE, USER);
    }

    @Test
    @DisplayName("DELETE — deleting last MANAGER returns 409 LastManager")
    void delete_lastManager_returns409() throws Exception {
        willThrow(new LastManagerException("min-MANAGER guard"))
                .given(userService).softDelete(ENTERPRISE, USER);

        mockMvc.perform(delete("/api/v1/enterprises/users/" + USER)
                        .header("X-Enterprise-ID", ENTERPRISE.toString())
                        .header("X-User-Role", "MANAGER"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.type").value("/docs/errors/last-manager"));
    }

    @Test
    @DisplayName("DELETE — unknown user returns 404")
    void delete_notFound_returns404() throws Exception {
        willThrow(new UserNotFoundException("not found"))
                .given(userService).softDelete(ENTERPRISE, USER);

        mockMvc.perform(delete("/api/v1/enterprises/users/" + USER)
                        .header("X-Enterprise-ID", ENTERPRISE.toString())
                        .header("X-User-Role", "MANAGER"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.type").value("/docs/errors/user-not-found"));
    }
}
