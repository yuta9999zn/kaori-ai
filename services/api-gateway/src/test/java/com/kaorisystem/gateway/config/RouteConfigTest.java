package com.kaorisystem.gateway.config;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.cloud.gateway.route.Route;
import org.springframework.cloud.gateway.route.RouteLocator;
import org.springframework.context.annotation.Import;
import org.springframework.mock.http.server.reactive.MockServerHttpRequest;
import org.springframework.mock.web.server.MockServerWebExchange;
import org.springframework.test.context.TestPropertySource;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Routing-correctness regression guards.
 *
 * Loads only the gateway autoconfig (no Redis, no R2DBC, no JWT filter)
 * so the real Spring Cloud Gateway predicate factories are wired up; the
 * production RouteConfig builds against the real RouteLocatorBuilder.
 *
 * Asserts:
 *   1. every expected route ID is registered;
 *   2. each frontend-visible URL pattern resolves to the right backend.
 *
 * If anyone reorders or drops a route, one of these tests fails fast.
 */
@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        classes = RouteConfigTest.GatewayTestConfig.class,
        properties = {
                // Keep the test surface tiny — exclude every data-access
                // autoconfig the production app imports. We only need the
                // gateway's predicate / filter factories.
                "spring.autoconfigure.exclude=" +
                    "org.springframework.boot.autoconfigure.r2dbc.R2dbcAutoConfiguration," +
                    "org.springframework.boot.autoconfigure.data.r2dbc.R2dbcRepositoriesAutoConfiguration," +
                    "org.springframework.boot.autoconfigure.r2dbc.R2dbcDataAutoConfiguration," +
                    "org.springframework.boot.autoconfigure.r2dbc.R2dbcTransactionManagerAutoConfiguration," +
                    "org.springframework.boot.autoconfigure.data.redis.RedisAutoConfiguration," +
                    "org.springframework.boot.autoconfigure.data.redis.RedisReactiveAutoConfiguration," +
                    "org.springframework.boot.autoconfigure.data.redis.RedisRepositoriesAutoConfiguration",
                "kaori.services.auth-url=http://auth-service:8091",
                "kaori.services.pipeline-url=http://data-pipeline:8092",
                "kaori.services.orchestrator-url=http://ai-orchestrator:8093",
        }
)
@DisplayName("RouteConfig — gateway routing matrix")
class RouteConfigTest {

    private static final String AUTH_URL = "http://auth-service:8091";
    private static final String PIPE_URL = "http://data-pipeline:8092";
    private static final String ORCH_URL = "http://ai-orchestrator:8093";

    /** Minimal test context: load only RouteConfig, skip the JWT/RateLimit/etc filters. */
    @SpringBootApplication
    @Import(RouteConfig.class)
    static class GatewayTestConfig {}

    @Autowired
    private RouteLocator routeLocator;

    private List<Route> routes() {
        List<Route> rs = routeLocator.getRoutes().collectList().block();
        assertThat(rs).isNotNull();
        return rs;
    }

    // ─── Route inventory ──────────────────────────────────────────────────

    @Test
    @DisplayName("expected route IDs are all registered")
    void allExpectedRouteIdsPresent() {
        Set<String> ids = routes().stream().map(Route::getId).collect(Collectors.toSet());
        assertThat(ids).containsExactlyInAnyOrder(
            "auth-public",
            // P2-AUTH-001 SSO — OAuth start + callback for /api/v1/p2/auth/sso/**.
            "sso-public",
            "health",
            // Dedicated long-timeout route for large file uploads (300s);
            // declared before "pipeline" so /api/v1/upload matches it first.
            "pipeline-upload",
            // Dedicated 120s route for heavy steps /schema + /clean
            // (multi-sheet sniff + Silver write), before "pipeline".
            "pipeline-heavy",
            "pipeline",
            "analytics",
            // F-060 — customer at-risk list/action endpoints on
            // ai-orchestrator north_star.py. Mounted at /api/v1/customers/**
            // so /p2/customers/at-risk has a BE to talk to.
            "customers",
            // F-033 — multi-tier analysis, mounted at /api/v1/analysis/**
            // (different prefix from /analytics so the legacy wizard runner
            // endpoint stays untouched).
            "multi-tier-analysis",
            // F-041 — explainability layer at /api/v1/explainability/**.
            "explainability",
            // EU AI Act — compliance risk register at /api/v1/compliance/**
            // (compliance_risk.py: POST/GET /compliance/ai-uses) on
            // ai-orchestrator. Without it the feature 404s at the edge.
            "compliance",
            // Operational Economics — NOV + ROI moat dashboard at
            // /api/v1/economics/** on ai-orchestrator (2026-06-05).
            "economics",
            // Analysis frameworks (SWOT/6W/2H/Fishbone) + reports (F-038) on
            // ai-orchestrator — re-baseline 2026-06-01 (were unreachable: no edge route).
            "frameworks-reports",
            // F-061 — shared services bucket. /api/v1/shared/agents/* now;
            // F-062 guardrails + F-063 external-AI gateway will share this
            // catchall.
            "shared",
            "insights",
            "dashboard-billing",
            "users",
            // P15-S11 Tuần 8 — corporate hierarchy + workflow builder +
            // RBAC role templates + customer/vendor read APIs on
            // ai-orchestrator. Single big route bucket.
            "corporate-tree",
            // CR-0019 — platform LLM/AI ops + tuning config on ai-orchestrator,
            // ahead of the auth-service platform catch-all.
            "platform-llm",
            // 3.2.b — single catchall replaces platform-keys + platform-workspaces.
            // Covers /api/v1/platform/{keys,workspaces,admins,billing,security,...}/**
            "platform"
        );
    }

