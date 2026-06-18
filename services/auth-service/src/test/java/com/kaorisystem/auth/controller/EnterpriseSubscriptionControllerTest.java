package com.kaorisystem.auth.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaorisystem.auth.model.SubscriptionChangeRequest;
import com.kaorisystem.auth.service.SubscriptionService;
import com.kaorisystem.auth.service.SubscriptionService.EnterpriseNotFoundException;
import com.kaorisystem.auth.service.SubscriptionService.InvalidPlanException;
import com.kaorisystem.auth.service.SubscriptionService.PendingRequestExistsException;
import com.kaorisystem.auth.service.SubscriptionService.SubscriptionState;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * F-030 — REST contract tests for EnterpriseSubscriptionController.
 *
 * Same WebMvcTest slice pattern as EnterpriseSettingsControllerTest /
 * EnterpriseUserControllerTest. Service layer is mocked; the
 * SubscriptionService unit tests cover the SQL + threshold math.
 */
@WebMvcTest(controllers = EnterpriseSubscriptionController.class,
            excludeAutoConfiguration = {
                org.springframework.boot.autoconfigure.security.servlet.SecurityAutoConfiguration.class
            })
@DisplayName("EnterpriseSubscriptionController — F-030 REST contract")
class EnterpriseSubscriptionControllerTest {

    @Autowired private MockMvc mockMvc;
    @Autowired private ObjectMapper objectMapper;

    @MockBean private SubscriptionService subscriptionService;

    private static final UUID ENTERPRISE = UUID.fromString("11111111-1111-1111-1111-111111111111");

    private static SubscriptionState sampleState(boolean alert80, boolean alert95) {
        return new SubscriptionState(
                ENTERPRISE, "Demo Kaori",
                "ENT_BASIC", "Enterprise Basic",
                1000, 2_000_000L,
                720, 1000, 72, 0, 1080,
                alert80, alert95,
                "2026-04-01", 30, 7,
                Instant.parse("2026-04-27T02:00:00Z"),
                null
        );
    }

    private static SubscriptionChangeRequest sampleRequest() {
        SubscriptionChangeRequest r = new SubscriptionChangeRequest();
        r.setRequestId(UUID.fromString("22222222-2222-2222-2222-222222222222"));
        r.setEnterpriseId(ENTERPRISE);
        r.setCurrentPlan("ENT_BASIC");
        r.setRequestedPlan("ENT_MID");
        r.setStatus("PENDING");
        r.setRequestedAt(Instant.parse("2026-04-27T03:00:00Z"));
        return r;
    }

    // =========================================================================
    // GET /api/v1/enterprises/me/subscription
    // =========================================================================

    @Test
    @DisplayName("GET — returns 200 with full subscription state JSON")
    void get_happyPath_returns200() throws Exception {
        given(subscriptionService.getSubscription(ENTERPRISE))
                .willReturn(sampleState(false, false));

        mockMvc.perform(get("/api/v1/enterprises/me/subscription")
                        .header("X-Enterprise-ID", ENTERPRISE.toString()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.current_plan").value("ENT_BASIC"))
                .andExpect(jsonPath("$.data.usage_count").value(720))
                .andExpect(jsonPath("$.data.usage_pct").value(72))
                .andExpect(jsonPath("$.data.forecast_eom").value(1080))
                .andExpect(jsonPath("$.data.alert_80_fired").value(false))
                .andExpect(jsonPath("$.data.days_remaining").value(7))
                .andExpect(jsonPath("$.data.pending_upgrade").doesNotExist());
    }

    @Test
    @DisplayName("GET — surfaces both alert flags when F-031 has fired them")
    void get_alertFlags_surfacedToFE() throws Exception {
        given(subscriptionService.getSubscription(ENTERPRISE))
                .willReturn(sampleState(true, true));

        mockMvc.perform(get("/api/v1/enterprises/me/subscription")
                        .header("X-Enterprise-ID", ENTERPRISE.toString()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.alert_80_fired").value(true))
                .andExpect(jsonPath("$.data.alert_95_fired").value(true));
    }

    @Test
    @DisplayName("GET — missing X-Enterprise-ID returns 401")
    void get_missingHeader_returns401() throws Exception {
        mockMvc.perform(get("/api/v1/enterprises/me/subscription"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.type").value("/docs/errors/missing-enterprise-id"));
        verify(subscriptionService, never()).getSubscription(any());
    }

    @Test
    @DisplayName("GET — service throws EnterpriseNotFound returns 404")
    void get_enterpriseNotFound_returns404() throws Exception {
        willThrow(new EnterpriseNotFoundException("not found"))
                .given(subscriptionService).getSubscription(ENTERPRISE);

        mockMvc.perform(get("/api/v1/enterprises/me/subscription")
                        .header("X-Enterprise-ID", ENTERPRISE.toString()))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.type").value("/docs/errors/enterprise-not-found"));
    }

    // =========================================================================
    // POST /api/v1/enterprises/me/subscription/upgrade
    // =========================================================================

    @Test
    @DisplayName("POST upgrade — MANAGER successfully requests an upgrade returns 201")
    void post_upgrade_managerHappyPath() throws Exception {
        given(subscriptionService.requestUpgrade(eq(ENTERPRISE), eq("ENT_MID"), any(), any()))
                .willReturn(sampleRequest());

        mockMvc.perform(post("/api/v1/enterprises/me/subscription/upgrade")
                        .header("X-Enterprise-ID", ENTERPRISE.toString())
                        .header("X-User-ID",       "33333333-3333-3333-3333-333333333333")
                        .header("X-User-Role",     "MANAGER")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of(
                                "target_plan", "ENT_MID"))))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.data.status").value("PENDING"))
                .andExpect(jsonPath("$.data.requested_plan").value("ENT_MID"));
    }

    @Test
    @DisplayName("POST upgrade — VIEWER role returns 403")
    void post_upgrade_viewer_returns403() throws Exception {
        mockMvc.perform(post("/api/v1/enterprises/me/subscription/upgrade")
                        .header("X-Enterprise-ID", ENTERPRISE.toString())
                        .header("X-User-Role",     "VIEWER")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of("target_plan", "ENT_MID"))))
                .andExpect(status().isForbidden());
        verify(subscriptionService, never()).requestUpgrade(any(), any(), any(), any());
    }

    @Test
    @DisplayName("POST upgrade — duplicate pending request returns 409")
    void post_upgrade_duplicatePending_returns409() throws Exception {
        willThrow(new PendingRequestExistsException("already pending to ENT_MID"))
                .given(subscriptionService).requestUpgrade(any(), any(), any(), any());

        mockMvc.perform(post("/api/v1/enterprises/me/subscription/upgrade")
                        .header("X-Enterprise-ID", ENTERPRISE.toString())
                        .header("X-User-Role",     "MANAGER")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of("target_plan", "ENT_MID"))))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.type").value("/docs/errors/upgrade-pending"));
    }

    @Test
    @DisplayName("POST upgrade — invalid plan returns 400")
    void post_upgrade_invalidPlan_returns400() throws Exception {
        willThrow(new InvalidPlanException("Unknown plan_code: BANANA"))
                .given(subscriptionService).requestUpgrade(any(), any(), any(), any());

        mockMvc.perform(post("/api/v1/enterprises/me/subscription/upgrade")
                        .header("X-Enterprise-ID", ENTERPRISE.toString())
                        .header("X-User-Role",     "MANAGER")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of("target_plan", "BANANA"))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.type").value("/docs/errors/invalid-plan"));
    }
}
