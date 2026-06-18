# Kaori AI — Data Pipeline End-to-End: Từ Upload đến Output
Tài liệu phân tích công đoạn xử lý data với chỉ định layers rõ ràng
Phiên bản: v1.0 (Unified — gộp Data Processing Solution + Cognitive Layer thành 1 doc theo flow chronological) Phát hành: Tháng 5 / 2026 Audience: Data Engineer · Backend Engineer · ML Engineer · Architect · Product Lead Cấu trúc: Đọc top-down = đi từ moment khách click upload đến moment ra insight có thể action. Mỗi stage có badge [LAYER X] chỉ rõ thuộc layer nào. Triết lý: Data Pipeline = Cognitive Pipeline. Pipeline KHÔNG chỉ ETL — nó là organizational learning loop khép kín feedback.

## Mục lục
### PHẦN I — TỔNG QUAN
Phần 0. Triết lý, 5-Layer Stack, Pipeline Overview, 7 Primitives, Reality Check
### PHẦN II — 12 STAGES THEO FLOW
Stage 1. Upload + Bronze Layer [L2]
Stage 2. Schema Detection & Mapping [L2 + L3]
Stage 3. Cleaning → Silver Layer [L2]
Stage 4. Quality Scorecard (Gate) [L2 + L4]
Stage 5. Semantic Enrichment — Ontology + Master + Lifecycle [L4]
Stage 6. Knowledge Extraction (Parallel branch) [L4]
Stage 7. Memory System (cross-stage) [L4]
Stage 8. Gold Layer (Business Views) [L2]
Stage 9. AI Decision Generation [L3 + L4]
Stage 10. Insight Composition (3-tuyến) [L3 + L4]
Stage 11. Action Runtime (8 sub-stages) [L4]
Stage 12. Output Delivery [L5]
### PHẦN III — CROSS-CUTTING (touch nhiều layers)
Phần 13. Lineage Tracking
Phần 14. Error Handling & DLQ
Phần 15. Versioning & Schema Evolution
Phần 16. Multi-tenant Security
### PHẦN IV — REFERENCE
Phần 17. Architecture Choice (Medallion + ETL Framework Mapping)
Phần 18. Implementation Roadmap (Phase 1/2/3 priorities)

# PHẦN I — TỔNG QUAN
# Phần 0. Triết lý + Stack + Pipeline Overview
## 0.1 Triết lý: Data Pipeline = Cognitive Pipeline
Pipeline của Kaori KHÔNG chỉ là ETL (Extract-Transform-Load). Nó là organizational learning loop khép kín:
DATA → DECISION → INSIGHT → ACTION → OUTCOME → FEEDBACK → BETTER MODEL
Mỗi component được thiết kế để feed loop này. Nếu chỉ có Bronze/Silver/Gold mà thiếu Action Runtime + Memory + Feedback — Kaori chỉ là BI tool. Đây là khác biệt then chốt.
## 0.2 Kaori Stack — 5 Layers
Đây là kiến trúc reference cho cả tài liệu. Mỗi stage trong pipeline sẽ tag thuộc layer nào.
┌─────────────────────────────────────────────────────────────────┐
│  L5: APPLICATION LAYER                                          │
│      P1 Platform Manager · P2 Enterprise · P3 Studio · P4 Personal │
│      Dashboards, Reports, Notifications, Workflow Builder UI    │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│  L4: COGNITIVE LAYER                                            │
│      Semantic Ontology · Memory (L1-L4) · Knowledge Extraction  │
│      · Action Runtime · Entity Lifecycle State Machines         │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│  L3: AI/ML PLANE                                                │
│      Models (churn, fraud, etc.) · LLM Gateway (Qwen + ext)     │
│      · Feature Store · Embedding Service (BGE-M3)               │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│  L2: DATA PLANE                                                 │
│      Bronze (S3 raw) · Silver (ClickHouse cleaned)              │
│      · Gold (Postgres MV business views)                        │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│  L1: INFRASTRUCTURE                                             │
│      Kubernetes · Kafka · Storage (S3/disk) · Network · Auth    │
└─────────────────────────────────────────────────────────────────┘
Mapping mỗi layer giải quyết câu hỏi gì: - L1: “Hệ thống chạy ở đâu?” - L2: “Data của khách ở đâu, sạch chưa?” - L3: “Model nào predict, dùng features gì?” - L4: “System biết gì, nhớ gì, hành động ra sao?” - L5: “Người dùng tương tác như thế nào?”
## 0.3 Pipeline Overview — 12 Stages với Layer Tags
                    ┌─────────────────┐
                    │   STRUCTURED    │
                    │  CUSTOMER DATA  │
                    │  (CSV/Excel/API)│
                    └────────┬────────┘
                             ↓
   ┌──────────────────────────────────────────────────┐
   │  STAGE 1: Upload + Bronze              [L2]      │
   │  Resumable upload → S3 Bronze raw                │
   └──────────────────────────────────────────────────┘
                             ↓
   ┌──────────────────────────────────────────────────┐
   │  STAGE 2: Schema Detection & Mapping   [L2 + L3] │
   │  Heuristic + Qwen LLM → User confirms            │
   └──────────────────────────────────────────────────┘
                             ↓
   ┌──────────────────────────────────────────────────┐
   │  STAGE 3: Cleaning → Silver            [L2]      │
   │  Universal + Domain + Custom rules               │
   │  PII masking · Within-file dedup                 │
   └──────────────────────────────────────────────────┘
                             ↓
   ┌──────────────────────────────────────────────────┐
   │  STAGE 4: Quality Scorecard (GATE)     [L2+L4]   │
   │  7 dimensions · Pass before promote              │
   └──────────────────────────────────────────────────┘                ┌──────────────────┐
                             ↓                                          │  UNSTRUCTURED    │
   ┌──────────────────────────────────────────────────┐                │  DATA            │
   │  STAGE 5: Semantic Enrichment           [L4]     │                │  PDF/DOCX/Image/ │
   │  Ontology · Master records · Lifecycle           │                │  Email/Chat      │
   └──────────────────────────────────────────────────┘                └─────────┬────────┘
                             ↑                                                    ↓
                             │                                          ┌──────────────────┐
                             │  ←─────────────────────────────────────  │  STAGE 6:        │
                             │                                          │  Knowledge       │
                             ↓                                          │  Extraction [L4] │
   ┌──────────────────────────────────────────────────┐                └──────────────────┘
   │  STAGE 7: Memory System (cross-stage)   [L4]     │                       ↑
   │  L1 Working / L2 Short / L3 Ep / L4 LT          │                  feeds Memory
   └──────────────────────────────────────────────────┘
                             ↓
   ┌──────────────────────────────────────────────────┐
   │  STAGE 8: Gold Layer (Business Views)   [L2]     │
   │  Per-domain views · MV · Cache                   │
   └──────────────────────────────────────────────────┘
                             ↓
   ┌──────────────────────────────────────────────────┐
   │  STAGE 9: AI Decision Generation        [L3+L4]  │
   │  Features → Model → Pred + Confidence + SHAP     │
   └──────────────────────────────────────────────────┘
                             ↓
   ┌──────────────────────────────────────────────────┐
   │  STAGE 10: Insight Composition          [L3+L4]  │
   │  3-tuyến: chuyện gì / tại sao / nên làm gì       │
   └──────────────────────────────────────────────────┘
                             ↓
   ┌──────────────────────────────────────────────────┐
   │  STAGE 11: Action Runtime (8 sub-stages) [L4]    │
   │  Recommend→Approve→Execute→Track→Outcome→Feedback│
   └──────────────────────────────────────────────────┘
                             ↓
   ┌──────────────────────────────────────────────────┐
   │  STAGE 12: Output Delivery              [L5]     │
   │  Reports · Dashboards · Notifications            │
   └──────────────────────────────────────────────────┘
                             ↓
                    ┌─────────────────┐
                    │   CUSTOMER      │
                    │  TAKES ACTION   │
                    └────────┬────────┘
                             ↓ outcome observed
                             │
                             └→ feedback loop closes back
                                to Stage 7 (Memory) +
                                Stage 9 (model retrain)
## 0.4 7 Core Primitives — Vocabulary toàn pipeline
Mọi service, mọi feature, mọi conversation phải dùng 7 từ vựng này. Không invent thuật ngữ mới.

| # | Primitive | Định nghĩa | Identity | Layer |
|---|---|---|---|---|
| 1 | ENTITY | Bất kỳ thứ gì system observe — customer, product, transaction, employee, asset, document | tenant_id + entity_type + external_id | L4 (cataloged), L2 (stored) |
| 2 | EVENT | Cái gì đó xảy ra với entity, có timestamp | event_id (UUID, immutable) | L2 (stored), L4 (linked) |
| 3 | WORKFLOW | Sequence of steps có branches tạo ra outcomes | workflow_id + version | L4 |
| 4 | DECISION | 1 phán đoán cụ thể từ AI hoặc human | decision_id + confidence + audit | L3 (generated), L4 (tracked) |
| 5 | INSIGHT | Pattern truyền đạt được — format “3-tuyến” | insight_id + citations | L4 |
| 6 | ACTION | Bước thực tế làm dựa trên decision/insight | action_id + performed_by + evidence | L4 |
| 7 | OUTCOME | Kết quả đo được sau action | outcome_id + attributed_to action_id | L4 |

## 0.5 Reality Check — Data khách hàng VN bẩn ra sao
Đo từ thực tế onboarding 50+ retail SME Việt Nam — 8 loại “rác” phổ biến nhất:

| # | Loại rác | Tần suất | Ví dụ thực tế | Severity |
|---|---|---|---|---|
| 1 | Encoding sai | 78% files | Excel save Win-1258, “Nguy?n V?n A” | HIGH (block parsing) |
| 2 | Header rows ẩn | 65% | 3 dòng “Báo cáo Q1 2026” trước header thật | HIGH |
| 3 | Tổng cộng giả mạo | 58% | Row “TỔNG CỘNG” lẫn vào transactions | HIGH |
| 4 | Ngày tháng đa format | 52% | “01/03/2026”, “1-Mar-2026” cùng file | MEDIUM |
| 5 | Customer ID không stable | 47% | “Anh Tuấn 0987” vs “Tuấn 098” — cùng người | CRITICAL |
| 6 | Duplicate rows | 41% | Nhân viên double-click submit | MEDIUM |
| 7 | Negative quantity nhầm refund | 35% | -5 không tách bảng riêng | MEDIUM |
| 8 | PII trong free text | 33% | “gọi 0987654321 lúc 3pm” trong notes | HIGH |

Insight quan trọng: Quality Score < 60 ở D14 → 47% chance churn at D90. Quality work từ Stage 3-4 là leverage point cao nhất.

# PHẦN II — 12 STAGES THEO FLOW
# Stage 1. Upload + Bronze Layer
Layer: [L2 — Data Plane]
Mục đích stage: Nhận file từ khách, validate cơ bản, write Bronze raw zone với immutability + audit. Bronze là single source of truth, không bao giờ UPDATE/DELETE.
## 1.1 Folder Architecture (giao diện như Windows Explorer)
📁 Workspace [tenant_id]
   ├── 📁 Departments
   │   ├── 📁 Marketing
   │   │   ├── 📁 Sources
   │   │   │   ├── 📁 KiotViet POS
   │   │   │   │   ├── 📁 2026/04
   │   │   │   │   │   ├── 📄 customers_20260401.csv
   │   │   │   │   │   └── 📄 transactions_20260401.csv
   │   │   ├── 📁 Workflows
   │   │   ├── 📁 Reports
   │   │   └── 📁 Insights
   │   ├── 📁 Sales / Operations / Finance / ...
   ├── 📁 Shared Resources (Master Data, Reference Tables)
   └── 📁 System (Bronze/Silver/Gold — read-only)
Nguyên tắc: - Mỗi folder = logical container có quota + permission + schema rules - Naming auto-fixed: lowercase, no spaces, strip diacritics in path (giữ tên hiển thị có dấu) - Permissions: DEPT_MANAGER full, ANALYST read+upload, OPERATOR view only
## 1.2 Upload Lifecycle — 5 Steps
### Step 1: Pre-flight Check (browser-side, before upload)
async function preFlightCheck(file) {
  // 1. File size vs plan limit
  if (file.size > planLimit) return error("File quá lớn");
  
  // 2. Extension check (csv/xlsx/xls/json)
  
  // 3. Encoding sniff (first 10KB)
  const head = await file.slice(0, 10240).text();
  const encoding = detectEncoding(head);
  
  // 4. Quick header detect
  const headerRow = findHeaderRow(head);
  
  // 5. Sample preview to user
  return { ok: true, metadata: { encoding, headerRow, ...} };
}
→ Reject obvious errors trước khi consume bandwidth.
### Step 2: Resumable Upload (chunk-based, 5MB chunks)
[Browser] PUT /api/v1/upload/init
  Body: { department_id, source_id, file_size, sha256_hash_client }

[Server] Returns:
  {
    upload_id: "upl_abc123",
    presigned_s3_url: "...",
    chunk_size: 5_242_880,
    expires_at: "..."
  }

[Browser] PUT chunks (resumable nếu network drop)
  Each chunk SHA-256 verified

[Browser] POST /api/v1/upload/{upload_id}/complete
[Server]:
  1. Verify hashes match
  2. Move staging → Bronze
  3. Write metadata to PostgreSQL
  4. Emit Kafka: kaori.ingest.bronze.uploaded
Why resumable: VN bandwidth → single-shot upload fail rate ~25% với file >100MB. Chunk-based reduce xuống ~3%.
### Step 3-5: Server-side validation, Schema mapping (Stage 2), Cleaning rules (Stage 3)
(Chi tiết trong stages tiếp theo.)
## 1.3 Bronze Storage Spec
Path convention:
s3://kaori-bronze/{tenant_id}/{department_id}/{source_id}/{year}/{month}/{day}/{upload_id}/
  ├── data.csv.gz                    # Original file (compressed)
  ├── metadata.json                   # Upload metadata
  ├── _SUCCESS                        # Marker file
  └── lineage.json                    # Lineage info
metadata.json schema:
{
  "upload_id": "upl_xyz789",
  "tenant_id": "tenant_abc",
  "uploaded_at": "2026-04-01T14:32:11Z",
  "file_info": {
    "original_filename": "customers_thang_3.csv",
    "size_bytes": 18723456,
    "sha256": "abc123...",
    "encoding_detected": "windows-1258",
    "encoding_normalized": "utf-8",
    "total_rows": 14237,
    "junk_rows_removed": [0, 14238]
  },
  "schema_inferred": {
    "columns": [
      {"name": "ma_kh", "type": "string", "semantic": "customer_id", "confidence": 0.92}
    ]
  },
  "ingest_pipeline": {
    "version": "v3.2.1",
    "rules_applied": ["rule_encoding_normalize", "rule_junk_removal"]
  }
}
## 1.4 Bronze Immutability
CRITICAL principle: Bronze is APPEND-ONLY. Never UPDATE, never DELETE.
Vì sao: - Audit trail (compliance) - Time-travel queries - Bug investigation when downstream Silver/Gold has issue - Right-to-erasure: mark tombstone.json flag, encrypt original, re-process Silver/Gold without that data — original deleted only after 7+ years retention
## 1.5 Compression + Tiering

| Tier | Age | Storage | Cost |
|---|---|---|---|
| Hot | 0-90 ngày | S3 Standard | $0.023/GB |
| Warm | 90-365 ngày | S3 Standard-IA | $0.0125/GB (52% cheaper) |
| Cold | 1-2 năm | S3 Glacier Instant | $0.004/GB (83% cheaper) |
| Archive | >2 năm | S3 Glacier Deep | $0.00099/GB (96% cheaper) |

Bronze CSV → gzip compression (~5:1 ratio) → 80% storage savings.
## 1.6 Acceptance Criteria — Stage 1
☐ Upload 500MB file with network drop → resume successful
☐ VN encoding (Win-1258, TCVN) auto-converted to UTF-8
☐ Bronze write < 30s for 100MB file
☐ SHA-256 verified client + server side match
☐ Audit log immutable, every upload tracked
☐ Quota enforced at workspace + department level

# Stage 2. Schema Detection & Mapping
Layer: [L2 Data Plane + L3 AI/ML Plane (cho LLM detection)]
Mục đích stage: Hiểu file vừa upload có cột gì, mỗi cột mang nghĩa business gì. Output là mapping table dùng cho cleaning ở Stage 3.
## 2.1 Multi-stage Detection
### Stage 2A: Heuristic Detection (fast, free) — [L2]
Per column, check name + value patterns:
def heuristic_classify(column_name, sample_values):
    name_lower = column_name.lower()
    
    # Vietnamese + English keywords
    if name_lower in ['ma_kh', 'customer_id', 'cust_id', 'ma_khach', 'maso']:
        return 'customer_id', confidence=0.85
    if name_lower in ['ngay', 'date', 'thoi_gian', 'ngay_mua']:
        return 'date', confidence=0.80
    if name_lower in ['so_tien', 'amount', 'gia_tri', 'tong_tien']:
        return 'amount', confidence=0.85
    
    # Value-pattern based
    sample_clean = [v for v in sample_values if v is not None][:50]
    
    if all(matches_date_pattern(v) for v in sample_clean):
        return 'date', confidence=0.90
    if all(matches_vn_phone(v) for v in sample_clean):
        return 'phone', confidence=0.95
    if all(matches_email(v) for v in sample_clean):
        return 'email', confidence=0.95
    if all(is_numeric(v) for v in sample_clean):
        if max(parse_num(v) for v in sample_clean) > 100_000:
            return 'amount_vnd', confidence=0.70
        return 'numeric', confidence=0.80
    
    return 'text', confidence=0.50
