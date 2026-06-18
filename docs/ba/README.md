# Kaori AI — Bộ tài liệu BA v2.3 (Business Analyst Documentation)

**Bản v2.3** căn chỉnh sau realtime sync với code repo state 2026-05-21 EOD3. BA layer giờ fully aligned với 5 HTML siblings (4 sibling cũ + SA HTML v1.2) + FE Spec v1.1 + Glossary v1.2 + Feature Tree v4.1.

```
Kaori_BA_Documentation_v2/
├── 01_Business_Requirement/
│   ├── 1.1_MRD_Market_Requirements_Document.md           (giữ v1.0)
│   ├── 1.2_BRD_Business_Requirements_Document.md         ✅ v4.1 (+Phase 1.5, +EPIC-12/13/14, feature count 1.147)
│   ├── 1.3_Product_Vision.md                              ✅ v1.1 (+Pillar K/L/M, +Anti-Vision, +Trade-off, +Success Ladder)
│   └── 1.4_Business_Case_and_Scope.md                     ✅ v1.1 (NOV ROI + Phase entry/exit + RACI CR)
│
├── 02_Stakeholder_Requirement/
│   ├── 2.1_URD_User_Requirements_Document.md             ✅ v2.1 (G/W/T + UR-CS 5 US US-CS-1..5)
│   ├── 2.2_FRD_Functional_Requirements_Document.md       (giữ v1.0)
│   └── 2.3_PRD_Product_Requirements_Document.md           ✅ v6.1 (GAP status + Product Behavior 4 state)
│
├── 03_Solution_Requirement/
│   ├── 3.1_SRS_Software_Requirements_Specification.md    (giữ v1.0)
│   ├── 3.2_NFRS_Non_Functional_Requirements.md           ✅ v1.1 (§5.bis Permission Claims; +NFR-DQ-07/08 cite glossary §28-29)
│   ├── 3.4_API_Contract.md                                ✅ v0.2 (POINTER bump 169→187, +10 connector Process Mining)
│   ├── 3.7_System_Architecture_Pointer.md                ✅ v0.2 (POINTER → SA HTML v1.2; Tier 3 7/7 closed)
│
├── 04_Governance/
│   ├── 4.1_RACI_and_Delivery_Governance.md               ✅ v1.1 (fix typo 4.3→3.4, +Phase 1.5 cadence, +G8/G9)
│   └── 4.2_Change_Request_Register.md                     ✅ v2.3 (CR-0001..0015; CR-0014 Tier 3 closed sớm ⭐; +CR-0015 cross-link)
│
├── 05_Implementation_Specs/
│   └── PHASE_2_8_FE_IMPL_SPEC_v1.1.md                    ✅ v1.1 (77 màn, 5 CS screens P2-33..P2-37, Claims, WCAG, OpenTelemetry)
│
├── 90_Day_Delivery_Process_v4.md                         (giữ v4.0)
├── Kaori_AI_Feature_Tree_v4_1.xlsx                       (Excel v4.0 → v4.1 fixed)
├── REVIEW_NOTES_for_Code_Repo.md                         (7 nhóm fix dev cần làm)
└── README.md                                              (file này)
```

## 5 HTML siblings — realtime state 2026-05-21 EOD3

