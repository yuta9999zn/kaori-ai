# Sprint History — Kaori AI v4

> Tách từ `CLAUDE.md` §14 ngày 2026-05-22 để giảm context size. File này = lịch sử commit shipping của các sprint v4. Đọc khi cần audit "wave nào ship gì / commit hash / test delta".
>
> Snapshot trạng thái mới nhất giữ trong `CLAUDE.md` §14 (1 dòng/sprint). Lịch sử v3 lưu tại `docs/archive/CLAUDE_v2.5.0.md` và `docs/archive/BACKLOG_v3.md`.

---

## Migration v3 → v4 (Phase A/B/C in `docs/RESTRUCTURE_PROPOSAL.md`)

- **Phase A — Documentation freeze (2026-05-08):** ✅ tạo strategic/* + BACKLOG_V4 + API_CATALOG_V4 + GAPS_V4 + RESTRUCTURE_PROPOSAL + 8 ADRs (0010-0017) + rewrite CLAUDE.md + archive v3 trackers. **Không touch code.**
- **Phase B — Code restructure (chờ anh duyệt):** internal split `data-pipeline/` + `ai-orchestrator/` theo v4 layer; skeleton folder + service.yaml cho 4 service mới (process-mining, adoption-intel, economics, workflow-engine) + 6 infra (temporal, clickhouse, minio, vault, otel, k8s). Không break API. Pilot Olist không gián đoạn.
- **Phase C — Sprint P1-S1 (chờ Phase B):** 21 features; 18 đã có, 3 net new (OBS-012 structured logger, P2-M20-007 first-login force-change-pwd, smoke test suite). ~3.5 ngày dev. K8s defer P15-S9.

### Branching

```
main            ← pilot Olist + Phase 2 v3 frozen (hotfix only)
docs/v4-reset    ← Phase A docs (em đã làm xong)
feat/v4-restructure ← Phase B (chờ anh OK)
feat/v4-p1-s1   ← Phase C Sprint 1
feat/f-061-...   ← (open) merge to main as deprecated experiment, không tính burndown v4
```

---

## Phase 1 (M1-M4)

| Sprint | Status |
|---|---|
| P1-S1 — Cluster ready, monorepo, CI/CD, basic auth | ✅ a465ca0 |
| P1-S2 — Multi-tenancy + RLS + Vault setup | ✅ 783a9ac (Task C deferred → P15-S9) |
| P1-S3 — First 3 connectors + Bronze tier (MinIO) | ✅ c2799f6 (skeleton + Phase B-2 bronze move) |
| P1-S4 — Silver + Gold + data quality | ✅ 76a5b27 (Phase B-2 silver+gold move complete) |
| P1-S5 — Reasoning Layer + LLM integration | ✅ 104b05b (K-20 + OBS-008 + reasoning/) |
| P1-S6 — Workflow Engine contract + idempotency | ✅ 62cd0b3 (K-17 + REL-002/004/005; Temporal worker → P15-S9) |
| P1-S7 — Process Mining v1 + Adoption + NOV basic | ✅ 5b7c153 (3 NEW org_intel modules; runtime → P15-S9) |
| P1-S8 — Telegram Bot pluggable adapter + closeout | ✅ Phase 1 v4 complete; tag `v4.0-phase1-complete` |

**Phase 1 v4 closeout 2026-05-08** — see `docs/archive/PHASE1_V4_CLOSEOUT.md`. 1003 Python pass + 31 Java AuthService + 3 Java IT compile. 8 sprints × 9 commits on linear branch chain `docs/v4-reset` → `feat/v4-p1-s8`. drift Olist stashed `stash@{0}` since P1-S3.

---

## Phase 1.5 (M5-M6)

| Sprint | Status |
|---|---|
| P15-S9 — K8s + Vault HA + Temporal + Telegram + Adoption full + NOV cron + ClickHouse | ✅ 8/10 D-pieces ship + pushed origin 2026-05-12 (`feat/p15-s9-d1`). PR #179 OPEN, CI red (budget exhausted → June reset). Defer to P2: D2 Java VaultClient, D4a Postgres CDC real, D4c Zalo metadata real, D8 dual-write cutover, K8s FPT Cloud provision, Temporal worker cutover. |
| P15-S10 — NOV A/B + PM email/cal + RAG router + PageIndex | ✅ 8/8 D-pieces ship + HTTP layer wired 2026-05-12. 5 endpoints exposed: `/rag/answer`, `/adoption/interventions/trigger`, `/process-mining/connectors/{gmail-outlook,calendar}`, `/economics/revenue/estimate`. PageIndex PyPI wrap stub-only (defer to P2). |
| P15-S11 — DocSage + Stage 5/7/12 + Memory storage adapters + perf | ✅ shipped 2026-05-17. DocSage D1→D6 end-to-end (`7a47b17`..`c6e47c5`) + Stage 5 Ontology 7-Primitives (`7c02538`) + Stage 7 Memory 4-tier (`2ed08e4`) + Stage 12 Loop A/B+Promotion (`1e0e620`) + Phase 2 storage adapters Postgres/Redis/Neo4j/Temporal (`d4ab620`..`09cbe7a`) + NOV-REV-006 variance + NOV-CST-012 cost amort (`a37f215`) + OBS-005 head-based sampling (`b503259`). ai-orch 623→1144 (+521 tests). |
| P15-S12 — CFO report + SLO alerting | ✅ shipped 2026-05-17. NOV-RPT-020 CFO quarterly digest (`66d2d31`) + OBS-017 SLO burn-rate alerts + OBS-020 SLI/SLO Grafana dashboards (`ddda88b`). |

**Phase 1.5 closeout 2026-05-17** — branch `feat/p15-s9-d1` HEAD `3d434e4`, 110+ commits ahead of `main`. All 4 sprints ship. Test deltas through Phase 1.5: ai-orchestrator 514→1261, notification-service 31→58, data-pipeline 366→~510, llm-gateway 96→102. **Deferred to Phase 2** (carried forward, NOT Phase 1.5 blockers): D2 Java VaultClient, D4a Postgres CDC connector real, D4c Zalo metadata connector real, D8 dual-write cutover, PageIndex PyPI wrap, K8s FPT Cloud cluster provision, Temporal worker live cutover (worker code ready, gated behind `TEMPORAL_ENABLE_WORKER=true`).

---

## Phase 2 (M7-M12)

| Sprint | Status |
|---|---|
| P2-S13 — All 8 PM sources operational | ✅ shipped 2026-05-17 (`a299bf5`). PM-EVT-006 Slack/Teams + PM-EVT-007 Microsoft SharePoint + PM-EVT-008 Generic webhook connectors. |
| P2-S14 — PM advanced algos + bypass detection + cohort | ✅ shipped 2026-05-17 (`c83fb84`). 5 anomaly detectors (PM-ANM-023..027) + Inductive/Fuzzy Miners (PM-ALG-016/017) + AI-HSC-016 cohort comparison. Established 8-section test methodology template at `tests/test_p2_s14_pm_algorithms.py`. |
| P2-S15 — Visual workflow builder (45 nodes + 25 templates) | ✅ shipped 2026-05-17 (`d0e959f`). Mig 068 `node_type_catalog` 45-row + mig 069 25 production templates × `industry_vertical` tag + `/workflow-node-types` + `/shared/agents/studio/builder/palette` (28 curated nodes) + 35 tests. |
| P2-S16 — Multi-user collab + Workflow as Code | ✅ shipped 2026-05-17. Workflow as Code = `POST /workflows/import` + `GET /workflows/{id}/export.yaml` validated against mig 068 catalog (`e438482`, +15 tests). Multi-user collab = mig 072 `workflow_editors/comments/locks` + 10 endpoints with K-13 anti-IDOR lock token (`ff8fd22`, +28 tests). |
| P2-S17 — Mobile app (read + approve) | ⏳ Features:0 — no scope in BACKLOG_V4, skip. |
| P2-S18 — Observability deep-dive | ✅ shipped 2026-05-17 (`1886ca8`). Row renamed from "SSO + MFA + field-level encryption" → "Observability deep-dive" because actual features are OBS-018/021/023, not security. OBS-018 anomaly detection (z-score + EWMA) + OBS-021 capacity planning (linear regression) + OBS-023 session replay (opt-in, mig 073) + 36 tests. Security carved out to new P2-S25. |
| P2-S19/P2-S20 — Microservices extraction | ⏭ **DEFERRED Phase 3** (decision 2026-05-18). Monolith sufficient at 100-customer scale; Phase B-2 internal boundaries already clean → Phase 3 extraction = file move. ADR-0010 updated. |
| P2-S21 — Workflow ontology + OKR mapping + T-Cube reasoning | ✅ shipped 2026-05-17. **T-Cube trace-augmented reasoning** (ADR-0021 + paper arXiv 2605.03344) D1-D4 + cron wiring + real llm-gateway adapter (`8b460a1`/`db9d6ba`/`e438482`/`050d835`, +79 tests). **OKR framework** P2-M212-001 (mig 071 + 9 endpoints `/p2/strategy/okr`) + **NOV-RPT-023 recommendations** + **NOV-RPT-024 simulation** (`24cf91e`, +36 tests). PLAYBOOK §2 rewritten (ADR-0022 org-first onboarding). |
| P2-S22 — Custom AI fine-tuning (MAX tier) | ⏳ not started — niche feature, low priority Phase 2. |
| P2-S23 — English UI + first non-VN customer | ⏳ not started — FE paused. |
| P2-S24 — 100 customer milestone + Phase 2 retro | ⏳ not started — Week 47-48. |
| P2-S25 ⭐ NEW — SSO + MFA + field-level encryption | ✅ shipped 2026-05-17→18. **P2-AUTH-001 SSO Google** live end-to-end 2026-05-18 (mig 083 + `shared/sso_providers/` + `routers/sso.py` + Java `SsoController/SsoExchangeService` + gateway sso-public route + JwtAuthFilter pre-auth whitelist + FE `/sso-callback` page + login button; browser-tested with `nguyentruongan25051997@gmail.com` Google account). Microsoft provider code-complete but inactive (anh provision M365 Dev tenant when ready). **P2-AUTH-002 MFA TOTP** + **P2-ENC-001 field encryption** shipped 2026-05-17 (`b46bdca`, mig 074, 43 tests). **F-NEW11 follow-up 2026-05-18:** field-key history (mig 080) + re-encrypt worker (`shared/field_key_rotation.py`) + 2 endpoints `/p2/auth/field-key/reencrypt[/status]` + 41 tests. Closes latent bug where rotation overwrote `key_ref` in-place. **F-NEW12 2026-05-18:** SSO Google end-to-end (this row). |
| P2.5 ⭐ NEW — MinerU pattern borrow + AI node catalog | ✅ shipped 2026-05-18→19 (10/10 BE done; FE bbox highlight UI waits FE restructure). **Patterns 1+2** block taxonomy + header/footer strip (`25e82be`). **Detection wire-in + spoof guard** ingestor whitelist by magic-byte-aware document_type (`7dfa2b1`). **Pattern 3** pdfplumber tables → TABLE blocks with markdown+html+rows metadata (`34afe4b`). **classify_document + extract_structured_data** AI nodes (`2792f21`, mig 085 catalog). **summarise_document + sentiment_analysis + dedup_records** (3 light nodes, `99471cd`, mig 086 — dedup is K-17 PURE, others read_only LLM). **Pattern 4** multi-column reading-order reconstruction via pdfplumber bbox + X-histogram bimodality detection (`be6867a`). **OCR Qwen2-VL adapter** /v1/ocr in llm-gateway + data-pipeline ocr_client + ingestor escape hatch on `unsupported_today`; K-4 ENFORCED at schema level (no consent_external on OcrRequest, pinned by test) — vendor vision = Phase 3 + ADR (`1c4667c`). **compare_to_template** RAG-backed contract diff with clause extraction → BGE-M3 embed → cosine match → per-pair LLM diff → 17-keyword risk bump → risk score 0..1 (`0ce5115`, mig 087). **Pattern 5 bbox BE foundation** (`e0ce848`) — Bbox dataclass on Block + populated from pdfplumber `find_tables()` for TABLE blocks; TEXT blocks bbox=None until paragraph chunking lands (Phase 2.6); FE highlight UI waits FE restructure. Test deltas: ai-orchestrator 1554→1899 (+345), data-pipeline 519→691 (+172), llm-gateway 102→178 (+76). |

**Phase 2 + 2.5 progress 2026-05-19 EOD** — `feat/p15-s9-d1` HEAD `0ce5115`, **185 commits ahead `main`**. ai-orchestrator **1874 tests pass / 0 failing**, llm-gateway 178, data-pipeline 663 (minus 4 pre-existing test_tenant_db.py MagicMock failures noted, unrelated). 12 new migs (068-074 P2; 080+083 SSO; 084 Vault grants; 085-087 P2.5 catalog extensions; 086 = node_type_catalog rows for the 9 P2.5 nodes). 4 new ADRs (0021 T-Cube, 0022 org-first onboarding, 0023 knowing-doing-gap heuristic, 0025 MinerU "borrow patterns NOT lib"; note 0024 was taken by Mem0 port — ADR-0025 is the MinerU sibling).

---

## Workflow Execution Closeout (post-2.5, gap audit driven)

| Step | Status |
|---|---|
| Audit 2026-05-19 — Gap finding | 25 mig 069 templates = seed-only; 45 catalog nodes but only 14 Temporal activities, none mapping to catalog keys; no `POST /workflows/{id}/run`; Temporal worker default OFF. **64% of 39 documented workflows non-executable.** |
| **Commit 1** Node executor registry + 6 first-wave + run endpoint | ✅ `d77cccd` (2026-05-19). `node_executor.py` ABC + REGISTRY singleton + coverage_report; 6 executors (`if_else`/`switch`/`aggregate` pure, `read_table` read_only, `update_record` write_idempotent, `send_email` external w/ K-13 dedup); `runner.py` Kahn topo-sort + per-node persistence + `run_in_background`; mig 088 `workflow_runs` + `workflow_run_nodes`; 4 endpoints `POST /workflows/{id}/run` (202 + RFC 7807 on missing executors) / `GET /workflow-runs/{id}` / `/nodes` / `/workflows/{id}/runs`; notification-service `workflow-freeform` template added. 37 new tests. ai-orch 1900→1936. |
| **Commit 2** Approval gate + form submission + resume | ✅ `def7a4f`. `ApprovalGateExecutor` (auto_threshold for tiered flows + pause/resume via workflow_approvals); `ReadFormSubmissionExecutor`; mig 089 `workflow_approvals` + `workflow_form_submissions` with RLS; resume-aware runner (preload completed nodes + resolved approvals before topo loop, idempotent re-run); 3 endpoints `GET/POST /workflow-runs/{id}/approvals,approve` + `POST /workflow-form-submissions`; K-13 anti-IDOR cross-check `X-User-Role` ∈ approver_roles[]. 20 new tests. ai-orch 1936→1955. **Registry coverage 6→8 of 45 (18%)**. |
| **Commit 3** Adoption hourly Temporal cron + activation runbook | ✅ `f8ca879`. 4 Temporal activities wrap existing `org_intel.adoption` (list_active_tenants/compute_snapshot/persist/trigger_intervention); `AdoptionHourlyAggregatorWorkflow` fan-out with per-class retry policies; mig 090 `adoption_health_snapshots` with at-risk partial index; `docs/runbooks/workflow-execution-enable.md` (Step 1 verify migs / Step 2 in-process path live today / Step 3 enable Temporal worker `TEMPORAL_ENABLE_WORKER=true` + schedule CLI for adoption/nov/memory crons / Step 4 holster / Step 5 8-symptom troubleshooting). 9 new tests. ai-orch 1955→1964. Temporal workflows 5→6. |
| **Coverage status post-closeout** | **8 of 45 catalog executors registered**; covers approval-driven templates (Discount/Refund/Invoice/Budget/Proposal/Vendor Pay = 6/25 = 24%); 37 remaining executors stub-mapped in runbook §2d (AI nodes wrap llm-gateway, action nodes wrap external integrations, data nodes wrap connectors). In-process runner production-ready (no Temporal needed); cron path runbook-ready (TEMPORAL_ENABLE_WORKER flip + CLI). |
| **Wave 2b** 8 AI node wrappers | ✅ commit `f433fff` (2026-05-19). `executors/ai.py` ships 8 read_only nodes wrapping llm-gateway: `classify_text` · `generate_narrative` · `rag_query` · `call_insight_engine` · `call_risk_detection` · `call_forecasting` (pure compute, linear regression) · `extract_entities` · `call_recommendation_engine`. Each handles input validation + LLM dispatch via `complete_structured` + output coercion (clamping, OOV-coerce, JSON repair fallback). 39 new tests pin per-executor behaviour with stubbed llm_router. **D.3 NPS Follow-up + E.1 Inventory Restock now fully LIVE 5/5 nodes.** Test suite: ai-orchestrator 1964 → 2003 passed. Templates now: 9 LIVE (was 7), 16 PARTIAL (was 11), 14 SEED (was 21). **Registry: 8 → 16 of 45 (36%)**. |
| **Wave 3** 10 output/action/validate/data nodes | ✅ commit `cd2b460` (2026-05-19). 4 new executor files: `output.py` (publish_insight + publish_alert + create_task + display_dashboard + save_to_database), `action.py` (call_api with K-13 in-process dedup + SSRF host allowlist + trigger_workflow child-run spawner + generate_report queue-then-render), `validate_exec.py` (pure JSON Schema validator — type/enum/range/length/pattern/array/nested-object), `data.py` extended with `read_email` (claim-from-intake-queue with SELECT FOR UPDATE SKIP LOCKED). mig 091: 5 new tables — workflow_insights / workflow_alerts / workflow_tasks (UNIQUE task_key) / workflow_dashboard_tiles (UNIQUE dashboard_key+tile_key) / workflow_email_intake — all with RLS isolation. 42 new tests. Test suite: ai-orchestrator 2003 → 2045 passed. **17 of 25 templates fully LIVE 5/5 nodes** (B.1/B.2/B.4 marketing + C.1/C.2/C.4/C.5 sales + D.1/D.3/D.4/D.5 CS + E.1/E.4/E.5 warehouse + F.2/F.4/F.5 finance). 5 PARTIAL (4/5 — B.3/B.5/C.3/E.3/F.1). 3 SEED still need scheduled_trigger + filter + send_chat_message + log (D.2 SLA Escalation / E.2 Supplier Audit / F.3 Monthly Close). 39-workflow totals: **24 LIVE (62%) / 12 PARTIAL (31%) / 3 SEED (8%)**. **Registry: 16 → 26 of 45 (58%)**. |
| **Wave 4** 8 utility nodes — closeout complete | ✅ commit `<TBD>` (2026-05-19). New `executors/utility.py`: scheduled_trigger (pure marker — Temporal Schedule provides actual cron) + filter (pure predicate via reused `_eval_condition`) + transform (pure project/rename/derive with map/fn/literal) + split (pure half/fraction/predicate split + deterministic seed for testing) + join (pure inner/left list join with prefix_right) + log (structlog pure emission) + send_chat_message (external — INSERT into workflow_chat_outbox with K-13 dedup via source_ref) + read_webhook (read_only — SELECT FOR UPDATE SKIP LOCKED claim from workflow_webhook_intake). mig 092: 2 new tables — workflow_chat_outbox + workflow_webhook_intake. 40 new tests. ai-orchestrator 2045 → 2085 passed. **All 8 remaining templates flip LIVE**: B.3 VIP + B.5 A/B + C.3 Renewal + D.2 SLA + E.2 Supplier + E.3 QC + F.1 Invoice + F.3 Monthly Close. **ALL 25/25 mig 069 business templates fully executable**. **Registry: 26 → 34 of 45 (76%)**. |
| **Wave 5** 11 final nodes — 100% catalog coverage | ✅ commit `<TBD>` (2026-05-19). New `executors/wave5.py`: `sort` + `merge` (concat/interleave/dedupe_keys) + `deduplicate` (composite-key keep-first/last) + `enrich` (read_only master left-join from TABLE_WHITELIST) + `wait_for_condition` (polling SELECT until match/timeout, POLL_WHITELIST ⊂ workflow_* tables) + `read_api` (HTTP GET mirror of call_api with shared host allowlist) + `read_calendar` / `read_chat` (claim from new intake tables via SELECT FOR UPDATE SKIP LOCKED) + `read_file_upload` (lookup `bronze_files` by file_id with K-12 RLS) + `send_sms` (workflow_chat_outbox channel='sms') + `export_file` (write_idempotent INSERT workflow_export_files queue). mig 093: workflow_calendar_intake + workflow_chat_intake + workflow_export_files + ALTER workflow_chat_outbox.channel CHECK to add 'sms'. 43 new tests. ai-orchestrator 2085 → 2128 passed. **Registry: 34 → 45 of 45 (100% catalog coverage)**. |
| **Closeout complete 2026-05-19** | Seven commits later (d77cccd→def7a4f→f8ca879→835269c→f433fff→cd2b460→bf2aa0d→`<W5 TBD>`): all 25 templates fully LIVE end-to-end via in-process runner; 100% catalog coverage. Registry 45/45. ai-orchestrator suite 1900 → 2128 (+228 tests). Templates LIVE: 0 → 25. Branch `feat/p15-s9-d1` ~204 commits ahead `main`. |

---

## Phase 2.6 — Orchestration Hardening (anh's architectural review 2026-05-19)

Following catalog closeout, anh raised 6 distributed-systems concerns: orchestration coupling / Temporal SPOF / Gold scaling / Ontology research-project risk / priority ordering / "biggest risk is distributed operational correctness, not AI quality". Em accepted all 6 + scoped 12 items P0/P1/P2.

### P0 — Operational Correctness Foundation

| Item | Status |
|---|---|
| **P0.1 Event sourcing** `workflow_events` | ✅ `c4eb59d`. mig 094 append-only table with immutability triggers + 15-value event_type enum + per-run monotonic sequence_no. event_store.py: EventType / WorkflowEvent / RunProjection dataclasses + async append_event + load_event_stream + pure project_state. Runner wired to emit workflow_created/started/resumed/paused + per-node started/completed/failed/skipped/paused/approval_resolved + terminal completed/failed. 13 new tests. ai-orch 2128 → 2141. |
| **P0.2 Formal state machine** | ✅ `1b3e9ae`. state_machine.py: WorkflowRunState + NodeRunState enums + ALLOWED_WORKFLOW + ALLOWED_NODE frozensets. transition_workflow_status() + transition_node_status() — atomic SELECT FOR UPDATE + validate + UPDATE. StateTransitionDenied exception. 53 new tests. ai-orch 2141 → 2194. |
| **P0.3 Persistent idempotency_records** | ✅ `e68f841`. mig 095 workflow_idempotency_records + RLS. idempotency_store.py: derive_key (SHA-256) + get_or_set (atomic SELECT FOR UPDATE handling miss/hit/expired) + record_outcome + sweep_expired. call_api executor now tiers: in-process cache → persistent ledger → HTTP. Worker restart no longer re-fires POST. 10 new tests. ai-orch 2194 → 2204. |
| **P0.4 Replay harness** | ✅ `8d54230`. replay.py: ReplayHarness + ReplayResult + CachedSnapshot + diff_projection_vs_snapshot pure comparator + assert_projection_matches_cached pytest helper. 15 new tests. ai-orch 2204 → 2219. |
| **P0 closeout 2026-05-19** | **All 4 P0 items complete.** Runtime now: (1) proves state via replay, (2) detects projection drift, (3) refuses illegal transitions, (4) dedupes external side effects across worker restarts. ai-orch suite 2128 → 2219 (+91). |

### P1 — Distributed Readiness

| Item | Status |
|---|---|
| **P1.1 Module split** runner→state_store + state_machine | ✅ `54caed7`. state_store.py extracts DB CRUD from runner.py. Runner methods now thin-wrap state_store; public surface unchanged so existing callers + tests untouched. |
| **P1.2 Worker pool isolation** queue routing | ✅ `6ddb099`. queue_routing.py with 3-tier queues (kaori-critical-finance / kaori-default / kaori-low-priority). route_node_to_queue() applies rule chain. 24 tests. Runbook in `docs/sprint/PHASE_2_6_DEFER_QUEUE.md`. |
| **P1.3 Gold incremental** CDC → ClickHouse | ⏳ DEFER (infra-gated). Design + cutover plan in defer-queue. Needs Kafka + Debezium + ClickHouse cluster. |
| **P1.4 Compensation runtime** saga | ✅ `54caed7`. compensation.py with COMPENSATION_REGISTRY + 4 builtin handlers (send_retraction_email / cancel_approval_request / delete_task / retract_alert). run_compensation_chain() walks completed external/write_non_idempotent nodes in REVERSE + invokes registered handler. 15 tests. |
| **P1 status** | 3 of 4 shipped; 1 defer (infra-gated). |

### P2 — Analytics + Ontology Governance

| Item | Status |
|---|---|
| **P2.1 ClickHouse cutover** | ⏳ DEFER (infra-gated). Helm chart in `infrastructure/clickhouse/` already; needs cluster provisioning + Debezium pipeline. |
| **P2.2 Lifecycle FSM** | ✅ `6ddb099`. mig 096 lifecycle_state_transitions. Seeded with 9 transitions: customer (lead/active_customer/at_risk/churned with win_back recovery) + asset (draft/published/archived). governance.py validate_lifecycle_transition(). |
| **P2.3 Edge taxonomy governance** | ✅ `6ddb099`. mig 096 ontology_edge_types. Seeded with 11 v0 edges. governance.validate_edge_type() — free-form edges blocked. |
| **P2.4 Streaming pipeline** | ⏳ DEFER (infra-gated). Flink/ksqlDB design in defer-queue. |
| **P2 status** | 2 of 4 shipped; 2 defer (infra-gated). |

**Phase 2.6 closeout 2026-05-19** — **9 of 12 items shipped, 3 in defer-queue.** Code-only items production-ready. Infra-gated: P1.3 (CDC) + P2.1 (ClickHouse) + P2.4 (Streaming) — full design in `docs/sprint/PHASE_2_6_DEFER_QUEUE.md`. ai-orch suite 2128 → 2279 (+151 tests across 8 commits c4eb59d→6ddb099).

---

## Phase 2.7 — Production-Readiness Governance Layer (anh's 3-dim review 2026-05-19)

Following Phase 2.6 close, anh raised a 3-dimension production-readiness review pushing Data Pipeline / Distributed Runtime / Observability-Governance from "trung bình-khá" to "cao". Em scoped 5 items around lineage / ops console / quotas / AI governance / declarative policy.

| Item | Status |
|---|---|
| **P1 Data lineage tracking** | ✅ `011965b`. mig 097 `data_lineage_edges` with 12 ObjectKind enum + RLS + ON CONFLICT idempotent ingestion. `shared/lineage.py`: record_edge / record_edges_batch / walk_upstream / walk_downstream (BFS w/ cycle detection + max_depth/max_nodes caps). 2 endpoints `GET /lineage/{kind}/{id}/{upstream,downstream}`. 14 new tests. |
| **P1 DLQ recovery console** | ✅ `011965b`. `routers/dlq_console.py`: 5-source unified ops surface — Kafka DLQ + Redis stream DLQ + workflow_run failed + workflow_idempotency_records expired + workflow_compensation logs. Endpoints `GET /admin/dlq` / `POST /admin/dlq/{source}/{id}/{retry,replay,requeue,discard}`. 22 new tests. |
| **P3 AI governance audit** | ✅ `5e750b2`. mig 098 `ai_decision_audit` with conditional immutability trigger. Captures model_version + model_provider + prompt_hash + prompt_size + context_refs jsonb + confidence + output_hash + output_validated + consent_external + pii_redacted + latency_ms + token counts + cost_cents + human_override fields. 9 tests. |
| **P3 Declarative policy engine** | ✅ `5e750b2`. mig 099 `policy_rules` seeded with 3 K-rule conversions: k4_consent_external_required (global deny) + finance_invoice_cfo_threshold (global require_approval) + mfa_required_super_admin (role deny). `shared/policy_engine.py`: PolicyDecision dataclass + evaluate_condition (pure recursive eval) + evaluate (top-level walks rules in priority order, first match wins) + 60s TTL cache. 14 tests. |
| **P2 Tenant quotas** | ✅ `5e750b2`. mig 099 `tenant_quotas` + `tenant_quota_usage` — both RLS-scoped. Seeded 5 default quota types: llm_tokens_external (per_day 1M), llm_tokens_local (per_day 10M), workflow_concurrent (rolling 20), api_calls (per_minute 1000), export_files (per_day 100). `shared/tenant_quotas.py`: check_and_consume atomic SELECT FOR UPDATE + UPSERT. 12 tests. |
| **Closeout 2026-05-19** | **5 of 5 items shipped, 0 defer.** Two commits (`011965b` + `5e750b2`). ai-orch suite 2279 → 2350 (+71 tests). 3 new migs (097/098/099). 5 new modules. |

### Phase 2.7 producer-side wiring (2026-05-20)

| Wiring | Status |
|---|---|
| **1/4** record_ai_call producer on llm-gateway | ✅ `7bb4c65`. NEW `services/llm-gateway/ai_governance.py` mirror. Wired to /v1/infer + /v1/embed + /v1/ocr. K-4 enforced at gov audit row: consent_external + pii_redacted set TRUE only for method='external'; embed/ocr ALWAYS False. 15 new tests, llm-gw 178 → 193. |
| **2/4** tenant_quotas pre-flight gate | ✅ `6f93cff`. NEW `services/llm-gateway/tenant_quotas.py` mirror. /v1/infer charges `llm_tokens_external` when method='external', `llm_tokens_local` otherwise. On QuotaExceeded → 429 RFC 7807 BEFORE providers.invoke fires. +17 tests llm-gw (193→210), +2 tests ai-orch (2350→2352). |
| **3/4** policy_engine.evaluate at approval_gate | ✅ `1796c16`. `executors/approval.py` builds policy_ctx and calls evaluate(). Three outcomes: deny / require_approval / allow. Closes the declarative-rule gap: TODAY config auto-approves <10M VND from finance dept regardless of business policy; AFTER wiring, the seeded finance_invoice_cfo_threshold rule (>100M → CFO required, 1440 min SLA) overrides config. +3 tests ai-orch (2352→2355). |
| **4/4** lineage edge emit at bronze→silver + output sinks | ✅ `31af408`. NEW `services/data-pipeline/shared/lineage.py` (write-side mirror). /clean endpoint emits ONE coarse edge per (bronze_file, run_id) → silver_row. Output executors (publish_insight/publish_alert/create_task) emit workflow_run_node → {insight,alert,task} edges. Backward walk now navigable end-to-end: workflow_insight → workflow_run_node → ... → silver_row → bronze_file. +4 tests data-pipeline (691→695). |
| **Wiring complete 2026-05-20** | **4 of 4 wiring commits shipped + pushed.** Phase 2.7 governance layer flips from "shape" → "production". All 4 K-rules — K-1 RLS / K-6 audit / K-13 idempotency / K-17 side-effect class — preserved. Test deltas: llm-gw 178 → 210 (+32), ai-orch 2350 → 2355 (+5), data-pipeline 691 → 695 (+4). Branch ahead `main` ~221 commits. |

---

## Phase 2.8 — Industry Template 3-tier Bootstrap (anh's UX redesign 2026-05-20 EOD)

Anh review 2026-05-20: "Workflow UI chưa rõ vật thể. SME không tạo workflow từ canvas trắng. Phải bắt đầu từ phòng ban. Card phải rõ. Có cấu hình chuẩn theo ngành (Retail / F&B / Logistics / Finance / Healthcare / Manufacturing / Education / Generic SME)."

| D-piece | Status |
|---|---|
| **D1** Mig 101 industry catalog tables | ✅. 6 bảng: `industry_templates` (8 industries — 3 seeded) + `industry_department_templates` + `industry_workflow_links` (M-N bridge industry × dept × workflow_template) + `industry_kpi_templates` + `industry_data_schema_templates` + `industry_role_permission_templates`. Tất cả platform-shared, no RLS. +1 view `v_industry_overview`. |
| **D2** Mig 102 customer config + versioning | ✅. 5 bảng RLS-scoped: `customer_workflow_versions` (immutable snapshot — K-2 trigger refuse UPDATE/DELETE) + `workflow_customizations` (edit log với edit_mode ∈ {simple, advanced, developer}) + `enterprise_industry_bootstrap` (UNIQUE per enterprise → K-13 idempotency) + `enterprise_workflow_mode` (3-mode + plan-gated unlock flags) + `workflow_change_requests`. +1 view `v_workflow_version_status`. |
| **D3** Mig 103 seed Retail/Finance/Generic SME | ✅. **Retail**: 6 dept × 15 wf link × 8 KPI × 6 schema × 5 role. **Finance**: 5 dept × 4 wf link × 7 KPI × 4 schema × 5 role. **Generic SME**: 4 dept × 5 wf link × 4 KPI × 3 schema × 4 role. 5 industry còn lại (F&B/Logistics/Healthcare/Manufacturing/Education) **defer Phase 3** — seed khi customer đầu tiên thuộc industry đó ký. |
| **D4** Router industry_bootstrap.py + 10 endpoint | ✅. `GET /industries` / `GET /industries/{id}` / `GET /industries/{id}/departments` / `GET /industries/{id}/workflows?recommendation_level=core\|suggested\|advanced` / `POST /enterprises/{id}/bootstrap-from-industry` / `GET /enterprises/{id}/bootstrap-status` / `GET /workflows/{id}/versions` / `POST /workflows/{id}/customize` / `GET /enterprises/{id}/workflow-mode` / `PATCH /enterprises/{id}/workflow-mode`. K-12 anti-IDOR. K-13 idempotency via UNIQUE(enterprise_id). |
| **D5** Tests + ADR-0026 | ✅. `tests/test_industry_bootstrap_router.py` 13 tests. ADR-0026 documents 3-tier decision + 3-mode plan-gate + customization → CR flow. |
| **D6** Update feature-workflows.html + CLAUDE.md | ✅. HTML viewer thêm section A.10 "Industry Template Bootstrap" với Mermaid flowchart. Glossary extended. Version bumped 3.8.1 → 3.9.0. |
| **D7** workflow-builder-ux.html mockup + feature-screens.html redesign | ✅ (anh's review 2026-05-20 EOD chấm feature-screens UX 6/10 + workflow catalog 5.5-6/10). NEW `docs/sprint/workflow-builder-ux.html`. 11-point UX redesign vào feature-screens.html. |
| **D8** Tiếp queue: P2-20/P2-27/P2-28 + Navigation IA + checkpoint | ✅ (anh review continue 2026-05-20 EOD2). P2-20 Insight Detail (3-tab + alternatives + lineage trace + T-Cube similar past), P2-27 Workflow Testing (Test Run + A/B Parallel-Run 90d), P2-28 Process Mining (Discovery SME + Analyst View). NEW IA section "Business vs Platform/Internal split". 9 màn priority Phase 2.8 done + 2 NEW. PROJECT_STATUS rev3 saved. |
| **D9** BA mirror docs/ba/ FRD bump + Excel | ⏳ defer next session. 2.2 FRD bump để document FR-IND-* + 3.1 SRS UC-TB-NEW cho Industry Wizard. |

**Phase 2.8 closeout 2026-05-20 EOD2** — 8/9 D-piece ship; D9 BA FRD bump defer next session. Branch ahead `main` ~227 commits. ai-orch +14 tests. Phase 2.8 = Industry tier + UX redesign — KHÔNG sửa workflow_templates / workflow_nodes / executors / runtime (additive). Mọi 25 mig 069 template tiếp tục LIVE.

### Phase 2.8 UX polish 2026-05-20 EOD3

Anh's review 8.3/10 → ship commit `8968d48` 16 fixes / 6 nhóm A-F / gộp 1 commit. Verified 8 điểm anh raise + tìm thêm 8 cải tiến em phát hiện sau khi đọc full 6124 dòng 3 file UX. Diff:
- `feature-screens.html` +92 (P1-04 industry list cleanup, P2-11 footer cross-ref đúng, P2-15 Re-run CTA, P2-20 Mark not actionable + Permanently dismiss, P2-32 confirm modal 2-lần wireframe, SH-04 rewrite 5-source unified DLQ, "30→32 screens" count fix)
- `feature-workflows.html` +12 (title + "Internal — NOT customer UX" disclaimer banner)
- `workflow-builder-ux.html` full rewrite (5-step lẫn Onboarding → 4-step builder-only post-bootstrap: Template Library → Template Detail [NEW] → Card Stack → Card Editor; + Advanced mode reference collapsible; + 2 button "Xem logic nhánh" / "Chuyển Advanced"; + K-rule enforcement block đầy đủ K-1/K-2/K-12/K-13/K-17/K-19)
- Branch ahead `main` 240 commits
- **+ NEW**: `docs/sprint/PHASE_2_8_FE_IMPL_SPEC.md` — FE Implementation Spec 11 màn priority + 2 NEW (route + component tree + state + API + permission + empty/loading/error states)

### Phase 2.8 Round 5 closeout 2026-05-21 EOD

REVIEW_NOTES_for_Code_Repo.md (sync Round 5 BA mirror) raise 7 nhóm action items cho dev-facing artefacts. Em tuần tự ship 4 commits trong 1 session:

- **N2 ship `4d67acc`** — OpenAPI regen + API_CATALOG_V4 expand (+155 lines):
  - `scripts/dump_openapi.py` regen: orchestrator 46→**163 paths** (P15-S10 snapshot stale); pipeline 24 paths unchanged
  - API_CATALOG_V4 header: 169 baseline + ~30 Phase 2.5/2.6/2.7/2.8 NEW = ~187 actual
  - Process Mining section: 10 connectors table (Postgres CDC/Excel/Zalo/Gmail/Outlook/Calendar/Slack/Teams/SharePoint/webhook) — closes CR-0008
  - + SLA per-endpoint section (NFR-P-01..12 class-level matrix)
  - + Rate Limit section (5 tenant_quota types mig 099 + 429 Retry-After NFR-SEC-09)
  - + Error Codes section (11 HTTP class mapping với USR-ERR-*/SYS-ERR-* + recovery)
  - + API Versioning Policy (deprecation 6-month window with Deprecation+Sunset headers)
  - + Outbound Webhooks Contract (HMAC-SHA256 + retry 5 exponential + 8 event types)
  - FE TypeScript types regen: orchestrator.d.ts 12332→14409 (+2077); pipeline.d.ts unchanged