### Stage 2B: LLM-Assisted (when heuristic confidence low) — [L3]
Prompt to Qwen 14B:

"Đây là 100 sample values từ cột '{column_name}' trong file CSV
của doanh nghiệp retail Việt Nam.

Sample: [v1, v2, ..., v100]

Phân loại vào: customer_id / transaction_id / product_id / 
amount_vnd / date / phone / email / product_name / category / 
store_id / channel / payment_method / text_other

Trả về JSON: {
  semantic_type, confidence, reasoning, potential_issues
}"
### Stage 2C: User Confirmation — [L5 UI]
┌──────────────────────────────────────────────────────────┐
│ Schema Mapping — customers_20260401.csv                  │
├──────────────────────────────────────────────────────────┤
│ Column from file       AI suggestion       Confirm      │
│ ─────────────────     ──────────────      ─────────     │
│ "ma_kh"                customer_id ✓       [✓]          │
│ "ho_ten"               customer_name       [✓]          │
│ "sdt"                  phone (VN)          [✓]          │
│ "ngay_mua"             transaction_date    [✓]          │
│ "tong_tien"            amount_vnd          [✓]          │
│ "ghi_chu"              text_other ⚠        [▼ Edit]    │
│                                                          │
│ ⚠ Cột "ghi_chu" có 33% giá trị chứa số điện thoại —     │
│   sẽ được mask khi vào Silver layer.                    │
│                                                          │
│ Required columns missing: NONE ✓                         │
│                                                          │
│ [Save Mapping]  [Cancel]  [Save as Template]            │
└──────────────────────────────────────────────────────────┘
## 2.2 Required vs Optional Fields per Domain
System enforces minimum required columns. Đây là gate: không đủ ESSENTIAL → không thể qua.

| Domain | ESSENTIAL (block) | PRIORITY (warn) | OPTIONAL |
|---|---|---|---|
| Retail | customer_id, transaction_date, amount | name, phone, category, channel | email, store_id, staff_id, review |
| E-com | order_id, customer_id, amount, date | product, status, payment | session, traffic_source, device |
| F&B | order_id, date, amount | customer_id, items, table | staff, payment_method, tip |
| Logistics | shipment_id, origin, destination, created_at | weight, carrier, status | weather, traffic |
| Manufacturing | batch_id, product_id, quantity, dates | machine, operator, defect_count | raw_material, quality |

## 2.3 Mapping Templates (Re-use)
template:
  name: "KiotViet weekly customers export"
  source_id: "kiotviet_pos_marketing"
  domain: "retail"
  file_pattern: "customers_*.csv"  # auto-apply when filename matches
  encoding: "utf-8"
  delimiter: ","
  header_row: 1
  junk_rows_handling: "skip_summary_footer"
  
  mappings:
    "ma_kh": customer_id
    "ho_ten": name
    "sdt": phone
    "tong_tien": ltv
    "loai_kh": customer_segment
  
  cleaning_rules_applied:
    - rule_phone_e164
    - rule_name_pii_mask
    - rule_dedup_by_phone
Next upload matching customers_*.csv từ source kiotviet_pos_marketing → auto-apply template, customer chỉ confirm.
## 2.4 Schema Evolution Detection
Khi user upload file mới với schema khác file cũ:

| Severity | Detection | Action |
|---|---|---|
| LOW | Add column | Auto-include in Bronze raw_payload |
| MEDIUM | Remove column | Alert if used in Silver/Gold |
| HIGH | Type change | Potential data loss → require approval |
| HIGH | Rename column | Need re-mapping → Schema Migration Wizard |

## 2.5 Acceptance Criteria — Stage 2
☐ Heuristic detection ≥80% accuracy on standard VN columns
☐ LLM fallback for confidence <0.7 cases
☐ Required columns missing → block with clear error
☐ Mapping templates re-usable across uploads
☐ Schema evolution alerts customer Manager

# Stage 3. Cleaning → Silver Layer
Layer: [L2 — Data Plane]
Mục đích stage: Áp dụng cleaning rules để transform raw Bronze data thành sạch, schema-enforced Silver data sẵn sàng cho analytics.
## 3.1 Triết lý: 3 Lớp Rules
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: UNIVERSAL RULES (apply to all uploads)            │
│  - Encoding fix                                             │
│  - Whitespace trim                                          │
│  - Empty row removal                                        │
│  - Junk row detection (TỔNG CỘNG, headers ẩn)               │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: DOMAIN RULES (per vertical)                       │
│  - Phone format VN → E.164                                  │
│  - Vietnamese name title case                               │
│  - VND amount normalization                                 │
│  - Province/city standardization                            │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: TENANT-CUSTOM RULES (per customer)                │
│  - Specific business logic                                  │
│  - Per-source quirks                                        │
│  - Mapping to internal schemas                              │
└─────────────────────────────────────────────────────────────┘
## 3.2 Universal Rules (apply 100% files)
### Rule U-1: Encoding Normalization
def normalize_encoding(file_path):
    detected = chardet.detect(open(file_path, 'rb').read(100_000))
    if detected['encoding'].lower() in ['utf-8', 'ascii']:
        return file_path
    
    # Common VN encodings
    converters = {
        'windows-1258': vn_win1258_to_utf8,
        'TCVN': tcvn_to_utf8,
        'VPS': vps_to_utf8,
        'iso-8859-1': latin1_to_utf8,
    }
    
    output_path = file_path + '.utf8'
    converter = converters.get(detected['encoding'])
    if converter:
        converter(file_path, output_path)
    else:
        force_utf8(file_path, output_path)
    return output_path
### Rule U-2: Whitespace Cleanup
def cleanup_whitespace(value):
    if not isinstance(value, str): return value
    value = value.strip()
    value = re.sub(r'\s+', ' ', value)
    # Remove invisible characters (zero-width spaces, BOM)
    value = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', value)
    return value
### Rule U-3: Junk Row Detection
def detect_junk_rows(df):
    junk_indices = []
    for idx, row in df.iterrows():
        if row.isnull().all():
            junk_indices.append(idx); continue
        
        row_text = ' '.join(str(v) for v in row.values).lower()
        if any(kw in row_text for kw in [
            'tổng cộng', 'total', 'sum', 'cộng', 'tổng', 
            'subtotal', 'báo cáo', 'note:'
        ]):
            junk_indices.append(idx); continue
        
        # Many cells merged (only first cell has value)
        non_null = row.notna().sum()
        if non_null == 1 and idx > 0:
            junk_indices.append(idx)
    return junk_indices
## 3.3 Domain-Specific Rules (Retail example)
### Rule R-1: Phone Normalization VN → E.164
def normalize_vn_phone(phone):
    if not phone: return None
    p = re.sub(r'[\s\-\.\(\)]', '', str(phone))
    
    # Handle: 0987654321 / 84987654321 / +84987654321 / 0084987654321
    if p.startswith('0084'):
        p = '+84' + p[4:]
    elif p.startswith('84'):
        p = '+' + p
    elif p.startswith('0'):
        p = '+84' + p[1:]
    elif not p.startswith('+'):
        p = '+84' + p
    
    if not re.match(r'^\+84\d{9,10}$', p):
        return None  # invalid
    return p
### Rule R-3: VND Amount Normalization
def normalize_vnd_amount(value):
    """
    Handle messy VND formats:
    "1,500,000" → 1500000
    "1.500.000" → 1500000  (VN style: dot as thousands sep)
    "1.5 triệu" → 1500000
    "VND 1500000" → 1500000
    """
    if value is None or value == '': return None
    s = str(value).strip().lower()
    s = re.sub(r'(vnd|đ|đồng|vnđ)', '', s).strip()
    
    if 'triệu' in s or ' tr ' in s:
        num = re.search(r'[\d.]+', s)
        if num: return float(num.group()) * 1_000_000
    
    if 'nghìn' in s or 'k' in s:
        num = re.search(r'[\d.]+', s)
        if num: return float(num.group()) * 1_000
    
    # Handle thousand separators
    if ',' in s and '.' in s:
        if s.rfind(',') < s.rfind('.'):
            s = s.replace(',', '')
        else:
            s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        parts = s.split(',')
        if len(parts) == 2 and len(parts[1]) <= 2:
            s = s.replace(',', '.')
        else:
            s = s.replace(',', '')
    elif '.' in s:
        parts = s.split('.')
        if len(parts) > 2 or len(parts[-1]) > 2:
            s = ''.join(parts)
    
    try: return float(s)
    except ValueError: return None
### Rule R-5: Date Format Detection
⚠️ Cảnh báo về %m/%d/%Y (US) vs %d/%m/%Y (VN): “03/04/2026” có thể là March 4 hoặc 3 April. Phải check entire column — if any value has day > 12, must be d/m format. Default to d/m for VN.
## 3.4 PII Detection & Masking
### PII Categories

| Category | Examples | Mask strategy | Reversible? |
|---|---|---|---|
| High sensitive | National ID (CCCD), passport, bank account | Hash SHA-256 + salt | No |
| Contact | Phone, email | Hash + last 4 chars visible | Partial (last 4) |
| Name | Full name | First letter + … (“N.V.A”) | No |
| Address | Street + house number | Keep city/region only | No |
| Free text | Notes, comments | Detect PII inline + redact | Partial |

### Detection Patterns
PII_PATTERNS = {
    'phone_vn': r'(\+84|0)[1-9]\d{8,9}',
    'national_id_vn': r'\b\d{12}\b',  # CCCD 12 digits
    'old_national_id_vn': r'\b\d{9}\b',  # CMND 9 digits
    'passport_vn': r'[A-Z]\d{7,8}',
    'email': r'[\w\.\-]+@[\w\.\-]+\.\w+',
    'bank_account_vn': r'\b\d{10,16}\b',
    'license_plate_vn': r'\d{2}[A-Z]\d?-?\d{4,5}',
}
### Per-Field Policy Example
field_pii_policy:
  customer_id:
    pii_class: 'identifier'
    masking: 'none'  # business identifier, not PII
  
  name:
    pii_class: 'name'
    masking: 'name_initials'  # "Nguyễn V.A"
    in_silver: 'name_masked'
  
  phone:
    pii_class: 'contact'
    masking: 'partial_last4'  # ****4321
    in_silver: 'phone_masked'
    tokenize_for: ['retention_calls']  # specific workflow can detokenize
  
  email:
    pii_class: 'contact'
    masking: 'hash_sha256'
    in_silver: 'email_hash'
  
  national_id:
    pii_class: 'high_sensitive'
    masking: 'hash_sha256'
    note: 'NEVER detokenize except legal request'
  
  notes:  # free text
    pii_class: 'free_text'
    masking: 'detect_inline_redact'
### PII Audit (immutable)
CREATE TABLE pii_access_log (
  id BIGSERIAL PRIMARY KEY,
  tenant_id UUID NOT NULL,
  accessed_by UUID NOT NULL,
  pii_field VARCHAR(100),
  entity_id VARCHAR(200),
  access_type VARCHAR(50),  -- 'read_raw', 'tokenize', 'detokenize'
  workflow_id UUID,
  reason TEXT NOT NULL,  -- mandatory
  ip_address INET,
  occurred_at TIMESTAMP NOT NULL DEFAULT now()
);
-- Cannot DELETE or UPDATE this table (RLS)
## 3.5 Within-File Deduplication (Level 1)
def dedup_within_file(df, dedup_keys):
    df_dedup = df.drop_duplicates(subset=dedup_keys, keep='last')
    dropped = len(df) - len(df_dedup)
    if dropped > 0:
        log_dedup({'dropped': dropped, 'pct': dropped/len(df)*100})
    return df_dedup
(Cross-upload + Cross-source dedup → Stage 5 Semantic Enrichment)
## 3.6 Silver Storage — Apache Parquet
Format: Parquet (columnar, compressed, schema-enforced)
Why not CSV/JSON: - 10× smaller than CSV - 50× faster for analytical queries - Schema embedded in file - Column pruning + predicate pushdown
silver/
├── customers/
│   ├── tenant_id=abc/
│   │   └── year=2026/month=04/
│   │       ├── part-00000.parquet
│   │       └── part-00001.parquet
├── transactions/...
## 3.7 Silver Schema (Retail example)
silver.customers
  customer_id           STRING (NOT NULL, unique per tenant)
  customer_external_id  STRING (raw từ source — for billing)
  name_masked          STRING (PII masked)
  phone_e164           STRING (+84xxxxxxxxx)
  email_hash           STRING (SHA-256 first 16 char)
  city, region         STRING (normalized)
  first_seen_at        TIMESTAMP
  last_seen_at         TIMESTAMP
  ltv                  NUMERIC(12,2) VND
  segment              ENUM (VIP/REGULAR/NEW/INACTIVE)
  ingested_at          TIMESTAMP
  source_system        STRING

silver.transactions
  txn_id               STRING (NOT NULL, unique)
  customer_id          STRING (FK)
  txn_ts               TIMESTAMP
  amount               NUMERIC(12,2)
  currency             ENUM ('VND', 'USD')
  channel              ENUM (online, in_store, marketplace)
  status               ENUM (completed, refunded, cancelled)
  payment_method       ENUM (vnpay, momo, vietqr, cod, card)
## 3.8 Schema Enforcement → DLQ
def enforce_silver_schema(df, domain):
    schema = get_silver_schema(domain)
    valid_records = []
    rejected = []
    
    for idx, row in df.iterrows():
        try:
            row_typed = cast_row_to_schema(row, schema)
            for col, rules in schema.constraints.items():
                if rules.get('not_null') and row_typed[col] is None:
                    raise ValueError(f"Column {col} cannot be null")
                if rules.get('enum') and row_typed[col] not in rules['enum']:
                    raise ValueError(f"Invalid enum value")
            valid_records.append(row_typed)
        except Exception as e:
            rejected.append({'row': row.to_dict(), 'error': str(e), 'index': idx})
    
    return valid_records, rejected
Rejected → DLQ topic for review.
## 3.9 Silver Refresh Strategy per Plan

| Plan | Refresh frequency | Latency Bronze→Silver |
|---|---|---|
| PILOT | Manual | Hours |
| ENT BASIC | Daily 02:00 | 1-4 hours |
| ENT MID | Hourly | 5-30 minutes |
| ENT MAX | Real-time stream | Seconds |

## 3.10 Acceptance Criteria — Stage 3
☐ Bronze → Silver pipeline E2E < 15 min for 100MB
☐ Schema enforcement rejects invalid → DLQ
☐ PII coverage: phone (95%+), email (95%+), name (80%+)
☐ PII masking 100% applied (no raw PII in Silver)
☐ Within-file dedup tested (1000 dups → all removed)
☐ Silver Parquet readable by ClickHouse + DuckDB
☐ Audit log per pipeline run

# Stage 4. Quality Scorecard (Gate)
Layer: [L2 Data Plane + L4 Cognitive Layer cho health integration]
Mục đích stage: Đo chất lượng Silver data theo 7 dimensions. Score < threshold → block promotion to Gold + alert customer. Score ≥ threshold → promote.
## 4.1 7 Dimensions

| Dimension | Measures | Target |
|---|---|---|
| Completeness | % non-null in essential columns | ≥95% |
| Validity | % rows passing schema validation | ≥98% |
| Uniqueness | % unique customer_ids (or business keys) | ≥99% |
| Consistency | % cross-source agreement | ≥85% |
| Timeliness | Time since last update | <14 days |
| Accuracy | % manually verified samples accurate | ≥90% |
| Integrity | % FK relationships valid | 100% |

## 4.2 Per-Dimension Formulas
### Completeness
def completeness_score(df, essential_cols):
    if not essential_cols: return 1.0
    scores = []
    for col in essential_cols:
        null_rate = df[col].isnull().sum() / len(df)
        scores.append(1 - null_rate)
    return sum(scores) / len(scores)
### Validity
def validity_score(df, schema):
    valid_count = sum(1 for idx, row in df.iterrows() if validates_schema(row, schema))
    return valid_count / len(df)
### Uniqueness
def uniqueness_score(df, key_col):
    return df[key_col].nunique() / len(df)
### Consistency (cross-source)
def consistency_score(records_per_source):
    total_compared = total_agree = 0
    for record_id, sources in records_per_source.items():
        if len(sources) < 2: continue
        for field in ['name', 'phone', 'email']:
            values = [s[field] for s in sources]
            total_compared += 1
            if all(v == values[0] for v in values):
                total_agree += 1
    return total_agree / max(total_compared, 1)
