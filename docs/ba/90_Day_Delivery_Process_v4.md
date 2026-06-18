# QUY TRÌNH TRIỂN KHAI 90 NGÀY — v4.0 (Viết lại)
## Kaori AI — Enterprise 90-Day Deployment Process

| Hạng mục | Thông tin |
|---|---|
| Tài liệu | 90-Day Delivery Process (rewrite) |
| Phiên bản | 4.0 — căn chỉnh Feature Tree v4.0 (Process Mining · Adoption Intelligence · NOV) |
| Thay thế | 90-Day Playbook v3.0 |
| Ngày | Tháng 05/2026 |
| Audience | CSM · Implementation Engineer · Sales AE · Product · Customer sponsor + project lead |
| Nguồn | Feature Tree v4.0 (Journeys A–F), Playbook v3.0 (kế thừa triết lý), BA Docs Folder 01–02 |

---

## 0. Thay đổi cốt lõi so với v3.0

| Khía cạnh | v3.0 (cũ) | v4.0 (mới) |
|---|---|---|
| Khám phá workflow | CSM workshop map thủ công (D31–45) | **Process Mining tự discover từ event log** (Postgres/Excel/Zalo/Gmail) ngay Phase 1 |
| Ngôn ngữ ROI | revenue_at_risk / is_actioned | **NOV = revenue − cost (VND)** + time-to-payback |
| CSM intervention | Health score 5 sub-score thủ công | **9 tín hiệu Adoption Intelligence** tự động + intervention playbook |
| Cấu trúc phase | 4 phase nội bộ trong 90 ngày | Bám 4 phase sản phẩm: P1 (4mo) · **P1.5 stabilization** · P2 · P3 |
| Workflow authoring | Giả định kéo-thả được sớm | Phase 1 = review DRAFT do mining sinh; **drag-drop authoring đầy đủ là Phase 2** |
| Cơ cấu tổ chức đa cấp | Mặc định "tạo phòng ban" | **Phẳng 1 cấp (AS-IS)**; đa cấp tập đoàn = **GAP-01**, không hứa trong 90 ngày |

Triết lý giữ nguyên: **Comprehensive visibility, incremental change** — quan sát toàn diện, thay đổi từng bước. Wedge canonical theo ngành. Segment theo 5 archetype.

---

## 1. Bốn giai đoạn 90 ngày (ánh xạ Journey v4.0)

| Giai đoạn | Tuần | Mục tiêu | Journey v4.0 | Health state |
|---|---|---|---|---|
| FOUNDATION | W1 | Workspace + member + first upload + Bronze alive | A | ONBOARDING → ACTIVATING |
| ACTIVATION | W2–4 | Pipeline E2E + first insight 3-tuyến + first NOV signal | B | ACTIVATING → PROVING |
| DISCOVERY & PROVE | W5–8 | **Process Mining discover workflow thật** + NOV review + Adoption baseline | C, E | PROVING → EXPANDING |
| HANDOVER | W9–12 | Workflow DRAFT vào parallel test + Studio (per archetype) + QBR | F, D | EXPANDING → HEALTHY |

---

## 2. PRE-LAUNCH (D-7 → D0)

### 2.1 Sales → CSM Handoff
Bàn giao: profile khách, pain points, plan, **archetype (1–5)**, **wedge canonical theo ngành**, nguồn dữ liệu (POS/ERP/CRM/Excel + **có Postgres/Zalo/Gmail cho Process Mining không?**), data residency, executive sponsor.

### 2.2 Discovery Questionnaire (gửi trước D1)
Bổ sung so với v3.0:
- **Nguồn event log cho Process Mining:** có DB Postgres? dùng Zalo Business/Gmail cho quy trình duyệt? → quyết định 4 connector Phase 1 nào bật.
- **Consent:** ai ký consent mining nguồn chat/email (cần cho BR-6).
- **Cấu trúc tổ chức:** đơn thể hay tập đoàn nhiều công ty con? → nếu đa cấp, **set kỳ vọng GAP-01 ngay** (xem §6).

### 2.3 Archetype → timeline điều chỉnh
| Archetype | Foundation | Activation | Discovery | Handover/Studio |
|---|---|---|---|---|
| 1 Chaotic SME | D1–14 | D15–45 | D46–75 | Studio defer Q2 |
| 2 Ops-Driven | D1–7 | D8–30 | D31–60 | Studio D60+ |
| 3 Data-Curious | D1–7 | D8–30 | D31–60 | Studio D30–45 |
| 4 Enterprise | D1–5 | D6–21 | D22–50 | Studio D14 |
| 5 Regulated | D1–21 (legal) | D22–45 (sandbox) | D46–75 (approval-heavy) | Studio D76+ post-audit |

