# UAT-EN-015 · Insight Detail (legacy mock route)

| | |
|---|---|
| **Mã test** | UAT-EN-015 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/insights/id-detail` (legacy literal route — mock template) |
| **Source FE** | `frontend/components/p2/templates/26-insight-id-detail.tsx` |
| **Endpoint** | `GET /api/v1/insights/{id}` |
| **Auth required** | Có |
| **Phase** | Phase 1 ✅ |
| **Fix** | commit `399a629` — window.location.pathname → usePathname() |

---

## Mục tiêu test

Detail 1 insight với prompt + LLM response + alternatives_considered + bookmarking + decision linkage.

> Note: route literal `/p2/insights/id-detail` là dev-mode link cũ. Production link đi qua `/p2/insights/{uuid}`.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |
| P2 | (Cho dev-mode): insight UUID có thể fake/seed. |

## Test cases

### TC-1 · Render (sau fix usePathname)

**Steps**
1. Vào `/p2/insights/id-detail`.

**Expected**
- ✅ HTTP 200 (sau fix `399a629`).
- ✅ Insight ID extracted từ pathname.
- ✅ Header: title + framework Badge + confidence percentage.
- ✅ Section "Prompt" + "LLM response" + "Alternatives considered" (K-6).
- ✅ Section "Decisions liên kết" → list decisions sinh ra từ insight.
- ✅ Actions: Bookmark / Generate report / Override decision.

### TC-2 · Bookmark toggle

**Expected**
- ✅ `POST /insights/{id}/bookmark` 200.
- ✅ Icon Bookmark filled.

### TC-3 · Generate report from insight

**Expected**
- ✅ Click "Tạo report" → modal chọn template → `POST /reports` → navigate report detail.

### TC-4 · Link to decision

**Expected**
- ✅ Click decision item → `/p2/decisions/{decision_id}` (UAT-EN-031).

### TC-5 · BE 404

**Expected**
- ✅ ErrorBanner "Insight không tồn tại".

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Trang là legacy mock — production link đi `/p2/insights/[id]` dynamic route. | UAT-EN-014 list dùng dynamic route. |

## Related screens

- **UAT-EN-014** list.
- **UAT-EN-016** generate.
