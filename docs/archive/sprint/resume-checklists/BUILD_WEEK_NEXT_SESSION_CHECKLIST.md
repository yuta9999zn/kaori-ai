# Build Week — Next Session Resume Checklist

> **Created:** 2026-05-15 (end of Tuần 7)
> **Deadline:** Build Week 8/7/2026 — em còn ~7 tuần
> **Branch:** `feat/p15-s9-d1` HEAD `7a408bd` origin (push xong)
> **PR:** #179 OPEN, CI red ALL (budget exhausted; anh "làm tay" — accept red CI)
> **Spec:** `docs/strategic/BUILD_WEEK_MULTI_TENANT_ANALYSIS.md` (anh đã chốt 4 default Tuần 7)

Đọc khi quay lại session. Đi từ §1 → §5 theo thứ tự.

---

## 1. Snapshot state (frozen 2026-05-15)

### Tests + commits

| Service | Tests | Δ Tuần 7 |
|---|---|---|
| ai-orchestrator | **782** | +37 (kpi_engine) |
| notification-service | 58 | 0 |
| data-pipeline | 424 | 0 |

11 commits ahead `origin/main` (toàn bộ session 2026-05-15):

```
7a408bd  feat(p15-s11): Olist seed script + shape tests — Tuần 7 ngày 7
8d2329b  feat(p15-s11): reasoning/kpi_engine/ — SQL-first deterministic KPI backbone
168dd58  feat(p15-s11): migs 047-050 — dept FKs + mapping templates + KPI backbone + GIN
9cde993  feat(p15-s11): mig 046 org hierarchy + SQL-first reasoning directive
832b33b  docs(p15-s11): Tuần 7 prep — multi-tenant analysis + 4 decisions chốt
81da71d  feat(p15-s11): Tuần 6 — CDFL IG re-ranking on /rag/answer + full demo E2E
9296019  feat(p15-s11): Tuần 5 — /workflow/from-cdfl-plan emitter
fea6387  feat(p15-s11): local-toc PageIndex backend + Tableau book fixture
560266e  feat(p15-s11): Tuần 4 — /process-mining/mine + /cdfl/plan-next-action + Phúc Long
65f357f  feat(p15-s11): PageIndex fixture builder + migration 045 + stub leak fix
e8efb01  feat(p15-s11): port CDFL v3 from NNL-NTHT thesis into reasoning/cdfl/
```

### Backend coverage cho enterprise multi-branch/multi-department

| Component | State |
|---|---|
| 3-cấp hierarchy (w→branch→dept) + RLS | ✅ mig 046 |
| Dept FK trên bronze/silver/gold + ABAC scope | ✅ mig 047 |
| mapping_templates re-usable | ✅ mig 048 (BE table) — endpoint chưa wire |
| 30 KPI definitions + industry benchmarks | ✅ mig 049 |
| GIN/BRIN/multi-col stats | ✅ mig 050 |
| `reasoning/kpi_engine/` deterministic compute | ✅ shipped + 37 tests |
| Olist seed script (dry-run verified) | ✅ scripts/seed_olist_into_kaori.py |
| 4 endpoint flagship (mine/plan/yaml/rag-ig) | ✅ Tuần 4-6 |
| Phúc Long demo fixture | ✅ Tuần 4 |
| Tableau book PageIndex fixture | ✅ Tuần 2 |

**BE: ~85-90% done. Còn thiếu: Upload endpoint upgrade + UI wire.**

---

## 2. Anh's directives chốt (canonical — không invent)

| # | Directive | Date |
|---|---|---|
| D1+D2 | 3-cấp w→branch→dept + 6 enum dept + custom | 2026-05-15 |
| D3+D5 | Mapping template dept-scope + 6 Gold views cố định | 2026-05-15 |
| D6 | Demo dataset = Olist English + narrative tiếng Việt | 2026-05-15 |
| D7 | Foundations trước, UI sau | 2026-05-15 |
| SQL-first | LLM chỉ RENDER, KHÔNG COMPUTE. Pipeline: SQL → KPI threshold → industry benchmark → RAG enrich → LLM render | 2026-05-15 |
| Branch state ko cần wait CI | Anh "làm tay" — push thoải mái, accept red CI cho tới tháng 6 budget reset | 2026-05-15 |

---

## 3. Pre-flight CHECK trước khi code Tuần 8

### Step 3.1 — Verify migrations apply OK

Anh có Postgres local chạy? Test mig 046-050:

```powershell
cd "D:\Kaori System"
docker compose up postgres -d
# Đợi 5s
docker exec kaori-postgres-1 psql -U kaori_user -d kaori -c "\dt branches"
docker exec kaori-postgres-1 psql -U kaori_user -d kaori -c "\dt departments"
docker exec kaori-postgres-1 psql -U kaori_user -d kaori -c "\dt data_sources"
docker exec kaori-postgres-1 psql -U kaori_user -d kaori -c "\dt mapping_templates"
docker exec kaori-postgres-1 psql -U kaori_user -d kaori -c "\dt kpi_definitions"
docker exec kaori-postgres-1 psql -U kaori_user -d kaori -c "\dt industry_benchmarks"
docker exec kaori-postgres-1 psql -U kaori_user -d kaori -c "\dt kpi_measurements"
# Expect: all 7 tables present
```

If Flyway chưa apply, force re-run auth-service boot:

```powershell
docker compose up auth-service -d
docker logs kaori-auth-service-1 | findstr "Flyway"
```

### Step 3.2 — Olist seed (real mode)

```powershell
cd "D:\Kaori System"
$env:DATABASE_URL = "postgresql://kaori_user:kaori_pass@localhost:5432/kaori"
python scripts/seed_olist_into_kaori.py --real --sample-rows 1000
```

Expected output:
```
workspace_id   = <uuid>
enterprise_id  = <uuid>
branch_id      = <uuid>
sales              : 4 files,      4,000 rows
customer_service   : 1 files,      1,000 rows
warehouse          : 2 files,      2,000 rows
finance            : 1 files,      1,000 rows
Total raw size: 120.3 MB
```

Verify:
```powershell
docker exec kaori-postgres-1 psql -U kaori_user -d kaori -c "SELECT dept_type, COUNT(*) FROM bronze_files JOIN departments ON bronze_files.department_id = departments.department_id GROUP BY dept_type;"
```

### Step 3.3 — Tests still green

```powershell
cd "D:\Kaori System\services\ai-orchestrator"
python -m pytest --tb=line | Select-Object -Last 3
# Expect: 782 passed
```

---

## 4. Tuần 8 plan — Upload upgrade + UI wire

### Step 4.1 (≈1d) — Upload endpoint upgrade

`services/data-pipeline/routers/upload.py` currently accepts only `X-Enterprise-ID` + `X-User-ID`. Upgrade signature:

- Add headers: `X-Branch-ID` (optional, default = enterprise default branch), `X-Department-ID` (required), `X-Source-ID` (optional, default = "Manual upload" source for that dept)
- Persist dept_id + branch_id + source_id on bronze_files + bronze_rows via ingestor
- Look up mapping_templates by (enterprise_id, source_id, file_pattern) → pre-fill schema confirmation
- Tests cover: header validation, dept lookup, template auto-load

Reference signature shape:
```python
@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: UUID = Header(..., alias="X-User-ID"),
    x_department_id: UUID = Header(..., alias="X-Department-ID"),
    x_branch_id: Optional[UUID] = Header(None, alias="X-Branch-ID"),
    x_source_id: Optional[UUID] = Header(None, alias="X-Source-ID"),
):
    ...
```

### Step 4.2 (≈1.5d) — Build Week wire 4 flagship UI screens