    // ─── Frontend → backend resolution ────────────────────────────────────

    @Test
    @DisplayName("auth + workspace activation paths land on auth-service")
    void authPathsGoToAuthService() {
        assertResolvesTo("/auth/login",                    AUTH_URL);
        assertResolvesTo("/auth/forgot-password",          AUTH_URL);
        assertResolvesTo("/auth/workspace/activate/abc",   AUTH_URL);
        // P2-AUTH-001 — exchange endpoint also lives on auth-service
        assertResolvesTo("/auth/sso/exchange",             AUTH_URL);
    }

    @Test
    @DisplayName("P2-AUTH-001 SSO start/callback land on ai-orchestrator")
    void ssoOauthPathsGoToOrchestrator() {
        assertResolvesTo("/api/v1/p2/auth/sso/google/start",     ORCH_URL);
        assertResolvesTo("/api/v1/p2/auth/sso/google/callback",  ORCH_URL);
        assertResolvesTo("/api/v1/p2/auth/sso/microsoft/start",  ORCH_URL);
        assertResolvesTo("/api/v1/p2/auth/sso/exchange-info",    ORCH_URL);
    }

    @Test
    @DisplayName("pipeline wizard paths land on data-pipeline")
    void pipelinePathsGoToDataPipeline() {
        assertResolvesTo("/api/v1/upload",                 PIPE_URL);
        assertResolvesTo("/api/v1/upload/abc/status",      PIPE_URL);
        assertResolvesTo("/api/v1/schema",                 PIPE_URL);
        assertResolvesTo("/api/v1/schema/confirm",         PIPE_URL);
        assertResolvesTo("/api/v1/clean/suggestions",      PIPE_URL);
        assertResolvesTo("/api/v1/clean/apply",            PIPE_URL);
    }

    @Test
    @DisplayName("/analyze + /results route to data-pipeline (NOT orchestrator)")
    void analyzeAndResultsGoToDataPipeline() {
        // These previously routed to ai-orchestrator by mistake; the handlers
        // live in data-pipeline. Regression guard for that fix.
        assertResolvesTo("/api/v1/analyze",                PIPE_URL);
        assertResolvesTo("/api/v1/results/abc",            PIPE_URL);
    }

    @Test
    @DisplayName("F-NEW3 — /api/v1/data/** routes to data-pipeline")
    void dataExplorerGoesToDataPipeline() {
        // F-NEW3 hub overview lives in data-pipeline (routers/data_explorer.py).
        // Future drill-down endpoints under /data/** will sit here too — the
        // pipeline route uses /api/v1/data/** so adding new sub-paths needs
        // no further routing change.
        assertResolvesTo("/api/v1/data/explorer",          PIPE_URL);
    }

    @Test
    @DisplayName("P15-S11 Hướng A — /api/v1/role-templates + /departments/{id}/role-template route to ai-orchestrator")
    void roleTemplatesGoToOrchestrator() {
        // mig 061 — onboarding approval flow asks ai-orchestrator for the
        // suggested role when a new employee record lands. Regression
        // guard so adding new role-template endpoints under the same root
        // doesn't accidentally route to auth-service.
        assertResolvesTo("/api/v1/role-templates",                              ORCH_URL);
        assertResolvesTo("/api/v1/role-templates?dept_type=finance",            ORCH_URL);
        assertResolvesTo("/api/v1/departments/" +
                         "33333333-3333-3333-3333-333333333333/role-template",  ORCH_URL);
    }

