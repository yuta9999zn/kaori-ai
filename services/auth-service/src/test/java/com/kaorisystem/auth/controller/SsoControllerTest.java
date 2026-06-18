package com.kaorisystem.auth.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaorisystem.auth.dto.AuthDtos.LoginResponse;
import com.kaorisystem.auth.dto.AuthDtos.SsoExchangeRequest;
import com.kaorisystem.auth.security.SecurityConfig;
import com.kaorisystem.auth.service.SsoExchangeService;
import com.kaorisystem.auth.service.SsoExchangeService.SsoExchangeError;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.UUID;

import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.willThrow;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Slice test for {@link SsoController}.
 *
 * <p>Verifies the controller's status-code mapping for the
 * {@link SsoExchangeError} hierarchy plus the happy-path 200 with
 * the standard {@link LoginResponse} payload.
 */
@WebMvcTest(SsoController.class)
@Import(SecurityConfig.class)
@DisplayName("SsoController — POST /auth/sso/exchange")
class SsoControllerTest {

    @Autowired private MockMvc mockMvc;
    @Autowired private ObjectMapper objectMapper;
    @MockBean  private SsoExchangeService ssoExchangeService;

    private static LoginResponse sampleResponse() {
        LoginResponse r = new LoginResponse();
        r.setAccessToken("sso.access.token");
        r.setRefreshToken("sso.refresh.token");
        r.setRole("ANALYST");
        r.setEnterpriseId(UUID.randomUUID().toString());
        r.setUserId(UUID.randomUUID().toString());
        r.setMustChangePassword(false);
        return r;
    }

    private static SsoExchangeRequest req(String code) {
        SsoExchangeRequest r = new SsoExchangeRequest();
        r.setSsoCode(code);
        return r;
    }

    @Test
    @DisplayName("happy path — 200 with LoginResponse fields")
    void exchange_ok() throws Exception {
        given(ssoExchangeService.exchange(anyString())).willReturn(sampleResponse());

        mockMvc.perform(post("/auth/sso/exchange")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(req("any-code"))))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.accessToken").value("sso.access.token"))
            .andExpect(jsonPath("$.refreshToken").value("sso.refresh.token"))
            .andExpect(jsonPath("$.role").value("ANALYST"))
            .andExpect(jsonPath("$.mustChangePassword").value(false));
    }

    @Test
    @DisplayName("400 — missing sso_code field rejected by @NotBlank")
    void exchange_missingCode_returns400() throws Exception {
        mockMvc.perform(post("/auth/sso/exchange")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{}"))
            .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("404 — service raises SsoExchangeError(404)")
    void exchange_unknownCode_404() throws Exception {
        willThrow(new SsoExchangeError(404, "Unknown SSO exchange code"))
            .given(ssoExchangeService).exchange(anyString());

        mockMvc.perform(post("/auth/sso/exchange")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(req("nope"))))
            .andExpect(status().isNotFound())
            .andExpect(jsonPath("$.error").value("SSO_EXCHANGE_FAILED"));
    }

    @Test
    @DisplayName("410 — code already consumed")
    void exchange_consumedCode_410() throws Exception {
        willThrow(new SsoExchangeError(410, "SSO exchange code already consumed or expired"))
            .given(ssoExchangeService).exchange(anyString());

        mockMvc.perform(post("/auth/sso/exchange")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(req("used"))))
            .andExpect(status().isGone());
    }

    @Test
    @DisplayName("502 — ai-orchestrator unreachable")
    void exchange_orchestratorDown_502() throws Exception {
        willThrow(new SsoExchangeError(502, "ai-orchestrator unreachable"))
            .given(ssoExchangeService).exchange(anyString());

        mockMvc.perform(post("/auth/sso/exchange")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(req("c"))))
            .andExpect(status().isBadGateway());
    }

    @Test
    @DisplayName("503 — internal token not configured")
    void exchange_serviceUnavailable_503() throws Exception {
        willThrow(new SsoExchangeError(503, "KAORI_INTERNAL_SVC_TOKEN not configured"))
            .given(ssoExchangeService).exchange(anyString());

        mockMvc.perform(post("/auth/sso/exchange")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(req("c"))))
            .andExpect(status().isServiceUnavailable());
    }
}
