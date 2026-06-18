# UAT-EN-022 · Decision Detail (wired)

| | |
|---|---|
| **Mã test** | UAT-EN-022 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/decisions/[id]` |
| **Source FE** | `frontend/components/p2/templates/32b-decisions-id-wired.tsx` |
| **Endpoint** | `GET /api/v1/decisions/{id}` |
| **Auth required** | Có |
| **Phase** | Phase 2 ✅ (F-036 wired) |

---

## Mục tiêu test

Production decision detail wired BE qua dynamic route `[id]`. Same UI as UAT-EN-021 nhưng `decisionId` passed via prop từ params thay vì pathname parse.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |
| P2 | Decision tồn tại với valid UUID. |
| P3 | Vào từ /decisions/log click row. |

## Test cases

### TC-1 · Render

**Expected**
- ✅ Same UI structure như UAT-EN-021.
- ✅ Decision data fetched từ `/decisions/{id}`.

### TC-2 · Action toggle

**Expected**
- ✅ Tương tự UAT-EN-021 TC-2.

### TC-3 · Override + feedback (F-036)

**Expected**
- ✅ Modal override + reason.
- ✅ `POST /decisions/{id}/feedback` 200.

### TC-4 · Audit log linkage

**Expected**
- ✅ Section "Audit log" hiện rows liên quan từ `/decisions/{id}/audit`.

### TC-5 · BE 404 / Turbopack crash

**Expected**
- ✅ ErrorBanner nếu BE 404.
- ✅ Note: route `[id]` thuộc nhóm jest-worker crash — test dùng webpack.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Turbopack 500 dynamic route. | webpack mode. |

## Related screens

- **UAT-EN-020** log.
- **UAT-EN-021** legacy.
