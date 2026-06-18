# Agent Framework (F-061) — Sprint 2.6

> **Status:** ✅ shipped 2026-05-05 (PR _pending_)
> **Scope:** Phase 2.6 v0 — one workflow (`insight-to-action`), 2 action tools, BE-only.
> **Predecessor:** Sprint 8 chat tool registry (F-NEW4) — same `ToolRegistry` class reused.
> **Consumed by:** future `/p2/workflows` page (FE follow-up); P3 Studio surface (Phase 3).

This document is the contract surface for `services/ai-orchestrator/agents/**`.
It explains:

1. The two endpoints + their wire format.
2. The Planner → Executor → Critic loop semantics.
3. Workflow + tool catalog (v0 = 1 workflow, 2 action tools).
4. Governance gates (K-3 / K-4 / K-12 / K-15 / K-16) and where each fires.
5. What is intentionally **not** in v0.

If you're touching `services/ai-orchestrator/agents/**` you should read all five.

---

## 1. Endpoints

| Method | Path                                                  | Auth                                  | Body            | Response          |
|--------|-------------------------------------------------------|---------------------------------------|-----------------|-------------------|
| POST   | `/api/v1/shared/agents/sessions`                      | JWT (any P2 role); X-Enterprise-ID    | `SessionRequest`| `SessionResponse` |
| POST   | `/api/v1/shared/agents/workflows/{workflow_id}/invoke`| JWT (any P2 role); X-Enterprise-ID    | `SessionRequest` (workflow_id ignored — path wins) | `SessionResponse` |

Both are **synchronous** — caller blocks until the loop terminates
(typically 5-15 s for one Qwen-local run). No streaming SSE in v0;
follow-up adds an `/agents/sessions/{id}/stream` endpoint.

### `SessionRequest`

```json
{
  "workflow_id": "insight-to-action",
  "input": { "insight_id": "11111111-1111-1111-1111-111111111111" },
  "dry_run": true
}
```

| Field         | Type         | Notes |
|---------------|--------------|-------|
| `workflow_id` | string       | Must match `workflows.WORKFLOWS` key. v0: `"insight-to-action"`. |
| `input`       | object       | Validated against the workflow's `input_schema`. |
| `dry_run`     | bool         | **Default TRUE.** Action tools record what they WOULD do but skip side-effects. Set FALSE only when the caller has reviewed the dry-run output. |

### `SessionResponse`

```json
{
  "session_id":   "...",
  "workflow_id":  "insight-to-action",
  "status":       "completed",
  "dry_run":      true,
  "plan":         { "steps": [...], "rationale": "..." },
  "transcripts":  [ { "step_index": 0, "role": "planner", ... }, ... ],
  "critic_verdict": { "action": "accept", "reason": "...", "issues": [] },
  "tokens_used":  0,
  "replan_count": 0,
  "error_message": null
}
```

`status` is one of:

| Status        | Terminal? | Meaning |
|---------------|-----------|---------|
| `planning`    | ❌        | Planner LLM call in flight (only seen on a poll mid-run) |
| `executing`   | ❌        | Executor running tool steps |
| `critiquing`  | ❌        | Critic LLM call in flight |
| `completed`   | ✅        | Critic verdict=`accept`. Workflow done OK. |
| `failed`      | ✅        | Hard error (gateway down, no plan, token budget blown). `error_message` set. |
| `escalated`   | ✅        | Critic verdict=`escalate` OR replan loop hit MAX_REPLAN. Surface to a MANAGER for review. |

---

## 2. Loop semantics

```
[PLAN] -> [EXECUTE] -> [CRITIC]
                           |
                           +-- action=accept   -> status=completed (terminal)
                           +-- action=escalate -> status=escalated (terminal)
                           +-- action=replan   -> back to [PLAN]
                                                  bounded by MAX_REPLAN=2;
                                                  exceeding the cap forces
                                                  status=escalated.
```

Hard caps (in `orchestrator.py`):

* `MAX_REPLAN = 2` — a critic can ask for replan at most twice before
  the orchestrator forces escalation. Without this an evil insight
  could trap the agent in a planner→critic infinite loop.
* `MAX_TOKENS_PER_SESSION = 6000` — soft budget across all LLM calls
  in one session. The gateway audit rows are the source of truth for
  billing; this is a runaway-cost backstop.

Plan caps (enforced by `Plan` Pydantic validator):

* `min_items=1, max_items=10` — fewer than 1 step = no-op; more than
  10 = planner artefact.
* No two consecutive identical steps (same tool + same args).

---

## 3. Workflow catalog (v0)

ONE workflow ships in PR1. Two more on the roadmap as follow-ups.

### `insight-to-action`

| Field           | Value |
|-----------------|-------|
| Description     | Turn an at-risk insight into a draft email + flag for human review |
| Input schema    | `{ insight_id: <uuid> }` (required) |
| Allowed tools   | `summarize_recent_decisions`, `get_top_at_risk_customers`, `draft_followup_email`, `mark_customer_for_review` |

Planner prompt (Vietnamese) tells the model: read first, action second,
max 6 steps, each step has rationale, **never** put `enterprise_id` /
`tenant_id` / `user_id` in args (registry rejects).

