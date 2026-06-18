# P2-S15 Resume Checklist — All 45 nodes + 25 templates + Visual builder

> **Created:** 2026-05-17 end-of-session
> **Branch state at freeze:** `feat/p15-s9-d1` HEAD `c83fb84`, **110 commits ahead** of `main`
> **PR #179:** open, CI red (June reset), all local tests green
> **Sprint backlog ID:** P2-S15 per docs/BACKLOG_V4.md line 833
> **Strategic spec:** docs/strategic/WORKFLOW_SYSTEM.md §2.2-2.7 (45 node types in 6 categories)
> **Single backlog item:** SH-M56b-026 Visual agent workflow builder (cross-cutting)

## What's already in the codebase

- **Workflow builder BE + FE** ship Tuần 8 (`b757082` + `ef42989`):
  - Mig 053: workflows / workflow_nodes / workflow_edges / workflow_step_documents / workflow_templates
  - Mig 054: 18 templates auto-generated
  - Mig 058: decision_nodes + folder attachments + stats
  - Mig 060: 6 enterprise node types ship (`Path B` per memory) — `step / decision_if_else / decision_switch / approval_gate / wait / external` plus 6 enterprise relabels
  - 13 CRUD endpoints in `services/ai-orchestrator/routers/workflow_builder.py`
  - FE: `/p2/workflows` hub + builder + tree viewer + cross-link badges

- **Workflow YAML schema validator**: `services/ai-orchestrator/workflow_runtime/yaml_schema.py`
- **K-17 side_effect_class taxonomy enforced**: every node type declares one of `pure / read_only / write_idempotent / write_non_idempotent / external` (this is the basis for the retry policy mapping)

## What P2-S15 needs to ship

Per WORKFLOW_SYSTEM.md §2.2-2.7 the **45 node types** in 6 categories:

| Cat | Count | What |
|---|---|---|
| 1. Data Input | 8 | manual_form / csv_upload / api_pull / db_query / file_watch / webhook_receive / scheduled_pull / streaming_subscribe |
| 2. Processing | 10 | transform / aggregate / filter / dedupe / enrich_lookup / split / merge / validate_schema / mask_pii / normalize_units |
| 3. Decision | 5 | if_else / switch / approval_gate / threshold_compare / ml_classify |
| 4. AI | 8 | summarize / extract / classify / predict / generate / embed / rag_retrieve / reasoning_call |
| 5. Action | 8 | send_email / send_zalo / send_slack / create_ticket / db_write / api_post / file_publish / webhook_emit |
| 6. Output | 6 | dashboard_tile / pdf_report / api_response / file_export / notification_card / scheduled_digest |

Plus **25 production-ready templates** (workflow templates seeded by mig — analogous to mig 054 but for general SME use cases):
- 5 marketing templates (campaign launch / churn intervention / VIP onboarding / lead nurture / email A/B test)
- 5 sales (lead qualification / proposal approval / contract renewal / discount approval / pipeline review)
- 5 customer service (ticket triage / SLA escalation / NPS follow-up / refund approval / churn save)
- 5 ops (inventory restock / supplier audit / quality check / shipment dispatch / warranty claim)
- 5 finance (invoice approval / expense reimburse / monthly close / vendor payment / budget approval)

Plus **SH-M56b-026 Visual builder** under `/shared/agents/studio/builder` — extends existing `/p2/workflows` builder with agent-specific node palette (the Sprint 8 chat-agent runtime grew this need).

## Work plan suggestion (anh chốt khi resume)

1. **Mig 068 — node_type_catalog table + 45-row seed** (~½ day)
   - Catalog table with `(node_type, category, side_effect_class, default_retry_policy, schema_json, description_vi)`
   - Pydantic shape per node type validated in workflow_builder router
   - Shape test guards 45 rows + 6 categories + every K-17 class represented

2. **Mig 069 — 25 production templates seed** (~1 day)
   - Each template = workflows row + node rows + edge rows
   - Vietnamese names + descriptions
   - Tag with `industry_vertical` from INDUSTRY_BENCHMARKS so Cohort comparison can filter

