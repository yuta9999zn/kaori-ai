# MULTI-LANG COMPLEX FILE HANDLING

> Kaori nhận file bất kỳ — kể cả file phức tạp như Excel 86 sheets, 3 ngôn ngữ mix, matrix format.
> Hệ thống phải **hiểu như data analyst người thật**, không chỉ parse raw.
>
> Architecture này được adapt từ Kise AI MULTILANG_FILE_HANDLING.md cho Kaori general-purpose.
> FE implement: `frontend/src/lib/parse-spreadsheet.ts`
> BE implement: `services/data-pipeline/bronze/` + `services/data-pipeline/silver/`

---

## 1. Kiến trúc 5 tầng

```
┌──────────────────────────────────────────────────────────────┐
│ Tầng 1: CẤU TRÚC (Structural Analysis)                        │
│   • Smart header detection — scan ≤15 rows, score theo:       │
│     - non-empty cells count                                   │
│     - structured labels (có chữ cái / kanji)                  │
│     - row bên dưới có data (không empty)                      │
│   • Banner extraction — rows trên header → metadata           │
│   • Format: tabular | matrix | report_with_banner | unknown   │
└──────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────┐
│ Tầng 2: NGÔN NGỮ (Language Detection)                         │
│   • Unicode range scan:                                       │
│     - Hiragana/Katakana [ぁ-ヿ] → JP (xác định)               │
│     - Hangul [가-힯] → KO                                      │
│     - CJK không kèm kana [一-鿿] → ZH                         │
│     - Latin + diacritics VI (ăâđêôơư) → VI                   │
│     - Latin plain → EN                                        │
│   • Mixed: scan tất cả 5 lang keyword dicts                   │
└──────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────┐
│ Tầng 3: SEMANTIC (Sheet Purpose Classification)               │
│   • 13 purposes × 5 languages × 2 weights = 130 keyword sets │
│   • Score = Σ (primary × 2 + secondary × 1)                  │
│   • Threshold: ≥0.25 → classify, <0.25 → purpose = 'other'   │
└──────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────┐
│ Tầng 4: CODE DECODING (Translation)                           │
│   • Detect cell values là known codes                         │
│   • 3 nguồn theo thứ tự ưu tiên:                              │
│     1. Inline lookup sheet (vd. 設定 trong cùng workbook)     │
│     2. BUILTIN_CODE_DICT (JP/KO/ZH shift codes phổ biến)     │
│     3. Qwen LLM fallback (codes lạ, cache kết quả)           │
└──────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────┐
│ Tầng 5: TRANSFORM (Cleaning + Unpivot)                        │
│   • Matrix → long format (unpivot dates/times)               │
│   • Code values → meaningful labels (dùng kết quả Tầng 4)    │
│   • Banner metadata → context (year, month, title)            │
│   • Cross-sheet join hints (khi detect shared index column)   │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. Language Detection — Unicode Ranges

```typescript
// frontend/src/lib/parse-spreadsheet.ts

export type Lang = 'ja' | 'ko' | 'zh' | 'vi' | 'en' | 'mixed';

export function detectLanguage(strings: string[]): Lang {
  const text = strings.join(' ');
  const counts = { ja: 0, ko: 0, zh: 0, vi: 0, en: 0 };

  for (const ch of text) {
    const cp = ch.codePointAt(0)!;
    if ((cp >= 0x3040 && cp <= 0x30FF) || (cp >= 0xFF65 && cp <= 0xFF9F)) counts.ja++;
    else if (cp >= 0xAC00 && cp <= 0xD7A3) counts.ko++;
    else if (cp >= 0x4E00 && cp <= 0x9FFF && counts.ja === 0) counts.zh++;
    else if (/[àáâãăạảấầẩậắặằẳẵ]/iu.test(ch)) counts.vi++;
    else if (/[a-z]/i.test(ch)) counts.en++;
  }

  const dominant = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
  const total = Object.values(counts).reduce((a, b) => a + b, 0);

  if (total === 0) return 'en';
  if (dominant[1] / total > 0.6) return dominant[0] as Lang;
  return 'mixed';
}
```

---

## 3. ParsedSheet Output Shape (Frontend)

```typescript
interface ParsedSheet {
  name: string;
  columns: string[];
  row_count: number;
  sample_rows: Array<Record<string, any>>;
  detected_lang: Lang;
  format: 'tabular' | 'matrix' | 'report_with_banner' | 'unknown';
  header_row_index: number;
  banner_metadata?: {
    title?: string;
    year?: number;
    month?: number;
    raw_rows: string[][];
  };
  pivot_columns?: string[];        // date/time columns khi matrix format
  detected_codes?: DetectedCode[]; // shift codes / category codes in data
  classification: {
    purpose: SheetPurpose;
    confidence: number;
    lang: Lang;
  };
}
```

---

## 4. ColumnMapping Output Shape (sau Canonical Layer C2)

```typescript
interface ColumnMapping {
  raw_name: string;             // "Số điện thoại" / "電話番号"
  canonical_name: string;       // "phone"
  detected_lang: Lang;          // 'vi' / 'ja'
  match_method: 'exact' | 'fuzzy' | 'llm' | 'user_confirmed';
  confidence: number;           // 0–1

