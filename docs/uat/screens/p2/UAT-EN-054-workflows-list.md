# UAT-EN-054 · Workflows List (Tất cả workflow)

| | |
|---|---|
| **Mã test** | UAT-EN-054 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/workflows` |
| **Source FE** | `frontend/components/p2/templates/53-workflows-list.tsx` |
| **Endpoint** | `GET /api/v1/workflows?cursor=&limit=` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 (P2-S15/S16) |

---

## Mục tiêu test

Liệt kê workflows trong workspace: status / template / department / runs count.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Render table

**Expected**
- ✅ PageHeader "Workflows" + button "+ Tạo workflow mới" → /p2/workflows/new.
- ✅ Table: Tên · Mô tả · Department · # Runs · Updated · Status · Actions (eye/edit/delete).

### TC-2 · Filter department

**Expected**
- ✅ Dropdown filter.

### TC-3 · Click row → detail

**Expected**
- ✅ Navigate `/p2/workflows/{id}` (UAT-EN-058).

### TC-4 · Empty / loading / error

**Expected**
- ✅ Standard.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-055** hub.
- **UAT-EN-056** new.
- **UAT-EN-058** detail.
