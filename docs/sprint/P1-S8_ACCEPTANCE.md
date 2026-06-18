# Sprint P1-S8 — Acceptance Mapping (Phase 1 v4 final sprint)

> **Sprint goal:** "Zalo Bot + final polish + beta launch" → pivoted to **Telegram Bot via pluggable adapter** (anh chốt 2026-05-08, ADR-0018)
> **Status:** ✅ shipped pluggable bot adapter + 16 unit tests + Phase 1 v4 closeout doc + tag `v4.0-phase1-complete`
> **Branch:** `feat/v4-p1-s8` (parent: `feat/v4-p1-s7`)
> **Date:** 2026-05-08

This is the **final Phase 1 v4 sprint**. 296 features in BACKLOG_V4 P1-S8 — most map to existing Phase 1 v3 features (auth/MFA/sessions/F-007/F-013/F-015/F-016/F-022/F-029/F-030/F-031/F-032 + Phase 2 Sprint 2.1/2.2 already shipped: F-033..F-041, F-060). 91 Studio + Personal features deferred (no portals).

Net new this sprint:
- Pluggable bot adapter package (`services/notification-service/bot/`) replacing the original Zalo Bot scope per ADR-0018.
- ADR-0018 capturing the Telegram-over-Zalo decision + adapter pattern rationale.
- Phase 1 v4 closeout doc summarising 8 sprints + cumulative test counts.
- CLAUDE.md §14 Phase Status updated (all 8 P1 v4 sprints done).

---

## Net new work shipped this sprint

| Feature | Description | Implementation |
|---|---|---|
| **BACKLOG_V4 P1-S8 "Zalo Bot" supersedes to Telegram Bot via pluggable adapter** | Zalo OA needs tax registration 2025; Telegram is free + open. Anh chốt design adapter so swap to Zalo / Line / Slack later is config-only (`KAORI_BOT_PROVIDER=...`). | `services/notification-service/bot/{__init__.py, base.py, telegram.py, README.md}` — `BotAdapter` ABC + `TelegramBotAdapter` impl + `WorkflowApprovalMarkup`/`ApprovalButton`/`BotSendError` dataclasses + `get_bot_adapter()` factory |
| ADR-0018 | Telegram over Zalo + adapter pattern rationale | `docs/adr/0018-pluggable-bot-adapter-telegram-default.md` |
| 16 unit tests | Adapter contract + factory dispatch + Telegram impl + MarkdownV2 escaping | `services/notification-service/tests/test_bot.py` |
| Phase 1 v4 closeout doc | 8-sprint summary + cumulative tests + deferred-to-P15 list | `docs/archive/PHASE1_V4_CLOSEOUT.md` |
| CLAUDE.md §14 update | All 8 P1 v4 sprints ticked done; tech stack §2 mentions bot adapter | `CLAUDE.md` modified |
| Tag | `v4.0-phase1-complete` annotated tag at the closeout commit | `git tag -a v4.0-phase1-complete` |

---

## Existing features mapped (296 total — most via prior sprints)

P1-S8 backlog row count breakdown:

| Audience | Total | Mapped to existing | New this sprint | Deferred |
|---|---|---|---|---|
| Platform | 28 | 27 (F-007/F-008/F-010/F-011/F-012/F-013/F-015 etc.) | 0 | 1 (per-tenant audit feed UI — Phase 2) |
| Enterprise | 134 | 132 (F-016/F-022/F-029/F-030/F-031/F-032/F-NEW3 + Phase 2 F-033..F-041, F-060) | 0 | 2 (custom subdomain Phase 2; report builder Phase 2) |
| Studio | 43 | 0 | 0 | 43 (no Studio portal) |
| Personal | 48 | 0 | 0 | 48 (no Personal portal) |
| Cross-cutting | 43 | 41 (F-031 cron + F-NEW1 outbox + F-041 explainability + audit + RLS already shipped) | 2 (bot adapter + ADR) | 0 |
| **Totals** | **296** | **200** | **2** | **94** |

Key existing-feature mappings (selective, not exhaustive):

