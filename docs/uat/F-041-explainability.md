# UAT — F-041 Explainability Layer

> **Function:** F-041 — top-3 factors + Vietnamese narrative for any decision_audit_log row.
> **Portal:** P2 Enterprise (visible on `/p2/decisions/{id}` detail page).
> **Roles allowed:** any P2 role can request an explanation of a decision they can already see (RLS gates the source row).
> **Service:** ai-orchestrator (`/api/v1/explainability/explain`) + llm-gateway (Issue #3 path).
> **DB:** reads `decision_audit_log`; writes 1 audit row per call (`decision_type='explainability.explain'`).
> **Owner:** anh (test) + em (standby fix).
> **Prepared:** 2026-05-04

---

## 0. Scope decision — why "lite", not real SHAP

True SHAP needs the fitted model object + the feature row that was scored, persisted somewhere the explainability call can read. Phase 1 doesn't persist model objects (no MLflow yet — that's F-046 in Sprint 2.3 P3 Studio). Persisting models also implies size/garbage-collection policy + version pinning + tenant isolation of artefact storage — too much to bolt on for one feature.

PR ships the **honest lite version**: read the audit row, prompt an LLM with the structured fields (chosen_value + confidence + alternatives + reasoning + uncertainty_flags), get back a top-3 + narrative. The FE labels this as "giải thích dựa trên nhật ký" so users don't conflate it with statistical SHAP values.

When the model registry lands (F-073), the same endpoint shape can switch to real SHAP without changing the FE — `top_factors[].weight` already maps to SHAP magnitudes, and `direction` to the sign.

---

## 1. What ships

| Surface | Purpose |
|---|---|
| `services/ai-orchestrator/explainability/` | New module: `templates.py` (system_prompt + output_schema), `service.py` (read row + call llm_router + audit), `routers/explainability.py` (single POST endpoint) |
| `POST /api/v1/explainability/explain` | Body `{decision_id, consent_external?}`. Returns `{decision_id, top_factors[], narrative, confidence_explanation}` |
| Gateway route `/api/v1/explainability/**` | Forwards to ai-orchestrator (same `/api/v1/(.*)` rewrite as the rest of the router) |
| FE — `/p2/decisions/[id]` "Vì sao Kaori quyết định thế?" section | Lazy: button "Tạo giải thích" triggers POST; result renders a 3-row factor table with weight bars + direction icons + narrative + confidence-explanation footer |
| Tests — `tests/test_explainability.py` | 7 cases: missing row → 404, happy path + audit, consent_external → tags external, LLM failure → 502, prompt rendering pulls every audit field (parsed dict + raw string alternatives) |

