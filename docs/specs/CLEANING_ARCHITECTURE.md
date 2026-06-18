# CLEANING PIPELINE — KIẾN TRÚC & TƯ DUY

> Cách **Canonical Layer → Transform T3** generalize cho **mọi loại data** (không giới hạn ngành nào).
>
> Nguyên tắc: Canonical Layer (C1–C3) cho Kaori biết **DATA LÀ GÌ**. Transform T3 dùng thông tin đó để chọn **CLEANING RULES NÀO** — hoàn toàn **ngôn ngữ-agnostic**, không đọc raw header.
>
> Xem thêm: [PIPELINE_WORKFLOW.md §3–§4](PIPELINE_WORKFLOW.md).

---

## 1. Tư duy cốt lõi — Canonical Layer cung cấp 3 chiều thông tin

```
┌────────────────────────────────────────────────────────────┐
│ CHIỀU 1 — SHEET PURPOSE (semantic ý nghĩa sheet)            │
│   customer_master · transaction_list · daily_sales          │
│   expense_list · product_catalog · inventory                │
│   staff_performance · bank_statement · attendance_log       │
│   employee_master · marketing_campaign · free_notes         │
│   (detect từ canonical column names — ngôn ngữ-agnostic)   │
└────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────┐
│ CHIỀU 2 — COLUMN CANONICAL (mapping hoàn thành tại C2)     │
│   raw_name → canonical_name                                 │
│   (vd "Số điện thoại" / "電話番号" → "phone")               │
│   + inferred_type (phone / date / number / string / id)     │
│   + is_pii flag                                             │
│   ** Rule Catalog chỉ đọc canonical_name **                 │
└────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────┐
│ CHIỀU 3 — DATA PROFILE (data thực tế trông ra sao)          │
│   null_rate · quality_score · sample_values                 │
│   distinct_count · distribution · min/max/p50/p99           │
│   time_range_days (với date cols)                           │
└────────────────────────────────────────────────────────────┘
```

Transform T3 **không** hardcode cho bất kỳ ngành nào.
Nó **query** 3 chiều trên bằng canonical names, match với **Rule Catalog** để sinh rules dynamically.

---

## 2. Rule Catalog — 4 nhóm rule

### 2.1 Universal rules (áp dụng MỌI sheet)

```python
UNIVERSAL = [
    Rule(
        id='trim_whitespace',
        category='auto',
        condition=lambda sheet: any(c.inferred_type == 'string' for c in sheet.columns),
        compute_affected=lambda sheet, profile: count_cells_with_leading_trailing_space(profile),
    ),
    Rule(
        id='normalize_nfc',
        category='auto',
        condition=lambda sheet: has_unicode_chars(sheet),
    ),
    Rule(
        id='strip_nbsp',
        category='auto',
        condition=lambda sheet: profile.has_nbsp_cells,
    ),
    Rule(
        id='parse_excel_serial_dates',
        category='auto',
        condition=lambda sheet: any(c.inferred_type == 'date' for c in sheet.columns),
    ),
    Rule(
        id='remove_empty_rows',
        category='auto',
        condition=lambda sheet, profile: profile.empty_row_count > 0,
    ),
]
```

### 2.2 Column-type-driven rules (kích hoạt bởi `inferred_type`)

