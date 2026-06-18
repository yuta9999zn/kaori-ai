# UAT-EN-062 · Auto DB Schema Suggestion

| | |
|---|---|
| **Mã test** | UAT-EN-062 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/auto-db/schema-suggestion` |
| **Source FE** | `frontend/components/p2/templates/62-auto-db-schema.tsx` |
| **Endpoint** | `POST /api/v1/auto-db/schema-suggest` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

LLM suggest schema từ data sample/description. Output: tables + columns + relationships + DDL preview.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Render form

**Expected**
- ✅ Textarea "Mô tả dữ liệu" hoặc upload sample.
- ✅ Submit button.

### TC-2 · Generate

**Expected**
- ✅ POST → entity diagram + DDL Postgres.

### TC-3 · Apply DDL

**Expected**
- ✅ Button "Áp dụng" → confirm → create tables.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Phase 2 — DDL apply chưa wire fully. | Phase 1 preview only. |

## Related screens

- **UAT-EN-061** hub.
