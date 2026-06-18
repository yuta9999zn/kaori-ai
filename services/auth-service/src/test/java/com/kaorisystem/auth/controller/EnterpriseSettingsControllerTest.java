package com.kaorisystem.auth.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaorisystem.auth.service.TenantSettingsService;
import com.kaorisystem.auth.service.TenantSettingsService.EnterpriseNotFoundException;
import com.kaorisystem.auth.service.TenantSettingsService.InvalidThemeException;
import com.kaorisystem.auth.service.TenantSettingsService.PatchRequest;
import com.kaorisystem.auth.service.TenantSettingsService.SettingsView;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.Map;
import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * F-016 — REST contract tests for EnterpriseSettingsController.
 *
 * Same pattern as WorkspaceControllerTest: web-layer slice with
 * TenantSettingsService mocked. SecurityAutoConfiguration excluded because
 * the gateway-trust filter is responsible for header injection in real
 * traffic; these tests verify the controller's own header handling.
 */
@WebMvcTest(controllers = EnterpriseSettingsController.class,
            excludeAutoConfiguration = {
                org.springframework.boot.autoconfigure.security.servlet.SecurityAutoConfiguration.class
            })
@DisplayName("EnterpriseSettingsController — F-016 REST contract")
class EnterpriseSettingsControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private TenantSettingsService settingsService;

    @Autowired
    private ObjectMapper objectMapper;

    private static final UUID ENTERPRISE_ID = UUID.fromString("11111111-1111-1111-1111-111111111111");

    private static SettingsView sampleView(boolean consent, String theme) {
        return new SettingsView(
                ENTERPRISE_ID,
                "Demo Kaori",
                "vi",
                theme,
                consent,
                true,
                null,
                null,
                "2026-04-01T00:00:00Z",
                "2026-04-27T00:00:00Z"
        );
    }

    // =========================================================================
    // GET /api/v1/enterprises/me/settings
    // =========================================================================

    @Test
    @DisplayName("GET — returns 200 with all fields when X-Enterprise-ID is present")
    void get_happyPath_returns200() throws Exception {
        given(settingsService.get(ENTERPRISE_ID)).willReturn(sampleView(false, "light"));

        mockMvc.perform(get("/api/v1/enterprises/me/settings")
                        .header("X-Enterprise-ID", ENTERPRISE_ID.toString()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.enterprise_id").value(ENTERPRISE_ID.toString()))
                .andExpect(jsonPath("$.data.enterprise_name").value("Demo Kaori"))
                .andExpect(jsonPath("$.data.locale").value("vi"))
                .andExpect(jsonPath("$.data.theme").value("light"))
                .andExpect(jsonPath("$.data.consent_external_ai").value(false))
                .andExpect(jsonPath("$.data.notification_email").value(true))
                .andExpect(jsonPath("$.data.created_at").exists())
                .andExpect(jsonPath("$.data.updated_at").exists());
    }

    @Test
    @DisplayName("GET — lazy-create flow: service returns view from a fresh row")
    void get_lazyCreate_returnsDefaults() throws Exception {
        // Service contract: get() lazy-creates if missing. Controller doesn't
        // distinguish; the assertion is that fresh rows surface with defaults.
        given(settingsService.get(ENTERPRISE_ID)).willReturn(sampleView(false, "light"));

        mockMvc.perform(get("/api/v1/enterprises/me/settings")
                        .header("X-Enterprise-ID", ENTERPRISE_ID.toString()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.consent_external_ai").value(false))
                .andExpect(jsonPath("$.data.theme").value("light"));
    }

    @Test
    @DisplayName("GET — missing X-Enterprise-ID header returns 401 with RFC 7807 body")
    void get_missingHeader_returns401() throws Exception {
        mockMvc.perform(get("/api/v1/enterprises/me/settings"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.type").value("/docs/errors/missing-enterprise-id"))
                .andExpect(jsonPath("$.status").value(401));

        verify(settingsService, never()).get(any());
    }

    @Test
    @DisplayName("GET — invalid UUID in X-Enterprise-ID returns 401 (treated as missing)")
    void get_invalidUuidHeader_returns401() throws Exception {
        mockMvc.perform(get("/api/v1/enterprises/me/settings")
                        .header("X-Enterprise-ID", "not-a-uuid"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.type").value("/docs/errors/missing-enterprise-id"));

        verify(settingsService, never()).get(any());
    }

    @Test
    @DisplayName("GET — service throws EnterpriseNotFound returns 404")
    void get_enterpriseNotFound_returns404() throws Exception {
        willThrow(new EnterpriseNotFoundException("Enterprise not found: " + ENTERPRISE_ID))
                .given(settingsService).get(ENTERPRISE_ID);

        mockMvc.perform(get("/api/v1/enterprises/me/settings")
                        .header("X-Enterprise-ID", ENTERPRISE_ID.toString()))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.type").value("/docs/errors/enterprise-not-found"));
    }

    // =========================================================================
    // PATCH /api/v1/enterprises/me/settings
    // =========================================================================

    @Test
    @DisplayName("PATCH — MANAGER toggling consent_external_ai returns 200 with updated value")
    void patch_managerConsentToggle_returns200() throws Exception {
        given(settingsService.patch(eq(ENTERPRISE_ID), any(PatchRequest.class)))
                .willReturn(sampleView(true, "light"));

        mockMvc.perform(patch("/api/v1/enterprises/me/settings")
                        .header("X-Enterprise-ID", ENTERPRISE_ID.toString())
                        .header("X-User-Role", "MANAGER")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                Map.of("consent_external_ai", true))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.consent_external_ai").value(true));
    }

    @Test
    @DisplayName("PATCH — MANAGER updating theme to 'dark' returns 200")
    void patch_managerThemeDark_returns200() throws Exception {
        given(settingsService.patch(eq(ENTERPRISE_ID), any(PatchRequest.class)))
                .willReturn(sampleView(false, "dark"));

        mockMvc.perform(patch("/api/v1/enterprises/me/settings")
                        .header("X-Enterprise-ID", ENTERPRISE_ID.toString())
                        .header("X-User-Role", "MANAGER")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of("theme", "dark"))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.theme").value("dark"));
    }

    @Test
    @DisplayName("PATCH — service throws InvalidThemeException returns 400")
    void patch_invalidTheme_returns400() throws Exception {
        willThrow(new InvalidThemeException("theme must be 'light' or 'dark'"))
                .given(settingsService).patch(eq(ENTERPRISE_ID), any(PatchRequest.class));

        mockMvc.perform(patch("/api/v1/enterprises/me/settings")
                        .header("X-Enterprise-ID", ENTERPRISE_ID.toString())
                        .header("X-User-Role", "MANAGER")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of("theme", "rainbow"))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.type").value("/docs/errors/invalid-theme"));
    }

    @Test
    @DisplayName("PATCH — VIEWER role returns 403")
    void patch_viewerRole_returns403() throws Exception {
        mockMvc.perform(patch("/api/v1/enterprises/me/settings")
                        .header("X-Enterprise-ID", ENTERPRISE_ID.toString())
                        .header("X-User-Role", "VIEWER")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                Map.of("consent_external_ai", true))))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.type").value("/docs/errors/forbidden"));

        verify(settingsService, never()).patch(any(), any());
    }

    @Test
    @DisplayName("PATCH — ANALYST role also returns 403 (only MANAGER can write)")
    void patch_analystRole_returns403() throws Exception {
        mockMvc.perform(patch("/api/v1/enterprises/me/settings")
                        .header("X-Enterprise-ID", ENTERPRISE_ID.toString())
                        .header("X-User-Role", "ANALYST")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                Map.of("consent_external_ai", true))))
                .andExpect(status().isForbidden());

        verify(settingsService, never()).patch(any(), any());
    }

    @Test
    @DisplayName("PATCH — empty body returns 400")
    void patch_emptyBody_returns400() throws Exception {
        mockMvc.perform(patch("/api/v1/enterprises/me/settings")
                        .header("X-Enterprise-ID", ENTERPRISE_ID.toString())
                        .header("X-User-Role", "MANAGER")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.type").value("/docs/errors/invalid-request"));

        verify(settingsService, never()).patch(any(), any());
    }

    @Test
    @DisplayName("PATCH — missing X-Enterprise-ID returns 401 (K-12: tenant from JWT only)")
    void patch_missingHeader_returns401() throws Exception {
        mockMvc.perform(patch("/api/v1/enterprises/me/settings")
                        .header("X-User-Role", "MANAGER")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(
                                Map.of("consent_external_ai", true))))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.type").value("/docs/errors/missing-enterprise-id"));

        verify(settingsService, never()).patch(any(), any());
    }
}