---

## 3. FOUNDATION — Week 1 (D1–7) · Journey A

| Ngày | Hành động | Gate |
|---|---|---|
| D1 | Platform Admin tạo workspace + key KAORI-XXXX → email + SMS/Zalo. Onboarding call 60' (dashboard, wizard demo, **wedge brief**, set kỳ vọng 90 ngày + ranh giới AS-IS/GAP) | M1: khách login, đổi mật khẩu, branding, member list confirm |
| D2–3 | Khai báo company; mời member; gán role (multi-role, ≥1 MANAGER). **Department = danh sách phẳng** (AS-IS) — không hứa cây đa cấp | M2: ≥1 dept + ≥1 user/dept |
| D4–5 | Upload đầu tiên qua Pipeline Wizard Step 1 (CSV/Excel UTF-8). Bật connector Process Mining nếu có (Postgres CDC/Excel/Zalo/Gmail) | M3: ≥1 file Bronze, schema detected |
| D6–7 | Data Quality Scorecard; khách accept hoặc apply cleaning rules | M4: quality ≥60, Bronze usable → **ACTIVATING** |

---

## 4. ACTIVATION — Week 2–4 (D8–30) · Journey B

| Ngày | Hành động | Gate |
|---|---|---|
| D8–14 | Silver layer: AI gợi ý cleaning rules tiếng Việt, khách duyệt từng luật + preview Before/After | M5: Silver ≥80% pass, schema versioned |
| D15–21 | Gold layer (views, refresh daily); Insights Engine 3-tuyến tự sinh per dept; Frameworks (SWOT tối thiểu) | M6: ≥1 insight/dept confidence ≥0.6; wedge dept ≥3 insight actionable |
| D22–30 | Reports tự động per dept; **NOV Engine: revenue Pre/Post baseline bắt đầu chạy**; push "first action" trên insight | M7: ≥1 report/dept; ≥1 action; ≥1 insight thumbs-up → **PROVING** |

> Khác v3.0: thay vì chỉ đếm "Đã xử lý", v4.0 bắt đầu **NOV baseline** ngay D22 để 30 ngày sau có số VND so sánh được.

---

## 5. DISCOVERY & PROVE — Week 5–8 (D31–60) · Journey C + E

### 5.1 D31–45 — Process Mining: discover workflow thật (thay map thủ công)
- Khách bấm "Discover My Workflows" → chọn nguồn + time range + dept (US-C1).
- PII tiếng Việt redact → role trước mining (US-C2); consent gate nguồn chat/email.
- Heuristic miner chạy → process model + bottleneck + shadow/bypass (US-C3).
- "Translate to Builder" → workflow DRAFT cho wedge workflow (US-C4).

> **Comprehensive visibility = mining toàn bộ; incremental change = chỉ DRAFT 1 wedge workflow.**
> Gate M8: ≥1 process model khai phá; wedge workflow có DRAFT; mỗi workflow có owner + risk class.