- **`P2-M20-001` Đăng nhập Enterprise User** → F-007 + auth-service `AuthController.login`
- **`P2-M20-004/005/006` Reset password / logout / change password** → F-007 + P1-S1 P2-M20-007 first-login force-change-pwd
- **`P2-M210-002..016` Insight panel + RAG + LLM choice** → F-029 explainability + F-041 + Sprint 8 chat tool registry (CHAT_TOOL_REGISTRY_V4)
- **`P2-M215-*` + `P2-M216-*` Decision log + override** → F-029 + F-036
- **`P2-M219-*` Quota tab + upgrade** → F-030 + F-031
- **`PM-OUT-028..033` Process Mining output stages** → P1-S7 HeuristicMiner result already provides direct_follows + avg_durations + event_counts which the report function will read; full PM-OUT-029 workflow YAML auto-generation lands P15-S9 (needs more PM real-world data)
- **`NOV-RPT-019..022` Manager email digest + ROI dashboard** → P1-S7 NOV core ready; P15-S9 wires cron + dashboard endpoint + bot push
- **`SH-M61-*` Payment methods** + **`SH-M62-*` Invoice email** + **`SH-M63-*` Subscription mgmt** → F-031 + F-NEW1 already shipped

---

## Quick-run smoke command

```bash
cd "D:\Kaori System\services\notification-service" && python -m pytest -q   # 33 pass (+16)
cd "D:\Kaori System\services\ai-orchestrator" && python -m pytest -q          # 507 pass (unchanged)
cd "D:\Kaori System\services\data-pipeline" && python -m pytest -q             # 367 pass + 1 skip
cd "D:\Kaori System\services\llm-gateway" && python -m pytest -q               # 96 pass
```

**Total: 1,003 Python pass** (was 987 after P1-S7, +16 from bot adapter tests). **Phase 1 v4 closeout milestone — 1K Python tests** ✅

---

## Files touched this sprint (P1-S8)

```
services/notification-service/
  bot/__init__.py                         NEW (factory + re-exports)
  bot/base.py                             NEW (BotAdapter ABC + dataclasses)
  bot/telegram.py                         NEW (TelegramBotAdapter + TelegramBotConfig)
  bot/README.md                           NEW (adapter pattern guide)
  tests/test_bot.py                       NEW (16 tests — factory + ABC + Telegram impl)

docs/adr/
  0018-pluggable-bot-adapter-telegram-default.md   NEW

docs/sprint/P1-S8_ACCEPTANCE.md           NEW (this file)
docs/archive/PHASE1_V4_CLOSEOUT.md                NEW (Phase 1 v4 closeout summary)

CLAUDE.md                                 MODIFIED (§14 sprint tracker → all 8 done; §2 bot adapter mention)
```

7 NEW + 1 MOD. **Smallest sprint footprint** (final polish + closeout).

---

## What this sprint did NOT do (deferred / not in scope)

- **Telegram bot full impl** (httpx call, webhook receiver, command parser, Vault token resolution) — Phase 1.5 P15-S9.
- **PM-OUT-029 workflow YAML auto-generator from MinedWorkflow** — requires more PM real-world data; P15-S9.
- **NOV-RPT-019/021 manager email digest + ROI dashboard** — engine ready (P1-S7 compute_monthly_nov); cron + bot push P15-S9.
- **AI-INT-018 CSM alert generation** — adoption health classification ready P1-S7; CSM endpoint + Slack/PagerDuty wire P15-S9.
- **drift Olist 12 file** — still stashed `drift-olist-pre-p1-s3`. Anh xử riêng.
- **Frontend** — paused per anh.

---

## Phase 1 v4 status after Sprint P1-S8

**8/8 sprints complete.** See `docs/archive/PHASE1_V4_CLOSEOUT.md` for the comprehensive closeout summary.

Tag created: `v4.0-phase1-complete` annotated at this commit.

Next milestone: Phase 1.5 (M5-M6) — 4 sprints stabilisation + critical gaps. Per BACKLOG_V4 Phase 1.5:
- P15-S9 90-day testing infra + Adoption full 9 signals (4 remaining) + K8s deploy + Telegram real impl + Vault prod
- P15-S10 NOV A/B attribution + Process Mining email/calendar sources + 3 more AI nodes + ClickHouse Silver migration
- P15-S11 10 more workflow templates + perf tuning + public APIs read-only
- P15-S12 Public APIs + bug fix from real load + onboard to 15 customers

---

## References

- `docs/BACKLOG_V4.md` Phase 1 P1-S8 (296 features)
- `docs/archive/PHASE1_V4_CLOSEOUT.md` (this sprint's bigger sibling — full Phase 1 v4 retro)
- `docs/adr/0018-pluggable-bot-adapter-telegram-default.md`
- `services/notification-service/bot/README.md`
- `docs/_v4_extract/sprint_phase1.json` — raw 296-feature list
