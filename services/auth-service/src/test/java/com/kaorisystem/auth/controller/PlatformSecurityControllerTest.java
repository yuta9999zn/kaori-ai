package com.kaorisystem.auth.controller;

import com.kaorisystem.auth.model.AdminSession;
import com.kaorisystem.auth.service.AdminSecurityService;
import com.kaorisystem.auth.service.AdminSecurityService.AdminNotFoundException;
import com.kaorisystem.auth.service.AdminSecurityService.EnableResult;
import com.kaorisystem.auth.service.AdminSecurityService.InvalidTotpException;
import com.kaorisystem.auth.service.AdminSecurityService.MfaNotInitiatedException;
import com.kaorisystem.auth.service.AdminSecurityService.RevokeResult;
import com.kaorisystem.auth.service.AdminSecurityService.SessionNotFoundException;
import com.kaorisystem.auth.service.AdminSecurityService.VerifyResult;
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
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.willThrow;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(controllers = PlatformSecurityController.class,
            excludeAutoConfiguration = {
                org.springframework.boot.autoconfigure.security.servlet.SecurityAutoConfiguration.class
            })
@DisplayName("PlatformSecurityController — REST contract")
class PlatformSecurityControllerTest {

    @Autowired private MockMvc mockMvc;
    @MockBean  private AdminSecurityService securityService;

    private static final String ADMIN_ID = "00000000-0000-0000-0000-000000000001";

    // -------------------------------------------------------------------------
    // POST /mfa/enable
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("POST /mfa/enable — happy path returns secret + otpauth URL + warning")
    void enable_happyPath() throws Exception {
        given(securityService.enableMfa(eq(UUID.fromString(ADMIN_ID)), anyString()))
                .willReturn(new EnableResult("ABCDE", "otpauth://...", "Kaori", "a@x"));

        mockMvc.perform(post("/api/v1/platform/security/mfa/enable")
                        .header("X-User-ID", ADMIN_ID))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.secret").value("ABCDE"))
                .andExpect(jsonPath("$.data.otpauth_url").value("otpauth://..."))
                .andExpect(jsonPath("$.data.issuer").value("Kaori"))
                .andExpect(jsonPath("$.meta.warning").exists());
    }

    @Test
    @DisplayName("POST /mfa/enable — missing X-User-ID → 401")
    void enable_missingHeader() throws Exception {
        mockMvc.perform(post("/api/v1/platform/security/mfa/enable"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.title").value("Unauthenticated"));
    }

    @Test
    @DisplayName("POST /mfa/enable — non-UUID X-User-ID → 401")
    void enable_invalidHeader() throws Exception {
        mockMvc.perform(post("/api/v1/platform/security/mfa/enable")
                        .header("X-User-ID", "not-a-uuid"))
                .andExpect(status().isUnauthorized());
    }

    // -------------------------------------------------------------------------
    // POST /mfa/verify
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("POST /mfa/verify — correct code returns mfa_enabled=true")
    void verify_happyPath() throws Exception {
        given(securityService.verifyMfa(eq(UUID.fromString(ADMIN_ID)), eq("123456"), anyString()))
                .willReturn(new VerifyResult(true, Instant.parse("2026-04-26T08:00:00Z")));

        mockMvc.perform(post("/api/v1/platform/security/mfa/verify")
                        .header("X-User-ID", ADMIN_ID)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"code\":\"123456\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.mfa_enabled").value(true))
                .andExpect(jsonPath("$.data.verified_at").exists());
    }

    @Test
    @DisplayName("POST /mfa/verify — wrong code → 400")
    void verify_wrongCode() throws Exception {
        willThrow(new InvalidTotpException("Invalid or expired code."))
                .given(securityService).verifyMfa(any(), eq("000000"), any());

        mockMvc.perform(post("/api/v1/platform/security/mfa/verify")
                        .header("X-User-ID", ADMIN_ID)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"code\":\"000000\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.title").value("Invalid or expired code"));
    }

