# FEATURE_EXECUTION_FLOWS.md

> **Mục đích:** mỗi chức năng đã ship được viết lại thành **quy trình chạy step-by-step + cases + sub-cases + non-functional** để anh review song song với code.
> **Ngày tạo:** 2026-05-19 (after Phase 2.5 BE close 10/10 — HEAD `8bb944c`). **Updated 2026-05-19** với full Phase 2.6 closeout + Phase 2.7 governance closeout below.
>
> ### Workflow execution closeout 2026-05-19 (catalog + hardening)
>
> **Step 1 — Catalog coverage (5 waves, 8 commits):**
> - W1 `d77cccd` — Node executor registry + 6 first-wave (if_else/switch/aggregate/read_table/update_record/send_email) + `POST /workflows/{id}/run` + mig 088.
> - W2a `def7a4f` — approval_gate + read_form_submission + resume-aware runner + mig 089.
> - Cron+runbook `f8ca879` — adoption hourly Temporal cron + activation runbook + mig 090.
> - Docs `835269c` — CLAUDE.md 3.5.0 + status badges + FE Run button.
> - W2b `f433fff` — 8 AI nodes (classify/generate/rag/insight/risk/forecast/extract/recommend) + mig (none).
> - W3 `cd2b460` — 10 output/action/validate/data nodes + mig 091 (insights/alerts/tasks/dashboard_tiles/email_intake).
> - W4 `bf2aa0d` — 8 utility nodes (scheduled_trigger/filter/transform/split/join/log/send_chat_message/read_webhook) + mig 092 (chat_outbox/webhook_intake).
> - W5 `8d40099` — final 11 nodes (sort/merge/dedupe/enrich/wait_for_condition/read_api/read_calendar/read_chat/read_file_upload/send_sms/export_file) + mig 093 (calendar_intake/chat_intake/export_files).
>
> **Result:** 45/45 catalog executors registered. 25/25 mig-069 business templates fully LIVE 5/5 nodes.
>
> **Step 2 — Phase 2.6 Operational hardening (8 commits, +151 tests, 2128 → 2279):**
> - P0.1 `c4eb59d` — Event sourcing (`workflow_events` mig 094).
> - P0.2 `1b3e9ae` — Formal state machine (`state_machine.py`).
> - P0.3 `e68f841` — Persistent idempotency (`workflow_idempotency_records` mig 095).
> - P0.4 `8d54230` — Replay harness (drift detection + deterministic test).
> - P1.1 + P1.4 `54caed7` — Module split (runner→state_store) + Saga compensation runtime.
> - P1.2 + P2.2 + P2.3 `6ddb099` — Queue routing + Lifecycle FSM + Edge taxonomy (mig 096).
> - Docs `370309b` — CLAUDE.md 3.7.0 + HTML closeout banner.
>
> **Deferred (infra-gated):** P1.3 Gold incremental (Kafka/Debezium/ClickHouse) · P2.1 ClickHouse cutover · P2.4 Streaming pipeline. Full design in `docs/sprint/PHASE_2_6_DEFER_QUEUE.md`.
>
> **Step 3 — Phase 2.7 Production-readiness governance layer (2 commits, +71 tests, 2279 → 2350):**
> - P1 + P1 `011965b` — Data lineage tracking (mig 097 `data_lineage_edges` + `shared/lineage.py` walk_upstream/downstream + 2 endpoints) + DLQ recovery console (`routers/dlq_console.py` unifying 5 failure sources + admin retry/replay/requeue/discard).
> - P3 + P3 + P2 `5e750b2` — AI governance audit (mig 098 `ai_decision_audit` with conditional immutability trigger + `shared/ai_governance.py` hash/record/override/list) + Declarative policy engine (mig 099 `policy_rules` with 3 K-rule seed + `shared/policy_engine.py` evaluate_condition / evaluate with priority + 60s TTL cache) + Tenant quotas (mig 099 `tenant_quotas`+`tenant_quota_usage` + `shared/tenant_quotas.py` atomic check_and_consume with 5 window periods).
>
> **Result:** 5/5 governance items shipped, 0 deferred. K-rules now declaratively enforced; every LLM call audited; every tenant quota'd; every data object lineage-traceable; every failure operationally recoverable.
>
> **Per-workflow executable status:** `docs/sprint/feature-workflows.html` summary table.
> **Activation runbook:** `docs/runbooks/workflow-execution-enable.md` §2d.
> **Scope:** Phase 2.5 (10/10 BE) trước, Phase 2 sprints sau, Phase 1.5 cuối.
> **Convention:**
> - **Golden case** = đường happy-path tối ưu.
> - **Alt case** = đường rẽ vẫn hợp lệ (degraded nhưng đúng spec).
> - **Sub-case** = edge / failure / boundary trong từng case.
> - **Phi chức năng** = perf · security (K-rules) · scale · error handling · observability.

---

## SECTION 1 — Phase 2.5 (MinerU pattern borrow + AI node catalog)

> 10/10 BE items ship 2026-05-18 → 19. FE bbox highlight UI (Pattern 5 FE half) chờ FE restructure resume. Migrations: 085 + 086 + 087.

### 1.1 — Block taxonomy + Bbox (foundation, không có endpoint riêng)

**File:** `services/data-pipeline/data_plane/silver/blocks.py` + cross-service shim `services/ai-orchestrator/data_plane_shim.py`.

**Mục đích:** Một shape thống nhất cho mọi extractor (PDF / DOCX / OCR / future MinerU) emit ra. Mọi AI node downstream (classify / extract / summarise / sentiment / compare) đều đọc `list[Block]` thay vì `str`.

**Quy trình chạy** (runtime trong từng extract call):
1. Extractor (docsage_extract / table_extractor / reading_order / ocr_client) tạo `Block(type, page_idx, char_start, char_end, text, metadata, bbox)`.
2. Reading-order luôn = thứ tự list (không cần sort key).
3. `bbox` populate cho TABLE (qua `pdfplumber.find_tables()[i].bbox`); TEXT blocks bbox=None ở v0 (Phase 2.6 paragraph chunking sẽ fill).
4. Caller có thể fold blocks về string qua `text_from_blocks()` để giữ backwards-compat.

**Cases:**
- **Golden** — extractor populate full 5 mandatory field + metadata + (nếu có nguồn) bbox; AI node đọc qua `blocks_by_type(BlockType.TABLE)`.
- **Alt — string-only callers** — old code không touch `blocks`, dùng `text=str` cũ; vẫn pass qua vì `text_from_blocks()` re-join.

**Sub-cases:**
- BlockType OOV → enum raise ValueError trước khi đặt vào Block (dataclass frozen=True ép defensive copy không cần).
- Bbox None trên TABLE (find_tables() fail nhưng extract_tables() pass) → caller nhận rows survive, bbox=None propagated.
- Page-level bbox fabricate trên TEXT block → em **từ chối** (CLAUDE.md §14c note). Phase 2.6 paragraph chunking là path đúng.

**Phi chức năng:**
- **Perf:** frozen dataclass + dict default factory → zero-overhead vs tuple. List comprehension filters O(n).
- **Security:** Block chỉ là data, không có I/O. PII bytes pass-through từ extractor lên caller — K-5 redaction là trách nhiệm caller trước khi feed vào AI node.
- **Drift control:** test `tests/test_block_shim_drift.py` so sánh BlockType enum giữa data-pipeline + ai-orch shim — catch class hit em với mig 053+059 writer-path coupling.
- **Observability:** None ở data shape; downstream node log per-block count vì block list = thông tin chính.

---

### 1.2 — Header / footer / page-number strip (Pattern 2)

**File:** `services/data-pipeline/data_plane/silver/header_footer_strip.py`.

**Mục đích:** Xoá header/footer/folio lặp ≥3 trang trước khi feed text cho DocSage / classify / summarise. Tránh "Page 3 of 12" ngấm vào embedding.

**Quy trình chạy:**
1. Caller pass `list[str]` = text per page.
2. `_candidate_lines()` lấy top_n (default 2) lines đầu + bottom_n cuối mỗi page.
3. `_normalize()` áp dụng digit substitution **chỉ khi line khớp `_PAGE_MARKER_PATTERNS`** (Page/Trang/pg/pp prefix, "12", "3/12", "3 of 12") — tránh body line "1B" + "2B" collapse nhầm.
4. Count normalised lines qua mọi page → set vào `header_set` nếu count ≥ min_repeats (default 3).
5. `strip_repeating_lines()` walk lại từng page, drop line khớp normalised set từ top + bottom; **skip pages < short_page_threshold (3) non-empty lines** (cover page giữ nguyên).

**Cases:**
- **Golden** — doc 10 trang có "© 2026 Kaori | Page N of N" lặp cả 10 → cả 2 line bị strip mỗi trang, body sạch.
- **Alt — không lặp đủ** — doc 4 trang, footer chỉ xuất hiện 2 lần → `min_repeats=3` không match → return list nguyên.
- **Alt — pages < min_repeats** — doc 2 trang → `if len(pages_text) < min_repeats` return immediately, không phân tích.

**Sub-cases:**
- **Short page** (cover sheet 1-2 lines) → bị skip cleanup (giữ nguyên). Tránh case "header = nội dung duy nhất bị xoá".
- **Body line khớp digit pattern** (vd "Bài 1B" + "Bài 2B") → `_is_page_marker_like` return False → digit không bị substitute → KHÔNG collapse → giữ nguyên. Hành vi conservative.
- **Same line ở cả top + bottom** (rare nhưng có) → contribute vào cả `top_counts` và `bot_counts`, có thể bị strip cả 2 đầu.
- **Per-page duplicate** ("Page 3" xuất hiện 2 lần trong top_n của 1 page) → `set(_normalize(x) for x in top)` ép thành 1 count per page → không inflate.

**Phi chức năng:**
- **Perf:** O(N pages × top_n + bottom_n) — vài chục lines per page → mili-giây.
- **Security:** N/A (text-only, in-process).
- **K-17:** pure function — caller persist output (`write_idempotent` upstream).
- **Failure mode:** input None / [] → return list rỗng / nguyên input. Không throw.
- **Observability:** không log; cần thêm `silver.header_footer_strip.stripped_count` nếu muốn drift detection.

---

### 1.3 — pdfplumber table extraction (Pattern 3)

**File:** `services/data-pipeline/data_plane/silver/table_extractor.py`.

**Mục đích:** PDF có bảng → emit `Block(type=TABLE)` riêng với `rows`, `markdown`, `html`, `bbox`. DocSage downstream phân biệt "12 dòng prose nhắc khách hàng" vs "12 dòng dữ liệu khách hàng".

**Quy trình chạy:**
1. `extract_tables_from_pdf(content: bytes)`:
   - `import pdfplumber`. Nếu fail → log `pdfplumber_unavailable` + return `[]`.
   - Open `pdfplumber.open(io.BytesIO(content))` (with-context cleanup).
2. Loop từng `page`:
   - `page.extract_tables()` → `list[list[list[str | None]]]`. Per-page exception → log + continue (table extract là enrichment, không gate upload).
   - `page.find_tables()` song song → lấy `.bbox` cho mỗi table. Fail → empty list (bbox=None nhưng rows vẫn live).
3. Per table:
   - `_clean_rows()` strip cell + collapse whitespace + drop fully-empty rows.
   - `_is_useful_table()` filter: rows ≥ 2 AND max_cols ≥ 2 (loại "1 row 1 cell = text trong box").
   - `rows_to_markdown()` + `rows_to_html()` render — markdown header row + separator, HTML escape `& < > "`.
4. Zip rows + bbox theo `tbl_idx` (cùng order theo pdfplumber API contract).
5. Return `list[ExtractedTable]`.

**Cases:**
- **Golden** — PDF báo cáo Q1 có 3 bảng (tổng kết + chi tiết + summary). Mỗi bảng → 1 ExtractedTable với rows + markdown sẵn cho LLM prompt + bbox cho FE crop preview.
- **Alt — pdfplumber không cài** — log warning + return `[]`. Caller (docsage_extract) tiếp tục với raw text (không có TABLE blocks).
- **Alt — page parse fail** — log `page_failed` + continue page sau. Caller nhận output partial.
- **Alt — open fail** — log `open_failed` + return tables_out đã accumulate được (có thể `[]`).

**Sub-cases:**
- **Merged cells / nested tables** — pdfplumber trả `None` cells → `_clean_cell` ép thành `""`. Caller (extract_structured_data) thấy empty cell.
- **Single-row "table"** (text-in-box false positive) → `_is_useful_table` drop, skip emit.
- **Bbox fail riêng** (find_tables raise) → rows vẫn được emit, bbox=None. Phase 2.6 FE highlight nhánh này không tô được nhưng rows vẫn dùng được.
- **Cell có pipe `|`** → `_esc` escape thành `\|` trước khi nối vào markdown.
- **HTML injection** trong cell → 4 ký tự (`&<>"`) escape trước khi nhúng vào `<td>`.

**Phi chức năng:**
- **Perf:** pdfplumber là CPU-bound, ~100-500ms per page với bảng. Hot path nên không trên upload sync — chạy trong silver_pending → silver_complete background path (writer-path coupling, mig 053+059).
- **K-3 N/A:** không LLM.
- **K-5 N/A:** bytes trong process, không leave Kaori.
- **K-17:** pure compute (caller writes Bronze metadata).
- **Memory:** PDF được mở qua `io.BytesIO` không leak — `with pdfplumber.open(...)` context manager.
- **Observability:** `pdfplumber_unavailable` / `page_failed` / `open_failed` log warning với `error=str(e)`. Em **nên** thêm counter `silver.table_extractor.tables_found` cho dashboard.