| Sibling | Version | Latest change | BA layer reference |
|---|---|---|---|
| `feature-screens.html` | **v2.8.2 Round 3** (stable) | 77 màn · 6 portals · BIL→P6 + SH→P5 + 5 CS screens | 3.3 Wireframes pointer; URD UR-CS US-CS-1..5 |
| `feature-workflows.html` | v2.8.1 Round 2 EOD3 (stable) | 40 workflows incl. Vertical D (CS) D.1-D.5 | feature-workflows trace tới URD UR-CS via 5 CS workflow |
| `workflow-builder-ux.html` | v2.0 Round 2 EOD3 (stable) | 3-mode Workflow Builder (Simple/Advanced/Developer) | FE Spec v1.1 P2-26 |
| `kaori-shared-glossary.html` | **v1.2 EOD3** ⭐ MỚI 33 sections | +§4 Phase Naming (Tier 3 #13) · v1.1 N10 +6 sections (8-Step Silver §28 + 7-dim Quality §29 + BIZ-ERR §30 + MCP JSON-RPC §31 + Governance scripts §32 + REVIEW_NOTES §33) | NFRS NFR-DQ-07/08 cite §28-29; 3.7 §4.bis map |
| `system-architecture.html` | **v1.2 EOD3** ⭐ Tier 3 closed | +Reading paths §1 · +3 sub-views §2 · +UAT col §12 · +CR Register link §12.1 | 3.7 SA Pointer v0.2 |

## Sibling references — code repo `D:\Kaori System\`

| Artefact | Vị trí | Quan hệ với BA |
|---|---|---|
| **SA HTML v1.2** ⭐ | `docs/sprint/system-architecture.html` | 3.7 pointer; 13 H2 section · 8 Mermaid diagram · EPIC + US-ID + NFR-SEC trace |
| `kaori-shared-glossary.html` v1.2 ⭐ | `docs/sprint/` | NFRS NFR-DQ-07/08 cite §28-29; 3.7 §4.bis |
| feature-screens / workflows / builder-ux v2.x | `docs/sprint/` | URD UR-CS, FE Spec v1.1 |
| `kaori-shared-tokens.css` | `docs/sprint/` | Design tokens chung cho 5 HTML (incl. SA) |
| `CLAUDE.md` v3.9.4 | repo root | Living architecture canonical |
| 27 ADRs | `docs/adr/` | Architecture decisions |

## Trạng thái batch update v1 → v2.3

| File | v1 | v2.3 | Thay đổi cốt lõi |
|---|---|---|---|
| 1.1 MRD | 1.0 | 1.0 | (không sửa) |
| **1.2 BRD** | 4.0 | **4.1** ⭐ EOD3 bumped | +Phase 1.5, +EPIC-12/13/14, +BO-7, +BR-13..16, +R13/R14, fix 986→**1.147** |
| 1.3 Product Vision | 1.0 | **1.1** | +Anti-Vision, +Trade-off, +MVP Wedge, +Success Ladder, +Pillar K/L/M |
| 1.4 Business Case + Scope | 1.0 | **1.1** | +NOV ROI worked example, +Phase entry/exit, +CR RACI, GAP status update |
| 2.1 URD | 1.0 | **2.1** | G/W/T + 4 negative scenarios; +UR-CS section (US-CS-1..5) |
| 2.2 FRD | 1.0 | 1.0 | (không sửa) |
| 2.3 PRD | 6.0 | **6.1** | §7 GAP status, +Product Behavior 4-state, Release Criteria 12 điểm |
| 3.1 SRS | 1.0 | 1.0 | (không sửa) |
| **3.2 NFRS** | 1.0 | **1.1** ⭐ EOD3 augmented | +§5.bis Permission Claims; **+NFR-DQ-07/08 cite glossary §28-29** |
| **3.4 API Contract** ⭐ NEW pointer | — | **v0.2** | POINTER bump 169→187; 10 connector Process Mining ship |
| **3.7 SA Pointer** ⭐ MỚI | — | **v0.2** | POINTER → SA HTML v1.2; Tier 3 7/7 closed table; §4.bis Glossary v1.2 expansion mapping |
| 4.1 RACI | 1.0 | **1.1** | Fix typo 4.3→3.4, +Phase 1.5 cadence, +G8/G9 |
| **4.2 CR Register** | 1.0 | **2.3** ⭐ EOD3 bumped | CR-0001..0015; **CR-0014 closed sớm hơn defer** ⭐ Pattern C ideal; +CR-0015 cross-link asymmetric |
| 90-Day Process | 4.0 | 4.0 | (không sửa) |
| Excel | 4.1 | 4.1 | (đã fix) |
| REVIEW_NOTES | — | 1.0 | (7 nhóm fix dev) |
| FE Impl Spec ⭐ | — | **v1.1** | 18 priority (11 + 2 NEW + 5 CS); Claims; WCAG; OpenTelemetry |

## Top findings reflected trong v2.3

1. **BA layer ↔ code repo drift** v2.0 — đã đồng bộ
2. **BRD thiếu 3 moat EPIC + Phase 1.5** v2.0 — đã thêm EPIC-12/13/14
3. **URD AC G/W/T missing** v2.1 — đã apply 24+ US
4. **GAP-01/02/03 status outdated** v2.0 — đã update
5. **CS vertical workflows orphan UI** v2.1 — 5 screen FE spec + 5 user story + 3 claim
6. **SA HTML missing BA pointer** v2.2 — đã tạo 3.7
7. **Tier 3 deferred but closed sớm** v2.3 ⭐ — pattern C ideal observed
8. **Glossary v1.0 → v1.2 + 7 new sections** v2.3 ⭐ — NFRS NFR-DQ-07/08 cite §28-29; API 187 bump
9. **Cross-link asymmetric SA HTML ↔ 4 siblings** v2.3 ⭐ — CR-0015 mới track

## Governance maturity progression

| Round | Pattern | Lesson |
|---|---|---|
| v2.0 | CR-0009/0010 IMPLEMENTED **post-facto** — không qua CR Board | Process tightening: PR phải gắn CR-#### |
| v2.1 | CR-0012 Permission Claims framework **post-facto formalize** | Concept mới phải reflect ngược BA cùng sprint |
| v2.2 | CR-0013 SA HTML — **submit + 3-tier review + plan Tier 3 defer** (Pattern B) | Pattern lý tưởng — replicate |
| **v2.3** ⭐ | CR-0014 — **submit + 3-tier review + close Tier 3 sớm hơn defer** (Pattern C) | **Maintainers chủ động → Tier 3 close cùng ngày. Defer sizing tương lai cân nhắc.** |

3 round → 3 pattern → 3 lesson. Phase 2.9 target Pattern C cho mọi CR LOW-MED.

## Việc tiếp theo (cho user thực thi HTML)

**Open CR cuối Phase 2.8:**
- **CR-0015 cross-link asymmetric** (LOW, ASSESSING) — 4 siblings → SA HTML link reverse. ~2.5 SP. User thực thi và gen lại HTML cho review.

**Pending HIGH/CRITICAL FE work:**
- CR-0001 GAP-01 FE Org Hierarchy canvas (BE shipped)
- CR-0003 GAP-03 FE Document Intelligence highlight UI (BE partial)
- CR-0006 Workflow Builder authoring full FE (~85 SP)
- CR-0011 CS vertical FE 5 screens (~150 SP, 3 sprint)

**Pending dev-side:** REVIEW_NOTES_for_Code_Repo.md — 7 nhóm fix (~2-3 tuần dev/QA/UX combined).

**BA layer:** sạch hoàn toàn cho Phase 2.8 closeout. Sẵn sàng baseline.

## Nguồn dữ liệu chính

BRD v3.0 Unified · PRD v5.0 · 90-Day Playbook v3.0 · **Feature Tree v4.1** (đã fix) · 5 HTML siblings tại code repo `D:\Kaori System\docs\sprint\` state 2026-05-21 EOD3 · CLAUDE.md v3.9.4 · 27 ADRs · branch `feat/p15-s9-d1` ~252 commits ahead main · ai-orchestrator 2128+ tests pass · 103 migrations.
