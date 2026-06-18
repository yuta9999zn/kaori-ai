package com.kaorisystem.auth.it;

import com.fasterxml.jackson.databind.JsonNode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.web.servlet.MvcResult;

import java.time.Instant;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Batch 3.1.a — End-to-end platform admin authentication flow.
 *
 * Covers: login → session row created → list-sessions → force idle expiry →
 * filter returns 401 with reason='idle_timeout' → DB row reflects revoked
 * state with the same reason.
 */
@DisplayName("E2E — Platform admin login + session lifecycle + idle timeout")
class PlatformAuthFlowIT extends AbstractIntegrationIT {

    @Autowired private JdbcTemplate     jdbc;
    @Autowired private PasswordEncoder  passwordEncoder;

    private final String runId = UUID.randomUUID().toString().substring(0, 8);
    private String adminId;
    private String adminEmail;
    private final String password = "Sup3rSecret-" + System.nanoTime();

    @BeforeEach
    void seedAdmin() {
        adminId    = UUID.randomUUID().toString();
        adminEmail = "platform-auth-" + runId + "@kaori.io";
        jdbc.update("""
                INSERT INTO platform_admins
                    (admin_id, email, full_name, role, is_active, mfa_enabled, password_hash)
                VALUES (?::uuid, ?, 'Auth IT', 'ADMIN', true, false, ?)
                """, adminId, adminEmail, passwordEncoder.encode(password));
    }

