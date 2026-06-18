# UAT-EN-042 · Report Builder

| | |
|---|---|
| **Mã test** | UAT-EN-042 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/reports/builder` |
| **Source FE** | `frontend/components/p2/templates/48-reports-builder.tsx` |
| **Endpoint** | `POST /api/v1/reports/build` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 (F-038) |

---

## Mục tiêu test

Drag-drop report builder: add blocks (KPI / chart / table / text) → arrange → preview → save as template hoặc export PDF.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Render canvas + palette

**Expected**
- ✅ 3 cột: Palette (left) · Canvas (center) · Properties (right).
- ✅ Palette: KPI · Chart · Table · Text · Image · Divider.

### TC-2 · Drag block

**Expected**
- ✅ Drag KPI block vào canvas → block appears → Properties panel update.

### TC-3 · Configure block

**Expected**
- ✅ Properties: data source select + format + style.

### TC-4 · Preview

**Expected**
- ✅ Button "Xem trước" → full-page preview render.

### TC-5 · Export PDF

**Expected**
- ✅ Button "Xuất PDF" → POST `/reports/build/export` → download.

### TC-6 · Save as template

**Expected**
- ✅ Button "Lưu mẫu" → name input → POST → template_id.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Builder Phase 2 — drag-drop library Phase 2. | Phase 1 form-based fallback. |

## Related screens

- **UAT-EN-040** hub.
- **UAT-EN-043** template.