---

### 1.4 — Multi-column reading-order reconstruction (Pattern 4)

**File:** `services/data-pipeline/data_plane/silver/reading_order.py`.

**Mục đích:** 2-column PDF (VN regulation, finance report, paper) bị pypdf đọc interleave column-line — output thành "Article 1 first sentence Article 2 first sentence". Pattern 4 phát hiện multi-column + reorder lại từng cột top-down.

**Quy trình chạy:**
1. `extract_reading_order_from_pdf(content)`:
   - Mở `pdfplumber.open(io.BytesIO(content))` (cùng PDF parse với table_extractor → 1 parse 2 output).
2. Per page:
   - `page.extract_words()` → `list[dict]` với text + bbox per word.
   - Build `_Word` dataclass list.
3. `detect_columns(words, page_width)`:
   - Nếu `len(words) < 15` → 1 band cover full width (single column path).
   - `_x_histogram()` bin x_center thành 30 bins.
   - `_find_peaks_and_valley()`:
     - Top 2 bins cách ≥3 bins.
     - Valley = min bin giữa 2 peaks.
     - Yêu cầu `valley / min(peak) ≤ 0.35` (VALLEY_RATIO).
     - **Tie-break** ở valley: lấy MIDPOINT của tie range (không phải leftmost) — fix bug em bắt được trong test khi nhiều bin có cùng giá trị min.
   - Trả 2 ColumnBand split tại midpoint của valley bin.
4. Per column: `_words_to_lines()` group word theo Y-tolerance = `page_height / 200` → sort line theo top Y → trong line sort theo x0.
5. Concat lines, page emit `PageReadingOrder(text, column_count, word_count)`.

**Cases:**
- **Golden — 2-col regulation** — page có 2 peaks clear ở x≈150 + x≈445, valley ở x≈300 < 0.35 × peak. Output: tất cả Article 1 trước, rồi Article 2. column_count=2.
- **Alt — single-column invoice** — `_find_peaks_and_valley` return None (1 peak hoặc valley > 0.35) → 1 band → output reorder Y-then-X cải thiện so với raw pypdf nhưng không phân cột.
- **Alt — sparse page** (cover sheet < 15 words) → single-band path → trả về Y-sorted output.

**Sub-cases:**
- **3-col layout** (newspaper rare) → today chỉ detect 2 columns; valley algorithm pick 2 strongest → kết quả approximate. Pattern 4b chưa scope.
- **Page rotation 90°** → x/y semantic đảo → column detection fail (peaks tại y thay vì x). Em chưa handle; Phase 3 add rotation detection.
- **Valley tie** — 5 bin cùng count min → pick **midpoint** của tie (đã fix trong test). Tránh boundary stick vào edge của 1 column.
- **page_width = 0** (PDF metadata corrupted) → `_x_histogram` return `[0]*30` → no peak → single-band.
- **pdfplumber không cài** → return None → caller (docsage_extract) fall back pypdf string per page.

**Phi chức năng:**
- **Perf:** ~50-200ms per page (pdfplumber extract_words + numpy-free histogram + sort). Single-col path zero cost (1 band → 1 word loop). Vast majority of business docs single-col → low average cost.
- **K-3 N/A / K-5 N/A:** pure compute.
- **K-17:** pure.
- **Telemetry:** `multi_column_page_count()` helper để dashboard biết Pattern 4 fire bao nhiêu page thực tế trong prod.
- **Failure:** log `reading_order.pdfplumber_unavailable` / `page_extract_failed` / `open_failed` — never raise.

---

### 1.5 — Bbox propagation BE foundation (Pattern 5)

**File:** `services/data-pipeline/data_plane/silver/blocks.py` (Bbox dataclass) + `table_extractor.py` (populate trên TABLE) + `data_plane_shim.py` (cross-service mirror).

**Mục đích:** Pattern 5 = FE bbox highlight UI. Em ship **BE half** (Bbox shape + population trên TABLE) trước, FE half chờ FE restructure resume. Lý do: rerun extraction lại sau khi FE consume = đắt (invalidate docsage_text cache toàn cục).

**Quy trình chạy (BE foundation only):**
1. `Bbox(x0, top, x1, bottom)` frozen dataclass — match pdfplumber convention (origin = top-left, y grows down).
2. Trong `table_extractor.extract_tables_from_pdf`:
   - `page.find_tables()[i].bbox` → tuple `(x0, top, x1, bottom)`.
   - Coerce `float()` per coord; non-numeric raise → catch và set bbox=None (em **không fabricate**).
3. `ExtractedTable.bbox` set; downstream `docsage_extract` map sang `Block(bbox=Bbox(...))`.
4. TEXT blocks **deliberately bbox=None ở v0** — page-level bbox useless cho FE; Phase 2.6 paragraph chunking là path đúng.

**Cases:**
- **Golden** — pdfplumber detect bảng + bbox → Block(type=TABLE, bbox=Bbox(...)) ship qua FE. FE crop PDF preview tại bbox để show inline.
- **Alt — find_tables fail nhưng extract_tables ok** — rows survive, bbox=None. FE thấy TABLE block không có bbox → fallback show whole page.

**Sub-cases:**
- **Non-numeric bbox** trong PDF metadata edge case → `float()` raise → except clause set bbox=None. Em refuse fabricate (CLAUDE.md note).
- **Paragraph chunking chưa land** → tests pin TEXT bbox=None để regression không ngấm vào.
- **Cross-service drift** — Bbox shape giữa data-pipeline (canonical) + ai-orch shim phải match. Test `test_block_shim_drift.py` so sánh fields — catch dạng bug mig 053+059 (writer-path coupling) gây ra trong quá khứ.

**Phi chức năng:**
- **Perf:** ~zero — bbox đã có sẵn từ pdfplumber, em chỉ coerce.
- **Memory:** Bbox = 4 floats per Block = ~32 bytes. Doc 100 bảng → ~3 KB extra.
- **K-17:** pure (cùng phần với table_extractor).
- **Observability:** ngầm qua test drift artefact.
- **Forward-compat:** Phase 2.6 add `bbox` cho TEXT blocks → FE highlight per paragraph; today bbox=None là sentinel.

---

### 1.6 — Document type detection + spoof guard (ingestor wire-in)

**Module:** `services/data-pipeline/data_plane/silver/document_type.py` (detector) + ingestor wire trong `/upload` route.

**Mục đích:** Người dùng đổi tên `.exe` thành `.pdf` để bypass whitelist → detector đọc magic bytes (PDF `%PDF-`, ZIP `PK\x03\x04` cho DOCX, JPEG `\xff\xd8\xff`, PNG `\x89PNG`) → trả `detected_kind` AUTHORITATIVE. Ext chỉ fallback khi `detected_kind == UNKNOWN`.

**Quy trình chạy:**
1. Upload POST `/upload` nhận `file` + `expected_document_types` (workflow-step yêu cầu).
2. Đọc `content[:512]` → detector trả enum `{PDF, DOCX, XLSX, JPEG, PNG, WEBP, CSV, TXT, UNKNOWN}`.
3. So `detected_kind` vs `expected_document_types`:
   - **Match** → tiếp tục Bronze write + extraction pipeline.
   - **Mismatch** → 422 RFC 7807 với `detail.detected_kind` + `detail.expected_types` + hint.
4. Nếu `detected_kind == UNKNOWN` → fall back theo ext (cuối cùng, mới defensive).

**Cases:**
- **Golden** — workflow step yêu cầu `[pdf, docx]`, user upload `report.pdf` magic byte `%PDF-` → match → tiếp tục.
- **Spoof case** — `malicious.pdf` thực ra là `MZ\x90...` (PE binary) → detector trả UNKNOWN → 422 "định dạng chưa hỗ trợ".
- **Renamed extension** — user save Excel thành `.csv` → magic bytes là ZIP+`xl/workbook.xml` → detector trả XLSX → mismatch với expected `[csv]` → 422 với clear hint.
- **Whitelist allow both** — workflow `[image, scan]` accepts JPEG+PNG+WebP → cả 3 magic bytes match.

**Sub-cases:**
- **Content < 512 bytes** (vd: empty txt) → detector chỉ thấy đầu nhỏ; vẫn detect đúng cho PDF/DOCX (magic ở 4-8 byte đầu).
- **DOCX vs XLSX** đều là ZIP → detector mở ZIP central directory peek `xl/` vs `word/` để phân biệt.
- **TXT vs CSV** không có magic byte phân biệt → fallback ext (CSV mặc định nếu ext = `.csv`).
- **MIME từ browser sai** (vd Firefox upload `.pdf` báo `application/octet-stream`) → em chỉ tin magic byte + ext, KHÔNG dùng MIME upstream.

**Phi chức năng:**
- **Perf:** read 512B header + simple byte compare → micro-giây.
- **Security K-12:** detected_kind không nhận từ query/body → JWT enterprise + magic byte = source of truth. Không trust ext.
- **Security K-5:** detector không log content (PII safety).
- **Defense in depth:** ext fallback chỉ khi UNKNOWN. Renamed-extension spoof = 422 (rejected before Bronze).
- **Test pin:** `test_upload_detection_wire.py` cover spoof + image aliases + ext fallback.

---

### 1.7 — OCR Qwen2-VL adapter (llm-gateway /v1/ocr + ocr_client)

**Files:** `services/llm-gateway/providers.py:ocr_image` + `/v1/ocr` route + `services/llm-gateway/models.py:OcrRequest` + `services/data-pipeline/data_plane/silver/ocr_client.py`.

**Mục đích:** Scan ảnh (JPG/PNG/WebP của hợp đồng đã ký, hoá đơn chụp điện thoại) cần text → gọi Qwen2.5-VL local qua Ollama, KHÔNG external vendor (K-4 enforce schema-level).

**Quy trình chạy:**
1. Ingestor sau `docsage_extract` trả `status='unsupported_today'` cho image MIME → check `is_ocr_candidate(mime_type, ext)`.
2. Nếu là candidate → `ocr_image_to_text(content, ent_id, mime, ext, prompt, max_tokens)` (async):
   - **Pre-flight gates** (KHÔNG burn gateway call):
     - `content` empty → `OcrResult(status='empty_image', text='', error_message="Ảnh rỗng")`.
     - `len(content) > MAX_OCR_BYTES (11 MB)` → `status='unsupported_today'` với hint giảm độ phân giải.
     - Không phải image candidate → `status='unsupported_today'` với hint JPG/PNG/WebP.
   - `base64.b64encode(content)` → JSON body `{image_b64, enterprise_id, prompt, max_tokens}`.
3. POST `http://llm-gateway:8095/v1/ocr` với `timeout=200s`.
4. llm-gateway route `/v1/ocr`:
   - Validate `OcrRequest` (Pydantic) — **không có field `consent_external`** (K-4 enforce schema-level; test pin để vendor vision không sneak vào).
   - `providers.ocr_image()` dispatch Ollama Qwen2.5-VL local with `temperature=0`.
   - Trả `{text, char_count, model_used, latency_ms}`.
5. Ingestor on `status='ok'`:
   - Upgrade file row `silver_complete`.
   - Populate `docsage_text` với OCR output (cùng contract với native PDF text).
6. On `status='failed'` (gateway / network) → giữ file trong `unstructured_pending`; manual queue handle.

**Cases:**
- **Golden** — `invoice.jpg` 2 MB → 200ms pre-flight + ~3-8s OCR → `text="Hoá đơn số 0123...\n..."` → silver_complete.
- **Alt — empty image** — 0-byte upload → pre-flight short-circuit, không gọi gateway.
- **Alt — oversize** — 25 MB photo → pre-flight reject với VN message.
- **Alt — non-image** — PDF lọt vào candidate path bằng cách nào đó → pre-flight reject (không phải MIME image).
- **Alt — OCR returned empty** — ảnh trắng → response `text=""` → status='empty_image' với hint "ảnh trắng hoặc không nhận dạng được".
- **Alt — gateway 500 / timeout** — except HTTPError → status='failed', error_message với exception type. File stay in unstructured_pending.

**Sub-cases:**
- **K-4 enforcement** — em pin test `test_ocr_request_schema.py` so OcrRequest **không có** `consent_external` / `prefer_external`. Future vendor vision adapter MUST add field → test fail → forced deliberate ADR review.
- **Vietnamese diacritics** — Qwen2.5-VL handle UTF-8; em không strip diacritics ở client.
- **temperature=0** ở providers.ocr_image — retry deterministic (same image → same text up to sampler floor).
- **MIME alias** (`image/jpg` vs `image/jpeg`) — `SUPPORTED_IMAGE_MIMES` cover cả 2.
- **Ext không có dot** (`jpg` thay vì `.jpg`) — `is_ocr_candidate` normalise.
- **Concurrent calls per tenant** — gateway sequential per Ollama instance; large enterprise có thể cần worker scaling Phase 3.