    // -------------------------------------------------------------------------
    // login
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("login → returns access/refresh + session_id; admin_sessions row created")
    void login_createsSession() throws Exception {
        MvcResult res = mockMvc.perform(post("/auth/platform/login")
                        .header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) Chrome/120.0")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"email":"%s","password":"%s"}
                                """.formatted(adminEmail, password)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.access_token").exists())
                .andExpect(jsonPath("$.data.refresh_token").exists())
                .andExpect(jsonPath("$.data.session_id").exists())
                .andExpect(jsonPath("$.data.role").value("ADMIN"))
                .andExpect(jsonPath("$.data.mfa_enabled").value(false))
                .andReturn();

        String sessionId = objectMapper.readTree(res.getResponse().getContentAsString())
                .get("data").get("session_id").asText();

        // DB row exists, active, with parsed device label
        Integer count = jdbc.queryForObject(
                "SELECT COUNT(*) FROM admin_sessions WHERE session_id=?::uuid AND admin_id=?::uuid AND revoked_at IS NULL",
                Integer.class, sessionId, adminId);
        assertThat(count).isEqualTo(1);

        String deviceLabel = jdbc.queryForObject(
                "SELECT device_label FROM admin_sessions WHERE session_id=?::uuid",
                String.class, sessionId);
        assertThat(deviceLabel).isEqualTo("Chrome trên macOS");
    }

    @Test
    @DisplayName("login — wrong password → 401 RFC 7807")
    void login_badPassword() throws Exception {
        mockMvc.perform(post("/auth/platform/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"email":"%s","password":"obviously-wrong-password"}
                                """.formatted(adminEmail)))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.title").value("Invalid credentials"));
    }

    @Test
    @DisplayName("login — unknown email → 401 (no enumeration)")
    void login_unknownEmail() throws Exception {
        mockMvc.perform(post("/auth/platform/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"email":"nobody-%s@kaori.io","password":"%s"}
                                """.formatted(runId, password)))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.title").value("Invalid credentials"));
    }

    // -------------------------------------------------------------------------
    // session enforcement via the filter
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("Idle timeout enforced by filter: forced last_active=31m ago → 401 idle_timeout, DB row revoked")
    void idleTimeout_enforcedByFilter() throws Exception {
        // Login creates the session
        MvcResult login = mockMvc.perform(post("/auth/platform/login")
                        .header("User-Agent", "Chrome/120.0")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"email":"%s","password":"%s"}
                                """.formatted(adminEmail, password)))
                .andExpect(status().isOk()).andReturn();
        JsonNode env = objectMapper.readTree(login.getResponse().getContentAsString());
        String sessionId = env.get("data").get("session_id").asText();

        // Force last_active 31 minutes in the past
        jdbc.update("""
                UPDATE admin_sessions
                   SET last_active_at = NOW() - INTERVAL '31 minutes'
                 WHERE session_id = ?::uuid
                """, sessionId);
        // Note: Redis is mocked at AbstractIntegrationIT (StringRedisTemplate
        // returns null on get/set). So no "valid" verdict is cached from login,
        // and the next request will read the DB and detect the stale row.

        // Now hit a guarded endpoint — filter will validate the session and
        // detect idle expiry.
        mockMvc.perform(get("/api/v1/platform/security/sessions")
                        .header("X-User-ID",    adminId)
                        .header("X-User-Role",  "ADMIN")
                        .header("X-User-Email", adminEmail)
                        .header("X-Session-Id", sessionId))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.title").value("Session expired (idle)"))
                .andExpect(jsonPath("$.reason").value("idle_timeout"));

        // DB row is now revoked with the right reason
        String reason = jdbc.queryForObject(
                "SELECT revoke_reason FROM admin_sessions WHERE session_id=?::uuid", String.class, sessionId);
        assertThat(reason).isEqualTo("idle_timeout");
        Instant revokedAt = jdbc.queryForObject(
                "SELECT revoked_at FROM admin_sessions WHERE session_id=?::uuid",
                java.sql.Timestamp.class, sessionId).toInstant();
        assertThat(revokedAt).isNotNull();
    }

    @Test
    @DisplayName("Absolute timeout enforced by filter: forced created_at=25h ago → 401 absolute_timeout")
    void absoluteTimeout_enforcedByFilter() throws Exception {
        // Seed a fresh session directly (skip login HTTP path)
        UUID sessionId = UUID.randomUUID();
        jdbc.update("""
                INSERT INTO admin_sessions (session_id, admin_id, created_at, last_active_at)
                VALUES (?::uuid, ?::uuid, NOW() - INTERVAL '25 hours', NOW())
                """, sessionId, adminId);

        mockMvc.perform(get("/api/v1/platform/security/sessions")
                        .header("X-User-ID",    adminId)
                        .header("X-User-Role",  "ADMIN")
                        .header("X-Session-Id", sessionId.toString()))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.title").value("Session expired (max duration)"))
                .andExpect(jsonPath("$.reason").value("absolute_timeout"));

        String reason = jdbc.queryForObject(
                "SELECT revoke_reason FROM admin_sessions WHERE session_id=?::uuid",
                String.class, sessionId.toString());
        assertThat(reason).isEqualTo("absolute_timeout");
    }

    @Test
    @DisplayName("Active session: filter touches last_active_at on each request")
    void activeSession_touchesLastActive() throws Exception {
        MvcResult login = mockMvc.perform(post("/auth/platform/login")
                        .header("User-Agent", "Chrome/120.0")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"email":"%s","password":"%s"}
                                """.formatted(adminEmail, password)))
                .andExpect(status().isOk()).andReturn();
        String sessionId = objectMapper.readTree(login.getResponse().getContentAsString())
                .get("data").get("session_id").asText();

        // Force last_active_at to a fixed past instant we can observe
        jdbc.update("""
                UPDATE admin_sessions SET last_active_at = NOW() - INTERVAL '5 minutes'
                 WHERE session_id = ?::uuid
                """, sessionId);
        Instant beforeRequest = jdbc.queryForObject(
                "SELECT last_active_at FROM admin_sessions WHERE session_id=?::uuid",
                java.sql.Timestamp.class, sessionId).toInstant();

        mockMvc.perform(get("/api/v1/platform/security/sessions")
                        .header("X-User-ID",    adminId)
                        .header("X-User-Role",  "ADMIN")
                        .header("X-Session-Id", sessionId))
                .andExpect(status().isOk());

        Instant afterRequest = jdbc.queryForObject(
                "SELECT last_active_at FROM admin_sessions WHERE session_id=?::uuid",
                java.sql.Timestamp.class, sessionId).toInstant();
        assertThat(afterRequest).isAfter(beforeRequest);
    }
}