  alternatives: Array<{ canonical: string; score: number }>;
  uncertainty_flags: Array<
    | 'low_confidence'     // confidence < 0.70
    | 'ambiguous_top2'     // top-2 within 0.05
    | 'lang_mismatch'      // detected ≠ file dominant lang
    | 'no_sample_values'   // header-only col, can't verify
  >;
  audit_id: string | null;      // FK → decision_audit_log.id
  needs_user_confirm: boolean;  // true when any uncertainty_flag
  is_pii: boolean;
}
```

**Invariant:** nếu `uncertainty_flags` non-empty → UI hiển thị warning badge, không tự áp dụng mapping — user phải confirm.

---

## 5. Built-in Code Dictionary (JP/KO/ZH)

```typescript
// Shift codes (Japanese/Korean beauty + hospitality)
export const BUILTIN_CODE_DICT: Record<string, CodeTranslation> = {
  // Japanese shift codes
  '早番':  { vi: 'ca sớm',    en: 'early shift',   typical_value: '09:00–15:00' },
  'ロング': { vi: 'ca dài',    en: 'long shift',    typical_value: '12:00–21:00' },
  '遅番':  { vi: 'ca muộn',   en: 'late shift',    typical_value: '15:00–21:00' },
  '休み':  { vi: 'nghỉ',      en: 'day off' },
  '定休日': { vi: 'nghỉ cố định', en: 'regular closed day' },
  '有休':  { vi: 'nghỉ phép', en: 'paid leave' },

  // Korean retail status
  '정상':  { vi: 'bình thường', en: 'normal' },
  '할인':  { vi: 'giảm giá',   en: 'discount' },
  '품절':  { vi: 'hết hàng',   en: 'out of stock' },
  '반품':  { vi: 'trả hàng',   en: 'return' },

  // Chinese status
  '正常': { vi: 'bình thường', en: 'normal' },
  '缺货': { vi: 'hết hàng',   en: 'out of stock' },
};
```

---

## 6. Backend Implementation

### `bronze/lang_dict.py` — Mirror Python của TypeScript dict

```python
# services/data-pipeline/bronze/lang_dict.py

PURPOSE_KEYWORDS = {
    'customer_master': {
        'vi': {'primary': ['khách hàng', 'khách'], 'secondary': ['thành viên', 'hội viên']},
        'en': {'primary': ['customer', 'client'], 'secondary': ['member', 'contact']},
        'ja': {'primary': ['顧客', 'お客様'], 'secondary': ['会員']},
        'ko': {'primary': ['고객'], 'secondary': ['회원', '멤버']},
        'zh': {'primary': ['顾客', '客户'], 'secondary': ['会员']},
    },
    'transaction_list': {
        'vi': {'primary': ['giao dịch', 'hóa đơn', 'đơn hàng'], 'secondary': ['thanh toán', 'mua']},
        'en': {'primary': ['transaction', 'invoice', 'order'], 'secondary': ['payment', 'sale']},
        'ja': {'primary': ['取引', '請求書', '注文'], 'secondary': ['支払い']},
        'ko': {'primary': ['거래', '청구서', '주문'], 'secondary': ['결제']},
        'zh': {'primary': ['交易', '发票', '订单'], 'secondary': ['付款']},
    },
    # ... 11 more purposes
}

BUILTIN_CODE_DICT = {
    '早番':  {'vi': 'ca sớm',    'en': 'early shift',   'typical_value': '09:00–15:00'},
    'ロング': {'vi': 'ca dài',    'en': 'long shift',    'typical_value': '12:00–21:00'},
    '遅番':  {'vi': 'ca muộn',   'en': 'late shift',    'typical_value': '15:00–21:00'},
    '休み':  {'vi': 'nghỉ',      'en': 'day off'},
    '定休日': {'vi': 'nghỉ cố định', 'en': 'regular closed day'},
    # Korean + Chinese...
}
```

### `silver/unpivot.py` — Matrix → Long Format

```python
# services/data-pipeline/silver/unpivot.py

import pandas as pd

def unpivot_matrix(
    df: pd.DataFrame,
    index_cols: list[str],   # ['氏 名'] — identity columns
    pivot_cols: list[str],   # ['2026-04-01', '2026-04-02', ...] — date cols
    value_name: str = 'value'
) -> pd.DataFrame:
    """
    Transform (staff × date) → long (staff, date, value).
    Reuses utils/wide_format.py logic for general wide-format.
    """
    return df.melt(
        id_vars=index_cols,
        value_vars=pivot_cols,
        var_name='date',
        value_name=value_name
    )

