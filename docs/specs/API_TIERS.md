# API TIERS — Kaori System

> Lookup nhanh: endpoint nào thuộc tier nào, role guard nào, forward đến service nào.
> Source of truth: `services/api-gateway/src/main/java/.../config/RouteConfig.java` + OpenAPI spec (khi có).
>
> **Auth unification:** FE có 3 route login khác nhau cho UX, nhưng BE chỉ có **1 auth service duy nhất**
> — một login endpoint, một rate-limiter, một lockout. Không duplicate auth logic.

---

## 1. Canonical 3-tier Model

| Tier | Actor | FE Portal | Login entry | JWT Role |
|------|-------|-----------|-------------|----------|
| **P1 · Platform Manager** | Kaori ops | `/platform/*` | `/platform/login` | `SUPER_ADMIN`, `ADMIN`, `SUPPORT` |
| **P2 · Enterprise** | Customer (end-user) | `/(app)/*` | `/login` | `MANAGER`, `OPERATOR`, `ANALYST`, `VIEWER` |

> P3 (Studio tier) là Phase 2 — chưa cần.

---

## 2. Gateway Middleware Matrix (Java Spring Cloud Gateway)

| Group | Filter Chain | Allowed Roles |
|-------|-------------|---------------|
| `/auth/**` | Public (no JWT) | — |
| `/workspaces/activate-key` | Public | — |
| `/health` | Public | — |
| `/debug/**` | `JwtAuthFilter` + `TenantFilter` + `AdminOnlyFilter` | SUPER_ADMIN, ADMIN |
| `/platform/**` (read) | `JwtAuthFilter` + `TenantFilter` + `PlatformFilter` | SUPER_ADMIN, ADMIN, SUPPORT |
| `/platform/**` (write), `/workspaces/**` | `JwtAuthFilter` + `TenantFilter` + `AdminFilter` | SUPER_ADMIN, ADMIN |
| `/api/v1/**` | `JwtAuthFilter` + `TenantFilter` + `BillingFilter` | Mọi role authenticated |

**Header forwarding** (downstream services trust, không verify lại JWT):
```
X-Enterprise-ID  ← từ JWT claim enterprise_id
X-User-ID        ← từ JWT claim sub
X-User-Role      ← từ JWT claim role
X-Trace-ID       ← UUID inject / forward
```

Downstream services check `X-User-Role` tại sensitive endpoints (defense-in-depth).

---

## 3. Endpoint Inventory

### Auth (Public, port 8091 hoặc qua gateway /auth/**)

| Path | Method | Service | Notes |
|------|--------|---------|-------|
| `/auth/login` | POST | auth-service | Email + bcrypt, 5-attempt lockout → Redis 15 min |
| `/auth/logout` | POST | auth-service | Add token to Redis blacklist |
| `/auth/refresh` | POST | auth-service | Rotate access + refresh tokens |
| `/auth/forgot-password` | POST | auth-service | ALWAYS return 200 (anti-enumeration) |
| `/auth/reset-password` | POST | auth-service | Token from email, 1h TTL, invalidate on use |
| `/workspaces/activate-key` | POST | auth-service | Onboarding: `KAORI-XXXX-XXXX` key |

### P1 · Platform (Ops Only)

| Path | Method | Service | Notes |
|------|--------|---------|-------|
| `/platform/stats` | GET | ai-orchestrator | Workspace counts, storage used |
| `/platform/incidents` | GET | ai-orchestrator | Error events last 7 days |
| `/platform/admins` | GET | auth-service | List platform admins |
| `/platform/admins/invite` | POST | auth-service | ADMIN+ only |
| `/platform/admins/:id/deactivate` | POST | auth-service | Min-1 SUPER_ADMIN guard |
| `/workspaces` | GET, POST | auth-service | List + create workspaces |
| `/workspaces/:id` | PATCH | auth-service | Rename / change plan |
| `/workspaces/:id/keys` | GET, POST | auth-service | Manage workspace keys |
| `/workspaces/:id/keys/:keyId/revoke` | POST | auth-service | Revoke key |
| `/billing/platform` | GET | ai-orchestrator | Platform-wide billing view |