    @Test
    @DisplayName("POST /mfa/verify — secret not yet stashed → 409")
    void verify_notInitiated() throws Exception {
        willThrow(new MfaNotInitiatedException("call enable first"))
                .given(securityService).verifyMfa(any(), any(), any());

        mockMvc.perform(post("/api/v1/platform/security/mfa/verify")
                        .header("X-User-ID", ADMIN_ID)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"code\":\"123456\"}"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.title").value("MFA not initiated"));
    }

    @Test
    @DisplayName("POST /mfa/verify — non-6-digit code → 400 from bean validation")
    void verify_validation() throws Exception {
        mockMvc.perform(post("/api/v1/platform/security/mfa/verify")
                        .header("X-User-ID", ADMIN_ID)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"code\":\"abcdef\"}"))
                .andExpect(status().isBadRequest());

        mockMvc.perform(post("/api/v1/platform/security/mfa/verify")
                        .header("X-User-ID", ADMIN_ID)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"code\":\"12345\"}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("POST /mfa/verify — rate limit hit → 423 with lockout_remaining_seconds")
    void verify_lockout() throws Exception {
        willThrow(new com.kaorisystem.auth.service.AdminSecurityService.MfaVerifyLockedException(
                "Too many invalid MFA codes. Try again in 873 seconds.", 873L))
                .given(securityService).verifyMfa(any(), any(), any());

        mockMvc.perform(post("/api/v1/platform/security/mfa/verify")
                        .header("X-User-ID", ADMIN_ID)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"code\":\"000000\"}"))
                .andExpect(status().isLocked())
                .andExpect(jsonPath("$.title").value("Too many failed attempts"))
                .andExpect(jsonPath("$.status").value(423))
                .andExpect(jsonPath("$.lockout_remaining_seconds").value(873));
    }

    @Test
    @DisplayName("POST /mfa/verify — admin missing → 404")
    void verify_adminGone() throws Exception {
        willThrow(new AdminNotFoundException("nope"))
                .given(securityService).verifyMfa(any(), any(), any());

        mockMvc.perform(post("/api/v1/platform/security/mfa/verify")
                        .header("X-User-ID", ADMIN_ID)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"code\":\"123456\"}"))
                .andExpect(status().isNotFound());
    }

