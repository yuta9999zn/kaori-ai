---
marp: true
theme: default
paginate: true
header: 'Kaori AI · Build Week 2026 · Yuta Kun'
footer: 'Enterprise Workflow OS for Vietnamese conglomerates'
size: 16:9
---

<!-- Marp slide source. Export to PDF / PPTX:
       npx @marp-team/marp-cli BUILD_WEEK_SLIDES.md -o BUILD_WEEK_SLIDES.pdf
     Or open in VS Code with Marp extension for live preview. -->

# Kaori AI

**Enterprise Workflow OS** for Vietnamese conglomerates

Yuta Kun · Solo builder · GenAI Build Week 2026

Track: **Enterprise AI → Enterprise Workflows**

---

## The Problem

Every Vietnamese conglomerate asks the same question:

> "Vingroup có **8 mảng × 16 công ty con × 6 phòng ban** = 96 đội.
> Mỗi đội có 5-20 workflow. **Quản lý xuyên tổ chức kiểu gì?**"

Today's tools fail because:

- **ERP** (SAP/Oracle) — biết về sổ kế toán, không biết workflow phòng ban
- **BPM** (Camunda/Bonita) — biết về workflow, không biết org hierarchy
- **Data platform** (Snowflake/Databricks) — biết về data, không biết process
- **Hackathon AI tools** — biết về LLM chat, không production-ready cho enterprise

**→ Kaori = OS unify 4 mảng trên cho corporate group**

---

## Approach

**1 platform. 4 capabilities. Vietnamese-first.**

```
┌─────────────────────────────────────────────────┐
│ L6  Workflow Studio  ·  Document Vault           │
│     Org-tree Builder ·  Reports                  │
├─────────────────────────────────────────────────┤
│ L5  Workflow CRUD · Org CRUD · IAM · Policy     │
├─────────────────────────────────────────────────┤
│ L4  CDFL Reasoning · KPI Engine · RAG Router    │
├─────────────────────────────────────────────────┤
│ L3  Temporal (Phase 2) · Kafka · Redis          │
├─────────────────────────────────────────────────┤
│ L2  Medallion (Bronze/Silver/Gold) · pgvector   │
├─────────────────────────────────────────────────┤
│ L1  Postgres + RLS + Vault + OTel               │
└─────────────────────────────────────────────────┘
```

---

## Medallion 3-layer (strict separation)

**Bronze** — raw immutable, JSONB landing, SHA-256 dedupe

**Silver** — cleaned, typed, **6 per-domain tables** (customers / orders / tickets / inventory / employees / finance_periods)

**Gold** — aggregated **views over Silver** — never touches Bronze (41 shape tests enforce)

```sql
-- Gold view CANNOT reference bronze_rows OR JSONB ops
CREATE VIEW gold.customer_360_marketing AS
SELECT sc.enterprise_id, sc.customer_id, gf.revenue_at_risk
FROM silver_customers sc
LEFT JOIN gold_features gf USING (enterprise_id, customer_external_id);
```

> Lineage captured per pipeline run → audit-able from KPI Gold → Bronze file

---

## Workflow Card Model

Each step in a workflow = **card** with:

- **Title VI + EN** — name in Vietnamese + internal English
- **Note** — free-form description / SOP
- **Hashtags[]** — GIN-indexed for cross-org filtering (`#q1_campaign`)
- **Required document types[]** — `[{kind:"csv", name:"Lead list", required:true}]`
- **Decision config** — for `if_else` / `switch` / `approval_gate` types
- **Folder tree** — Windows-style nested folders per card
- **Expected mapping template** — auto-fill schema mapping on upload

Plus: **node types** = `step` | `decision_if_else` | `decision_switch` | `approval_gate`

---

## Node Palette — shipped today vs roadmap

Path B (2026-05-15) — workflow builder hỗ trợ **10 node types** thay vì 4. Roadmap ~30 nodes thêm.

| Nhóm | Shipped Build Week | Roadmap Q4 2026 |
|---|---|---|
| **Nghiệp vụ cơ bản** | Bước nghiệp vụ, Phê duyệt, Thông báo | Đa cấp phê duyệt, Thu chữ ký, Tải lên tài liệu |
| **Quyết định** | Quyết định (if/else đa nhánh), Phân loại (switch) | Bảng quyết định, AI Classification, AI Validation |
| **Điều phối thời gian** | Chờ sự kiện, Hạn xử lý | Lịch định kỳ, Cảnh báo SLA tự động, Re-open request |
| **Điều phối nâng cao** | Chạy song song, Hợp nhánh, Quy trình con | Fork & Merge, Race, Loop, Compensation |
| **Dữ liệu & Pipeline** | (auto-trigger qua workflow_step_documents) | ETL Trigger, Sync ERP/CRM, Data Quality Check |
| **Tích hợp hệ thống** | (consent_external opt-in trên LLM gateway) | REST connector, gRPC connector, SAP/Oracle adapter |
| **Bảo mật & tuân thủ** | (RLS + decision audit log) | Risk Check, Compliance Check, Contract Validation |
| **Phân tích & báo cáo** | (KPI Gold view) | KPI Check, Audit Snapshot, Analytics Push |
| **Ngoại lệ & phục hồi** | (saga compensation schema) | Retry policy, Rollback, Manual override |

> **Tổng:** 10 ship hôm nay × 12 nhóm × ~30 node roadmap → Kaori ngang Camunda (~38 nodes) vào Phase 2.

