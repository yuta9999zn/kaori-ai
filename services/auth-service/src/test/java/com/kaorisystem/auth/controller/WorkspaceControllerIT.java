package com.kaorisystem.auth.controller;

import com.kaorisystem.auth.service.WorkspaceMemberService;
import com.kaorisystem.auth.service.WorkspaceService;
import com.kaorisystem.auth.service.WorkspaceService.WorkspaceNotFoundException;
import com.kaorisystem.auth.service.WorkspaceService.WorkspacePage;
import com.kaorisystem.auth.service.WorkspaceService.WorkspaceView;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.data.redis.RedisAutoConfiguration;
import org.springframework.boot.autoconfigure.data.redis.RedisRepositoriesAutoConfiguration;
import org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration;
import org.springframework.boot.autoconfigure.mail.MailSenderAutoConfiguration;
import org.springframework.boot.autoconfigure.orm.jpa.HibernateJpaAutoConfiguration;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.security.web.FilterChainProxy;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.is;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Integration test for WorkspaceController.
 *
 * Boots the full Spring application context (@SpringBootTest) to verify:
 *   - controller ↔ service wiring via Spring DI
 *   - JSON serialization / deserialization round-trip
 *   - HTTP status codes
 *   - Jakarta Bean Validation is active
 *   - pagination query params are bound correctly
 *
 * Infrastructure excluded:
 *   - DataSource / JPA / Redis / Mail  (no external dependency needed for controller IT;
 *     service is mocked — "mock repo ok for now" per tracker)
 */
@SpringBootTest(
        properties = {
                "spring.autoconfigure.exclude=" +
                    "org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration," +
                    "org.springframework.boot.autoconfigure.orm.jpa.HibernateJpaAutoConfiguration," +
                    "org.springframework.boot.autoconfigure.data.redis.RedisAutoConfiguration," +
                    "org.springframework.boot.autoconfigure.data.redis.RedisRepositoriesAutoConfiguration," +
                    "org.springframework.boot.autoconfigure.mail.MailSenderAutoConfiguration"
        }
)
@TestPropertySource(properties = {
        "jwt.private-key=",
        "jwt.public-key=",
        "spring.main.allow-bean-definition-overriding=true"
})
@DisplayName("WorkspaceController — full-context integration tests")
class WorkspaceControllerIT {

    @Autowired private WebApplicationContext webContext;
    @Autowired private FilterChainProxy       springSecurityFilter;
    private MockMvc mockMvc;

    @BeforeEach
    void buildMockMvc() {
        // Inject trusted-gateway headers on every request so SecurityConfig's
        // role-based matcher on /api/v1/platform/** doesn't return 403.
        mockMvc = MockMvcBuilders.webAppContextSetup(webContext)
                .addFilters(springSecurityFilter)
                .defaultRequest(org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get("/")
                        .header("X-User-ID",       "00000000-0000-0000-0000-000000000001")
                        .header("X-User-Role",     "ADMIN")
                        .header("X-Enterprise-ID", "00000000-0000-0000-0000-000000000001"))
                .build();
    }

    @MockBean
    private WorkspaceService workspaceService;

    /** Required to satisfy WorkspaceController's constructor dependency added by F-008 expansion. */
    @MockBean
    private WorkspaceMemberService workspaceMemberService;

    @MockBean
    private com.kaorisystem.auth.service.WorkspaceKeyService workspaceKeyService;

    /** F-011 platform billing controller is auto-instantiated; its repo dep needs a mock. */
    @MockBean
    private com.kaorisystem.auth.repository.BillingAggregationRepository _billingAggRepo;

    /** Module 3 — PlatformSecurityController is auto-instantiated; AdminSessionRepository needs a mock. */
    @MockBean
    private com.kaorisystem.auth.repository.AdminSessionRepository _adminSessionRepo;

    /** 3.1.b — PlatformAdminAuditService depends on this JPA repo; mock so context loads with JPA excluded. */
    @MockBean
    private com.kaorisystem.auth.repository.PlatformAdminAuditLogRepository _adminAuditRepo;

    /** Issue #6 outbox — NotificationClient depends on NotificationOutboxRepository,
     *  which uses NamedParameterJdbcTemplate (no DataSource in this slice); mock the
     *  repo so the NotificationClient bean still wires. */
    @MockBean
    private com.kaorisystem.auth.repository.NotificationOutboxRepository _notifOutboxRepo;

    /** F-037 — alert_rules + alert_events repos use NamedParameterJdbcTemplate; mock
     *  so AlertRuleService + BillingAlertService context loads without a DataSource. */
    @MockBean
    private com.kaorisystem.auth.repository.AlertRuleRepository _alertRuleRepo;

