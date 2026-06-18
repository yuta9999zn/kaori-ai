# PROJECT STATUS — 2026-05-20 rev 3 (Phase 2.8 UX redesign in progress)

> **rev 3 cùng ngày** với rev 1 (sáng — BA sync) và rev 2 (EOD — Excel v4.2).
> rev 3 ghi checkpoint **trước** khi tiếp tục Phase 2.8 UX redesign queue còn lại.
> Quy ước: KHÔNG sửa rev 1, rev 2; rev 3 chỉ ghi delta + plan tiếp theo.

---

## 0. Delta so với rev 2

| Trục | rev 2 (EOD trước) | rev 3 (sau Phase 2.8 commit 1+2+3) | Δ |
|---|---|---|---|
| Phase code | 3.8.1 (governance wired) | **3.9.0 (Industry Bootstrap + UX redesign)** | +0.1 minor |
| Branch commits ahead `main` | ~221 | **~225** | +4 |
| BE files mới | — | Mig 101+102+103 + router industry_bootstrap (10 endpoint) + 14 tests + ADR-0026 | Phase 2.8 BE done |
| UX docs files mới/updated | — | `workflow-builder-ux.html` mới + `feature-screens.html` 6 màn + 2 NEW | 2.8 UX 8/11 màn |
| ai-orch tests | 2355 | **2369** | +14 |

---

## 1. Phase 2.8 BE — DONE (commit `49748f9`)

| D-piece | Status | Ref |
|---|---|---|
| D1 Mig 101 industry catalog (6 bảng + view) | ✅ | `infrastructure/postgres/migrations/101_industry_templates.sql` |
| D2 Mig 102 customer versioning (5 bảng + view) | ✅ | `102_customer_workflow_versioning.sql` |
| D3 Mig 103 seed Retail/Finance/Generic SME | ✅ | `103_industry_templates_seed.sql` |
| D4 Router industry_bootstrap.py 10 endpoint | ✅ | `services/ai-orchestrator/routers/industry_bootstrap.py` |
| D5 Tests 14/14 pass + ADR-0026 | ✅ | `tests/test_industry_bootstrap_router.py` + `docs/adr/0026-…` |
| D6 CLAUDE.md §14 Phase 2.8 row + version 3.9.0 | ✅ | `CLAUDE.md` |
| D7 BA mirror docs/ba/ resync | ⏳ | defer next commit |

**Defer Phase 3** (theo ADR-0026): 5 industry còn lại (F&B / Logistics / Healthcare / Manufacturing / Education) — trigger seed = customer thật ký.

---

## 2. Phase 2.8 UX redesign — IN PROGRESS

### 2.1 Done — 8 of 11 màn (commit `4fc1bc4` + `136df49`)

| # | Màn | Cập nhật chính |
|---|---|---|
| 1 | **P2-02 Onboarding Wizard** | 5-step → **7-step Industry-first** (Chọn ngành → Preview → Phòng ban → Workflow → Users → Data → Confirm) |
| 2 | **P2-03 Enterprise Dashboard** | Thêm **Today Queue action-first** ở top (3 approvals + 2 wf failures + 5 docs + 1 insight) |
| 3 | **P2-04 Organization** | **3-view toggle** Department Cards (DEFAULT cho SME) / Org Tree / Cross-WF |
| 4 | **P2-11 Upload** | **2-mode**: Quick Inbox / Workflow Step Upload + Mode 3 legacy wizard. Required doc checklist gating cho Mode 2. |
| 5 | **P2-15 Results** | **Workflow Context Header** không ẩn được + What-changed diff + Lineage walk (mig 097) + Action right rail prioritized |
| 6 | **P2-26 Workflow Builder** | **3-mode**: Simple (card stack, không canvas) / Advanced (Branch Inspector) / Developer (canvas + YAML + K-17 visible) |
| 7 | **NEW P2-31 Industry Template Library** | `/p2/templates/industries` — 3 seeded + 5 "Sắp có" |
| 8 | **NEW P2-32 Bootstrap Preview** | `/p2/onboarding/bootstrap-preview` — 4 panel preview trước confirm |

NEW file:
- **`docs/sprint/workflow-builder-ux.html`** — Interactive 5-step wizard mockup (~600 dòng pure HTML + vanilla JS) demonstrate card format chuẩn anh chốt (Owner / Input / Required docs / AI action / Branch / Output / SLA). FE component reference khi FE restructure resume.

### 2.2 Queue còn lại — 3 màn + 1 IA restructure