- **N3 ship `b820a81`** — Medallion Contract sync với SRS §2 (+65 lines):
  - 8-step Silver pipeline canonical: schema_validation → type_cast → null_handling → dedup → PII_masking_VN → normalize → outlier_flag → lineage_tag
  - 7-Dimension Quality Scorecard (mig 065 + `silver/quality.py`): Completeness 0.20 / Validity 0.20 / Uniqueness 0.15 / Consistency 0.15 / Timeliness 0.10 / Accuracy 0.10 / Conformity 0.10
  - Gate ≥80% weighted avg trước promote Gold
  - Silver schema fields canonical: 12 mandatory columns (lineage_bronze_id FK + silver_pipeline_version + transformations_applied JSONB + pii_masked_fields JSONB + outlier_flag + quality_dimensions JSONB + partition_key generated + RLS K-1)

- **N4 ship `fc43181`** — 19 UAT scripts (+1606 lines):
  - Priority 1 Phase 2.5: F-CLASSIFY/EXTRACT/SUMMARISE/SENTIMENT/DEDUP/COMPARE/MINERU/WORKFLOW-EXEC-CLOSEOUT (8 files)
  - Priority 2 Phase 2.6: F-WORKFLOW-EVENTS/IDEMPOTENCY-LEDGER/DLQ-CONSOLE/ONTOLOGY-GOV (4 files)
  - Priority 3 Phase 2.7: F-LINEAGE-WALK/AI-DECISION-AUDIT/POLICY-ENGINE/QUOTA-429 (4 files)
  - Priority 4: CROSS_PORTAL_FLOW + K_RULE_INVARIANTS + PERFORMANCE_NFR (3 files)
  - Each: What landed + Test scenarios G/W/T + 4-case negative per NFRS §13.3 + K-rule invariants + Performance + Execution checklist

