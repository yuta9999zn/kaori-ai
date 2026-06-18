# Chat Tool Registry — v4 context refresh

> **Status:** ✅ shipped 2026-04-29 (Sprint 8 v3, F-NEW4); **classified as v4 utility** — kept working, but **NOT counted in v4 burndown** (no direct mapping in `BACKLOG_V4.md`).
> **Replaces:** `docs/archive/specs-v3/CHAT_TOOL_REGISTRY.md` (v3 spec, archived 2026-05-17) — vẫn đọc được, nhưng K-rules + LLM routing dưới này là phiên bản hiện hành.
> **Code path:** `services/ai-orchestrator/chat/` (intra-process, modular monolith Phase 1 — ADR-0010).
> **Updated:** 2026-05-08 — anh chốt "update lại trước khi thực thi tiếp" + chọn option (a) spec/doc only.

This v4 doc **does not change behaviour**. Its job is to explain how Sprint 8 chat fits the v4 narrative (where chat layer sits, what's burndown vs utility, where it overlaps with Insight Panel `P2-M210-*`).

If you're touching `services/ai-orchestrator/chat/**`, read this **and** the v3 spec (`docs/archive/specs-v3/CHAT_TOOL_REGISTRY.md`) — v3 is still the implementation contract.

---

## 0. v3 → v4 mapping summary

| v3 narrative | v4 narrative |
|---|---|
| **F-NEW4 Conversational Layer** (Sprint 8) — Phase 1.5 polish, intra-process tool registry | **No direct v4 feature code.** v4 BACKLOG_V4 không có sprint slot cho chat tool registry — coi là "utility / experimental" giữ working. |
| Standalone MCP server = Phase 2 goal | Vẫn Phase 2 goal — không thay đổi. |
| 6 curated tools (3 P2 + 3 P1), no generic SQL | Giữ nguyên. Không thêm tool mới Phase 1 v4 trừ khi Sprint nói rõ. |
| K-3/K-4/K-12/K-15/K-16 enforced | + thêm K-19 (OTel mandatory, span attr `tenant_id`) + K-20 (LLM version pinning per workflow — chat dùng `qwen2.5-14b@<pinned>`). |

**Overlap với Insight Panel (P2-M210-*) — KHÔNG cùng feature:**

| Khía cạnh | Chat Tool Registry (this doc, F-NEW4) | Insight Panel (P2-M210-*, v4 Phase 1 P1-S5) |
|---|---|---|
| Mục đích | Admin/manager hỏi nhanh về system state qua NL → tool dispatch | Người dùng đọc phân tích "Chuyện gì / Tại sao / Nên làm gì" trên data analysis result |
| Input | Free-text message + history | Pipeline analysis run + tài liệu nội bộ |
| Output | Streaming text + tool result preview | Insight card với confidence + data citation + document citation |
| RAG | Không (chat v0) | **Có** — vector embedding + index (P2-M210-013/014) |
| Persistence | Stateless v0 (FE buffers history) | Save insight + track acted/not-acted (P2-M210-010) |
| LLM routing | Qwen always (K-4 + ADR-0015) | Qwen default; vendor opt-in qua `consent_external + prefer_external` (ADR-0015) |
| Backlog status | utility (no v4 sprint) | Phase 1 v4 P1-S5 — **planned implementation** |

→ Khi Phase 1 v4 P1-S5 ship Insight Panel, có thể tái dùng **adapter pattern** từ chat (LLM call qua `llm-gateway`, output_schema validation) nhưng **schema + UI tách biệt**. Đừng gộp.

---

## 1. Endpoints (giữ nguyên v3)

| Method | Path | Auth | Body | Response |
|---|---|---|---|---|
| POST | `/api/v1/chat/enterprise/stream` | JWT (any P2 role) | `ChatRequest` | `text/event-stream` |
| POST | `/api/v1/chat/platform/stream` | JWT + role ∈ `{SUPER_ADMIN, ADMIN, SUPPORT}` | `ChatRequest` | `text/event-stream` |

Wire format, headers, SSE event types — xem `CHAT_TOOL_REGISTRY.md` §1. Không thay đổi.

---

## 2. Tool catalog (giữ nguyên 6 tool v3)

| Scope | Tool | Args | Source |
|---|---|---|---|
| P2 | `summarize_recent_decisions` | `days?: 1–90` | `decision_audit_log` group-by-type |
| P2 | `get_top_at_risk_customers` | `limit?: 1–20` | `gold_features` (F-032 v3 / `SH-M57-003` v4) |
| P2 | `get_billing_quota_status` | — | `v_billing_summary` + `enterprise_monthly_billing` (F-031 / `SH-M51-*`) |
| P1 | `get_platform_summary` | — | `workspaces` + `enterprises` + `enterprise_users` + `pipeline_runs` |
| P1 | `count_recent_signups` | `days?: 1–365` | `enterprises` |
| P1 | `find_workspaces_in_alert` | `threshold?: '80'\|'95'\|'any'` | `enterprise_monthly_billing` JOIN `enterprises` |

**Add new tool** — checklist xem `CHAT_TOOL_REGISTRY.md` §2. Em giữ nguyên forbidden args set: `enterprise_id`, `tenant_id`, `workspace_id`, `user_id`, `actor_id`, `admin_id` (K-12 + K-16).

---

## 3. K-rules — v4 update

| Invariant | Where enforced trong chat | Note v4 |
|---|---|---|
| **K-1** | Enterprise tools wrap `acquire_for_tenant(ctx.enterprise_id)` → RLS | Không đổi (ADR-0013 vẫn RLS Phase 1) |
| **K-3** | Mọi LLM call qua `llm_router.chat()` → `llm-gateway:8095` | Không đổi |
| **K-4** | Chat default `consent_external=False`. Agent **không** đọc `tenant_settings.consent_external_ai` — luôn pass `False`. | **v4 update (ADR-0015):** chat scope giữ Qwen-only Phase 1. Phase 2 mở vendor qua flag riêng `consent_external_chat` (khác `consent_external` chung dùng cho insight panel + analysis). |
| **K-7** | `ToolContext` build từ `X-Enterprise-ID` / `X-User-ID` / `X-User-Role` headers (gateway-trusted) | Không đổi |
| **K-12** | Forbidden args set; registry raise `ToolDispatchError` nếu xuất hiện | Không đổi |
| **K-15** | Mỗi enterprise dispatch ghi `decision_audit_log` row `decision_type='chat.tool_call'`. Platform dispatch chỉ structured log (audit table NOT NULL enterprise_id). | Không đổi |
| **K-16** | Chat tool args không nhận tenant identifiers — JWT only via `ToolContext` | Không đổi |
| **K-19 ⭐ NEW v4** | Mọi span trong chat path PHẢI có attribute `tenant_id`. Hiện chat code đã có (`ctx.enterprise_id`); cần verify khi OTel SDK onboard P1-S2. | Smoke test khi Phase B/C ship OTel collector |
| **K-20 ⭐ NEW v4** | LLM version pinning per workflow — chat agent gọi `llm-gateway` với pinned model `qwen2.5:14b` version `<pinned>`. Hiện chat dùng default Ollama tag → cần update `chat/agent.py` ghi `model+version` rõ ràng khi P1-LLM-004 land. | DEFERRED — sửa khi P1-S5 ship LLM version pinning |

---

## 4. Agent loop — không đổi

```
1. messages = [system, ...history, user]
2. POST llm-gateway with tools=registry.openai_tools_for_scope(scope)
3. If finish_reason='tool_calls': dispatch + loop up to MAX_HOPS (3)
4. Else: emit `message` event + `done`
```

Caps: `MAX_HOPS=3`, `MAX_TOOL_CALLS_PER_HOP=4`, `MAX_TOKENS=1500`. System prompts scope-specific.

System prompt note (giữ nguyên VN tenets, không đổi v4): "Bạn là Kaori — trợ lý AI cho doanh nghiệp..." (P2) / "Bạn là Kaori Ops — trợ lý nội bộ cho admin platform..." (P1).

---

## 5. Out of scope cho Phase 1 v4 (deliberate)

Same as v3 spec §5, **plus** v4-specific exclusions:

- **Standalone MCP server (Node.js).** Phase 2 goal. Không nằm trong P1-S1..S8 v4.
- **Conversation persistence.** No `chat_conversations` / `chat_messages` tables. Phase 2 (when ready) — sẽ là một feature code mới trong `BACKLOG_V4.md` (chưa có).
- **`execute_read_query` generic SELECT.** Multi-tenant K-1 = không có generic SQL executor. Argument không thay đổi v4.
- **Streaming token-by-token assistant text.** v0 emit single `message` event. Token streaming là follow-up; SSE wire đã hỗ trợ (FE append).
- **External chat (Claude / GPT) cho khách hàng.** Phase 2 unlock với flag `consent_external_chat` riêng (ADR-0015 Rule 4 chat). Lý do tách flag: tenant có thể opt-in `consent_external` cho analysis insight (PII redaction route đã ổn) mà KHÔNG opt-in chat (PII surface khác — chat history dài hơn, free-text user input rủi ro cao hơn).
- **Token / rate-limit Redis bucket.** Không Phase 1 v4. Hiện chỉ có hard cap `3 hop × 4 tool × 1500 tokens` per turn.
- **Insight panel integration.** P2-M210-* sẽ là feature riêng; KHÔNG gộp chat tool registry với insight panel ngay cả khi cùng dùng llm-gateway.

---

## 6. Code refactor follow-up (deferred)

Khi anh OK option (b) ở phiên sau, em refactor code theo:
1. Add OTel span instrumentation in `chat/router.py` + `chat/registry.py` (K-19).
2. Add explicit model+version pinning in `chat/agent.py` LLM call (K-20).
3. Add `consent_external_chat` flag plumbing (Phase 2 prep, default deny).
4. Move chat module under `services/ai-orchestrator/conversational/` (Phase B internal split — gather chat + future insight panel chat-mode under one package). Currently lives flat at `chat/`.
5. Standalone MCP server packaging — Phase 2.

**None of items 1–5 happens this session.** Spec/doc only per anh's choice (a).

---

## 7. MCP JSON-RPC 2.0 mapping (Round 5 N7 — Phase 2 prep)

Hiện tại (Phase 1): intra-process tool registry trong `services/ai-orchestrator/chat/`. Phase 2 EPIC-10: standalone MCP server expose tools qua JSON-RPC 2.0 cho AI clients ngoài (Claude Desktop / Cursor / Copilot).

### 7.1 MCP schema cho mỗi tool

```json
{
  "name": "summarize_recent_decisions",
  "description": "Tóm tắt các quyết định AI trong N ngày gần nhất theo loại + tenant scope",
  "inputSchema": {
    "type": "object",
    "properties": {
      "days": {"type": "integer", "minimum": 1, "maximum": 90, "default": 7}
    },
    "required": []
  },
  "metadata": {
    "tenant_scope": "required",
    "required_permission": ["VIEWER", "OPERATOR", "ANALYST", "MANAGER"],
    "rate_limit": "100 calls/hour/tenant",
    "side_effect_class": "read_only",
    "version": "1.0.0",
    "epic": "F-NEW4"
  }
}
```

Mọi tool MCP-exposed MUST có:
- `name` (snake_case, verb_object pattern)
- `description` (VN OK; FE/agent translate per locale)
- `inputSchema` JSON Schema 2020-12 (no tenant_id/user_id/workspace_id per K-12 + K-16)
- `metadata.tenant_scope` — `required` (most), `none` (system tools), `cross_tenant` (Studio Analyst với `view_mcp` claim)
- `metadata.required_permission` — role hierarchy hoặc claim list (per NFRS §5.bis)
- `metadata.rate_limit` — per-tool quota (defaults 100/hour/tenant)
- `metadata.side_effect_class` — K-17 (`pure`/`read_only`/`write_idempotent`/etc.)
- `metadata.version` — semver
- `metadata.epic` — traceback to BRD Epic

### 7.2 NEW tools cho EPIC-12 + EPIC-13 + EPIC-14 (Phase 2 expand)

#### EPIC-12 Process Mining tool

| Tool | Args | Source | Claim |
|---|---|---|---|
| `discover_workflow_from_mining` | `dept_key: str, date_range_days?: int = 90, sources?: [str]` | mig 057 + 069 → `/process-mining/sessions/start` | ANALYST+ |
| `get_mining_anomalies` | `session_id: uuid, severity?: 'high'|'medium'|'low'` | `/process-mining/sessions/{id}/findings` | ANALYST+ |
| `translate_finding_to_workflow_draft` | `finding_id: uuid` | `/process-mining/findings/{id}/translate-to-workflow` | ANALYST+ |

#### EPIC-13 Adoption Intelligence tool

| Tool | Args | Source | Claim |
|---|---|---|---|
| `get_tenant_adoption_health` | `enterprise_id?: uuid (admin only)` | mig 090 `adoption_health_snapshots` + 9 signals | CSM với `view_observability` claim |
| `trigger_intervention` | `enterprise_id: uuid, playbook_key: str, urgency?: 'low'|'med'|'high'` | `/adoption/interventions/trigger` | CSM (PLT-03) |
| `get_intervention_effectiveness` | `intervention_id: uuid, window_days?: int = 14` | post-intervention 14d compare | CSM |

#### EPIC-14 NOV / ROI tool

| Tool | Args | Source | Claim |
|---|---|---|---|
| `get_nov_monthly` | `month?: 'YYYY-MM' (default last month), dept_key?: str` | NOV ship Phase 1 | MANAGER |
| `get_nov_workflow_breakdown` | `workflow_id?: uuid, period?: str` | NOV-RPT-* | MANAGER |
| `simulate_nov_what_if` | `scenario: {workflow_changes: [...], variant?: str}` | NOV-RPT-024 | MANAGER + ANALYST |
| `get_cfo_quarterly_digest` | `quarter: 'YYYY-QN'` | `/economics/reports/manager-digest/...` | MANAGER + CFO role |

### 7.3 Standalone MCP server packaging (Phase 2 EPIC-10)

When standalone MCP server ships:
1. Tools exported via `mcp-server.json` manifest declaring above metadata
2. Auth via service-account JWT (tenant_scope embedded)
3. Rate limit enforced bằng tenant_quotas mig 099 per-tool
4. Audit log every MCP tool call (K-15) → ai_decision_audit mig 098 với `decision_type='mcp.tool_call'`
5. Drift detection (NFR-SEC-20): weekly job so sánh BE catalog vs FE registry — alert nếu lệch

### 7.4 Forbidden patterns (CRITICAL — KHÔNG để code/AI agent vi phạm)

- ❌ Tool nhận `tenant_id` / `user_id` / `workspace_id` / `actor_id` từ args (K-12 + K-16)
- ❌ Tool side_effect_class = `external` mà KHÔNG có Idempotency-Key (K-13)
- ❌ Tool gọi LLM mà KHÔNG qua llm-gateway (K-3)
- ❌ Generic SQL execution tool (security risk — SQL injection vector)
- ❌ Tool có write side-effect mà KHÔNG có K-17 declaration

### 7.5 MCP test plan (Phase 2 ship UAT)

- [ ] Manifest validation: mọi tool MUST có 8 metadata fields
- [ ] Schema validation: input args pass JSON Schema 2020-12
- [ ] K-rule pen-test: try forbidden args → expect 400 ToolDispatchError
- [ ] Rate limit: 100/hour/tenant per tool → 429 on 101st call
- [ ] Audit completeness: every tool call → ai_decision_audit row exists
- [ ] Cross-tenant block: Studio Analyst calls tenant A tool → enforced via claim `view_mcp` scope

---

## 8. References

- **v3 spec (still authoritative for code wiring):** `docs/archive/specs-v3/CHAT_TOOL_REGISTRY.md`
- **v4 architecture:** `docs/strategic/SAD_SKELETON_V2.md` Phần 25-28 (User Layer)
- **v4 LLM routing:** `CLAUDE.md` §8 + `docs/adr/0015-qwen-first-with-pluggable-vendor-adapters.md`
- **v4 K-rules:** `CLAUDE.md` §4 (K-1..K-20)
- **Insight Panel feature codes:** `P2-M210-001..016` trong `docs/BACKLOG_V4.md` (Phase 1 v4 P1-S5)
- **Code:**
  - `services/ai-orchestrator/chat/registry.py` — dispatch + audit
  - `services/ai-orchestrator/chat/agent.py` — main loop
  - `services/ai-orchestrator/chat/router.py` — endpoint + SSE
  - `services/ai-orchestrator/chat/tools/{base,enterprise,platform}.py` — tool implementations
  - `services/llm-gateway/providers.py:invoke_chat` — provider dispatch
- **UAT:** `docs/uat/CHAT_PANEL.md`