| # | Item | Plan |
|---|---|---|
| 9  | **P2-20 Insight Detail** | Drilldown từ P2-15 / P2-19. Lineage trace + alternative interpretations + comparison run + citation deep links + action attachment. Full states. |
| 10 | **P2-27 Workflow Testing** | Test mode + step-through debugger + A/B parallel-run + 90-day comparison + promote winner. 6 states. |
| 11 | **P2-28 Process Mining** | "Discover My Workflows" 8 sources + privacy redact + heuristic miner + findings + translate-to-builder. SME mode vs analyst mode. |
| 12 | **Navigation IA split** | Tách Business (Workflows / Data / Insights / Reports / Admin) vs Platform/Internal (AI Decision Log / Observability / DLQ / MCP / Guardrails). Ẩn technical screens khỏi customer top nav. |

### 2.3 Đánh giá vs anh's review

| Tiêu chí | rev 2 (theo anh) | Hiện tại (rev 3) | Mục tiêu |
|---|---|---|---|
| Coverage màn hình | 8.5/10 | **~9/10** (72 screens, 2 NEW) | 9.5/10 |
| Logic sản phẩm tổng thể | 8/10 | **~8.5/10** (Industry tier BE + spec UX) | 9/10 |
| UX cho SME | 6/10 | **~7.5/10** (8 màn priority redesigned) | 9/10 (sau queue) |
| Sẵn sàng dev FE | 6.5/10 | **~8/10** (mockup live + spec đủ states) | 9/10 (sau queue + FE restructure) |

---

## 3. Files được tạo/sửa session 2026-05-20 (cumulative)

```
D:\Kaori System\
├── infrastructure/postgres/migrations/
│   ├── 101_industry_templates.sql                     ⭐ NEW
│   ├── 102_customer_workflow_versioning.sql           ⭐ NEW
│   └── 103_industry_templates_seed.sql                ⭐ NEW
├── services/ai-orchestrator/
│   ├── routers/industry_bootstrap.py                  ⭐ NEW (10 endpoint)
│   ├── tests/test_industry_bootstrap_router.py        ⭐ NEW (14 tests)
│   └── main.py                                        (registered router)
├── docs/adr/
│   └── 0026-industry-template-3-tier-bootstrap.md     ⭐ NEW
├── docs/sprint/
│   ├── workflow-builder-ux.html                       ⭐ NEW (SME mockup)
│   ├── feature-screens.html                           (8 màn redesigned)
│   └── feature-workflows.html                         (A.10 + glossary)
├── docs/ba/
│   ├── 4.2_Change_Request_Register.md                 (CR-0008 IMPLEMENTED)
│   └── (21 file BA mirror từ commit f2dc205)
└── CLAUDE.md                                          (3.8.1 → 3.9.0)

D:\Tài liệu dự án\
├── PROJECT_STATUS_2026-05-20.md         (rev 1 — sáng — BA sync)
├── PROJECT_STATUS_2026-05-20-rev2.md    (rev 2 — EOD trước — Excel v4.2)
├── PROJECT_STATUS_2026-05-20-rev3.md    ← file này (rev 3 — Phase 2.8 UX)
├── Kaori_AI_Feature_Tree_v4_2.xlsx      (baseline current)
└── (10 BA file khác)
```

---

## 4. Commit history session

```
136df49  docs(2.8): UX redesign P2-11 Upload 2-mode + P2-15 Results context-aware
4fc1bc4  docs(2.8): UX spec — workflow-builder-ux.html mockup + feature-screens 11-point redesign
49748f9  feat(2.8): Industry Template 3-tier Bootstrap — anh's "rõ vật thể" UX redesign
f2dc205  docs(ba): mirror BA folder snapshot 2026-05-20 (PROJECT_STATUS + Excel v4.2)
cef012a  feat(f5): Memory L3 via Redis Streams producer + drain (gated, default OFF)  ← origin baseline
```

Branch `feat/p15-s9-d1` đã push tới `136df49`, sync với origin.

---

## 5. Hành động kế tiếp (sau khi save rev 3)

1. **Update P2-20 Insight Detail** — drilldown structure + alternative + lineage.
2. **Update P2-27 Workflow Testing** — debugger + A/B + promote.
3. **Update P2-28 Process Mining** — SME mode vs analyst mode.
4. **Navigation IA split section** — Business vs Platform/Internal IA in feature-screens.html.
5. Commit + push.

Sau khi xong queue 4 items → Phase 2.8 UX redesign close. Rev 4 sẽ ghi final scoring.

---

*— Hết PROJECT STATUS 2026-05-20 rev 3 —*
