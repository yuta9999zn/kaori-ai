# Build Week — Multi-tenant Enterprise Analysis

> **Version:** 1.1 | **Created:** 2026-05-15 | **Updated:** 2026-05-15 (anh's SQL-first directive)
> **Sprint:** P15-S11 Tuần 7 prep
> **Spec source:** `D:\Kaori Document\2Kaori_Pipeline_Unified.docx` (611 paragraphs, 12 stages, Phần 16 multi-tenant, Phần 18 roadmap)
> **Reference dataset:** Olist Brazilian E-Commerce (`data/kaggle/olist/`, 121MB, 9 CSVs)
> **Branch state:** `feat/p15-s9-d1` HEAD `81da71d` — 8 commits ahead origin/main

This doc maps anh's enterprise multi-branch/multi-department questions to the canonical Pipeline_Unified spec, then audits current BE state against it. It exists so we don't jump to UI before the foundations work for a real enterprise dataset.

---

## 1. The enterprise reality anh asked about

Câu hỏi của anh (paraphrased):

> "1 doanh nghiệp được connect Kaori → upload data. Nhưng doanh nghiệp có nhiều chi nhánh, mỗi chi nhánh nhiều công ty con, mỗi công ty con nhiều phòng ban (KD/marketing/sales/CSKH/nhập kho/xuất kho/nhân sự...). Thiết kế upload + storage + AI mapping + correction UI + SQL optimization + Medallion ETL + per-department reports — như nào cho hợp lý?"

Spec `2Kaori_Pipeline_Unified.docx §1.1` đã có folder architecture tương ứng:

```
📁 Workspace [tenant_id]            ← doanh nghiệp tổng
   ├── 📁 Departments               ← phòng ban LÀ first-class concept
   │   ├── 📁 Marketing
   │   │   ├── 📁 Sources           ← KiotViet POS / Manual upload / API
   │   │   │   ├── 📁 2026/04       ← partition theo Year/Month/Day
   │   │   │   │   ├── 📄 customers_20260401.csv
   │   │   │   │   └── 📄 transactions_20260401.csv
   │   ├── 📁 Sales
   │   ├── 📁 Customer Service
   │   ├── 📁 Warehouse
   │   ├── 📁 HR
   │   └── 📁 Finance
```

Spec missing: **chi nhánh (branch) level**. Spec dừng ở `Workspace → Department`. Em đề xuất extend thành `Workspace → Branch → Department` (3 cấp) hoặc dùng `organizational_units` self-referencing (n cấp).

---

## 2. Current BE coverage — % done vs spec

### Multi-tenant hierarchy

| Spec component | Table/Code | State | % |
|---|---|---|---|
| `workspaces` (tenant) | `001_init.sql:27` | ✅ Ship | 100% |
| `enterprises` (sub-org under workspace) | `001_init.sql:37` | ✅ Ship | 100% |
| `branches` (chi nhánh) | **không có** | ❌ | **0%** |
| `departments` (phòng ban) | **không có** | ❌ | **0%** |
| `data_sources` (KiotViet/Manual/...) | **không có** | ❌ | **0%** |
| RLS K-1 by `tenant_id` | enabled all data tables | ✅ Ship | 100% |
| RLS by `department_id` (ABAC §16.4) | không có | ❌ | **0%** |
| Per-tenant DEK + KEK envelope (§16.1) | có Vault scaffold | ⚠️ Phase 1.5 deferred | 30% |

### Upload pipeline

| Spec component | Code | State | % |
|---|---|---|---|
| Pre-flight check (browser-side) §1.2 step 1 | không có | ❌ | **0%** |
| Resumable chunk upload §1.2 step 2 | `routers/upload.py:upload_file` single-shot | ❌ chỉ single-shot | **20%** |
| Bronze path `{tenant}/{dept}/{source}/{year}/{month}/{day}/` §1.3 | MinIO root chưa partition | ⚠️ Phase B-2 sẽ split | 40% |
| metadata.json sidecar §1.3 | có manifest table thay vì JSON file | ⚠️ functional equiv | 70% |
| Bronze append-only + SHA256 (K-2 + K-8) | ✅ enforced | ✅ Ship | 100% |
| Compression gzip §1.5 | không default | ❌ | **0%** |
| Quota per workspace | có (subscription_plans) | ⚠️ chưa per-dept | 50% |

### Schema detection (Stage 2)

| Spec component | Code | State | % |
|---|---|---|---|
| 2A Heuristic detection §2.1 | `routers/schema.py` + `services/llm-gateway` keyword match | ✅ Ship | 80% |
| 2B LLM-assisted fallback | llm-gateway Qwen path | ✅ Ship | 80% |
| 2C User Confirmation UI §2.1 | BE `/schema/confirm` có, **FE chưa wire** | ⚠️ Half | **50%** |
| Required vs Optional gate §2.2 | có | ✅ Ship | 80% |
| **Mapping templates re-use** §2.3 | **không có table** | ❌ | **0%** |
| Schema Evolution Detection §2.4 | partial (snapshot test) | ⚠️ | 30% |

### Cleaning + Quality (Stage 3-4)

| Spec component | Code | State | % |
|---|---|---|---|
| Universal rules (encoding/whitespace/junk row) §3.2 | `silver/rule_catalog.py` | ✅ Ship | 90% |
| Domain rules (phone VN E.164/etc) §3.3 | `silver/rule_catalog.py` | ✅ Ship | 80% |
| AI-detected rules §3.4 | có hook | ⚠️ partial | 50% |
| Quality scorecard 7 dimensions §4 | có | ✅ Ship | 70% |
| Quality gate block <60 → blocked | có | ✅ Ship | 80% |

### Gold layer (Stage 8)

| Spec component | Code | State | % |
|---|---|---|---|
| Gold = views (not tables) §8.1 | có `data_plane/gold/` | ✅ Ship | 80% |
| Materialized views for hot queries | partial | ⚠️ | 40% |
| **Per-department Gold customization** §8.3 | **không có routing** | ❌ | **0%** |
| Redis cache layer §8.5 | hạ tầng có, chưa wire | ⚠️ | 30% |

### Per-department reports (Stage 10-12)

| Spec component | Code | State | % |
|---|---|---|---|
| Insight composition 3-layer §10 | `reasoning/insight_engine/` | ✅ Ship | 60% |
| Per-department layout | **không có** | ❌ | **0%** |
| Workflow Builder UI | có FE template (1 file) | ⚠️ 10% | 10% |

### Tổng hợp

**BE đã giải quyết: ~55-60% so với enterprise multi-branch/multi-department requirements.**

Critical gaps (phải lấp trước khi UI có giá trị thực):
1. `branches` + `departments` tables + RLS ABAC scope
2. `mapping_templates` table for re-usable schema rules
3. `data_sources` registry (KiotViet/Manual/API/...)
4. Upload endpoint accept `department_id` + `source_id`
5. Bronze path include department partition
6. Per-department Gold view routing

---

## 3. Bài toán "data lớn" — risks + xử lý

Anh hỏi: "với số lượng data lớn thì sẽ có thể xảy ra lỗi gì?"

### Risk register

| Risk | Khả năng | Phase 1 mitigation |
|---|---|---|
| Single-shot upload fail trên file >100MB (VN bandwidth) | High (~25% spec §1.2) | Resumable chunk upload — chưa có, **gap** |
| OOM khi parse Excel >500MB | Medium | Stream parser (pandas chunksize) — em xác nhận `bronze/ingestor.py` đã có |
| JSONB raw_data swell trên `bronze_rows` | High | Partition theo `year_month` — không có, **gap** |
| Index lookup chậm trên bronze >10M rows | High | `enterprise_id, file_id` index có; thêm `department_id, source_id, uploaded_at` partial indexes |
| Silver re-compute toàn bộ khi upload mới | High (theo spec §15 Strategy A) | Incremental processing — Phase 3 (chấp nhận Phase 1) |
| Gold MV refresh kéo dài >5min → dashboard 503 | Medium | Async refresh + Redis serve stale — chưa wire |
| RLS bypass do query forget `acquire_for_tenant` | High (incident risk) | `check-tenant-filter.py` arch guard — ✅ có |
| Cross-tenant data leak qua bronze_rows JSONB | High | RLS + K-12 header enforcement — ✅ có |
| LLM schema detect timeout >30s | Medium | Cache `mapping_templates` per source — **gap** |
| Workflow run lost on worker crash | Medium | Temporal + idempotency_records — ✅ shipped P15-S6 |
| Quota gaming via department split | Low | `enterprise_monthly_billing` K-11 dedup — ✅ |

### Phải fix Tuần 7 (trước UI demo)

1. **Bronze partition by `(enterprise_id, department_id, year_month)`** — migration 048
2. **Composite indexes** `(department_id, source_id, uploaded_at DESC)` trên bronze + silver
3. **`mapping_templates` cache table** + retrieval lookup
4. **Resumable upload** — Phase B follow-up, defer post-Build-Week (Build Week demo dùng file ≤50MB)

### Defer post-Build-Week

- Incremental Silver re-compute
- Redis Gold cache wire
- Differential schema evolution

---

## 4. UI design — Upload + display + correction

### 4.1 Upload UI hierarchy (FE Wizard)

Step 1 — **Choose context** (mới):
```
Workspace: Cà phê Phúc Long (current)
├─ Branch: ◯ HN  ◯ HCM  ◯ All branches
└─ Department: ◯ Sales  ◯ Marketing  ◯ Warehouse  ◯ HR  ...
   Source: ◯ KiotViet  ◯ Manual upload  ◯ Zalo OA  ◯ Other
```

Step 2 — **Pre-flight + Upload** (`20-data-pipeline-step-1-upload-file.tsx`):
- File picker
- BE returns: `{upload_id, presigned_url, sha256}` — em đề xuất add resumable trong Phase 2.
- Build Week version: single-shot ≤50MB.

Step 3 — **Schema Mapping confirmation** (`21-data-pipeline-step-2-configure-columns.tsx`):

Mockup (per spec §2.1 stage 2C):

```
┌────────────────────────────────────────────────────────────┐
│ Schema Mapping — customers_20260401.csv                    │
├────────────────────────────────────────────────────────────┤
│ Column file       AI suggestion (conf)    Sửa             │
│ ────────────────  ──────────────────────  ────────        │
│ ma_kh             customer_id (0.95)      [✓ keep] ▼      │
│ sdt               phone (0.88)             [✓ keep] ▼      │
│ tong_tien         amount_vnd (0.92)        [✓ keep] ▼      │
│ ngay              date (0.78)              [✓ keep] ▼      │
│ ghi_chu           ⚠ unknown (0.45)        [! pick]  ▼     │← cần user sửa
│  ↓ pick dropdown:                                          │
│    - customer_note                                         │
│    - internal_memo                                         │
│    - other                                                 │
│    - DROP COLUMN                                           │
└────────────────────────────────────────────────────────────┘
```

**Rule:** confidence ≥0.7 → auto-confirm + show as keep. <0.7 → highlight + force user pick.

### 4.2 AI uncertainty correction loop

Spec §2.1 stage 2B fallback to LLM, §2.1 stage 2C user confirm. Workflow:

```
Upload → 2A Heuristic per column
       → if confidence >= 0.85: auto-accept
       → if 0.7 <= confidence < 0.85: pre-fill + user confirms
       → if confidence < 0.7: invoke 2B LLM (Qwen)
       → if LLM confidence < 0.7: ⚠ require user input (block)
       → record correction → save as mapping_template (Section 2.3)
       → next time same source: auto-apply template, user just confirms
```

**Correction storage:** new table `mapping_templates`:
- `template_id`
- `enterprise_id`, `department_id`, `source_id`
- `file_pattern` (e.g. `customers_*.csv`)
- `column_mapping` JSONB
- `created_by_user`, `confirmed_count`

When new file matches `file_pattern` → auto-load template → user reviews changes (if any) → applies.

### 4.3 Display after ingestion

Bronze (`15-data-bronze.tsx`): show raw rows paginated, lineage breadcrumb (workspace → branch → dept → source → file).
Silver (`16-data-silver.tsx`): show cleaned rows + which cleaning rules fired.
Gold (`17-data-gold.tsx`): show **per-department** views — Marketing sees campaign_performance, Sales sees lead_scoring, Warehouse sees stock_turnover.

---

## 5. SQL optimization — stored procedures + triggers + indexes

### 5.1 Stored procedures (defer)

Spec không yêu cầu SP cho Phase 1. Mọi business logic ở app layer (Python/Java). SP only when:
- Hot read path needs server-side aggregation (e.g. real-time KPI tile)
- ETL step needs transaction-scoped multi-table mutation

Em đề xuất: **không SP cho Build Week.** Phase 2 add 2-3 SP cho dashboard tiles.

### 5.2 Triggers (defer mostly)

K-2 (Bronze append-only) đã enforce via `UPDATE/DELETE ... USING (false)` policy không bằng trigger. Audit logging có thể dùng trigger nhưng:

- **trigger on bronze_files INSERT** → write to `pipeline_runs` already done by app code.
- **trigger on silver_rows UPDATE** → invalidate Redis cache. Phase 2 add 1 trigger.

Em đề xuất: **1 trigger `silver_cache_invalidate`** post-Build-Week.

### 5.3 Indexes — what to add Tuần 7

Em propose migration 048 thêm:

```sql
-- Hot read paths
CREATE INDEX idx_bronze_files_dept_uploaded
    ON bronze_files (enterprise_id, department_id, uploaded_at DESC);
CREATE INDEX idx_bronze_rows_file_idx
    ON bronze_rows (file_id, row_index);
CREATE INDEX idx_silver_rows_dept_quality
    ON silver_rows (enterprise_id, department_id, quality_score DESC);
CREATE INDEX idx_gold_views_dept
    ON gold_features (enterprise_id, department_id, computed_at DESC);

-- Mapping template lookup
CREATE INDEX idx_mapping_templates_pattern
    ON mapping_templates (enterprise_id, source_id, file_pattern);

-- JSONB GIN cho raw_data filter
CREATE INDEX idx_bronze_rows_raw_gin
    ON bronze_rows USING gin (raw_data);
```

GIN trên `raw_data` JSONB cho phép `WHERE raw_data->>'customer_id' = ?` nhanh.

### 5.4 Partitioning

`api_request_log` đã partition theo month. Apply same cho:
- `bronze_rows` — partition by year_month (cut size per partition)
- `silver_rows` — partition by year_month

Migration 049 implements.

---

## 5.5 SQL-first directive (anh's principle, 2026-05-15)

> "Hệ thống này không được rời xa SQL. Từ kết quả SQL, sau đó với RAG của
> từng chuyên ngành, từng đối tượng được update với thước đo chuẩn nhất,
> ta mới ra được kết quả và đánh giá được."

**Insight pipeline pattern (mandatory):**

```
1. SQL aggregation (Gold view per dept)          ← Backbone, single source of truth
       ↓ raw measurement (numbers)
2. KPI definition lookup (per dept_type)         ← Thước đo chuẩn (`kpi_definitions` table)
       ↓ classification (Good / Warning / Critical)
3. Industry benchmark lookup (per industry)      ← Compare with peers (`industry_benchmarks` table)
       ↓ percentile / variance
4. RAG enrich — chuyên ngành context             ← Định nghĩa thuật ngữ + formula
       ↓ Vietnamese explanation
5. Final insight + recommendation                ← LLM RENDERS, không phải LLM COMPUTES
```

**Critical constraints:**
- ❌ Không bypass SQL bằng vector search trực tiếp answer câu hỏi business.
- ❌ Không cho LLM tự tính KPI — số liệu luôn từ SQL Gold view.
- ✅ RAG chỉ dùng để: định nghĩa thuật ngữ, tra industry benchmark text, render Vietnamese explanation.
- ✅ Mỗi dept_type có ~5-8 KPI chuẩn pre-defined, mỗi industry có percentile reference.

**New tables (Tuần 7.5):**

| Table | Purpose |
|---|---|
| `kpi_definitions` | per (dept_type, kpi_code) → formula SQL fragment, threshold ranges, unit, direction (higher_better / lower_better) |
| `industry_benchmarks` | per (industry, kpi_code) → P25/P50/P75/P90 percentile values + source citation (Bain/McKinsey/Olist data) |
| `kpi_measurements` | per (enterprise_id, dept_id, kpi_code, period) → computed value + classification + percentile vs benchmark |

KPI definition examples for `dept_type='marketing'`:

| kpi_code | formula (Gold view fragment) | unit | threshold_good | threshold_warning |
|---|---|---|---|---|
| `cac` | `SUM(marketing_spend) / COUNT(new_customers)` | VND | <500K | 500K-1M |
| `ltv` | `SUM(revenue) / COUNT(unique_customers) * avg_lifespan_months` | VND | >5M | 2-5M |
| `ltv_cac_ratio` | `ltv / cac` | ratio | >3.0 | 1.5-3.0 |
| `roas` | `SUM(campaign_revenue) / SUM(campaign_spend)` | ratio | >4.0 | 2-4 |
| `churn_rate_monthly` | `COUNT(churned) / COUNT(active_start)` | pct | <2% | 2-5% |

For `dept_type='sales'`:
- `conversion_rate_lead_to_deal`, `deal_velocity_days`, `win_rate`, `avg_deal_size`, `quota_attainment`

For `dept_type='finance'`:
- `gross_margin_pct`, `ar_days_outstanding`, `cash_runway_months`, `revenue_growth_yoy`

For `dept_type='warehouse'`:
- `stockout_rate`, `inventory_turnover`, `dead_stock_pct`, `supplier_lead_time_days`

For `dept_type='hr'`:
- `attrition_rate_annual`, `time_to_hire_days`, `cost_per_hire`, `employee_nps`

For `dept_type='customer_service'`:
- `csat_score`, `nps`, `first_response_minutes`, `ticket_resolution_hours`, `escalation_rate`

**Reasoning Layer architecture (L3 update):**

```
reasoning/
├── insight_engine/           # Existing
├── kpi_engine/              # NEW Tuần 7
│   ├── definitions.py        # Load kpi_definitions table
│   ├── compute.py            # Run SQL formula against Gold view
│   ├── classify.py           # Classify Good/Warning/Critical vs threshold
│   └── benchmark.py          # Lookup industry_benchmarks + percentile
├── cdfl/                     # Tuần 1 — exploration/lookahead/IG
└── rag/                      # Tuần 2,6 — chuyên ngành context only
```

CDFL ↔ KPI engine relationship:
- KPI engine = **deterministic SQL** (mandatory backbone)
- CDFL = **optional ranking layer** when surfacing top-K recommendations from a candidate set
- RAG = **context enrichment** (Vietnamese explanation, term definition, benchmark citation)

Output composer:
```python
async def render_insight(enterprise_id, dept_id, kpi_code, period):
    # 1. SQL aggregation
    raw = await sql_compute(kpi_code, enterprise_id, dept_id, period)

    # 2. KPI classify
    klass = classify_against_thresholds(raw, kpi_code)  # Good / Warning / Critical

    # 3. Industry benchmark
    pct = await lookup_percentile(industry, kpi_code, raw)

    # 4. RAG enrich
    context = await rag_lookup_kpi_context(kpi_code, locale='vi')

    # 5. LLM render (not compute)
    return await llm_render({
        'kpi': kpi_code,
        'value': raw,
        'classification': klass,
        'percentile_vs_industry': pct,
        'context_text': context,  # term def + benchmark citation
    })
```

This guarantees:
- All numbers traceable to SQL (auditable, reproducible)
- LLM cannot hallucinate KPI values
- Industry benchmark always cited (no "según mi conocimiento general")
- RAG layer's job is narrow + verifiable

---

## 6. Medallion ETL — chuẩn hóa

### 6.1 Bronze (immutable raw)

Path: `s3://kaori-bronze/{tenant_id}/{branch_id}/{dept_id}/{source_id}/{year}/{month}/{day}/{upload_id}/data.csv.gz`

Tables:
- `bronze_files` — 1 row per upload, manifest metadata
- `bronze_rows` — JSONB raw payload, append-only, partitioned year_month

### 6.2 Silver (cleaned + typed)

Tables per domain:
- `silver_customers` — schema-enforced customer master
- `silver_orders` — order line items
- `silver_products`
- `silver_employees` (HR)
- `silver_inventory` (warehouse)
- Each carries `enterprise_id` + `department_id` + `branch_id` for ABAC

ETL: Bronze → cleaning rules (3 layers: universal + domain + AI) → Silver. Trigger on Bronze write fan-out → Silver workers.

### 6.3 Gold (per-department views)

Views named `gold.<domain>_<department>`:
- `gold.customer_360_marketing` (lifecycle + segments)
- `gold.customer_360_sales` (pipeline + deal stage)
- `gold.customer_360_cs` (tickets + satisfaction)
- `gold.inventory_warehouse` (stock turnover)
- `gold.payroll_hr` (headcount + cost)
- `gold.kpi_finance` (revenue / margin / cash flow)

Each view filters by `enterprise_id` + optionally `department_id` per ABAC.

Materialized for hot queries; Redis cache 15min TTL.

---

## 7. Per-department report layouts

Spec §8.3:

| Department | Top-3 Gold views | Default dashboard tiles |
|---|---|---|
| **Marketing** | customer_360_marketing, campaign_performance, cohort_retention | LTV, churn risk, top campaigns |
| **Sales** | customer_360_sales, lead_scoring, deal_pipeline | conversion rate, deal velocity, top reps |
| **Customer Service** | ticket_summary, csat_trend, complaint_categories | avg response time, csat NPS, escalations |
| **Warehouse** | inventory_warehouse, stock_turnover, supplier_lead_time | stockout rate, dead stock %, restock alerts |
| **HR** | payroll_hr, headcount_trend, attrition_rate | turnover %, payroll cost, hiring funnel |
| **Finance** | kpi_finance, revenue_breakdown, cash_flow | margin %, AR aging, cash runway |

Each FE dashboard page = `/p2/dashboard/{department_slug}` (e.g. `/p2/dashboard/marketing`), fetches `/api/v1/p2/dashboard/marketing/state`.

---

## 8. Olist dataset — Build Week demo mapping

Em pull Olist Brazilian E-commerce (`data/kaggle/olist/`). Mapping vào Kaori multi-tenant:

| Olist file | Map vào Kaori |
|---|---|
| `olist_sellers_dataset.csv` (3,095 sellers) | **branches** (mỗi seller = 1 chi nhánh) |
| Product categories (74) | **departments** (electronics, fashion, food, etc.) |
| `olist_customers_dataset.csv` (99,441) | customers in `silver_customers` |
| `olist_orders_dataset.csv` (99,441) | transactions in `silver_orders` |
| `olist_order_items_dataset.csv` (112,650) | order line items |
| `olist_order_payments_dataset.csv` | payment events |
| `olist_order_reviews_dataset.csv` (100k) | CSAT signals |
| `olist_products_dataset.csv` (32,951) | product catalog |
| `olist_geolocation_dataset.csv` | geographic enrichment |

Demo narrative: "Olist là marketplace có 3,095 chi nhánh người bán, 74 phòng ban (category), 99k customer. Kaori ingest → cho thấy:
- Marketing dept: top categories by revenue
- Sales dept: top sellers by GMV
- CS dept: reviews + complaints
- Warehouse dept: shipping delays per seller"

→ Tự nhiên show được multi-tenant + multi-department + per-dept reports.

---

## 9. Plan Tuần 7-8 (revised từ original)

Original plan: UI wire 7 màn flagship. Sau review: phải lấp 5 gap critical trước.

### Tuần 7 (15-22/5) — Foundation (revised)

| Day | Task | Output |
|---|---|---|
| 1 | Migration 046 — `branches` + `departments` + `data_sources` tables | SQL ship |
| 2 | Migration 047 — add `branch_id` + `department_id` + `source_id` columns to bronze_files, silver_*, gold_features + RLS update | SQL ship |
| 3 | Migration 048 — `mapping_templates` table + cache lookup | SQL ship |
| 4 | Upload endpoint upgrade — accept `branch_id` + `dept_id` + `source_id` headers | `routers/upload.py` |
| 5 | Per-department Gold view routing — `data_explorer.py` returns per-dept views | router update |

### Tuần 7.5 (23-26/5) — Olist seed

| Day | Task | Output |
|---|---|---|
| 6 | Script `scripts/seed_olist_into_kaori.py` — ingest Olist → branches + departments + bronze | script ship |
| 7 | Verify pipeline: upload 1 Olist file → schema confirm → Silver → Gold per-dept | E2E smoke |

### Tuần 8 (26/5 → 8/7) — UI wire

7 flagship màn — anh đã có TSX templates ở `D:\Kaori Document\frontend template\user enterprise\`. Em wire BE → FE component-by-component.

Time-boxed: nếu Tuần 7 trượt → reduce UI to 4 màn flagship (Pipeline Wizard + Bronze/Silver/Gold + Marketing dashboard).

---

## 10. Decisions cần anh chốt

| # | Decision | Em đề xuất |
|---|---|---|
| D1 | Hierarchy: 3-cấp (workspace→branch→department) hay self-referencing `organizational_units`? | **3-cấp** — đơn giản, đủ cho 95% SME Việt; n-level chỉ cần khi enterprise nội-bộ đa quốc gia |
| D2 | Department list: enum cố định (Marketing/Sales/CS/Warehouse/HR/Finance) hay free-form? | **Enum cố định 6 phòng** mặc định + free-form custom — UX rõ ràng, default reports work |
| D3 | Mapping templates: workspace-scope hay department-scope? | **Department-scope** — Marketing's customer file khác Sales's customer file |
| D4 | Resumable upload: ship Build Week hay defer? | **Defer** — Build Week file ≤50MB an toàn |
| D5 | Per-dept Gold view: 6 views cố định hay generated per dept? | **6 views cố định Phase 1** — generated per-dept là Phase 2 |
| D6 | Demo dataset: Olist (English) hay self-translate (Vietnamese)? | **Olist English** — đỡ overhead translate, anh dùng narrative tiếng Việt show |
| D7 | Wire UI ngay (giảm 4 màn) hay làm foundations trước? | **Foundations trước** — UI mà không có dept routing thì không demo "doanh nghiệp đa chi nhánh" được |

---

## 11. Sources cross-referenced

- `D:\Kaori Document\2Kaori_Pipeline_Unified.docx` — canonical 12-stage spec
- `D:\Kaori Document\5Kaori_AI_SAD_Skeleton_v2.docx` — architecture
- `data/kaggle/olist/` — reference dataset
- `services/data-pipeline/routers/upload.py` — current upload endpoint
- `services/data-pipeline/data_plane/{bronze,silver,gold}/` — pipeline code
- `services/auth-service/.../WorkspaceController*` — workspace/enterprise CRUD
- `infrastructure/postgres/migrations/001_init.sql` — base schema
- `docs/strategic/CDFL_INTEGRATION.md` — Tuần 1-6 prior work

---

*Author: Kaori (em) — prep before Tuần 7 implementation, 2026-05-15.*
*Awaits anh decision on D1-D7 before coding.*