def suggest_matrix_transform(
    df: pd.DataFrame,
    sample_rows: list[dict]
) -> dict | None:
    """
    Detect nếu columns là dates/times → suggest unpivot.
    Returns {'index_cols': [...], 'pivot_cols': [...]} or None.
    """
    date_pattern = re.compile(r'^\d{4}[-/]\d{2}[-/]\d{2}$')
    pivot_cols = [c for c in df.columns if date_pattern.match(str(c))]
    if len(pivot_cols) >= 5:  # likely matrix if ≥5 date columns
        index_cols = [c for c in df.columns if c not in pivot_cols]
        return {'index_cols': index_cols, 'pivot_cols': pivot_cols}
    return None
```

### `silver/code_resolver.py` — Inline Lookup

```python
# services/data-pipeline/silver/code_resolver.py

def extract_inline_lookup(workbook: Workbook) -> dict[str, str]:
    """
    Look for settings sheet (設定, Settings, config, 설정) in workbook.
    Extract code → meaning mapping from 2-column table.
    """
    SETTINGS_SHEET_NAMES = ['設定', 'Settings', 'Config', '설정', '設置', 'Cài đặt']
    for sheet_name in workbook.sheetnames:
        if sheet_name in SETTINGS_SHEET_NAMES:
            ws = workbook[sheet_name]
            lookup = {}
            for row in ws.iter_rows(values_only=True):
                if row[0] and row[1]:
                    lookup[str(row[0]).strip()] = str(row[1]).strip()
            return lookup
    return {}

def resolve_codes(
    df: pd.DataFrame,
    column: str,
    inline_lookup: dict[str, str],
    builtin_dict: dict[str, dict],
) -> pd.DataFrame:
    """Translate codes in column using inline lookup → BUILTIN → original."""
    def translate(code):
        code_str = str(code).strip()
        if code_str in inline_lookup:
            return inline_lookup[code_str]
        if code_str in builtin_dict:
            return builtin_dict[code_str].get('vi', code_str)
        return code_str  # keep original if unknown
    df[column] = df[column].apply(translate)
    return df
```

---

## 7. UI Display Example

Khi detect sheet phức tạp, FE SchemaReview hiển thị:

```
Sheet T4.2026 🇯🇵 · Lịch ca nhân viên · Tháng 4/2026
─────────────────────────────────────────────────────
Định dạng: Ma trận (nhân viên × ngày) · 30 cột ngày · 9 nhân viên
Header: hàng 8 (có 7 hàng banner phía trên)

Mã ca phát hiện:
  早番  → ca sớm 09:00–15:00
  ロング → ca dài 12:00–21:00
  遅番  → ca muộn 15:00–21:00
  休み  → nghỉ
  定休日 → nghỉ cố định

Kaori sẽ tự unpivot thành bảng:
  (nhân_viên, ngày, mã_ca) → 270 hàng dữ liệu
```

---

## 8. Khi file có ngôn ngữ lạ / code không nhận ra

1. **BUILTIN_CODE_DICT miss**: Qwen LLM translate batch
   - Prompt: `"Dịch các mã sau sang tiếng Việt + giải thích: ['早番', 'ロング']"`
   - Cache trong DB `code_translations` (key = `{lang}:{code}`)
   - Reuse cho file upload tiếp theo

2. **Purpose confidence < 0.25**: Label = `'other'`
   - UI hiển thị: "Không xác định được loại sheet"
   - Apply UNIVERSAL rules only
   - User có thể tag thủ công

3. **Mixed language columns**: Flag `lang_mismatch` uncertainty
   - Apply keyword dict cho cả 5 ngôn ngữ
   - Chọn best match bất kể lang

---

## 9. Phân biệt: File Data Language vs UI Language

| Layer | Locale |
|---|---|
| UI labels (button, menu, error messages) | User's preferred UI language (settings) |
| File data classification | Auto-detect từ file content (5 tầng trên) |
| Analysis narrative (AI text output) | User's preferred output language |

3 layer độc lập. Người Nhật upload file tiếng Nhật, xem UI tiếng Việt → hoàn toàn OK.

---

## 10. Implementation Status (2026-04-22)

| Thành phần | Status | File |
|---|---|---|
| `parse-spreadsheet.ts` (FE) | ⚠️ Cần copy từ Kise AI | `frontend/src/lib/parse-spreadsheet.ts` |
| `lang_dict.py` (BE) | ⚠️ Pending | `bronze/lang_dict.py` |
| `detectLanguage()` in `column_mapper.py` | ✅ Done | `bronze/column_mapper.py` |
| `unpivot.py` | ⚠️ Pending (reuse `utils/wide_format.py`) | `silver/unpivot.py` |
| `code_resolver.py` inline lookup | ⚠️ Pending | `silver/code_resolver.py` |
| Qwen translate fallback | ⚠️ Pending | wired via `llm_router.py` |
| Cross-sheet relationship detector | Phase 2 | `gold/relationship_detector.py` |
| UI i18n (next-intl) | Phase 2 | `frontend/src/locales/` |

**Priority cho Sprint 3:** `lang_dict.py` (mirrors `parse-spreadsheet.ts`), `unpivot.py`, `code_resolver.py`.
