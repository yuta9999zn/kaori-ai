# Validation Rules — Per-Field Input Constraints

> **Source:** `D:\Kaori Document\Validation Rule.pdf` v1.0.3 (06 Aug 2025)
> **Last imported:** 2026-05-12 — full extract retained at `.claude/scratch_Validation_Rule.txt` (gitignored)
> **Audience:** Frontend (form-field validators + error-message wiring), Backend (server-side echo of same constraints — never trust FE alone, K-3 / K-12 spirit)
> **Cross-ref:** error codes in `docs/specs/MESSAGE_DEFINITIONS.md`

This spec is the **single canonical source** of input validation. Both FE and BE MUST implement identical constraints.

**Enforcement (BE live since 2026-05-24):** §2 is executable in `services/ai-orchestrator/shared/validators.py`, driven by the shared fixture contract `services/ai-orchestrator/tests/fixtures/validation_rules_fixtures.json` and asserted by `tests/test_validation_rules_parity.py`. Add a rule here → add a fixture case → the test fails until the validator implements it. **FE half is deferred to FE restructure (CLAUDE.md §2)**: when FE resumes, its form validator consumes the *same* fixture JSON, so FE↔BE drift surfaces as a test failure on whichever side falls behind. Until then, BE constraints are enforced; FE parity is not yet automated.

---

## 1. Common pattern (applies to every field)

Every field declares 5 concerns:

| Concern | Question |
|---|---|
| **Kiểu dữ liệu** (data type) | String / Int / Timestamp / Year? |
| **Độ dài hợp lệ** (length) | Min, Max characters? |
| **Ký tự hợp lệ** (allowed chars) | Letters, digits, special set? |
| **Cấu trúc hợp lệ** (structure) | Regex / format spec? |
| **Yêu cầu nghiệp vụ** (business rule) | Unique, in range, dependent on other field? |

Trim convention: tất cả String field auto-trim leading/trailing space; nội-tâm space giữ trừ field cấm.

---

## 2. Field rules

### 2.1 Email (`email`)

| Concern | Rule | Error on fail |
|---|---|---|
| Type | String | — |
| Length | Min 6, Max 255 (incl. `@` + local-part + domain) | `USR-ERR5` |
| local-part chars | `A-Z`, `a-z`, `0-9`, `.`, `-`, `_`, `+` | `USR-ERR4` |
| local-part rules | Không toàn số, không toàn ký tự đặc biệt, không 2 special liên tiếp, không bắt đầu/kết thúc bằng special | `USR-ERR4` |
| domain | Min 2 labels, ngăn cách bởi `.` | `USR-ERR4` |
| each label | 1-63 ký tự; `A-Z` `a-z` `0-9` `-`; không toàn số/special | `USR-ERR4` |
| top-level label | 2-6 ký tự; chỉ `A-Z` `a-z` | `USR-ERR4` |
| Structure | Match `^[local-part]@[domain]$` (≥1 `@`) | `USR-ERR4` |
| Business | Unique trong tenant (per signup / invite) | `USR-ERR6` |
| Whitespace | Disallow space inside string (auto-fail) | `USR-ERR4` |

### 2.2 Username / Code (`username`, `*_code`)

| Concern | Rule | Error |
|---|---|---|
| Type | String | — |
| Length | Min 1, Max 20 | `USR-ERR5` |
| Chars | `A-Z` `a-z` `0-9` `A-Y` (Vietnamese hoa, không dấu) `a-y` (thường, không dấu) `.` `-` `_` `+` | `USR-ERR4` |
| Rules | Không emoji, không ký tự ngoài set; không dấu thanh (huyền sắc hỏi ngã nặng); không toàn special | `USR-ERR4` |
| Business | Unique trong tenant; không nhập trùng mã | `USR-ERR6` |
| Whitespace | Auto-trim leading/trailing | (silent) |

### 2.3 Password (`password`)

