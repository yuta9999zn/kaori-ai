package com.kaorisystem.gateway.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.cloud.gateway.route.RouteLocator;
import org.springframework.cloud.gateway.route.builder.RouteLocatorBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RouteConfig {

    @Value("${kaori.services.auth-url}")
    private String authUrl;

    @Value("${kaori.services.pipeline-url}")
    private String pipelineUrl;

    @Value("${kaori.services.orchestrator-url}")
    private String orchestratorUrl;

    /**
     * Public route table.
     *
     * Convention (kept consistent across all services):
     *   - The frontend always calls under /api/v1/...
     *   - Each downstream service's handlers are mounted WITHOUT the /api/v1
     *     prefix (so the service can be tested directly without a gateway).
     *   - Every /api/v1 route group below applies the shared rewrite:
     *         /api/v1/(?<segment>.*) → /${segment}
     *     so handlers receive the bare path.
     *
     * Exceptions:
     *   - /auth/**           served at the same path on auth-service (legacy).
     *   - /health            served at the same path on auth-service.
     *   - /api/v1/platform/**  served at the same path on auth-service —
     *     PlatformController and WorkspaceController declare their own
     *     /api/v1/platform/... @RequestMapping, so no rewrite is applied.
     */
    @Bean
    public RouteLocator routes(RouteLocatorBuilder builder) {
        return builder.routes()

            // ---- Public auth routes (no JWT required) ----
            .route("auth-public", r -> r
                .path("/auth/**")
                .uri(authUrl))

            // ---- P2-AUTH-001 SSO (OAuth start + callback — pre-auth) ----
            // ai-orchestrator owns the OAuth dance. /start issues state +
            // returns authorize_url. /callback consumes provider code,
            // matches user by email, issues one-shot exchange code, 302s
            // back to FE. auth-service /auth/sso/exchange then swaps the
            // code for a real RS256 JWT (handled by the auth-public route
            // above).
            .route("sso-public", r -> r
                .path("/api/v1/p2/auth/sso/**")
                .filters(f -> f
                    .rewritePath("/api/v1/(?<segment>.*)", "/${segment}"))
                .uri(orchestratorUrl))

            // ---- Health check ----
            .route("health", r -> r
                .path("/health")
                .uri(authUrl))

            // ---- Data Pipeline (JWT required — handled by JwtAuthFilter) ----
            // /analyze and /results moved here from the orchestrator group:
            //   data-pipeline owns POST /analyze (creates analysis_run) and
            //   GET /results/{run_id} (reads analysis_results joined by run_id).
            //   They were routed to ai-orchestrator by mistake → 404.
            // ---- File upload (large multipart → long-running ingest) ----
            // Dedicated route BEFORE "pipeline" so big xlsx/csv uploads get a
            // generous response-timeout. The global 30s (application.yml) is
            // too short for a 10MB+ workbook: chunked read + magic-byte
            // detection + SHA-256 + Bronze write on the pilot box exceeds it
            // → 504 Gateway Timeout. Other pipeline calls keep the tight 30s.
            .route("pipeline-upload", r -> r
                .path("/api/v1/upload/**")
                .filters(f -> f
                    .stripPrefix(0)
                    .rewritePath("/api/v1/(?<segment>.*)", "/${segment}"))
                .metadata("response-timeout", 300000)   // 5 min (ms), per-route override
                .uri(pipelineUrl))

            // ---- Heavy pipeline steps (schema detection + cleaning) ----
            // Dedicated route BEFORE "pipeline" with a longer timeout. A
            // multi-sheet workbook samples rows + sniffs types (/schema) then
            // applies rules + writes Silver for tens of thousands of rows
            // (/clean) — both exceed the global 30s and 504. Work is bounded
            // (schema fallback budget; clean uses batched executemany), so
            // this is a safety ceiling, not a licence to hang.
            .route("pipeline-heavy", r -> r
                .path("/api/v1/schema/**", "/api/v1/clean/**")
                .filters(f -> f
                    .stripPrefix(0)
                    .rewritePath("/api/v1/(?<segment>.*)", "/${segment}"))
                .metadata("response-timeout", 120000)   // 120s (ms), per-route override
                .uri(pipelineUrl))

            .route("pipeline", r -> r
                .path("/api/v1/pipeline/**", "/api/v1/pipelines/**",
                      "/api/v1/analyze/**",  "/api/v1/results/**",
                      // F-NEW3 — Data Explorer hub overview at /data/explorer
                      // (and future /data/** drill-down endpoints).
                      "/api/v1/data/**")
                .filters(f -> f
                    .stripPrefix(0)
                    .rewritePath("/api/v1/(?<segment>.*)", "/${segment}"))
                .uri(pipelineUrl))

            // ---- Analytics (results dashboards, runs metadata) ----
            // Only /analytics/** stays on orchestrator. /analyze and /results
            // were reassigned to the pipeline group above.
            .route("analytics", r -> r
                .path("/api/v1/analytics/**")
                .filters(f -> f
                    .rewritePath("/api/v1/(?<segment>.*)", "/${segment}"))
                .uri(orchestratorUrl))

            // ---- Customer at-risk list (F-060) ----
            // ai-orchestrator north_star.py serves /customers/at-risk (cursor
            // list of revenue_at_risk > 0 customers) and POST /customers/{id}/action
            // (toggle is_actioned + Kafka emit). Without this route, the FE
            // /p2/customers/at-risk page 404s on the BE side.
            .route("customers", r -> r
                .path("/api/v1/customers/**")
                .filters(f -> f
                    .rewritePath("/api/v1/(?<segment>.*)", "/${segment}"))
                .uri(orchestratorUrl))

            // ---- EU AI Act compliance risk register ----
            // ai-orchestrator compliance_risk.py serves POST /compliance/ai-uses
            // (classify a workflow's AI use into a risk tier + register it) and
            // GET /compliance/ai-uses (list the tenant's risk register). Handlers
            // are mounted WITHOUT the /api/v1 prefix → shared rewrite applies.
            // Without this route /api/v1/compliance/** 404s at the edge.
            .route("compliance", r -> r
                .path("/api/v1/compliance/**")
                .filters(f -> f
                    .rewritePath("/api/v1/(?<segment>.*)", "/${segment}"))
                .uri(orchestratorUrl))

            // ---- Operational Economics: NOV + ROI (moat) ----
            // ai-orchestrator economics.py (/economics/nov/current|trend,
            // /economics/revenue/estimate) + roi_billing.py (/economics/roi/*)
            // serve flat paths WITHOUT the /api/v1 prefix → shared rewrite.
            // Without this route the /p2/economics NOV/ROI dashboard 503s at
            // the edge even though the handlers work (same gap class as the
            // industries route, 2026-06-05).
            .route("economics", r -> r
                .path("/api/v1/economics/**")
                .filters(f -> f
                    .rewritePath("/api/v1/(?<segment>.*)", "/${segment}"))
                .uri(orchestratorUrl))

            // ---- Multi-tier Analysis (F-033) ----
            // /api/v1/analysis/** — different prefix from /analytics/** so the
            // legacy wizard runner endpoint stays untouched. Both ultimately
            // land on the same `analysis_runs` table after migration 036.
            .route("multi-tier-analysis", r -> r
                .path("/api/v1/analysis/**")
                .filters(f -> f
                    .rewritePath("/api/v1/(?<segment>.*)", "/${segment}"))
                .uri(orchestratorUrl))

            // ---- Explainability (F-041) ----
            // POST /api/v1/explainability/explain — LLM-derived top-3
            // factors + Vietnamese narrative for any decision_audit_log row.
            .route("explainability", r -> r
                .path("/api/v1/explainability/**")
                .filters(f -> f
                    .rewritePath("/api/v1/(?<segment>.*)", "/${segment}"))
                .uri(orchestratorUrl))

            // ---- Analysis frameworks + Reports ----
            // frameworks.py (SWOT/6W/2H/Fishbone/5-Why generation) and
            // reports.py (F-038) serve flat /api/v1 paths on ai-orchestrator.
            // Without these routes the FE framework generation + report builder
            // 404 at the edge even though the handlers work (verified direct on
            // :8093) — re-baseline 2026-06-01.
            .route("frameworks-reports", r -> r
                .path("/api/v1/frameworks/**", "/api/v1/reports/**")
                .filters(f -> f
                    .rewritePath("/api/v1/(?<segment>.*)", "/${segment}"))
                .uri(orchestratorUrl))

            // ---- Shared services bucket (F-061 agents + future shared/) ----
            // POST /api/v1/shared/agents/sessions               (F-061 BE-SH-210)
            // POST /api/v1/shared/agents/workflows/{id}/invoke  (F-061 BE-SH-211)
            // The /shared/** path is the BACKEND_TASKS_PHASE.md convention for
            // cross-portal services that don't fit /enterprise or /platform.
            // ai-orchestrator is the current owner; F-062 guardrails service
            // and F-063 external AI gateway will land under the same prefix.
            .route("shared", r -> r
                .path("/api/v1/shared/**")
                .filters(f -> f
                    .rewritePath("/api/v1/(?<segment>.*)", "/${segment}"))
                .uri(orchestratorUrl))

            // ---- Insights + Strategy ----
            .route("insights", r -> r
                .path("/api/v1/insights/**", "/api/v1/strategy/**",
                      "/api/v1/chat/**",     "/api/v1/ai/**",
                      "/api/v1/knowledge-base/**",  // F-061 — Knowledge Base (CR-0017)
                      "/api/v1/decisions/**")  // F-029 — AI Decision Log
                .filters(f -> f
                    .rewritePath("/api/v1/(?<segment>.*)", "/${segment}"))
                .uri(orchestratorUrl))

            // ---- Dashboard + Billing summary (orchestrator) ----
            // Frontend reads /api/v1/dashboard/state and /api/v1/billing/summary
            // for the main dashboard page; both handlers live in the
            // ai-orchestrator dashboard router. Previously had no gateway
            // route at all → 404 at the edge.
            .route("dashboard-billing", r -> r
                .path("/api/v1/dashboard/**", "/api/v1/billing/**")
                .filters(f -> f
                    .rewritePath("/api/v1/(?<segment>.*)", "/${segment}"))
                .uri(orchestratorUrl))

            // ---- P15-S11 Tuần 8 — Workflow + corporate hierarchy ----
            // ai-orchestrator's corporate_tree.py + workflow_builder.py +
            // workflow_from_cdfl.py. MUST come before the auth-service
            // /api/v1/enterprises/** catch-all so the orchestrator-served
            // sub-paths (org-detail + parent) don't get shadowed.
            .route("corporate-tree", r -> r
                .path("/api/v1/corporate-tree/**",
                      "/api/v1/corporate-groups/**",
                      "/api/v1/business-divisions/**",
                      "/api/v1/departments/**",
                      "/api/v1/workflows/**",
                      "/api/v1/workflow-templates",
                      "/api/v1/workflow-cross-links/**",
                      "/api/v1/workflow-step-folders/**",
                      // P15-S11 Hướng A — RBAC tĩnh role-template lookup
                      // (mig 061). /departments/{id}/role-template is
                      // already covered by the /departments/** entry above;
                      // /role-templates + /enterprise-users need their own.
                      "/api/v1/role-templates",
                      "/api/v1/role-templates/**",
                      "/api/v1/enterprise-users/**",
                      // P15-S11 — customer/vendor/contract read APIs
                      // (mig 062/063). All resolve under ai-orchestrator;
                      // auth-service has no overlap on these paths.
                      "/api/v1/customers",
                      "/api/v1/customers/**",
                      "/api/v1/vendors",
                      "/api/v1/vendors/**",
                      "/api/v1/customer-contracts",
                      "/api/v1/customer-contracts/**",
                      "/api/v1/vendor-contracts",
                      "/api/v1/vendor-contracts/**",
                      // ADR-0037 Tier-3 — documents / contracts / approvals / RBAC
                      // (migs 119-126). All resolve under ai-orchestrator.
                      "/api/v1/workflow-runs/**",
                      "/api/v1/workflow-documents/**",
                      "/api/v1/doc-requirements/**",
                      "/api/v1/contracts",
                      "/api/v1/contracts/**",
                      "/api/v1/approval-chains",
                      "/api/v1/approval-chains/**",
                      "/api/v1/approval-inbox",
                      "/api/v1/approval-delegations",
                      "/api/v1/approval-delegations/**",
                      "/api/v1/user-department-roles",
                      "/api/v1/user-department-roles/**",
                      // ADR-0039 enterprise Document Repository / DMS
                      "/api/v1/document-folders",
                      "/api/v1/document-folders/**",
                      "/api/v1/document-repository/**",
                      // ADR-0026 Industry Template bootstrap (mig 101-103).
                      // industry_bootstrap.py lists industries + dry-run/apply
                      // bootstrap. Served by ai-orchestrator WITHOUT /api/v1
                      // prefix → shared rewrite applies. Without these the
                      // /p2 industry library + bootstrap-preview 503 at the edge.
                      "/api/v1/industries",
                      "/api/v1/industries/**",
                      // org-detail + parent + bootstrap-from-industry live under
                      // enterprises/ but are served by ai-orchestrator, not
                      // auth-service.
                      "/api/v1/enterprises/*/org-detail",
                      "/api/v1/enterprises/*/parent",
                      "/api/v1/enterprises/*/bootstrap-from-industry")
                .filters(f -> f
                    .rewritePath("/api/v1/(?<segment>.*)", "/${segment}"))
                .uri(orchestratorUrl))

            // ---- User management (JWT required, forwarded to auth-service) ----
            // No rewrite — controllers carry their own /api/v1 path prefix.
            .route("users", r -> r
                .path("/api/v1/users/**", "/api/v1/enterprises/**",
                      "/api/v1/workspaces/**", "/api/v1/settings/**")
                .uri(authUrl))

            // ---- Platform admin (SUPER_ADMIN / ADMIN / SUPPORT only) ----
            //
            // 3.2.b — single catch-all forwards every platform sub-resource
            // to auth-service. Replaces the earlier per-sub-path routes
            // (platform-keys, platform-workspaces) — JwtAuthFilter still
            // enforces the role + token_kind gate per request, the route
            // layer is just plumbing. New endpoints under /api/v1/platform
            // (billing, security, admins, audit, …) are picked up
            // automatically with no further config drift.
            //
            // Covers (non-exhaustive):
            //   /api/v1/platform/keys                       (legacy flat — F-009)
            //   /api/v1/platform/workspaces[/**]            (F-008 + F-009 nested keys)
            //   /api/v1/platform/admins[/**]                (F-010)
            //   /api/v1/platform/billing/**                 (F-011)
            //   /api/v1/platform/security/**                (Module 3 + 3.1.b)
            // ---- Platform LLM/AI ops + tuning config (ai-orchestrator) ----
            // CR-0019 / FR-PLT-08. MUST precede the auth-service /api/v1/platform/**
            // catch-all below: /platform/llm/* (llm_ops.py providers/api-keys/
            // tokens/upgrade-tests + ai_config GET/PATCH /config) lives in
            // ai-orchestrator, which serves WITHOUT the /api/v1 prefix → rewrite.
            .route("platform-llm", r -> r
                .path("/api/v1/platform/llm/**")
                .filters(f -> f
                    .rewritePath("/api/v1/(?<segment>.*)", "/${segment}"))
                .uri(orchestratorUrl))

            .route("platform", r -> r
                .path("/api/v1/platform/**")
                .uri(authUrl))

            .build();
    }
}
