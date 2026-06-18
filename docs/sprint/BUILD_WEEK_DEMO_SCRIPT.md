# Build Week Demo Script — Kaori AI Enterprise OS (Vingroup-class pitch)

> **Updated:** 2026-05-15 (Tuần 3 rewrite — enterprise positioning, không phải SME)
> **Target run-time:** 9-11 phút (Demo Day 12/7 slot)
> **Audience:** Engineers từ NVIDIA + AWS, decision-makers từ Tasco + Phong Vu, GenAI Fund judges
> **Track:** Enterprise AI → **Enterprise Workflows** (or Retail/Manufacturing — alignable per brief)
> **Backup video:** record cuối Tuần 7 (3-4/7), play if live fail

---

## Định vị 1 câu

> "Kaori AI là **Enterprise Workflow OS** cho tập đoàn Việt Nam quản lý nhiều công ty con. Hôm nay em demo với Vingroup-class data: 1 tập đoàn × 8 mảng × 16 công ty con × 96 phòng ban — tất cả trong 1 platform. SQL-first reasoning + CDFL planning (port từ luận văn nhị nguyên giao thoa nhất nguyên 2 trường) làm differentiator."

---

## 5 differentiator (mỗi cái 1 demo moment)

| # | Differentiator | Đối thủ 2000 builder khác có không? | Demo moment |
|---|---|---|---|
| 1 | **Multi-level corporate hierarchy** (Tập đoàn → Mảng → Công ty con → Chi nhánh → Phòng ban) | ❌ Hầu hết build cho 1 enterprise đơn lẻ | Phần 2 (~90s) |
| 2 | **Cross-workflow link giữa các công ty con** với cross-dimension badges | ❌ Concept này không có trong workflow framework nào commodity | Phần 4 (~75s) |
| 3 | **SQL-first KPI reasoning** với industry benchmark percentile | ❌ Most demos LLM-compute KPI = ảo giác | Phần 5 (~90s) |
| 4 | **CDFL plan-next-action** (luận văn anh, balance explore/exploit AI reasoning) | ❌ UNIQUE, không có hệ thống nào có | Phần 6 (~90s) |
| 5 | **Medallion strict 3-layer** + lineage capture (Bronze→Silver→Gold) | ⚠️ Một số có lakehouse architecture nhưng không strict separation | Phần 3 (~60s) |

Tổng 5 demo moment = ~7 phút. Phần opening + closing = ~2 phút. Buffer Q&A = ~1-2 phút.

---

## Setup checklist (làm 30 phút trước demo)

### Mở terminal 1 — Docker stack

```powershell
docker compose up -d postgres redis kafka zookeeper ollama
sleep 30   # wait healthchecks
docker compose up -d auth-service notification-service data-pipeline ai-orchestrator api-gateway
```

Verify all services healthy:
```powershell
docker compose ps | findstr "healthy"
# Expect: postgres, redis, kafka, ollama healthy
```

### Mở terminal 2 — DB seed nếu fresh

```powershell
# Vingroup demo data (mig 056 — idempotent)
# Đã apply tự động khi postgres init fresh
# Verify: 25 tree nodes
docker exec kaorisystem-postgres-1 psql -U kaori -d kaori -c "SELECT COUNT(*) FROM v_corporate_tree;"
# Expect: 25

# Olist data nếu cần
$env:DATABASE_URL = "postgresql://kaori:kaori_dev_password@localhost:5432/kaori"
python scripts/seed_olist_into_kaori.py --real --sample-rows 1000

# Demo user (vingroup MANAGER under Vinhomes)
# password bcrypt hash đã seed (xem mig 056 + Tuần 1 patch)
```

### Mở terminal 3 — FE dev

```powershell
cd frontend
npm run dev
# wait "Ready in ..." message
```

### Smoke test (cuối — anh phải confirm pass)

```bash
bash scripts/smoke_test_build_week.sh
# Expect: SMOKE PASS: 19 / 19
```

### Browser tab pre-load

| Tab | URL | Mục đích |
|---|---|---|
| 1 | `http://localhost:3000/login` | Login screen |
| 2 | `http://localhost:3000/p2/org-tree` | Main demo entry |
| 3 | `http://localhost:3000/p2/workflows` | Workflow hub |
| 4 (backup) | `http://localhost:3000/p2/dashboard/overview` | Fallback if main flow fails |
| 5 (curl) | Terminal mở sẵn JWT export + curl examples | If FE fail, demo qua API |

---

## Script (9-11 phút)

### 🎬 Phần 1 — Opening (60s)