- **N5+N6+N7+N8 ship `8e67d9a`** — Specs catalogs extend + Governance scripts (+872 lines):
  - **N5 VALIDATION_RULES.md** §7 Extended (+123 lines): VN Phone · VND Amount · Percentage · UUID v4 · Date/Timestamp · Password · VN Tax Code/CCCD · File upload · Currency Format · Cross-field dependency · Industry vertical
  - **N6 MESSAGE_DEFINITIONS.md** §3 BIZ-ERR catalog filled (15 codes) + §4 Warning/Success/Info/Confirmation/Helper catalogs filled (8+8+6+7+8 codes)
  - **N7 CHAT_TOOL_REGISTRY_V4.md** §7 MCP JSON-RPC 2.0 mapping: per-tool 8 metadata fields + 10 NEW tools EPIC-12 PM (3) + EPIC-13 Adoption (3) + EPIC-14 NOV (4) + standalone MCP server Phase 2 packaging + 5 forbidden patterns CRITICAL + MCP test plan
  - **N8 Governance scripts** (NEW 3 scripts + 1 reference doc): `check_cr_compliance.py` · `check_ba_sync.py` · `openapi_precommit_hook.sh` · `GOVERNANCE_TIGHTENING.md`

**Verification post-Round 5** (per `scripts/check_ba_sync.py` self-test):
- Migrations: 100 .sql files
- Pipeline OpenAPI: 24 paths · Orchestrator: 163 paths
- BA Sync: 0 DIFFER, 0 MISSING ✓
- CR Reference rate: 0/219 feat commits (workshop commits — expected, post-facto register CR-0009..0012 caught up via Round 4 CR Register v2.1)
- Branch ahead `main`: 250 commits, sync với origin/feat/p15-s9-d1
- Working tree clean