### Timeliness
def timeliness_score(last_update_at, max_lag_days=14):
    days_lag = (now() - last_update_at).days
    return max(0, 1 - days_lag / max_lag_days)
### Integrity
def integrity_score(df, fk_relationships):
    total_fks = valid_fks = 0
    for fk_col, ref_table, ref_col in fk_relationships:
        for value in df[fk_col].dropna():
            total_fks += 1
            if exists_in_ref(ref_table, ref_col, value):
                valid_fks += 1
    return valid_fks / max(total_fks, 1)
## 4.3 Overall Quality Score
def overall_quality_score(scorecard):
    weights = {
        'completeness': 0.25, 'validity': 0.20, 'uniqueness': 0.15,
        'consistency': 0.15, 'timeliness': 0.10, 'accuracy': 0.10,
        'integrity': 0.05,
    }
    weighted = sum(scorecard[d] * weights[d] for d in weights if scorecard[d] is not None)
    weight_sum = sum(weights[d] for d in weights if scorecard[d] is not None)
    return (weighted / weight_sum) * 100  # 0-100
## 4.4 Phase-Aware Targets

| Phase | Min overall score | Outcome if below |
|---|---|---|
| W1 (Foundation) | 60 | Block Silver promotion |
| W2-4 (Activation) | 70 | Warning, but proceed |
| W5-8 (Workflow) | 75 | Acceptable |
| W9-12 (Handover) | 80 | Target HEALTHY |
| Steady state | 85+ | Continuous monitoring |

## 4.5 Customer-Facing Dashboard
┌──────────────────────────────────────────────────────────┐
│ Data Quality Scorecard — Marketing Department           │
│ Last computed: 2 hours ago                              │
├──────────────────────────────────────────────────────────┤
│ Overall: 78/100 ⚠️ ACCEPTABLE (target: 80+)             │
│                                                          │
│ Completeness     ████████████░░░░  85% ✓               │
│ Validity         ███████████████░  92% ✓               │
│ Uniqueness       ████████████░░░░  88% ⚠               │
│ Consistency      ████████░░░░░░░░  62% ⚠               │
│ Timeliness       ████████████████  98% ✓               │
│ Accuracy         ███████████████░  93% ✓               │
│ Integrity        ████████████████ 100% ✓               │
│                                                          │
│ ⚠ Improvement opportunities:                             │
│   1. Customer ID uniqueness: 12% duplicate              │
│      → Apply rule "dedup_by_phone"                      │
│   2. Cross-source consistency low                       │
│      → Many name variations between KiotViet & HubSpot  │
│      → Suggest master record matching workshop          │
└──────────────────────────────────────────────────────────┘
## 4.6 Acceptance Criteria — Stage 4
☐ Scorecard generated < 5s after Silver write
☐ All 7 dimensions computed correctly (test on Online Retail II)
☐ Customer dashboard shows radar chart + trend
☐ Each low score has actionable suggestion
☐ Score history retained 90 days minimum
☐ Score affects Health State Machine

# Stage 5. Semantic Enrichment — Ontology + Master Records + Lifecycle
Layer: [L4 — Cognitive Layer]
Mục đích stage: Bridge từ Silver (cleaned data) → Cognitive understanding. Customer “Anh Tuấn 0987654321” trong KiotViet + HubSpot + Excel → 1 master entity. Plus: state machine cho mỗi entity hiểu được lifecycle.
## 5.1 7 Primitives Ontology — Full Graph Schema (Neo4j)
// ENTITY types
CREATE (c:Entity:Customer {tenant_id, customer_id, name_masked, ...})
CREATE (p:Entity:Product {tenant_id, product_id, ...})
CREATE (t:Entity:Transaction {tenant_id, txn_id, ...})
CREATE (s:Entity:Store {tenant_id, store_id, ...})
CREATE (e:Entity:Employee {tenant_id, employee_id, ...})

// EVENT types
CREATE (ev:Event:Purchase {event_id, occurred_at, ...})
CREATE (ev:Event:Complaint {event_id, occurred_at, ...})
CREATE (ev:Event:Login {event_id, occurred_at, ...})

// === RELATIONS ===

// Entity ↔ Entity
(:Customer)-[:BOUGHT {qty, amount}]->(:Product)
(:Customer)-[:VISITED]->(:Store)
(:Employee)-[:SERVED]->(:Customer)
(:Product)-[:BELONGS_TO]->(:Category)
(:Customer)-[:REFERRED]->(:Customer)

// Entity → Event
(:Customer)-[:HAS_EVENT]->(:Event)

// Event → Event (causality)
(:Event)-[:CAUSED]->(:Event)
(:Event)-[:FOLLOWED_BY]->(:Event)

// Decision provenance (CRITICAL for audit)
(:Decision)-[:BASED_ON]->(:Entity)
(:Decision)-[:USED_FEATURE]->(:Feature)
(:Decision)-[:PRODUCED_BY]->(:Model)

// Insight composition
(:Insight)-[:DERIVED_FROM]->(:Decision)
(:Insight)-[:CITES]->(:Entity)

// Action chain
(:Action)-[:TRIGGERED_BY]->(:Insight)
(:Action)-[:AFFECTED]->(:Entity)

// Outcome attribution
(:Outcome)-[:ATTRIBUTED_TO]->(:Action)
(:Outcome)-[:MEASURED_ON]->(:Entity)

// Workflow contains
(:Workflow)-[:HAS_STEP]->(:Step)
(:Workflow)-[:USES_DATA]->(:Entity_Type)
(:Workflow)-[:PRODUCES]->(:Decision_Type)
## 5.2 Cross-Source Master Records (Level 3 Dedup)
Customer “Anh Tuấn 0987654321” xuất hiện ở nhiều sources: - KiotViet POS: customer_id=“KV12345”, phone=“0987654321” - HubSpot CRM: contact_id=“HS98765”, phone=“+84987654321” - Excel manual: row 234, name=“Tuấn Anh”, phone=“098 765 4321”
3 records, 1 person thật. Cần match thành master entity.
### Matching Algorithm — Score-Based
def match_master_entity(new_record, existing_masters):
    candidates = []
    for master in existing_masters:
        score = 0
        
        # Phone exact match (after E.164 normalization) — strongest
        if normalize_phone(new_record.phone) == master.phone_e164:
            score += 50
        
        # Email exact match
        if hash_email(new_record.email) == master.email_hash:
            score += 30
        
        # Name similarity (Vietnamese-aware)
        name_sim = vietnamese_name_similarity(new_record.name, master.name)
        if name_sim > 0.85: score += 15
        elif name_sim > 0.70: score += 8
        
        # Address proximity
        if address_match(new_record.address, master.address): score += 5
        
        # Birth year match
        if new_record.birth_year == master.birth_year: score += 3
        
        candidates.append((master, score))
    
    candidates.sort(key=lambda x: -x[1])
    
    if candidates and candidates[0][1] >= 50:
        return candidates[0][0]  # high confidence
    elif candidates and candidates[0][1] >= 30:
        return candidates[0][0]  # medium — flag for review
    else:
        return None  # no match — create new master
### Master Record Schema
CREATE TABLE silver.master_customers (
  master_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  
  -- Best-known canonical values
  canonical_name TEXT,
  canonical_phone TEXT,
  canonical_email_hash TEXT,
  canonical_address TEXT,
  
  -- Aggregated facts
  first_seen_at TIMESTAMP,
  last_seen_at TIMESTAMP,
  total_ltv NUMERIC(12,2),
  total_transactions INT,
  
  -- Sources contributing
  source_records JSONB,  -- [{source_id, source_record_id, confidence}]
  
  match_confidence NUMERIC(3,2),
  needs_review BOOLEAN DEFAULT false,
  reviewed_by UUID,
  reviewed_at TIMESTAMP
);

CREATE TABLE silver.master_customer_links (
  master_id UUID,
  source_id VARCHAR(50),
  source_record_id VARCHAR(200),
  match_score NUMERIC,
  matched_at TIMESTAMP,
  PRIMARY KEY (master_id, source_id, source_record_id)
);
### Conflict Resolution UI
Khi match score 30-49 (medium confidence):
┌──────────────────────────────────────────────────────────┐
│ Possible Duplicate Detected                              │
├──────────────────────────────────────────────────────────┤
│ NEW (from KiotViet 2026-04-01)                           │
│   Name: Tuấn Anh                                         │
│   Phone: 098 765 4321                                    │
│                                                          │
│ EXISTING MASTER (master_id_abc123)                       │
│   Canonical: Anh Tuấn                                    │
│   Phone: +84987654321                                    │
│   LTV: 12.5M VND                                         │
│   Sources: HubSpot CRM, Excel Manual                     │
│                                                          │
│ Match confidence: 47% (MEDIUM)                           │
│ Phone matches: ✓                                         │
│ Name similarity: 78% (different word order)              │
│                                                          │
│ Action:                                                  │
│   [✓ Merge as same person]  [✗ They are different]      │
│   [⏳ Decide later]                                      │
└──────────────────────────────────────────────────────────┘
## 5.3 Entity Lifecycle State Machines
Mỗi entity type có state machine. AI hiểu transitions → biết entity đang ở đâu trong lifecycle.
### Customer Lifecycle (Retail)
PROSPECT ──┐
           ↓
        NEW (≤30 days, ≤3 transactions)
           ↓
        ACTIVE (regular pattern emerged)
        ╱       ╲
       ↓         ↓
    REGULAR    VIP (LTV > P90)
       ↓         ↓
       ╲       ╱
        AT_RISK (recency growing, frequency dropping)
           ↓
        DORMANT (>60 days no activity)
           ↓
        CHURNED (>180 days)
           ↓
     RECOVERED (came back) → ACTIVE
### State Storage
CREATE TABLE entity_states (
  state_id UUID PRIMARY KEY,
  tenant_id UUID,
  entity_type VARCHAR(50),  -- 'Customer', 'Product', 'Workflow'
  entity_id VARCHAR(200),
  current_state VARCHAR(50),
  state_entered_at TIMESTAMP,
  previous_state VARCHAR(50),
  transition_reason TEXT,
  computed_at TIMESTAMP
);

CREATE TABLE entity_state_transitions (
  id BIGSERIAL PRIMARY KEY,
  tenant_id UUID,
  entity_type VARCHAR(50),
  entity_id VARCHAR(200),
  from_state VARCHAR(50),
  to_state VARCHAR(50),
  trigger_type VARCHAR(50),
  triggered_by_event_id UUID,
  triggered_by_decision_id UUID,
  occurred_at TIMESTAMP
);
### State Computation
def compute_customer_state(customer_id, tenant_id):
    customer = get_customer(customer_id, tenant_id)
    txns = get_transactions(customer_id, last_n_days=180)
    
    days_since_last = (now() - customer.last_seen_at).days if customer.last_seen_at else 999
    txn_count_lifetime = len(txns)
    ltv_percentile = compute_percentile(customer.ltv, all_customers_ltv)
    
    if customer.created_at > now() - 30 and txn_count_lifetime <= 3:
        new_state = 'NEW'
    elif days_since_last > 180:
        new_state = 'CHURNED'
    elif days_since_last > 60:
        new_state = 'DORMANT'
    elif (predicted_churn_prob and predicted_churn_prob > 0.7):
        new_state = 'AT_RISK'
    elif ltv_percentile > 0.9:
        new_state = 'VIP'
    elif customer.previous_state == 'CHURNED' and days_since_last < 30:
        new_state = 'RECOVERED'
    else:
        new_state = 'REGULAR'
    
    if new_state != customer.current_state:
        record_transition(customer_id, customer.current_state, new_state)
        emit_event('customer.state_transition', ...)
### Other Entity Lifecycles
Product Lifecycle: NEW_LAUNCH → GROWING → MATURE → DECLINING → END_OF_LIFE → DISCONTINUED
Workflow Lifecycle: DRAFT → LIVE_OLD → EXPERIMENTAL_NEW → PROMOTED OR ROLLED_BACK → DEPRECATED → ARCHIVED
Transaction Lifecycle: PENDING → COMPLETED OR CANCELLED → REFUND_REQUESTED → REFUNDED → DISPUTED → RESOLVED
Decision Lifecycle (NEW — important): GENERATED → SURFACED → REVIEWED → ACCEPTED OR OVERRIDDEN → ACTIONED OR IGNORED → OUTCOME_TRACKED → FEEDBACK_RECORDED
→ Decision Lifecycle là chìa khóa đóng feedback loop AI (Stage 11).
## 5.4 Why Graph Beats SQL — Example
Query: “Find customers who bought from Store A in last 30 days, AND received campaign X, but did NOT redeem”
SQL (painful):
SELECT DISTINCT c.customer_id 
FROM customers c
JOIN transactions t ON c.customer_id = t.customer_id
WHERE t.store_id = 'A' AND t.date > now() - 30
AND c.customer_id IN (SELECT ... FROM campaigns WHERE id='X')
AND c.customer_id NOT IN (SELECT ... FROM redemptions);
Cypher (natural):
MATCH (c:Customer)-[:BOUGHT]->(:Transaction {store_id: 'A'})-[:WHEN]->(t:Time)
MATCH (c)-[:RECEIVED_CAMPAIGN]->(camp:Campaign {id: 'X'})
WHERE NOT (c)-[:REDEEMED]->(camp)
  AND t.date > date() - duration({days:30})
RETURN c
Graph queries scale better khi business questions càng complex.
## 5.5 Acceptance Criteria — Stage 5
☐ Master record matching ≥85% accuracy on test data
☐ Customer state computed daily for all tenants
☐ State transitions trigger downstream workflows correctly
☐ Cypher queries replace 80% of complex SQL joins by Phase 2
☐ Conflict resolution UI works for medium-confidence matches

# Stage 6. Knowledge Extraction (Parallel Branch — Unstructured Data)
Layer: [L4 — Cognitive Layer]
Mục đích stage: SME có 40-60% knowledge ở dạng unstructured (PDF, DOCX, images, emails, chat logs). Pipeline song song với main flow để extract knowledge từ những asset này → feed vào Memory + Knowledge Graph.
## 6.1 Document Types & Volumes

| Type | % của enterprise knowledge | Examples |
|---|---|---|
| PDF | 40% | Hợp đồng, biên bản họp, báo cáo, SOP |
| DOCX/TXT | 25% | Quy trình, training material, KB notes |
| Images/scans | 15% | Hóa đơn scan, biên lai, name card, chứng từ |
| Emails | 10% | Customer complaints, partner discussions |
| Chat logs | 5% | Zalo OA, Facebook customer service |
| Audio/video | 5% | Meeting recordings (rare Phase 1) |

## 6.2 10-Stage Pipeline
┌─────────────────────────────────────────────────────────┐
│  1. INGEST                                              │
│     Same Bronze paths nhưng /unstructured/              │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  2. PARSE & OCR                                         │
│     PDF → PyMuPDF / pdfplumber                          │
│     PDF scan → Tesseract VN / Azure OCR                 │
│     DOCX → python-docx                                  │
│     Email → MIME parse                                  │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  3. LAYOUT ANALYSIS                                     │
│     LayoutLM v3 / layout-parser                         │
│     Detect: title, headings, paragraphs, tables, figures│
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  4. TABLE EXTRACTION                                    │
│     PDF tables → structured                             │
│     Camelot / Tabula / Azure Form Recognizer            │
│     Bridge: tables → Silver layer (standard pipeline)   │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  5. ENTITY EXTRACTION (NER)                             │
│     Vietnamese NER + Qwen-prompted                      │
│     Detect: persons, orgs, locations, dates, amounts    │
│     Domain entities: customer/product/store names       │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  6. SEMANTIC CHUNKING                                   │
│     Split by section heading / topic shift              │
│     NOT arbitrary 500-token chunks                      │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  7. PII DETECTION + MASKING                             │
│     Per Stage 3 PII rules                               │
│     Plus: faces in images, signatures detection         │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  8. EMBEDDING                                           │
│     BGE-M3 → 1024-dim vectors                           │
│     Per chunk + per entity                              │
│     Store: pgvector (per-tenant namespace)              │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  9. GRAPH LINKING                                       │
│     Link extracted entities to existing Knowledge Graph │
│     New entity → create node                            │
│     Existing → add edge: (Document)-[:MENTIONS]->(Entity)│
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  10. MEMORY INDEXING                                    │
│     Domain knowledge → L4b shared (anonymized)          │
│     Entity-specific → L4a per-tenant                    │
│     Searchable via RAG                                  │
└─────────────────────────────────────────────────────────┘
## 6.3 Per-Document-Type Handling
### Type 1: Digital PDF (text selectable)
def process_digital_pdf(file_path):
    doc = pymupdf.open(file_path)
    sections = []
    for page in doc:
        blocks = page.get_text("blocks")
        sections.extend(parse_blocks_to_sections(blocks))
    return {
        'type': 'digital_pdf',
        'pages': len(doc),
        'sections': sections,
        'tables': extract_tables_camelot(file_path),
        'has_signatures': detect_signatures(doc),
    }
