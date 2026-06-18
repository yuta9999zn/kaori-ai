# Workflow use cases — phân tích các case khác nhau

> **Status:** Research 2026-05-18. Phân tích các loại workflow + document types Kaori cần xử lý để thiết kế pipeline + AI capabilities cho đúng.
>
> Anh's note: "Contract approval là 1 ví dụ thôi. Cần phân tích các case khác nhau". Doc này list 20 use case từ thực tế VN business → categorize → identify pipeline + AI implication cho mỗi loại.

## Phân loại theo trục pipeline

### Trục 1 — Document shape

| Shape | Examples | Pipeline path |
|---|---|---|
| **Structured table** | CSV/XLSX export từ CRM, POS, kế toán | Parse direct → Silver typed |
| **Form-like PDF** | Đơn từ, ứng dụng, biểu mẫu | Extract → field detection → Silver |
| **Prose-heavy** | Hợp đồng, báo cáo, biên bản họp | Extract → DocSage Schema Discovery (LLM) → Silver |
| **Mixed (prose + table)** | Báo cáo tài chính, brochure | Extract → blocks split → DocSage per block-type |
| **Image-only / scanned** | Hóa đơn giấy, CCCD scan, dấu đỏ | OCR (Phase 2 Qwen2-VL) → text → DocSage |
| **Email + attachments** | Forwarded threads | Parse email body + dispatch attachments theo type |
| **Audio/video** | Meeting recordings | Transcribe (Phase 3) → text → DocSage |

### Trục 2 — Workflow conditional complexity

