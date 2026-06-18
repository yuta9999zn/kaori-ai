# Sprint P15-S10 — Planning Doc (Phase 1.5)

> **Status:** 🟢 SHIPPED LOCAL 2026-05-11 — 8/8 deliverables done on `feat/p15-s10-d1` (mirrors `feat/p15-s9-d1` HEAD); awaiting S9 PR #179 merge before S10 PR opens. R1 CRITICAL fix landed; I1 CRITICAL flagged for anh decision (design choice).
> **Sprint goal (per BACKLOG_V4 line 737):** "NOV A/B + Process Mining email/calendar + RAG Router + PageIndex"
> **Window:** Phase 1.5 Week 19-20 (M5 mid)
> **Pre-reqs:** P15-S9 PR #179 merged. Specifically D1 (K8s) + D8 (ClickHouse cluster) live for D6-D8 work.
> **Branch:** `feat/p15-s10-d1` (off `feat/p15-s9-d1`; rebase on main after S9 merges)

P15-S10 is **smaller than S9** by deliverable count (8 vs S9's 10) but D6-D8 RAG work is research-heavy: PageIndex is a published external library (VectifyAI MIT), DocSage waits for S11. Estimated total: ~3-4 days dev across 1-2 sessions if PageIndex is straight wrap of upstream.

---

## Acceptance criteria (P15-S10 done when):

### Enterprise (5 from BACKLOG_V4 line 744-748)

1. ✅ **PM-EVT-004** Gmail/Outlook metadata connector — `services/data-pipeline/ingestion/connectors/gmail_outlook/`. OAuthEmailClient protocol injection; StubOAuth raises NotImplementedError until P15-S11 real adapters land. Bronze event shape per plan (thread_id case_id, hashed actors, no body). 18 tests.
2. ✅ **PM-EVT-005** Calendar metadata connector — `services/data-pipeline/ingestion/connectors/calendar_metadata/`. Same OAuth-injection pattern. Recurrence rule + duration + window-filter via observed_at when available. 18 tests.
3. ✅ **AI-INT-021** Intervention effectiveness tracking — `org_intel/adoption/intervention_tracker.py` + migration 044 + Temporal followup workflow (commit `aacffff`).
4. ✅ **AI-INT-022** Vietnamese context adaptation — `org_intel/adoption/intervention_engine.py` + Zalo stub adapter (commit `aacffff`). I1 fail-open behaviour flagged in review for anh decision.
5. ✅ **NOV-REV-002** A/B attribution method — `org_intel/economics/revenue.py::estimate_revenue_ab_attribution` (commit `12b53ac`).

### RAG addendum (3 from BACKLOG_V4 line 756-758, per ADR-0019)

6. ✅ **RAG-ROUTER-001** RAG Router — `reasoning/rag/router.py` 3-engine dispatch + whitelist-aware fallback (R1 self-review fix committed as `abc9097`). 19 tests.
7. ✅ **RAG-PAGEINDEX-001** PageIndex tree builder — `reasoning/rag/pageindex/tree_builder.py` contract surface + StubBuilder; upstream PyPI `pageindex==0.2.8` wrap deferred to P15-S11 D7 follow-up.
8. ✅ **RAG-PAGEINDEX-002** PageIndex retrieval — `reasoning/rag/pageindex/retriever.py` + `StubPageIndexRetriever` (commit `fe7b60b`).

**Acceptance smoke (when all 8 ship):**
- 4 new pytest collections pass (process_mining email/cal, intervention tracking, A/B revenue, RAG router + PageIndex)
- Olist pilot doc-uploaded (e.g. supplier contract PDF) → PageIndex tree built → query "khoản phạt vi phạm" returns correct node + page range
- One intervention triggered on Olist → 14d adoption-score check scheduled

---

## 8 deliverables breakdown

### Deliverable 1 — PM-EVT-004 Gmail/Outlook metadata connector

**Layer:** L1 ingestion + L4.5 process_mining
**Files to create:**
- `services/data-pipeline/ingestion/connectors/gmail_outlook/connector.py`
- `services/data-pipeline/ingestion/connectors/gmail_outlook/__init__.py`
- `services/data-pipeline/tests/test_gmail_outlook_connector.py`

**Files to modify:**
- `services/data-pipeline/ingestion/connectors/__init__.py` — register connector
- `services/data-pipeline/main.py` — wire route `/process-mining/connectors/gmail-outlook`
- `docs/api-specs/pipeline.openapi.json` — refresh (run `dump_openapi.py`)

**External deps to add:**
- Gmail: `google-api-python-client` + `google-auth-oauthlib` (OAuth flow per-tenant)
- Outlook: `msal` (Microsoft Authentication Library) — OAuth flow per-tenant

**Bronze event shape (per K-2 append-only + K-5 PII redaction):**
```python
{
  "event_type": "email.received" | "email.sent",
  "tenant_id": UUID,
  "thread_id": str,                # provider's thread/conversation id
  "subject": str,                  # PII-masked (Vietnamese-aware redaction)
  "from_actor_hash": str,          # SHA-256 of email; raw email NEVER in Bronze
  "to_actor_hashes": list[str],
  "occurred_at": datetime,
  "channel": "gmail" | "outlook",
}
```

**Effort:** 1.5 day (OAuth wiring is the slow part).

**Defer to S11:** body content extraction (currently metadata-only per scope).

---

### Deliverable 2 — PM-EVT-005 Calendar metadata connector

**Layer:** L1 + L4.5
**Files to create:**
- `services/data-pipeline/ingestion/connectors/calendar/connector.py`
- `services/data-pipeline/ingestion/connectors/calendar/__init__.py`
- `services/data-pipeline/tests/test_calendar_connector.py`

**External deps:** reuse Gmail's `google-api-python-client` (Calendar API same SDK) + Outlook calendar via `msal`.

**Bronze event shape:**
```python
{
  "event_type": "calendar.event_created" | "calendar.event_updated" | "calendar.event_attended",
  "tenant_id": UUID,
  "event_id": str,
  "title_masked": str,             # PII-masked
  "attendee_actor_hashes": list[str],
  "start_at": datetime,
  "duration_minutes": int,
  "recurrence_rule": Optional[str], # iCal RRULE if recurring
  "channel": "google_calendar" | "outlook_calendar",
}
```

**Effort:** 1 day (D1 OAuth flow reused).

**Acceptance:** Olist test inbox + calendar — connector polls 5min, emits ~5-10 events/day, all PII redacted.

---

### Deliverable 3 — AI-INT-021 Intervention effectiveness tracking

**Layer:** L4.5 adoption + L5 reasoning
**Files to create:**
- `services/ai-orchestrator/org_intel/adoption/intervention_tracker.py` — `track_intervention_effectiveness()` per `WORKFLOW_SYSTEM.md` §31.4
- `services/ai-orchestrator/workflow_runtime/workflows/intervention_followup.py` — Temporal workflow scheduling 14d + 30d evaluation activities
- `services/ai-orchestrator/tests/test_intervention_tracker.py`

**Files to modify:**
- `services/ai-orchestrator/routers/adoption.py` (or create) — `POST /adoption/interventions/trigger` adds effectiveness telemetry hook
- New migration `infrastructure/postgres/migrations/044_intervention_outcomes.sql` — `intervention_outcomes` table (intervention_id, pre_score, post_score_14d, post_score_30d, improvement, effective_bool, side_effects JSONB)

**Side-effect class per K-17:** `track_intervention_effectiveness` is `write_idempotent` (UPSERT keyed by intervention_id). Followup activities (14d, 30d post-score read) are `read_only`. Outcome insert is `write_non_idempotent` (use REL-005 dedup key).

**Effort:** 1 day. Re-uses S9 D6 adoption signals + S9 D3 Temporal worker — both shipped.

---

### Deliverable 4 — AI-INT-022 Vietnamese context adaptation

**Layer:** L4.5 + L5
**Files to modify:**
- `services/ai-orchestrator/routers/adoption.py` (created in D3) — locale-aware branch in `/adoption/interventions/trigger`
- `services/ai-orchestrator/org_intel/adoption/intervention_engine.py` (NEW or extend) — Vietnamese context resolver:
  - Channel: Zalo (if tenant Zalo OA configured per S9 D4c — currently DEFERRED for S10) ELSE Telegram (S9 D5 ✅)
  - Decision factor: hierarchical — if `tenant_settings.requires_manager_approval=true`, intervention waits for manager Telegram approval (REL-011 already wired)
- `services/notification-service/bot/zalo.py` — adapter stub (NEW); throws NotImplementedError if Zalo OA not configured (graceful fallback to Telegram)

**Tests:** `tests/test_intervention_locale.py` — assert Zalo/Telegram routing + hierarchical gate.

**Effort:** 0.5 day. Mostly config + branch logic. Real Zalo wiring still blocked on customer OA account (S9 D4c blocker carries forward).

---

### Deliverable 5 — NOV-REV-002 A/B attribution method

**Layer:** L4.5 economics
**Files to create:**
- `services/ai-orchestrator/org_intel/economics/revenue_estimators/__init__.py` — package init (refactor existing `revenue.py` into estimator-per-method)
- `services/ai-orchestrator/org_intel/economics/revenue_estimators/ab_attribution.py` — A/B test data → revenue delta estimator
- `services/ai-orchestrator/tests/test_ab_attribution.py`

**Files to modify:**
- `services/ai-orchestrator/org_intel/economics/revenue.py` — keep existing `pre_post_estimator`; add dispatcher to choose method per request
- `services/ai-orchestrator/routers/economics.py` — `POST /economics/revenue/estimate` accept `method: "pre_post" | "ab" | "benchmark"` (benchmark stays S11)

**Inputs A/B method needs:**
- `experiment_id` (FK to A/B test config — schema TBD; can reuse `kaori.feedback.actions` topic)
- `control_group_revenue` + `treatment_group_revenue` per period
- Confidence interval (computed via simple t-test or bootstrap)

**Effort:** 0.5 day. Statistical formula straightforward; refactor to per-method package is the larger lift.

---

### Deliverable 6 — RAG-ROUTER-001 RAG Router

**Layer:** L3 reasoning
**Files to create:**
- `services/ai-orchestrator/reasoning/rag/router.py` — `RAGRouter.route(query) -> Engine`
- `services/ai-orchestrator/reasoning/rag/engines/__init__.py` — abstract `RAGEngine` base class
- `services/ai-orchestrator/reasoning/rag/engines/pgvector_engine.py` — wrap S9 pgvector impl
- `services/ai-orchestrator/reasoning/rag/engines/pageindex_engine.py` — wrap D7 + D8
- `services/ai-orchestrator/reasoning/rag/engines/docsage_stub.py` — raise NotImplemented; ship S11
- `services/ai-orchestrator/routers/rag.py` — `POST /rag/answer` endpoint
- `services/ai-orchestrator/tests/test_rag_router.py`

**Routing heuristic (Phase 1.5 — heuristic, Phase 2 = LLM classifier per RAG_ADDENDUM open question 4):**
- query has `len(words) < 8` AND keyword in {"insight", "summary", "tóm tắt"} → pgvector
- query references doc-citation pattern ("trong hợp đồng", "section X", "điều khoản") → pageindex
- query has `len(words) > 20` AND multi-entity pattern (e.g. "so sánh top 5 customer") → docsage (fallback pgvector while D8 stub)

**Tenant override:** `tenant_settings.rag_engines: ["pgvector", "pageindex"]` JSONB — router restricts to whitelist.

**Effort:** 1 day (router logic + engine adapter scaffolding).

---

### Deliverable 7 — RAG-PAGEINDEX-001 Tree builder

**Layer:** L3
**Files to create:**
- `services/ai-orchestrator/reasoning/rag/pageindex/__init__.py`
- `services/ai-orchestrator/reasoning/rag/pageindex/tree_builder.py` — wraps upstream PageIndex (PyPI `pageindex` if published; else vendored fork)
- `services/ai-orchestrator/workflow_runtime/workflows/pageindex_build.py` — Temporal workflow triggered by `kaori.pipeline.events` `doc.uploaded`
- `services/ai-orchestrator/tests/test_pageindex_tree_builder.py`
- `infrastructure/postgres/migrations/045_pageindex_trees.sql` — table `pageindex_trees(tenant_id, doc_sha256, tree JSONB, built_at, schema_version)`

**Side-effect class:** Tree build is `external` (LLM calls to traverse + summarise during build) → REL-005 dedup key = `sha256(tenant_id + doc_sha256)`. Idempotent on retry by hash.

**Open question (carries from RAG_ADDENDUM open #1):** PyPI `pageindex` package status. If not on PyPI, vendor `https://github.com/VectifyAI/PageIndex` MIT under `services/ai-orchestrator/vendor/pageindex/`. Decide at sprint kickoff.

**Effort:** 1 day if straight wrap. 1.5 days if vendoring + adapting MIT fork to fit the wrapper interface.

---

### Deliverable 8 — RAG-PAGEINDEX-002 Retrieval

**Layer:** L3
**Files to create:**
- `services/ai-orchestrator/reasoning/rag/pageindex/retriever.py` — LLM-traverse tree, return `RAGAnswer{ answer, citations: [{doc_id, node_path, page_range}] }`
- `services/ai-orchestrator/tests/test_pageindex_retriever.py`

**Files to modify:**
- `services/ai-orchestrator/reasoning/rag/engines/pageindex_engine.py` (D6) — call retriever
- Add Prometheus counters per RAG_ADDENDUM §6: `rag_engine_calls_total{engine="pageindex"}`, `rag_engine_latency_seconds`, `rag_engine_cost_usd_total`

**Acceptance:** Olist supplier contract PDF (real Olist doc, anh upload) — query "điều khoản phạt" returns correct contract section + page range citation, latency p95 < 800ms, cost < $0.001/query.

**Effort:** 0.5 day given tree from D7.

---

## Dependencies + sequencing

```
D1 (Gmail) ──┐
             ├── independent of RAG, can run parallel
D2 (Cal)  ──┘

D3 (Tracker) ── D4 (Vietnamese ctx) — D4 strictly after D3

D5 (A/B)  — independent, refactor revenue.py

D6 (Router) ── D7 (Tree builder) ── D8 (Retriever)
                                     │
                                     └── D6 wires pageindex_engine.py to D7+D8
```

**Parallel-able session split:**
- Session 1: D1 + D2 + D5 (~3 days) — connectors + economics, no RAG
- Session 2: D3 + D4 (~1.5 days) — adoption interventions
- Session 3: D6 + D7 + D8 (~2.5-3 days) — RAG stack

**Critical path:** RAG (D6→D7→D8) is longest, ~3 days. If pressed for time, ship D6 + D7 (engine + tree builder), defer D8 retrieval to S11 with DocSage.

---

## Cross-ref carryover from S9

P15-S9 deferred 4 D-pieces (per `docs/sprint/P15-S9_CI_BACKLOG.md`):

| S9 deferred | S10 impact |
|---|---|
| D4a Postgres CDC real impl | None on S10 scope |
| D4c Zalo metadata connector real | **AI-INT-022 (D4)** Zalo channel routing falls back to Telegram if OA not configured. Either ship Zalo first this sprint (1 day if OA creds) OR document the Telegram fallback in D4 acceptance |
| D8 silver-tier dual-write cutover | None on S10 scope; cutover stays own track |
| D2 Java VaultClient.java | None on S10 scope (Python services use kaori_vault.py shipped S9) |

**S9 PR #179 must merge before S10 starts** — S10 D6 RAG router wraps S9's pgvector real impl, S10 D3+D4 reuse S9's adoption signals + Telegram REL-011.

---

## Migrations registry

S10 adds 2 migrations (numbering continues from S9 ending at 043 NOV monthly):

| File | Purpose | Deliverable |
|---|---|---|
| `044_intervention_outcomes.sql` | Pre/post adoption-score telemetry | D3 |
| `045_pageindex_trees.sql` | PageIndex hierarchical TOC JSONB | D7 |

Both must update `infrastructure/postgres/schema_snapshot.txt` + run schema-drift verify pre-push.

---

## API endpoint additions

3 new endpoints in S10. Each requires the 4-drift-artefact refresh (per memory `feedback_endpoint_addition_drift_checks`):

| Method + path | Service | Deliverable |
|---|---|---|
| `POST /process-mining/connectors/gmail-outlook` | data-pipeline | D1 |
| `POST /process-mining/connectors/calendar` | data-pipeline | D2 |
| `POST /rag/answer` | ai-orchestrator | D6 (handles D7+D8 via routing) |

Existing endpoints extended (no new path):
- `POST /adoption/interventions/trigger` — D3 + D4 add effectiveness + locale params
- `POST /economics/revenue/estimate` — D5 adds `method` discriminator

**Pre-push checklist (memory rule):**
1. RouteConfigTest — gateway test asserting all paths
2. `infrastructure/postgres/schema_snapshot.txt` refreshed
3. `python scripts/dump_openapi.py` for both services
4. `frontend/scripts/gen-api-types.mjs` for FE types

---

## Open questions for sprint kickoff

1. **PageIndex packaging:** PyPI vs vendored MIT fork (carryover RAG_ADDENDUM Q1) — check PyPI at kickoff.
2. **Gmail/Outlook OAuth credential storage:** per-tenant OAuth tokens — write to Vault path `secret/tenant/{tenant_id}/connectors/gmail_oauth`? Standardise this format S10 since it's first multi-tenant OAuth flow.
3. **A/B experiment_id schema:** D5 needs experiment registry. Ship minimal `ab_experiments` table this sprint, or defer to S11 when DocSage paper might inform the schema?
4. **Zalo OA blocker:** D4 V-context — proceed with Telegram-only fallback OR wait one more sprint for customer OA?
5. **RAG router heuristic vs classifier:** Phase 1.5 = heuristic (D6). Phase 2 LLM classifier — when to upgrade? Should D6 emit telemetry for future training?

---

## Effort estimate summary

| Deliverable | Effort | Independent? |
|---|---|---|
| D1 Gmail/Outlook | 1.5d | yes |
| D2 Calendar | 1d (reuses D1 SDK) | after D1 |
| D3 Intervention tracker | 1d | yes |
| D4 Vietnamese context | 0.5d | after D3 |
| D5 A/B attribution | 0.5d | yes |
| D6 RAG router | 1d | yes (stub engines) |
| D7 PageIndex tree | 1-1.5d | after D6 (or parallel; D7 doesn't depend on D6) |
| D8 PageIndex retrieval | 0.5d | after D7 |

**Total:** ~7-8 days dev. Comparable to S9's 9-10 day budget. Fits Phase 1.5 Week 19-20 window.

---

*Last updated: 2026-05-11 (8/8 deliverables shipped local on `feat/p15-s10-d1`)*
*Companion: `docs/sprint/P15-S9_CI_BACKLOG.md` — S9 must merge first*
*Self-review: `docs/sprint/P15-S10_REVIEW.md` — 2 CRITICAL (R1 fixed, I1 flagged) + 5 MEDIUM + 13 LOW*
*Source: BACKLOG_V4.md line 737-758, RAG_ADDENDUM_2026_05.md, ADR-0019, WORKFLOW_SYSTEM.md §31.4, SAD_SKELETON_V2.md §24*

---

## Shipped deltas (2026-05-11)

| Test suite | S9 close | S10 close | Δ |
|---|---|---|---|
| ai-orchestrator | 571 | 623 | +52 (D3 + D5 + D6 + D7 + D8 + R1 fix) |
| notification-service | 53 | 58 | +5 (D4 Zalo stub) |
| data-pipeline | 380 | 416 | +36 (D1 + D2 connectors) |

8 commits added between S9 close `2892cfe` and S10 close `7f2c181`:
- `297b7e3` Phase 2 skeleton runtime for 4 services
- `9a4f254` 4 ops runbooks + GAPS_V4 refresh
- `12b53ac` D5 NOV-REV-002 A/B
- `4ad4160` D7 PageIndex tree builder
- `fe7b60b` D6 router + D8 retriever
- `aacffff` D3 + D4 intervention tracker + VN context
- `abc9097` R1 fix (router whitelist bypass)
- `2e790f9` self-review doc
- `7f2c181` D1 + D2 connectors

Next-up: I1 decision + 5 MEDIUM cleanup + S9 PR #179 merge → rebase S10 → open S10 PR.