> **Slide 1 (title):**
>
> "Kính chào hội đồng. Em là Yuta Kun. Hôm nay em present Kaori AI — Enterprise Workflow OS cho tập đoàn Việt Nam.
>
> Mỗi tập đoàn lớn ở Việt Nam — Vingroup, FPT, Vinamilk, Hòa Phát — đều có cùng bài toán: 1 holding với 10-30 công ty con, mỗi cty con có Sales/Marketing/Finance/HR/Kho/CSKH, workflows chồng chéo, dữ liệu phân tán.
>
> Kaori AI cho HQ 1 OS để quản lý hết: kéo thả cơ cấu, kéo thả workflow, upload tài liệu, AI tự lý luận. Em demo với data của Vingroup theo Corporate Profile 2018 — 8 mảng kinh doanh, 16 công ty con."

### 🏢 Phần 2 — Multi-level corporate hierarchy (90s) ⭐

> **Switch sang Tab 2: `/p2/org-tree`.**
>
> "Đây là cây tổ chức Vingroup. Cấp 1 là Tập đoàn. Cấp 2 là 8 mảng kinh doanh — BĐS, Du lịch, Bán lẻ, Công nghiệp, Y tế, Giáo dục, Nông nghiệp, Công nghệ. Cấp 3 là 16 công ty con — Vinhomes, VinMart, VinFast, Vinmec, VinSchool, VinAI, …
>
> Đa số platform commodity chỉ có 1 cấp 'enterprise'. Kaori có recursive parent_enterprise_id nên hỗ trợ N cấp — VinFast Auto có thể là sub-subsidiary của VinFast trong cùng cấu trúc."
>
> **Click vào VinMart trong tree → right panel hiện 1 chi nhánh + 6 phòng ban.**
>
> "Click vào VinMart — hiện chi nhánh và 6 phòng ban. Nhấn 'Di chuyển' — em re-parent VinMart từ mảng Bán lẻ sang mảng Công nghệ. PUT /enterprises/{id}/parent với cycle detection 16 cấp."
>
> **Demo move thực tế. Reload tree — VinMart giờ dưới Công nghệ.**
>
> "Đây là live HQ restructure. Tập đoàn không cần ngừng hoạt động khi đổi org chart."

### 📊 Phần 3 — Medallion strict 3-layer + lineage (60s)

> **Switch terminal — query SQL:**
>
> ```sql
> SELECT 'Bronze' AS layer, COUNT(*) FROM bronze_rows
> UNION ALL SELECT 'Silver', COUNT(*) FROM silver_customers
> UNION ALL SELECT 'Gold', (SELECT row_count FROM gold.customer_360_marketing LIMIT 1);
> ```
>
> "Mỗi lớp 1 trách nhiệm — Bronze raw immutable, Silver typed cleaned, Gold view aggregated. Anh chốt nguyên tắc 'không chồng chéo' 2 tuần trước. Mig 051 + 052 ship strict separation. Test pháp gắn: 41 shape test hard-fail bất kỳ Gold view nào touch Bronze hoặc dùng JSONB operator."
>
> **Mở `/p2/data/bronze` → `/p2/data/silver` → `/p2/data/gold` để show 3 layer.**
>
> "Lineage edge bắt từ pipeline run — sau này anh có thể trace từ KPI Gold ngược về Bronze file gốc upload bởi user nào."

### 🔗 Phần 4 — Cross-workflow link giữa các công ty con (75s) ⭐

> **Switch sang `/p2/workflows`. Click "Từ template" → pick "Lead Qualification Workflow" → clone vào VinMart Sales.**
>
> "5 cards tự sinh: Lead intake → BANT scoring → SQL/MQL split → Sales rep handoff → Conversion track. Mỗi card có note, hashtag, required document types."
>
> **Mở workflow detail tab Builder → click card 1.**
>
> "Đây là Builder. Click card → edit drawer phải. Em đổi node_type 'step' sang 'decision_if_else' — condition input xuất hiện. Phase 2 runtime sẽ evaluate; Phase 1 lưu metadata cho audit."
>
> **Switch tab 'Cây tài liệu'.**
>
> "Còn cái này — workflow VinMart Reorder Trigger trigger workflow VinEco Production. 2 công ty khác mảng. Badges 'khác cty' + 'khác mảng' tự nhận diện via v_workflow_cross_links_enriched view."
>
> **Point at badges trong UI.**
>
> "Đây là feature differentiator. Trong Camunda/Zeebe không có concept này — cross-process link tách biệt khỏi xet process flow. Vingroup-class scenario: VinMart hết hàng → tự trigger VinEco tăng sản xuất → tự trigger logistics tăng chuyển hàng."

### 📈 Phần 5 — SQL-first KPI + industry benchmark percentile (90s) ⭐

