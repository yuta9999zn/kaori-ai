# F-061 Agent Framework — retrospective

> **Status:** ✅ Shipped 2026-05-05 (commit `85509f6` + 2 follow-up fixes); merged via [PR #173](https://github.com/yuta9999zn/kaori-system/pull/173) 2026-05-05 17:05 UTC.
> **Sprint:** Phase 2 Sprint 2.6 (Phase 2 was BACKLOG_V4 before the v4 reset; mapped to that sprint slot retrospectively).
> **Spec:** `docs/specs/AGENT_FRAMEWORK.md` · **UAT:** `docs/uat/F-061-agent-insight-to-action.md`
> **Retro authored:** 2026-05-19 (closing the defer-queue item em flagged in [[project_2026_05_18_defer_queue_closeout]] — F-061 was kept, not killed; this doc is the missing post-mortem).

## What F-061 actually is

Em's first feature where the AI does more than answer read-only chat questions. It runs a multi-step workflow that may dispatch **action tools** (draft email, mark customer for review) on top of the read-only tools the Sprint 8 chat layer already exposes.

Architecture (custom Python — BRD T11 Microsoft Agent Framework decision deferred):

```
POST /api/v1/shared/agents/sessions
  → orchestrator.run_session()
     → PLANNER  (LLM call, output_schema enforced)
     → EXECUTOR (chat ToolRegistry dispatch, K-12/K-15/K-16 reused)
     → CRITIC   (LLM call, verdict: accept | replan | escalate)
     → persist agent_sessions + agent_transcripts (RLS-scoped)
```

## What shipped (v0 scope)

| Component | Where | LOC |
|---|---|---|
| Orchestrator (run_session, replan loop, escalation) | `services/ai-orchestrator/agents/orchestrator.py` | 445 |
| Planner (LLM call producing a Plan with structured PlanStep list) | `agents/planner.py` | 165 |
| Executor (ToolRegistry dispatch + result threading) | `agents/executor.py` | 126 |
| Critic (LLM verdict on whether plan output meets goal) | `agents/critic.py` | 96 |
| Workflows registry (1 production workflow + skeletons) | `agents/workflows.py` | 210 |
| Schemas (SessionRequest/Response, Plan, PlanStep, CriticVerdict, …) | `agents/schemas.py` | 198 |
| Tools registry setup (allowlist enforcement per workflow) | `agents/registry_setup.py` | 47 |
| Action tools (`agent.draft_email`, `agent.flag_for_review`) | `agents/tools/actions.py` | 253 |
| `__init__.py` re-exports | `agents/__init__.py` | 79 |
| FastAPI router (`POST /shared/agents/sessions` + invoke variant) | `agents/router.py` | 143 |
| Migration 038 (agent_sessions + agent_transcripts + RLS + append-only trigger) | `infrastructure/postgres/migrations/038_agent_sessions.sql` | 249 |
| ToolContext `dry_run: bool = False` extension | `chat/tools/base.py` | +7 |
| Main.py wire-in | `ai-orchestrator/main.py` | +6 |
| Gateway route `/api/v1/shared/**` catch-all | `RouteConfig.java` | +13 |
| Spec + UAT docs | `docs/specs/` + `docs/uat/` | 377 |

Total: **24 files, +3301 LOC**.

### The one workflow that actually runs end-to-end

`insight-to-action`:
1. Planner reads `summarize_recent_decisions` + `get_top_at_risk_customers` (Sprint 8 read-only tools).
2. Planner outputs a 2-3 step plan with action tool calls.
3. Executor dispatches `agent.draft_email` (writes a Vietnamese churn-save email to a draft slot) and/or `agent.flag_for_review` (sets a `risk_items.review_status='flagged'` row).
4. Critic verifies the plan addressed the top-risk customer + the email mentions the risk reason.
5. Verdict accepted → session persists; replan → retry with critic feedback (up to MAX_REPLAN=2); escalate → mark `requires_human_review=true` in `agent_sessions`.

### Hard caps em baked in

| Cap | Value | Why |
|---|---|---|
| `MAX_REPLAN` | 2 | Anti-runaway loop. After 2 critic replans, force-escalate. |
| `MAX_TOKENS_PER_SESSION` | 6000 | Anti-runaway cost. Gateway audit row still source-of-truth for billing per K-11 — this is em's session-level circuit breaker. |
| `dry_run` default | `True` on every action tool | Em ship action tools but they DON'T mutate by default. Caller (or future FE confirm dialog) flips `dry_run=False` after human OK. Killed an entire class of "AI accidentally emailed 1000 customers" foot-guns at the design layer. |

### Migration 038 design choice worth pinning

`agent_transcripts` is **append-only enforced by a DB trigger**, not by app code. Same pattern as `decision_audit_log` from earlier sprints. App code can't accidentally `UPDATE agent_transcripts SET step_output = ...` and rewrite history. This matters because the transcript is the audit trail for any agent-dispatched action — em want it forensics-grade.

`agent_sessions` is mutate-allowed (need to flip `requires_human_review`, `final_status`, etc), but RLS tenant_isolation + admin_bypass policies match the `risk_items` pattern from mig 033, so cross-tenant leaks fail at the row level even with a buggy controller.

## What got CUT from v0 (intentional)

Captured in `docs/PHASE2_PLAN.md` so the next sprint inherits the backlog:

| Cut item | Why deferred | Where it lands |
|---|---|---|
| 2 of 3 pre-built workflows (`data-quality-check`, `retention-campaign`) | Each needs its own action-tool review + UAT pass; em ship 1 to prove the loop, the other 2 follow | P2 follow-up sprint |
| FE `/p2/workflows` page (session list, replay, escalation queue) | FE paused per CLAUDE.md §2 | Unblocks when FE restructure resumes |
| Streaming SSE (token-by-token responses for the planner/critic) | Premature optimisation at 1 workflow | Phase 2.7+ when interactive feel matters |
| Human-in-loop escalation queue (BRD M11) | Needs FE before it's useful | Together with FE page above |
| P3 Studio surface | Studio is Phase 3 by definition | Phase 3 |
| Per-minute Redis rate limit | `MAX_TOKENS_PER_SESSION` covers cost-per-session; rate limit covers DoS — em accept the gap for v0 | Phase 2 follow-up before customer #2 |
| MS Agent Framework dep (BRD T11 still open) | Em ship custom Python today, swap to MS AF when the BRD decision lands | Track in BRD T11 |

## Tests

| Test file | Count | Coverage |
|---|---|---|
| `tests/test_agent_workflows.py` | ~5 | Workflow registry + allowlist enforcement (planner can't dispatch tools outside the workflow's allowed set) |
| `tests/test_agent_planner_critic.py` | ~10 | Planner output_schema validation + critic verdict shapes (accept / replan / escalate) |
| `tests/test_agent_action_tools.py` | ~7 | Action tool dry_run path (no DB mutation) + side-effect path (DB row written; decision_audit_log row tagged `agent.draft_email` / `agent.flag_for_review`) |
| `tests/test_agent_orchestrator.py` | ~5 | End-to-end run_session with mocked LLM + DB (planner returns plan → executor dispatches → critic accepts → session persists); replan branch; escalation branch |

**27 tests total** at ship. ai-orchestrator suite went 381 → 408 with this PR.

## What went well

1. **dry_run-by-default for action tools.** Caught zero foot-guns in v0 (no accidental mutations during testing), and now every future action tool inherits the pattern at the `chat/tools/base.py` ToolContext level. Em consider this the most valuable single line of the feature.

2. **Reused Sprint 8 ToolRegistry instead of building new dispatch.** K-12/K-15/K-16 enforcement (tenant_id never from arguments; per-call audit log) came for free. Saved ~500 LOC + the bug surface that comes with duplicating security infrastructure.

3. **DB-trigger-enforced append-only on agent_transcripts.** Same pattern as decision_audit_log — copy-paste-able, auditor-friendly. If em build a 4th audit table later, em already know the recipe.

4. **Hard caps before scale.** `MAX_REPLAN=2` + `MAX_TOKENS_PER_SESSION=6000` baked into the orchestrator constructor before the first production call. If a customer ever hits these, em surface a clear "session escalated to human review" message — no surprise OpenAI bill spike, no infinite loop hanging the orchestrator pool.

5. **Spec + UAT shipped IN THE SAME PR as the code.** `docs/specs/AGENT_FRAMEWORK.md` (200 lines) describes the planner/executor/critic loop + the v0 workflow; `docs/uat/F-061-agent-insight-to-action.md` (177 lines) has the test scenarios anh runs to accept the feature. Both shipped together so the spec can't drift from the code on day 1.

## What surfaced post-ship

| Surfaced | What happened | Lesson |
|---|---|---|
| RouteConfigTest red on first CI run | The new `/api/v1/shared/**` catch-all wasn't in the test fixture | Added to em's drift-checks list ([[feedback_endpoint_addition_drift_checks]]) — for any new endpoint, refresh ALL FOUR artefacts (RouteConfigTest + schema_snapshot + openapi spec + FE types) before first push |
| Schema snapshot missed agent_sessions tables | `schema_snapshot.txt` didn't carry mig 038's tables + RLS policies + indexes | Same drift-checks list — schema snapshot regen is part of any new-migration commit |
| OpenAPI spec drift (39 → 41 paths) | Two new `/shared/agents/...` paths added but the committed snapshot didn't reflect it | Same |
| FE TypeScript types stale | `frontend/lib/api/types/orchestrator.d.ts` missing SessionRequest/SessionResponse/Plan/CriticVerdict (+295 lines) | Same — FE types regen via `npm run codegen:orchestrator` after openapi refresh |

These all surfaced as PR #173 follow-up commits `90e0af3` + `b898e7a` BEFORE merge (em caught them in CI). Two extra commits = ~30 min of fix work. The memory entry [[feedback_endpoint_addition_drift_checks]] now codifies the 4-artefact checklist so the next agent-style feature pays this cost once, not four times.

## Cost guardrails — what em learned about LLM-driven agents

The `MAX_TOKENS_PER_SESSION=6000` cap was set conservatively. Em observed in UAT (against the mocked LLM in tests + 3 real runs against Qwen2.5:14b local):

| Workflow phase | Token avg | Why |
|---|---|---|
| Planner | ~800-1200 | Plan output_schema is structured; LLM doesn't ramble |
| Executor → tool result back to LLM | ~600 per tool call × 2-3 tools | Tool results are the chunky part — em didn't truncate at v0 |
| Critic | ~400-800 | Just a verdict + 1-2 sentence reasoning |

Total per accepted plan: **2000-3500 tokens**. Per replan (up to 2): another 2000-3500 each. Worst-case session: 6000-10000. Em set the cap at 6000 because most accepted runs land at ~3K, and forcing escalation at 6K means anh almost never pays for a 3-replan runaway. If em were starting over today em'd probably set 8000 — but 6000 hasn't caused customer-visible degradation in 14 days production.

## Follow-up backlog (tracked, not done)

| Item | Priority | When |
|---|---|---|
| Ship `data-quality-check` workflow (2nd of 3 v0 set) | P1 | Next Phase 2 sprint after FE unblocks |
| Ship `retention-campaign` workflow (3rd of 3) | P1 | Same |
| FE `/p2/workflows` session list + replay viewer | P0 (blocks customer-visible feature) | When FE restructure resumes per CLAUDE.md §2 |
| Human-in-loop escalation queue (BRD M11) | P1 | After FE page |
| Per-minute Redis rate limit | P2 | Before customer #2 (anti-DoS hardening) |
| Streaming SSE for planner/critic responses | P3 | Phase 2.7+ — only if interactive UX needs it |
| MS Agent Framework adoption decision (BRD T11) | P2 | Anh's call when MS AF stabilises + benchmarks |
| Tool-result truncation in executor (avoid pumping 600+ tokens of tool output back into planner context) | P2 | Profile-driven — em didn't see budget pressure in v0, watch when 2nd/3rd workflow ships |
| Tenant-level disable flag for agent action tools (some customers will want read-only agent + manual action) | P1 | Driven by first customer who asks |

## Key cross-references

- PR #173: <https://github.com/yuta9999zn/kaori-system/pull/173>
- Commits: `85509f6` (feature) · `90e0af3` (drift fixes) · `b898e7a` (FE types) · `9495565` (merge)
- Spec: `docs/specs/AGENT_FRAMEWORK.md`
- UAT: `docs/uat/F-061-agent-insight-to-action.md`
- Migration: `infrastructure/postgres/migrations/038_agent_sessions.sql`
- Drift-checks memory: [[feedback_endpoint_addition_drift_checks]]
- Defer-queue closeout (where em flagged this retro as missing): [[project_2026_05_18_defer_queue_closeout]]
- Sprint 8 chat infra reused: `services/ai-orchestrator/chat/tools/`
- BRD T11 (Microsoft Agent Framework adoption decision): tracked in `docs/product/BRD_v4.docx` (gitignored)
- Phase 2 retro that surfaced the backlog deferrals: `docs/sprint/P2_RETRO_PHASE2_CLOSEOUT.md`