**Phi chức năng:**
- **Perf:** preflight gates < 1ms. OCR call 3-15s per image (Qwen2.5-VL trên CPU/GPU local). Timeout 200s (heavy upper bound).
- **K-3** ✅: dispatch qua llm-gateway only, không call Ollama direct từ data-pipeline.
- **K-4** ✅: enforced schema-level — không có field external consent. Vendor vision = Phase 3 + ADR-mới.
- **K-5** ✅: image bytes never leave Kaori — Qwen local only.
- **K-17** write_idempotent: same image + same model rev → same output.
- **Observability:** `ocr_client.gateway_call_failed` / `ocr_client.unexpected` log warning. `model_used` + `latency_ms` propagated qua response cho audit.
- **Backpressure:** ingestor synchronous on OCR right now; nếu queue dài → defer Phase 3 worker pattern.

---

### 1.8 — `classify_document` AI node

**File:** `services/ai-orchestrator/reasoning/document_classifier.py` (mig 085).

**Mục đích:** Doc → 1 category trong caller-supplied list (default 12 cat VN business). Output có confidence + reasoning → caller gate threshold (default 0.7 per ADR-0023).

**Quy trình chạy:**
1. Caller (workflow node) gọi `classify_document(ClassifyInput(blocks, enterprise_id, candidates, consent_external, run_id, min_confidence))`.
2. `_build_prompt`:
   - Lấy mọi TITLE block (lead signal).
   - Lấy body 3 KB đầu (skip HEADER/FOOTER/PAGE_NUMBER).
   - Compose prompt VN với danh sách candidates + schema yêu cầu JSON `{category, confidence, reasoning}`.
3. `llm_router.complete_with_schema(prompt, task='classify_document', output_schema, consent_external, enterprise_id, run_id, max_tokens=300)`.
4. Output_schema `_OUTPUT_SCHEMA` ép `{category: string, confidence: 0..1, reasoning: string maxLength 500}` — 1 repair round nếu LLM ra invalid JSON; second fail 502.
5. Coerce OOV: `cat = "uncertain"` + confidence=0 nếu category không trong `candidates_lower`.
6. `meets = (confidence ≥ min_confidence) AND (cat != 'uncertain')`.
7. Log `classify_document.done` + return `ClassifyOutput`.

**Cases:**
- **Golden** — NDA upload, default categories → `{category: "contract", confidence: 0.92, reasoning: "Tài liệu có tiêu đề 'Thỏa thuận bảo mật'...", meets_threshold: True}`.
- **Alt — caller candidates** — mig 069 workflow template pass `["nda", "service_contract", "employment", "lease"]` → classify trong scope đó.
- **Alt — uncertain** — doc ngắn 3 dòng "hello world" → confidence < 0.7 → meets=False → caller route to human review.

**Sub-cases:**
- **OOV category** — LLM emit "report_quarterly" (không có trong list) → coerce thành "uncertain", confidence=0, log `oov_category` warning.
- **Backwards compat** — old `llm_router` không có `complete_with_schema` → fall back `complete()` + `_parse_json_fallback()` (strip code fences + bracket isolate).
- **Empty blocks** — caller pass `blocks=[]` → prompt body rỗng → LLM thường ra "other" với confidence thấp → meets=False.
- **JSON parse fail (cả 2 lần repair)** — output_schema repair fail twice → llm-gateway raise 502 LLM.OUTPUT_VALIDATION_FAILED → propagate exception lên caller.
- **Consent denied** — caller `consent_external=True` nhưng tenant `consent_external=False` → llm_router raise ConsentDeniedError trước khi gọi vendor.

**Phi chức năng:**
- **Perf:** 1 LLM call. Qwen 14B ~1-3s typical. Prompt cap 3 KB → ~800-1000 token in. Response 300 tokens cap → < 1s out.
- **K-3** ✅: llm_router only.
- **K-4** default Qwen local; opt-in external per call.
- **K-17** read_only.
- **K-20** model pinning: cần thêm vào llm_router routing config Phase 2.5 follow-up (TODO mở).
- **Observability:** `classify_document.done` log với category + confidence + meets_threshold + ent_id. `oov_category` warning catch model drift.
- **Determinism:** Qwen temperature thường 0.3 → confidence ≥ 0.7 stable; nếu cần reproducibility cho audit thì caller `consent_external=False` + `task='classify_document'` ép Qwen + temperature=0 ở gateway side.

---

### 1.9 — `extract_structured_data` AI node

**File:** `services/ai-orchestrator/reasoning/structured_extractor.py` (mig 085).

**Mục đích:** TABLE blocks (Pattern 3) + target schema (columns) → typed rows ready to INSERT vào Silver per-domain tables. Closes loop "Pattern 3 emit table" → "Silver INSERT".

**Quy trình chạy:**
1. Caller `extract_structured_data(ExtractInput(blocks, target_schema: list[ColumnSpec], enterprise_id, consent_external, run_id, min_mapping_confidence=0.6))`.
2. Filter `blocks` → list TABLE blocks với index `(block_idx, block)`.
3. Nếu không có TABLE → return `ExtractOutput(rows=[], warnings=["no_tables_in_input"], tables_processed=0, rows_extracted=0)`.
4. `_output_schema_for(columns)` build JSON Schema:
   - `{type: "object", required: ["rows", "mapping_confidence", "notes"]}`.
   - `rows: {type: "array", items: {type: "object", required: [...required col names], properties: {<colname>: {type, enum?, format?}}}}`.
5. Per table:
   - `_build_prompt(block.text [= markdown từ Pattern 3], columns)` → VN prompt với column brief + định dạng "1234567.89" cho số, "YYYY-MM-DD" cho date.
   - `llm_router.complete_with_schema(...)` với `max_tokens=2000`.
   - Per-table exception → log `extract_structured_data.table_failed` + append warning `"trang N: trích xuất thất bại (TypeName)"` + **continue** (không abort run).
   - Confidence < threshold → append warning, **vẫn emit rows** (caller quyết drop hay keep).
6. Per row trong response: skip nếu không phải dict → `ExtractedRow(values, source_page_idx=block.page_idx, source_block_id=block_idx)`.
7. Return `ExtractOutput(rows, warnings, tables_processed, rows_extracted)`.

**Cases:**
- **Golden** — bank statement có 1 bảng transaction 60 rows. target_schema = `[date, description, debit, credit, balance]`. LLM map cell → 60 ExtractedRow với confidence 0.95.
- **Alt — multi-table doc** — Q1 report 4 bảng (summary + revenue + expense + headcount). 4 LLM calls, 4 sets of rows merge.
- **Alt — low confidence** — bảng có cột "Số tiền" nhưng schema yêu cầu "amount_vnd" + "amount_usd" → mapping ambiguous → confidence 0.4 → warning emit, rows vẫn ship.

**Sub-cases:**
- **Per-table fail isolated** — bảng 2 OOM (giả lập 50 rows), bảng 1+3+4 vẫn ship rows. Pattern em đề cập trong CLAUDE.md §14c "per-item LLM failure ≠ abort run".
- **Required column missing** — schema required `["customer_id", "amount"]`, LLM emit row `{customer_id: "C1"}` thiếu amount → output_schema validation 1 repair round; nếu vẫn fail → row drop trong response, caller thấy warning + less rows.
- **Number format dirty** — cell "1.234.567,89" VN format → prompt yêu cầu "1234567.89" → LLM normalise; nếu LLM emit nguyên "1.234.567,89" → schema validate type=number → repair round → cuối cùng converted hoặc 502.
- **Date format** — cell "01/02/2026" → schema `{type: string, format: date}` ép "YYYY-MM-DD". LLM thường parse OK; fail → repair.
- **Enum column** — `target_schema` có `ColumnSpec(name="status", enum=["paid", "pending", "overdue"])` → JSON Schema enum → out-of-enum value → repair → final fail → 502.
- **K-9 NUMERIC** — em pass số dạng string canonical; Silver INSERT cast Decimal. Em **không** Decimal-coerce trong node (CLAUDE.md ghi K-9).

**Phi chức năng:**
- **Perf:** N TABLE × ~3-10s LLM call mỗi cái. Doc 5 bảng → ~30s. Async I/O → nếu cần thì caller parallelize qua `asyncio.gather` (chưa làm; tuần tự trong v0).
- **K-3** ✅. **K-4** Qwen default + opt-in. **K-17** read_only. **K-20** model pin TODO.
- **Provenance:** `source_block_id` + `source_page_idx` per row → caller có thể cite "row này từ page 3 bảng 2".
- **Observability:** `extract_structured_data.done` log tables / rows / warnings count. `table_failed` warning per bảng.
- **Scale:** doc 50 bảng cùng lúc = 50 LLM calls = expensive. Caller phải gate (default workflow timeout ≈ 60s; doc >10 tables bắt đầu rủi ro). Phase 3 batch-extract pattern.

---

### 1.10 — `summarise_document` AI node

**File:** `services/ai-orchestrator/reasoning/document_summariser.py` (mig 086).

**Mục đích:** Long regulation / proposal / meeting minutes → executive summary 2-4 sentences + 3-7 bullets + next-action hint. Feed CFO digest (NOV-RPT-020) hoặc inline FE card.

**Quy trình chạy:**
1. Caller `summarise_document(SummariseInput(blocks, enterprise_id, consent_external, run_id, max_bullets=5, target_lang='vi'))`.
2. `_estimate_reading_time(blocks)` — sum `char_length` của blocks không phải HEADER/FOOTER/PAGE_NUMBER → seconds = `round(total / 17 / 5) * 5` (~200 wpm assumption, round to nearest 5s, min 5).
3. `_build_prompt`:
   - Persona VN/EN tuỳ `target_lang`.
   - TITLE blocks lead (3 đầu).
   - Body 6 KB (bigger than classify, summary cần context).
4. `llm_router.complete_with_schema(..., max_tokens=900)`.
5. Output schema `_OUTPUT_SCHEMA`:
   - `summary: maxLength 1500`.
   - `bullets: maxItems 7, items maxLength 400`.
   - `next_action_hint: maxLength 300`.
6. Truncate `bullets[:max_bullets]` post-LLM (defensive cap).
7. Return `SummariseOutput(summary, bullets, next_action_hint, source_char_length, reading_time_seconds)`.

**Cases:**
- **Golden** — Thông tư 30/2026 NHNN 12 trang → summary 3 sentences VN + 5 bullets (impact + deadline + scope + exception + penalty) + next_action_hint "Forward to compliance team trước 30/06".
- **Alt — short doc** — internal memo 200 chars → reading_time 5s min → LLM ra 2-3 bullets is enough.
- **Alt — target_lang='en'** — vendor proposal English → persona EN → bullets EN.

**Sub-cases:**
- **bullets > 7** từ LLM → schema maxItems=7 ép. Em **also** trim `[:max_bullets]` post — defensive.
- **bullets có non-string** (number leak) → filter `isinstance(b, (str, int, float))` → coerce string.
- **next_action_hint rỗng** → schema cho rỗng string; FE show "—" hoặc bullet cuối cùng.
- **Body > 6 KB** — `_build_prompt` slice `[:1500]` per block + break khi total > 6000 → tail blocks skip. Long doc → summary có thể miss conclusion section. Workaround Phase 2.6: chunked-then-merge summary.
- **Char count zero** (blocks empty) → reading_time=5 (min floor).

**Phi chức năng:**
- **Perf:** 1 LLM call. Qwen 14B ~2-5s với 6 KB in + 900 tokens out.
- **K-3** ✅. **K-4** Qwen default, opt-in external (English-heavy doc với Claude/GPT có thể chất lượng cao hơn).
- **K-17** read_only. **K-20** task='summarise_document' pin model version.
- **Reading time** = pure compute → khi LLM down vẫn show reading time → graceful degradation possible nếu wrap call trong try/except (today raise).
- **Observability:** `summarise_document.done` log bullets + reading_time + ent_id.

---

### 1.11 — `sentiment_analysis` AI node

**File:** `services/ai-orchestrator/reasoning/sentiment_analyser.py` (mig 086).

**Mục đích:** Support ticket / review / NPS comment / sales call transcript → overall sentiment + (optional) per-aspect (delivery / quality / price / support). 5-point scale symmetric.