| Concern | Rule | Error |
|---|---|---|
| Type | String | — |
| Length | Per-field định nghĩa (thường Min 8, Max 64) | `USR-ERR5` |
| Chars | Letters (`A-Z` `a-z`), digits, special: `.` `-` `_` `+` `*` `&` `@` `(` `)` `,` `;` `:` `?` `!` `/` `'` | `USR-ERR4` |
| Rules | Không emoji, không ký tự control, không SQL injection / `<script>` / HTML tag | `USR-ERR4` |
| Business | Per zxcvbn or NIST 800-63B (planned) | `USR-ERR4` |

### 2.4 Number — natural int (`*_count`, `*_quantity`)

| Concern | Rule | Error |
|---|---|---|
| Type | int | — |
| Length | Per-field | `USR-ERR5` |
| Chars | Chỉ `0-9` | `USR-ERR4` |
| Structure | String convertible → natural int | `USR-ERR4` |
| Business | `≥ 0` (natural number, không âm) | `USR-ERR7` |

### 2.5 Free text / description (`description`, `notes`)

| Concern | Rule | Error |
|---|---|---|
| Type | String | — |
| Length | Min 1, Max 2000 | `USR-ERR5` |
| Chars | `A-Z` `a-z` `0-9` + special set: `.` `-` `_` `+` `*` `&` `@` `(` `)` `,` `;` `:` `?` `!` `/` | `USR-ERR4` |
| Rules | Không emoji, không script/XSS payload | `USR-ERR4` |
| Business | Có thể chứa whitelist HTML tag nếu nghiệp vụ define (`<b>`, `<i>`, `<br>`) — declare per field | — |

### 2.6 Datetime (`created_at`, `updated_at`, `due_at`)

| Concern | Rule | Error |
|---|---|---|
| Type | Timestamp | — |
| Format | `dd/mm/yyyy hh:mm:ss` | `USR-ERR4` |
| Length | Date 01-31, Month 01-12, Year 1900-2200 | `USR-ERR4` |
| Chars | `0-9`, `/`, `:` | `USR-ERR4` |
| Business | Date phải tồn tại (no 30/02, no 29/02 non-leap) | `USR-ERR4` |

### 2.7 Year (`fiscal_year`, `expiry_year`)

| Concern | Rule | Error |
|---|---|---|
| Type | Year | — |
| Length | Min 4, Max 5 chars | `USR-ERR5` |
| Chars | Chỉ `0-9` | `USR-ERR4` |
| Structure | `yyyy` | `USR-ERR4` |
| Business | Trong khoảng 1900-2200 | `USR-ERR7` |
| Whitespace | Auto-trim toàn bộ space, không hiện message | (silent) |

### 2.8 Phone (`phone`)

| Concern | Rule | Error |
|---|---|---|
| Type | String | — |
| Length | VN: 8, 10, 11 ký tự (không tính `+`); Intl: ≤15 (E.164) | `USR-ERR4` |
| Chars | `0-9`, `+` (chỉ ở đầu) | `USR-ERR4` |
| Structure | • `+84` → 9 số, bắt đầu 9x/8x/7x/3x/5x (di động) hoặc 2x (cố định)<br>• `0` → tương tự<br>• Cố định 02x: 11 số<br>• Tổng đài: 8 số bắt đầu `19xx` / `18xx` | `USR-ERR4` |
| Business | Lưu cả prefix (`+84`, `+1`, ...) để phân biệt VN vs nước ngoài; FE hiển thị nội bộ auto-convert `+84` → `0` | — |

### 2.9 URL (`website`, `link_*`)

| Concern | Rule | Error |
|---|---|---|
| Type | String (URL structure) | — |
| Length | Total ≤ 255, mỗi label ≤ 63 | `USR-ERR5` |
| Chars | Per RFC 3986 (host/path/query/fragment); special chars percent-encoded | `USR-ERR4` |
| Structure | • Bắt đầu `http://` hoặc `https://` (nếu thiếu auto-add `https://`)<br>• Host có ≥1 `.`<br>• Mỗi label: `A-Z` `a-z` `0-9` `-`, không toàn số/special, không bắt đầu/kết thúc bằng `-` hoặc `.` | `USR-ERR4` |
| Business | Path/query/fragment optional; chứa script/mã độc → reject | `USR-ERR4` |

