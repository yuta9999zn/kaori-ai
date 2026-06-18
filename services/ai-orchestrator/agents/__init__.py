"""
F-061 Agent Framework — Planner / Executor / Critic loop.

Sprint 2.6, Phase 2. First feature where the AI does more than answer
read-only chat questions: it runs a multi-step workflow that may
dispatch *action* tools (draft email, mark customer for review) on
top of the read-only tools the Sprint 8 chat layer already exposes.

Architecture
============

::

    POST /api/v1/shared/agents/sessions
       │
       ▼
    orchestrator.run_session()
       │
       ├── 1. PLANNER (planner.plan_workflow)
       │      LLM call (output_schema enforced) → ordered list of steps
       │
       ├── 2. EXECUTOR (executor.execute_steps)
       │      For each step:
       │        ├── dispatch via chat.registry.ToolRegistry
       │        │     (reuses K-12/K-15/K-16 enforcement +
       │        │      6 chat tools + 2 new action tools)
       │        └── append agent_transcripts row
       │
       ├── 3. CRITIC (critic.review_session)
       │      LLM call (output_schema enforced) → verdict
       │        ok=true             → status=completed
       │        ok=false + replan   → re-PLAN (capped at MAX_REPLAN=2)
       │        ok=false + escalate → status=escalated (human review)
       │
       └── persist: agent_sessions row updates + agent_transcripts append

Why custom Python instead of Microsoft Agent Framework
======================================================

The BRD T11 decision ("MS Agent Framework vs LangGraph vs custom")
has not been finalised by CTO/ML Lead. Three reasons to roll custom
for v0:

  1. Pattern is small (~300 LOC core). MS AF would add a heavy dep
     (Python preview release, AutoGen Studio = full GUI tool we don't
     need) for a thin wrapper around 3 LLM calls.
  2. We already have ``chat.registry.ToolRegistry`` enforcing K-12 /
     K-15 / K-16 — the right tool-calling primitive lives in the
     Sprint 8 chat module. MS AF would either duplicate this or force
     us to wrap.
  3. Swap to MS AF later is cheap: the 3-method orchestrator interface
     (plan -> execute -> critique) maps directly onto MS AF's
     PlannerAgent / ExecutorAgent / CriticAgent classes.

When pilot feedback warrants more sophisticated behaviour (parallel
planner, agent-to-agent negotiation, learned routing) we revisit.

What's intentionally out of scope (PR1)
=======================================

* **Streaming SSE** — return final SessionResult; FE polls or refreshes.
* **2 of 3 pre-built workflows** — only ``insight-to-action`` ships
  in PR1. ``data-quality-check`` and ``retention-campaign-draft`` are
  follow-up PRs once the loop is proven on the first vertical.
* **Human-in-loop escalation queue** — M11 milestone. v0 status
  ``escalated`` is read-only on the dashboard; no assignment workflow.
* **P3 Studio surface** — Phase 3 (BE-ST-301..303). Same orchestrator
  reused under /api/v3/studio/agents/*.
* **Tenant-defined workflows** — workflow catalog is code-only.

References
==========

* ``services/ai-orchestrator/chat/registry.py`` — tool registry reused here
* ``services/ai-orchestrator/engine/llm_router.py`` — complete_structured (Issue #3)
* ``infrastructure/postgres/migrations/038_agent_sessions.sql`` — tables + RLS
* ``docs/specs/AGENT_FRAMEWORK.md`` — architecture deep-dive
* ``docs/uat/F-061-agent-insight-to-action.md`` — UAT script
"""
