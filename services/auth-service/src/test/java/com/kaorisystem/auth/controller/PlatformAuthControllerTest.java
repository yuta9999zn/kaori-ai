package com.kaorisystem.auth.controller;

import com.kaorisystem.auth.dto.AuthDtos.LoginRequest;
import com.kaorisystem.auth.dto.AuthDtos.MfaVerifyRequest;
import com.kaorisystem.auth.service.AuthService.InvalidCredentialsException;
import com.kaorisystem.auth.service.AuthService.LockoutException;
import com.kaorisystem.auth.service.PlatformAuthService;
import com.kaorisystem.auth.service.PlatformAuthService.MfaChallengeExpiredException;
import com.kaorisystem.auth.service.PlatformAuthService.PlatformLoginResult;
import com.kaorisystem.auth.service.PlatformAuthService.TokenReplayException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.willThrow;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(controllers = PlatformAuthController.class,
            excludeAutoConfiguration = {
                org.springframework.boot.autoconfigure.security.servlet.SecurityAutoConfiguration.class
            })
@DisplayName("PlatformAuthController — REST contract")
class PlatformAuthControllerTest {

    @Autowired private MockMvc mockMvc;
    @MockBean  private PlatformAuthService authService;

    @Test
    @DisplayName("POST /auth/platform/login — happy path returns full result envelope")
    void login_happyPath() throws Exception {
        UUID sessionId = UUID.randomUUID();
        UUID adminId   = UUID.randomUUID();
        given(authService.login(any(LoginRequest.class), anyString(), any()))
                .willReturn(PlatformLoginResult.session(
                        "access.token", "refresh.token",
                        sessionId, adminId, "ADMIN", true, 900L));

        mockMvc.perform(post("/auth/platform/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"email\":\"a@kaori.io\",\"password\":\"correct-horse-battery-staple\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.access_token").value("access.token"))
                .andExpect(jsonPath("$.data.refresh_token").value("refresh.token"))
                .andExpect(jsonPath("$.data.session_id").value(sessionId.toString()))
                .andExpect(jsonPath("$.data.admin_id").value(adminId.toString()))
                .andExpect(jsonPath("$.data.role").value("ADMIN"))
                .andExpect(jsonPath("$.data.mfa_enabled").value(true))
                .andExpect(jsonPath("$.data.expires_in_sec").value(900));
    }