| Complexity | Examples | Node types needed (mig 068) |
|---|---|---|
| **Linear** | Upload → clean → store | `step` only |
| **Single-branch approval** | Upload → approve → archive | `step` + `approval_gate` |
| **If/else loop** | Upload → review → if NOK return; else next | `step` + `approval_gate` + `if_else` |
| **Multi-stage approval** | Draft → manager → director → CFO | Chain of `approval_gate`s |
| **Switch by document type** | Auto-route based on detected type | `switch` (mig 068 #32) |
| **Wait + timer** | Auto-escalate if no action in 48h | `wait_for_condition` + `scheduled_trigger` |
| **Parallel fan-out** | Send to 3 reviewers simultaneously, gate when all approve | Multiple branches + `wait_for_condition` |

### Trục 3 — AI involvement boundary

| Boundary | What AI does | What human does |
|---|---|---|
| **Read-only assist** | Extract fields, summarise, classify | Read AI output, decide |
| **Suggest + confirm** | Propose schema/category, draft email | Approve before action |
| **Auto-act with audit** | Auto-categorise + auto-route, log decision | Periodic review of audit log |
| **Out-of-scope** | (nothing) | Signature verify, legal interpret, risk decision |

## 20 use cases cụ thể

### Tài chính + kế toán

**Use case 1 — Báo cáo doanh thu tháng (CFO digest)**
- **Shape:** CSV/Excel export từ POS / ERP
- **Pipeline:** Structured path. Parse → Silver `orders` table → Gold aggregate → KPI engine SQL
- **AI:** Optional anomaly detection on top (insight node, read_only)
- **Workflow:** Linear. Upload → clean → store. No approval needed.
- **Anh's SQL-first:** PERFECT FIT. 100% SQL aggregate.

**Use case 2 — Báo cáo tài chính quý (PDF, multi-column)**
- **Shape:** Mixed PDF — prose narrative + complex tables + footnotes
- **Pipeline:** Unstructured path. Extract → blocks split → DocSage extracts table rows
- **Critical:** Multi-column reading order (Pattern 4 Phase 2.5)
- **AI:** Schema Discovery cho table layout per page
- **Workflow:** Linear; approval optional cho audited reports
- **Risk:** Tables flatten if Pattern 3 (pdfplumber) chưa ship

**Use case 3 — Hóa đơn nhà cung cấp (vendor invoices)**
- **Shape:** PDF/image scan, sometimes email forwarded
- **Pipeline:** Image → OCR (Phase 2 Qwen2-VL) → DocSage extracts (vendor, amount, due_date, line_items)
- **AI:** `classify_document` (invoice vs receipt vs PO), `extract_structured_data` (form-like)
- **Workflow:** Upload → AI classify → if amount > threshold → approval_gate → pay/archive
- **Conditional logic:** `switch` on vendor type / `if_else` on amount threshold

**Use case 4 — Sao kê ngân hàng (bank statements)**
- **Shape:** PDF từ ngân hàng (text-layer OK) hoặc scan (cần OCR)
- **Pipeline:** Unstructured → tables critical
- **AI:** Map columns to schema (date / desc / debit / credit / balance)
- **Workflow:** Monthly upload → auto-reconcile against `silver_orders` → flag mismatches
- **Anh's SQL-first:** Reconciliation logic = SQL JOIN. AI only for column mapping.

**Use case 5 — Báo cáo thuế (VAT, monthly)**
- **Shape:** Mixed — government PDF template + Excel attachment
- **Pipeline:** Excel direct + PDF unstructured for narrative
- **AI:** Validate against template (clause deviation check)
- **Workflow:** Draft → manager approve → director sign → submit to portal

### Hợp đồng + pháp lý

**Use case 6 — Hợp đồng phê duyệt (anh's example)**
- **Shape:** PDF/DOCX, có thể có dấu đỏ scan
- **Pipeline:** Unstructured. Extract parties / amount / dates / clauses
- **AI:** Extract structured fields; classify contract type; flag clauses deviating from template
- **Workflow:** if/else loop — anh's spec
- **AI boundary:** AI extracts + flags; human approves. NO signature/stamp verify.

**Use case 7 — NDA (Non-disclosure agreement)**
- **Shape:** DOCX template, populated per counterparty
- **Pipeline:** DOCX. Template-matching detection
- **AI:** Detect template version, flag custom edits, extract counterparty
- **Workflow:** Generate → review → sign → archive

**Use case 8 — Hợp đồng lao động**
- **Shape:** DOCX với placeholder, sau khi sign trở thành PDF scan
- **Pipeline:** 2 phases — draft (DOCX template) + signed (PDF scan)
- **AI:** Extract employee info, salary, position, start date
- **Workflow:** HR draft → manager approve → CEO sign → onboarding triggers (account creation, email setup, training schedule)
- **Cross-system:** SSO provisioning, Slack invite, calendar sync

**Use case 9 — Đơn từ pháp lý (legal correspondence)**
- **Shape:** PDF letter, prose-heavy, structured header
- **Pipeline:** Unstructured prose. Block taxonomy useful — title block carries metadata
- **AI:** Classify sender authority, extract claims, summarise
- **Workflow:** Receive → AI classify urgency → route to legal team
- **AI boundary:** AI summarises; lawyer interprets legal risk.

### Nhân sự (HR)

**Use case 10 — Hồ sơ ứng viên (CV / resume)**
- **Shape:** PDF (sometimes DOCX or image)
- **Pipeline:** Unstructured. Block taxonomy great for sections (skills / experience / education)
- **AI:** Extract structured fields (name, contact, experience years, skills array)
- **Workflow:** Upload → AI screen → if match score > threshold → schedule interview
- **Conditional:** `switch` on department or `if_else` on minimum experience

**Use case 11 — Onboarding documents**
- **Shape:** Multiple — CCCD scan (image, need OCR), tax form (PDF form), bank info (form), photo (image)
- **Pipeline:** Per-document type detection branches differently
- **AI:** OCR + field extraction + validation against employee record
- **Workflow:** Bulk upload to step → each doc auto-classified → progress checklist
- **Critical:** `required_document_types` whitelist per step (already shipped)

**Use case 12 — Đánh giá hiệu suất (performance reviews)**
- **Shape:** DOCX form with structured sections
- **Pipeline:** Unstructured but template-driven
- **AI:** Extract ratings, summarise feedback, sentiment analysis
- **Workflow:** Self-review → manager review → HR archive
- **Multi-stage approval**

### Vận hành (operations)

**Use case 13 — Đơn đặt hàng (purchase order)**
- **Shape:** PDF (vendor-generated) or form (web-submitted JSON)
- **Pipeline:** Form path direct; PDF path extract → fields
- **AI:** Match against approved vendor list, validate budget
- **Workflow:** Draft → budget check (auto) → manager approve → vendor send

**Use case 14 — Phiếu nhập kho / xuất kho**
- **Shape:** Excel / CSV daily
- **Pipeline:** Structured direct
- **AI:** Optional anomaly detection (unusual quantities)
- **Workflow:** Daily auto-import; auto-reconcile with sales

**Use case 15 — Báo cáo kiểm soát chất lượng**
- **Shape:** Mixed — Excel sheet + photo evidence
- **Pipeline:** Excel for data; images stored separately (link via lot_id)
- **AI:** Photo classification (Phase 3 vision model) — accept/reject visual
- **Workflow:** QC inspector upload → if rate > threshold → escalate to ops manager

### Khách hàng + bán hàng

**Use case 16 — Khảo sát khách hàng (customer surveys)**
- **Shape:** CSV export từ Google Forms / SurveyMonkey, or JSON API
- **Pipeline:** Structured direct
- **AI:** Sentiment analysis on open-ended responses, topic clustering
- **Workflow:** Monthly upload → AI analyse → report to product team

**Use case 17 — Phản hồi khách hàng (support tickets)**
- **Shape:** Email body + attachments (mixed)
- **Pipeline:** Email parser; attachments dispatched per type
- **AI:** Classify priority, extract intent, suggest response
- **Workflow:** Ticket inbox → AI route → assigned agent → resolve
- **Conditional:** `switch` on priority / department

**Use case 18 — Master data khách hàng (CRM export)**
- **Shape:** Excel / CSV bulk
- **Pipeline:** Structured direct → upsert into `silver_customers`
- **AI:** Dedup detection (similar names, addresses)
- **Workflow:** Quarterly sync; conflict resolution UI

### Tuân thủ + báo cáo cơ quan

**Use case 19 — Thông tư / nghị định mới**
- **Shape:** PDF circular từ cơ quan thuế / ngân hàng nhà nước
- **Pipeline:** Unstructured prose
- **AI:** Summarise, extract effective date + scope, flag if impacts existing workflows
- **Workflow:** Auto-fetch (RSS or manual upload) → AI summary → notify compliance officer

**Use case 20 — Đơn bảo hiểm (insurance claim)**
- **Shape:** Multi-doc bundle — form PDF + photo evidence + receipt scans
- **Pipeline:** Each doc dispatched per type; cross-linked via claim_id
- **AI:** Field extraction per doc; cross-validate amounts; classify claim type
- **Workflow:** Submit → AI validate → if complete + amount < threshold → auto-approve; else → adjuster review
- **Conditional:** `if_else` on completeness + amount; `approval_gate` for adjuster

## Pattern matrix — workflow nodes per use case

| Use case | step | approval_gate | if_else | switch | wait_for | scheduled | send_email | AI nodes |
|---|---|---|---|---|---|---|---|---|
| 1 — Revenue report | ✓ | | | | | ✓ | | optional |
| 2 — Financial Q | ✓ | optional | | | | ✓ | | classify+extract |
| 3 — Vendor invoice | ✓ | ✓ | ✓ (amount) | ✓ (type) | | | ✓ | classify+extract |
| 4 — Bank statement | ✓ | | | | | ✓ | | extract |
| 5 — VAT report | ✓ | ✓✓ | ✓ | | | ✓ | | validate |
| 6 — Contract approve | ✓ | ✓ | ✓ (return loop) | | | | ✓ (stamped) | extract+classify+deviate |
| 7 — NDA | ✓ | ✓ | | | | | ✓ | classify |
| 8 — Employment | ✓ | ✓✓ | | | | | ✓ | extract |
| 9 — Legal letter | ✓ | | | ✓ (urgency) | | | ✓ | classify+summarise |
| 10 — CV/resume | ✓ | | ✓ (score) | | | | | extract+score |
| 11 — Onboarding | ✓ | ✓ | | ✓ (doc type) | | | ✓ | extract per type |
| 12 — Performance | ✓ | ✓✓ | | | | ✓ | | sentiment |
| 13 — Purchase order | ✓ | ✓ | ✓ (budget) | | | | ✓ | validate |
| 14 — Inventory | ✓ | | | | | ✓ | | anomaly |
| 15 — QC report | ✓ | | ✓ (defect rate) | | | | ✓ | photo classify |
| 16 — Survey | ✓ | | | | | ✓ | | sentiment+cluster |
| 17 — Support tickets | ✓ | | | ✓ (priority) | | | ✓ | classify+route |
| 18 — Customer CRM | ✓ | | | | | ✓ | | dedup |
| 19 — Regulation | ✓ | | | | | ✓ | ✓ | summarise+impact |
| 20 — Insurance | ✓ | ✓ | ✓ (auto-approve) | | | | ✓ | extract+validate |

**Reading:** Em see 9/20 cases need `if_else`, 6/20 need `switch`, 11/20 need approval gate, 14/20 need AI extract.

## AI capability coverage (gaps cho catalog)

Today's `node_type_catalog` (mig 068) has:
- ✅ `call_insight_engine` (already in catalog)
- ✅ `approval_gate`, `if_else`, `switch`, `scheduled_trigger`, `wait_for_condition`
- ✅ `send_email`

Phase 2.5 additions em propose (mig extension):
- `classify_document` — input: blocks, schema; output: {category, confidence}
- `extract_structured_data` — input: blocks + target schema; output: typed rows
- `summarise_document` — for legal/regulation use cases
- `compare_to_template` — clause deviation detection (RAG-backed)
- `sentiment_analysis` — for surveys + reviews
- `dedup_records` — for CRM master data

Each AI node: `category=ai`, `side_effect_class=read_only`, configurable `llm_pinned_version` per K-20.

## Pipeline implications across all 20 cases

| Implication | Affected use cases |
|---|---|
| **Structured path enough** — no Stage 6 extract | 1, 14, 16, 18 (4/20) |
| **Unstructured needs block taxonomy** (Pattern 1) | 2, 6, 7, 9, 19 (5/20) |
| **Tables critical** (Pattern 3 — pdfplumber) | 2, 4, 5, 13, 20 (5/20) |
| **OCR needed** (Phase 2 Qwen2-VL) | 3 (some), 6 (stamped), 8 (signed), 11 (CCCD), 15 (photos), 20 (receipts) — 6/20 |
| **Multi-stage approval** | 5, 8, 12 (3/20) |
| **Cross-system action** (send_email + others) | 3, 5, 6, 8, 11, 13, 17, 19, 20 (9/20) |
| **AI extraction critical** | 3, 6, 7, 9, 10, 11, 12, 17, 19, 20 (10/20) |
| **SQL-first answers questions** | 1, 4, 14, 16, 18 (5/20) — heavy structured cases |
| **RAG fallback genuinely needed** | 6 (clause search), 9 (legal precedent), 19 (regulation lookup) — 3/20 |

**Key insight:** Most cases (17/20) need AI extraction NHƯNG sau extraction data vào Silver typed tables → questions trả lời bằng SQL. RAG-genuine cases chỉ 3/20 (legal/regulation textual lookup).

## Đề xuất rollout (cập nhật từ analysis trên)

### Phase 2.5 — Foundation (sign-off pending)

1. ✅ **Pattern 1 (block taxonomy) + Pattern 2 (header/footer strip)** — shipped 2026-05-18 (commit `25e82be`)
2. **Document-type detection vào upload router** — wire detection vào `/api/v1/upload`, validate `required_document_types` whitelist. 1 dev-day.
3. **Pattern 3 (pdfplumber table extraction)** — covers use cases 2, 4, 5, 13, 20 (25% of total). 2 dev-days.
4. **`classify_document` AI node** — covers 8 use cases. 0.5 dev-day.
5. **`extract_structured_data` AI node** — covers 10 use cases. 1 dev-day.

Total Phase 2.5 budget: **~5 dev-days for 50% of use case coverage**.

### Phase 2.5 stretch

6. **OCR via Qwen2-VL adapter** — unlocks 6 use cases (30%). 2 dev-days.
7. **Pattern 4 (multi-column reading order)** — improves use case 2. 1.5 dev-days.
8. **`compare_to_template` AI node** — covers use case 6 (contract deviation) + 19 (regulation impact). 2 dev-days (needs RAG embedding setup).

### Phase 3

9. **Phase 2 Qwen2-VL vision for invoice/receipt fields** — production-grade OCR.
10. **Audio transcription** — meeting minutes use case.
11. **Phase 5 — Pattern 5 (bbox citation) + FE PDF viewer** — once FE template restart.

## SQL-first re-emphasis cho mọi case

Mọi case PHẢI converge:

```
upload → extract (per shape) → DocSage Schema Discovery → Silver typed rows → Gold views → SQL aggregate
                                                                                              ↓
                                                                                       RAG fallback (only 3/20 cases)
```

**Anti-patterns rejected:**
- Use case 17 (support tickets): KHÔNG dùng vector search để answer "ticket gần đây của KH X" — SQL `WHERE customer_id = X ORDER BY created DESC` đủ
- Use case 18 (CRM): KHÔNG dùng embedding similarity để dedup — exact-match + fuzzy SQL (trigram) faster
- Use case 1+4+14+16: KHÔNG dùng RAG — pure SQL aggregate

**RAG legitimate:**
- Use case 6: "Hợp đồng nào có clause hợp tác độc quyền?" — text content match across contracts
- Use case 9: "Văn bản pháp lý nào liên quan vấn đề X?" — semantic search across letters
- Use case 19: "Có thông tư nào ảnh hưởng tới điều khoản Y?" — semantic search across regulations

3/20 = 15% of questions go to RAG. 85% answered bằng SQL.

## Workflow conditional templates — em đề xuất

Em propose adding 5 new templates to mig 069 catalog (workflow templates table):

| Template ID | Name | Nodes used | Use cases covered |
|---|---|---|---|
| `tmpl-contract-approval` | Phê duyệt hợp đồng (if/else loop) | step + approval_gate + if_else + send_email | 6, 7, 8 |
| `tmpl-invoice-process` | Xử lý hóa đơn nhà cung cấp | step + classify + amount-if + approval + send_email | 3 |
| `tmpl-onboarding-bundle` | Onboarding nhân viên mới | step (×4) + switch + cross-system actions | 11 |
| `tmpl-monthly-report` | Báo cáo định kỳ | scheduled + step + aggregate + send_email | 1, 14, 16 |
| `tmpl-claim-validate` | Validate đơn yêu cầu (insurance/refund) | step + extract + amount-if + approval | 20 |

Mig 069 đã có 25 templates; em add 5 nữa = 30 templates. Phase 2.5 task.

## Tóm tắt

**20 use cases → 4 pipeline shape patterns:**
1. Structured direct (4/20) — pure SQL
2. Unstructured prose (5/20) — extract → blocks → Schema Discovery
3. Tables-dominant (5/20) — need Pattern 3
4. Image/OCR (6/20) — Phase 2 Qwen2-VL

**Workflow conditional patterns:**
- 11/20 need approval_gate
- 9/20 need if_else (most: loop-back on rejection)
- 6/20 need switch (multi-branch routing)
- 9/20 need cross-system actions

**AI extraction:**
- 10/20 need structured field extraction
- 8/20 need document classification
- 3/20 need template comparison (RAG-backed)

**SQL-first preserved across all 20:** every case converges to Silver typed tables; RAG legitimate only in 3/20 (15%).

Phase 2.5 đầu tư 5 dev-days = covers 50% use cases. Anh chốt rollout order.
