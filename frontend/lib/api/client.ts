import axios, { AxiosError } from "axios";
import axiosRetry from "axios-retry";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

export const api = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

// Phase 2 #11 — retry storm controls.
//
// We retry idempotent reads only (GET) and only on transient failures
// (network errors + 5xx). 4xx is the server explicitly saying "don't retry"
// (validation, auth, business 409); replaying it just burns rate-limit
// budget. Mutations (POST/PUT/PATCH/DELETE) are NEVER retried — even though
// our K-13 Idempotency-Key would make a server-side replay safe, retrying
// the network layer can re-fire side effects the server already accepted
// (the response was lost in transit) and double-bills users / sends emails
// twice.
//
// Backoff is exponential with jitter: ~ 200ms, 400ms (each ±50% jitter).
// Max 2 retries → worst case 600-900ms before a hard failure surfaces.
// That's tight enough that a slow upstream doesn't compound across many
// concurrent FE calls but loose enough to absorb a single packet drop.
axiosRetry(api, {
  retries: 2,
  retryCondition: (error: AxiosError) => {
    const method = (error.config?.method ?? "get").toLowerCase();
    if (method !== "get") return false;
    // Network-level failure (no response object) → retryable.
    if (!error.response) return true;
    // 5xx only — never replay 4xx (server told us to stop).
    return error.response.status >= 500 && error.response.status < 600;
  },
  retryDelay: (retryCount: number) => {
    const base = 200 * Math.pow(2, retryCount - 1);          // 200, 400
    const jitter = base * 0.5 * (Math.random() * 2 - 1);     // ±50%
    return Math.max(50, base + jitter);
  },
  // Don't retry while a refresh is in flight — the response interceptor
  // below handles 401 by triggering a token refresh; axios-retry firing
  // on the same response would race it.
  shouldResetTimeout: true,
});

// Public endpoints that must NOT receive an Authorization header even when
// the browser still has a leftover token in localStorage. /auth/workspace/activate
// is the offender that surfaced the bug — Spring Security treats a token-bearing
// request as authenticated, runs role-check, and 403s a SUPER_ADMIN platform
// token trying to bootstrap an enterprise. Symptoms: 403 + empty body, no JSON.
const PUBLIC_PATHS = [
  "/auth/workspace/activate",
  "/auth/login",
  "/auth/platform/login",
  "/auth/refresh",
  "/auth/platform/refresh",
];

// Attach JWT + Idempotency-Key to every request
api.interceptors.request.use((config) => {
  const url      = config.url ?? "";
  const isPublic = PUBLIC_PATHS.some((p) => url.includes(p));
  const token    = localStorage.getItem("kaori.access_token");
  if (token && !isPublic) {
    config.headers.Authorization = `Bearer ${token}`;
  } else if (isPublic) {
    // Strip any header that an earlier caller (or a default header config)
    // might have set, so leftover localStorage tokens can't poison the
    // bootstrap request.
    delete config.headers.Authorization;
  }

  // K-13 — gateway IdempotencyFilter rejects POST/PUT/PATCH/DELETE under
  // /api/v1/** without an Idempotency-Key header (400 RFC 7807). Generate a
  // fresh UUID per request so every mutation is dedup-keyed; callers that
  // explicitly want to retry the same logical mutation can override the
  // header before the request reaches this interceptor.
  const method = (config.method ?? "get").toLowerCase();
  const isMutation = ["post", "put", "patch", "delete"].includes(method);
  const isApiV1    = url.includes("/api/v1/");
  if (isMutation && isApiV1 && !config.headers["Idempotency-Key"]) {
    config.headers["Idempotency-Key"] = crypto.randomUUID();
  }
  return config;
});

