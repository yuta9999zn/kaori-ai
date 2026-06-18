package com.kaorisystem.auth.controller;

import com.kaorisystem.auth.service.PlatformStatsService;
import com.kaorisystem.auth.service.PlatformStatsService.PlatformStats;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.BDDMockito.given;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * F-012 — REST contract for the platform-dashboard KPI roll-up.
 *
 * <p>Service layer is mocked; we only assert HTTP shape (the FE landed
 * `/platform` page reads exactly these field names since PR #69 / the
 * MSW handler).
 */
@WebMvcTest(controllers = PlatformStatsController.class,
            excludeAutoConfiguration = {
                org.springframework.boot.autoconfigure.security.servlet.SecurityAutoConfiguration.class
            })
@DisplayName("PlatformStatsController — REST contract")
class PlatformStatsControllerTest {

    @Autowired private MockMvc mockMvc;
    @MockBean  private PlatformStatsService statsService;

    @Test
    @DisplayName("GET /api/v1/platform/stats — happy path")
    void stats_happyPath() throws Exception {
        given(statsService.getStats()).willReturn(new PlatformStats(
                5, 3, 58, 486, 14, true, 0L, 420L));

        mockMvc.perform(get("/api/v1/platform/stats"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.total_workspaces").value(5))
                .andExpect(jsonPath("$.data.active_workspaces").value(3))
                .andExpect(jsonPath("$.data.total_users").value(58))
                .andExpect(jsonPath("$.data.total_runs").value(486))
                .andExpect(jsonPath("$.data.runs_today").value(14))
                .andExpect(jsonPath("$.data.ollama_online").value(true))
                .andExpect(jsonPath("$.data.kafka_lag").value(0))
                .andExpect(jsonPath("$.data.p95_latency_ms").value(420));
    }

    @Test
    @DisplayName("GET /api/v1/platform/stats — Ollama offline reflected in payload")
    void stats_ollamaOffline() throws Exception {
        given(statsService.getStats()).willReturn(new PlatformStats(
                5, 3, 58, 486, 14, false, 0L, 420L));

        mockMvc.perform(get("/api/v1/platform/stats"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.ollama_online").value(false));
    }

    @Test
    @DisplayName("GET /api/v1/platform/stats — empty SaaS (zero workspaces) does not 500")
    void stats_emptyTenant() throws Exception {
        given(statsService.getStats()).willReturn(new PlatformStats(
                0, 0, 0, 0, 0, true, 0L, 420L));

        mockMvc.perform(get("/api/v1/platform/stats"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.total_workspaces").value(0));
    }
}
