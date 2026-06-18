# PROJECT STATUS — 2026-05-20 rev 2 (EOD)

> **rev 2 cùng ngày** với `PROJECT_STATUS_2026-05-20.md` (rev 1, đầu session). rev 2 ghi delta sau khi đóng CR-0004 + CR-0005 (Excel v4.2 baseline).
> Snapshot kế tiếp sẽ là `PROJECT_STATUS_YYYY-MM-DD.md` khi quota CI reset (đầu June 2026) hoặc khi CR HIGH/CRITICAL kế đóng.
> Quy ước: KHÔNG sửa rev 1; rev 2 chỉ ghi **delta** so với rev 1.

---

## 0. Delta so với rev 1 (cùng ngày 2026-05-20)

| Trục | rev 1 (sáng) | rev 2 (EOD — hiện tại) | Δ |
|---|---|---|---|
| CR-0004 Excel phase mismatch | SUBMITTED | **IMPLEMENTED** | +Closed |
| CR-0005 Excel Owner trống | SUBMITTED | **IMPLEMENTED** | +Closed |
| CR-0006 BA baseline sync | IMPLEMENTED | IMPLEMENTED | (giữ) |
| CR-0007 Secret rotation | PENDING anh confirm | PENDING anh confirm | (chưa Δ) |
| CR-0001/0002/0003 (GAP-01/02/03) | PARTIAL | PARTIAL | (chưa Δ) |
| Excel baseline | v4.1 (lệch) | **v4.2** (sạch) | +1 version |
| GitHub vs local | ~221 commit ahead | (TBD sau CI reset) | — |
| CI status | Red (quota) | (TBD sau CI reset) | — |

---

## 1. Đã đóng (CR-0004 + CR-0005)

### 1.1 CR-0004 — Sửa lệch Phase/Sprint 266 feature

**File:** `Kaori_AI_Feature_Tree_v4_2.xlsx` (giữ v4_1 làm history baseline).

**Cách fix:** 266 row có `Phase='Phase 1.5'` AND `Sprint LIKE 'P3-%'` đổi cột Phase thành `Phase 3`, giữ nguyên sprint code `P3-S25`.

**Lý do chọn fix theo hướng Phase 3 (thay vì đổi sprint sang P15-S*):**
- Sprint code `P3-S25` rõ ràng phản ánh intent Phase 3 Sprint 25.
- Phase 1.5 Sprint Backlog đã có sẵn 25 feature (sheet riêng) — nếu push thêm 266 sẽ vỡ scope 2-month stabilization.
- Số 25 = 291 - 266 → khớp đúng sau khi 266 dồn về Phase 3 (auto-resolve ISS-002).

**Phân bố 266 feature fixed:**

| Sheet | Số feature đổi phase |
|---|---|
| 🏢 P2 Enterprise Features | 214 |
| 🔗 Shared Cross-cutting Feature | 52 |
| **Tổng** | **266** |

**Phân bố theo module prefix:**

| Module | Count | Module name (đoán theo code) |
|---|---|---|
| M214 | 114 | 2.14 Chart & Visualization Library |
| M213 | 36 | 2.13 Reports Management |
| M28  | 33 | 2.8 Multi-tier Data Analysis |
| M55  | 32 | 5.5 Shared Cross-cutting (cụ thể) |
| M29  | 31 | 2.9 Analysis Frameworks |
| M56  | 20 | 5.6 Shared Cross-cutting (cụ thể) |

**Sync luôn ở Status Tracker:** 266 row + 1147 row → đồng bộ Phase column.

**Issues sheet đánh dấu:**
- ISS-001 ✅ FIXED 2026-05-20 (266 feature đổi phase)
- ISS-002 ✅ AUTO-RESOLVED 2026-05-20 (sau ISS-001 fix, 291 - 266 = 25 = đúng Phase 1.5 Sprint Backlog)

### 1.2 CR-0005 — Điền Owner cho 1.143 feature

**Cách fix:** loop 10 feature sheet + Status Tracker, cell `Owner` trống → gán default theo audience.

**Default mapping:**

| Sheet | Default Owner |
|---|---|
| 🏛️ P1 Platform Features | PM Platform |
| 🏢 P2 Enterprise Features | PM Enterprise |
| 🎨 P3 Studio Features | PM Studio |
| 👤 P4 Personal Features | PM Personal |
| 🔗 Shared Cross-cutting Feature | TL Shared Services |
| 🔍 Process Mining | TL Process Mining |
| 📊 Adoption Intelligence | TL Adoption Intelligence |
| 💰 Operational Economics (NOV) | TL Economics (NOV) |
| 🛡️ Runtime Reliability | SRE Lead |
| 🔭 Observability | SRE Lead |

Status Tracker dùng audience text (Platform / Enterprise / Studio / etc) hoặc fallback theo prefix Feature Code (P1- / P2- / P3- / P4- / PM- / AI- / NOV- / REL- / OBS-).

**Phân bố 1143 Owner filled:**

| Sheet | Owner filled |
|---|---|
| 🏢 P2 Enterprise Features | 579 |
| 🔗 Shared Cross-cutting Feature | 205 |
| 🏛️ P1 Platform Features | 109 |
| 🎨 P3 Studio Features | 62 |
| 👤 P4 Personal Features | 58 |
| 🔍 Process Mining | 33 |
| 📊 Adoption Intelligence | 25 |
| 🛡️ Runtime Reliability | 25 |
| 💰 Operational Economics (NOV) | 24 |
| 🔭 Observability | 23 |
| **Tổng** | **1143** |