> **Tab 'Báo cáo' của workflow.**
>
> "4 stat tile: tổng bước, mũi tên, folder, file. Đây là static stats. Quan trọng là phía dưới — KPI recent của phòng ban."
>
> **Show KPI list — CAC/LTV/ROAS cho Marketing dept.**
>
> "30 KPI canonical seed trong mig 049. Mỗi KPI có formula_sql, target_gold_view, threshold_good/warning, **industry_benchmarks percentile**.
>
> Em chốt anh nguyên tắc 'SQL-first reasoning, LLM chỉ render'. Pipeline:
> 1. Postgres compute formula_sql → raw_value (deterministic, audit-able)
> 2. classify(raw_value, threshold) → good/warning/critical
> 3. lookup_percentile(value, industry_benchmarks) → 'tier P40 của Vietnam Retail SME 2022'
> 4. LLM render Vietnamese narrative
>
> LLM không tự compute KPI. Không có hallucination về số. Mỗi quyết định business audit-able."
>
> **Open terminal — show curl:**
>
> ```bash
> curl -H "Authorization: Bearer $JWT" \
>   http://localhost:8080/api/v1/economics/nov/current
> # Returns: {nov_vnd: 20000000, classification: positive, percentile: P55}
> ```

### 🧠 Phần 6 — CDFL plan-next-action (90s) ⭐⭐⭐ (DIFFERENTIATOR LỚN NHẤT)

> **Mở slide CDFL theory (slide 7-8).**
>
> "Đây là phần em proud nhất. CDFL = Curiosity-Driven Foraging Logic. Port từ luận văn cao học của em — 'Nhị nguyên giao thoa nhất nguyên 2 trường' về AI reasoning.
>
> Vấn đề: AI agent thông thường mắc kẹt giữa **exploit** (chọn action có expected reward cao) vs **explore** (thử action novel chưa biết). Hệ thống commodity không balance được — agent chỉ làm 1 trong 2.
>
> CDFL formalize via Information Gain — chọn action maximize { expected_reward × confidence_high } OR { novelty × information_gain_potential }. Bayes-update sau mỗi action."
>
> **Switch terminal — curl /cdfl/plan-next-action:**
>
> ```bash
> curl -X POST http://localhost:8080/api/v1/cdfl/plan-next-action \
>   -H "Authorization: Bearer $JWT" \
>   -d '{"current_state": "vingroup_q1_review", "candidate_actions": [...]}'
> ```
>
> "Return: top-3 actions với IG score. VinMart manager thấy 'campaign style X đã thử 47 lần, tier P25 — KHÔNG novel; campaign style Y mới 0/47, IG cao — recommend explore'. AI suggest hành động chưa từng làm có thông tin giá trị cao nhất.
>
> Code em ship `reasoning/cdfl/` Tuần 1-6 prep — port code Python từ thesis. Đối thủ 2000 builder không ai có thuật toán này — đây là moat differentiator."

### 🚀 Phần 7 — Closing + Deployment posture (90s)

> **Slide 10-12 — Roadmap + Deployment.**
>
> "Phase 1 hôm nay = Workflow Definition + Document Organizer + KPI engine + CDFL reasoning + cross-link metadata.
>
> Phase 2 (Q4-2026): Temporal worker execution engine — workflow chạy thực sự (timer/event/saga/compensation). Em đã có K-17 side_effect_class invariant + REL-012 compensation YAML từ Tuần 5.
>
> Phase 3 (Q1-2027): Knowledge Graph layer (Apache AGE on Postgres → Neo4j scale-out) + multi-aspect entity (1 canonical customer × 16 enterprise views).
>
> Deployment ready hôm nay:
> - Multi-tenant RLS K-1 + ABAC dept-scope (mig 047/059)
> - Audit log decision_audit_log + cross_tenant_attempts
> - Idempotency K-13 + workflow approval mig 042
> - SOC 2 posture: 80% coverage cho Type 1 audit
>
> Em sẵn sàng cho câu hỏi của hội đồng."

---

## Q&A — 10 câu hỏi chuẩn bị trước

