# UAT-EN-034 · SWOT Framework

| | |
|---|---|
| **Mã test** | UAT-EN-034 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/frameworks/swot` |
| **Source FE** | `frontend/components/p2/templates/40-frameworks-swot.tsx` |
| **Endpoint** | `POST /api/v1/frameworks/swot/generate` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

SWOT analysis 2×2 matrix: Strengths / Weaknesses / Opportunities / Threats. LLM generate từ data context.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |
| P2 | Workspace có context (data/insights). |

## Test cases

### TC-1 · Render input

**Expected**
- ✅ PageHeader "SWOT" + form: context textarea + scope select + generate button.

### TC-2 · Generate

**Expected**
- ✅ `POST .../swot/generate` 200 → 2×2 grid render với items mỗi quadrant.

### TC-3 · Edit item

**Expected**
- ✅ Click item → inline edit + save → PATCH.

### TC-4 · Add custom item

**Expected**
- ✅ "+ Thêm" button mỗi quadrant.

### TC-5 · Export to insight

**Expected**
- ✅ Button "Lưu thành insight" → POST /insights → navigate detail.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-033** hub.
