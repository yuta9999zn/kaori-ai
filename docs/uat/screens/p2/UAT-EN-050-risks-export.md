# UAT-EN-050 · Risks Export

| | |
|---|---|
| **Mã test** | UAT-EN-050 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/risks/export` |
| **Source FE** | `frontend/components/p2/templates/f039-risks-export.tsx` |
| **Endpoint** | `GET /api/v1/risks/export?...` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

Export risk register sang CSV / PDF. Filter severity + owner + status trước export.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Render form

**Expected**
- ✅ Filters: Severity / Owner / Status / Date range.
- ✅ Format: CSV / PDF.
- ✅ Button "Xuất".

### TC-2 · Submit

**Expected**
- ✅ Download file.
- ✅ Toast "Đã tải <filename>".

### TC-3 · Empty result

**Expected**
- ✅ Banner "Không có risk khớp bộ lọc.".

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-049** hub.