**4-layer alignment maintained**: code repo ↔ UX spec (3 HTML Round 3) ↔ FE Impl Spec v1.1 (Round 4) ↔ BA layer (URD v2.1 + NFRS v1.1 + CR Register v2.1 + BRD/Vision/BusinessCase/PRD/RACI Round 5) ↔ engineering action list (REVIEW_NOTES 7 nhóm + Round 5 N2-N8 ship).

### Phase 2.8 UX polish Round 3 2026-05-21

Anh's review round 3 raise 2 CRITICAL: (1) Title "72 màn · 6 portals" vs IA convention inconsistency (BIL/SH ≠ P5/P6 prefix); (2) Customer Service vertical gap (0 CS-vertical screens render workflows D.1-D.5). Em fix triệt để Option 1 per anh's BA docs alignment (BRD v4.1 + PRD v6.1 + Product Vision + Business Case + RACI v1.1 đều treat Shared+Billing là portal 5+6).

- **R6 rename**: SH-01..06 → P5-01..06 (P5 Shared Infrastructure cross-cutting admin-only) · BIL-01..04 → P6-01..04 (P6 Billing cross-cutting financial ops). CSS classes (s-bil→s-p6, s-sh→s-p5, portal-bil→portal-p6, portal-sh→portal-p5) + CSS vars (--bil/--bil-bg → --p6/--p6-bg, --sh/--sh-bg → --p5/--p5-bg) + sidebar order (P5 trước P6) + sub-labels rõ "cross-cutting · admin-only/financial ops".
- **R7 add 5 CS screens**: P2-33 CS Ticket Inbox (D.1 runtime) · P2-34 Ticket Detail+SLA Timer (D.2 runtime) · P2-35 NPS Dashboard (D.3 runtime) · P2-36 Refund Approval Queue (D.4 runtime + saga compensation) · P2-37 Churn Save Workspace (D.5 runtime + Stage 12 A/B offer test). Each screen: purpose + functions + wireframe + 5-6 states + BE endpoints + cross-link tới workflow catalog internal ref.
- **R8 medium**: glossary entry "Workflow Card" expanded 2-layer field model + render mapping + sample date "2026-06-01" tagged.