    @MockBean
    private com.kaorisystem.auth.repository.AlertEventRepository _alertEventRepo;

    /** F-037 — BillingAlertService is auto-wired via BillingAggregationService;
     *  its dependencies (alertEvents/outbox/userRepo/jdbc) are already mocked,
     *  but mocking the service itself keeps the slice context fast. */
    @MockBean
    private com.kaorisystem.auth.service.BillingAlertService _billingAlertService;

    /** F-037 — AlertRuleService backs EnterpriseAlertController; mock so the
     *  controller's bean wires without pulling in JPA / JDBC at slice time. */
    @MockBean
    private com.kaorisystem.auth.service.AlertRuleService _alertRuleService;

    /** F-039 — RiskItemRepository uses NamedParameterJdbcTemplate; mock so
     *  RiskItemService context loads without a DataSource at slice time. */
    @MockBean
    private com.kaorisystem.auth.repository.RiskItemRepository _riskItemRepo;

    /** F-039 — RiskItemService backs EnterpriseRiskController; mock so the
     *  controller bean wires cleanly at slice time. */
    @MockBean
    private com.kaorisystem.auth.service.RiskItemService _riskItemService;

    /** F-040 — OkrRepository uses NamedParameterJdbcTemplate; mock so
     *  OkrService context loads without a DataSource at slice time. */
    @MockBean
    private com.kaorisystem.auth.repository.OkrRepository _okrRepo;

    /** F-040 — OkrService backs EnterpriseOkrController; mock so the
     *  controller bean wires cleanly at slice time. */
    @MockBean
    private com.kaorisystem.auth.service.OkrService _okrService;

    // -------------------------------------------------------------------------
    // Stubs for beans the @SpringBootTest context needs but this slice test
    // doesn't exercise. Required because the test excludes JPA/Redis/Mail
    // autoconfig (no DB / Redis / SMTP), so any @Service that depends on a
    // JPA repository would fail to wire without a mock.
    // The new *IT.java classes in com.kaorisystem.auth.it cover real-DB E2E.
    // -------------------------------------------------------------------------
    @MockBean private com.kaorisystem.auth.repository.UserRepository                       _userRepo;
    @MockBean private com.kaorisystem.auth.repository.PasswordResetTokenRepository         _resetTokenRepo;
    @MockBean private com.kaorisystem.auth.repository.WorkspaceKeyRepository               _keyRepo;
    @MockBean private com.kaorisystem.auth.repository.WorkspaceRepository                  _wsRepo;
    @MockBean private com.kaorisystem.auth.repository.WorkspaceAuditLogRepository          _auditRepo;
    @MockBean private com.kaorisystem.auth.repository.PlatformAdminRepository              _adminRepo;
    @MockBean private com.kaorisystem.auth.repository.PlatformAdminPasswordResetRepository _adminResetRepo;
    /** F-016 — TenantSettingsService depends on this JPA repo; mock so context loads with JPA excluded. */
    @MockBean private com.kaorisystem.auth.repository.TenantSettingsRepository             _tenantSettingsRepo;
    /** F-031 — BillingAggregationService depends on NamedParameterJdbcTemplate (no DataSource in this slice); mock the whole service so PlatformBillingController still wires. */
    @MockBean private com.kaorisystem.auth.service.BillingAggregationService               _billingAggService;
    /** B1 PR #1 — JobLeaseService depends on NamedParameterJdbcTemplate; mock so BillingAggregationJob constructor wires. */
    @MockBean private com.kaorisystem.auth.service.JobLeaseService                         _jobLeaseService;
    /** B1 PR #1 — OrphanJobSweeper @Component is auto-discovered and depends
     *  on NamedParameterJdbcTemplate (no DataSource in this slice); mock the
     *  whole bean so context loads. */
    @MockBean private com.kaorisystem.auth.scheduled.OrphanJobSweeper                      _orphanJobSweeper;
    /** B1 PR #2 — OutboxReconciliationJob @Component, same pattern as the
     *  orphan sweeper above. Mocking the whole bean keeps the slice context
     *  free of NamedParameterJdbcTemplate wiring. */
    @MockBean private com.kaorisystem.auth.scheduled.OutboxReconciliationJob               _outboxReconciliationJob;
    /** B3 PR #8 — PlatformAuthService now depends on this JPA repo for the
     *  MFA challenge flow; mock so context loads with JPA excluded. */
    @MockBean private com.kaorisystem.auth.repository.MfaChallengeRepository               _mfaChallengeRepo;
    /** Migration 024 prep — PlatformBillingService / WorkspaceService /
     *  PlatformStatsService now depend on this @Component to disable RLS for
     *  cross-tenant reads. Slice context excludes JdbcTemplate auto-config so
     *  the helper itself wouldn't construct; mocking it is enough. */
    @MockBean private com.kaorisystem.auth.service.RlsBypassHelper                         _rlsBypassHelper;
    /** F-030 — SubscriptionService depends on NamedParameterJdbcTemplate + SubscriptionChangeRequestRepository (JPA); mock both so EnterpriseSubscriptionController context loads. */
    @MockBean private com.kaorisystem.auth.service.SubscriptionService                     _subscriptionService;
    @MockBean private com.kaorisystem.auth.repository.SubscriptionChangeRequestRepository  _subscriptionChangeRequestRepo;
    /** Sprint 7 PR A — PlatformStatsService depends on JdbcTemplate (no DataSource in this slice); mock so PlatformStatsController still wires. */
    @MockBean private com.kaorisystem.auth.service.PlatformStatsService                    _platformStatsService;
    /** Sprint 7 PR B — AuthService + EnterpriseUserService depend on this client; mock so context loads without notification-service running. */
    @MockBean private com.kaorisystem.auth.service.NotificationClient                      _notificationClient;
    /** Sprint 7 PR B — EnterpriseUserService.invite() now uses JdbcTemplate to look up enterprise name; mock so context loads with no DataSource. */
    @MockBean private org.springframework.jdbc.core.JdbcTemplate                           _jdbcTemplate;
    /** Mocked so the test doesn't need valid RSA keys (jwt.private-key="" would fail Base64 decode). */
    @MockBean private com.kaorisystem.auth.security.JwtUtil                                _jwtUtil;
    @MockBean private org.springframework.data.redis.core.StringRedisTemplate              _redis;
    @MockBean private org.springframework.mail.javamail.JavaMailSender                     _mailSender;