    @Test
    @DisplayName("P15-S11 Hướng A — /api/v1/enterprise-users/{id}/role routes to ai-orchestrator")
    void enterpriseUsersGoToOrchestrator() {
        // PATCH endpoint that applies a templated or override role +
        // writes a workspace_audit_log row. Auth-service owns user
        // CRUD under /api/v1/users, but role-write goes through
        // ai-orchestrator so the template lookup + audit happen
        // server-side in one transaction.
        assertResolvesTo("/api/v1/enterprise-users/" +
                         "44444444-4444-4444-4444-444444444444/role",           ORCH_URL);
    }

    @Test
    @DisplayName("P15-S11 — customer/vendor/contract paths route to ai-orchestrator")
    void customersAndVendorsGoToOrchestrator() {
        // Mig 062/063 — customer + vendor + contracts read APIs land on
        // ai-orchestrator. Regression guard so the FE list/detail pages
        // don't 404 at the gateway after a deploy.
        assertResolvesTo("/api/v1/customers",                                   ORCH_URL);
        assertResolvesTo("/api/v1/customers/" +
                         "55555555-5555-5555-5555-555555555555",                ORCH_URL);
        assertResolvesTo("/api/v1/vendors",                                     ORCH_URL);
        assertResolvesTo("/api/v1/vendors/" +
                         "66666666-6666-6666-6666-666666666666",                ORCH_URL);
        assertResolvesTo("/api/v1/customer-contracts?status=active",            ORCH_URL);
        assertResolvesTo("/api/v1/vendor-contracts?status=active",              ORCH_URL);

        // ADR-0037 Tier-3 — documents / contracts / approvals / RBAC land on
        // ai-orchestrator. Regression guard so the new FE pages don't 404.
        assertResolvesTo("/api/v1/contracts?status=cho_ky",                     ORCH_URL);
        assertResolvesTo("/api/v1/contracts/" +
                         "77777777-7777-7777-7777-777777777777/sign",           ORCH_URL);
        assertResolvesTo("/api/v1/approval-inbox",                              ORCH_URL);
        assertResolvesTo("/api/v1/approval-chains",                             ORCH_URL);
        assertResolvesTo("/api/v1/user-department-roles?department_id=x",       ORCH_URL);
        assertResolvesTo("/api/v1/workflow-runs/" +
                         "88888888-8888-8888-8888-888888888888/approve",        ORCH_URL);
        // K-23 EU AI Act human oversight — POST /workflow-runs/{id}/stop is
        // covered by the same /api/v1/workflow-runs/** prefix.
        assertResolvesTo("/api/v1/workflow-runs/" +
                         "88888888-8888-8888-8888-888888888888/stop",           ORCH_URL);
        assertResolvesTo("/api/v1/workflow-documents/" +
                         "99999999-9999-9999-9999-999999999999/download",       ORCH_URL);
        // ADR-0039 enterprise Document Repository / DMS
        assertResolvesTo("/api/v1/document-folders",                            ORCH_URL);
        assertResolvesTo("/api/v1/document-folders/" +
                         "11111111-1111-1111-1111-111111111111/files",          ORCH_URL);
        assertResolvesTo("/api/v1/document-repository/search?q=x",              ORCH_URL);
        // Mig 138 — business-date metadata + virtual timeline
        assertResolvesTo("/api/v1/document-repository/timeline?granularity=year", ORCH_URL);
        assertResolvesTo("/api/v1/document-repository/" +
                         "99999999-9999-9999-9999-999999999999",                ORCH_URL);
        // ADR-0042 — doc-type templates + folder-as-page + index + insights
        assertResolvesTo("/api/v1/document-templates",                          ORCH_URL);
        assertResolvesTo("/api/v1/document-templates/" +
                         "77777777-7777-7777-7777-777777777777",                ORCH_URL);
        assertResolvesTo("/api/v1/document-folders/" +
                         "11111111-1111-1111-1111-111111111111/page",           ORCH_URL);
        assertResolvesTo("/api/v1/document-repository/index?limit=10",         ORCH_URL);
        assertResolvesTo("/api/v1/document-repository/insights",                ORCH_URL);
    }

    @Test
    @DisplayName("EU AI Act — /api/v1/compliance/** lands on ai-orchestrator")
    void compliancePathsGoToOrchestrator() {
        // compliance_risk.py — POST classifies a workflow's AI use into a risk
        // tier, GET lists the tenant register. Regression guard so the new
        // /compliance/ai-uses endpoints don't 404 at the gateway after deploy.
        assertResolvesTo("/api/v1/compliance/ai-uses",     ORCH_URL);
        assertResolvesTo("/api/v1/compliance/ai-uses?tier=high", ORCH_URL);
    }