Critic prompt asks 3 questions:
1. Has the workflow goal been met? (i.e. draft email + mark for review)
2. Did any step fail in a recoverable way (replan)?
3. Any sign of PII leak / scope violation (escalate)?

### Tool catalog used by the agent loop

The agent registry (`registry_setup.py`) is a **superset** of the chat
registry — it adds 2 action tools while reusing the 6 chat tools. Each
workflow narrows further via `allowed_tools`.

| Tool | Source | Args | Side effect |
|------|--------|------|-------------|
| `summarize_recent_decisions`     | chat (Sprint 8) | `days?: 1-90` | none (read) |
| `get_top_at_risk_customers`      | chat (Sprint 8) | `limit?: 1-20`| none (read) |
| `get_billing_quota_status`       | chat (Sprint 8) | —             | none (read) — NOT in `insight-to-action` allowlist |
| `draft_followup_email`           | **agents (this PR)** | `customer_external_id, subject, body` | INSERT decision_audit_log row tagged `agent.draft_email` |
| `mark_customer_for_review`       | **agents (this PR)** | `customer_external_id, reason, priority?` | INSERT decision_audit_log row tagged `agent.flag_for_review` |

Both action tools honour `ToolContext.dry_run` — when TRUE they return
a `would_action` preview without writing.

---

## 4. Governance — where each invariant fires

| Invariant | Where enforced |
|-----------|----------------|
| **K-1** (RLS) | `agent_sessions` + `agent_transcripts` carry RLS policies (migration 038). Action tools wrap DB writes in `acquire_for_tenant`. |
| **K-3** (LLM router) | All planner / critic / chat-style LLM calls go through `engine.llm_router.complete_structured` — never direct SDK. |
| **K-4** (consent) | Both planner + critic pass `consent_external=False` (Qwen local) regardless of tenant `consent_external_ai`. CLAUDE.md §8 Rule 7 extended. External-agent unlocks behind a separate `consent_external_agent` flag in Phase 2.7. |
| **K-6** (audit) | One `agent_transcripts` row per planner step + per executor step + per critic step. Plus the gateway's own K-6 audit on each LLM call. |
| **K-12** (tenant_id JWT-only) | `ToolContext` built in router from gateway-trusted X-Enterprise-ID. Action tools read `ctx.enterprise_id`, never an args field. |
| **K-15** (per-tool audit) | Reused from chat — `ToolRegistry.dispatch` writes `decision_audit_log` with `decision_type='chat.tool_call'` for enterprise tools. Agent tools also write their OWN audit row inline (different `decision_type` so /p2/decisions can filter). |
| **K-16** (forbidden args) | Reused from chat — registry's `_FORBIDDEN_ARG_KEYS` set is the single point of enforcement. Identical to chat path. |

Defence-in-depth: even if a future endpoint refactor bypasses the
router, the registry still enforces forbidden-arg rejection. Even if
the planner LLM hallucinates a tool name outside the allowlist,
`planner.plan_workflow` catches it before the executor runs.

---

## 5. Out of scope (do not ask why these aren't in PR1)

* **Streaming SSE.** v0 returns the final SessionResponse; FE polls or
  shows a "running…" until the response lands.
* **2 of 3 pre-built workflows.** `data-quality-check` and
  `retention-campaign-draft` are follow-up PRs once the loop is proven.
* **Human-in-loop escalation queue.** M11 milestone in the BRD. v0
  status `escalated` is read-only on `/decisions`; no assignment flow.
* **Tenant-defined workflows.** Catalog is code-only (`workflows.py`).
  A tenant cannot register their own — `agent_sessions.workflow_id`
  is validated against the static registry before anything runs.
* **MS Agent Framework dependency.** BRD T11 deferred. Custom Python
  P/E/C is small (~300 LOC) and the interface is narrow enough to
  swap to MS AF later if pilot feedback warrants.
* **External-agent (Claude / GPT) unlock.** Phase 2.7 — separate
  `consent_external_agent` tenant flag.
* **P3 Studio surface.** Phase 3 (`/api/v3/studio/agents/{build,run,inspect}`).
* **Token / rate-limit budgets per minute.** Soft cap is per-session
  (6000 tokens). Per-minute Redis bucket is a follow-up.

---

## 6. Reference

* `services/ai-orchestrator/agents/__init__.py` — module-level docstring (architecture diagram)
* `services/ai-orchestrator/agents/orchestrator.py:run_session` — coordinator + persistence
* `services/ai-orchestrator/agents/planner.py:plan_workflow` — planner LLM call
* `services/ai-orchestrator/agents/executor.py:execute_steps` — step dispatcher (reuses chat registry)
* `services/ai-orchestrator/agents/critic.py:review_session` — critic LLM call
* `services/ai-orchestrator/agents/workflows.py:WORKFLOWS` — catalog
* `services/ai-orchestrator/agents/tools/actions.py` — 2 action tools
* `infrastructure/postgres/migrations/038_agent_sessions.sql` — tables + RLS
* `services/ai-orchestrator/tests/test_agent_*.py` — 27 unit tests
* `docs/uat/F-061-agent-insight-to-action.md` — UAT script
