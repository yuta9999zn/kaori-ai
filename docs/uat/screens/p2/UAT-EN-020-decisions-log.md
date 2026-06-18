# UAT-EN-020 · Decisions Log

| | |
|---|---|
| **Mã test** | UAT-EN-020 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/decisions/log` (alias `/p2/decisions`) |
| **Source FE** | `frontend/components/p2/templates/31-decision-log.tsx` |
| **Endpoint** | `GET /api/v1/decisions?cursor=&limit=` |
| **Auth required** | Có |
| **Phase** | Phase 1 ✅ (K-6) |

---

## Mục tiêu test

Nhật ký quyết định bất biến (K-6) — mọi automated decision + manual override đều ghi. Filter status / framework / actioned / date range.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |
| P2 | Workspace có ≥ 1 decision. |

## Test cases

### TC-1 · Render table

**Expected**
- ✅ PageHeader "Nhật ký quyết định".
- ✅ Filters: framework / actioned (yes/no) / date range / confidence min.
- ✅ Table columns: Title · Framework · Confidence · LLM provider · Actioned · Created · Actions.

### TC-2 · LLM provider badge

**Expected**
- ✅ qwen-2.5-internal → green Badge "Qwen 2.5 nội bộ" + icon Lock.
- ✅ claude-sonnet → yellow Badge "Claude Sonnet" + icon Globe.
- ✅ gpt-4o → yellow Badge "GPT-4o".

### TC-3 · Click row → detail

**Expected**
- ✅ Navigate `/p2/decisions/{id}` (UAT-EN-031 wired) hoặc `/p2/decisions/id` (mock).

### TC-4 · Filter + pagination

**Expected**
- ✅ Filter active → reset cursor.

### TC-5 · Export log

**Expected**
- ✅ Button "Xuất CSV" → audit log dump.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-021** /p2/decisions/id (legacy mock).
- **UAT-EN-031** /p2/decisions/{id} (wired).