    @Test
    @DisplayName("POST /auth/platform/login — invalid credentials → 401 RFC 7807")
    void login_invalidCreds() throws Exception {
        willThrow(new InvalidCredentialsException("Invalid email or password."))
                .given(authService).login(any(), any(), any());

        mockMvc.perform(post("/auth/platform/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"email\":\"a@kaori.io\",\"password\":\"x12345678\"}"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.title").value("Invalid credentials"))
                .andExpect(jsonPath("$.status").value(401));
    }

    @Test
    @DisplayName("POST /auth/platform/login — locked → 423 with seconds-remaining hint")
    void login_locked() throws Exception {
        willThrow(new LockoutException("Account locked. Try again in 873 seconds.", 873L))
                .given(authService).login(any(), any(), any());

        mockMvc.perform(post("/auth/platform/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"email\":\"a@kaori.io\",\"password\":\"x12345678\"}"))
                .andExpect(status().isLocked())
                .andExpect(jsonPath("$.title").value("Account locked"))
                .andExpect(jsonPath("$.lockout_remaining_seconds").value(873));
    }

    @Test
    @DisplayName("POST /auth/platform/login — bean validation rejects malformed body")
    void login_validation() throws Exception {
        mockMvc.perform(post("/auth/platform/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"email\":\"not-an-email\",\"password\":\"\"}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("POST /auth/platform/refresh — invalid token → 401 RFC 7807")
    void refresh_invalidToken() throws Exception {
        willThrow(new InvalidCredentialsException("Invalid or expired refresh token."))
                .given(authService).refresh(any());

        mockMvc.perform(post("/auth/platform/refresh")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"refreshToken\":\"bad.token\"}"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.title").value("Invalid token"));
    }

    @Test
    @DisplayName("POST /auth/platform/refresh — happy path returns new tokens")
    void refresh_happyPath() throws Exception {
        UUID sessionId = UUID.randomUUID();
        UUID adminId   = UUID.randomUUID();
        given(authService.refresh(any())).willReturn(PlatformLoginResult.session(
                "new.access", "new.refresh", sessionId, adminId, "ADMIN", true, 900L));

        mockMvc.perform(post("/auth/platform/refresh")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"refreshToken\":\"old.refresh\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.access_token").value("new.access"))
                .andExpect(jsonPath("$.data.session_id").value(sessionId.toString()));
    }

    // -------------------------------------------------------------------------
    // B3 PR #8 — MFA-required envelope + /mfa/verify endpoint + refresh replay
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("POST /auth/platform/login — mfa_required envelope when mfa_enabled (no access_token)")
    void login_mfaRequiredEnvelope() throws Exception {
        UUID adminId = UUID.randomUUID();
        given(authService.login(any(LoginRequest.class), anyString(), any()))
                .willReturn(PlatformLoginResult.mfaRequired(adminId, "challenge.jwt", 300L));

        mockMvc.perform(post("/auth/platform/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"email\":\"a@kaori.io\",\"password\":\"correct-horse\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.mfa_required").value(true))
                .andExpect(jsonPath("$.data.mfa_challenge_token").value("challenge.jwt"))
                .andExpect(jsonPath("$.data.mfa_challenge_expires_in_sec").value(300))
                .andExpect(jsonPath("$.data.admin_id").value(adminId.toString()))
                // NO access_token / refresh_token / session_id at this leg.
                .andExpect(jsonPath("$.data.access_token").doesNotExist())
                .andExpect(jsonPath("$.data.refresh_token").doesNotExist());
    }

    @Test
    @DisplayName("POST /auth/platform/mfa/verify — happy path returns full session envelope")
    void verifyMfa_happyPath() throws Exception {
        UUID sessionId = UUID.randomUUID();
        UUID adminId   = UUID.randomUUID();
        given(authService.verifyMfaChallenge(any(MfaVerifyRequest.class), anyString(), any()))
                .willReturn(PlatformLoginResult.session(
                        "post.mfa.access", "post.mfa.refresh",
                        sessionId, adminId, "ADMIN", true, 900L));

        mockMvc.perform(post("/auth/platform/mfa/verify")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"mfaChallengeToken\":\"challenge.jwt\",\"code\":\"123456\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.access_token").value("post.mfa.access"))
                .andExpect(jsonPath("$.data.session_id").value(sessionId.toString()))
                .andExpect(jsonPath("$.data.mfa_required").value(false));
    }

    @Test
    @DisplayName("POST /auth/platform/mfa/verify — wrong code → 401 with code=AUTH.MFA_INVALID_CODE")
    void verifyMfa_wrongCode() throws Exception {
        willThrow(new InvalidCredentialsException("Invalid MFA code."))
                .given(authService).verifyMfaChallenge(any(), any(), any());

        mockMvc.perform(post("/auth/platform/mfa/verify")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"mfaChallengeToken\":\"challenge.jwt\",\"code\":\"000000\"}"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("AUTH.MFA_INVALID_CODE"));
    }

    @Test
    @DisplayName("POST /auth/platform/mfa/verify — expired challenge → 401 with code=AUTH.MFA_CHALLENGE_EXPIRED")
    void verifyMfa_expiredChallenge() throws Exception {
        willThrow(new MfaChallengeExpiredException("MFA challenge has expired."))
                .given(authService).verifyMfaChallenge(any(), any(), any());

        mockMvc.perform(post("/auth/platform/mfa/verify")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"mfaChallengeToken\":\"old.challenge\",\"code\":\"123456\"}"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("AUTH.MFA_CHALLENGE_EXPIRED"));
    }

    @Test
    @DisplayName("POST /auth/platform/mfa/verify — used / invalid challenge → 401 with code=AUTH.MFA_CHALLENGE_INVALID")
    void verifyMfa_invalidChallenge() throws Exception {
        // Default mapping for non-"invalid mfa code" InvalidCredentialsException
        // messages — covers used / mismatched / missing challenge cases.
        willThrow(new InvalidCredentialsException("MFA challenge already used or closed."))
                .given(authService).verifyMfaChallenge(any(), any(), any());

        mockMvc.perform(post("/auth/platform/mfa/verify")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"mfaChallengeToken\":\"used.challenge\",\"code\":\"123456\"}"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("AUTH.MFA_CHALLENGE_INVALID"));
    }

    @Test
    @DisplayName("POST /auth/platform/mfa/verify — bean validation rejects code != 6 digits")
    void verifyMfa_validation() throws Exception {
        mockMvc.perform(post("/auth/platform/mfa/verify")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"mfaChallengeToken\":\"challenge.jwt\",\"code\":\"123\"}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("POST /auth/platform/refresh — replay → 401 with code=AUTH.TOKEN_REPLAYED")
    void refresh_replayed() throws Exception {
        willThrow(new TokenReplayException("Refresh token has already been used."))
                .given(authService).refresh(any());

        mockMvc.perform(post("/auth/platform/refresh")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"refreshToken\":\"used.refresh\"}"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("AUTH.TOKEN_REPLAYED"));
    }
}
