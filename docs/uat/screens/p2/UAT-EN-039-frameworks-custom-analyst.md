# UAT-EN-039 · Custom Analyst Framework

| | |
|---|---|
| **Mã test** | UAT-EN-039 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/frameworks/custom-analyst` |
| **Source FE** | `frontend/components/p2/templates/45-frameworks-custom.tsx` |
| **Endpoint** | `POST /api/v1/frameworks/custom/generate` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

Custom framework: user define các sections + prompts + variables → LLM generate analysis theo template tự chế.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login MANAGER. |

## Test cases

### TC-1 · Render builder

**Expected**
- ✅ Template name input + Sections list + each section: name + prompt template (with `{{vars}}`) + add/remove.

### TC-2 · Define variable

**Expected**
- ✅ Variables panel: declare `data_context`, `target_metric`, ...
- ✅ Auto-fill from selected dataset.

### TC-3 · Test run

**Expected**
- ✅ Button "Chạy thử" với sample data → preview output.

### TC-4 · Save template

**Expected**
- ✅ POST → saved framework_id → có thể reuse khắp.

### TC-5 · Share with team

**Expected**
- ✅ Toggle "Chia sẻ workspace" → visible to all.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Custom builder Phase 2 — phức tạp, nhiều edge. | Phase 1 mock UI. |

## Related screens

- **UAT-EN-033** hub.
