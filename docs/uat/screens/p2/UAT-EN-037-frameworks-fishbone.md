# UAT-EN-037 · Fishbone (Ishikawa) Framework

| | |
|---|---|
| **Mã test** | UAT-EN-037 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/frameworks/fishbone-ishikawa` |
| **Source FE** | `frontend/components/p2/templates/43-frameworks-fishbone.tsx` |
| **Endpoint** | `POST /api/v1/frameworks/fishbone/generate` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

Fishbone diagram (Ishikawa) cho root cause analysis: problem → 6M categories (Method / Machine / Material / Man / Measurement / Environment).

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Render diagram

**Expected**
- ✅ Input "Vấn đề chính" (head fish).
- ✅ SVG/canvas fishbone với 6 branches (categories).
- ✅ Mỗi branch có sub-causes list.

### TC-2 · Generate causes

**Expected**
- ✅ POST → LLM populate causes mỗi branch.

### TC-3 · Add manual sub-cause

**Expected**
- ✅ Click "+ " trên branch → input → save.

### TC-4 · Export PNG

**Expected**
- ✅ Button "Tải xuống PNG" → SVG to image.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | SVG rendering Phase 2 cần D3/Recharts setup. | Phase 1 simple text list. |

## Related screens

- **UAT-EN-033** hub.