    @Test
    @DisplayName("operational economics NOV/ROI lands on ai-orchestrator")
    void economicsPathsGoToOrchestrator() {
        // economics.py + roi_billing.py — the /p2/economics moat dashboard.
        // Regression guard: without this route the page 503s at the edge.
        assertResolvesTo("/api/v1/economics/nov/current",      ORCH_URL);
        assertResolvesTo("/api/v1/economics/nov/trend?months=6", ORCH_URL);
        assertResolvesTo("/api/v1/economics/roi/subscription", ORCH_URL);
    }

    @Test
    @DisplayName("ADR-0026 industry bootstrap lands on ai-orchestrator")
    void industryBootstrapPathsGoToOrchestrator() {
        // industry_bootstrap.py — lists industries + dry-run/apply bootstrap.
        // Regression guard: /p2 industry library + bootstrap-preview 503'd at
        // the edge because /api/v1/industries had no route (2026-06-05 fix).
        assertResolvesTo("/api/v1/industries",                              ORCH_URL);
        assertResolvesTo("/api/v1/industries/abc",                          ORCH_URL);
        assertResolvesTo("/api/v1/enterprises/abc/bootstrap-from-industry", ORCH_URL);
    }

    @Test
    @DisplayName("analytics dashboards land on ai-orchestrator")
    void analyticsPathsGoToOrchestrator() {
        assertResolvesTo("/api/v1/analytics/templates",    ORCH_URL);
        assertResolvesTo("/api/v1/analytics/runs",         ORCH_URL);
        assertResolvesTo("/api/v1/analytics/runs/abc",     ORCH_URL);
    }

    @Test
    @DisplayName("F-061 knowledge base paths land on ai-orchestrator")
    void knowledgeBasePathsGoToOrchestrator() {
        assertResolvesTo("/api/v1/knowledge-base/documents",  ORCH_URL);
        assertResolvesTo("/api/v1/knowledge-base/search",     ORCH_URL);
    }

    @Test
    @DisplayName("dashboard + billing summary routes land on ai-orchestrator")
    void dashboardAndBillingGoToOrchestrator() {
        // Without the dashboard-billing route the frontend's main dashboard
        // call (/api/v1/dashboard/state) and quota gauge (/api/v1/billing/summary)
        // 404 at the gateway. Regression guard.
        assertResolvesTo("/api/v1/dashboard/state",        ORCH_URL);
        assertResolvesTo("/api/v1/billing/summary",        ORCH_URL);
    }

    @Test
    @DisplayName("F-061 — /api/v1/shared/agents/** routes to ai-orchestrator")
    void sharedAgentsGoToOrchestrator() {
        // Both endpoint variants should land on ai-orchestrator.
        // F-062 guardrails + F-063 external-AI gateway will reuse this
        // route — adding new /shared/* sub-paths needs no further config.
        assertResolvesTo("/api/v1/shared/agents/sessions",                          ORCH_URL);
        assertResolvesTo("/api/v1/shared/agents/workflows/insight-to-action/invoke", ORCH_URL);
    }

    @Test
    @DisplayName("insights + strategy + ai paths land on ai-orchestrator")
    void insightsPathsGoToOrchestrator() {
        assertResolvesTo("/api/v1/insights/feed",          ORCH_URL);
        assertResolvesTo("/api/v1/strategy/ask",           ORCH_URL);
        assertResolvesTo("/api/v1/ai/query",               ORCH_URL);
    }

    @Test
    @DisplayName("frameworks + reports paths land on ai-orchestrator (re-baseline 2026-06-01)")
    void frameworksReportsPathsGoToOrchestrator() {
        assertResolvesTo("/api/v1/frameworks/templates",   ORCH_URL);
        assertResolvesTo("/api/v1/frameworks/generate",    ORCH_URL);
        assertResolvesTo("/api/v1/reports",                ORCH_URL);
    }

    @Test
    @DisplayName("CR-0019: /platform/llm/** lands on ai-orchestrator (ahead of platform catchall)")
    void platformLlmPathsGoToOrchestrator() {
        assertResolvesTo("/api/v1/platform/llm/config",                 ORCH_URL);
        assertResolvesTo("/api/v1/platform/llm/config/grounding_tolerance", ORCH_URL);
        assertResolvesTo("/api/v1/platform/llm/catalog/providers",      ORCH_URL);
        // sibling platform paths must STILL fall through to auth-service
        assertResolvesTo("/api/v1/platform/workspaces",                 AUTH_URL);
    }

