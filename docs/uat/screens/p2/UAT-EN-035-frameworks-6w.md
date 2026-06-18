# UAT-EN-035 · 6W Framework

| | |
|---|---|
| **Mã test** | UAT-EN-035 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/frameworks/6w` |
| **Source FE** | `frontend/components/p2/templates/41-frameworks-6w.tsx` |
| **Endpoint** | `POST /api/v1/frameworks/6w/generate` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

6W framework: Who / What / When / Where / Why / How (W6 + 1H).

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Render 6-question form

**Expected**
- ✅ 6 question cards với input textarea mỗi cái.
- ✅ Context input chung.

### TC-2 · Generate auto-fill

**Expected**
- ✅ Button "AI điền tự động" → LLM populate 6 fields.

### TC-3 · Edit + save

**Expected**
- ✅ Inline edit + save.

### TC-4 · Export insight

**Expected**
- ✅ Tương tự SWOT.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-033** hub.