**Quy trình chạy:**
1. Caller `sentiment_analysis(SentimentInput(blocks, enterprise_id, consent_external, run_id, aspects=[AspectRequest...], min_aspect_confidence=0.5))`.
2. `_collect_text(blocks)` — body 4 KB cap, skip HEADER/FOOTER/PAGE_NUMBER.
3. `_warn_if_pii(text, ent_id)` — regex email + VN phone → log `pii_smoke_alarm` (warning, không raise; K-5 redaction là caller's job).
4. `_output_schema(aspects)`:
   - Base: `overall_label ∈ {very_negative, negative, neutral, positive, very_positive}`, `overall_confidence 0..1`, `overall_reasoning maxLength 500`.
   - Nếu aspects → thêm `aspects: object` với required per-aspect, mỗi entry `{label ∈ scale ∪ "unknown", confidence, reasoning}`.
5. `_build_prompt` — VN prompt với schema instruction. Per-aspect hint "Nếu khía cạnh không nhắc, label='unknown', confidence=0".
6. `llm_router.complete_with_schema(..., max_tokens=600)`.
7. Coerce `overall_label` không trong scale → "neutral" + log warning.
8. Per aspect: coerce OOV label → "unknown" + score=0; `SENTIMENT_SCALE` map label → float (-1.0..+1.0).
9. Return `SentimentOutput(overall_label, overall_score, overall_confidence, overall_reasoning, aspects=[AspectScore...])`.

**Cases:**
- **Golden — ticket triage** — "Sản phẩm giao thiếu, dịch vụ hỗ trợ không phản hồi 3 ngày" → overall="negative", score=-0.5, confidence=0.85. Aspects `[delivery_speed, support_quality]` → cả 2 negative.
- **Golden — overall only** — aspects=None → 1 LLM call, prompt ngắn hơn ~30%, response không có `aspects` key.
- **Alt — neutral overall** — internal memo "Báo cáo quý 1 đã hoàn tất" → overall=neutral, confidence ~0.7.
- **Alt — aspects not mentioned** — review "Giao hàng nhanh" + aspects=`[delivery, price]` → delivery=positive, price=unknown confidence=0.

**Sub-cases:**
- **PII smoke alarm** — text chứa "khach.com.vn / 0912345678" → log warning, vẫn xử lý (em không strip; caller K-5 trách nhiệm).
- **OOV overall label** — LLM emit "extremely_negative" → coerce "neutral" + log `invalid_overall_label`. Bug catch.
- **Aspect missing trong response** — `aspects_raw.get(a.name)` None → default `{label='unknown', conf=0, score=0}`.
- **min_aspect_confidence** filter — caller có thể loop result + treat aspect confidence < 0.5 as "unknown for UI purposes". Em surface raw confidence, caller filter.
- **target_lang ngụ ý VN** — prompt VN cứng; future Phase 3 add target_lang.

**Phi chức năng:**
- **Perf:** 1 LLM call. 4 KB in + 600 tokens out → 2-4s. Aspects nhiều (10+) → prompt dài → token budget tăng nhưng vẫn 1 call.
- **K-3** ✅. **K-4** Qwen default; opt-in cho English-heavy.
- **K-5 caveat:** sentiment KHÔNG redact PII tự thân — caller phải redact trước (em chỉ log smoke alarm).
- **K-17** read_only.
- **Observability:** `sentiment_analysis.done` log overall + aspect count. `pii_smoke_alarm` catch caller skip K-5.
- **Idempotency:** với temperature thấp + schema enforce → response stable. Audit reproducibility OK.

---

### 1.12 — `dedup_records` pure-compute node

**File:** `services/ai-orchestrator/reasoning/record_dedup.py` (mig 086).

**Mục đích:** ExtractedRow list từ `extract_structured_data` (hoặc CSV import) có duplicate (same customer phone format khác, same transaction across 2 báo cáo overlap) → collapse. **K-17 pure** — không LLM, không DB.

**Quy trình chạy:**
1. Caller `dedup_records(rows: list[ExtractedRow], spec: DedupSpec)`:
   - `spec.keys` = list `DedupKey(column, normaliser)`.
   - `spec.conflict_policy ∈ {'first', 'last', 'longest_non_empty'}` hoặc `merge_fn` override.
   - `spec.fuzzy_threshold ∈ (0..1]` — 1.0 = exact only.
2. Per row → `_composite_key(values, spec)`:
   - Per key: lookup `NORMALISERS[k.normaliser]` (`lower` / `vn_phone` / `vn_name` / `email` / `raw`).
   - Concat normalised parts với `\x1f` separator → SHA1 hex.
3. Group rows by composite key (preserve first-occurrence order).
4. Nếu `fuzzy_threshold < 1.0` AND any DedupKey use `vn_name` → `_fuzzy_collapse`:
   - Per group → rebuild repr text từ first member's normalised parts.
   - O(N²) over group keys → `SequenceMatcher.ratio() ≥ threshold` → merge buckets.
   - Log `fuzzy_collapse` count before / after.
5. Per group → `_pick_winner(group, policy)` hoặc `spec.merge_fn(group)`:
   - `first`: dict(group[0].values).
   - `last`: dict(group[-1].values).
   - `longest_non_empty`: merge col-by-col, prefer non-empty + longer string.
6. Return `DedupOutput(rows: list[DedupedRow], rows_in, rows_out, duplicates_dropped)` where `DedupedRow` carry `source_block_ids`, `source_page_idxs`, `collapsed_from`.

**Normalisers:**
- `lower` — strip + lower.
- `vn_phone` — strip non-digit, drop +84/0 prefix → last 9 digits. `'+84 912 345 678'` ≡ `'0912.345.678'` ≡ `'912345678'`.
- `vn_name` — NFKD decompose + strip diacritics + explicit `đ→d`, `Đ→D` + collapse whitespace + lower. `"Nguyễn Văn  An"` → `"nguyen van an"`.
- `email` — strip + lower.
- `raw` — passthrough (any → str).

**Cases:**
- **Golden — CRM import 3 source files** — same khách hàng "Nguyễn Văn An" + phone "0912345678" / "+84912345678" / "0912 345 678" + email "an@kaori.vn" → 3 row collapse → 1 row, `collapsed_from=3`.
- **Golden — bank dedup transactions** — overlap 2 monthly reports → same `(date, amount, ref)` triplet → dedup keep first.
- **Alt — fuzzy on name only** — phone formats diff không đủ collapse exact (vd 1 phone bị typo) → exact pass 2 groups → fuzzy pass `vn_name` similarity ≥ 0.85 → merge thành 1.

**Sub-cases:**
- **Empty key value** — row thiếu phone column → normaliser trả `""` → degenerate key `""`. Em **không** all-empty-collapse vì SHA1(empty parts joined) khác SHA1(other empty composite of different keys); thực tế nhiều row missing phone sẽ collapse vào nhau — caller phải biết.
- **Conflict policy `longest_non_empty`** — row A `{phone: "0912...", email: ""}` + row B `{phone: "0912...", email: "an@..."}` → merge cả phone + email (B's email wins because A empty).
- **Custom `merge_fn`** — caller pass lambda sum quantities for SKU dedup line items.
- **Fuzzy disabled** (threshold = 1.0 default) → skip _fuzzy_collapse entirely → zero O(N²) cost.
- **Fuzzy without vn_name** — em **explicitly skip** fuzzy nếu không có DedupKey nào dùng `vn_name`. Tránh O(N²) tốn kém trên phone/email exact matching.
- **rapidfuzz vs difflib** — code import path note "rapidfuzz when available, fallback difflib SequenceMatcher". Today em chỉ dùng `SequenceMatcher`; rapidfuzz upgrade Phase 3 optimisation.

**Phi chức năng:**
- **Perf — exact path:** O(N) → 1000 rows < 50ms.
- **Perf — fuzzy path:** O(G²) where G = group count (đã exact-collapsed). 100 groups → 5000 SequenceMatcher.ratio() calls → ~100-300ms. Restrict to vn_name keep cost bounded.
- **K-17** ✅ PURE. Pin via test `tests/test_dedup_pure_determinism.py` — same input twice → same output bytes-for-bytes.
- **Determinism:** key normaliser deterministic; SHA1 deterministic; iteration order preserved.
- **No I/O:** zero network, zero DB.
- **Provenance:** `source_block_ids` + `source_page_idxs` preserved → caller cite "Khách hàng A từ pages 3, 7, 12".
- **Observability:** `dedup_records.done` log rows_in / rows_out / duplicates_dropped + keys. `fuzzy_collapse` count when fuzzy fired.

---

### 1.13 — `compare_to_template` AI node (RAG-backed contract diff)

**File:** `services/ai-orchestrator/reasoning/template_comparator.py` (mig 087).

**Mục đích:** Compare candidate contract vs known-good template. Phát hiện clause MISSING / ADDED / MODIFIED / MATCH + risk_level + overall_risk_score. Use case: vendor NDA review, regulatory filing check, PO change detection.

**Quy trình chạy:**
1. Caller `compare_to_template(CompareInput(template_blocks, candidate_blocks, enterprise_id, consent_external, run_id, similarity_threshold=0.65, risk_keywords=DEFAULT_RISK_KEYWORDS, llm_gateway_url=None))`.
2. `extract_clauses(blocks)` cho mỗi bên:
   - Walk blocks: TITLE → start new clause; TEXT/LIST/QUOTE → accumulate body; TABLE/CODE/EQUATION → flush + skip; HEADER/FOOTER/PAGE_NUMBER/IMAGE_REF/CAPTION → skip.
   - Nếu zero TITLE → emit 1 clause `title=""` + full body (giữ content).
   - Body cap 3 KB per clause (`_CLAUSE_TEXT_CAP`).
3. `_embed_clauses(clauses, ent_id, gateway_url)`:
   - Per clause: POST `gateway/v1/embed` với `{text: title + "\n" + body, enterprise_id}`, timeout 30s.
   - Per-embed exception → log + push empty vector (downstream treat sim=0).
4. **Pass 1** — per candidate clause:
   - Compute `_cosine(cand_vec, tpl_vec)` over all template clauses.
   - Best sim ≥ threshold → save tpl_idx vào `used_template_indices` → goto LLM diff.
   - Best sim < threshold → `ClauseMatch(status='added', risk=_bump_risk_for_keywords(cand, 'medium', keywords), similarity=best_sim, explanation="Candidate có điều khoản không tìm thấy trong template")`.
5. LLM diff per matched pair:
   - `_build_diff_prompt(tpl_clause, cand_clause)` — VN prompt với schema `{status: 'match'|'modified', risk_level: 'low'|'medium'|'high', explanation: maxLength 500}`.
   - `llm_router.complete_with_schema(task='compare_to_template', max_tokens=600)`.
   - Per-pair fail → fall back `{status='modified', risk='medium', explanation='LLM diff lỗi ...; đánh giá thủ công.'}` (never aborts run).
6. `_bump_risk_for_keywords` — nếu clause text chứa keyword (vd "trách nhiệm" / "indemnity") → bump risk one notch (low→medium→high).
7. **Pass 2** — template clauses không trong `used_template_indices` → emit `ClauseMatch(status='missing', risk='high' (+ bump), explanation="Template có điều khoản X không xuất hiện trong candidate")`.
8. `_aggregate_risk_score(matches)` → weighted sum: missing=1.0, added=0.5, others = `_RISK_WEIGHTS[risk_level]` (low=0.1, medium=0.5, high=1.0) → normalise / `len(matches) * 1.0`.
9. Return `CompareOutput(matches, summary={match, modified, missing, added}, overall_risk_score, template_clause_count, candidate_clause_count)`.

**Cases:**
- **Golden — NDA review** — template 8 clauses (definitions / confidentiality / IP / term / governing-law / termination / liability / signatures). Candidate 9 (sneak in "data licensing" clause). Output: 7 match + 1 modified (termination notice 30d→60d) + 1 added (data licensing) + 0 missing. Risk score 0.45.
- **Alt — empty input** — both `template_blocks=[]` + `candidate_blocks=[]` → return `matches=[], summary={}, risk_score=0, template_clause_count=0, candidate_clause_count=0`.
- **Alt — template-only doc** (candidate empty) — every template clause → status='missing' high risk → overall_risk = 1.0.

**Sub-cases:**
- **LLM diff fail per pair** — vendor 502 cho 1 pair → fall back `{status='modified', risk='medium'}` cho pair đó; pair khác tiếp tục. **Never aborts run** (pattern CLAUDE.md §14c).
- **Embedding fail** — `/v1/embed` 500 cho 1 clause → vec=[] → cosine returns 0.0 → clause appear "added" (low sim). Em log `template_comparator.embed_failed`.
- **Cosine = 0 (dim mismatch)** — _cosine returns 0.0 thay vì divide-by-zero. Caller thấy sim=0.
- **Risk keyword bump cascade** — base="low" + keyword "liability" found → bump to "medium". Cap at "high".
- **default_risk_keywords** = 17 entries (10 VN + 7 EN). Caller có thể override `risk_keywords` qua `CompareInput`.
- **No TITLE in document** — extract_clauses fall back "1 clause title='' body=all". Single-clause comparison is weak but defensive.
- **Long clause > 3 KB** — `_CLAUSE_TEXT_CAP` cut; caller chấp nhận truncation hoặc pre-chunk.
- **Test injection** — `inp.llm_gateway_url` override env LLM_GATEWAY_URL cho test isolation.

**Phi chức năng:**
- **Perf:** N_template + N_candidate embed calls (~50ms each) + N_candidate × cosine O(N_template) (mili-giây) + M LLM diff calls (M = matched pair count, ~3-5s each). NDA 10 clauses → ~20 embeds + ~10 diffs → ~30-60s total. Heavy operation; caller phải gate workflow timeout.
- **K-3** ✅ embed + LLM via llm-gateway only.
- **K-4** — embed always Qwen local (schema-level pin trong `/v1/embed`). LLM diff respects `consent_external`.
- **K-17** read_only — caller persist into `contract_compare_results` table.
- **Risk model** — weighted aggregate normalised 0..1. Caller có thể remap để align với business risk taxonomy (vd 0.7+ = "BLOCK", 0.4-0.7 = "REVIEW", < 0.4 = "AUTO-APPROVE").
- **Observability:** `compare_to_template.done` với summary + risk_score. Per embed/diff fail log warning với clause indices.
- **Caveat (in CLAUDE.md):** template embedding cache em **chưa làm** — mỗi compare call em re-embed template clauses. Phase 3 optimization: cache template vectors keyed bằng `(template_id, model_version)`.

---

### 1.14 — Patterns summary table (Phase 2.5 trên 1 trang)

| Pattern | Item | Side-effect | LLM? | Timing per doc | K-rules enforced |
|---|---|---|---|---|---|
| 1 | Block taxonomy | pure (data shape) | no | 0 | — |
| 2 | Header/footer strip | pure | no | ~ms | K-17 |
| 3 | Table extraction | pure | no | ~100ms/page | K-17 |
| 4 | Reading order | pure | no | ~50-200ms/page | K-17 |
| 5 | Bbox propagation | pure | no | ~0 | K-17 (FE half: defer) |
| Det | Doc type + spoof | pure | no | ~µs | K-12 (no body-id) |
| OCR | Qwen2-VL adapter | external (local) | yes (Qwen-VL) | 3-15s | K-3/K-4 schema-pin/K-5 |
| AI-1 | classify_document | read_only | 1 call | 1-3s | K-3/K-4/K-17/K-20 |
| AI-2 | extract_structured | read_only | N calls | 3-10s × N | K-3/K-4/K-9/K-17 |
| AI-3 | summarise_document | read_only | 1 call | 2-5s | K-3/K-4/K-17/K-20 |
| AI-4 | sentiment_analysis | read_only | 1 call | 2-4s | K-3/K-4/K-5(caller)/K-17 |
| AI-5 | dedup_records | **pure** | 0 | <100ms | K-17 pure |
| AI-6 | compare_to_template | read_only | M diffs + embeds | 30-60s | K-3/K-4/K-17 |

---

## SECTION 2 — Phase 2 sprints shipped

> **Shipped:** P2-S13 / S14 / S15 / S16 / S18 / S21 / S25. **Skip:** S17 (mobile, no scope). **Deferred Phase 3:** S19/S20 (microservices extraction — ADR-0010 updated). **Not started:** S22 (fine-tune) / S23 (EN UI) / S24 (100-customer retro).

---

### 2.1 — P2-S13: Process Mining connectors (Slack/Teams + SharePoint + Webhook)

**Files:** `services/data-pipeline/ingestion/connectors/{slack_teams,microsoft_sharepoint,generic_webhook}/connector.py` + router `services/data-pipeline/routers/process_mining.py`.

**Mục đích:** Phase 1.5 đã có Gmail/Outlook + Calendar metadata connectors. Phase 2 mở rộng 3 nguồn nữa để Process Mining reconstruct workflow sessions từ event stream: Slack/Teams audit log, Microsoft SharePoint version events, Generic webhook (3rd-party).

**Quy trình chạy (registration endpoint):**
1. FE wizard "Connect Slack" → POST `/process-mining/connectors/slack-teams` với body `{channel: 'slack'|'teams', tenant_workspace_id, oauth_credential_path, poll_interval_seconds}`.
2. Router validate `X-Enterprise-Id` header (K-12 — never from body).
3. Lookup Vault path (prod) hoặc env fallback (dev) → resolve OAuth credential.
4. INSERT vào `pm_connector_sessions` với `session_id=uuid4()`, `status='registered'`, `next_poll_at=null`.
5. Return `ConnectorRegisterResponse(session_id, connector_source='slack_teams', channel, status='registered', next_poll_at=null)`.
6. **Actual polling** — Temporal worker (gated `TEMPORAL_ENABLE_WORKER=true`) consume registration rows, run cron polling, INSERT events vào Bronze + emit Redis Stream `s:{tenant}:pm.events.raw`.

**Cases:**
- **Golden — Slack audit** — admin grant scope `audit:read` → connector poll `audit.logs.v1`. Per event (file_uploaded, channel_created, message_pinned) → emit `{source: 'slack', event_type, actor, timestamp, case_hint}`.
- **Golden — SharePoint** — Graph API `sites/{id}/lists/{id}/items?$expand=versions` → version diff events.
- **Golden — Generic webhook** — caller POST `/process-mining/webhooks/{tenant}/{secret}` với schema-free JSON → connector normalize via mig 068 catalog mapping.

**Sub-cases:**
- **OAuth expired** — refresh token via Vault credential → re-store → continue. Permanent fail → set `status='error'` + alert ops.
- **Rate limit upstream** (Slack 1 req/s tier) — connector backoff exponential, never burst.
- **Webhook signature verify** — HMAC-SHA256 với per-tenant secret (Vault path). Fail → 401, log `connector.webhook.bad_signature` + tenant_id.
- **Duplicate event** (Slack replay) — composite key `(source, event_id, tenant_id)` → ON CONFLICT DO NOTHING.

**Phi chức năng:**
- **K-3 N/A** (no LLM in connectors), **K-12** ✅ (tenant from JWT only), **K-15** ✅ (audit log every connector registration).
- **Idempotency** — registration POST has Idempotency-Key header (K-13); event ingestion has natural dedup via composite key.
- **Backpressure** — Temporal worker cron interval ≥ 60s (Pydantic Field `ge=60`).
- **Observability** — per-source metrics: `pm_connector.poll.success` / `pm_connector.poll.failed` + tenant span attribute (K-19).
- **Status (CLAUDE.md):** all 3 connectors **registration surface ship**; actual polling = Temporal worker pending P15-S11+ when worker enables prod.

---

### 2.2 — P2-S14: PM advanced algorithms (5 anomalies + 2 miners + cohort)

**Files:** `services/ai-orchestrator/org_intel/process_mining/{anomalies,inductive_miner,fuzzy_miner}.py` + cohort module.

#### 2.2.1 — 5 anomaly detectors (PM-ANM-023..027)

**`detect_approval_bypass`** — cases skip required approver step.
- Input: EventLog + required_approver_step + sample_limit.
- Per case (qua `infer_cases`): nếu `required_approver_step ∉ sequence` → BypassEvent.
- Use case: "Was finance director sign-off skipped on any invoice approval?"

**`detect_rework_loops`** — same activity fires N>1 in 1 case.
- Per case Counter activity → if any count > 1 → ReworkLoop.
- Use case: customer support ticket reopened 3 times → coaching signal.

**`score_bypass_risk`** (PM-ANM-025) — high-value bypass = high risk.
- `score = base_severity × revenue_at_risk_factor`, capped 1.0.
- Risk band: low (<0.3) / medium / high / critical (≥0.85).
- Use case: $50K invoice bypass = critical; $5 expense bypass = low.

**`analyze_conformance`** (PM-ANM-026) — actual vs designed workflow.
- Compute LCS (Longest Common Subsequence) between designed and actual sequence.
- `conformance_score = LCS_len / max(|designed|, |actual|)`.
- Threshold: 1.0 = perfect; ≥ 0.8 = acceptable; < 0.6 = significant drift.

**`token_replay`** (PM-ANM-027) — Petri-net fitness simulation.
- Single-token marking → fires when actual activities arrive in designed order.
- `fitness = 1 - tokens_missing / total_expected`.
- Today simplified; full Petri-net replay = Phase 2.5 follow-up.

**Cases:**
- **Golden** — 1000 invoice approval cases, required_approver_step='finance_director_sign'. Of these 12 bypass → all 12 returned (within sample_limit).
- **Alt — no bypass** — every case has required step → return `[]`.
- **Alt — sample_limit reached** — 500 bypass cases, sample_limit=100 → return first 100, callers see 100 = sample, not total.

**Sub-cases:**
- **Empty event log** → return `[]` (no infer_cases yields).
- **Case w/o case_id** → fall back to `event_id` as case_id.
- **Multi-required step** — caller pass list ≠ single string → today only single string supported; chain calls if multi.

**Phi chức năng:**
- **Perf:** O(N events) for infer_cases + O(C cases × seq_len) per detector. 10K events / 500 cases → < 500ms.
- **K-17 PURE** — no I/O, no LLM, deterministic. Test methodology established at `tests/test_p2_s14_pm_algorithms.py` (8-section template: chuẩn chỉ + edge + perf + non-functional).
- **K-3 / K-5 N/A**.
- **Determinism** — same EventLog twice → same anomaly list bytes-for-bytes.

#### 2.2.2 — Inductive + Fuzzy Miners (PM-ALG-016/017)

**Inductive Miner** — discover process model from event log.
- Algorithm: alpha-relations → directly-follows graph → recursively cut into operators (sequence / parallel / choice / loop).
- Output: ProcessTree với operator + children + activities.

**Fuzzy Miner** — frequency-thresholded process map.
- Compute edge frequency → drop edges below cutoff → significance + correlation metrics.
- Output: FuzzyModel với nodes + edges with weights.

**Cases:**
- **Golden** — well-structured order workflow → Inductive Miner returns clean tree `seq(receive, parallel(verify_inventory, verify_payment), ship)`.
- **Alt — noisy log** — Fuzzy Miner better; Inductive may return choice over noise.

**Sub-cases:**
- **Empty log** → ProcessTree với 0 activities.
- **Single trace** — degenerate; Inductive returns flat sequence.
- **Self-loops** — both miners handle; Inductive emits loop operator, Fuzzy emits self-edge.

**Phi chức năng:**
- **Perf:** O(E²) for alpha-relations on event count. 100K events → ~10s; pre-aggregate to directly-follows for prod scale.
- **K-17 PURE**.
- **Determinism** ✅.

#### 2.2.3 — Cohort comparison (AI-HSC-016)

**Mục đích:** "How does the workflow for new customers differ from veterans?" — compare 2 cohorts of cases for divergent paths.

**Quy trình chạy:**
1. Caller pass `EventLog` + `cohort_a_filter_fn` + `cohort_b_filter_fn`.
2. Partition cases by predicate.
3. Per cohort: compute activity frequency + path frequency + duration stats.
4. Diff: activities only in A / only in B / freq ratio difference > threshold.
5. Return `CohortComparison` with delta_activities + delta_paths + duration_distribution.

**Cases:**
- **Golden** — cohort A = new customers (signup < 30d), cohort B = veterans → discover "new customers loop in onboarding 2x more than veterans".

**Phi chức năng:** O(N events) + O(P paths) per cohort. K-17 pure.

---

### 2.3 — P2-S15: Visual workflow builder (45 nodes + 25 templates)

**Files:** `services/ai-orchestrator/routers/workflow_builder.py` + `agents_studio_builder.py` + mig 068 `node_type_catalog` + mig 069 templates.

**Mục đích:** FE Studio drag-drop builder. 45-row `node_type_catalog` = all node types (ai-classify / db-write / approval-gate / branch / merge / external-api / etc.). 25 templates = production-ready workflows per industry vertical.

**Quy trình chạy (builder flow):**
1. FE loads palette qua `GET /shared/agents/studio/builder/palette` → 28 curated nodes (subset of 45) với category + icon + sample config.
2. FE drag node to canvas → `POST /workflows/{id}/nodes` với `node_type` (must exist in `node_type_catalog`) + `position` + `config_json`.
3. Server validate `config_json` against catalog row's `config_schema_json` (JSON Schema).
4. FE connect 2 nodes → `POST /workflows/{id}/edges` với `from_node_id`, `to_node_id`, `condition_expr` (optional).
5. FE save workflow → `POST /workflows` final → validate full graph (DAG check + side_effect_class K-17 on every node).
6. `GET /workflows/{id}/export.yaml` cho Workflow-as-Code (P2-S16 add).
7. `POST /workflow-templates/instantiate/{template_id}` → clone template thành workflow mới của tenant.

**Cases:**
- **Golden — from scratch** — FE drag 5 nodes (upload → classify → approval-gate → db-write → notify) → save → run.
- **Golden — from template** — `POST /workflow-templates/instantiate/contract-approval-v2` → clone mig 069 row → ready to customize.
- **Alt — invalid config** — `config_json` không match `config_schema_json` → 422 RFC 7807 với pointer to bad field.
- **Alt — cycle in graph** — DAG check fail → 422 `WORKFLOW.CYCLE_DETECTED`.
- **Alt — K-17 missing** — node config thiếu `side_effect_class` → 422 hint "every node must declare side_effect_class".

**Sub-cases:**
- **node_type không trong catalog** → 422 `NODE_TYPE_NOT_FOUND` (whitelist by mig 068).
- **Concurrent edit** — 2 users edit same workflow → P2-S16 lock token handles (xem 2.4).
- **Template instantiate quá nhiều** — caller spam → rate limit 10/min per tenant.

**Phi chức năng:**
- **Perf:** palette load static 28 rows → <50ms. Workflow save = single tx INSERT nodes + edges → ~100-200ms for 20-node workflow.
- **K-1 / K-12** ✅ tenant scoping.
- **K-17** enforced at save time (every node `side_effect_class ∈ {pure, read_only, write_idempotent, write_non_idempotent, external}`).
- **Observability:** workflow_builder.save / template.instantiate metrics + tenant span.
- **Test coverage:** 35 tests, palette + catalog + node config + DAG + template.

---

### 2.4 — P2-S16: Multi-user collab + Workflow as Code

**Files:** `services/ai-orchestrator/routers/{workflow_collab,workflow_yaml}.py` + mig 072 `{workflow_editors,workflow_comments,workflow_locks}`.

**Mục đích:** Phase 1 = single editor. Phase 2 = team collab — assignments (OWNER/EDITOR/REVIEWER/VIEWER) + threaded comments per-node + optimistic locks. Plus Workflow as Code (YAML import/export validated against mig 068 catalog).

#### 2.4.1 — Editors (assignments + roles)

**Quy trình chạy:**
1. `POST /workflows/{id}/editors` body `{user_id, role}` → INSERT vào `workflow_editors`, set `invited_by = JWT.user_id`, `accepted=false`.
2. Email/in-app notif sent (notification-service).
3. Invitee `PATCH /workflows/{id}/editors/{user_id}` body `{accepted: true}` → flip flag.
4. `GET /workflows/{id}/editors` returns list.

**Sub-cases:**
- OWNER cannot demote self below OWNER → 409 INVARIANT_OWNER_REQUIRED.
- Remove last OWNER → 409.
- Promote VIEWER to EDITOR without OWNER permission → 403.

#### 2.4.2 — Comments (threaded + node-anchored)

**Quy trình chạy:**
1. `POST /workflows/{id}/comments` body `{body, node_id?, parent_comment_id?}` → INSERT.
2. `node_id` set → anchor to specific node (FE bubble on canvas).
3. `parent_comment_id` set → reply thread (1 level deep).
4. `PATCH /comments/{cid}` body `{body?, resolved?}` → edit body OR mark resolved.
5. `GET /workflows/{id}/comments?node_id=...&resolved=false` filter.

**Sub-cases:**
- Comment author edit own → OK. Non-author edit → 403.
- Mark resolved → records `resolved_by = JWT.user_id`, `resolved_at = now()`.
- Reply to resolved comment → unresolve parent (or keep — caller flag).

#### 2.4.3 — Locks (K-13 anti-IDOR lock_token)

**Quy trình chạy:**
1. User A `POST /workflows/{id}/lock` body `{ttl_seconds: 600, intent: 'edit'}` → server check no existing live lock → INSERT với `lock_token=uuid4()`, return token.
2. User A PATCH/DELETE any workflow resource → must include `lock_token` header.
3. User A `DELETE /workflows/{id}/lock` body `{lock_token}` → release.
4. User B `POST /workflows/{id}/lock` while live → 409 LOCK_HELD với `held_by_user_id` info.
5. TTL expire → background sweeper marks released (or first new lock attempt → auto-release expired).

**Sub-cases:**
- Stolen lock_token (user A token used by user B) → K-13 server cross-check `held_by_user_id == JWT.user_id` → 403.
- User abandons lock (browser crash) → TTL 600s default; user can extend `POST /lock` again before expiry.
- Multi-tab same user → re-acquire returns existing lock_token (idempotent).

#### 2.4.4 — Workflow as Code (YAML import/export)

**Quy trình chạy:**
1. Export: `GET /workflows/{id}/export.yaml` → serialise nodes + edges + config → validate against mig 068 catalog → return YAML.
2. Import: `POST /workflows/import` body `{yaml: '...'}` →
   - Parse YAML.
   - Validate every node_type against mig 068.
   - Validate every node config_json against catalog config_schema_json.
   - Validate DAG (no cycle).
   - INSERT new workflow + nodes + edges as fresh resources (preserves source-of-truth pattern).
3. Round-trip — export then import → semantically equivalent (test pin).

**Sub-cases:**
- YAML invalid syntax → 422 with line/col pointer.
- node_type unknown → 422 `NODE_TYPE_NOT_FOUND` (whitelist).
- Cycle → 422.
- Importing same YAML twice → 2 distinct workflows (no upsert; intentional).

**Phi chức năng (P2-S16 toàn bộ):**
- **K-1 / K-12** tenant scoping mọi route.
- **K-13** lock_token anti-IDOR ✅.
- **K-15** audit log per editor/comment/lock change.
- **Perf:** comment list paginated cursor-based.
- **Observability:** workflow_collab.* metrics; lock contention histogram.
- **Test coverage:** 28 tests P2-S16 (locks K-13 IDOR + editors + comments + YAML round-trip), 15 tests P2-S15 import follow-up.

---

### 2.5 — P2-S18: Observability deep-dive

**Files:** `services/ai-orchestrator/org_intel/observability/{anomaly_detector,capacity_planning,session_replay}.py` + router `observability.py` + mig 073.

**Mục đích:** Phase 1 đã có Prometheus + Loki + Jaeger basic. Phase 2 thêm 3 deep-dive feature: OBS-018 anomaly detection trên metrics, OBS-021 capacity planning forecast, OBS-023 opt-in session replay.

#### 2.5.1 — OBS-018: Metric anomaly detection (z-score + EWMA)

**Quy trình chạy:**
1. Caller pass time-series `list[(timestamp, value)]` + `method='zscore'|'ewma'`.
2. Z-score path: compute mean + stddev → flag points where `|value - mean| / stddev ≥ threshold` (default 3.0).
3. EWMA path: exponentially-weighted moving avg + variance → flag drift.
4. Return `AnomalyResult(anomalies: list[(ts, value, score)], baseline_stats)`.

**Cases:**
- **Golden — request latency spike** — p99 normally 200ms suddenly 2s for 5min → z-score flags points.
- **Alt — gradual drift** — EWMA catches; z-score doesn't (mean shifts with series).

**Sub-cases:**
- **Cold start** — < 30 points → return `insufficient_data`.
- **All-zero series** — stddev=0 → can't compute z-score → return early with warning.

#### 2.5.2 — OBS-021: Capacity planning (linear regression forecast)

**Quy trình chạy:**
1. Input: time-series of resource (CPU / memory / disk).
2. Linear regression on last N days → slope + intercept.
3. Project forward → "days until threshold reached" (vd 90% disk).
4. Return `CapacityForecast(current_value, projection_curve, days_until_threshold)`.

**Cases:**
- **Golden** — disk 60% growing 1%/day → forecast says 30 days until 90% → ops can plan upgrade.
- **Alt — negative slope** — usage decreasing → return "no exhaustion projected".

**Sub-cases:**
- **Non-linear trend** — exponential growth (DB log table) → linear forecast underestimates → caller should escalate to ML regression Phase 3.
- **Noisy data** — high R² uncertainty → return `confidence='low'` flag.

#### 2.5.3 — OBS-023: Session replay (opt-in, mig 073)

**Mục đích:** Replay FE user session for support investigation. **Opt-in** — tenant must enable per-feature flag + user consent banner.

**Quy trình chạy:**
1. Tenant admin enable `session_replay_enabled=true` trong tenant settings.
2. FE shows opt-in banner; user click "Accept" → SDK starts recording DOM events.
3. Replay SDK posts events to `POST /observability/session-replay/{session_id}/events` (batched 5s window).
4. Support agent later `GET /observability/session-replay/{session_id}` → replays in admin tool.

**Sub-cases:**
- **PII redaction** — input fields với `data-pii=true` mask before recording (caller side).
- **No consent** — SDK doesn't record; backend rejects events 403.
- **Retention** — events auto-purge after 30 days (mig 073 partition by ts).

**Phi chức năng (P2-S18 toàn bộ):**
- **K-1 / K-12** tenant scoping.
- **K-5** PII redaction in replay (caller).
- **K-17** anomaly + capacity = pure compute; session replay = write_idempotent (event batch INSERT).
- **Test coverage:** 36 tests.

---

### 2.6 — P2-S21: T-Cube reasoning + OKR + NOV-RPT-023/024

#### 2.6.1 — T-Cube trace-augmented reasoning (ADR-0021, paper arXiv 2605.03344)

**Files:** `services/ai-orchestrator/reasoning/trace_distiller/{transformer,worker,runner,prompts}.py` + `reasoning/rag/engines/trace_recall.py` + `reasoning/augment.py`.

**Mục đích:** Mỗi `decision_audit_log` row có `reasoning` field (raw thinking trace). T-Cube distil mỗi row thành **3 forms**: Struct (facts SPO triples), Semantic (paraphrase), Reflect (lesson learned). Store as L4 PROCEDURAL memory; future prompts retrieve trace context để augment reasoning.

**Quy trình chạy:**
1. Cron worker `trace_distiller.worker` cứ 10 phút quét `decision_audit_log` for new rows.
2. Per row → `ThinkingTrace(source_decision_id, tenant_id, raw_text, problem_context, source_llm_provider, source_llm_version)`.
3. `transformer.distill(form, trace)` × 3:
   - Struct: call LLM với `prompts.STRUCT_PROMPT` → JSON facts → SPO list.
   - Semantic: prompt VN → paraphrase ~500 tokens.
   - Reflect: prompt → "lesson learned" form.
4. Per form → embed via BGE-M3 → INSERT vào `memory_l3` (PROCEDURAL) với `metadata.tcube_form ∈ {struct, semantic, reflect}`.
5. Retrieval: `reasoning/rag/engines/trace_recall.py` (4th RAG engine) — query embedded similar past traces during new LLM call → augment prompt.

**Cases:**
- **Golden** — manager approve credit increase 50M → decision_audit_log row có reasoning "Customer history clean, 24mo on-time payment, revenue trend +15%". T-Cube distil → 3 records. Next similar decision (customer X+1) → trace_recall returns past similar reasoning → augmented prompt includes "Em đã từng quyết tương tự cho khách Y; outcome ...".
- **Alt — distill fail** — LLM 502 → log + skip; cron retry next tick.

**Sub-cases:**
- **K-20 model pinning** — `source_llm_version` carried through; future drift detection.
- **Tenant isolation** — `memory_l3` RLS by tenant_id.
- **Dedup** — re-distill same row → ON CONFLICT (source_decision_id, tcube_form) update.

**Phi chức năng:**
- **Perf:** 3 LLM calls per decision row. 100 decisions/hour × 3 = 300 calls/hour. Qwen Ollama can absorb.
- **K-3** ✅ via llm-gateway. **K-4** Qwen default. **K-17** write_idempotent (memory store). **K-20** version pinned.
- **Test coverage:** 79 tests T-Cube + cron + real llm-gateway adapter.

#### 2.6.2 — OKR framework (P2-M212-001)

**Files:** `services/ai-orchestrator/routers/okr.py` + mig 071.

**Mục đích:** Multi-level OKR tracker: company → department → individual. Linked to workflow templates qua mig 071.

**9 endpoints:** `POST /p2/strategy/okr` (create) + `GET /list` + `PATCH /{id}` (progress) + `DELETE` + `GET /{id}/children` (tree drill) + `POST /{id}/key-results` + `PATCH /key-results/{id}` (progress 0..100) + workflow link mapping + report endpoint.

**Quy trình chạy:**
1. Manager create company OKR `POST /p2/strategy/okr` body `{objective, period_q, parent_id=null}`.
2. Add key results `POST /{id}/key-results` body `{name, target_value, unit}`.
3. Department head create child OKR with `parent_id=<company OKR>`.
4. Individual link workflow to OKR via mig 071 `workflow_okr_links`.
5. Per workflow run completed → KR progress auto-bump (driven by workflow output).

**Sub-cases:**
- Circular OKR parent (A→B→A) → 422.
- Delete OKR with children → 409 cascade required.

#### 2.6.3 — NOV-RPT-023 (recommendations) + NOV-RPT-024 (simulation)

**Files:** `services/ai-orchestrator/org_intel/economics/{recommendations,simulation}.py`.

**Mục đích:** NOV (North-of-Value) layer — biz recommendations + what-if simulation.

**Recommendations flow:** Analyze last 90d NOV signals → emit ordered list `[{action, expected_lift_vnd, confidence, evidence_decision_ids}]`. Caller (CFO digest) renders.

**Simulation flow:** Given a hypothetical action → forecast NOV trajectory next 30 days with confidence band. Monte Carlo if `confidence_method='mc'`, deterministic projection if `confidence_method='linear'`.

**Sub-cases:**
- Sparse data — < 30 days history → return `confidence='insufficient'`.
- Simulation diverging → cap projection at 3× current value, flag instability.

**Phi chức năng (P2-S21 toàn bộ):**
- **K-3 / K-4 / K-17 / K-20** ✅.
- **Perf:** OKR endpoints cursor paginated. Recommendations/simulation pre-compute snapshot in MV (Phase 2.6).
- **Test coverage:** 79 T-Cube + 36 OKR/NOV.

---

### 2.7 — P2-S25: SSO + MFA + field encryption

**Files:** `services/ai-orchestrator/{routers/sso.py,shared/{crypto,totp,field_key_rotation}.py,sso_providers/}` + `services/auth-service/src/main/java/com/kaori/auth/sso/*.java` + migs 074 + 080 + 083.

#### 2.7.1 — SSO Google + Microsoft (P2-AUTH-001)

**Quy trình chạy (Google golden path):**
1. FE login page → click "Sign in with Google" → `GET /p2/auth/sso/google/start?return_url=<FE>`.
2. ai-orch generate `state_token = secrets.token_urlsafe(32)` → INSERT vào `sso_oauth_state` với TTL 10min.
3. Return Google authorization URL với state embedded.
4. Browser redirects to Google → user authenticates → Google redirects to `GET /p2/auth/sso/google/callback?code=<X>&state=<S>`.
5. ai-orch verify state (consume row, check expired) → exchange code for Google access_token + id_token.
6. Parse id_token → email + sub (Google user ID) → lookup `sso_identities` table by `(provider, provider_user_id)`:
   - **Match found** → load `user_id` + `enterprise_id`.
   - **No match + auto-provision allowed** → create user + sso_identity (tenant must enable).
   - **No match + not auto-provision** → 403 `SSO.UNREGISTERED_USER`.
7. Generate one-shot `sso_code = secrets.token_urlsafe(32)` (TTL 60s) → INSERT vào `sso_exchange_codes`.
8. Redirect browser to FE `<return_url>?sso_code=<X>`.
9. FE page `/sso-callback` reads sso_code → POST `auth-service/api/v1/auth/sso/exchange` body `{sso_code}`.
10. auth-service Java POST `/p2/auth/sso/exchange-info` (internal — `X-Internal-Service-Token` shared secret) → ai-orch validates code + returns `{user_id, enterprise_id, sso_identity_id}` + marks consumed.
11. auth-service load user → generate RS256 JWT → return to FE.
12. FE stores JWT → proceeds as if password login.

**Cases:**
- **Golden Google** — `nguyentruongan25051997@gmail.com` user click → redirects → consents → callback → FE shows logged-in state. **End-to-end LIVE 2026-05-18** (commit `6c92b69`).
- **Holstered Microsoft** — Microsoft adapter code-complete since `53421b7` + `fa58712` (array-driven SSO provider buttons). Activation = `MICROSOFT_CLIENT_ID/SECRET/TENANT_ID` env. Runbook ship `f3e09bb`.

**Sub-cases:**
- **state expired** (> 10min) → 400 `SSO.STATE_EXPIRED`.
- **state already consumed** (replay) → 400.
- **id_token signature invalid** → 401 `SSO.INVALID_TOKEN`.
- **sso_code already consumed** → 401 (race condition between FE and auth-service).
- **JWT RS256 private key access** — stays inside auth-service per security boundary (split design from `routers/sso.py:42`).
- **Multi-tenant mismatch** — sso_identity's enterprise_id != JWT's enterprise → reject (current single-tenant SSO per identity).

**Phi chức năng:**
- **K-1 / K-12** tenant from sso_identity + JWT, never query.
- **K-5** — Google id_token contains email; OK to log (not PII per consent grant).
- **K-15** — every SSO start/callback/exchange logged.
- **K-18** Vault — Google client_secret in Vault path `platform/sso/google_oauth` prod (env fallback dev).
- **Observability:** `sso.start` / `sso.callback.success|failed` / `sso.exchange.consumed`.

#### 2.7.2 — MFA TOTP (P2-AUTH-002)

**Files:** `services/ai-orchestrator/shared/totp.py` + auth-service Java `TotpService`.

**Quy trình chạy:**
1. User enable MFA → `POST /p2/auth/mfa/enroll` → server generates 20-byte secret via `secrets.token_bytes(20)`.
2. Encrypt secret với `KAORI_MFA_KEY` (Vault prod, env dev fallback) → AES-256-GCM với IV 12B → `base64(IV || ciphertext)` wire format matching Java TotpService.
3. INSERT vào `user_mfa_secrets` (mig 074) với encrypted secret.
4. Return TOTP URI `otpauth://totp/Kaori:{email}?secret=...&issuer=Kaori` → FE renders QR code.
5. User scans qua Google Authenticator → enters 6-digit code → `POST /p2/auth/mfa/verify` body `{code}` → server compute `totp_code(decrypt(stored_secret), at=now)` with ± 30s drift window → match → flip `mfa_enabled=true`.
6. Subsequent login → after password → 401 require MFA → user submits code → JWT issued only if match.

**Sub-cases:**
- **Drift window** — accept codes from `[now-30s, now, now+30s]` (3 steps) for clock skew.
- **Recovery codes** — generate 10 single-use codes at enroll → user prints → if phone lost → recovery code can disable MFA temporarily.
- **Brute force** — rate limit 5 failed verify per minute per user; lock 15min after 10 fails (K-5 spirit).

**Phi chức năng:**
- **K-18 Vault** — `KAORI_MFA_KEY` resolves from Vault path `platform/encryption/mfa_master_key` prod profile; env fallback dev with warning log.
- **Cross-service** — Python `shared/totp.py` + Java `TotpService` produce same wire format for cross-verify (decryption + code generation identical).
- **Test coverage:** 43 tests P2-S25 covering TOTP + encryption + field-level.

#### 2.7.3 — Field-level encryption (P2-ENC-001) + Field-key rotation (F-NEW11)

**Files:** `services/ai-orchestrator/shared/{crypto,field_key_rotation}.py` + migs 074 + 080.

**Mục đích:** Per-tenant field-level encryption for sensitive PII columns (vd customer SSN, salary). Key per tenant; rotation supported; old ciphertext stays decryptable.

**Quy trình chạy (encrypt path):**
1. Tenant onboarded → `generate_key_b64()` → 32-byte AES key.
2. Store in Vault path `tenant/{id}/encryption/field_key_<timestamp>` prod → write `key_ref='vault:<path>'` into `tenant_field_keys`.
3. App code wants to write `customer.ssn`:
   - `wrapped = resolve_tenant_key(tenant_id, key_ref, vault_client)`.
   - `ciphertext_b64 = encrypt_field("123-45-6789", wrapped)`.
   - INSERT into `customer.ssn_enc` column.
4. Read path: `plaintext = decrypt_field(ciphertext_b64, wrapped)`.

**Quy trình chạy (rotation path — F-NEW11 fix):**
1. `POST /p2/auth/field-key/rotate` → generate new key → Vault write to new timestamped path → INSERT vào `tenant_field_keys_history` (mig 080) — preserves old `key_ref` so existing ciphertext stays decryptable.
2. Update `tenant_field_keys.key_ref` to new path.
3. `POST /p2/auth/field-key/reencrypt` → background worker `field_key_rotation.py`:
   - Iterate all encrypted columns in tenant scope.
   - For each row: decrypt with **old** key (lookup history) → encrypt with new key → UPDATE in place.
   - Mark row's `key_version` to current.
4. `GET /p2/auth/field-key/reencrypt/status` → progress dashboard.

**Cases:**
- **Golden — rotate without re-encrypt** — new keys in use for new writes; old rows still decryptable via history lookup.
- **Golden — full re-encrypt** — worker iterate all rows → all rows on new key → history can be archived.

**Sub-cases:**
- **Closed bug — pre-F-NEW11** — rotate **overwrote** `key_ref` in-place → all old ciphertext became undecryptable (silent data loss). Fix: add `tenant_field_keys_history` table + lookup-fallback.
- **Vault path missing** — production profile + bad Vault → raise K-18 enforcement error, refuse env fallback.
- **Wrong key tried** — decryption fails authenticated decryption → caller iterate history backward.

**Phi chức năng:**
- **K-18 Vault enforcement** — production must Vault; dev profile env fallback with warning.
- **AES-256-GCM** — authenticated encryption; tamper detection built-in.
- **Test coverage:** 41 follow-up tests (mig 080 + re-encrypt worker + 2 endpoints).
- **Observability:** `field_key.rotate` / `field_key.reencrypt.{started,row_done,completed}` metrics.

---

## SECTION 3 — Phase 1.5 sprints shipped (P15-S9 → S12)

> 4 sprints close 2026-05-17 (`feat/p15-s9-d1` HEAD bumped 110+ commits ahead at sprint close). Test deltas Phase 1.5 toàn bộ: ai-orch 514→1261 / notif 31→58 / pipeline 366→~510 / llm-gw 96→102. Deferred to Phase 2: K8s FPT Cloud provision, Temporal worker live cutover, dual-write cutover, Postgres CDC real, Zalo metadata connector real, PageIndex PyPI wrap (runbook ship Phase 2).

---

### 3.1 — P15-S9: Adoption signals full + interventions + PM connectors foundation

**Mục đích sprint:** Phase 1 đã có Adoption skeleton + 3/9 signals. P15-S9 lên đủ 9 signals + intervention engine + RAG router skeleton + NOV revenue dispatcher.

#### 3.1.1 — 9 Adoption signals (PM-EVT-001..009)

**File:** `services/ai-orchestrator/org_intel/adoption/signals.py` + `cohort.py` + `intervention_engine.py` + `intervention_tracker.py` + `health_score.py`.

**Mục đích:** Tổng hợp 9 signal đo "khách dùng Kaori sâu/nông": login frequency, feature breadth, decision rate, integration adoption, workflow runs, report generation, alert response, framework switch, multi-user.

**Quy trình chạy:**
1. Cron worker (10 phút/lần) read events from Redis Streams `s:{tenant}:adoption.raw`.
2. Compute 9 signals per tenant qua `signals.compute_health(events)`:
   - login_frequency_score (last 30d)
   - feature_breadth_score (unique features used)
   - decision_rate_score (decisions taken / opportunities)
   - integration_adoption_score (connectors active)
   - workflow_runs_score (workflows fired)
   - report_generation_score (reports created)
   - alert_response_score (alerts acted on within SLA)
   - framework_switch_score (multi-framework usage)
   - multi_user_score (active editor count)
3. Weighted aggregate → `health_score 0..100`.
4. `intervention_engine.suggest(health, signals)` → recommend actions: re-onboarding, customer success call, feature spotlight email.
5. `intervention_tracker.persist(interventions)` → INSERT `tenant_interventions` table.
6. `cohort.compare(cohorts)` for benchmark ("Your decision_rate 0.4 vs peer median 0.7").

**Cases:**
- **Golden — healthy tenant** — all 9 signals > 0.7 → health 85 → no intervention.
- **Risk — declining** — login_frequency drops < 0.3 last 7d → intervention "Customer Success call within 24h".

**Sub-cases:**
- **No data tenant** (just onboarded) → all signals 0 → health=0 → "early life" intervention "send onboarding playbook".
- **Skewed weights** — caller pass custom weights to `compute_health`.

**Phi chức năng:**
- **K-17:** signals = pure compute. interventions = write_idempotent (per-tenant per-day dedup).
- **K-1 / K-12** tenant scoping.
- **Perf:** ~50ms per tenant aggregate, scales linear.
- **Test coverage:** 9/9 signals shipped trước P15-S9 thực ra (CLAUDE.md memory ghi "9/9 ship trước rồi"). P15-S9 D-piece chính = intervention engine + tracker + cohort.

#### 3.1.2 — NOV revenue estimate (5 methods, dispatcher)

**File:** `services/ai-orchestrator/org_intel/economics/revenue_estimator.py` + router `economics.py`.

**Mục đích:** Estimate revenue impact của một intervention/decision. 5 methods: cohort_delta / linear_regression / decision_tree / monte_carlo / dcf.

**Quy trình chạy:**
1. `POST /economics/revenue/estimate` body `{method, signals, params}`.
2. Dispatcher route theo method:
   - `cohort_delta` — compare actioned vs control cohort revenue.
   - `linear_regression` — fit y=ax+b from history.
   - `decision_tree` — tree split on key signals.
   - `monte_carlo` — N=1000 sim with random params.
   - `dcf` — discounted cash flow projection.
3. Return `RevenueEstimate(point_estimate, confidence_band, method, evidence)`.

**Sub-cases:**
- **Insufficient history** (<10 actions) → 422 `INSUFFICIENT_DATA`.
- **NaN result** (singular matrix) → fall back simpler method + flag.

**Phi chức năng:** K-17 pure. Test coverage 5 tests. Pin method outputs deterministic via fixed seed.

#### 3.1.3 — RAG router skeleton (3 engines)

**File:** `services/ai-orchestrator/reasoning/rag/router.py` + engines `pgvector_stub|real`, `pageindex_engine`, `docsage_stub`.

**Mục đích:** Dispatcher dispatch query đến best RAG engine based on signal:
- pgvector — flat doc embedding for general semantic search.
- pageindex — vectorless tree retrieval (ADR-0019) for long structured docs.
- docsage — schema-aware retrieval for tabular/Q&A.
- trace_recall (P2-S21 add) — past decision traces.

**Quy trình chạy (qua /rag/answer P15-S10 HTTP):**
1. `POST /rag/answer` body `{query, enterprise_id, task_type?, top_k=5}`.
2. Router dispatch theo `task_type`:
   - `factual_long_doc` → pageindex_engine.
   - `tabular` → docsage_engine.
   - `reasoning` → trace_recall (nếu `RAG_TRACE_RECALL_ENABLED=true`).
   - else → pgvector_real (BGE-M3 embedding).
3. Engine returns `Chunk[]` with `(text, citation, score)`.
4. CDFL reranker (Phase 1.5 in-memory) bump signal Information Gain.
5. Final LLM compose answer with citations.
6. Return `{answer, citations: [{doc_id, page, snippet}], trace_id}`.

**Sub-cases:**
- **No chunks found** → answer `"Em chưa tìm thấy thông tin liên quan..."` + empty citations.
- **Engine fail** → fallback to next engine in priority list.

**Phi chức năng:**
- **K-3** ✅ via llm-gateway.
- **K-12** tenant scoping every chunk fetch (RLS `tenant_id`).
- **Perf:** embed ~50ms + retrieval ~100ms + LLM compose 2-4s.

---

### 3.2 — P15-S10: NOV A/B + PM connector HTTP + RAG /answer + revenue dispatcher

**Mục đích sprint:** Library code Phase 1.5 đã có, P15-S10 wire HTTP layer + finish RAG router stack + add NOV A/B + PageIndex stub builder.

**5 endpoints wired (CLAUDE.md §14a):**

| Endpoint | Router | Test |
|---|---|---|
| `POST /rag/answer` | `routers/rag.py` | 6/6 |
| `POST /adoption/interventions/trigger` | `routers/adoption.py` | 5/5 |
| `POST /economics/revenue/estimate` | `routers/economics.py` | 5/5 |
| `POST /process-mining/connectors/gmail-outlook` | `data-pipeline/routers/process_mining.py` | 4/8 |
| `POST /process-mining/connectors/calendar` | same | 2/8 |

**Quy trình chạy chung — adoption intervention trigger:**
1. Cron compute health score (P15-S9 §3.1.1).
2. health_score drop > threshold → `intervention_engine.suggest(...)` returns `interventions=[...]`.
3. Trigger via `POST /adoption/interventions/trigger` body `{tenant_id, intervention_type, params}` (idempotency K-13).
4. Intervention executes:
   - Email — notification-service SMTP outbox.
   - Customer Success call — create CRM task (placeholder; integration phase 2).
   - Feature spotlight — push to user inbox.
5. INSERT `tenant_interventions` row with status='triggered'.
6. Track outcome — next health snapshot 7d later → compute lift.

**Sub-cases:**
- **Duplicate trigger same day** — idempotency dedup per `(tenant_id, intervention_type, date)`.
- **No active editor** — skip in-app intervention; fall back email only.

**Phi chức năng:** 
- **K-13 idempotency** Redis 24h.
- **K-15 audit** every trigger logged.
- **Perf:** trigger 50-200ms (DB insert + notif queue push).

---

### 3.3 — P15-S11: DocSage + Stage 5/7/12 + Phase 2 storage adapters

**Mục đích sprint:** Biggest Phase 1.5 sprint — close DocSage Schema Discovery pipeline + open Stage 5 (Ontology) + Stage 7 (Memory) + Stage 12 (Loop) + lay Phase 2 storage adapter foundation.

#### 3.3.1 — DocSage Schema Discovery D1→D6 end-to-end

**Mục đích:** Auto-discover schema from uploaded doc (PDF / DOCX / CSV with header chaos). Reduce manual mapping.

**Quy trình chạy:**
1. Upload completes Bronze ingest + Silver extraction → blocks list.
2. DocSage `analyze(blocks)`:
   - **D1 — chunk + classify** blocks by likely semantic (header / data row / footer / annotation).
   - **D2 — type infer** per column: detect numeric / date / categorical / freetext.
   - **D3 — semantic role** infer per column: customer_id / amount / date / category (LLM-assisted).
   - **D4 — confidence aggregate** per column + global mapping_confidence.
   - **D5 — schema fingerprint** SHA-256 of `(column_names normalised, types, semantics)`.
   - **D6 — propose Silver schema** + auto-fill mapping_template_id if fingerprint matches a known template.
3. Return `SchemaProposal(columns, mapping_template_id?, confidence)`.

**Cases:**
- **Golden — known shape** — Customer CSV upload → fingerprint match `mig_054_template_customer_v1` → auto-fill mapping.
- **Alt — novel shape** — propose new template → user confirms → INSERT into `mapping_templates`.

**Sub-cases:**
- Multi-table doc — D1 emits 2 separate schema proposals.
- Unicode/diacritic column names — `vn_normalise()` before fingerprint hashing.

**Phi chức năng:**
- **K-3** ✅ LLM via gateway. **K-4** Qwen default. **K-17** read_only.
- **Perf:** 1-3 LLM calls per doc, < 10s.
- **Test coverage:** 6 commits D1→D6 (`7a47b17`..`c6e47c5`).

#### 3.3.2 — Stage 5 Ontology 7-Primitives

**File:** `services/ai-orchestrator/reasoning/ontology/{types,store,in_memory,neo4j_store}.py`.

**Mục đích:** Universal ontology for ANY business: 7 primitives = `Customer, Transaction, Product, Location, Time, Channel, Outcome`. Cross-tenant standard so reasoning ports.

**Quy trình chạy:**
1. Silver row → `OntologyMapper.project(row, template_id)` → `Primitives(customer, transaction, ...)`.
2. INSERT vào `ontology_nodes` (Postgres in-memory store dev / Neo4j adapter prod).
3. Build relationships (Customer—buys→Product) → `ontology_edges`.
4. Reasoning queries: `OntologyStore.query("customers who bought in Q1 from channel X")`.

**Sub-cases:**
- Primitives missing (vd no Channel detected) → `null` in node; queries handle.
- Multi-tenancy — Neo4j path uses label `_T_<hash[:16]>` to isolate.

**Phi chức năng:**
- **K-1 / K-12** ✅ tenant label.
- **K-17:** in_memory pure; neo4j store = write_idempotent.
- **Test coverage:** 18 tests `7c02538`.

#### 3.3.3 — Stage 7 Memory 4-tier

**Files:** `services/ai-orchestrator/reasoning/memory/{types,service,...}.py` + tier adapters.

**Mục đích:** Long-term memory cho AI agent + RAG. 4 tiers:
- **L1 Ephemeral** — conversation context (in-process / Redis short TTL).
- **L2 Episodic** — recent events (Redis 7d).
- **L3 Semantic** — embedded facts (Postgres + pgvector mig 067 HNSW 1024d).
- **L4 Procedural** — distilled how-to (T-Cube store; ADR-0024 Mem0 port).

**Quy trình chạy (write):**
1. Caller `MemoryService.write(record, tier=Lx)` → adapter dispatch.
2. L3 — embed via BGE-M3 → HNSW upsert; importance score gate (default 0.3+).
3. L4 — T-Cube distil 3 forms (struct/semantic/reflect) → store all 3.

**Quy trình chạy (read):**
1. `MemoryService.recall(query, tier=Lx, top_k=5)`.
2. L3 — embed query + HNSW search → cosine ≥ 0.5 threshold.
3. L4 — query by tcube_form filter.

**Sub-cases:**
- **Tier swap via env** — `MEMORY_L3_BACKEND=postgres|redis|in_memory`.
- **Importance gate** — low importance memory → drop instead of store (saves vector space).

**Phi chức năng:**
- **K-1 / K-12** RLS by tenant_id.
- **K-3** ✅ embed via gateway.
- **K-17** write_idempotent.
- **Perf:** L3 HNSW search ~10-30ms.
- **Test coverage:** 23 tests `2ed08e4` + 64 storage adapters `09cbe7a`.

#### 3.3.4 — Stage 12 Loop (A/B + Promotion)

**Mục đích:** 60-day baseline + 90-day A/B test → promote winning variant. Production deployment of "framework as continuous experiment".

**Quy trình chạy:**
1. Baseline period (60d) — Variant A runs; record outcomes.
2. A/B period (90d) — randomly split traffic A vs B (new framework).
3. Per period close → compute lift = `mean(B) - mean(A)` + confidence interval.
4. Promote: B > A by ≥ ε + CI excludes 0 → flip B to default; archive A as fallback.
5. Loop — next variant C vs promoted B.

**Sub-cases:**
- **Insufficient traffic** — < 100 cases per variant → extend period.
- **Reversed (B worse)** — keep A, log failed promotion attempt.
- **Statistical tie** — keep A (status quo bias for cost control).

**Phi chức năng:**
- **K-17** baseline tracker = write_idempotent (event journal).
- **Test coverage:** 16 tests `1e0e620`.

#### 3.3.5 — Phase 2 storage adapters (4 backends ship Phase 1.5)

| Adapter | Backend | Tier | Commit |
|---|---|---|---|
| PostgresTierStore | Postgres mig 067 VECTOR HNSW | L3 | `d4ab620` |
| EmbeddingWorker | Postgres + BGE-M3 | L3 ingest | same |
| RedisTierStore | Redis Streams + key-prefix | L2 | next |
| Neo4jOntologyStore | Neo4j 5.25 | Stage 5 | next |
| Temporal activities × 5 | Temporal cluster | Workflow runtime | `09cbe7a` |
| Workflows × 3 | Temporal | — | same |

**Quy trình chạy adopter swap:**
- Env `MEMORY_L3_BACKEND` controls swap; pinned via test that interface contract stable across all 3.

**Phi chức năng:**
- **Drop-in TierStore/OntologyStore ABC** — caller code identical regardless of backend.
- **Tenant isolation triple — RLS + key-prefix + Neo4j label hash.**

---

### 3.4 — P15-S12: CFO digest + SLO alerting + dashboards

**Mục đích sprint:** Last Phase 1.5 sprint. CFO digest output (NOV-RPT-020) + observability SLO burn-rate alerts (OBS-017) + Grafana dashboards (OBS-020).

#### 3.4.1 — NOV-RPT-020: CFO quarterly digest

**Quy trình chạy:**
1. Cron quarterly (or admin-triggered) `POST /economics/cfo-digest` body `{enterprise_id, period_q}`.
2. Aggregate from `enterprise_monthly_billing` + NOV signals + `tenant_interventions` + `decision_audit_log`:
   - Revenue protected (NSM = revenue_at_risk actioned).
   - Cost avoided (interventions outcomes).
   - Decisions automated (count by category).
   - Top 3 wins + Top 3 issues.
3. Compose markdown report → render as PDF (notification-service template).
4. Email to CFO + Manager roles.

**Sub-cases:**
- **No data this quarter** — degenerate report "Quý X chưa có signal" + suggestions.
- **PII safety** — names + emails not in digest body; aggregate only.

**Phi chức năng:**
- **K-1 / K-12** scoped enterprise.
- **K-17** read_only.
- **K-15** audit log generation.
- **Test coverage:** included in `66d2d31`.

#### 3.4.2 — OBS-017: SLO burn-rate alerts

**Mục đích:** Multi-window multi-burn-rate alert per Google SRE workbook. 2 windows (5min + 1h) + 2 burn rates (fast + slow) = 4 alert conditions.

**Quy trình chạy:**
1. Prometheus scrape SLI (vd `kaori_request_latency_p99 < 500ms`).
2. PrometheusRule:
   - Fast burn — 14.4× error budget in 5min → page immediately (catches sudden incident).
   - Slow burn — 6× error budget in 1h → ticket (catches gradual drift).
3. Alertmanager route per severity → PagerDuty or Slack.

**Sub-cases:**
- **Cold start metric** — < 1h history → suppress slow-burn alerts.
- **Maintenance window** — silence applied via Alertmanager.

**Phi chức năng:**
- **K-19** ✅ tenant_id span attribute → can drill down per-tenant SLO violation.
- **Test coverage:** included in `ddda88b`.

#### 3.4.3 — OBS-020: SLI/SLO Grafana dashboards

**Mục đích:** Per-service SLO dashboard. 99.5% uptime (Phase 1 target) → 99.9% (Phase 2 target).

**Dashboards:**
- Service health board — request rate / error rate / p50/p95/p99 latency / SLO burn.
- Per-tenant board — top 10 tenants by request volume + their burn rate.
- LLM gateway board — per-task latency + token spend + Qwen vs external split.

**Phi chức năng:**
- **K-19** mandatory tenant_id span attribute → dashboards drill per tenant.
- **Files:** `infrastructure/grafana/dashboards/*.json`.

---

## SECTION 4 — Tổng kết review

### 4.1 — Trạng thái shipped

| Phase | Sprints | Test count post-sprint | Test count now | Delta |
|---|---|---|---|---|
| Phase 1 v4 (M1-M4) | 8 sprints | 1003 ai-orch + 31 Java | — | closed |
| Phase 1.5 (M5-M6) | 4 sprints S9-S12 | 1261 ai-orch / 510 pipeline / 102 llm-gw / 58 notif | 1900 / 692 / 178 / 58 | Phase 2 added |
| Phase 2 (M7-M12) | 7 shipped (S13/14/15/16/18/21/25), 2 deferred (S19/20), 3 not started (S22/23/24), 1 skip (S17) | 1554 ai-orch | 1900 ai-orch | +346 Phase 2.5 |
| Phase 2.5 | 10/10 BE done (FE bbox half waits) | 1899 ai-orch / 691 pipeline / 178 llm-gw | 1900 / 692 / 178 | +1 sau Pattern 5 BE |

### 4.2 — Items deferred / pending

| Item | Status | Where |
|---|---|---|
| Pattern 5 FE bbox highlight UI | waits FE restructure | CLAUDE.md §2 |
| K8s FPT Cloud provision | runbook ship `41eb7c3`; cluster bring-up = anh action | `docs/runbooks/k8s-fpt-cloud-provision.md` |
| Temporal worker live cutover | runbook + flag ready; `TEMPORAL_ENABLE_WORKER=true` to enable | docs/runbooks |
| Dual-write cutover | runbook ship `225dec0` | `docs/runbooks/dev-to-prod-data-cutover.md` |
| Microsoft SSO live | runbook ship `f3e09bb`; needs M365 Dev tenant | `docs/runbooks/sso-microsoft-setup.md` |
| Phase 2 microservices extraction (S19/20) | ✅ deferred Phase 3 (ADR-0010) | — |
| P2-S22 Custom AI fine-tuning | not started, low priority | BACKLOG_V4 |
| P2-S23 English UI | not started — FE paused | BACKLOG_V4 |
| P2-S24 100-customer milestone retro | doc shipped earlier `dda15c0`, business milestone tracker | — |

### 4.3 — Cách dùng doc này

- Mỗi section trỏ tới file + commit cụ thể → anh có thể `git show <hash>` để check exact diff.
- Pattern Cases/Sub-cases có thể dùng làm input cho QA team viết regression suite.
- Phi chức năng phần highlight K-rule + perf benchmark cần monitor trên Grafana.
- Khi ship feature mới → copy pattern 4 mục (Mục đích / Quy trình / Cases / Phi chức năng) làm spec template.

---

*End of FEATURE_EXECUTION_FLOWS.md — generated 2026-05-19 from HEAD `8bb944c`.*

