package com.kaorisystem.auth.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.kaorisystem.auth.dto.AuthDtos.*;
import com.kaorisystem.auth.security.SecurityConfig;
import com.kaorisystem.auth.service.AuthService;
import com.kaorisystem.auth.service.AuthService.InvalidCredentialsException;
import com.kaorisystem.auth.service.AuthService.LockoutException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.UUID;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.BDDMockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * Slice test for AuthController — only the web layer is loaded.
 * AuthService is mocked via @MockBean; no database, no Redis, no real JWT.
 *
 * Spring Security is part of @WebMvcTest auto-configuration. Because
 * SecurityConfig permits all /auth/** requests, no authentication header
 * is required in these tests.
 */
@WebMvcTest(AuthController.class)
@Import(SecurityConfig.class)
@DisplayName("AuthController — REST endpoint contract tests")
class AuthControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private AuthService authService;

    @Autowired
    private ObjectMapper objectMapper;

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private static LoginResponse sampleLoginResponse() {
        LoginResponse r = new LoginResponse();
        r.setAccessToken("sample.access.token");
        r.setRefreshToken("sample.refresh.token");
        r.setRole("MANAGER");
        r.setEnterpriseId(UUID.randomUUID().toString());
        r.setUserId(UUID.randomUUID().toString());
        return r;
    }

    // =========================================================================
    // POST /auth/login
    // =========================================================================

    @Test
    @DisplayName("POST /auth/login — valid credentials returns 200 with accessToken in body")
    void login_validCredentials_returns200WithTokens() throws Exception {
        // given
        LoginRequest req = new LoginRequest();
        req.setEmail("user@kaori.vn");
        req.setPassword("Secure@1234");

        given(authService.login(any(LoginRequest.class))).willReturn(sampleLoginResponse());

        // when / then
        mockMvc.perform(post("/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.accessToken").value("sample.access.token"))
                .andExpect(jsonPath("$.refreshToken").value("sample.refresh.token"))
                .andExpect(jsonPath("$.role").value("MANAGER"));
    }

    @Test
    @DisplayName("POST /auth/login — invalid credentials returns 401 with INVALID_CREDENTIALS error code")
    void login_invalidCredentials_returns401() throws Exception {
        // given
        LoginRequest req = new LoginRequest();
        req.setEmail("user@kaori.vn");
        req.setPassword("wrong-password");

        given(authService.login(any(LoginRequest.class)))
                .willThrow(new InvalidCredentialsException("Invalid email or password."));

        // when / then
        mockMvc.perform(post("/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.error").value("INVALID_CREDENTIALS"));
    }

    @Test
    @DisplayName("POST /auth/login — locked account returns 423 with LOCKED code and lockoutRemainingSeconds")
    void login_lockedAccount_returns423() throws Exception {
        // given
        LoginRequest req = new LoginRequest();
        req.setEmail("locked@kaori.vn");
        req.setPassword("any");

        given(authService.login(any(LoginRequest.class)))
                .willThrow(new LockoutException("Account locked. Try again in 600 seconds.", 600L));

        // when / then
        mockMvc.perform(post("/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().is(423))
                .andExpect(jsonPath("$.error").value("LOCKED"))
                .andExpect(jsonPath("$.lockoutRemainingSeconds").value(600));
    }

    @Test
    @DisplayName("POST /auth/login — missing/empty email returns 400 (Bean Validation)")
    void login_missingEmail_returns400() throws Exception {
        // given — email is blank, violating @NotBlank @Email constraint
        LoginRequest req = new LoginRequest();
        req.setEmail("");
        req.setPassword("SomePassword");

        // when / then — MethodArgumentNotValidException → 400
        mockMvc.perform(post("/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("POST /auth/login — null email in body returns 400 (Bean Validation)")
    void login_nullEmail_returns400() throws Exception {
        // given — email field omitted from JSON
        String body = """
                {"password":"SomePassword"}
                """;

        // when / then
        mockMvc.perform(post("/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest());
    }

    // =========================================================================
    // POST /auth/logout
    // =========================================================================

    @Test
    @DisplayName("POST /auth/logout — returns 204 No Content regardless of token validity")
    void logout_returns204() throws Exception {
        // given — authService.logout is void; we just verify the status
        willDoNothing().given(authService).logout(anyString());

        // when / then
        mockMvc.perform(post("/auth/logout")
                        .header("Authorization", "Bearer sample.access.token"))
                .andExpect(status().isNoContent());
    }

    @Test
    @DisplayName("POST /auth/logout — no Authorization header still returns 204")
    void logout_noAuthHeader_returns204() throws Exception {
        // when / then — controller is defensive about missing header
        mockMvc.perform(post("/auth/logout"))
                .andExpect(status().isNoContent());
    }

    // =========================================================================
    // POST /auth/refresh
    // =========================================================================

    @Test
    @DisplayName("POST /auth/refresh — valid refresh token returns 200 with new token pair")
    void refresh_validToken_returns200() throws Exception {
        // given
        RefreshRequest req = new RefreshRequest();
        req.setRefreshToken("valid.refresh.token");

        given(authService.refresh(any(RefreshRequest.class))).willReturn(sampleLoginResponse());

        // when / then
        mockMvc.perform(post("/auth/refresh")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.accessToken").exists());
    }

    @Test
    @DisplayName("POST /auth/refresh — invalid/revoked token returns 401 with INVALID_TOKEN code")
    void refresh_invalidToken_returns401() throws Exception {
        // given
        RefreshRequest req = new RefreshRequest();
        req.setRefreshToken("revoked.token");

        given(authService.refresh(any(RefreshRequest.class)))
                .willThrow(new InvalidCredentialsException("Refresh token has been revoked."));

        // when / then
        mockMvc.perform(post("/auth/refresh")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.error").value("INVALID_TOKEN"));
    }

    // =========================================================================
    // POST /auth/forgot-password
    // =========================================================================

    @Test
    @DisplayName("POST /auth/forgot-password — any email always returns 200 (anti-enumeration guarantee)")
    void forgotPassword_alwaysReturns200() throws Exception {
        // given — for known email
        ForgotPasswordRequest known = new ForgotPasswordRequest();
        known.setEmail("someone@kaori.vn");
        willDoNothing().given(authService).forgotPassword(any(ForgotPasswordRequest.class));

        // when / then
        mockMvc.perform(post("/auth/forgot-password")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(known)))
                .andExpect(status().isOk());

        // given — for unknown email (same mock: no exception)
        ForgotPasswordRequest ghost = new ForgotPasswordRequest();
        ghost.setEmail("nobody@example.com");

        mockMvc.perform(post("/auth/forgot-password")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(ghost)))
                .andExpect(status().isOk());
    }

    @Test
    @DisplayName("POST /auth/forgot-password — invalid email format returns 400")
    void forgotPassword_invalidEmailFormat_returns400() throws Exception {
        // given
        String body = """
                {"email":"not-an-email"}
                """;

        // when / then
        mockMvc.perform(post("/auth/forgot-password")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest());
    }

    // =========================================================================
    // POST /auth/reset-password
    // =========================================================================

    @Test
    @DisplayName("POST /auth/reset-password — valid token and password returns 200")
    void resetPassword_validToken_returns200() throws Exception {
        // given
        ResetPasswordRequest req = new ResetPasswordRequest();
        req.setToken("valid-sha256-token");
        req.setNewPassword("NewSecure@9876");

        willDoNothing().given(authService).resetPassword(any(ResetPasswordRequest.class));

        // when / then
        mockMvc.perform(post("/auth/reset-password")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk());
    }

    @Test
    @DisplayName("POST /auth/reset-password — expired/invalid token returns 400 with INVALID_TOKEN code")
    void resetPassword_invalidToken_returns400() throws Exception {
        // given
        ResetPasswordRequest req = new ResetPasswordRequest();
        req.setToken("expired-token");
        req.setNewPassword("NewSecure@9876");

        willThrow(new InvalidCredentialsException("Invalid or expired reset token."))
                .given(authService).resetPassword(any(ResetPasswordRequest.class));

        // when / then
        mockMvc.perform(post("/auth/reset-password")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("INVALID_TOKEN"));
    }

    @Test
    @DisplayName("POST /auth/reset-password — password shorter than 8 chars returns 400 (Bean Validation)")
    void resetPassword_shortPassword_returns400() throws Exception {
        // given — newPassword violates @Size(min=8)
        String body = """
                {"token":"some-token","newPassword":"short"}
                """;

        // when / then
        mockMvc.perform(post("/auth/reset-password")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest());
    }

    // =========================================================================
    // GET /auth/health
    // =========================================================================

    @Test
    @DisplayName("GET /auth/health — returns 200 with body 'OK'")
    void health_returns200OK() throws Exception {
        // when / then
        mockMvc.perform(get("/auth/health"))
                .andExpect(status().isOk())
                .andExpect(content().string("OK"));
    }

    // =========================================================================
    // POST /auth/workspace/activate
    // =========================================================================

    @Test
    @DisplayName("POST /auth/workspace/activate — valid key returns 200 with tokens and MANAGER role")
    void activateWorkspace_validKey_returns200() throws Exception {
        // given
        ActivateKeyRequest req = new ActivateKeyRequest();
        req.setWorkspaceKey("valid-workspace-key");
        req.setAdminEmail("admin@kaori.vn");
        req.setAdminPassword("AdminP@ss123");
        req.setAdminName("First Admin");

        LoginResponse resp = sampleLoginResponse();
        resp.setRole("MANAGER");
        given(authService.activateWorkspace(any(ActivateKeyRequest.class))).willReturn(resp);

        // when / then
        mockMvc.perform(post("/auth/workspace/activate")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.role").value("MANAGER"))
                .andExpect(jsonPath("$.accessToken").exists());
    }

    @Test
    @DisplayName("POST /auth/workspace/activate — invalid/revoked key returns 400 with INVALID_KEY code")
    void activateWorkspace_invalidKey_returns400() throws Exception {
        // given
        ActivateKeyRequest req = new ActivateKeyRequest();
        req.setWorkspaceKey("bad-key");
        req.setAdminEmail("admin@kaori.vn");
        req.setAdminPassword("AdminP@ss123");

        given(authService.activateWorkspace(any(ActivateKeyRequest.class)))
                .willThrow(new InvalidCredentialsException("Invalid or revoked workspace key."));

        // when / then
        mockMvc.perform(post("/auth/workspace/activate")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(req)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("INVALID_KEY"));
    }

    @Test
    @DisplayName("POST /auth/workspace/activate — missing required fields returns 400 (Bean Validation)")
    void activateWorkspace_missingFields_returns400() throws Exception {
        // given — workspaceKey is blank, violating @NotBlank
        String body = """
                {"workspaceKey":"","adminEmail":"admin@kaori.vn","adminPassword":"AdminP@ss123"}
                """;

        // when / then
        mockMvc.perform(post("/auth/workspace/activate")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest());
    }
}