### 2.10 Symbol / Code (mã hiệu văn bản, `doc_no`)

| Concern | Rule | Error |
|---|---|---|
| Type | String | — |
| Length | ≤50 | — |
| Chars | `A-Z` (auto-uppercase nếu thường), tiếng Việt `Ă Â Ê Đ Ô Ơ Ư`, `0-9`, `:` `/` `-` | `USR-ERR4` |
| Structure | `Số/KýhiệuVB-KýhiệuVB`; không cách chữ; số < 10 thêm `0` ở đầu | `USR-ERR4` |

### 2.11 Address (`address`)

| Concern | Rule | Error |
|---|---|---|
| Type | String | — |
| Length | 10-255 | `USR-ERR5` |
| Chars | Chữ, số, space, `,` `.` `-` `/` | `USR-ERR4` |
| Structure | 3 formats theo loại:<br>• Nhà riêng: `[Số nhà],[Tổ/thôn],[Phường/Xã],[Quận/Huyện],[Tỉnh/TP],[Quốc gia]`<br>• Chung cư: thêm `[Số căn hộ],[Tầng],[Toà],[Dự án]` ở đầu<br>• Cơ quan: thêm `[Tên cơ quan]` ở đầu | `USR-ERR4` |
| Business | Unique nếu nghiệp vụ yêu cầu (vd 1 enterprise = 1 trụ sở chính) | `USR-ERR6` |

### 2.12 ID card (CCCD) — `national_id`

| Concern | Rule | Error |
|---|---|---|
| Type | String | — |
| Length | VN: 9 hoặc 12 ký tự; Foreign: ≤20 | `USR-ERR5` |
| Chars | • VN: chỉ `0-9` (bắt buộc nhập)<br>• Foreign: `0-9` + `a-z` (optional; cho phép toàn số, cấm toàn chữ; cấm ký tự đặc biệt) | `USR-ERR4` |

---

## 3. Gridview / Pagination (UI control validation)

Per PDF §8.

| Field | Widget | Behavior |
|---|---|---|
| Số bản ghi / trang | droplist `[10, 20, 50, 100]` mặc định 10 | Nếu `Σ records > page_size` → hiện total_pages; auto về trang 1 khi đổi size; sort `createDate` desc default |
| Số trang nhảy đến | textbox numeric | Display: "Trang [n] trên [max]". Nếu `n > max` → return trang 1. Nếu `n ≤ max` → trang `n`. `n = 0` → trang 1 |

---

## 4. Backend implementation (Pydantic)

Each FE rule mirrors as a Pydantic `field_validator`. Pattern:

```python
from pydantic import BaseModel, Field, field_validator

class UserCreate(BaseModel):
    email: str = Field(min_length=6, max_length=255)
    username: str = Field(min_length=1, max_length=20)

    @field_validator("email")
    @classmethod
    def email_format(cls, v: str) -> str:
        # mirror VALIDATION_RULES.md §2.1
        if not EMAIL_RE.match(v):
            raise ValueError("USR-ERR4")  # errcode for RFC 7807 envelope
        ...
```

CI test pinning (planned P15-S11 — `tests/test_validation_drift.py`) loads this MD's tables + asserts every Pydantic schema rejects the matching invalid-case fixtures.

---

## 5. Frontend implementation (Zod / RHF)

Mirror in `frontend/lib/validators/`. Each schema imports the constraint tuple from a single source-of-truth file (`frontend/lib/validators/constants.ts`) generated from this MD via codegen (planned with P15-S11 cleanup).

```ts
import { z } from "zod";
import { EMAIL_RE, EMAIL_LEN } from "./constants";

export const emailSchema = z
  .string()
  .min(EMAIL_LEN.min, "USR-ERR5")
  .max(EMAIL_LEN.max, "USR-ERR5")
  .regex(EMAIL_RE, "USR-ERR4");
```

---

## 6. Maintenance

- PDF version bump → re-extract via `python -c "import pypdf; ..."` → diff with this MD → update sections.
- New field nghiệp vụ (vd `tax_code`, `bank_account_number`) → add §2.x with same 5-concern table.
- FE/BE drift caught at runtime → file bug + update this MD as the canonical fix.