---

## Cross-Workflow Links (Vingroup-class differentiator)

Workflow A của VinMart Sales **trigger** Workflow B của VinEco Production.

System auto-detects 5 **cross-dimension flags**:

| Flag | Example |
|---|---|
| `crosses_department` | Sales → CS (same enterprise) |
| `crosses_enterprise` | VinMart → VinMart+ (same division) |
| `crosses_division` | **VinMart Bán lẻ → VinEco Nông nghiệp** |
| `crosses_branch` | HN Sales → HCM Warehouse |
| `crosses_corporate_group` | (blocked — workspace boundary) |

**Why this matters:** Camunda/Zeebe model workflow chains within 1 enterprise. Kaori models conglomerate-wide chains within 1 workspace. → Vingroup HQ thấy + audit toàn bộ chain xuyên 16 công ty.

---

## CDFL — The Differentiator

**Curiosity-Driven Foraging Logic** — ported from my master's thesis.

The problem with commodity AI agents:

> Pure **exploit** → agent loops on top-N actions, never discovers new patterns
> Pure **explore** → agent thrashes, never converges

CDFL formalizes the balance via **Information Gain**:

$$
\text{score}(a) = \alpha \cdot \mathbb{E}[r|a] \cdot c(a) + \beta \cdot \text{IG}(a)
$$

where `c(a)` = confidence, `IG(a)` = expected information gain.

→ Agent prefers actions with **high reward × high confidence** OR **novel × high IG**.

---

## CDFL — Bayesian Update

After each action, update belief distribution:

$$
P(\theta | D_{t+1}) \propto P(o_{t+1} | a_t, \theta) \cdot P(\theta | D_t)
$$

**Plain Vietnamese:**
> Mỗi lần thử 1 action, agent cập nhật xác suất reward expectation. Action càng có information gain cao thì càng learn nhanh.

**Demo moment:** curl `/cdfl/plan-next-action` → return top-3 actions với IG score.

Code shipped: `services/ai-orchestrator/reasoning/cdfl/` — ~143 tests pass.

---

## SQL-first KPI Reasoning

Anh's directive 2026-05-15: **"LLM never computes KPI — only renders"**

Pipeline:

```
1. SQL formula → raw_value     (deterministic, audit-able)
2. classify(raw_value, threshold) → {good, warning, critical}
3. lookup_percentile(value, industry_benchmarks) → tier
4. LLM render Vietnamese narrative
```

**30 canonical KPIs** seeded (mig 049): CAC, LTV, ROAS, ROAS,
churn_rate, inventory_turnover, AR_DSO, cash_runway, working_capital_ratio, …

**Industry benchmarks** per (industry, kpi_code, region, year) — `P25 / P50 / P75 / P90`.

→ No hallucination on numbers. Every audit trail traceable.

---

## Compliance & Multi-Tenant Posture

**Today (Phase 1):**

| Capability | Coverage |
|---|---|
| K-1 tenant isolation (RLS) | ✅ workspace-scoped + enterprise-scoped + ABAC dept-scope |
| K-12 — tenant_id JWT-only | ✅ never accepted from request |
| K-13 — Idempotency keys | ✅ Redis 24h + Postgres 7d (mig 041) |
| K-17 — side_effect_class on every node | ✅ schema-enforced (mig 053) |
| Cross-tenant attempt audit | ✅ mig 040 |
| Workflow approval audit | ✅ mig 042 |
| Decision audit log | ✅ since mig 005 |

**SOC 2 Type 1 readiness:** ~80%.
Gaps remaining: hash-chained immutable audit log (Phase 2), GDPR data subject workflow (Phase 2).

---

## Roadmap

```
2026-07 ───── Build Week (today)
                ├── Workflow Definition + Card model
                ├── CDFL reasoning live endpoint
                ├── Cross-workflow link metadata
                ├── SQL-first KPI engine
                └── Medallion strict 3-layer

2026-Q4 ───── Phase 2: Execution Engine
                ├── Temporal worker enable (skeleton today)
                ├── Saga + compensation runtime
                ├── Timer + event correlation
                └── Process Mining auto-discovery

2027-Q1 ───── Phase 3: Knowledge Graph
                ├── Apache AGE on Postgres (low ops cost)
                ├── Multi-aspect entity (1 canonical customer × N views)
                ├── Lineage column-level
                └── Neo4j scale-out when 10M+ entities
```

---

## Ask

Em tìm **1 Vietnamese conglomerate** (5+ subsidiaries) sẵn sàng pilot Phase 1.

**Currently shipped + reproducible:**
- Vingroup-class demo dataset (mig 056) — 1 corp + 8 divisions + 16 subsidiaries
- 18 workflow templates × 6 dept types
- Smoke test 19 checks PASS reliable (5 consecutive runs)
- 833 backend tests pass · TypeScript clean

**Pilot scope (3 months):**
1. Onboard 1 subsidiary fully (workflow + docs + KPI)
2. Extend to 3 subsidiaries (cross-link demo)
3. CDFL recommendation A/B test vs baseline (measure decision quality lift)

Em mong hội đồng giới thiệu mentor / corporate contact.

**GitHub:** github.com/yuta9999zn/kaori-system (privatized for pilot)
**Email:** yuta9999k@gmail.com

---

# Cảm ơn

Q&A — 5 phút buffer