```python
BY_COLUMN_TYPE = {
    'phone': [
        Rule(id='normalize_vn_phone', category='suggested',
             condition=lambda c: c.inferred_type == 'phone',
             action=lambda v: to_phone_vn(v)),   # '0912-345' → '+84912345'
        Rule(id='normalize_intl_phone', category='suggested',
             condition=lambda c: c.inferred_type == 'phone' and has_intl_prefix(c)),
    ],
    'date': [
        Rule(id='parse_multi_format', category='auto',
             condition=lambda c: c.inferred_type == 'date'),
        Rule(id='sort_ascending', category='suggested',
             condition=lambda c: c.canonical_name in {'transaction_date', 'date', 'created_at'}),
        Rule(id='fill_forward_date', category='suggested',
             condition=lambda c: c.canonical_name == 'date' and profile.has_merged_cells),
    ],
    'number': [
        Rule(id='parse_vnd_currency', category='auto',
             condition=lambda c: c.inferred_type == 'number' and is_currency_col(c)),
        Rule(id='parse_usd_currency', category='auto',
             condition=lambda c: c.inferred_type == 'number' and is_usd_col(c)),
        Rule(id='validate_positive', category='suggested',
             condition=lambda c: c.canonical_name in {'amount', 'revenue', 'price', 'salary'}),
        Rule(id='strip_thousand_separator', category='auto',
             condition=lambda c: profile.has_formatted_numbers(c)),
    ],
    'string': [
        Rule(id='title_case_name', category='auto',
             condition=lambda c: c.canonical_name.endswith('_name')),
        Rule(id='normalize_fullwidth', category='auto',
             condition=lambda c: profile.has_fullwidth_chars(c)),
        Rule(id='fix_encoding_vi', category='auto',
             condition=lambda c: profile.has_mojibake_vi(c)),
        Rule(id='fuzzy_dedup', category='ai_detected',
             detector=FuzzyDupDetector()),
    ],
    'id': [
        Rule(id='dedup_by_id', category='suggested',
             condition=lambda c: c.canonical_name.endswith('_id') and profile.has_duplicates(c)),
    ],
}
```

### 2.3 Purpose-driven rules (kích hoạt bởi sheet purpose)

```python
BY_PURPOSE = {
    'customer_master': [
        Rule(id='dedup_by_phone', category='suggested',
             condition=lambda sheet: sheet.has_canonical('phone')),
        Rule(id='dedup_by_id', category='suggested',
             condition=lambda sheet: sheet.has_canonical('customer_external_id')),
        Rule(id='normalize_customer_name', category='auto',
             condition=lambda sheet: sheet.has_canonical('customer_name')),
    ],
    'transaction_list': [
        Rule(id='fill_forward_date', category='suggested',
             condition=lambda sheet: sheet.has_canonical('transaction_date')),
        Rule(id='drop_test_transactions', category='suggested',
             condition=lambda sheet, profile: profile.detect_test_keywords(['test', 'huỷ', 'demo', 'xxx'])),
        Rule(id='parse_amount_vnd', category='auto',
             condition=lambda sheet: sheet.has_canonical('amount')),
    ],
    'bank_statement': [
        Rule(id='classify_transaction_category', category='suggested',
             condition=lambda sheet: sheet.has_canonical('description'),
             # Uses config/bank_rules.json
             action=lambda v: BankClassifier().classify(v)),
        Rule(id='normalize_bank_amount', category='auto',
             condition=lambda sheet: sheet.has_canonical('credit') or sheet.has_canonical('debit')),
        Rule(id='merge_credit_debit', category='suggested',
             condition=lambda sheet: sheet.has_canonical('credit') and sheet.has_canonical('debit')),
    ],
    'expense_list': [
        Rule(id='normalize_category_text', category='auto',
             condition=lambda sheet: sheet.has_canonical('category')),
        Rule(id='map_expense_categories', category='suggested',
             condition=lambda sheet, profile: profile.unique_count('category') >= 4),
    ],
    'product_catalog': [
        Rule(id='fill_missing_sku', category='suggested',
             condition=lambda sheet: sheet.missing_canonical('sku')),
    ],
    'inventory': [
        Rule(id='pivot_wide_to_long', category='auto',
             # Reuses utils/wide_format.py
             condition=lambda sheet: sheet.format == 'matrix'),
    ],
    'staff_performance': [
        Rule(id='unpivot_matrix', category='auto',
             condition=lambda sheet: sheet.format in {'matrix', 'report_with_banner'}),
        Rule(id='decode_shift_codes', category='auto',
             condition=lambda sheet: sheet.has_canonical('shift_code')),
    ],
    'attendance_log': [
        Rule(id='merge_clock_pairs', category='suggested',
             condition=lambda sheet: sheet.has_canonical('clock_in') and sheet.has_canonical('clock_out')),
    ],
    'employee_master': [
        Rule(id='redact_pii_export', category='auto',
             condition=lambda sheet: any(c.is_pii for c in sheet.columns)),
        Rule(id='validate_salary_range', category='ai_detected',
             detector=SalaryOutlierDetector()),
    ],
    # Thêm purpose mới → add entries ở đây, không đụng code cũ
}
```