### P2 · Enterprise (Authenticated Users)

#### Onboarding + Users
| Path | Method | Notes |
|------|--------|-------|
| `/enterprises/users` | GET | List users (paginated) |
| `/enterprises/users/invite` | POST | MANAGER only |
| `/users/:id/role` | PATCH | Prevent last MANAGER demotion |
| `/users/:id/deactivate` | POST | Prevent last active user removal |
| `/enterprises/me/settings` | GET, POST | Theme, locale, consent_external flag |

#### Pipeline (data-pipeline:8092)
| Path | Method | Notes |
|------|--------|-------|
| `/api/v1/upload` | POST | BillingFilter gated. Multipart file upload |
| `/api/v1/runs` | GET | List pipeline runs (paginated) |
| `/api/v1/runs/:id` | GET | Run detail + status |
| `/api/v1/runs/:id/status` | GET | Poll status: `queued→processing→silver_complete→done` |
| `/api/v1/runs/:id/schema` | GET | Canonical schema + column mappings + uncertainty flags |
| `/api/v1/runs/:id/schema/confirm` | POST | User confirm / override mappings |
| `/api/v1/runs/:id/cleaning-suggestions` | GET | Rule catalog suggestions + quality preview |
| `/api/v1/runs/:id/clean` | POST | Apply selected rules → Silver layer |
| `/api/v1/runs/:id/analyze` | POST | Trigger analysis (multi-template) |
| `/api/v1/runs/:id/results` | GET | Analysis results (charts + narrative JSON) |

#### Analytics (ai-orchestrator:8093)
| Path | Method | Notes |
|------|--------|-------|
| `/api/v1/analytics/templates` | GET | List eligible templates for current run |
| `/api/v1/analytics/runs` | GET | List analysis runs |
| `/api/v1/analytics/runs/:id` | GET | Analysis run detail |

#### AI + Strategy
| Path | Method | Notes |
|------|--------|-------|
| `/api/v1/ai/query` | POST | Command palette query → framework router |
| `/api/v1/ai/recommendations` | GET | Top-3 recommendations based on analysis |
| `/api/v1/strategy/ask` | POST | Route to 5Why/SWOT/Fishbone/5W1H/MoM |
| `/api/v1/strategy/swot` | POST | SWOT analysis |
| `/api/v1/strategy/five-why` | POST | 5 Why analysis |
| `/api/v1/strategy/fishbone` | POST | Fishbone diagram |

#### Dashboard + Insights
| Path | Method | Notes |
|------|--------|-------|
| `/api/v1/dashboard/state` | GET | 5-state dashboard aggregator |
| `/api/v1/insights/feed` | GET | AI-generated insights feed |

#### Billing
| Path | Method | Notes |
|------|--------|-------|
| `/api/v1/billing/summary` | GET | Current month usage + quota |
| `/api/v1/billing/upgrade-preview` | GET | Cost estimate for upgrade |

#### Internal
| Path | Notes |
|------|-------|
| `/health` | Unauthenticated liveness |
| `/metrics` | Prometheus scrape |
| `/debug/health` | AdminOnly system health |
| `/debug/errors` | AdminOnly error feed |

---

## 4. Java Spring Cloud Gateway — Route Config Pattern