3. **Workflow router extension** (~½ day)
   - `GET /workflows/node-types` — list catalog
   - `GET /workflows/templates?industry=...` — list templates with filter
   - `POST /workflows/from-template/{template_id}` — instantiate

4. **SH-M56b-026 visual builder endpoint scaffold** (~1 day)
   - `GET /shared/agents/studio/builder/palette` — agent-specific node palette
   - Backend reuses workflow_builder; FE wires the agent-specific palette
   - FE work likely defers per `frontend/` paused state per CLAUDE.md §2

5. **Tests per anh's "chuẩn chỉ + hiệu năng + phi chức năng"** (~1 day)
   - Functional: each node type instantiable, validation per schema, edge rules
   - Performance: load all 45 catalog rows < 50ms; instantiate template with 20 nodes < 200ms
   - Non-functional: tenant isolation on template instantiation; deterministic node ordering; K-17 invariant locked
   - Integration: end-to-end template → workflow → first-step ready-to-execute

**Estimated total: ~4-5 dev-days.**

## Pre-flight before first push (memory `feedback_endpoint_addition_drift_checks`)

```powershell
cd "D:\Kaori System"

# 1. Verify branch is on c83fb84
git log --oneline -1
git status

# 2. Apply mig 068 + 069 to local pg + regen snapshot
docker compose up postgres -d   # if not already
docker run -d --name kaori-drift-pg --rm -p 55432:5432 \
    -e POSTGRES_USER=kaori \
    -e POSTGRES_PASSWORD=your_secure_password_here \
    -e POSTGRES_DB=kaori \
    pgvector/pgvector:pg15
# Wait for ready, apply ALL migrations:
for /F %f in ('dir /b infrastructure\postgres\migrations\*.sql') do (
    psql -h localhost -p 55432 -U kaori -d kaori -f infrastructure\postgres\migrations\%f
)
$env:DATABASE_URL="postgresql://kaori:your_secure_password_here@localhost:55432/kaori"
python scripts\schema-drift.py --write

# 3. Regen OpenAPI + FE types (per memory drift checklist)
python scripts\dump_openapi.py orchestrator
python scripts\dump_openapi.py pipeline
cd frontend
node scripts\gen-api-types.mjs

# 4. Run shape tests + pytest sweep
cd "D:\Kaori System"
python -m pytest scripts\test_migration_068_shape.py
python -m pytest scripts\test_migration_069_shape.py
cd services\ai-orchestrator
python -m pytest
```

## Expected baseline counts at session start

| Service | Tests | Last verified |
|---|---|---|
| ai-orchestrator | **1261 pass / 1 skip** | session 2026-05-17 EOD |
| data-pipeline   | **~510 pass / 1 skip** (490 + 24 P2-S13) | session 2026-05-17 EOD |
| llm-gateway     | **102 pass** | session 2026-05-17 EOD |

13 pre-existing `test_workflow_builder_router` fails (workspace_id fixture drift from 2026-05-15 commits) — leave alone unless P2-S15 work happens to touch the fixture; root cause is in those commits, not this sprint's responsibility.

## Pending CI work (parallel, can wait for June reset)

- PR #179 CI red status; 110 commits accumulated for the post-reset batch run
- Schema snapshot needs regen after mig 068 + 069 (use the ephemeral-pg recipe above)
- 4 drift artefacts to refresh on each endpoint addition (OpenAPI + FE types + RouteConfigTest + schema_snapshot)

## File pointers (where to start reading)

- `docs/strategic/WORKFLOW_SYSTEM.md` §2.2-2.7 — full 45-node spec with side_effect_class + retry budgets
- `services/ai-orchestrator/routers/workflow_builder.py` — existing CRUD (line 13 endpoints already shipped)
- `infrastructure/postgres/migrations/053_workflow_builder_tables.sql` — base schema
- `infrastructure/postgres/migrations/060_enterprise_node_taxonomy.sql` — existing Path B 6-type taxonomy (extend, don't replace)
- `services/ai-orchestrator/workflow_runtime/yaml_schema.py` — K-17 enforcement
- `services/ai-orchestrator/tests/test_p2_s14_pm_algorithms.py` — reference template for "chuẩn chỉ + hiệu năng + phi chức năng" test coverage