// Auto-refresh on 401. Platform admin tokens (token_kind=platform) refresh via
// /auth/platform/refresh and bounce back to /platform/login on failure; enterprise
// tokens use /auth/refresh and bounce to /login. The kind is stamped at sign-in.
api.interceptors.response.use(
  (res) => res,
  async (err) => {
    if (err.response?.status === 401) {
      const refresh  = localStorage.getItem("kaori.refresh_token");
      const kind     = localStorage.getItem("kaori.token_kind");           // 'platform' | 'enterprise' | null
      const isAdmin  = kind === "platform";
      const loginUrl = isAdmin ? "/platform/login" : "/login";
      if (refresh) {
        try {
          if (isAdmin) {
            const { data } = await axios.post(`${API_URL}/auth/platform/refresh`,
              { refresh_token: refresh });
            const a = data.data ?? data;
            localStorage.setItem("kaori.access_token",  a.access_token  ?? a.accessToken);
            localStorage.setItem("kaori.refresh_token", a.refresh_token ?? a.refreshToken);
            err.config.headers.Authorization = `Bearer ${a.access_token ?? a.accessToken}`;
          } else {
            const { data } = await axios.post(`${API_URL}/auth/refresh`,
              { refreshToken: refresh });
            localStorage.setItem("kaori.access_token",  data.accessToken);
            localStorage.setItem("kaori.refresh_token", data.refreshToken);
            err.config.headers.Authorization = `Bearer ${data.accessToken}`;
          }
          return axios(err.config);
        } catch {
          localStorage.clear();
          window.location.href = loginUrl;
        }
      } else {
        window.location.href = loginUrl;
      }
    }
    return Promise.reject(err);
  }
);

// Auth
export const authApi = {
  login: (email: string, password: string) =>
    api.post("/auth/login", { email, password }),
  logout: () => api.post("/auth/logout"),
  forgotPassword: (email: string) => api.post("/auth/forgot-password", { email }),
  resetPassword: (token: string, newPassword: string) =>
    api.post("/auth/reset-password", { token, newPassword }),
  /** P2-AUTH-001 SSO — start the provider's authorize flow. Returns the
   *  URL the browser should navigate to next. `provider` is 'google' |
   *  'microsoft'. `return_url` is where the SSO callback page lives.
   *  Path uses /api/v1 prefix to match gateway "sso-public" route which
   *  strips /api/v1 before forwarding to ai-orchestrator. */
  ssoStart: (provider: "google" | "microsoft", returnUrl: string) =>
    api.get(`/api/v1/p2/auth/sso/${provider}/start`, { params: { return_url: returnUrl } }),
  /** P2-AUTH-001 SSO — swap the one-shot sso_code (from the provider
   *  callback's ?sso_code= query) for a real JWT. Mirrors the password-
   *  login response shape so the FE can re-use the same setAuth logic. */
  ssoExchange: (ssoCode: string) =>
    api.post("/auth/sso/exchange", { ssoCode }),
  /** Phase 3 Batch 3.1.a + B3 PR #8 — separate platform admin login.
   *  Backend returns RFC 7807 problem+json on 401/423 and one of:
   *    - Full session: {data:{access_token, refresh_token, session_id,
   *      admin_id, role, mfa_enabled, mfa_required:false, expires_in_sec}}
   *    - MFA required: {data:{mfa_required:true, mfa_challenge_token,
   *      mfa_challenge_expires_in_sec, admin_id}} — caller MUST POST the
   *      challenge to /auth/platform/mfa/verify with the user's TOTP code. */
  platformLogin: (email: string, password: string) =>
    api.post("/auth/platform/login", { email, password }),
  /** B3 PR #8 — second leg of the 2-step platform login. Accepts the
   *  challenge token returned by /platform/login + a 6-digit TOTP code.
   *  Returns the same {data:{access_token, refresh_token, ...}} envelope
   *  as a no-MFA login. RFC 7807 401 carries one of code=
   *  AUTH.MFA_INVALID_CODE / AUTH.MFA_CHALLENGE_EXPIRED /
   *  AUTH.MFA_CHALLENGE_INVALID so the FE can pick the right copy. */
  platformVerifyMfa: (mfaChallengeToken: string, code: string) =>
    api.post("/auth/platform/mfa/verify", { mfaChallengeToken, code }),
  /** Sprint 7 PR D — F-013 onboarding 2-step page POSTs here. The
   *  endpoint validates the workspace activation key, creates the
   *  initial MANAGER user, and returns a tokens pair (caller can
   *  go straight to /dashboard without a separate /login round-trip). */
  activateWorkspace: (workspaceKey: string, adminEmail: string,
                      adminPassword: string, adminName?: string) =>
    api.post("/auth/workspace/activate", {
      workspaceKey, adminEmail, adminPassword, adminName,
    }),
};