    // -------------------------------------------------------------------------
    // GET /sessions
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("GET /sessions — returns mapped rows; is_current uses X-Session-Id header")
    void listSessions_happyPath() throws Exception {
        UUID currentSession = UUID.randomUUID();
        UUID otherSession   = UUID.randomUUID();

        AdminSession s1 = new AdminSession();
        s1.setSessionId(currentSession);
        s1.setAdminId(UUID.fromString(ADMIN_ID));
        s1.setIpAddress("1.2.3.4");
        s1.setUserAgent("Chrome/120.0");
        s1.setDeviceLabel("Chrome on macOS");
        s1.setCreatedAt(Instant.parse("2026-04-26T08:00:00Z"));
        s1.setLastActiveAt(Instant.parse("2026-04-26T08:30:00Z"));

        AdminSession s2 = new AdminSession();
        s2.setSessionId(otherSession);
        s2.setAdminId(UUID.fromString(ADMIN_ID));
        s2.setIpAddress("5.6.7.8");
        s2.setCreatedAt(Instant.parse("2026-04-25T10:00:00Z"));
        s2.setLastActiveAt(Instant.parse("2026-04-25T10:00:00Z"));

        given(securityService.listActiveSessions(UUID.fromString(ADMIN_ID)))
                .willReturn(List.of(s1, s2));

        mockMvc.perform(get("/api/v1/platform/security/sessions")
                        .header("X-User-ID",    ADMIN_ID)
                        .header("X-Session-Id", currentSession.toString()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data", hasSize(2)))
                .andExpect(jsonPath("$.data[0].session_id").value(currentSession.toString()))
                .andExpect(jsonPath("$.data[0].is_current").value(true))
                .andExpect(jsonPath("$.data[0].device_label").value("Chrome on macOS"))
                .andExpect(jsonPath("$.data[1].session_id").value(otherSession.toString()))
                .andExpect(jsonPath("$.data[1].is_current").value(false));
    }

    @Test
    @DisplayName("GET /sessions — missing X-User-ID → 401")
    void listSessions_unauth() throws Exception {
        mockMvc.perform(get("/api/v1/platform/security/sessions"))
                .andExpect(status().isUnauthorized());
    }

    // -------------------------------------------------------------------------
    // DELETE /sessions/{id}
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("DELETE /sessions/{id} — happy path, signed_out=false when not current")
    void revoke_otherSession() throws Exception {
        UUID sessionId = UUID.randomUUID();
        Instant now = Instant.parse("2026-04-26T09:00:00Z");
        given(securityService.revokeSession(eq(UUID.fromString(ADMIN_ID)), eq(sessionId), anyString()))
                .willReturn(new RevokeResult(sessionId, now));

        mockMvc.perform(delete("/api/v1/platform/security/sessions/" + sessionId)
                        .header("X-User-ID", ADMIN_ID))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.session_id").value(sessionId.toString()))
                .andExpect(jsonPath("$.data.revoked_at").exists())
                .andExpect(jsonPath("$.meta.signed_out").value(false));
    }

    @Test
    @DisplayName("DELETE /sessions/{id} — signed_out=true when revoking own session")
    void revoke_selfSession() throws Exception {
        UUID sessionId = UUID.randomUUID();
        given(securityService.revokeSession(any(), eq(sessionId), any()))
                .willReturn(new RevokeResult(sessionId, Instant.now()));

        mockMvc.perform(delete("/api/v1/platform/security/sessions/" + sessionId)
                        .header("X-User-ID",    ADMIN_ID)
                        .header("X-Session-Id", sessionId.toString()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.meta.signed_out").value(true));
    }

    @Test
    @DisplayName("DELETE /sessions/{id} — IDOR / already-revoked → 404")
    void revoke_notFound() throws Exception {
        UUID sessionId = UUID.randomUUID();
        willThrow(new SessionNotFoundException("nope"))
                .given(securityService).revokeSession(any(), eq(sessionId), any());

        mockMvc.perform(delete("/api/v1/platform/security/sessions/" + sessionId)
                        .header("X-User-ID", ADMIN_ID))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.title").value("Session not found"));
    }

    @Test
    @DisplayName("DELETE /sessions/{id} — invalid UUID → 400")
    void revoke_invalidUuid() throws Exception {
        mockMvc.perform(delete("/api/v1/platform/security/sessions/not-a-uuid")
                        .header("X-User-ID", ADMIN_ID))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.title").value("Invalid session ID"));
    }

    // -------------------------------------------------------------------------
    // 3.3 — POST /sessions/revoke-others
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("POST /sessions/revoke-others — keeps current session, returns count")
    void revokeOthers_happyPath() throws Exception {
        UUID currentSession = UUID.randomUUID();
        Instant now = Instant.parse("2026-04-26T10:00:00Z");
        given(securityService.revokeOtherSessions(
                eq(UUID.fromString(ADMIN_ID)), eq(currentSession), anyString()))
                .willReturn(new com.kaorisystem.auth.service.AdminSecurityService.RevokeOthersResult(3, now));

        mockMvc.perform(post("/api/v1/platform/security/sessions/revoke-others")
                        .header("X-User-ID",    ADMIN_ID)
                        .header("X-Session-Id", currentSession.toString()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.revoked_count").value(3))
                .andExpect(jsonPath("$.data.kept_session_id").value(currentSession.toString()))
                .andExpect(jsonPath("$.data.revoked_at").exists());
    }

    @Test
    @DisplayName("POST /sessions/revoke-others — count=0 when no other active sessions")
    void revokeOthers_noOthers() throws Exception {
        UUID currentSession = UUID.randomUUID();
        given(securityService.revokeOtherSessions(any(), any(), any()))
                .willReturn(new com.kaorisystem.auth.service.AdminSecurityService.RevokeOthersResult(0, Instant.now()));

        mockMvc.perform(post("/api/v1/platform/security/sessions/revoke-others")
                        .header("X-User-ID",    ADMIN_ID)
                        .header("X-Session-Id", currentSession.toString()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.revoked_count").value(0));
    }

    @Test
    @DisplayName("POST /sessions/revoke-others — missing X-User-ID → 401")
    void revokeOthers_unauth() throws Exception {
        mockMvc.perform(post("/api/v1/platform/security/sessions/revoke-others"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @DisplayName("POST /sessions/revoke-others — malformed X-Session-Id treated as null (no session kept)")
    void revokeOthers_badSessionHeader() throws Exception {
        // null kept means everything gets revoked. Service returns whatever count.
        given(securityService.revokeOtherSessions(any(), org.mockito.ArgumentMatchers.isNull(), anyString()))
                .willReturn(new com.kaorisystem.auth.service.AdminSecurityService.RevokeOthersResult(2, Instant.now()));

        mockMvc.perform(post("/api/v1/platform/security/sessions/revoke-others")
                        .header("X-User-ID",    ADMIN_ID)
                        .header("X-Session-Id", "not-a-uuid"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.revoked_count").value(2));
    }
}