### Type 2: Scanned PDF / Image (needs OCR)
def process_scanned_pdf(file_path):
    images = convert_pdf_to_images(file_path, dpi=300)
    results = []
    for img in images:
        if config.use_azure_ocr:
            ocr_result = azure_ocr.read(img, language='vi')
        else:
            ocr_result = tesseract.image_to_data(img, lang='vie+eng')
        results.append({
            'text': ocr_result.text,
            'confidence_avg': ocr_result.confidence,
        })
    
    # Quality flag: avg confidence < 0.6 → human review
    overall_conf = avg([r['confidence_avg'] for r in results])
    return {'type': 'scanned_pdf', 'pages': results, 'overall_confidence': overall_conf}
### Type 3: DOCX
def process_docx(file_path):
    doc = docx.Document(file_path)
    sections = []
    current_heading = None
    for para in doc.paragraphs:
        if para.style.name.startswith('Heading'):
            current_heading = para.text
        sections.append({
            'heading': current_heading,
            'text': para.text,
            'style': para.style.name,
        })
    tables = [[[cell.text for cell in row.cells] for row in t.rows] for t in doc.tables]
    return {'type': 'docx', 'sections': sections, 'tables': tables}
### Type 4: Email + Type 5: Chat logs
def process_email(eml_file):
    msg = email.message_from_file(eml_file)
    return {
        'type': 'email',
        'from': msg['from'], 'to': msg['to'],
        'subject': msg['subject'], 'date': msg['date'],
        'body': extract_body(msg),
        'attachments': [a.filename for a in get_attachments(msg)],
    }

def process_chat_log(file_path, source='zalo_oa'):
    if source == 'zalo_oa':
        messages = parse_zalo_export(file_path)
    elif source == 'fb_messenger':
        messages = parse_fb_export(file_path)
    
    conversations = group_by_thread(messages)
    summaries = []
    for conv in conversations:
        summary = qwen_summarize(conv['messages'])
        summaries.append({
            'participants': conv['participants'],
            'duration': conv['duration'],
            'message_count': len(conv['messages']),
            'summary': summary,
            'sentiment': detect_sentiment(conv['messages']),
            'topics': extract_topics(conv['messages']),
        })
    return {'type': 'chat_log', 'conversations': summaries}
## 6.4 Use Cases SME
### UC1: SOP Knowledge Base
Customer uploads SOP documents → Kaori extract + index → New employee asks “Cách xử lý complaint kênh online?” → Kaori retrieves từ SOP, answer context-aware.
### UC2: Customer Complaint Mining
Email + chat logs từ Zalo OA → Extract complaint patterns → Cluster (“delivery slow” / “quality” / “staff”) → Per-cluster trend → Link to Customer 360.
### UC3: Contract Analysis
Supplier contracts (PDF) → Extract: parties, terms, prices, expiration → Alert: contract expires 30 days → Compare pricing across suppliers.
### UC4: Invoice Reconciliation
Invoice scans → OCR → Extract: invoice number, date, amount, supplier → Match to ERP records → Flag mismatches/duplicates.
## 6.5 Quotas per Plan

| Plan | Unstructured docs/month | OCR pages/month | Embedding refresh |
|---|---|---|---|
| PILOT | 10 | 50 | Manual |
| ENT BASIC | 100 | 500 | Weekly |
| ENT MID | 1,000 | 10,000 | Daily |
| ENT MAX | Unlimited | Unlimited | Real-time |

## 6.6 Acceptance Criteria — Stage 6
☐ PDF text extraction works for 95% Vietnamese PDFs
☐ OCR confidence reported, < 0.6 → flag review
☐ Entity extraction VN ≥85% precision
☐ Tables extracted with cell-level accuracy ≥90%
☐ Graph linking connects 70% extracted entities to existing
☐ PII masking applied 100%

# Stage 7. Memory System (Cross-Stage)
Layer: [L4 — Cognitive Layer]
Mục đích stage: Memory is HOW Kaori remembers context across queries, sessions, weeks. Without memory, every AI query starts cold. Memory feeds AI Decision (Stage 9) + Insight Composition (Stage 10).
## 7.1 4-Tier Memory Hierarchy
┌────────────────────────────────────────────────────────────────┐
│ L1 — WORKING MEMORY (current request)                          │
│ TTL: request lifetime (seconds)                                │
│ Storage: in-process Python objects                             │
│ Use: current LLM context, intermediate computation             │
└────────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────┐
│ L2 — SHORT-TERM MEMORY (session)                               │
│ TTL: 24 hours default                                          │
│ Storage: Redis Cluster (per-tenant key prefix)                 │
│ Use: agent conversation, multi-turn context                    │
└────────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────┐
│ L3 — EPISODIC MEMORY (recent events)                           │
│ TTL: 30-90 days configurable                                   │
│ Storage: PostgreSQL + pgvector embeddings                      │
│ Use: "Last week we discussed", "User overrode X 3 times"       │
└────────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────┐
│ L4 — LONG-TERM MEMORY (knowledge, patterns)                    │
│ Persistent until contract ends                                 │
│ Storage: Knowledge Graph (Neo4j) + Vector DB + Feature Store   │
│ Use: customer profile, learned patterns, domain knowledge      │
└────────────────────────────────────────────────────────────────┘
## 7.2 Mapping 5 Memory Types → Tier

| Memory type | Kaori storage | Purpose | Example |
|---|---|---|---|
| Episodic | L3 | Specific events with timestamp | “Customer A complained on 2026-04-01” |
| Semantic | L4b shared | General facts, business knowledge | “Vietnamese retail Q1 lull post-Tết” |
| Procedural | L4c | How-to knowledge | “Retention campaign workflow for VIP” |
| Operational | L3-L4a hybrid | Past actions + outcomes | “Voucher 10% to 234 → 67 redeemed” |
| Decision | L4a-c (linked) | Past decisions + context | “Why approve workflow X last month?” |

## 7.3 Memory Write Flow
Event happens →
  L1 (in-memory during processing)
       ↓
  L2 (Redis if part of session)
       ↓ (when session closes OR every 24h cron)
  Summarization step (Qwen 14B → 200-token summary)
       ↓
  L3 (PostgreSQL + pgvector) — Episodic
       ↓ (if importance > 0.7 OR explicit user flag)
  L4 — promoted to:
       L4a if entity-related → Knowledge Graph
       L4b if domain knowledge → Vector DB shared
       L4c if workflow/pattern → Feature Store / Workflow library
## 7.4 Memory Read Flow (RAG hierarchy)
LLM prompt construction:
  1. Always include L1 (current query + system prompt)
  2. Fetch L2 last 10 conversation turns (if session continues)
  3. Semantic search L3 — top 5 episodic memories
  4. Semantic search L4b — top 3 domain knowledge chunks
  5. Knowledge Graph traversal L4a — fetch entity profile
  6. Feature Store L4c — fetch latest features
  7. Compose final prompt within Qwen 32k context window
## 7.5 Memory Importance Scoring
def compute_importance(memory):
    score = 0
    
    # Recency (recent more important)
    days_old = (now() - memory.occurred_at).days
    score += 0.2 * max(0, 1 - days_old / 90)
    
    # Repeat occurrence (mentioned multiple sessions)
    score += 0.3 * min(1, memory.session_appearance_count / 5)
    
    # User explicit flag
    if memory.user_flagged_important:
        score += 0.3
    
    # Outcome significance
    if memory.linked_outcome_value > 10_000_000:  # 10M VND
        score += 0.2
    
    return min(1.0, score)
Memory với score > 0.7 → promote L3 → L4. Score < 0.3 sau 90 ngày → forget.
## 7.6 Memory Service API
class MemoryService:
    def write(tenant_id, memory_type, content, metadata):
        """Write memory at appropriate tier"""
    
    def retrieve(tenant_id, query, top_k=5, tier='auto'):
        """RAG retrieval across tiers"""
    
    def consolidate(tenant_id):
        """Daily cron: L2 → L3 with summarization"""
    
    def promote(tenant_id):
        """Periodic: L3 → L4 based on importance"""
    
    def forget(tenant_id, criteria):
        """Erase per GDPR right-to-erasure or TTL"""
    
    def introspect(tenant_id, entity_id):
        """Show all memories about an entity (audit)"""
## 7.7 Per-Tenant Isolation

| Tier | Isolation | Failure mode if violated |
|---|---|---|
| L1 | Implicit (request scope) | Never crosses |
| L2 | Redis key prefix mem:l2:{tenant}: + ACL | 403 + audit |
| L3 | PostgreSQL row-level WHERE tenant_id | Same as Silver |
| L4a | Neo4j label per tenant + WHERE | Same |
| L4b | SHARED — anonymized only | Audit content quarterly |
| L4c | Model registry filter by tenant_id | 403 cross-tenant load |

L4b is the ONLY cross-tenant memory. Strict review process before any data goes there.
## 7.8 Acceptance Criteria — Stage 7
☐ L2 Redis isolation: cross-tenant read = 403
☐ Multi-turn conversation maintains context
☐ TTL works correctly per tier
☐ Importance scoring promotes L3→L4 reliably
☐ Memory introspection UI for admin/audit
☐ Right-to-erasure clears all 4 tiers within 30d SLA

# Stage 8. Gold Layer — Business Views
Layer: [L2 — Data Plane]
Mục đích stage: Transform Silver clean data + Master Records (Stage 5) → business-ready views/MVs phục vụ analytics, reports, AI inference. Gold = output cuối của Data Plane.
## 8.1 Gold = Views, không phải Tables
Per industry standard (Image 3 reference): Gold object_type = Views (not Tables).
Why views? - Always reflects latest Silver - Can re-define without data migration - Customers có custom Gold views per dept - Cheap to evolve
CREATE VIEW gold.customer_health AS
SELECT ... FROM silver.master_customers c
JOIN silver.transactions t ON ...
WHERE c.tenant_id = current_tenant_id();
But views can be slow → also create materialized views (MVs) for hot queries:
CREATE MATERIALIZED VIEW gold_mv.customer_health
AS SELECT ... FROM gold.customer_health;

CREATE INDEX idx_health_tenant_segment 
ON gold_mv.customer_health (tenant_id, segment);
MVs refreshed daily or on-demand.
## 8.2 Gold Schema (Retail Customer 360 example)
CREATE VIEW gold.customer_360 AS
SELECT
  c.customer_id,
  c.tenant_id,
  c.segment,
  c.ltv,
  c.first_seen_at,
  c.last_seen_at,
  
  -- RFM (auto-derived)
  date_diff('day', max(t.txn_ts), now()) AS recency_days,
  count(distinct t.txn_id) AS frequency_30d,
  sum(t.amount) FILTER (WHERE t.txn_ts > now() - interval '90 days') AS monetary_90d,
  avg(t.amount) FILTER (WHERE t.txn_ts > now() - interval '90 days') AS avg_basket_90d,
  
  -- Behavioral
  std_dev(date_diff('day', lag(t.txn_ts) over (...), t.txn_ts)) AS purchase_interval_variance,
  count(distinct t.product_category) AS category_diversity,
  
  -- Risk signals
  count(*) FILTER (WHERE t.status='refunded') / count(*)::float AS refund_rate_30d,
  
  -- Predictions (from ML — Stage 9)
  m.churn_probability,
  m.churn_risk_label,
  m.revenue_at_risk,
  m.top_factors_vi,
  m.recommended_action,
  m.confidence,
  m.calibration_band,
  
  -- Action tracking (from Stage 11)
  m.is_actioned,
  m.actioned_at,
  m.actioned_by,
  
  c.last_updated_at
  
FROM silver.master_customers c
LEFT JOIN silver.transactions t ON c.master_id = t.customer_master_id
LEFT JOIN model.predictions m ON c.master_id = m.customer_id
WHERE c.tenant_id = current_tenant_id()
GROUP BY c.customer_id, c.tenant_id, c.segment, c.ltv, ...;
Other Gold views: - gold.transaction_daily — daily aggregates - gold.cohort_retention — cohort by signup month - gold.product_performance - gold.channel_performance - gold.store_performance (retail)
## 8.3 Per-Department Customization
# Marketing dept Gold
marketing_gold:
  - gold.customer_360_marketing  # focus: lifecycle, segments
  - gold.campaign_performance
  - gold.cohort_retention
  
# Sales dept Gold  
sales_gold:
  - gold.customer_360_sales  # focus: pipeline, deal stage
  - gold.lead_scoring
  - gold.revenue_forecast

# Operations dept Gold
operations_gold:
  - gold.inventory_health
  - gold.store_performance
  - gold.staff_productivity
## 8.4 Refresh Strategy
Hot Gold MVs (refresh daily 03:00):
  - gold_mv.customer_360 (large, expensive query)
  - gold_mv.cohort_retention (computational heavy)

Warm Gold views (on-demand):
  - gold.daily_kpi_snapshot

Cold Gold (weekly):
  - gold.product_lifecycle_analysis (long horizon)
## 8.5 Cache Layer (Redis)
For sub-second dashboard load:
User opens P2 dashboard "Customer Health"
  → Backend checks Redis: redis.get("gold:tenant_abc:customer_health:2026-04-01")
  → Cache HIT → return < 100ms
  → Cache MISS → query gold_mv → cache 15min TTL → return < 1s
Cache invalidation triggered by: - Pipeline run complete - User action (manual refresh) - TTL expiry
## 8.6 Acceptance Criteria — Stage 8
☐ Gold views refresh successful daily 03:00
☐ Customer 360 query < 1s P50, < 3s P99
☐ MVs auto-refresh on Silver update
☐ Cache hit rate > 70% on dashboard queries
☐ Per-department views accessible per permission
☐ Customer can customize report views (within plan)

# Stage 9. AI Decision Generation
Layer: [L3 AI/ML Plane + L4 Cognitive Layer (Decision primitive tracked)]
Mục đích stage: Take features từ Gold + context từ Memory (Stage 7) → run model inference → produce DECISION với confidence + calibration + explanation. Decision is core unit Kaori operates on.
## 9.1 Decision Generation Flow
Features từ Gold (Stage 8) + Memory context (Stage 7)
          ↓
Model inference (L3 ML Plane)
          ↓
Raw prediction (probability, score)
          ↓
Calibration applied (Platt / Isotonic / Temperature)
          ↓
Confidence band assigned (TRUSTED / REVIEW / UNCERTAIN)
          ↓
SHAP explanation generated (top 3 factors)
          ↓
Decision record persisted with full audit trail
## 9.2 AI Accuracy Lifecycle

| Stage | Time period | Data status | Expected accuracy | Confidence floor |
|---|---|---|---|---|
| Cold Start | D1-D30 | <30 days customer data + industry baseline | 60-65% | 0.5 |
| Warm Up | D31-D60 | 1-2 months tenant data + transfer learning | 65-72% | 0.6 |
| Active Learning | D61-D90 | 2-3 months + active feedback loop | 72-78% | 0.65 |
| Personalized | D91-D180 | 3-6 months + multiple retrains | 78-85% | 0.7 |
| Mature | D180+ | 6+ months + continuous learning | 85-92% | 0.75 |

Critical: Data quality matters MORE than time. Bad data + time = plateau forever (~65%).
## 9.3 Confidence vs Calibration
Confidence ≠ Correctness. Một model có thể self-report confidence 0.85 mà thực tế chỉ 60% đúng. Đây là silent killer của AI products.
### Required Calibration Metrics (track daily)

| Metric | Formula | Target Phase 1 | Target Phase 3 |
|---|---|---|---|
| Brier Score | mean((pred_prob - actual)²) | <0.20 | <0.10 |
| Expected Calibration Error (ECE) | Weighted avg of \|conf - acc\| per bin | <0.10 | <0.03 |
| Maximum Calibration Error (MCE) | Max \|conf - acc\| across bins | <0.15 | <0.05 |

### Calibration Techniques

| Technique | When to use | Phase |
|---|---|---|
| Platt scaling | Binary classification, simple | Phase 1 M3 |
| Isotonic regression | More flexible, larger calibration set | Phase 2 M5 |
| Temperature scaling | LLM confidence outputs | Phase 1 M4 |
| Beta calibration | Heavy class imbalance | Phase 2 |

### Calibration Drift Monitoring (daily cron)
def check_calibration(model_id, tenant_id):
    samples = get_recent_predictions_with_labels(model_id, tenant_id, days=7)
    if len(samples) < 100:
        return None  # not enough signal
    
    ece = compute_ece(samples)
    if ece > 0.10:
        alert_ml_team(f"Calibration drift: {model_id} ECE={ece:.3f}")
        schedule_recalibration(model_id)
## 9.4 Confidence-Based Action Policy
Confidence ≥ 0.85 + ECE < 0.05 → "TRUSTED" badge
                                  Auto-execute OK for ENT MAX with policy

