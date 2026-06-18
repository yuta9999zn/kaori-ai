# UAT-EN-063 · Auto DB Form Generate

| | |
|---|---|
| **Mã test** | UAT-EN-063 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/auto-db/form-generate` |
| **Source FE** | `frontend/components/p2/templates/63-auto-db-form-generate.tsx` |
| **Endpoint** | `POST /api/v1/auto-db/form-generate` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

Auto-generate input form từ schema: field type, validation, layout, submit endpoint.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |
| P2 | Schema/table tồn tại. |

## Test cases

### TC-1 · Render

**Expected**
- ✅ Select table → preview form auto-generated.

### TC-2 · Customize

**Expected**
- ✅ Toggle field on/off, change label, validation rules.

### TC-3 · Embed code

**Expected**
- ✅ Button "Lấy mã nhúng" → React/HTML snippet.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-061** hub.
- **UAT-EN-062** schema.
