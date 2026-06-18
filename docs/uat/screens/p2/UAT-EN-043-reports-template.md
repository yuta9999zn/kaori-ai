# UAT-EN-043 · Report Templates

| | |
|---|---|
| **Mã test** | UAT-EN-043 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/reports/template` |
| **Source FE** | `frontend/components/p2/templates/49-reports-template.tsx` |
| **Endpoint** | `GET/POST/DELETE /api/v1/reports/templates` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

Quản lý templates (built-in + custom): list, preview, clone, edit, delete.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Render list

**Expected**
- ✅ Grid templates: built-in (lock icon) + custom (edit/delete icons).
- ✅ Mỗi card: thumbnail + name + description + "Sử dụng".

### TC-2 · Preview

**Expected**
- ✅ Click "Xem trước" → modal full-page.

### TC-3 · Clone built-in

**Expected**
- ✅ "Sao chép" → POST → new template_id (custom).

### TC-4 · Delete custom

**Expected**
- ✅ Trash icon → confirm → DELETE.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-040** hub.
