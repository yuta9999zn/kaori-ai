# Pilot DB — actual schema state vs canonical migrations

> **Status as of 2026-06-01 (DB-introspection verified, not flyway-trusted).** The
> pilot DB (local UAT on anh's 16GB laptop) is a **partial subset** of the canonical
> migration set (canonical = **mig 129**, 126 .sql files). `flyway_schema_history`
> reports only **v105**, but direct introspection shows the **workflow / builder /
> BPMN / doc-tree / approval / contract surface (089, 112–124) was applied
> out-of-band** — so those features genuinely work. What's still missing is the
> **reasoning layer (106 KB / 108 AI-config / 110 memory-trust)** and a couple of
> **node-catalog seeds (125/128)**. ⚠️ Because flyway under-reports, NEVER trust
> `flyway_schema_history` for pilot state — introspect the actual table/column
> (`to_regclass`, `information_schema.columns`) as the queries below do.
>
> **Cutover impact:** see [`dev-to-prod-data-cutover.md`](dev-to-prod-data-cutover.md) **Step 4b** —
> `flyway_schema_history` claims these migs `success=true` but their DDL was
> never executed, so a dump→restore propagates the gap to prod silently unless
> the operator re-applies the real DDL.

## What the pilot actually runs

| Range | Source | State |
|---|---|---|
| migs 001–084 | Phase 1 + 1.5 + early Phase 2 core | ✅ real DDL applied |
| migs 085–100 | Phase 2.5 / 2.6 / 2.7 feature schema | ⚠️ **mostly stubbed**, EXCEPT 088 (workflow_runs) + **094 / 099 / 100 applied 2026-05-31** to enable real workflow runs (events + quota). Rest still stubbed. |
| migs 101–104 | Industry Templates + UUIDv7/ULID | ✅ DDL applied **2026-05-24** (was stubbed; filled to enable FE P2-31/32) |
| mig 105 | admin-bypass RLS drift fix | ✅ real DDL applied |
| migs 106–124 (workflow/builder/doc/approval/contract surface) | NNL-Harness + n8n + Tier-3 (ADR-0037) | 🟢 **MOSTLY APPLIED out-of-band** — **verified 2026-06-01** by direct DB introspection (NOT via flyway_schema_history, which still reports v105). PRESENT: 089 `workflow_approvals`, 112 `ui_schema_json`, 113 `type_version`, 114 `port_type`, 115 `bpmn_xml`, 116 BPMN lane metadata, 117 `node_type_catalog_key`, 119 `workflow_step_document_requirements` + `workflow_step_folders`, 120 doc-instance lifecycle, 121 `approval_chains`, 122 chain wiring, 123 `user_department_roles`, 124 `contracts`. This is why the builder / BPMN / Cây tài liệu / approval / contract features all work in pilot. |
| migs 106 / 108 / 110 (KB + AI-config + memory-trust) | NNL-Harness reasoning layer | 🔴 **ABSENT (verified 2026-06-01)** — `knowledge_documents` (106), `platform_ai_config` (108), `memory_l3` trust columns (110) do NOT exist. Consequence: KPI/Qwen "chưa có lần compute", analyze-narrative grounding degraded, AI-config knobs fall back to defaults. Compounded by the `bge-m3` embedding model not being pulled into Ollama. |
| migs 125 / 128 node-catalog seeds | loop + contract builder nodes | 🔴 **NOT SEEDED (verified 2026-06-01)** — `node_type_catalog` has 0 loop/contract rows, so those node types are missing from the builder palette. |
| migs 126 / 127 / 129 | ABAC dept-restrictive + approval-gate binding + node_type constraint | ⚪ unverified — audit if relying on dept-scoped RLS or loop/contract node types. |

## Stubbed migrations (085–100) — what's MISSING in pilot

| Mig | Feature | Consequence in pilot |
|---|---|---|
| 085 | node_catalog_classify_extract | classify/extract workflow nodes — catalog rows absent |
| 086 | node_catalog_summarise_sentiment_dedup | summarise/sentiment/dedup nodes absent |
| 087 | node_catalog_compare_to_template | compare-to-template node absent |
| **088** | **workflow_runs** | ✅ **present** (applied in an earlier session) — workflow runs persist; real runs verified 2026-05-31 |
| 089 | workflow_approvals_and_forms | approval/form steps unavailable |
| 090 | adoption_snapshots | adoption / NOV tracking unavailable |
| 091 | workflow_output_tables | workflow node outputs can't persist |
| 092 | workflow_chat_and_webhook | chat/webhook workflow triggers unavailable |
| 093 | workflow_wave5_tables | wave-5 workflow features unavailable |
| **094** | **workflow_events** | ✅ **applied 2026-05-31** — event backbone + `workflow_events_next_seq()` present; run events persist (run-trace works) |
| **095** | **workflow_idempotency_records** | ⛔ per-node K-13 idempotency (workflow) absent |
| 096 | ontology_governance | 7-Primitives ontology governance absent |
| 097 | data_lineage | lineage tracking absent |
| 098 | ai_governance_audit | `ai_decision_audit` / governance audit rows can't persist |
| 099 | policy_engine_and_quotas | ✅ **applied 2026-05-31** — `tenant_quotas` + `tenant_quota_usage` + `policy_rules` + default quota seed for all enterprises |
| 100 | quota_fail_open_knob | ✅ **applied 2026-05-31** — `tenant_quotas.fail_open` column present |

## What works / does NOT work in pilot

**✅ Works:** auth + SSO, file upload → Bronze → Silver → Gold pipeline, schema detection, cleaning, quality scorecard, analysis frameworks, AI decisions + audit log (decision_audit_log, pre-2.7), reports, **Industry Template Library (P2-31/32)**, corporate hierarchy, RLS multi-tenancy.

**✅ Now works (2026-05-31):** **workflow execution / runs** — real `POST /workflows/{id}/run` completes, events persist (`workflow_events`), per-node rows recorded, quota enforced (`tenant_quotas`, fail-open). Loop/for-each runner verified (body runs N× per item). The builder constructs (if/else, switch ranges, dry-run, loop, BPMN swimlanes) are all live.

**⛔ Does NOT work** (DB tables absent — FE screens will error if exercised against real backend): adoption + NOV dashboards (Stage 11), AI governance audit console (mig 098), ontology graph + lineage (096/097), per-node workflow idempotency (mig 095), the extended workflow node catalog (085-087, 093).

## Making a stubbed feature testable in pilot

The migration files are idempotent-friendly (`CREATE TABLE IF NOT EXISTS`, `ON CONFLICT DO NOTHING`, `CREATE OR REPLACE FUNCTION`). To enable e.g. workflow execution:

```bash
# Apply in dependency order; some migs ALTER tables from earlier stubbed migs.
for n in 085 086 087 088 089 090 091 092 093 094 095; do
  f=$(ls infrastructure/postgres/migrations/${n}_*.sql | head -1)
  docker compose exec -T postgres psql -U kaori -d kaori -v ON_ERROR_STOP=1 -f - < "$f"
done
# Governance/quota layer (096-100) likewise, in order, if testing P5 / quota.
```

After applying, mark the rows honest so the cutover detection (Step 4b) stops
flagging them:

```sql
UPDATE flyway_schema_history
   SET description = description || ' [DDL applied to pilot <date>]'
 WHERE version IN ('088','089', ...);   -- whichever you applied
```

> **Decision (2026-05-24, anh + Kaori):** keep pilot lean — apply only what a
> given UAT pass needs (industry templates done). Do NOT bulk-apply 085–100;
> the omitted features (workflow exec, governance, adoption, quota) aren't
> exercised in the current core-flow UAT and the full Phase-2 schema isn't
> worth the weight/risk on the laptop env. Revisit per the feature being tested.

## Phase 6 / NNL landing (migs 106–117) — apply plan

Shipped to canonical 2026-05-27/29 but not yet applied to pilot. All twelve
migrations target tables that **already exist in pilot** (memory_l3 from
mig 067; node_type_catalog from mig 068; workflows/workflow_nodes/edges from
mig 053); none ALTER or depend on the stubbed 085–100 range, so applying them
is **independent** of any decision about the gap.

| Mig | Touches | Why apply on pilot |
|---|---|---|
| 106 | new `knowledge_documents` (FOUNDATIONAL KB) | ADR-0033 grounding gate; analyze narrative needs it |
| 107 | seed retail-SME knowledge into 106 | "học 1 hiểu 10" content (RFM / Pareto / NOV / đơn-giá vi) |
| 108 | new `platform_ai_config` (CR-0019) | tune AI knobs without redeploy |
| 109 | flip `applied=true` for wired knobs | runtime read paths landed |
| 110 | ADD 3 cols on `memory_l3` (ADR-0030) | trust/decay/verify for memory recall |
| 111 | ADD 7 cols on `knowledge_documents` (ADR-0033) | aging + version chain + supersede |
| 112 | ADD `ui_schema_json` on `node_type_catalog` | declarative builder forms (FE unblock) |
| 113 | ADD `type_version` on node_type + workflow_nodes (K-20) | no silent node-type upgrade |
| 114 | typed ports on `workflow_edges` + `is_trigger` on catalog (ADR-0035) | agent-tool/memory/model wiring + trigger nodes |
| 115 | ADD `bpmn_xml TEXT` on `workflows` | builder pivot → bpmn-js canvas persists |
| 116 | ADD BPMN metadata on `workflow_nodes` (pool/lane/bpmn_type/event_def/attached_to) + `workflow_edges` (flow_kind/is_default) | BPMN ↔ nodes sync; swimlanes |
| 117 | RENAME `workflow_nodes.kaori_node_type → node_type_catalog_key` + executor key align (refs node_type_catalog, mig 068) | fix latent runner schema mismatch |

**Apply command (in dependency order):**
```bash
for n in 106 107 108 109 110 111 112 113 114 115 116 117; do
  f=$(ls infrastructure/postgres/migrations/${n}_*.sql | head -1)
  docker compose exec -T postgres psql -U kaori -d kaori -v ON_ERROR_STOP=1 -f - < "$f"
done
```

Migrations are `CREATE TABLE IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` style
(117 is a `RENAME COLUMN` — guarded, run once); re-running is idempotent. Apply
unlocks: pilot RAG against curated knowledge, memory trust scoring, workflow
Phase 6 builder schema (typed ports + triggers + BPMN swimlanes).

## Tier-3 docs/contracts/approvals epic (migs 118–129) — apply plan

Shipped to canonical 2026-05-31/06-01 (ADR-0037) but not yet applied to pilot.
Mostly additive, K-21-compliant (`gen_uuid_v7()` PK / `gen_ulid()` external).
**One real dependency on the stubbed range:** mig **122** ALTERs
`workflow_approvals`, which is created by the **stubbed mig 089**
(`workflow_approvals_and_forms`). Apply 089 first (or skip 122 + the
approval-chain wiring) — every other mig here touches tables present in pilot
(`workflows`/`workflow_nodes`/`bronze_files` from mig 053; `node_type_catalog`
from mig 068; `knowledge_documents` from mig 106).

| Mig | Touches | Why apply on pilot | Dep |
|---|---|---|---|
| 118 | knobs on `platform_ai_config` (KB-promote) | tune KB→memory promotion without redeploy | 108 |
| 119 | new `workflow_step_document_requirements` | per-step required-doc binding (refs workflows/workflow_nodes/bronze_files) | 053 |
| 120 | ALTER `workflow_step_documents` (lifecycle/supersede) | doc instance versioning | **053** (table present) |
| 121 | new `approval_chains` + `approval_levels` | multi-level approval + SLA + escalation | — |
| 122 | ALTER `workflow_approvals` + new `approval_delegations` | wire approval_gate node → chain; delegations | ⚠️ **089 (stubbed)** |
| 123 | new `user_department_roles` + `chk_node_assigned_role` on workflow_nodes | dept-scoped approver assignment | 053 |
| 124 | new `contracts` + `contract_parties` + `contract_signatures` | contract lifecycle + e-sign (refs bronze_files) | 053 |
| 125 | seed `node_type_catalog` contract nodes | contract steps in builder catalog | 068 |
| 126 | ABAC dept-restrictive RLS policies | dept-scoped row access (uses user_department_roles) | 123 |
| 127 | bind approval_gate node ↔ approval chain | builder wiring for approval steps | 121 |
| 128 | seed `node_type_catalog` loop node | for-each/loop construct in catalog | 068 |
| 129 | refresh `chk_node_type` constraint on workflow_nodes | allow loop + contract node types | 053 |

**Apply command (089 first, then in order):**
```bash
# Prereq for 122: apply the stubbed approvals/forms migration first.
docker compose exec -T postgres psql -U kaori -d kaori -v ON_ERROR_STOP=1 \
  -f - < infrastructure/postgres/migrations/089_workflow_approvals_and_forms.sql

for n in 118 119 120 121 122 123 124 125 126 127 128 129; do
  f=$(ls infrastructure/postgres/migrations/${n}_*.sql | head -1)
  docker compose exec -T postgres psql -U kaori -d kaori -v ON_ERROR_STOP=1 -f - < "$f"
done
```

Apply unlocks: pilot Document Tree + per-step required docs, approval chains
with SLA/escalation, contracts + e-sign, and the contract/loop builder nodes.
The BE for this epic is LIVE on canonical; executor-wiring + FE are the
remaining debt (see memory `project_tier3_documents_contracts_approvals`).
