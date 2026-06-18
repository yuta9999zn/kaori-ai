# UAT-EN-071 · Branding Hub

| | |
|---|---|
| **Mã test** | UAT-EN-071 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/branding` |
| **Source FE** | `frontend/components/p2/templates/70-branding-hub.tsx` |
| **Endpoint** | `GET/PATCH /api/v1/branding` |
| **Auth required** | Có (MANAGER) |
| **Phase** | Phase 1 ✅ |

---

## Mục tiêu test

Workspace branding: logo, primary color, font, custom CSS. White-label reports + emails.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login MANAGER. |

## Test cases

### TC-1 · Render form

**Expected**
- ✅ Logo upload (preview + remove).
- ✅ Color picker primary / accent.
- ✅ Font select (Inter / Playfair / custom).
- ✅ Preview pane bên phải hiển thị mẫu report với branding applied.

### TC-2 · Save

**Expected**
- ✅ PATCH 200 → toast.
- ✅ Reload page → branding persist.

### TC-3 · Reset to default

**Expected**
- ✅ Confirm → DELETE → restore Kaori default cream/gold.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-072** branding/email.
