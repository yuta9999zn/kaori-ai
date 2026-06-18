# UAT-EN-014 · Insights List

| | |
|---|---|
| **Mã test** | UAT-EN-014 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/insights/list` |
| **Source FE** | `frontend/components/p2/templates/25-insight-list.tsx` |
| **Endpoint** | `GET /api/v1/insights?cursor=&limit=` |
| **Auth required** | Có |
| **Phase** | Phase 1 ✅ (F-025) |

---

## Mục tiêu test

Liệt kê tất cả insights generated trong workspace. Filter framework / status / confidence threshold. Click sang detail.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login enterprise role. |
| P2 | Workspace có ≥ 1 insight (từ pipeline step-5 hoặc generate manual). |

## Test cases

### TC-1 · Render table

**Expected**
- ✅ PageHeader "Insights" + button "+ Tạo insight".
- ✅ Filters: framework (all/SWOT/6W/...) + status (new/saved/archived) + confidence threshold.
- ✅ Table columns: Title · Framework · Confidence · Pipeline source · Created · Actions.

### TC-2 · Click insight → detail

**Expected**
- ✅ Navigate `/p2/insights/id-detail?id={uuid}` (UAT-EN-015 — note legacy mock route).

### TC-3 · Bookmark insight

**Expected**
- ✅ Click bookmark icon → `POST /insights/{id}/bookmark` → badge "Đã lưu".

### TC-4 · Filter confidence

**Steps**
1. Slider min confidence = 0.8.

**Expected**
- ✅ Table chỉ rows confidence ≥ 0.8.

### TC-5 · Empty / loading / error

**Expected**
- ✅ Skeleton + empty state "Chưa có insight" + ErrorBanner.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-015** /p2/insights/id-detail.
- **UAT-EN-016** /p2/insights/generate.
- **UAT-EN-017** /p2/insights/knowledge-base.