| # | Câu hỏi từ judges | Câu trả lời gói gọn |
|---|---|---|
| 1 | "Workflow này có chạy được không?" | Phase 1 = static digital twin (organizer). Phase 2 với Temporal là execution engine. K-17 side_effect_class đã ép retry policy đúng từ Phase 1 schema. |
| 2 | "Tại sao chọn Vingroup làm demo?" | Vingroup Corporate Profile 2018 public — 8 mảng đầy đủ. Reproducible. Mig 056 seed idempotent cho mọi reviewer chạy local. |
| 3 | "Cross-link runtime sao chạy?" | Phase 1 metadata. Phase 2 Temporal worker subscribe Kafka kaori.workflow.completed → match cross_links target → fire trigger workflow. Spec docx PART V Phần 2. |
| 4 | "AI có ảo giác KPI không?" | KHÔNG. SQL-first. 30 KPI có formula_sql deterministic. Mig 049 + reasoning/kpi_engine/. LLM chỉ render narrative, không compute. |
| 5 | "Multi-tenant isolation?" | RLS K-1 hard rule. Mig 059 workspace-scoped cho corporate group. Cross_tenant_attempts table audit mọi lần thử leak. CI test 'isolation_workflow_*' check policies. |
| 6 | "CDFL khác Q-learning chuẩn thế nào?" | Q-learning maximize expected_reward. CDFL **adds Information Gain term** — agent prefer action có cao đóng góp future knowledge. Bayesian update after each. Port từ thesis chương 4. |
| 7 | "Drag-drop UX khi nào ship full?" | Phase 2 với React Flow. Build Week ship vertical chain + chevron up/down. Functionally equivalent cho demo. |
| 8 | "Process Mining đâu?" | Skeleton endpoint (Tuần 4 ngày 4). Auto-discovery Phase 2. Docx PART IV. |
| 9 | "Knowledge graph khi nào?" | Phase 3 Q1-2027. Apache AGE on existing Postgres trước (low ops cost), Neo4j khi cần scale-out. |
| 10 | "Pilot customer?" | Em mong hội đồng giới thiệu 1 tập đoàn Việt Nam có 5+ công ty con để pilot. Olist demo data sẵn sàng cho test enterprise tương đương. |

---

## Backup plan

| Lỗi | Workaround |
|---|---|
| FE dev server crash | Switch sang `next build && next start` đã chạy port 3001 trước demo |
| Postgres không lên | Pre-record video phần 2-7 (~7 phút), play |
| Login JWT expire | 2 user backup pre-prepared, switch ngay |
| API gateway 5xx | Curl trực tiếp port 8093 ai-orchestrator (bypass gateway) — demo qua terminal cũng impressive |
| LLM chậm (Qwen 14B local) | Pre-warm Ollama trước demo 10 phút + có cached response fallback sẵn |
| Câu hỏi vượt scope | "Câu này đúng là Phase 2/3 trong roadmap. Em ghi note để follow-up sau demo." — KHÔNG bịa đáp án |

---

## Pre-demo dry-run schedule

| Ngày | Việc | Owner |
|---|---|---|
| 2026-06-26 | Dry-run 1 — full flow, ghi note mọi lỗi | Em |
| 2026-06-27 | Fix lỗi + record backup video | Em |
| 2026-07-01 | Dry-run 2 — timing với đồng hồ; nhắm 9-10 phút | Em |
| 2026-07-03 | Dry-run 3 — audience test (1 senior dev hoặc 1 founder) | Em + reviewer |
| 2026-07-05 | Buffer day — fix bất kỳ lỗi nào còn lại | — |
| 2026-07-07 | Demo day prep | — |
| 2026-07-08 | **ENABLE Day 1 (workshop)** | GenAI Fund |
| 2026-07-11 | **BUILD Day 4** — hackathon kicks off | All |
| 2026-07-12 | **DEMO Day 5** — sáng 9h presentation slot | — |

---

## Slide deck structure (10-12 slide)

| # | Slide | Nội dung |
|---|---|---|
| 1 | Title | Kaori AI — Enterprise Workflow OS · Yuta Kun · Build Week 2026 |
| 2 | The problem | "10-30 công ty con × 6 phòng ban × N workflows — Vingroup hôm nay quản lý thế nào?" Pain points table |
| 3 | Approach | "1 OS. Multi-level org tree. Kéo thả workflow. AI lý luận." Architecture diagram L1-L7 (em vẽ ở Phần 8 review trước) |
| 4 | Medallion 3-layer | Bronze/Silver/Gold sơ đồ + đặc tính per layer + lineage edge |
| 5 | Workflow card model | Card với title/note/hashtags/required_docs + decision/approval types |
| 6 | Cross-workflow links | 5 cross-dimension flags illustration + Vingroup example |
| 7 | CDFL theory | Slide 1 — exploit vs explore tradeoff |
| 8 | CDFL formal | Slide 2 — IG formula + Bayesian update |
| 9 | SQL-first reasoning | Pipeline 4-step + 30 KPI seed + industry benchmark percentile |
| 10 | Compliance posture | Multi-tenant + audit + idempotency + SOC 2 80% |
| 11 | Roadmap | Phase 1 (today) → Phase 2 (Temporal) → Phase 3 (Knowledge Graph) timeline |
| 12 | Ask | "Pilot với 1 Vietnamese conglomerate — em đề xuất bridge conversation" |

Slide source format: Marp markdown → PDF export. Em commit slide source `docs/sprint/BUILD_WEEK_SLIDES.md` separately.

---

*End of demo script. Build Week scope locked — không add feature mới sau Tuần 4.*