    private static WorkspaceView workspace(UUID id, String name, String plan, String status) {
        Instant fixed = Instant.parse("2026-04-25T10:00:00Z");
        return new WorkspaceView(id, name, plan, "Retail", status, fixed, fixed);
    }

    // =========================================================================
    // GET /workspaces — context boots, controller wired, pagination works
    // =========================================================================

    @Test
    @DisplayName("Context loads and GET /workspaces returns JSON envelope with data + meta")
    void contextLoads_andListEndpointReturnsEnvelope() throws Exception {
        UUID id = UUID.randomUUID();
        given(workspaceService.list(isNull(), eq(50))).willReturn(
                new WorkspacePage(List.of(workspace(id, "Acme", "ENT_MID", "active")), null, 1L)
        );

        mockMvc.perform(get("/api/v1/platform/workspaces"))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.data").exists())
                .andExpect(jsonPath("$.meta").exists())
                .andExpect(jsonPath("$.data[0].workspace_id").value(id.toString()))
                .andExpect(jsonPath("$.data[0].plan_code").value("ENT_MID"))
                .andExpect(jsonPath("$.meta.total").value(1));

        verify(workspaceService, times(1)).list(isNull(), eq(50));
    }

    @Test
    @DisplayName("GET /workspaces?cursor=abc&limit=5 — service receives exact pagination args")
    void list_paginationArgsForwarded() throws Exception {
        given(workspaceService.list(eq("abc"), eq(5)))
                .willReturn(new WorkspacePage(List.of(), "next", 0L));

        mockMvc.perform(get("/api/v1/platform/workspaces")
                        .param("cursor", "abc")
                        .param("limit", "5"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.meta.cursor").value("next"));

        verify(workspaceService).list(eq("abc"), eq(5));
    }

    // =========================================================================
    // POST /workspaces — full serialization round-trip
    // =========================================================================

    @Test
    @DisplayName("POST /workspaces — body deserialized, service called, response serialized")
    void create_fullSerializationRoundTrip() throws Exception {
        UUID id = UUID.randomUUID();
        given(workspaceService.create(eq("Acme Ltd"), eq("ENT_MAX"), eq("Retail")))
                .willReturn(workspace(id, "Acme Ltd", "ENT_MAX", "active"));

        String body = """
                {"name":"Acme Ltd","plan_code":"ENT_MAX","industry":"Retail"}
                """;

        mockMvc.perform(post("/api/v1/platform/workspaces")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.data.workspace_id", is(id.toString())))
                .andExpect(jsonPath("$.data.name", is("Acme Ltd")))
                .andExpect(jsonPath("$.data.plan_code", is("ENT_MAX")))
                .andExpect(jsonPath("$.data.industry", is("Retail")))
                .andExpect(jsonPath("$.data.status", is("active")))
                .andExpect(jsonPath("$.data.created_at").exists())
                .andExpect(jsonPath("$.data.updated_at").exists());

        verify(workspaceService).create("Acme Ltd", "ENT_MAX", "Retail");
    }

    @Test
    @DisplayName("POST /workspaces — service normalizes plan_code to upper case and trims name")
    void create_serviceReceivesNormalizedInput() throws Exception {
        UUID id = UUID.randomUUID();
        given(workspaceService.create(eq("Acme"), eq("ENT_MID"), eq("Retail")))
                .willReturn(workspace(id, "Acme", "ENT_MID", "active"));

        String body = """
                {"name":"  Acme  ","plan_code":"ent_mid","industry":"  Retail  "}
                """;

        mockMvc.perform(post("/api/v1/platform/workspaces")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isCreated());

        verify(workspaceService).create("Acme", "ENT_MID", "Retail");
    }

    @Test
    @DisplayName("POST /workspaces — validation active in full context (missing name → 400)")
    void create_validationActive_returns400() throws Exception {
        mockMvc.perform(post("/api/v1/platform/workspaces")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"plan_code\":\"ENT_MID\"}"))
                .andExpect(status().isBadRequest());
    }

    // =========================================================================
    // PATCH /workspaces/{id}
    // =========================================================================

    @Test
    @DisplayName("PATCH /workspaces/{id} — plan upgrade flows through context end-to-end")
    void update_planUpgrade_200WithNewValues() throws Exception {
        UUID id = UUID.randomUUID();
        given(workspaceService.update(eq(id), isNull(), eq("ENT_MAX"), isNull()))
                .willReturn(workspace(id, "Acme", "ENT_MAX", "active"));

        mockMvc.perform(patch("/api/v1/platform/workspaces/" + id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"plan_code\":\"ENT_MAX\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.plan_code", is("ENT_MAX")))
                .andExpect(jsonPath("$.data.workspace_id", is(id.toString())));
    }

    @Test
    @DisplayName("PATCH /workspaces/{id} — status suspended persisted and serialized")
    void update_statusSuspended_200() throws Exception {
        UUID id = UUID.randomUUID();
        given(workspaceService.update(eq(id), isNull(), isNull(), eq("suspended")))
                .willReturn(workspace(id, "Acme", "ENT_MID", "suspended"));

        mockMvc.perform(patch("/api/v1/platform/workspaces/" + id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"status\":\"suspended\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.status", is("suspended")));
    }

    @Test
    @DisplayName("PATCH /workspaces/{id} — service throws NotFound → 404 Problem Details")
    void update_serviceThrowsNotFound_returns404() throws Exception {
        UUID id = UUID.randomUUID();
        willThrow(new WorkspaceNotFoundException("not found"))
                .given(workspaceService).update(eq(id), anyString(), any(), any());

        mockMvc.perform(patch("/api/v1/platform/workspaces/" + id)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"name\":\"Renamed\"}"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.type").exists())
                .andExpect(jsonPath("$.title").value("Workspace not found"))
                .andExpect(jsonPath("$.status").value(404));
    }

    // =========================================================================
    // DELETE /workspaces/{id}
    // =========================================================================

    @Test
    @DisplayName("DELETE /workspaces/{id} — soft delete round-trip returns status=inactive")
    void softDelete_roundTrip_200() throws Exception {
        UUID id = UUID.randomUUID();
        given(workspaceService.softDelete(eq(id)))
                .willReturn(workspace(id, "Acme", "ENT_MID", "inactive"));

        mockMvc.perform(delete("/api/v1/platform/workspaces/" + id))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.workspace_id", is(id.toString())))
                .andExpect(jsonPath("$.data.status", is("inactive")));

        verify(workspaceService).softDelete(id);
    }

    @Test
    @DisplayName("DELETE /workspaces/{id} — unknown id → 404 Problem Details envelope")
    void softDelete_notFound_returnsProblemDetails404() throws Exception {
        UUID id = UUID.randomUUID();
        willThrow(new WorkspaceNotFoundException("not found"))
                .given(workspaceService).softDelete(eq(id));

        mockMvc.perform(delete("/api/v1/platform/workspaces/" + id))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.title").value("Workspace not found"))
                .andExpect(jsonPath("$.status").value(404));
    }

    // =========================================================================
    // Suppress unused-import warnings for the excluded-autoconfig class refs.
    // They are used at the string level inside @SpringBootTest(properties=…)
    // but we import them so a typo in the FQN would fail at compile time.
    // =========================================================================
    @SuppressWarnings("unused")
    private static final Class<?>[] EXCLUDED_FOR_REFERENCE = {
            DataSourceAutoConfiguration.class,
            HibernateJpaAutoConfiguration.class,
            RedisAutoConfiguration.class,
            RedisRepositoriesAutoConfiguration.class,
            MailSenderAutoConfiguration.class
    };

    @SuppressWarnings("unused")
    private static void ignoreUnused() {
        // keep `anyInt` import — used by sibling slice test; referenced here for parity
        anyInt();
    }
}