// Analytics (ai-orchestrator, routed through gateway)
export const analyticsApi = {
  listTemplates: (detectedTypes: string, detectedPurpose: string | null, rowCount: number) =>
    api.get("/api/v1/analytics/templates", {
      params: {
        detected_types: detectedTypes,
        detected_purpose: detectedPurpose ?? undefined,
        row_count: rowCount,
      },
    }),
  createRun: (runId: string, templates: string[], config: Record<string, unknown>) =>
    api.post("/api/v1/analytics/runs", { run_id: runId, templates, config }),
  getRun: (analysisRunId: string) =>
    api.get(`/api/v1/analytics/runs/${analysisRunId}`),
  listRuns: (limit = 20) =>
    api.get("/api/v1/analytics/runs", { params: { limit } }),
};

// Pipeline
export const pipelineApi = {
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.post("/api/v1/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  getStatus: (runId: string) => api.get(`/api/v1/upload/${runId}/status`),
  getSchema: (runId: string) => api.post("/api/v1/schema", { run_id: runId }),
  confirmSchema: (runId: string, overrides: unknown[]) =>
    api.post("/api/v1/schema/confirm", { run_id: runId, overrides }),
  getCleaningSuggestions: (runId: string) =>
    api.post("/api/v1/clean/suggestions", { run_id: runId }),
  applyCleaningRules: (runId: string, ruleIds: string[]) =>
    api.post("/api/v1/clean/apply", { run_id: runId, rule_ids: ruleIds }),
  analyze: (runId: string, templates: string[], config: unknown, consent: boolean) =>
    api.post("/api/v1/analyze", {
      run_id: runId,
      templates,
      config,
      consent_external_ai: consent,
    }),
  getResults: (runId: string) => api.get(`/api/v1/results/${runId}`),
};

// Dashboard (ai-orchestrator)
export const dashboardApi = {
  getState: () => api.get("/api/v1/dashboard/state"),
  getInsights: (limit = 5) => api.get("/api/v1/insights/feed", { params: { limit } }),
  getBillingSummary: () => api.get("/api/v1/billing/summary"),
};

// Knowledge Base (ai-orchestrator · F-061 / CR-0017). X-Enterprise-ID is
// injected by the gateway JwtAuthFilter from the JWT — never sent from here.
export const knowledgeApi = {
  /** Semantic search over global (tier 1-3) + this tenant's own (tier 4)
   *  knowledge. Returns {query, results:[{document_id, tier, scope, category,
   *  title, source, source_url, lang, tags, similarity}]}. */
  search: (query: string, topK = 5, category?: string) =>
    api.post("/api/v1/knowledge-base/search", {
      query,
      top_k: topK,
      category: category ?? undefined,
    }),
  /** List knowledge visible to the tenant (global + own). */
  list: (category?: string, limit = 100) =>
    api.get("/api/v1/knowledge-base/documents", {
      params: { category: category ?? undefined, limit },
    }),
  /** Ingest a tenant-specific (tier 4) knowledge document. Embedded
   *  server-side at ingest so it is searchable immediately. */
  ingest: (doc: {
    title: string;
    content: string;
    category?: string;
    source?: string;
    source_url?: string;
    tags?: string[];
  }) => api.post("/api/v1/knowledge-base/documents", doc),
};