### 2.4 AI Detectors (pattern detection từ data thực)

```python
AI_DETECTORS = [
    FuzzyDupDetector(),          # rapidfuzz ratio > 92 trên name + phone
    OutlierDetector(),           # IQR / p99 cho numeric columns
    TimeGapDetector(),           # gap > 3 sigma cho date columns
    CategoryExplosionDetector(), # unique_count > 0.3 × row_count → có vẻ free-text
    SeasonalityDetector(),       # STL decompose cho date + amount
    TypoClusterDetector(),       # chuỗi tương tự ("Mỹ phẩm" vs "Mỹ Phẩm")
    BimodalDistribution(),       # 2 mode → có thể mix 2 loại khác nhau
    DuplicateKeyDetector(),      # ID trùng nhưng giá trị khác
]
```

Mỗi detector return `Optional[Rule]`:
- `None` nếu không phát hiện gì
- `Rule(...)` với mô tả cụ thể + `affected_rows` từ data thực

---

## 3. Flow Canonical Layer → Transform T3

```python
def generate_cleaning_rules(canonical_output: CanonicalLayerResult) -> list[SheetCleaningPlan]:
    plans = []
    for sheet in canonical_output.sheets:
        profile = sheet.profile
        rules = []

        # 1. Universal — mọi sheet
        for r in UNIVERSAL:
            if r.condition(sheet, profile):
                rules.append(r.instantiate(sheet, profile))

        # 2. Per column type — đọc inferred_type (canonical)
        for col in sheet.columns:
            for r in BY_COLUMN_TYPE.get(col.inferred_type, []):
                if r.condition(col):
                    rules.append(r.instantiate(sheet, col, profile))

        # 3. Per purpose — đọc sheet.purpose (canonical)
        for r in BY_PURPOSE.get(sheet.purpose, []):
            if r.condition(sheet, profile, all_sheets=canonical_output.sheets):
                rules.append(r.instantiate(sheet, profile))

        # 4. AI detectors — chạy trên sample data thực
        for detector in AI_DETECTORS:
            detected_rule = detector.run(sheet, profile)
            if detected_rule:
                rules.append(detected_rule)

        plans.append(SheetCleaningPlan(
            sheet=sheet,
            rules=rules,
            quality_before=profile.quality_score,
            quality_after=estimate_quality_after(rules),
        ))
    return plans
```

Output → `GET /clean/suggestions` endpoint.

---

## 4. Bảng quyết định — rule nào cho data gì

| Tình huống | Rule | Category |
|---|---|---|
| Canonical type = phone | `normalize_vn_phone` | Suggested |
| Canonical type = date | `parse_multi_format` | Auto |
| canonical_name = `amount` / `revenue` / `price` | `parse_vnd_currency` | Auto |
| Unique ratio cột category > 30% | `CategoryExplosionDetector` | AI detected |
| Phone + name fuzzy 92%+ cross-row | `FuzzyDupDetector` | AI detected |
| Numeric value > p99 × 3 | `OutlierDetector` | AI detected |
| Date gap > 3σ | `TimeGapDetector` | AI detected |
| Purpose = staff_performance + matrix format | `unpivot_matrix` | Auto |
| Purpose = bank_statement + `description` col | `classify_transaction_category` | Suggested |
| Purpose = employee_master + PII col | `redact_pii_export` | Auto |
| Purpose = inventory + matrix format | `pivot_wide_to_long` | Auto |

---

## 5. Non-destructive guarantee

```python
class Rule:
    def preview(self, df: pd.DataFrame) -> RulePreview:
        """Chạy rule trên bản sao, return (before, after, affected_rows). KHÔNG mutate df."""

    def apply(self, bronze_df: pd.DataFrame) -> pd.DataFrame:
        """Return copy đã clean. Bronze df không đổi."""

    def log(self, step_log: PipelineStepLog) -> None:
        """Append-only log — K-2."""

    def audit(self, mapping: ColumnMapping) -> RuleAuditEntry:
        """Decision audit entry cho decision_audit_log — K-6."""
```