Confidence ≥ 0.85 + ECE > 0.10 → "OVER-CONFIDENT WARNING"
                                  → require manual verify

Confidence 0.65 - 0.84       → "REVIEW NEEDED"
                                  → mandatory verification
                                  → show top 3 SHAP factors

Confidence 0.40 - 0.64       → "AI UNCERTAIN"
                                  → recommend manual investigation
                                  → show alternative scenarios

Confidence < 0.40            → No actionable display
                                  → trigger fallback hierarchy
## 9.5 Fallback Hierarchy (When AI Cannot Predict)
5-level priority:
### Level 1: Domain Expert Rules
Retail rules:
  - if recency > 60 days AND frequency_lifetime > 5 → "Possibly churning"
  - if first_purchase < 7 days AND amount > 5x avg → "VIP onboarding"
  - if return_rate_30d > 30% → "Investigate satisfaction"

Finance rules:
  - if days_past_due > 30 → "Collection priority HIGH"
  - if 3+ failed login → "Security review"
### Level 2: Cohort/Peer Comparison
“Khách này thuộc cohort X. Cohort X có 23% churn rate”
### Level 3: Trend Analysis (aggregate)
Department-level KPI trend, cohort retention curves, anomaly on totals.
### Level 4: Crowd-sourced patterns (Phase 3+)
Patterns learned across tenants in same vertical (anonymized + consent).
### Level 5: Studio Manual Investigation
Customer’s data team manually investigates edge cases.
## 9.6 Decision Record (Audit Trail)
CREATE TABLE model.decisions (
  decision_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  
  -- Subject
  entity_type VARCHAR(50),  -- 'Customer', 'Product', etc.
  entity_id VARCHAR(200),
  
  -- Generation
  model_id VARCHAR(100),
  model_version VARCHAR(50),
  generated_at TIMESTAMP,
  
  -- Inputs (lineage to Stage 5+8)
  features_used JSONB,
  memory_context_ids UUID[],  -- which memories were used
  
  -- Output
  prediction_raw NUMERIC,
  prediction_calibrated NUMERIC,
  prediction_label VARCHAR(50),
  confidence NUMERIC(3,2),
  calibration_band VARCHAR(20),  -- TRUSTED / REVIEW / UNCERTAIN
  
  -- Explanation
  shap_factors JSONB,  -- top factors with weights
  explanation_text_vi TEXT,
  
  -- State (per Decision Lifecycle from Stage 5)
  current_state VARCHAR(50),  -- GENERATED / SURFACED / ACTIONED / etc.
  
  audit_metadata JSONB
);
## 9.7 Domain-Specific Metrics Priority
### Retail

| Priority | Metric |
|---|---|
| 1 | Recency (days since last purchase) |
| 2 | Frequency (purchase count) |
| 3 | LTV |
| 4 | Average Basket Size |
| 5 | Repeat purchase rate |

### Finance / Banking

| Priority | Metric |
|---|---|
| 1 | Probability of Default (PD) |
| 2 | Days past due |
| 3 | Customer profitability |
| 4 | Cross-sell propensity |
| 5 | Fraud risk score |

### Manufacturing

| Priority | Metric |
|---|---|
| 1 | OEE |
| 2 | Yield rate |
| 3 | Defect rate |
| 4 | Downtime % |

## 9.8 AI Risk Responsibility Model
Cốt lõi: “AI không chịu rủi ro nếu dự đoán sai.”
5 nguyên tắc: 1. AI là Co-pilot, không phải Auto-pilot. Mọi action có human approval. 2. Confidence transparency mọi nơi. User luôn thấy “AI tin x%”. 3. Audit trail immutable. Every AI suggestion + every human decision logged. 4. Override always available. User có thể từ chối AI. 5. Disclaimer mọi insight. “⚠️ AI-generated, verify before action”.
### When AI is Wrong — Incident Protocol
Customer reports: "AI dự đoán sai, tôi mất 50tr"
  →
Step 1: Investigation
  - Reproduce: same data, same time, same result?
  - Was confidence shown? What level?
  - Was override option clearly available?

Step 2: Categorize
  - Type A: AI confidence < 0.6 + customer ignored warning → Customer's call
  - Type B: AI confidence > 0.8 but wrong → Kaori issue
  - Type C: System bug → Kaori SLA breach

Step 3: Resolution
  - Type A: Coaching call, no compensation
  - Type B: Apology + model fix + 1-3 month credit
  - Type C: Full refund + SLA credit
## 9.9 Acceptance Criteria — Stage 9
☐ Churn model AUC ≥0.75 on validation set
☐ Calibration ECE <0.10 Phase 1
☐ Decision generation < 100ms P99 per record
☐ SHAP explanation generated 100% with top 3 factors
☐ Decision audit trail complete (lineage to features + memory)
☐ Calibration drift alert fires when ECE > 0.15

# Stage 10. Insight Composition (3-tuyến)
Layer: [L3 AI/ML + L4 Cognitive Layer]
Mục đích stage: Take Decision (Stage 9) + Memory context → compose human-readable Insight format 3-tuyến (chuyện gì / tại sao / nên làm gì) với citations + frameworks.
## 10.1 3-tuyến Format
═══════════════════════════════════════════════════════
  INSIGHT — Marketing Department · 2026-04-22
═══════════════════════════════════════════════════════
  
  📊 CHUYỆN GÌ ĐANG XẢY RA?
  Trong 14 ngày qua, 234 khách VIP có dấu hiệu giảm tần suất
  mua hàng — giảm 38% so với 14 ngày trước đó. Tổng giá trị
  doanh thu tiềm năng đang ở rủi ro: 187 triệu VND.
  
  🔍 TẠI SAO?
  AI phân tích top 3 yếu tố (qua SHAP):
  • [38%] Khách không nhận voucher tháng này (so với 92%
    nhận tháng trước)
  • [29%] Chiến dịch email tháng 4 mở rate giảm xuống 12%
    (baseline 28%)
  • [24%] 3 cửa hàng key tồn kho sản phẩm best-seller dưới 20%
  
  Confidence: 0.74 (chấp nhận được)
  ⚠ Calibration: Predictions ở mức 0.74 thực tế đúng 71% (last 100)
  
  💡 NÊN LÀM GÌ?
  Action 1: Gửi voucher 10% cho 234 khách VIP risk này
            (chi phí ước tính 5tr, ROI dự kiến 12-15x)
  Action 2: A/B test subject line email tháng 5
  Action 3: Re-stock 3 cửa hàng theo demand forecast
  
  [Đã xử lý] [Tạm hoãn] [Không phù hợp + Lý do]
  
  ⚠️ AI-generated — verify before action
═══════════════════════════════════════════════════════
## 10.2 Insight Composition Process
def compose_insight(decision, memory_context, domain_kb):
    # 1. Layer 1: WHAT happened
    what = generate_what_layer(
        decision.prediction,
        decision.entity,
        compare_to_baseline=True
    )
    
    # 2. Layer 2: WHY (using SHAP)
    why = generate_why_layer(
        decision.shap_factors[:3],  # top 3
        translate_to_vietnamese=True,
        cite_sources=True
    )
    
    # 3. Layer 3: HOW (recommendations)
    similar_past_outcomes = memory.retrieve(
        query=decision,
        type='operational',
        top_k=5
    )
    how = generate_how_layer(
        decision,
        domain_kb_recommendations(decision),
        learned_from_outcomes=similar_past_outcomes
    )
    
    # 4. Citations
    citations = collect_citations(decision.features_used + memory_context)
    
    # 5. Confidence display
    confidence_display = format_confidence(
        raw=decision.confidence,
        calibration_band=decision.calibration_band,
        ece_drift=current_ece(decision.model_id)
    )
    
    return Insight(what, why, how, citations, confidence_display)
## 10.3 Frameworks Auto-Generation
Per dept, AI generates analysis theo frameworks:

| Framework | Use case | Output |
|---|---|---|
| SWOT | Strategic position | 4 quadrants với data backing |
| 6W2H | Drill into specific issue | Who/What/When/Where/Why/Whom + How/How much |
| Fishbone (xương cá) | Root cause | Diagram 6M: Man/Machine/Method/Material/Measurement/Mother nature |
| MoM/YoY | Trend over time | Time series với highlight anomaly |
| 5 Why | Deep dive root cause | Iterative why with data validation |

## 10.4 Anti-Hallucination Guardrails
Before insight surfaced:
  1. Citations check: every factual claim must have source
  2. SHAP factors must match actual model output (not invented)
  3. Numbers in insight must trace to Gold view (not LLM-generated)
  4. Confidence band aligned with calibration data
  5. Domain knowledge used must be from authorized KB sources
  6. PII check: insight cannot mention raw PII
If any check fails → log + block insight from surfacing.
## 10.5 Insight Storage
CREATE TABLE cognitive.insights (
  insight_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  department_id UUID,
  
  -- Source
  decision_id UUID REFERENCES model.decisions(decision_id),
  generated_at TIMESTAMP,
  
  -- Content
  layer_what TEXT,
  layer_why TEXT,
  layer_how JSONB,  -- list of actions
  
  -- Citations (lineage)
  citations JSONB,  -- [{source_type, source_id, relevance}]
  
  -- Confidence
  confidence_display VARCHAR(50),  -- TRUSTED / REVIEW / UNCERTAIN
  
  -- Frameworks (if applicable)
  swot_data JSONB,
  framework_data JSONB,
  
  -- User interaction
  viewed_at TIMESTAMP,
  viewed_by UUID,
  user_rating VARCHAR(20),  -- thumbs_up / thumbs_down / null
  user_action_taken VARCHAR(50),  -- actioned / dismissed / ignored
  
  -- Lifecycle (per Decision Lifecycle Stage 5)
  current_state VARCHAR(50),  -- SURFACED / REVIEWED / ACTIONED / EXPIRED
  shelf_life_until TIMESTAMP,  -- expire if not actioned
  
  -- Audit
  audit_metadata JSONB
);
## 10.6 Acceptance Criteria — Stage 10
☐ Insight generation < 10s P99
☐ 100% insights include citations
☐ Hallucination rate < 2% (manually sampled 50/week)
☐ User feedback (thumbs up/down) tracked
☐ SWOT analysis generated weekly per department
☐ All numbers in insight traceable to Gold view

# Stage 11. Action Runtime (8 Sub-Stages)
Layer: [L4 — Cognitive Layer]
Mục đích stage: Đây là điểm Kaori KHÁC BI tools. Insight không phải endpoint — nó là start of execution chain. 8 sub-stages khép feedback loop về model retrain.
## 11.1 Full Chain (8 Sub-Stages)
DATA → DECISION → INSIGHT → RECOMMENDATION → APPROVAL → 
EXECUTION → TRACKING → OUTCOME → FEEDBACK → MODEL RETRAIN
8 stages, 7 transitions. Mỗi stage có state, owner, SLA, audit.
## 11.2 Stage Definitions
### Sub-Stage A: DECISION → INSIGHT (already done in Stage 10)
### Sub-Stage B: INSIGHT → RECOMMENDATION
trigger: insight surfaced
inputs:
  - insight
  - tenant policy (auto-action thresholds)
  - workflow library (matching workflows exist?)
process:
  - generate top 1-3 recommended actions
  - each action: type, target, estimated impact, cost
  - blast radius pre-check
outputs:
  - recommendation: {actions, urgency, recommended_owner}
state: RECOMMENDED
### Sub-Stage C: RECOMMENDATION → APPROVAL (per Policy Engine)
trigger: recommendation generated
inputs:
  - recommendation
  - workflow.risk_class (LOW/MEDIUM/HIGH/CRITICAL)
  - approval_graph
process:
  - identify required approvers per Policy Engine
  - notify approvers
  - wait or timeout per policy
outputs:
  - approval: {approved_by, decision, reason, timestamp}
state: APPROVED OR REJECTED
audit: all approver responses logged
### Approval Graph
approval_graph:
  LOW:
    auto_approve: true
    log_only: true
    
  MEDIUM:
    require_approve_from:
      - role: department_manager
      - count: 1
    timeout: 24h
    timeout_action: deny
    
  HIGH:
    require_approve_from:
      - role: department_manager
      - count: 1
      - AND
      - role: enterprise_manager
      - count: 1
    timeout: 48h
    timeout_action: escalate_to_admin
    
  CRITICAL:
    require_approve_from:
      - role: department_manager
      - count: 1
      - AND
      - role: enterprise_manager
      - count: 1
      - AND
      - role: compliance_officer
      - count: 1
    timeout: 72h
    timeout_action: deny
    require_evidence: true
    require_reason: true
### Sub-Stage D: APPROVAL → EXECUTION
trigger: approved
inputs:
  - approved recommendation
  - integration credentials (e.g., SendGrid for email)
process:
  - execute action via tool/integration
  - capture evidence (e.g., email_id from SendGrid)
outputs:
  - action: {action_id, performed_by_system, evidence, completion_status}
state: EXECUTED
rollback_window: 24h for HIGH/CRITICAL
### Sub-Stage E: EXECUTION → TRACKING
trigger: action executed
process:
  - schedule outcome measurement (7d, 14d, 30d windows)
  - define outcome metric
  - persist tracking task
state: TRACKING
### Sub-Stage F: TRACKING → OUTCOME
trigger: tracking window arrives
process:
  - measure outcome metric
  - compare to baseline / control / counterfactual
  - compute attribution
outputs:
  - outcome: {metric_name, value, baseline, attribution, attributed_revenue}
state: OUTCOME_TRACKED
### Sub-Stage G: OUTCOME → FEEDBACK
trigger: outcome tracked
process:
  - link outcome → action → decision (full chain via lineage)
  - update model training data (label generation)
  - if outcome significantly differs from prediction → flag for retrain
outputs:
  - feedback record contributes to next training cycle
state: FEEDBACK_RECORDED
### Sub-Stage H: FEEDBACK → MODEL RETRAIN
Trigger conditions: - Drift detected (ECE > 0.15) - N new feedback records collected (e.g., 1000) - Scheduled (monthly) - Manual ML team request
## 11.3 Blast Radius Pre-Check
Before execute, simulate:
def simulate_blast_radius(workflow_id, dry_run=True):
    return {
        'entities_count': N,
        'entities_sample': [...first 10 IDs],
        'cost_estimate_vnd': X,
        'downstream_workflows': [list of dependent workflows],
        'reversibility_score': 0-1,
        'risk_score': 0-100
    }
UI shows: “If you run this, 1,247 customer records updated. 3 downstream workflows triggered. Estimated cost: 15M VND voucher campaign.”
## 11.4 Rollback Capability
workflow:
  rollback:
    available: true
    strategy: 'inverse_action'  # generate inverse SQL/API calls
    window: 24h
    requires_approval: same as forward (for HIGH/CRITICAL)
    audit: full inverse action log
Rollback button visible 24h after run for HIGH/CRITICAL workflows.
## 11.5 Action Runtime Implementation (Temporal-based)
class ActionRuntime:
    """
    Orchestrates Decision → Outcome chain.
    Built on Temporal workflow engine.
    """
    
    def on_decision_generated(self, decision):
        """Sub-stage A → B"""
        insight = self.insight_engine.compose(decision)
        self.memory.write_episodic(insight)
        emit_event('insight.generated', insight)
        
    def on_insight_surfaced(self, insight):
        """Sub-stage B → C"""
        recommendations = self.recommend_actions(insight)
        emit_event('recommendation.generated', recommendations)
        
    def on_recommendation(self, recommendation):
        """Sub-stage C → D"""
        approval_required = self.policy_engine.evaluate(recommendation)
        if approval_required:
            self.start_approval_workflow(recommendation)
        else:
            self.proceed_to_execution(recommendation)
    
    def on_approved(self, approval):
        """Sub-stage D → E"""
        try:
            action = self.execute(approval.recommendation)
            self.audit.log(action)
            self.start_tracking(action)
        except ExecutionError as e:
            self.handle_execution_failure(approval, e)
    
    def on_action_executed(self, action):
        """Sub-stage E → F"""
        schedule_at = action.executed_at + action.tracking_window
        temporal.schedule_workflow(
            'measure_outcome',
            args=[action.id],
            run_at=schedule_at
        )
    
    def on_outcome_tracked(self, outcome):
        """Sub-stage G → H"""
        # Feed back into model
        self.model_trainer.add_training_record(
            features=outcome.action.decision.features,
            prediction=outcome.action.decision.prediction,
            actual_outcome=outcome.value
        )
        # Update Memory L4
        self.memory.promote_to_long_term(outcome)
## 11.6 UI: Action Status
┌──────────────────────────────────────────────────────────┐
│ INSIGHT: 234 VIP customers at risk                       │
│ ────────────────────────────────────────────────────────│
│ Status: [✓ APPROVED] → [▶️ EXECUTING] → [⏳ TRACKING]   │
│                                                          │
│ Stage history:                                           │
│ • 14:32 Decision generated (model: churn_v3.2.1)        │
│ • 14:33 Insight composed                                │
│ • 14:34 Recommendation: Send voucher 10%                │
│ • 14:45 Approved by Marketing Manager                   │
│ • 14:46 Execution started: SendGrid campaign #abc123    │
│ • 14:47 ✓ 234 emails sent                               │
│ • 14:48 ⏳ Tracking window: 14 days                     │
│ • Expected outcome on: 2026-04-15                       │
└──────────────────────────────────────────────────────────┘
## 11.7 Action Failure Handling
# In execution stage:
try:
    result = sendgrid.send_batch(emails)