Count totals: 16 P1 + **37 P2** (+5 CS) + 8 P3 + 6 P4 + **6 P5** + **4 P6** = **77 screens × 6 portals (P1-P6)**. PHASE_2_8_FE_IMPL_SPEC.md SH-* refs migrated to P5-*. CLAUDE.md historical SH-04 mention giữ nguyên (commit message accurate).

### Phase 2.8 BA alignment Round 4 2026-05-21

Anh review FE Impl Spec v1.0 raise 13 issues (2 CRITICAL + 3 HIGH + 5 MED + 3 LOW). Anh tự sửa hết trong `D:\Tài liệu dự án\` + bổ sung 2 BA docs companion. Em sync 4 file từ `Tài liệu dự án` vào repo `docs/`:

- **`docs/sprint/PHASE_2_8_FE_IMPL_SPEC.md` v1.0 → v1.1** (712→952 lines): cập nhật 72→77 màn + P5/P6 naming; thêm spec 5 CS screens P2-33..P2-37 đầy đủ; §Permission Claims link NFRS §5.bis; §Accessibility WCAG 2.1 AA (NFR-U-08); §Mobile Responsiveness (NFR-U-07); §Observability OpenTelemetry (NFR-O-01); STU-01 alias STUDIO_ANALYST; Phase 2.8 = sprint code clarify; URD US-ID per screen; test pyramid full (Unit Vitest + Integration Testing Library + E2E Playwright + a11y axe-core + visual regression + Lighthouse perf); P2-11 "legacy" → "standalone Phase 1 flow"; Open Qs 5 → 3 (chốt shadcn/ui + Zustand + polling); phasing 8→11 weeks (Phase A/B/C/D); +Changelog table.

- **`docs/ba/2.1_URD_User_Requirements_Document.md` v1.0 → v2.1** (146→415 lines): mọi US giờ có AC dạng **Given/When/Then** với 4 negative scenario (Happy/Validation/Permission/Dependency) bắt buộc; bổ sung persona priority MVP (P0/P1/P2); **NEW UR-CS section với US-CS-1..US-CS-5** match 5 CS workflow D.1-D.5 và 5 screen P2-33..P2-37; reference claim concept; cập nhật traceability table với CS row.

- **`docs/ba/3.2_NFRS_Non_Functional_Requirements.md` v1.0 → v1.1** (277→394 lines): **NEW §5.bis Permission Claims** formalize concept đã code-side + FE spec-side dùng nhưng chưa BA documented. 10 claim chính thức catalog với auto-grant logic. **6 NFR-SEC mới** (NFR-SEC-15..20). 3 phase migration path.

- **`docs/ba/4.2_Change_Request_Register.md` v1.1 → v2.1** (364→432 lines): **NEW CR-0011 CS Vertical FE** (HIGH, APPROVED 2026-05-21) — 5 screen P2-33..P2-37 + 3 claim mới + 5 US-CS-1..5 + 150 SP ~3 sprint. **NEW CR-0012 Permission Claims framework** (HIGH, APPROVED 2026-05-21 partial — NFRS §5.bis done) — 31 SP còn lại Phase 2.9. Plus **Governance finding lần 2:** lesson learned "bất kỳ concept mới trong code/FE phải reflect ngược lên BA layer cùng sprint, không defer".

**Phase 2.8 = anh's "rõ vật thể" redesign — BE foundation + UX spec.** FE Workflow Library page (per-industry empty state + "Tạo workflow đầu tiên cho phòng Sales") đợi FE restructure resume per CLAUDE.md §2.

### 2-file UX vs internal split (anh's review 2026-05-20 EOD)

- `docs/sprint/feature-workflows.html` — **INTERNAL CATALOG** cho dev / AI agent audit. 40 workflows full với Mermaid + K-rule + executor coverage + mig refs. Đừng show cho khách.
- `docs/sprint/workflow-builder-ux.html` — **SME UX MOCKUP** cho FE team. Interactive 5-step wizard demonstrate card format chuẩn anh chốt (Owner/Input/Required docs/AI action/Branch/Output/SLA). KHÔNG render Mermaid; render card stack vertical.
- `docs/sprint/feature-screens.html` — **SCREEN INVENTORY** (77 màn). Mỗi màn priority có functions + layout wireframe + states (empty/loading/error/permission/CTA).

**Phase 2.8 close: 9 màn priority redesigned + 2 màn NEW + IA section**:
- P2-02 Onboarding (Industry-first 7-step)
- P2-03 Dashboard (Today Queue action-first)
- P2-04 Organization (3-view: Department Cards/Org Tree/Cross-WF)
- P2-11 Upload (2-mode: Quick Inbox/Workflow Step + standalone Phase 1 flow)
- P2-15 Results (workflow context header + what-changed diff + lineage walk)
- P2-20 Insight Detail (3-tab Descriptive/Diagnostic/Prescriptive + alternatives + lineage trace + T-Cube similar past)
- P2-26 Workflow Builder (3-mode: Simple/Advanced/Developer + Branch Inspector)
- P2-27 Workflow Testing (2-mode: Test Run + A/B Parallel-Run 90d)
- P2-28 Process Mining (2-mode: Discovery Insights SME / Analyst View)
- NEW P2-31 Industry Template Library
- NEW P2-32 Bootstrap Preview
- **NEW Navigation IA section** — Business IA (Workspace / Workflows / Data / Insights / Reports / OKR / Admin) vs Platform-Internal IA (Audit / Observability / DLQ / MCP / Guardrails / P1) gated qua JWT permission claim; KHÔNG render menu mục với permission denied (anti-pattern fixed).
- 8 state đầy đủ mỗi màn priority (empty/loading/error/permission/CTAs/drilldown).

---

*Snapshot 1 dòng/sprint trong `CLAUDE.md` §14. Phase 2/3 backlog trong `docs/BACKLOG_V4.md`.*