---

## 7. Extended field rules (Round 5 N5 — 2026-05-21)

### 7.1 VN Phone (`phone`, `customer_phone`, `contact_phone`)

| Concern | Rule | Error |
|---|---|---|
| Type | String | — |
| Length | Min 9, Max 11 sau khi strip non-digit | `USR-ERR5` |
| Allowed chars | `0-9`, `+`, ` `, `-`, `(`, `)` (whitespace + special trong format ngày upload allowed) | `USR-ERR4` |
| Structure | Match `^(\+84|0)[0-9]{9,10}$` after normalize | `USR-ERR4` |
| Business | Normalize via `vn_phone` normalizer (mig 086 P2.5 dedup_records): `+84xxx` ↔ `0xxx` ↔ formatted with separators | — |
| Whitespace | Strip all whitespace + separators before validate | — |

Examples valid: `+84912345678`, `0912345678`, `+84 912-345-678`, `(+84) 912 345 678`. Normalize all to `+84912345678` canonical.

### 7.2 VND Amount (`amount_vnd`, `revenue`, `deal_amount`)

| Concern | Rule | Error |
|---|---|---|
| Type | Integer (KHÔNG dùng float để tránh precision loss) | `USR-ERR4` |
| Range | Min 0, Max 1 trillion VND (1_000_000_000_000) | `USR-ERR7` |
| Format input | Accept thousands separator `.` (VN convention) or `,` (en-US). E.g. `1.000.000` or `1,000,000` | — |
| Format output | Always display as `1.000.000₫` (per memory `feedback_vnd_currency_format`) | — |
| Business | NEVER use scientific notation; NEVER abbreviate "1M VND" / "2M" in user-facing UI | — |

### 7.3 Percentage (`discount_pct`, `margin_pct`, `confidence`)

| Concern | Rule | Error |
|---|---|---|
| Type | NUMERIC(5,4) per CLAUDE.md K-9 | `USR-ERR4` |
| Range | 0.0 to 1.0 (NOT 0-100); display × 100 với 2 decimal | `USR-ERR7` |
| DB storage | NUMERIC(5,4) — 4 decimal precision | — |
| Display | Frontend renders `value * 100` với 2 decimal + `%` suffix; backend stores raw 0..1 | — |

### 7.4 UUID v4 (`enterprise_id`, `workflow_id`, `run_id`, etc.)

| Concern | Rule | Error |
|---|---|---|
| Type | String UUID v4 | `USR-ERR4` |
| Structure | Match `^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$` (case-insensitive) | `USR-ERR4` |
| Business | Path params validate tenant scope via JWT (K-12 anti-IDOR) | 403 USR-ERR-403-IDOR |

### 7.5 Date / Timestamp (`event_ts`, `created_at`, `expires_at`)

| Concern | Rule | Error |
|---|---|---|
| Type | ISO 8601 string | `USR-ERR4` |
| Format input | Accept `YYYY-MM-DD` (date only) or `YYYY-MM-DDTHH:MM:SSZ` (timestamp) | — |
| Format output | TIMESTAMPTZ canonical with UTC; FE converts to ICT (UTC+7) display | — |
| Business | Date-range validation USR-ERR8 (start ≤ end) | `USR-ERR8` |
| Future date | Per field: `expires_at` MUST > NOW; `event_ts` MAY be past or future depending context | — |

### 7.6 Password (`password`, new password during reset)

| Concern | Rule | Error |
|---|---|---|
| Type | String | — |
| Length | Min 12, Max 128 (per NFRS NFR-SEC-07) | `USR-ERR5` |
| Composition | ≥1 uppercase + ≥1 lowercase + ≥1 digit + ≥1 special. Special = `!@#$%^&*()_+-=[]{}|;:,.<>?` | `USR-ERR4` |
| Disallow | Common passwords (top 10k list) + username substring | `USR-ERR4` |
| Storage | bcrypt cost 12 (NFR-SEC-07) | — |
| Reset OTP | Email/SMS, expire 1h, single-use | — |