except APIException as e:
    # Action marked PARTIALLY_FAILED
    action.update_status('partial_failure')
    
    sent_ids = [r.id for r in result.successful]
    failed_ids = [r.id for r in result.failed]
    
    # Decision: retry failed
    schedule_retry(failed_ids, delay=300)
    
    audit.log({
        'action_id': action.id,
        'event': 'partial_failure',
        'sent': len(sent_ids),
        'failed': len(failed_ids)
    })
    
    notify(action.workflow.owner, 'partial_execution')
User sees: “Action partially executed: 220 of 234 emails sent. 14 retrying.”
## 11.8 Critical: Feedback Loop closes Learning
prediction(model_v1, customer_X) = "HIGH risk, p=0.82"
    ↓
action: send voucher 10%
    ↓
outcome 14d later: customer made purchase = retained
    ↓
feedback: prediction was correct, action effective
    ↓
training data: (features, label=retained_after_action)
    ↓
model_v2 retrained with this data
    ↓
better predictions over time
Without explicit Action Runtime, this loop never closes → model stays at cold-start performance forever.
## 11.9 Acceptance Criteria — Stage 11
☐ User clicks “Đã xử lý” → action recorded với evidence
☐ LOW risk auto-approved
☐ MEDIUM/HIGH risk → notify approver, wait response
☐ Email sending works via SendGrid
☐ Audit log per stage transition complete
☐ Action status visible real-time in UI
☐ Tracking + outcome measurement automated
☐ Feedback feeds model retraining

# Stage 12. Output Delivery
Layer: [L5 — Application Layer]
Mục đích stage: Deliver insights, decisions, actions to humans through P2 Enterprise Portal, P3 Studio, emails, notifications. Final mile của pipeline.
## 12.1 Delivery Channels

| Channel | Use case | Delay |
|---|---|---|
| In-app dashboard (P2) | Daily decision review | Real-time |
| Email reports | Weekly/monthly digest | Scheduled |
| Slack notifications | Urgent insights | Real-time |
| Webhook (custom) | ENT MAX integration | Real-time |
| PDF export | Stakeholder presentations | On-demand |
| API endpoint | Programmatic access | Real-time |

## 12.2 Reports Auto-Generated per Plan
Daily reports (auto, 7am):
  - Department KPI snapshot
  - Top 10 risks alerts
  - Yesterday's performance summary

Weekly reports (Monday 7am):
  - Department deep-dive
  - WoW comparison
  - Workflow effectiveness

Monthly reports (1st 7am):
  - Executive summary all departments
  - ROI realized
  - Action conversion rate
  - Recommendations for next month
## 12.3 Customer Dashboard (Module 2.3a in P2)
┌──────────────────────────────────────────────────────────┐
│ Marketing Department · Today                             │
├──────────────────────────────────────────────────────────┤
│ 🎯 NEW INSIGHTS (12)                                     │
│  ⚠ 234 VIP customers at risk     [View] [Action]        │
│  ✓ Cohort H2 2025 retention up    [View]                │
│  ⚠ Email open rate dropped 38%   [View] [Action]        │
│                                                          │
│ 📊 KPIs THIS WEEK                                        │
│  • Active customers: 14,237 (+3.2%)                     │
│  • Revenue: 187M VND (+5.8%)                            │
│  • Churn alerts: 234 (+15.6% — investigate)             │
│                                                          │
│ ⏳ ACTIONS IN PROGRESS (5)                               │
│  • Voucher campaign #abc123 — 14d tracking              │
│  • A/B test email subject — 7d remaining                │
│                                                          │
│ 📈 HEALTH SCORE                                          │
│  78/100 ⚠ ACCEPTABLE                                    │
│  [View details]                                         │
└──────────────────────────────────────────────────────────┘
## 12.4 Output Quotas per Plan

| Quota | PILOT | ENT BASIC | ENT MID | ENT MAX |
|---|---|---|---|---|
| Auto reports/month | 5 | 20 | 100 | Unlimited |
| Custom report templates | 0 | 3 | 15 | Unlimited |
| Distribution channels | Email | + In-app | + Slack | + Webhook |
| Export formats | PDF | PDF, Excel | + CSV, JSON | + Custom |
| Scheduled reports | ✗ | Weekly | Daily | Hourly |
| Multi-department aggregate | ✗ | ✗ | ✓ | ✓ |
| Real-time updates | ✗ | ✗ | ✓ | ✓ |
| Embed external | ✗ | ✗ | ✓ | ✓ |

## 12.5 Acceptance Criteria — Stage 12
☐ Daily reports sent on schedule (7am tenant timezone)
☐ PDF export works with proper branding per tenant
☐ Slack integration delivers urgent insights real-time
☐ Customer can customize report templates within plan
☐ Dashboard load < 2s P99
☐ Webhook delivery success rate > 99% (with retry)

# PHẦN III — CROSS-CUTTING (touch nhiều layers)
# Phần 13. Lineage Tracking
Layers: [L2 + L3 + L4 — across stages]
Mục đích: Trace mọi output back to inputs. Phục vụ debugging, audit, compliance, explainability.
## 13.1 Lineage Schema
CREATE TABLE data_lineage (
  lineage_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  
  -- What was created
  asset_type VARCHAR(50),  -- 'bronze_file', 'silver_table', 'gold_view', 'decision', 'insight', 'action'
  asset_id VARCHAR(200) NOT NULL,
  asset_path VARCHAR(500),
  
  -- Where it came from
  upstream_assets JSONB,  -- [{asset_type, asset_id}]
  
  -- How it was created
  pipeline_id UUID,
  pipeline_step VARCHAR(100),
  rules_applied JSONB,
  code_version VARCHAR(50),
  
  -- When + Who
  created_at TIMESTAMP NOT NULL,
  created_by UUID,
  
  -- Stats
  record_count INTEGER,
  size_bytes BIGINT,
  schema_hash VARCHAR(64),
  checksum VARCHAR(64),
  
  INDEX (tenant_id, asset_type, created_at DESC),
  INDEX (asset_id)
);

-- Lineage edges (for graph queries)
CREATE TABLE data_lineage_edges (
  parent_lineage_id UUID,
  child_lineage_id UUID,
  edge_type VARCHAR(50),  -- 'derived_from', 'transformed_to', 'aggregated_from'
  PRIMARY KEY (parent_lineage_id, child_lineage_id)
);
## 13.2 Lineage Capture Points
1. Stage 1 Bronze write (from upload)
   - asset: bronze file
   - upstream: source upload

2. Stage 3 Silver write (from Bronze + cleaning rules)
   - asset: silver partition
   - upstream: 1+ bronze files
   - rules_applied: list

3. Stage 5 Master record creation
   - asset: master entity
   - upstream: 1+ source records that matched

4. Stage 8 Gold materialization
   - asset: gold MV
   - upstream: silver tables joined

5. Stage 9 Decision generation
   - asset: model.decisions row
   - upstream: features used + memory used
   - model_version

6. Stage 10 Insight generation
   - asset: insight document
   - upstream: decision + LLM prompt + KB sources

7. Stage 11 Action execution
   - asset: action record
   - upstream: insight + workflow + approval

8. Stage 11 Outcome measurement
   - asset: outcome record
   - upstream: action + measurement features
## 13.3 Lineage Queries
### “Where did this insight come from?”
WITH RECURSIVE lineage_chain AS (
  SELECT lineage_id, asset_type, asset_id, upstream_assets, 0 as depth
  FROM data_lineage
  WHERE asset_id = 'insight_xyz789'
  
  UNION ALL
  
  SELECT dl.lineage_id, dl.asset_type, dl.asset_id, dl.upstream_assets, lc.depth + 1
  FROM data_lineage dl
  JOIN lineage_chain lc ON dl.asset_id = ANY(...)
  WHERE lc.depth < 10
)
SELECT * FROM lineage_chain ORDER BY depth;
### “What insights are affected if I delete this Bronze file?” (Impact analysis)
WITH RECURSIVE downstream AS (
  SELECT lineage_id, asset_id, asset_type, 0 as depth
  FROM data_lineage
  WHERE asset_id = 'bronze_file_abc'
  
  UNION ALL
  
  SELECT child.lineage_id, child.asset_id, child.asset_type, ds.depth + 1
  FROM data_lineage_edges edge
  JOIN data_lineage child ON edge.child_lineage_id = child.lineage_id
  JOIN downstream ds ON edge.parent_lineage_id = ds.lineage_id
  WHERE ds.depth < 10
)
SELECT asset_type, count(*) FROM downstream GROUP BY 1;
## 13.4 Time-Travel Queries
“Show me dashboard as of 2 weeks ago”:
SELECT * FROM gold.customer_health
WHERE asset_created_at <= '2026-04-01T00:00:00Z'
  AND tenant_id = current_tenant_id();
## 13.5 Lineage UI (for admin/audit)
┌──────────────────────────────────────────────────────┐
│ Lineage View — Insight "234 VIP at risk"             │
├──────────────────────────────────────────────────────┤
│  insight_xyz789                                      │
│       ↑                                              │
│  prediction_set_001 (model: churn_v3.2.1)           │
│       ↑                                              │
│  features_2026-04-01 (feature_store)                │
│       ↑                                              │
│  ┌────────────────┬────────────────┐                │
│  silver.customers  silver.transactions               │
│       ↑                ↑                            │
│  bronze:upl_xyz    bronze:upl_abc                    │
│  (KiotViet)        (HubSpot)                        │
│  uploaded: 2026-03-30                                │
│                                                      │
│ [View raw upload] [Query timeline] [Export audit]   │
└──────────────────────────────────────────────────────┘

# Phần 14. Error Handling & DLQ
Layers: [All — error can happen anywhere]
## 14.1 Error Taxonomy

| Code | Severity | Stage | Example | Recovery |
|---|---|---|---|---|
| E_UPL_001 | HIGH | 1 | File too large | User retry smaller |
| E_UPL_002 | HIGH | 1 | Invalid format | User check format |
| E_UPL_003 | MEDIUM | 1 | Encoding undetectable | Try multiple encodings |
| E_UPL_004 | LOW | 1 | Network interrupt | Resume upload |
| E_BRZ_001 | HIGH | 1 | S3 write fail | Retry exponential |
| E_BRZ_002 | MEDIUM | 1 | Checksum mismatch | Re-upload |
| E_SCH_001 | HIGH | 2 | Missing essential column | User fix mapping |
| E_SCH_002 | MEDIUM | 2 | Column type incompatible | LLM re-detect |
| E_SCH_003 | LOW | 2 | Optional column missing | Continue with NULL |
| E_CLN_001 | HIGH | 3 | Rule application fail | DLQ + alert |
| E_CLN_002 | MEDIUM | 3 | High null rate after rules | Customer review |
| E_PII_001 | CRITICAL | 3 | PII detected unexpected col | Block, notify |
| E_DUP_001 | LOW | 3 | High duplicate rate | Customer review |
| E_SLV_001 | HIGH | 3 | Schema enforcement fail | DLQ |
| E_SLV_002 | MEDIUM | 3 | FK violation | Skip + log |
| E_GLD_001 | MEDIUM | 8 | Materialization fail | Retry |
| E_GLD_002 | LOW | 8 | Cache miss | Compute on-demand |
| E_PRD_001 | HIGH | 9 | Model serving fail | Fallback to rules |
| E_PRD_002 | MEDIUM | 9 | Confidence too low | Show with warning |
| E_INS_001 | HIGH | 10 | Hallucination detected | Block insight |
| E_INS_002 | MEDIUM | 10 | Citations missing | Generate without insight |
| E_ACT_001 | CRITICAL | 11 | Approval timeout | Per policy |
| E_ACT_002 | HIGH | 11 | Execution API fail | Retry + partial handling |
| E_OUT_001 | MEDIUM | 11 | Tracking measurement fail | Re-schedule |

## 14.2 DLQ Strategy
For each error:
  1. Categorize per error code
  2. Decide:
     CRITICAL → Block pipeline, alert immediately
     HIGH → Retry 3x exp backoff → DLQ if fail
     MEDIUM → Retry 1x → log + continue
     LOW → Log + continue
  3. Write to DLQ topic with full context
DLQ schema:
{
  "error_id": "err_abc123",
  "tenant_id": "tenant_xyz",
  "error_code": "E_SLV_001",
  "severity": "HIGH",
  "stage": "Stage 3",
  "occurred_at": "2026-04-01T...",
  "pipeline_id": "pipe_001",
  "step": "schema_enforcement",
  "error_details": {...},
  "retry_history": [...],
  "resolution_status": "pending",
  "assigned_to": null
}
## 14.3 DLQ Dashboard (CSM/Engineering)
┌────────────────────────────────────────────────────────┐
│ DLQ Inbox — 14 active errors                          │
├────────────────────────────────────────────────────────┤
│ CRITICAL (1):                                          │
│   E_PII_001 — Tenant ABC — phone in notes column      │
│   2 min ago | [Investigate] [Mark reviewed]           │
│                                                        │
│ HIGH (5):                                              │
│   E_SCH_001 — Tenant DEF — missing customer_id        │
│   45 min ago | [Investigate] [Reach customer]         │
│   ...                                                  │
│                                                        │
│ MEDIUM (8):  ...                                       │
│                                                        │
│ ─── Filters: [All severities] [All tenants] ───       │
└────────────────────────────────────────────────────────┘
## 14.4 Recovery Workflows
### For E_SCH_001 (Missing essential column):
CSM gets alert
Check upload metadata
Reach customer (Email/Slack/Phone)
Customer either re-export or manually map
Resolution logged
### For E_PII_001 (Unexpected PII):
PIPELINE BLOCKED automatically
Alert Compliance + CSM immediately
Investigate: which rows, which column, acceptable?
Decision: apply masking + retry / reject / override
Document outcome

# Phần 15. Versioning & Schema Evolution
## 15.1 File Versioning
When customer re-uploads same logical file:
CREATE TABLE file_versions (
  version_id UUID PRIMARY KEY,
  logical_id UUID,  -- shared across versions of same logical file
  upload_id UUID,
  version_number INT,
  is_active BOOLEAN,
  superseded_by UUID,
  uploaded_at TIMESTAMP,
  uploaded_by UUID,
  reason TEXT,  -- why re-uploaded?
  
  PRIMARY KEY (version_id),
  UNIQUE (logical_id, version_number)
);
## 15.2 Re-process Strategy
Strategy A: Always re-process (Phase 1)
  - For each new version, re-run Bronze → Silver → Gold
  - Pro: simple, always latest
  - Con: expensive at scale

Strategy B: Differential update (Phase 3)
  - Compute diff between v1 and v2
  - Only re-process changed rows
  - Pro: efficient
  - Con: complex

Strategy C: User decides (Phase 1 default)
  - Show diff to user
  - User confirms re-process scope
## 15.3 Schema Evolution Handling
Detection (auto):
  - Diff vs previous schema
  - Detect: column added / removed / type changed / renamed

Severity → Action:
  Add column: LOW → auto-include
  Remove column: MEDIUM → alert if used downstream
  Type change: HIGH → require approval
  Rename column: HIGH → Schema Migration Wizard

Workflow MEDIUM/HIGH:
  - Alert customer Manager
  - Open Schema Migration Wizard
  - Customer approves changes
  - Apply with rollback option
## 15.4 Backfill Strategy
When customer wants to load 2 years historical data:
Phase 1: Initial discovery
  - How much data? Volume estimate
  - Schema consistent over time?

Phase 2: Plan
  - Break into chunks (1 month per chunk)
  - Schedule during off-peak
  - Allow user monitor

Phase 3: Execute
  - Process 1 chunk at a time
  - Validate quality scorecard per chunk
  - User confirms before next
  - Auto-pause if quality drops

Phase 4: Verify
  - End-to-end validation
  - Compare aggregates with customer's historical reports
  - Sign-off

# Phần 16. Multi-tenant Security
Layers: [L1 + L2 + L3 + L4 — cross-cutting]
## 16.1 Tenant Encryption Keys (Envelope)
encryption_strategy:
  approach: "envelope encryption"
  
  per_tenant:
    DEK (Data Encryption Key): generated unique per tenant
    KEK (Key Encryption Key): managed by Vault, rotated quarterly
    DEK encrypted by KEK, stored alongside data
    Plaintext DEK only in memory during use
  
  key_rotation:
    KEK: every 90 days
    DEK re-encryption: every 365 days
    on_key_compromise: immediate rotation + re-encrypt
  
  storage_areas:
    s3_bronze: SSE-C with per-tenant key
    clickhouse: column-level encryption for PII
    postgres: row-level + column encryption for sensitive
    redis: encrypt-at-rest with per-tenant key prefix
    vector_db (pgvector): namespace-level encryption