Status Tracker (1147 row riêng) cũng được sync 1143 Owner (4 row header/banner không phải data).

**Note:** đây là **tentative default**. Eng Leads (mỗi module có lead riêng) finalize per-module trong **CR Review Board kế** — đổi từ "TL Shared Services" thành tên người cụ thể.

**Issues sheet đánh dấu:** ISS-004 ✅ FIXED 2026-05-20.

### 1.3 Verification

Sau khi save `v4_2.xlsx`, em loop lại 11 sheet (10 feature + Status Tracker):

```
Total feature rows scanned: 2286 (= 1143 catalog × 2: 1 row feature sheet + 1 row Status Tracker, trừ header)
Remaining Phase 1.5 + sprint P3-*: 0 (target 0) ✅
Remaining empty Owner: 0 (target 0) ✅

Phase distribution (cumulative across 2 sheets per feature):
  Phase 1: 1006
  Phase 2: 698
  Phase 3: 532 (gồm 266 mới chuyển từ Phase 1.5)
  Phase 1.5: 50 (= 25 × 2 sheet, đúng intent)
```

⇒ Excel v4.2 baseline sạch.

---

## 2. Còn open

### 2.1 CR-0007 — Secret rotation (PENDING anh confirm)

**Câu hỏi cần anh trả lời:** Zip có chứa `.env` thật (Telegram token / JWT keypair / DB pw / SMTP / Zalo / Anthropic+OpenAI keys) — anh đã từng gửi zip qua kênh nào ra ngoài (email / Drive / chat / gist / etc) chưa?

- **Nếu YES:** chạy rotation playbook trong PROJECT_STATUS_2026-05-20.md §2.1.
- **Nếu NO:** giữ secret hiện tại + thêm `.env*` vào `.gitignore` chắc chắn + xoá zip khỏi máy local sau khi xong việc.

### 2.2 CR-0001/0002/0003 — GAP-01/02/03 PARTIAL → đóng nốt

Phase 2 sprint dedicated (sau khi anh duyệt scope còn lại). Chi tiết phần còn thiếu xem `4.2_Change_Request_Register.md` §5/§6/§7 Section 7.

### 2.3 CI quota reset

Theo plan:
1. Đầu June 2026 quota GitHub Actions reset 3000 min.
2. Push branch `feat/p15-s9-d1` (~221 commit ahead `main`) lên GitHub.
3. Confirm `.gitignore` exclude:
   - `.env`, `.env.*` (giữ `.env.example`)
   - `.claude/`
   - `node_modules/`, `.next/`
   - `target/` (Java build)
   - `*.zip`
4. CI re-run.
5. PR #179 review + merge.
6. Tag `v2.7-governance-wired`.
7. **Rev PROJECT_STATUS** thành snapshot 3 — đánh dấu CI green + tag.

### 2.4 Excel v4.2 housekeeping còn open

- **Owner finalization per-module:** Eng Leads thay default sang tên người cụ thể. Mục tiêu: CR Review Board kế → close 100%.
- **Sprint planning:** điền các cột Effort/SP, MoSCoW, AC, Test Status, Release, Dep Status, FR/US/UC mapping (ISS-005 partial) cho từng sprint khi đến phiên.
- **Journey F vs module 2.17 phase mismatch:** ISS-006 còn OPEN — chốt với PO.

---

## 3. Files được tạo / sửa session 2026-05-20

```
D:\Tài liệu dự án\
├── PROJECT_STATUS_2026-05-20.md           ← rev 1 (sáng — BA sync)
├── PROJECT_STATUS_2026-05-20-rev2.md      ← rev 2 (EOD — file này — Excel fix)
├── Kaori_AI_Feature_Tree_v4_2.xlsx        ← Excel baseline mới (CR-0004 + CR-0005 closed)
├── Kaori_AI_Feature_Tree_v4_1.xlsx        ← Excel cũ — history baseline
├── 4.2_Change_Request_Register.md         ← rev 1.1 (CR closed update)
├── 2.2_FRD_Functional_Requirements_Document.md  ← rev 1.1 (GAP PARTIAL + FR mới)
├── 3.1_SRS_Software_Requirements_Specification.md ← rev 1.1 (UC PARTIAL + §9 §10)
├── 3.3_Wireframes_and_Screen_Spec.md      ← pointer
├── 3.4_API_Contract.md                    ← pointer
├── 3.5_Data_Dictionary_and_Event_Schema.md ← pointer
├── 3.6_UAT_Test_Cases_and_Acceptance_Criteria.md ← pointer
└── README.md                              ← bảng Batch + quy ước source-of-truth update
```

---

## 4. Quy ước rev tiếp theo

1. Mỗi snapshot đặt tên `PROJECT_STATUS_YYYY-MM-DD.md` — KHÔNG sửa snapshot cũ.
2. Snapshot mới chỉ ghi **delta** so với snapshot trước; không lặp.
3. Trigger tạo snapshot:
   - Sau CR HIGH/CRITICAL đóng.
   - Sau Phase milestone (Phase 2.7 → Phase 3 transition).
   - Sau security incident.
   - Sau anh request.
4. Excel rev tăng version (v4_2 → v4_3) khi:
   - CR đụng cấu trúc workbook (cột mới / sheet mới).
   - Phase / Module thay đổi lớn.
   - **KHÔNG rev** khi chỉ điền data per-sprint.

---

*— Hết PROJECT STATUS 2026-05-20 rev 2 —*