### 7.7 VN Tax Code / CCCD (`tax_code`, `cccd`)

| Concern | Rule | Error |
|---|---|---|
| Type | String digits | `USR-ERR4` |
| Tax code length | 10 digits (company) or 13 digits (branch — 10 + `-` + 3) | `USR-ERR5` |
| CCCD length | 12 digits (new format) or 9 (old CMND deprecated) | `USR-ERR5` |
| Tax structure | Match `^\d{10}(-\d{3})?$` | `USR-ERR4` |
| Business | PII — K-5 redact before external; mask to `{{cccd:hash:abc123}}` (hash-based, last 4 visible) | — |
| Validation | Tax code optionally validate via VN General Department of Taxation API (Phase 3) | — |

### 7.8 File upload (`file`, `document`, `attachment`)

| Concern | Rule | Error |
|---|---|---|
| Type | Multipart binary | — |
| Size | Max 100MB per file; plan-gated (PILOT 50MB, BASIC 100MB, MID 500MB, MAX 2GB) | `USR-ERR5` SIZE_EXCEEDED |
| MIME types allowed | PDF, DOCX, XLSX, CSV, JPG, PNG, WebP (per workflow_nodes.required_document_types) | `USR-ERR4` SYS-ERR-006 |
| Magic byte | Verify content match extension via libmagic (anti-spoof, per P2.5) | `USR-ERR4` SYS-ERR-007 |
| Filename | Sanitize: alphanumeric + `_.-`; KHÔNG path traversal `../` | `USR-ERR4` |
| Idempotency | SHA-256 fingerprint K-8 — duplicate file → return existing reference | — |

### 7.9 Currency Format Display (UI convention)

Per memory `feedback_vnd_currency_format`:
- ✅ "1.000.000₫" hoặc "1 triệu VNĐ"
- ❌ "1M" / "2M" / "$1,000,000" (KHÔNG dùng English/USD abbreviation cho VN UI)
- Frontend `formatVND(value)` utility canonical (mọi component import from `frontend/lib/format/currency.ts`)

### 7.10 Cross-field dependency rules

| Rule | Condition | Error |
|---|---|---|
| Date range | `start_date ≤ end_date` | `USR-ERR8` |
| Discount tier | If `discount_pct > 0.25` → require CFO approval (policy_engine mig 099) | Policy deny + redirect approval queue |
| Refund threshold | If `amount > 5M VND` → require MANAGER claim `approve_refund` (NFRS §5.bis) | 403 USR-ERR-403-CLAIM |
| K-4 external LLM | If `prefer_external=true` → require tenant `consent_external_ai=true` | Policy deny → Qwen fallback |
| MFA required | If user role = SUPER_ADMIN/ADMIN + action=high-risk → require MFA verified within 12h session | 401 + redirect MFA |

### 7.11 Industry vertical enum (Phase 2.8)

| Concern | Rule | Error |
|---|---|---|
| Type | String enum | `USR-ERR4` |
| Allowed values | `Retail`, `F&B`, `Logistics`, `Finance`, `Healthcare`, `Manufacturing`, `Education`, `Generic SME` (8 industries — 3 seeded Phase 2.8, 5 defer Phase 3) | `USR-ERR4` |
| DB | FK to `industry_templates.industry_id` (mig 101) | — |
| Deprecated values | `retail`, `fintech`, `saas`, `manufacturing` (lowercase legacy — accept on read but warn on write) | `WRN-1` |

---

## 8. Implementation cross-ref

- **FE:** zod schemas in `frontend/lib/validators/{email,phone,vnd,...}.ts` — generated from this MD constants
- **BE Python (FastAPI):** Pydantic `field_validator` in `services/*/schemas/`
- **BE Java (auth-service):** Hibernate Validator + custom `@VnPhone` annotation
- **Drift test:** `tests/test_validation_drift.py` (planned) — load this MD's tables + assert every Pydantic schema rejects matching invalid-case fixtures
- **Codegen:** Future cron job that diffs PDF v1.0.X → MD → constants.ts; alerts on drift