## 16.2 Vector DB Tenant Isolation
class TenantVectorStore:
    def __init__(self, tenant_id):
        self.namespace = f"vec_{tenant_id}"
    
    def search(self, query_vec, k=10):
        sql = f"""
        SELECT * FROM embeddings 
        WHERE tenant_id = '{current_tenant_id()}' 
        ORDER BY embedding <-> '{query_vec}' 
        LIMIT {k}
        """
        # CRITICAL: tenant_id check enforced at:
        # 1. Application code
        # 2. PostgreSQL RLS (last line of defense)
Test mandatory: TenantIsolationTest_VectorDB suite — attempt cross-tenant search expecting 0 results.
## 16.3 Row-Level Security (RLS)
ALTER TABLE silver.customers ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON silver.customers
USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

-- Application middleware sets:
SET app.current_tenant_id = '${jwt.tenant_id}';
RLS = last line of defense.
## 16.4 Attribute-Based Access Control (ABAC)
Beyond RBAC, ABAC adds attribute conditions:
policy:
  name: "Marketing Manager view PII for own dept customers"
  effect: ALLOW
  subject:
    role: MARKETING_MANAGER
  resource:
    type: silver.customers
    attributes:
      pii_fields: [name, phone, email]
  conditions:
    - subject.department_id == resource.department_id
    - subject.tenant_id == resource.tenant_id
    - resource.sensitivity_tag != 'RESTRICTED'
    - context.access_reason is not null
  audit: 
    - log_to: pii_access_log
    - retention: 7_years
## 16.5 Secret Rotation
secrets:
  database_passwords:
    rotation: every 90 days
    automation: HashiCorp Vault dynamic secrets
    
  api_keys:
    rotation: every 180 days OR on suspicion
    
  jwt_signing_keys:
    rotation: every 30 days
    key_versioning: support 2 versions concurrent
    
  encryption_kek:
    rotation: every 90 days
    process: all data re-keyed (background task)
## 16.6 Audit Immutability
audit_logs:
  storage: PostgreSQL append-only
  protection:
    - DELETE/UPDATE blocked at application layer
    - DB role for app cannot DELETE
    - Daily integrity check (hash chain)
    - Critical events also written to S3 with WORM lock
  retention:
    standard: 2 years
    compliance: 7 years
## 16.7 Tenant-level Model Policies
tenant_ai_policy:
  tenant_id: "abc123"
  
  llm_routing:
    pii_data: "internal_only"  # NEVER external
    non_pii: "any"  # OK external
  
  auto_action:
    enabled: false  # ALL require human approval
  
  data_residency:
    storage: "VN_only"
    transit: "VN_only"
    
  model_governance:
    custom_prompts: false
    model_versions: ["v3.2.1", "v3.2.0"]  # whitelisted only
    feature_flags: ["churn_classifier", "insight_engine"]

# PHẦN IV — REFERENCE
# Phần 17. Architecture Choice — Medallion + ETL Framework Mapping
## 17.1 5 Patterns Compared

| Pattern | Pros | Cons | Best for |
|---|---|---|---|
| Inmon (3NF EDW) | Highly normalized, no redundancy | Complex, slow analytical | Large enterprise, fixed schema |
| Kimball (Star schema) | Fast analytics, easy understand | Pre-defined dims inflexible | BI-heavy, structured business |
| Data Vault | Flexible to schema change, audit-friendly | Steep learning, complex ETL | Banks, healthcare, complex orgs |
| Medallion (Bronze/Silver/Gold) | Simple, scales well, lake-based | Younger pattern, less mature tooling | Modern data lake, cloud-native |
| Data Mesh | Domain ownership, decentralized | Org overhead, governance complex | Very large org with strong data culture |

## 17.2 ADR — Why Kaori Chooses Medallion
Decision: Use Medallion (Bronze/Silver/Gold) as primary data architecture.
Context: - Multi-tenant SaaS — need isolation per tenant - Heterogeneous sources (POS/CRM/Excel/marketplace APIs) - Vietnamese SME có data bẩn — need staging layer - Customer’s data team will collaborate (Studio) - Cloud-native (S3 + ClickHouse + PostgreSQL)
Alternatives considered:
Inmon (EDW 3NF): Rejected — too rigid for messy SME data.
Kimball Star Schema: Considered. Will adopt Star Schema inside Gold layer as data marts.
Data Vault: Considered for Bank/Healthcare. Steep learning. Reserved for Special Domain Supplements.
Data Mesh: Rejected — requires customer multi-team domain ownership. Premature.
Medallion (chosen): Simple, lake-aligned, industry standard with Databricks/Delta patterns.
Consequences:
Positive: - Easy onboarding for customer data team - Aligns with modern tooling (Spark, Delta, Iceberg compatible) - Clear separation: Engineer (Bronze/Silver) → Analyst (Silver/Gold) → Business User (Gold) - Audit trail via Bronze immutability
Negative: - Less normalized than Inmon → some redundancy - Less audit-rich than Vault → mitigation: explicit lineage tables (Phần 13)
## 17.3 Mapping Industry Terms to Kaori

| Industry term | Kaori implementation |
|---|---|
| Inmon EDW | Not used directly. Silver layer denormalized. |
| Kimball Star | Used in Gold layer as fact + dim MVs. |
| Data Vault Hub/Link/Sat | Used in Master Records (Silver) for cross-source matching. |
| Lambda Architecture | Used in pipeline runtime (Phase 2+). |
| Kappa Architecture | Used for ENT MAX real-time pipelines. |
| Data Lake | = Bronze layer (S3 raw). |
| Lakehouse | = Bronze + Silver in S3 with ClickHouse query engine. |
| Data Warehouse | = Gold layer (MVs in PostgreSQL/ClickHouse). |
| Data Mesh | Future (Phase 3+). |

## 17.4 ETL Framework Mapping
### Extract (per industry mind map)

| Branch | Kaori implementation | Stage |
|---|---|---|
| Pull Extraction | Connector workers cron-based | Stage 1 |
| Push Extraction | Webhook receivers /api/v1/ingest/event | Stage 1 |
| Full Extraction | Initial backfill 6-24 months | Stage 1 |
| Incremental Extraction | Cursor-based (modified_date > last_sync) | Stage 1 |
| Manual Data Extraction | UI drag-drop upload | Stage 1 |
| Database Querying | CDC via Debezium for ENT MAX | Stage 1 |
| File Parsing | CSV/Excel/JSON parsers in Wizard | Stages 1-2 |
| API Calls | Pull connectors per Connector Library | Stage 1 |
| Event Based Streaming | Kafka topic kaori.ingest.bronze.* | Stage 1 |
| Web Scraping | NOT supported Phase 1 | — |
| CDC | Phase 3 for ENT MAX with on-prem DBs | Stage 1 |

### Transform — Data Cleansing

| Branch | Kaori implementation | Stage |
|---|---|---|
| Remove Duplicates | Within-file (Stage 3) + Master records (Stage 5) | Stages 3, 5 |
| Outlier Detection | Statistical (P99.5) + LLM-assisted | Stage 3 |
| Data Type Casting | Schema enforcement | Stage 3 |
| Handling Unwanted Spaces | Universal Rule U-2 | Stage 3 |
| Handling Invalid Values | Domain rules + DLQ | Stages 3, 14 |
| Handling Missing Data | Per-rule policy: drop / impute / flag | Stage 3 |
| Data Filtering | User-defined rules in Wizard | Stage 3 |

### Transform — Data Transformation

| Branch | Kaori implementation | Stage |
|---|---|---|
| Data Normalization & Standardization | Domain rules R-1 to R-5 | Stage 3 |
| Business Rules & Logic | Tenant-custom rules (Layer 3) | Stage 3 |
| Data Aggregations | Gold layer MVs | Stage 8 |
| Data Integration | Cross-source master records | Stage 5 |
| Data Enrichment | Add external data (weather, holidays) Phase 2 | Stage 8 |
| Derived Columns | Computed in Silver/Gold (RFM, segments) | Stages 3, 8 |

### Load

| Branch | Kaori implementation | Stage |
|---|---|---|
| Batch Processing | Default — daily/hourly per plan | Stages 1-8 |
| Stream Processing | ENT MAX only — Kafka + Flink | Stages 1-8 |
| Full Load (Truncate & Insert) | Used for Bronze (rare — usually append) | Stage 1 |
| Full Load (Upsert) | Used for Master Records refresh | Stage 5 |
| Incremental (Upsert) | Default for Silver new rows | Stage 3 |
| Incremental (Append) | Default for Bronze (append-only) | Stage 1 |
| Incremental (Merge) | For SCD Type 2 — Master Records | Stage 5 |

### Slowly Changing Dimensions (SCD)

| Branch | Kaori implementation |
|---|---|
| SCD 0 (No Historization) | NOT used — always preserve history |
| SCD 1 (Overwrite) | Used for current canonical values in Master Records |
| SCD 2 (Historization) | Used for tracking customer segment changes over time |
| SCD 3-7 | Phase 2+ as needed |


# Phần 18. Implementation Roadmap
## 18.1 Phase 1 (Months 1-4) — Foundation MVP

| # | Component | Stage | Layer |
|---|---|---|---|
| 1 | Folder hierarchy + permissions | Stage 1 | L2 |
| 2 | Upload Wizard 5 steps + resumable | Stage 1 | L2 |
| 3 | Schema detection (heuristic + Qwen) | Stage 2 | L2+L3 |
| 4 | Universal cleaning rules (8 rules) | Stage 3 | L2 |
| 5 | Domain rules cho Retail | Stage 3 | L2 |
| 6 | Bronze → Silver pipeline (Parquet) | Stages 1-3 | L2 |
| 7 | Silver schema enforcement + DLQ | Stage 3 | L2 |
| 8 | PII detection + masking (basic) | Stage 3 | L2 |
| 9 | Within-file dedup | Stage 3 | L2 |
| 10 | Quality scorecard (7 dimensions) | Stage 4 | L2+L4 |
| 11 | Customer Lifecycle State Machine (basic) | Stage 5 | L4 |
| 12 | Gold views (top 5) | Stage 8 | L2 |
| 13 | Insights Engine 3-tuyến | Stages 9-10 | L3+L4 |
| 14 | Lineage capture (basic) | Phần 13 | All |
| 15 | Error taxonomy + DLQ | Phần 14 | All |
| 16 | Memory Service L1+L2 | Stage 7 | L4 |
| 17 | Action Runtime stages B-D (Recommendation→Approval→Execution) | Stage 11 | L4 |
| 18 | Knowledge Extraction: PDF + DOCX text only | Stage 6 | L4 |
| 19 | Tenant encryption keys (envelope) | Phần 16 | All |
| 20 | RLS on all tenant tables | Phần 16 | L1+L2 |

## 18.2 Phase 2 (Months 5-8) — Cognitive Maturation

| # | Component | Stage |
|---|---|---|
| 21 | Cross-upload + Cross-source dedup (master records full) | Stage 5 |
| 22 | Domain rules cho 4 thêm verticals | Stage 3 |
| 23 | Schema migration wizard | Phần 15 |
| 24 | File versioning + re-process workflow | Phần 15 |
| 25 | Backfill orchestration | Phần 15 |
| 26 | Tokenization vault (reversible PII) | Stage 3 |
| 27 | Memory Service L3 (Episodic + pgvector) | Stage 7 |
| 28 | Action Runtime stages E-H (Tracking→Outcome→Feedback→Retrain) | Stage 11 |
| 29 | Knowledge Extraction: Image OCR | Stage 6 |
| 30 | Knowledge Extraction: Email + Chat logs | Stage 6 |
| 31 | Semantic Graph (Neo4j) cho top entity types | Stage 5 |
| 32 | ABAC policy engine | Phần 16 |
| 33 | Time-travel queries | Phần 13 |
| 34 | Calibration drift monitoring auto-retrain | Stage 9 |

## 18.3 Phase 3 (Months 9-24) — Mastery

| # | Component | Stage |
|---|---|---|
| 35 | Memory Service L4 full | Stage 7 |
| 36 | Cross-tenant pattern learning (privacy-safe L4b) | Stage 7 |
| 37 | Knowledge Extraction: Audio/video | Stage 6 |
| 38 | OCR upgrade (Azure Form Recognizer) | Stage 6 |
| 39 | Tenant-level model policies + custom prompt tuning | Stage 9, Phần 16 |
| 40 | Decision Lifecycle full với feedback loops | Stage 11 |
| 41 | Memory introspection UI | Stage 7 |
| 42 | CDC support (Debezium) | Stage 1 |
| 43 | Real-time streaming (Kafka + Flink) | Stages 1-8 |
| 44 | Differential update for re-process | Phần 15 |
| 45 | Auto-suggest custom rules from common patterns | Stage 3 |
| 46 | Special domain supplements (Bank, Healthcare) | All |

## 18.4 Critical Path & Dependencies
Phase 1 critical path:
1 Identity → 2 Folders → 3 Bronze → 4-5 Cleaning → 6-7 Silver → 
10 Quality → 12 Gold → 13 Insights → 17 Action → done MVP

Parallel possible:
- 11 State Machine với 12 Gold
- 14 Lineage với 15 DLQ
- 16 Memory với 17 Action Runtime
- 18 Knowledge Extraction (PDF) — independent branch
- 19-20 Security from start
Total Phase 1: ~16 weeks với 8 FTE engineers. ~30 person-months.

# Tóm tắt — Hành trình của 1 file data
Khách click upload customers_thang_3.csv
    ↓
Stage 1 (L2): File chunked, encoding fixed Win-1258→UTF-8, junk rows removed,
              written to Bronze raw S3 với metadata.json + lineage.json
              [< 30s for 100MB]
    ↓
Stage 2 (L2+L3): Heuristic detect "ma_kh"=customer_id, Qwen confirms ambiguous columns,
                 user confirms mapping, template saved
                 [user time: 2-5 min]
    ↓
Stage 3 (L2): Cleaning rules apply — phone +84xxx, names titled, VND parsed,
              PII masked, within-file dedup, schema enforced, written to Silver Parquet
              [5-15 min]
    ↓
Stage 4 (L2+L4): Quality scorecard 78/100 ACCEPTABLE — pass gate, alert customer
                 about uniqueness issue (dedup suggestion)
                 [< 5s]
    ↓
Stage 5 (L4): Customer "Anh Tuấn 0987" matched to existing master record from HubSpot,
              Customer state computed: ACTIVE → AT_RISK (recency growing),
              ontology graph updated
              [10-30 min for full pipeline]
    ↓
Stage 6 (L4): [Parallel] Customer also uploaded SOP.pdf — extracted, embedded, indexed
              in Knowledge Graph
    ↓
Stage 7 (L4): Recent decisions for similar customers loaded from L3 Memory
    ↓
Stage 8 (L2): gold.customer_360 MV refreshed với new master record + features
              [< 5 min]
    ↓
Stage 9 (L3+L4): Churn model inference: P(churn)=0.74, calibration band REVIEW NEEDED,
                 SHAP top 3 factors generated
                 [< 100ms per record]
    ↓
Stage 10 (L3+L4): 3-tuyến insight composed:
                  WHAT: 234 VIP at risk
                  WHY: voucher gap, email drop, inventory low
                  HOW: send voucher 10%, A/B email, restock
                  Citations included, anti-hallucination passed
                  [< 10s]
    ↓
Stage 11 (L4): Marketing Manager approves voucher campaign (MEDIUM risk),
               SendGrid sends 234 emails, tracking scheduled 14d,
               outcome will measure retention rate
               [Approval: minutes-hours; Tracking: 14 days]
    ↓
Stage 12 (L5): Insight surfaced in P2 dashboard, daily report email sent,
               Slack notification to Marketing Manager
               [Real-time]
    ↓
14 days later: Outcome measured — 67/234 retained = 29% retention,
               revenue recovered: 45M VND, ROI 9x
               Feedback fed back to Stage 9 → model_v2 retrained
               Memory L4 promoted: "voucher 10% works for VIP at risk segment"
End-to-end first time: 30-60 phút từ upload click đến first insight. Full feedback loop closed: 14-30 ngày. Phase 3 with real-time streaming: End-to-end < 30 giây.
Mỗi component được thiết kế để feed organizational learning loop. Không component nào tồn tại độc lập. Đây là sự khác biệt giữa Kaori và BI tools.

Tài liệu này gộp Data Processing Solution v1 + Cognitive Layer v1 thành 1 doc theo flow chronological với layer tags rõ ràng. Đi cùng: - Playbook v3 (operational — WHAT happens 90 days) - SAD Skeleton (architecture — HOW system designed) - Pipeline Unified (THIS — HOW data flows from upload to output)
Khi update: chỉ update file này. Playbook v3 reference vào đây cho data + cognitive details.

