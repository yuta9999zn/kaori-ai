# Live-deep Feature Audit — cụm PR #333–#338 + epic Tier-3

> **Ngày:** 2026-06-02 · **Người audit:** Kaori (Claude Opus) · **Phương pháp:** live-deep (chạy thật qua gateway :8080 + orchestrator :8093 + đối chiếu DB) trên stack pilot đang chạy.
> **Bối cảnh:** reviewer ngoài chấm 60–65% (test-qua-UI lúc backend gãy nửa). Audit này verify độc lập từng chức năng đã ship & merge lên `main`.

## 0. Phán quyết tổng

Cụm chức năng **chạy thật** — không phải vỏ rỗng. Reviewer 60–65% là thấp giả tạo (route gap + data phân mảnh, không phải "chưa build"). Nhưng live-deep lộ **1 finding P1 đúng lõi CDFL** mà unit test bỏ sót, + một loạt P2 robustness/hygiene. Trục "đã build": ~85%. Trục "vòng AI grounding chặt như thiết kế": còn lỗ hổng calibration.

---

## 1. Đã verify CHẠY THẬT (live evidence)

| # | Chức năng | Bằng chứng live |
|---|---|---|
| 1 | Gateway routes (Nhóm 1 wiring) | `frameworks/templates`, `reports`, `insights/feed`, `insights/industry-compare`, `workflows`, `enterprises/users`, `contracts`, `approval-chains`, `document-folders`, `document-repository/search`, `corporate-tree` → **tất cả 200**. `/api/v1/users` → 404 **đúng** (FE đã trỏ sang `/enterprises/users`). |
| 2 | RLS K-1 isolation | `approval-chains` trả `[]` cho tenant 0001 = **ĐÚNG** (2 chain thuộc tenant khác). `contracts`/`workflows`/`memory_l3` đều scoped per-enterprise. Không rò chéo tenant. |
| 3 | industry-compare (RAG ngành) | tenant `2d185ee6`: coverage **0.7988 → "đủ"**, 3 finding cited KB doc-id, kèm disclaim "KHÔNG phải hằng số tuyệt đối" (chống overclaim, K-3). |
| 4 | Gold aggregator (#337) | `gold_features` = **8222 khách** trên tenant giàu; revenue_at_risk 320k₫. Fix JSONB-as-str thật. |
| 5 | \|OR\| coverage_gate | code thật (không stub), ngưỡng env-configurable `_GEN_MIN=0.60`/`_GEN_CAUTION=0.30`/`K=0.6`; **directionally đúng** (on-KB 80% vs off-KB 54%); critic tất định wired; có test. |
| 6 | consolidate → memory L3 | `memory_l3` tăng 1→6 sau các run; mỗi row tag đúng `enterprise_id` (0001 vs 2d185ee6 tách bạch). Cross-process persistence = THẬT. |
| 7 | Workflow advisor (ADR-0040) | `workflow_review`: bắt đúng "Cổng duyệt rỗng quyền" (compliance/high/conf 0.9 + suggestion) + narrative Qwen grounded. |
| 8 | Document analyzer (mig131) | hóa đơn thật → summary "CIF 368,200 USD" + key_field. |
| 9 | Contracts + e-sign | HD-2026-001 lifecycle + whose-turn gating (`is_turn=True`). |
| 10 | DMS kho 10 năm | 2 folder + breadcrumb path-prefix + sibling-unique enforced. |

---

## 2. FINDINGS

### 🔴 P1 — \|OR\| gate calibration: nhánh DECLINE gần như chết (đúng lõi CDFL "học 1 hiểu 10")

**Bằng chứng định lượng (grounded-advisory, dry_run, tenant 2d185ee6):**

| Câu hỏi | similarities top-5 | Σsim | coverage | band | verdict |
|---|---|---|---|---|---|
| On-KB (giảm churn) | 0.59/0.56/0.54/0.51/0.45 | 2.65 | 80% | đủ | accept ✓ |
| **Off-KB (nuôi cá koi)** | 0.29/0.28/0.26/0.24/0.23 | 1.30 | **54%** | **thận trọng** | **accept (cautious)** ✗ |

Câu hỏi hoàn toàn lạc đề vẫn đạt 54% và trả lời "có cơ sở" trích KB bán lẻ churn.

**Nguyên nhân gốc** (`agents/grounding_gate.py:53`): `mass = sum(sims)` — **số lượng bù chất lượng**. 5 doc yếu (~0.25) cộng lại ≈ 1.30 → `1-exp(-0.6·1.30)` = 54%. bge-m3 cho sàn cosine ~0.23 với mọi văn bản cùng tiếng Việt; top-K luôn trả 5 doc → coverage gần như **không bao giờ < 30%** → nhánh "chưa đủ"/decline gần như không kích hoạt.

**Vì sao unit test không bắt:** `test_no_evidence_is_insufficient` truyền **0 citation** → coverage 0. Nhưng production `retrieve_evidence` luôn trả 5 citation → coverage thực sàn ~54%. Test pass, thực tế K-3 chống-hallucinate **yếu hơn thiết kế**.

**Đề xuất fix (build phase):**
- Sàn similarity per-citation: bỏ qua citation < ~0.35 TRƯỚC khi cộng mass.
- Hoặc đổi aggregation: `max(sims)` hoặc mean-of-top-2 thay vì sum → số lượng không bù chất lượng.
- Hoặc relevance-gate ở `retrieve_evidence`: best-sim < ngưỡng → trả `found=0` (thật sự off-domain).
- Calibrate lại `_GEN_CAUTION` theo phân bố similarity thực của bge-m3 (đo trên KB thật).

**✅ ĐÃ FIX (2026-06-06):** floor per-citation (0.35) đã có từ trước (chặn off-domain rõ); nay thêm **max-aggregation** — `grounding_gate.py` xếp hạng citation trên-floor rồi cộng với **geometric decay** `_AGG_DECAY=0.6` (best hit trội, đuôi giảm dần), tách `_GATE_K=0.85` khỏi `_COVERAGE_K`. Hệ quả: mass của N hit ở similarity `s` bị chặn bởi `s/(1−decay)` → **không số lượng nào** của hit vừa-trên-floor chạm "đủ" (6×/20×/50×/100× → đều "thận trọng", ≤59%), trong khi on-KB audit (0.59..0.45) vẫn "đủ" (66.6%). 2 hằng env-tunable. Verify: chạy thật `assess_grounding` (8 case cũ + 3 case max-agg) ALL-PASS. **Còn nợ:** calibrate `_GATE_K` theo phân bố bge-m3 đo trên KB thật; cân nhắc áp cùng max-agg cho `knowledge_coverage` (insight layer, hiện vẫn sum — chưa đụng để khỏi regress industry-compare 80%).

### 🟠 P2 — Robustness / Hygiene

1. **`UUID(actor_user_id)` không guard**: X-User-ID dị dạng → **500** thay vì 4xx RFC7807. → **✅ ĐÃ FIX** (`_parse_actor`→WorkflowInputError→400; 2 test).
2. **`dry_run=true` vẫn ghi memory L3**: consolidate persist OPERATIONAL kể cả dry_run. → **✅ ĐÃ FIX** (`_consolidate_session(dry_run=...)` early-return; 1 test).
3. **Nội dung consolidate = metadata workflow**, không phải insight nghiệp vụ → `recall_memory=0` cho câu hỏi nghiệp vụ. → **DEFER** (thay-đổi-thiết-kế "consolidate→palace", chốt với anh).
4. **Doc analyzer tỷ lệ trống cao**: 2/3 row summary rỗng (Qwen 7B cold-start > FE poll 40s) → cần async UX / cache / fail-loud lý do.
5. **Pilot data phân mảnh theo tenant**: Gold/silver/compare ở `2d185ee6`; `admin@kaori.local` (0001) = 0 gold/0 requirement → demo 1 enterprise thấy "trống". Vệ sinh-dữ-liệu, không phải bug code.

### ❌ Finding bị RÚT (false — do test artifact của chính audit)

- ~~DMS sibling-unique trả 400 thay 409~~ → **SAI.** Code đã trả **409** đúng (`document_repository.py` bắt `uq_docfolder_sibling`). 400 em thấy do tiếng Việt inline curl bị Git-Bash mangle → body parse fail. Re-test file UTF-8 → 409 `RESOURCE.CONFLICT`.
- ~~Contracts detail `party_name=None`~~ → **SAI.** Tên ở `external_name` ("Nguyễn Văn A") + `party_role` ("Bên A"); không có field `party_name` — em parse sai key.

### ⚪ Coverage gap (không live-verify được trên pilot)

- **Approval-chain advance** (level N→N+1 resolve): pilot dùng `workflow_approvals` legacy mig-042, mig-122 chưa apply → không có đường chạy live. Engine có 24 pure test nhưng chưa e2e trên pilot. (Đã biết, ghi nhận trong [[project_tier3_documents_contracts_approvals]].)

---

## 3. Ưu tiên xử lý đề xuất

1. **P1 \|OR\| calibration** — fix aggregation + per-citation floor, đo lại trên KB thật. Ảnh hưởng trực tiếp chất lượng "chống bịa" (K-3) của toàn bộ RAG/advisory.
2. **P2 #1 + #2** — guard UUID (1 dòng) + dry_run gate consolidate (đúng semantics, tránh pollution).
3. **P2 #3** — consolidate insight thật để recall có giá trị.
4. P2 còn lại — gom vào polish pass.