    @Test
    @DisplayName("platform admin paths land on auth-service (3.2.b catchall)")
    void platformPathsGoToAuthService() {
        // Existing — F-009 flat keys
        assertResolvesTo("/api/v1/platform/keys",                       AUTH_URL);
        assertResolvesTo("/api/v1/platform/keys/abc",                   AUTH_URL);
        // F-008 workspace CRUD + nested keys (F-009)
        assertResolvesTo("/api/v1/platform/workspaces",                 AUTH_URL);
        assertResolvesTo("/api/v1/platform/workspaces/abc",             AUTH_URL);
        assertResolvesTo("/api/v1/platform/workspaces/abc/keys",        AUTH_URL);
        assertResolvesTo("/api/v1/platform/workspaces/abc/billing",     AUTH_URL);
        // F-010 admins
        assertResolvesTo("/api/v1/platform/admins",                     AUTH_URL);
        assertResolvesTo("/api/v1/platform/admins/abc",                 AUTH_URL);
        assertResolvesTo("/api/v1/platform/admins/abc/reset-password",  AUTH_URL);
        // F-011 platform billing
        assertResolvesTo("/api/v1/platform/billing/overview",           AUTH_URL);
        assertResolvesTo("/api/v1/platform/billing/quota",              AUTH_URL);
        assertResolvesTo("/api/v1/platform/billing/enterprises/abc",    AUTH_URL);
        assertResolvesTo("/api/v1/platform/billing/export",             AUTH_URL);
        // Module 3 + 3.1.b platform security
        assertResolvesTo("/api/v1/platform/security/mfa/enable",        AUTH_URL);
        assertResolvesTo("/api/v1/platform/security/mfa/verify",        AUTH_URL);
        assertResolvesTo("/api/v1/platform/security/sessions",          AUTH_URL);
        assertResolvesTo("/api/v1/platform/security/sessions/abc",      AUTH_URL);
    }

    @Test
    @DisplayName("3.1.a: /auth/platform/login lands on auth-service via /auth/** route")
    void platformLoginGoesToAuthService() {
        assertResolvesTo("/auth/platform/login",                        AUTH_URL);
        assertResolvesTo("/auth/platform/refresh",                      AUTH_URL);
    }

    @Test
    @DisplayName("user management paths land on auth-service")
    void userPathsGoToAuthService() {
        assertResolvesTo("/api/v1/users/abc",              AUTH_URL);
        assertResolvesTo("/api/v1/enterprises/abc",        AUTH_URL);
        assertResolvesTo("/api/v1/workspaces/abc",         AUTH_URL);
        assertResolvesTo("/api/v1/settings/profile",       AUTH_URL);
    }

    // ─── Negative cases ───────────────────────────────────────────────────

    @Test
    @DisplayName("unknown paths match no route (gateway returns 404)")
    void unknownPathsMatchNothing() {
        assertResolvesToNothing("/totally/unknown");
        assertResolvesToNothing("/api/v2/anything");
        assertResolvesToNothing("/api/v1/nonexistent/foo");
    }

    // ─── helpers ──────────────────────────────────────────────────────────

    private void assertResolvesTo(String path, String expectedBackend) {
        ServerWebExchange exchange = mockExchange(path);
        Route matched = routes().stream()
                .filter(r -> matches(r, exchange))
                .findFirst()
                .orElse(null);
        assertThat(matched)
                .as("path %s should match a route", path)
                .isNotNull();
        assertThat(matched.getUri().toString())
                .as("path %s should resolve to %s", path, expectedBackend)
                .isEqualTo(expectedBackend);
    }

    private void assertResolvesToNothing(String path) {
        ServerWebExchange exchange = mockExchange(path);
        boolean anyMatch = routes().stream().anyMatch(r -> matches(r, exchange));
        assertThat(anyMatch)
                .as("path %s should not match any route", path)
                .isFalse();
    }

    /** AsyncPredicate.apply returns Publisher<Boolean>; collect into a Mono and block. */
    private boolean matches(Route route, ServerWebExchange exchange) {
        Boolean result = Mono.from(route.getPredicate().apply(exchange)).block();
        return Boolean.TRUE.equals(result);
    }

    private ServerWebExchange mockExchange(String path) {
        MockServerHttpRequest req = MockServerHttpRequest.get(path).build();
        return MockServerWebExchange.from(req);
    }
}