# Phần 19. Comprehensive Data Risk Inventory (v1.1 addendum)
Layers: [All — risks span entire stack]
Mục đích phần này: Catalog đầy đủ data risks + coverage map. Phục vụ compliance evidence, Phase 2 planning, audit readiness. Không re-implement — chỉ inventory + reference back to stages đã cover.
## 19.1 Risk Categories Overview
┌──────────────────────────────────────────────────────────┐
│  6 Risk Categories                                       │
├──────────────────────────────────────────────────────────┤
│  A. Data Quality          (8 risks — Stage 3+4)         │
│  B. Data Privacy          (6 risks — Stage 3 + Phần 16) │
│  C. Data Security         (8 risks — Phần 16)           │
│  D. Data Compliance       (5 risks — Phần 13+16)        │
│  E. Data Operational      (7 risks — Phần 14)           │
│  F. Data Veracity (NEW)   (4 risks — gap Phase 1)       │
└──────────────────────────────────────────────────────────┘
## 19.2 Category A — Data Quality Risks

| Risk | Where covered | Status |
|---|---|---|
| Encoding errors (Win-1258, TCVN) | Stage 3 Rule U-1 | ✅ Phase 1 |
| Format inconsistency (date, phone, amount) | Stage 3 Rules R-1, R-3, R-5 | ✅ Phase 1 |
| Missing values | Stage 3 cleaning rules | ✅ Phase 1 |
| Duplicates (within/cross-source) | Stage 3, Stage 5 master records | ✅ Phase 1 |
| Outliers / statistical anomalies | Stage 3 mention only | ⚠️ GAP — see 19.8 |
| Referential integrity violations | Stage 3 schema enforcement | ✅ Phase 1 |
| Business rule violations (amount > limit) | Stage 3 custom rules | ⚠️ Tenant-defined Phase 2 |
| Statistical drift over time | Not addressed | ⚠️ Phase 2 gap |

## 19.3 Category B — Data Privacy Risks

| Risk | Where covered | Status |
|---|---|---|
| Direct PII exposure | Stage 3 PII detection + masking | ✅ Phase 1 |
| PII in free text fields | Stage 3 inline detection | ✅ Phase 1 |
| PII inference attacks (joins re-identify) | Not addressed | ⚠️ Phase 2 gap |
| Unauthorized PII access | Phần 16 ABAC + audit | ✅ Phase 1 |
| K-anonymity, l-diversity violations | Not addressed | ⚠️ Phase 3 gap |
| Differential privacy | Not addressed | ⚠️ Phase 3 gap |

## 19.4 Category C — Data Security Risks

| Risk | Where covered | Status |
|---|---|---|
| Encryption at rest | Phần 16 envelope encryption | ✅ Phase 1 |
| Encryption in transit (mTLS, cert rotation) | Mention only | ⚠️ GAP — see 19.9 |
| Tenant data isolation | Phần 16 RLS + ABAC | ✅ Phase 1 |
| Vector DB cross-tenant leak | Phần 16 namespace isolation | ✅ Phase 1 |
| API key leakage | Mention secret rotation | ⚠️ Phase 2 enforcement |
| SQL injection | Application code review | ⚠️ Phase 1 testing required |
| Insider threat detection | Audit only, no anomaly detection | ⚠️ GAP — see 19.10 |
| Privilege escalation | RBAC role boundaries | ⚠️ Phase 2 monitoring |

## 19.5 Category D — Data Compliance Risks

| Risk | Where covered | Status |
|---|---|---|
| Right-to-erasure (GDPR) | Stage 1 tombstone + Phần 15 | ✅ Phase 1 partial |
| Right-to-portability | Phần 12 export formats | ✅ Phase 1 |
| Data residency (VN-only) | Phần 16 tenant policy | ✅ Phase 1 |
| Retention policy enforcement | Phần 11 storage tiering | ⚠️ Auto-delete gap |
| Audit log immutability | Phần 16 append-only + WORM | ✅ Phase 1 |

## 19.6 Category E — Data Operational Risks

| Risk | Where covered | Status |
|---|---|---|
| Pipeline failures | Phần 14 DLQ | ✅ Phase 1 |
| Schema drift breaking downstream | Phần 15 evolution detection | ✅ Phase 1 |
| Backup & recovery (RTO/RPO) | Not specified | ⚠️ GAP — see 19.11 |
| Disaster recovery | Not specified | ⚠️ GAP — see 19.11 |
| Data corruption (silent) | Checksum at upload, no continuous | ⚠️ GAP — see 19.12 |
| Time-zone confusion | Not specified | ⚠️ GAP — see 19.13 |
| Cascade failures | Stage 11 blast radius pre-check | ✅ Phase 1 |

## 19.7 Category F — Data Veracity Risks (SME VN reality)
This category is unique to SME VN where employees may manipulate data to hit KPIs.

| Risk | Status |
|---|---|
| Data fabrication (fake transactions to hit sales target) | ⚠️ GAP — see 19.14 |
| Backdating (enter today’s data as yesterday) | ⚠️ GAP — see 19.14 |
| Selection bias in upload (only good data uploaded) | ⚠️ Phase 2 detection |
| Survivorship bias (only winning customers tracked) | ⚠️ Phase 2 detection |

## 19.8 GAP — Outlier/Anomaly Detection Framework
Status: Phase 1 addition required.
Spec:
class OutlierDetector:
    """
    Multi-method outlier detection per column.
    Apply during Stage 3 Silver write.
    """
    
    def detect(self, column_data, column_type):
        outliers = []
        
        if column_type == 'numeric':
            # Method 1: IQR
            q1, q3 = np.percentile(column_data, [25, 75])
            iqr = q3 - q1
            lower, upper = q1 - 1.5*iqr, q3 + 1.5*iqr
            iqr_outliers = column_data[(column_data < lower) | (column_data > upper)]
            
            # Method 2: Z-score
            z_scores = np.abs((column_data - column_data.mean()) / column_data.std())
            z_outliers = column_data[z_scores > 3]
            
            # Method 3: Isolation Forest (Phase 2)
            
            outliers = list(set(iqr_outliers) | set(z_outliers))
        
        elif column_type == 'categorical':
            # Frequency-based: values appearing < 0.1% are suspicious
            freq = column_data.value_counts(normalize=True)
            rare_values = freq[freq < 0.001].index
            outliers = column_data[column_data.isin(rare_values)]
        
        elif column_type == 'temporal':
            # Future-dated, weekend-only patterns, etc.
            future_dates = column_data[column_data > now()]
            outliers = future_dates
        
        return outliers
    
    def action(self, outliers, action_policy):
        """
        Per outlier, decide:
        - flag: write to outliers table for review
        - reject: block from Silver
        - cap: replace with P99.5 value
        """
        pass
Action policy per domain: - Retail amounts: cap at P99.5 (likely typo) - Finance amounts: flag for review (could be fraud) - Counts/quantities: flag if negative - Dates: reject if future-dated > 7 days
## 19.9 GAP — Encryption in Transit Detail
Spec:
transit_encryption:
  external_facing:
    - tls_version: ">=1.3"
    - cipher_suites: "TLS_AES_256_GCM_SHA384, TLS_CHACHA20_POLY1305_SHA256"
    - certificates: Let's Encrypt with auto-renew
    - hsts: max-age=31536000; includeSubDomains
  
  internal_service_mesh:
    - mTLS: mandatory (Istio or Linkerd)
    - cert_rotation: every 24h (SPIFFE-based)
    - identity_per_service: yes
  
  database_connections:
    - postgres: SSL required, sslmode=verify-full
    - clickhouse: TLS with client cert
    - redis: TLS 1.3 + auth token
  
  message_queue:
    - kafka: SASL_SSL with mTLS
    - cert_rotation: every 90 days
## 19.10 GAP — Insider Threat Detection
Spec:
class InsiderThreatDetector:
    """
    Detect anomalous access patterns by internal users.
    Run as daily cron over audit logs.
    """
    
    def detect_suspicious(self, tenant_id, days=7):
        signals = []
        
        # Signal 1: Unusual volume of PII access
        pii_accesses = count_pii_access_per_user(tenant_id, days)
        for user_id, count in pii_accesses.items():
            user_baseline = get_user_baseline(user_id, 'pii_access', days=90)
            if count > user_baseline.p99:
                signals.append({
                    'user_id': user_id,
                    'signal': 'pii_access_spike',
                    'severity': 'HIGH',
                    'details': f"{count} accesses vs baseline {user_baseline.median}"
                })
        
        # Signal 2: After-hours access
        after_hours = get_after_hours_access(tenant_id, days)
        for access in after_hours:
            if access.user_role != 'on_call':
                signals.append({
                    'signal': 'after_hours_access',
                    'severity': 'MEDIUM',
                    ...
                })
        
        # Signal 3: Cross-department data access
        # (User normally Marketing, suddenly accessing Finance)
        cross_dept = detect_cross_department_access(tenant_id, days)
        
        # Signal 4: Bulk export
        bulk_exports = detect_bulk_exports(tenant_id, days)
        
        # Signal 5: Repeated failed access attempts (precursor to breach)
        failed_attempts = detect_repeated_failures(tenant_id, days)
        
        return signals
Alerts sent to security team + tenant Manager (per severity).
## 19.11 GAP — Backup & Disaster Recovery
Spec:
backup_strategy:
  bronze_layer:
    method: S3 versioning + cross-region replication
    rpo: 1 hour
    rto: 15 minutes
    
  silver_layer:
    method: ClickHouse incremental backup to S3 (every 6h)
    rpo: 6 hours
    rto: 2 hours
    
  postgres (metadata + lineage):
    method: pg_basebackup hourly + WAL archiving
    rpo: 5 minutes
    rto: 30 minutes
    
  redis (memory L2):
    method: AOF persistence + snapshot every 30 min
    rpo: 30 minutes
    rto: 15 minutes (data acceptable to lose if needed)
    
  encryption_keys (Vault):
    method: HA cluster + auto-snapshot every 6h to encrypted S3
    rpo: 6 hours
    rto: 1 hour
    note: CRITICAL — without keys, all data unrecoverable

disaster_recovery:
  scenarios:
    - region_failure: failover to secondary region (warm standby)
    - data_center_loss: cross-region replicas activate
    - ransomware: restore from immutable WORM backups
    - human_error: time-travel queries + version rollback
  
  testing:
    - quarterly DR drill (full failover test)
    - monthly backup restoration test (random tenant)
    - weekly automated integrity check
## 19.12 GAP — Continuous Data Corruption Monitoring
Spec:
class CorruptionMonitor:
    """
    Daily integrity checks beyond upload checksum.
    """
    
    def check_bronze(self, tenant_id, day):
        # Random sample 100 files
        files = sample_bronze_files(tenant_id, day, n=100)
        
        for file in files:
            # Re-compute SHA-256
            computed_hash = sha256(read_s3(file.path))
            if computed_hash != file.expected_hash:
                alert('CORRUPTION', file)
        
    def check_silver(self, tenant_id):
        # Row count consistency Bronze → Silver
        bronze_count = count_bronze_records(tenant_id, last_day=True)
        silver_count = count_silver_records(tenant_id, last_day=True)
        
        if abs(bronze_count - silver_count) / bronze_count > 0.05:
            alert('SILVER_DRIFT', tenant_id)
    
    def check_gold(self, tenant_id):
        # Aggregate consistency Silver → Gold
        for view in ['customer_360', 'transaction_daily']:
            recompute_from_silver = recompute_aggregate(view, tenant_id)
            current_value = query_gold(view, tenant_id)
            
            if abs(recompute_from_silver - current_value) > tolerance:
                alert('GOLD_DRIFT', view, tenant_id)
## 19.13 GAP — Time-Zone Handling
Spec:
timezone_policy:
  storage:
    rule: ALL timestamps stored in UTC (ISO 8601 format)
    no_exceptions: true
  
  display:
    rule: convert to tenant's primary timezone for UI
    tenant_timezone: stored in tenant_config.primary_timezone
    default: "Asia/Ho_Chi_Minh"
  
  business_logic:
    rule: business day calculations use tenant timezone
    examples:
      - "Daily report" runs at 7am tenant timezone
      - "Recency" computed from tenant midnight, not UTC
  
  multi_region_tenants:
    rule: each store/branch has its own timezone tag
    aggregation: summed in tenant primary timezone
    note: ENT MAX feature, Phase 2
Test cases mandatory: - Tenant in HCM uploads file at 23:30 local → date “2026-04-01” preserved (not “2026-04-02 UTC”) - Daily report 7am triggered at 00:00 UTC for VN tenant (midnight + 7h) - Multi-region: HCM store + HN store dates aggregate correctly
## 19.14 GAP — Data Veracity Detection (SME VN specific)
Reality: Nhân viên VN có pressure hit KPI → có thể fake transactions, backdate, etc.
Spec:
class VeracityDetector:
    """
    Detect statistically suspicious patterns suggesting fabrication.
    """
    
    def detect_backdating(self, tenant_id):
        # Pattern: transactions entered in batch at end-of-month
        # Look for: spike of "transaction_date < created_at" near month-end
        suspicious = query("""
            SELECT staff_id, count(*) as suspicious_count
            FROM silver.transactions
            WHERE date_diff('day', transaction_date, created_at) > 7
              AND day_of_month(created_at) >= 28
              AND tenant_id = :tenant_id
            GROUP BY staff_id
            HAVING count(*) > 10
        """)
        return suspicious
    
    def detect_round_number_bias(self, tenant_id):
        # Pattern: too many "round" amounts (1000000, 500000)
        # Real transactions have natural distribution
        amounts = query_amounts(tenant_id, last_30_days=True)
        round_pct = sum(1 for a in amounts if a % 100000 == 0) / len(amounts)
        if round_pct > 0.4:  # >40% round = suspicious
            alert('ROUND_NUMBER_BIAS', tenant_id, round_pct)
    
    def detect_benford_violations(self, tenant_id):
        # Benford's law: leading digit distribution
        # Real data follows Benford. Fabricated often doesn't.
        from scipy.stats import chisquare
        amounts = query_amounts(tenant_id, last_90_days=True)
        leading_digits = [int(str(a)[0]) for a in amounts if a > 0]
        observed = [leading_digits.count(d) for d in range(1, 10)]
        expected_benford = [math.log10(1 + 1/d) * len(amounts) for d in range(1, 10)]
        chi2, p_value = chisquare(observed, expected_benford)
        if p_value < 0.01:
            alert('BENFORD_VIOLATION', tenant_id, p_value)
    
    def detect_velocity_anomaly(self, tenant_id):
        # Pattern: 1 staff entering 100 transactions in 10 minutes
        # Normal data entry rate: 1-5 transactions/minute
        velocity = query("""
            SELECT staff_id, 
                   count(*) / extract(epoch from (max(created_at) - min(created_at))/60) AS per_min
            FROM silver.transactions
            WHERE tenant_id = :tenant_id
              AND created_at > now() - interval '7 days'
            GROUP BY staff_id, date(created_at)
            HAVING per_min > 10
        """)
        return velocity
Action when detected: 1. Flag suspicious transactions (don’t auto-reject — may be legitimate edge case) 2. Notify tenant Manager với evidence 3. Manager reviews, takes HR action if confirmed 4. Audit log all detections + resolutions
## 19.15 Risk Coverage Summary Matrix

| Category | # Risks | Phase 1 covered | Gaps to fill |
|---|---|---|---|
| A. Data Quality | 8 | 6 | 2 (outliers + drift) |
| B. Data Privacy | 6 | 3 | 3 (Phase 2-3) |
| C. Data Security | 8 | 5 | 3 (transit detail, insider threat, escalation) |
| D. Data Compliance | 5 | 4 | 1 (auto-delete) |
| E. Data Operational | 7 | 4 | 3 (backup/DR, corruption, timezone) |
| F. Data Veracity | 4 | 0 | 4 (all new) |
| Total | 38 | 22 (58%) | 16 (42%) |

Phase 1 priority gaps to fill (7 critical): 1. Outlier detection framework (19.8) 2. Encryption in transit detail (19.9) 3. Insider threat detection (19.10) 4. Backup & DR strategy (19.11) 5. Continuous corruption monitoring (19.12) 6. Time-zone policy enforcement (19.13) 7. Data veracity detection — Benford, velocity, backdating (19.14)
After filling these 7 → Phase 1 covers ~76% of all data risks (29/38). Remaining 9 are Phase 2-3 (advanced privacy, ML bias, etc.).
Phase 2 backlog: - Statistical drift monitoring - PII inference attacks defense - K-anonymity, l-diversity - Selection/survivorship bias detection - Privilege escalation monitoring - Auto-delete after retention enforcement - Differential privacy (Phase 3)
## 19.16 Special Domain Risks (out of scope, defer to Phần 14 of Playbook v3)
Banking, Healthcare, Government domains có additional risks: - Banking: Basel III, AML, fraud-specific - Healthcare: HIPAA-equivalent, patient consent, ethics - Government: Public records, transparency requirements
Refer to Playbook v3 Phần 14 (Special Domain Supplements) for those.