Bronze KHÔNG BAO GIỜ bị sửa. Silver = Bronze + rules applied.
Nếu user disable rule → re-run Silver từ Bronze, không mất data gốc.

---

## 6. Quality Score Formula

```
Per column quality =
    0.4 × (1 - null_rate)
    + 0.3 × type_consistency_score
    + 0.2 × uniqueness_score (nếu là ID column)
    + 0.1 × format_consistency_score

Sheet quality = weighted_avg(column_quality,
    weight = mapping_confidence × required_flag)

After cleaning estimate:
    for each rule applied:
        quality += rule.quality_delta  (pre-computed in rule metadata)
```

---

## 7. Khi user upload data hoàn toàn lạ

1. `SchemaClassifier` (Qwen T=0.1) classify → confidence < 0.7 → flag `needs_review`
2. UI prompt user "Mô tả sheet này" → Qwen đọc description + sample → sinh purpose mới
3. Lưu vào `enterprise_column_mappings` — lần sau auto recognize

**T3 cho sheet "unknown-but-described":**
- Chỉ apply UNIVERSAL rules
- Bỏ qua BY_PURPOSE (chưa có rule cho purpose custom)
- Chạy AI_DETECTORS (generic — hoạt động trên mọi data)

---

## 8. Extend Catalog — thêm ngành mới

### Ví dụ: Thêm support cho Healthcare

**Canonical Layer detect được:**
- Purpose mới `medical_records` (`patient_id`, `diagnosis_code`, `visit_date`)
- Purpose mới `prescription` (`drug_name`, `dosage`, `prescriber_id`)

**Extend catalog:**
```python
BY_PURPOSE['medical_records'] = [
    Rule(id='redact_patient_pii', category='auto',
         condition=lambda sheet: sheet.has_canonical('patient_id')),
    Rule(id='validate_diagnosis_code', category='suggested',
         condition=lambda sheet: sheet.has_canonical('diagnosis_code')),
]
BY_PURPOSE['prescription'] = [
    Rule(id='normalize_drug_name', category='auto',
         condition=lambda sheet: sheet.has_canonical('drug_name')),
]
```

**Kết quả:** T3 engine không thay đổi. Chỉ add entries.

---

## 9. Implementation Status (2026-04-22)

| Thành phần | Status | File |
|---|---|---|
| Universal rules (trim, NFC, NBSP, date) | ✅ Done | `silver/rule_catalog.py` |
| Smart header detection | ✅ Done | `bronze/ingestor.py` |
| Column mapping C2 | ✅ Done | `bronze/column_mapper.py` |
| SHA-256 idempotency | ✅ Done | `bronze/ingestor.py` |
| Unpivot engine | ✅ Done | reuse `utils/wide_format.py` |
| Bank classifier | ✅ Done | reuse `etl/classify_bank.py` → `config/bank_rules.json` |
| BY_COLUMN_TYPE rules (phone, date, number) | ✅ Done | `silver/rule_catalog.py` |
| BY_PURPOSE rules (basic) | ✅ Done | `silver/rule_catalog.py` |
| **8 AI Detectors** | ⚠️ Pending | `silver/detectors/` |
| **PipelineStepLog wiring** | ⚠️ Pending | bảng có, chưa wire |
| **Rule.audit() → decision_audit_log** | ⚠️ Pending | Sprint 2+ |
| SCD Type 1/2 | ⚠️ Phase 2 | `silver/scd_handler.py` |

---

## 10. TL;DR

**T3 không biết data là của ngành nào.** Nó nhận 3 chiều từ Canonical Layer (purpose + canonical columns + data profile) và query Rule Catalog. Thay data → Canonical Layer output khác → T3 sinh rules khác tự động.

- **Ngành mới** = add entries vào Rule Catalog, không sửa T3.
- **Pattern mới** = add AI detector, không sửa T3.
- **Cột mới** = add canonical schema mapping, không sửa T3.