```java
// services/api-gateway/src/main/java/com/kaorisystem/gateway/config/RouteConfig.java

@Bean
public RouteLocator routes(RouteLocatorBuilder builder) {
    return builder.routes()

        // PUBLIC — Auth endpoints (bypass JWT)
        .route("auth-public", r -> r
            .path("/auth/**", "/workspaces/activate-key", "/health")
            .filters(f -> f.filter(traceIdFilter).filter(corsFilter))
            .uri(AUTH_SERVICE_URI))

        // PLATFORM READ (SUPER_ADMIN + ADMIN + SUPPORT)
        .route("platform-read", r -> r
            .path("/platform/**")
            .and().method(HttpMethod.GET)
            .filters(f -> f
                .filter(jwtAuthFilter)
                .filter(tenantFilter)
                .filter(platformFilter))
            .uri(AUTH_SERVICE_URI))

        // PLATFORM WRITE (SUPER_ADMIN + ADMIN)
        .route("platform-write", r -> r
            .path("/platform/**", "/workspaces/**")
            .and().method(HttpMethod.POST, HttpMethod.PUT, HttpMethod.PATCH, HttpMethod.DELETE)
            .filters(f -> f
                .filter(jwtAuthFilter)
                .filter(tenantFilter)
                .filter(adminFilter))
            .uri(AUTH_SERVICE_URI))

        // API v1 — All authenticated (with billing check on /upload)
        .route("api-v1-upload", r -> r
            .path("/api/v1/upload")
            .filters(f -> f
                .filter(jwtAuthFilter)
                .filter(tenantFilter)
                .filter(billingCheckFilter))   // Quota check before upload
            .uri(DATA_PIPELINE_URI))

        .route("api-v1-pipeline", r -> r
            .path("/api/v1/runs/**", "/api/v1/upload")
            .filters(f -> f.filter(jwtAuthFilter).filter(tenantFilter))
            .uri(DATA_PIPELINE_URI))

        .route("api-v1-analytics", r -> r
            .path("/api/v1/analytics/**", "/api/v1/strategy/**",
                  "/api/v1/ai/**", "/api/v1/dashboard/**", "/api/v1/insights/**",
                  "/api/v1/billing/**")
            .filters(f -> f.filter(jwtAuthFilter).filter(tenantFilter))
            .uri(AI_ORCHESTRATOR_URI))

        // ENTERPRISES (user management) → auth-service
        .route("enterprises", r -> r
            .path("/enterprises/**", "/users/**")
            .filters(f -> f.filter(jwtAuthFilter).filter(tenantFilter))
            .uri(AUTH_SERVICE_URI))

        .build();
}
```

---

## 5. Filter Behavior Reference

### JwtAuthFilter
```java
// Validate JWT (HS256 Phase 1, RS256 Phase 2)
// Extract: enterprise_id, user_id, role
// Check Redis blacklist (logout)
// On failure: 401 Unauthorized
// Downstream: sets X-Enterprise-ID, X-User-ID, X-User-Role
```

### TenantFilter
```java
// Require X-Enterprise-ID present (set by JwtAuthFilter)
// Log X-Trace-ID for distributed tracing
// On missing: 403 Forbidden
```

### BillingCheckFilter
```java
// Read v_billing_summary (Redis cache 60s TTL)
// PILOT plan: hard-stop at quota → 402 Payment Required
// ENT plans: allow overage → set X-Quota-Overage header
// Soft warning at 80%: X-Quota-Warning: 0.82
```

### RateLimitFilter
```java
// Redis sorted-set sliding window
// Per-JWT: 120 req/min (configurable: RATE_LIMIT_JWT_PER_MIN)
// Per-IP: 600 req/min (configurable: RATE_LIMIT_IP_PER_MIN)
// On exceed: 429 Too Many Requests + Retry-After header
```

### AdminFilter / PlatformFilter
```java
// Check X-User-Role header
// AdminFilter: require SUPER_ADMIN or ADMIN
// PlatformFilter: require SUPER_ADMIN, ADMIN, or SUPPORT
// On fail: 403 Forbidden
```

---

## 6. Adding a New Route

1. Pick tier (P1 / P2 / Internal)
2. Add FastAPI handler in appropriate service (`data-pipeline` or `ai-orchestrator`)
3. Add gateway route in `RouteConfig.java` under matching group (do NOT create new filter group without reason)
4. Add path to OpenAPI spec with:
   - `tags: [P2 · Pipeline]`
   - `x-kaori-tier: P1|P2`
   - `x-kaori-roles: [MANAGER, OPERATOR]` (if stricter than group default)
5. Verify X-Enterprise-ID filter appears in all downstream handlers (K-1)

---

## 7. Known Gaps

- OTP / 2FA flow — Phase 2
- Token-based invite flow — Phase 2
- Webhook ingest endpoint — Phase 2
- Rate limit per endpoint (not just per-JWT global) — Phase 2