Output schema (Issue #3 enforced):

```json
{
  "top_factors": [
    {
      "factor_name": "Khớp ngữ nghĩa Levenshtein cao",
      "direction": "positive",
      "weight": 0.65,
      "evidence": "Edit-distance 0.92 với 'revenue' trong language_dictionary VI."
    },
    ...
  ],
  "narrative": "Kaori chọn map 'doanh_thu' sang 'revenue' vì...",
  "confidence_explanation": "Confidence 0.92 phản ánh..."
}
```

---

## 2. Pre-flight

| # | Check | Expected |
|---|---|---|
| A1 | `curl -fsS localhost:8093/health` | `{"status":"ok"}` |
| A2 | `curl -fsS localhost:8095/health` | `{"status":"ok"}` |
| A3 | Pilot tenant has ≥ 5 rows in `decision_audit_log` (mapping confirms, override decisions, framework runs from F-034, etc.) | required for SCN-1 to find a real decision to explain |
| A4 | Gateway route active: `curl -i http://localhost:8080/api/v1/explainability/explain -H 'Authorization: Bearer …' -H 'Content-Type: application/json' -d '{"decision_id":"…"}' ` returns non-404 (200/422/etc — anything but route-not-found) | confirms RouteConfig wired |

---

## 3. Test scenarios

### SCN-1 — Happy path against a real decision

| Step | Action | Expected |
|------|--------|----------|
| 1 | `/p2/decisions` → click any row → `/p2/decisions/{id}` | Header card + reasoning + alternatives + override + audit sections render |
| 2 | The "Vì sao Kaori quyết định thế?" card renders BETWEEN reasoning and alternatives, with a "Tạo giải thích" button | section initially shows the disclaimer about "không phải SHAP value thực thụ" |
| 3 | Click "Tạo giải thích" | spinner ~5-15s on Qwen 14B (~2s in MSW dev mode) |
| 4 | Result render | Top-3 rows, each with: factor_name + direction icon (TrendingUp/Down/Minus) + weight % + evidence quote + horizontal bar; narrative paragraph; confidence-explanation footer with Lightbulb icon |
| 5 | DB inspect: `SELECT decision_type, subject FROM decision_audit_log ORDER BY created_at DESC LIMIT 1` | new row `decision_type='explainability.explain', subject='<decision_id>'` |
| 6 | Click "Tạo lại" | regenerates (new LLM call) — shows fresh top_factors (may differ slightly due to LLM temperature; this is OK, second-opinion feature) |

### SCN-2 — RLS isolation

| Step | Action | Expected |
|------|--------|----------|
| 1 | Login enterprise A | get a valid decision_id |
| 2 | Login enterprise B; POST `/api/v1/explainability/explain` with A's decision_id | **404** RFC 7807 — `Decision not found`. Don't leak existence |
| 3 | DB inspect from B's tenant context: `SELECT … FROM decision_audit_log WHERE decision_id = $1` | empty (RLS prunes the row) |

### SCN-3 — LLM failure (Issue #3 repair gave up)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Trigger by setting `LLM_GATEWAY_URL` to an unreachable host OR run on a small Qwen variant where structured-output repair fails | POST returns **502** RFC 7807 — `LLM gave up explaining this decision: …` |
| 2 | DB inspect | NO new audit row (audit only writes on success) |
| 3 | FE | ErrorBanner with the 502 detail; "Tạo giải thích" button stays available so user can retry |

### SCN-4 — K-4 consent path (external AI)

| Step | Action | Expected |
|------|--------|----------|
| 1 | POST with `consent_external: true` while tenant has not opted in | **403** RFC 7807 from llm_router — `Tenant has not enabled consent_external_ai (K-4)` |
| 2 | Flip `tenant_settings.consent_external_ai = true`, re-POST | **200** + the audit row tags `llm_provider='external'` |
| 3 | FE never sends `consent_external=true` from the section UI today (always Qwen) — to test the external path use curl directly | ensures the K-4 surface stays opt-in, not auto-enabled |

### SCN-5 — Schema validation gates

| Step | Action | Expected |
|------|--------|----------|
| 1 | POST without `decision_id` | **422** — pydantic validation, `field required` |
| 2 | POST with `decision_id: "not-a-uuid"` | **422** — `Invalid UUID` |
| 3 | LLM accidentally returns non-JSON or missing required field | gateway tries one repair (Issue #3); if repair also fails → 502 (covered by SCN-3) |

### SCN-6 — Audit chain integrity

| Step | Action | Expected |
|------|--------|----------|
| 1 | After SCN-1 step 6 (regenerate) | TWO audit rows now (1 per call), both `decision_type='explainability.explain'` for the same `subject` |
| 2 | Show explainability log: `SELECT subject, COUNT(*) FROM decision_audit_log WHERE decision_type='explainability.explain' GROUP BY subject` | counts the regen attempts per source decision |

---

## 4. Edge cases — known gaps (intentional)

- **Not real SHAP** — `weight` values come from the LLM's reasoning, not from gradient-times-baseline shapley computation. UI labels the section accordingly. PR D for F-073 model registry will swap the implementation while keeping the response shape.
- **No persistence** — explanations are not cached. Two clicks = two LLM calls. Add a Redis cache (TTL 1h, key=decision_id+model_version) when pilot users complain about latency or cost.
- **`/p2/decisions` list** — does not show an "explained" badge today; we don't write a column on the source decision row. If a UI sort by "has been explained" becomes valuable, add a denormalised flag (or a small lookup view over decision_audit_log subject filtering).
- **Override-aware explanation** — if a decision has been overridden, the LLM doesn't currently see the override row; it explains the *original* AI choice. For "explain my override" use F-036's existing override note field. Possibly cross-link in a follow-up PR if pilots ask.

---

## 5. Rollback

Disable by removing the router include + gateway route. The endpoint module stays harmless; nothing else imports it. Restart ai-orchestrator + api-gateway picks up the change.

```py
# services/ai-orchestrator/main.py — comment out:
# app.include_router(explainability.router, tags=["Explainability"])
```

```java
// services/api-gateway/.../RouteConfig.java — comment out:
// .route("explainability", r -> r ...
```

The decision detail page (`/p2/decisions/[id]`) still renders without the section if you also remove the `<ExplainabilitySection ... />` mount in `32b-decisions-id-wired.tsx`.

---

*Last updated: 2026-05-04 — Phase 2 Sprint 2.1 close-out (F-041 final).*