TSX templates ở `D:\Kaori Document\frontend template\user enterprise\`. Em wire 4 màn tối thiểu:

| File | Endpoint | BE state |
|---|---|---|
| `09-dashboard-overview.tsx` | `GET /api/v1/dashboard/state` | ✅ orchestrator có |
| `15-data-bronze.tsx` | `GET /api/v1/data/explorer` (đã có) + filter `?department_id=` | ⚠️ filter chưa add |
| `20-24-data-pipeline-step-*.tsx` (Pipeline Wizard 5 bước) | `/upload` + `/schema/*` + `/clean/*` + `/analyze` + `/results` | ✅ all BE có |
| `26-insight-id-detail.tsx` | `/api/v1/rag/answer?ranking=cdfl_ig` | ✅ Tuần 6 |

If kịp thêm 3 nữa:
- `16-data-silver.tsx`, `17-data-gold.tsx` (data explorer drill-down)
- Mới — **KPI Dashboard per-department** (chưa có TSX template, em phải design)

### Step 4.3 (≈0.5d) — Per-department Gold views

Migrations 047 chỉ add `department_id` column. Em phải tạo Postgres views:
- `gold.customer_360_marketing`
- `gold.sales_pipeline`
- `gold.ticket_summary`
- `gold.inventory_warehouse`
- `gold.payroll_hr`
- `gold.kpi_finance`

Skeleton SQL ở `docs/strategic/BUILD_WEEK_MULTI_TENANT_ANALYSIS.md §7`. Each view filters by `enterprise_id` + `department_id`.

→ Migration 051_per_dept_gold_views.sql

### Step 4.4 (≈1d) — Demo script + slide deck

3 slide CDFL section (theory + benchmark + niche statement — see `docs/strategic/CDFL_INTEGRATION.md §5`).
1 slide multi-tenant story (Olist 3,095 sellers as branches, 74 categories as departments simplified to 6 dept_types).
1 slide SQL-first reasoning pipeline.

Demo script 8-12 phút:
1. Show Olist data uploaded into 4 depts (Bronze viewer)
2. Pipeline Wizard 5 bước on a small CSV
3. Marketing dashboard KPI (CAC/LTV with industry benchmark percentile)
4. CDFL Insight: "from current state browse — what are top-3 unexplored actions?" via `/cdfl/plan-next-action`
5. Workflow YAML emit + show K-17 side_effect_class validation
6. RAG `?ranking=cdfl_ig` — query Tableau book → see novelty-seeking across queries

### Step 4.5 (≈0.5d) — 2 dry-run + backup video

Record screen demo as backup if live fail.

---

## 5. Long-term tech-debt — defer post-Build-Week

| Item | Why deferred |
|---|---|
| Resumable chunk upload (S3 presigned URL) | Build Week file ≤50MB safe single-shot |
| Bronze year_month declarative partitioning | Mig 050 BRIN proxy enough; full partitioning needs maintenance window |
| 2-GUC consolidation (`app.enterprise_id` vs `app.current_enterprise_id`) | Cross-cutting change touching shared/db.py + 49 migrations; needs careful planning |
| Differential Silver re-compute | Phase 3 work per spec §15 strategy B |
| Redis Gold cache wire | Infrastructure có, app code chưa hook |
| Generated per-dept Gold templates | 6 hard-coded views Phase 1; template-driven Phase 2 |
| RouteConfig.java gap (/rag, /adoption, /economics, /process-mining, /cdfl, /workflow) | Pre-existing S9/S10 gap; FE bypass gateway in dev. Production cutover phải fix |
| Vendored PageIndex OSS fork (vs cloud SDK) | Currently using `local-toc` fallback via pypdf — K-4/K-5 safe |
| FlywayMigrationIT @MockBean cleanup | Auto-derives from classpath now (verified 2026-05-15); legacy memory had outdated info |

---

## 6. Critical references — bookmark these

| File | What's in it |
|---|---|
| `docs/strategic/BUILD_WEEK_MULTI_TENANT_ANALYSIS.md` | Anh's 4 decisions + SQL-first directive + 7 per-dept report layouts |
| `docs/strategic/CDFL_INTEGRATION.md` | 3 component map + API contract + Build Week slide narrative |
| `services/ai-orchestrator/reasoning/kpi_engine/__init__.py` | KPI compute backbone + GUC tech-debt note |
| `infrastructure/postgres/migrations/049_kpi_definitions_and_benchmarks.sql` | 30 KPI canonical formulas + industry benchmarks |
| `scripts/seed_olist_into_kaori.py` | Olist → Kaori multi-tenant ingest |
| `services/ai-orchestrator/tests/fixtures/demo_phuc_long.py` | Phúc Long demo fixture (54k events) |
| `services/ai-orchestrator/tests/test_build_week_demo_e2e.py` | Full demo E2E chain — mine→plan→yaml→rag-ig |
| `D:\Kaori Document\2Kaori_Pipeline_Unified.docx` | Canonical 12-stage pipeline spec |
| `D:\Luận văn nhất nguyên 2 trường luận giao thoa\` | CDFL theory + 8-phase benchmark |

---

## 7. Quick-resume command sequence

```powershell
# 1. Sync local with origin
cd "D:\Kaori System"
git fetch --all --tags
git checkout feat/p15-s9-d1
git pull --ff-only origin feat/p15-s9-d1

# 2. Verify tests still green
cd services\ai-orchestrator
python -m pytest --tb=line | Select-Object -Last 3
# Expect: 782 passed

# 3. Open the analysis doc + this checklist
code D:\Kaori System\docs\strategic\BUILD_WEEK_MULTI_TENANT_ANALYSIS.md
code D:\Kaori System\docs\sprint\BUILD_WEEK_NEXT_SESSION_CHECKLIST.md

# 4. Decide: Step 4.1 (upload upgrade) hay Step 4.4 (demo script first)?
#    Em đề xuất 4.1 trước vì UI work depends on it.
```

---

*End of resume checklist. Em (Kaori) đã lưu state đầy đủ. Lần tới anh chỉ cần mở file này + tiếp Step 4.1.*