### 5.2 D46–60 — NOV Review + Adoption baseline
- **NOV Engine** tính revenue − cost theo workflow (VND); time-to-payback (US-E2, E3).
- **Adoption Intelligence**: thiết lập baseline 9 tín hiệu (8 signal Phase 1 + signal 9 Phase 1.5); composite health score per workflow/dept.
- **Mid-cycle Review D60** (90'): health + NOV thực tế vs dự báo + findings Process Mining + quyết định DRAFT nào vào parallel test.
- Gate M9+M10: ≥1 NOV dương hoặc payback path rõ; review ký off; ≥1 DRAFT duyệt cho parallel test → **EXPANDING**.

---

## 6. HANDOVER — Week 9–12 (D61–90) · Journey F + D

### 6.1 D61–75 — Parallel Test 90 ngày (hạ tầng Phase 1.5)
- Workflow DRAFT → REVIEWING → **TESTING song song ACTIVE_BASELINE** (traffic split theo plan).
- So sánh A/B; auto-rollback nếu nhánh mới tệ hơn >20%.
- CSM theo dõi **9 tín hiệu Adoption**: trigger AT_RISK tự động → chọn intervention playbook → đo effectiveness (Journey D).
- Gate M11: ≥1 workflow parallel; significance test chạy; auto-rollback cấu hình.

### 6.2 D76–89 — Studio Activation (per archetype)
Theo Feature Tree v4.0: Studio cho power user (visual workflow builder đầy đủ là Phase 2). Timing: Enterprise D14, Data-Curious D30–45, Mid-market D60+, Chaotic SME Q2, Regulated post-audit.

### 6.3 D90 — Final Review & Handover
- Báo cáo 90 ngày tự động (PDF): health journey, insights, **NOV realized (VND)**, workflows discovered/tested, adoption score.
- Handover decision matrix theo health + NOV; QBR cadence; kế hoạch wedge tiếp theo.
- Gate M12: review xong; báo cáo bàn giao; kế hoạch 90 ngày tiếp ký off → **HEALTHY**.

---

## 7. Xử lý kịch bản "tập đoàn đa cấp" (GAP) trong 90 ngày

Nếu khách là tập đoàn nhiều công ty con (vd Vingroup) và muốn kéo-thả sơ đồ phả hệ + card đính tài liệu:

1. **D-7 set kỳ vọng đúng:** 90 ngày v4.0 hỗ trợ **danh sách phòng ban phẳng** + Process Mining discover workflow + pipeline dữ liệu giao dịch. **KHÔNG** hứa Org Hierarchy Modeler đa cấp / workflow card document library — đây là GAP-01/02/03.
2. **Workaround Phase 1 hợp lệ:** mô hình hoá mỗi công ty con / mảng lớn thành **workspace hoặc department riêng** với sensitivity tag; dùng "Organization chart" (chart type 2.14) để *hiển thị* sơ đồ từ dữ liệu — không phải canvas tương tác.
3. **Mở Change Request:** GAP-01/02/03 vào pipeline sản phẩm (đề xuất Phase 2). Use Case "to-be" đặc tả ở SRS (Folder 03) để khi build xong, happy case "làm được".
4. **Không trượt timeline:** GAP không nằm trong 90 ngày → tách thành "Quarter 2+ roadmap" trong Wedge Brief.

---

## 8. 12 Milestone Gates (tóm tắt)

| M | Day | Gate | Owner |
|---|---|---|---|
| M1 | D1 | Workspace + key + login | CSM |
| M2 | D3 | ≥1 dept + user/dept | CSM |
| M3 | D5 | ≥1 file Bronze + schema | Customer+CSM |
| M4 | D7 | Quality ≥60 → ACTIVATING | Impl Eng |
| M5 | D14 | Silver ≥80% pass | Impl Eng |
| M6 | D21 | ≥1 insight 3-tuyến conf ≥0.6 | AI System |
| M7 | D30 | ≥1 action + NOV baseline → PROVING | Customer+CSM |
| M8 | D45 | ≥1 process model discovered + DRAFT wedge | Customer+CSM |
| M9 | D60 | NOV dương / payback path + DRAFT duyệt | AI System |
| M10 | D60 | Mid-cycle review ký off | CSM+AE |
| M11 | D75 | Workflow parallel test live | Impl+Customer |
| M12 | D90 | QBR + kế hoạch 90 ngày tiếp → HEALTHY | CSM+Sales |

---

## 9. Anti-patterns (cập nhật v4.0)

- ❌ Hứa kéo-thả workflow đầy đủ ở Phase 1 — đó là Phase 2; Phase 1 là Process Mining discover.
- ❌ Hứa cây tổ chức tập đoàn đa cấp trong 90 ngày — GAP-01, cần Change Request.
- ❌ Map workflow thủ công bằng workshop dài — để Process Mining làm, CSM chỉ validate.
- ❌ Nói ROI mơ hồ — luôn dùng **NOV bằng VND** + time-to-payback.
- ❌ Bỏ qua 9 tín hiệu Adoption — đây là cảnh báo sớm tự động, không chờ khách than.
- ❌ Đẩy ENT MAX cho Archetype 1 — cost-to-serve vượt doanh thu.
- ❌ Thay workflow cũ ngay — luôn parallel ACTIVE_BASELINE trước khi promote.

---

## 10. Định nghĩa thành công 90 ngày

Sau 90 ngày khách có 3 thay đổi căn bản: (1) habit: từ "report 2 tuần" → "dashboard mỗi sáng"; (2) decision style: từ "cảm tính" → "cảm tính + data + NOV"; (3) capability: từ "phụ thuộc Kaori" → "self-service". Đo bằng: health state HEALTHY, **NOV dương hoặc payback path rõ**, ≥1 workflow discovered + parallel-tested, adoption score ≥ HEALTHY.

> Iterate sau mỗi 5 khách onboarding — đo cái gì hiệu quả, refine. Special domain (Bank/Healthcare/Government) cần supplement riêng (kế thừa Playbook v3.0 Phần 14).

---

*— Hết Quy trình 90 ngày v4.0 —*
