# UAT-EN-056 · New Workflow (Visual Builder)

| | |
|---|---|
| **Mã test** | UAT-EN-056 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/workflows/new` |
| **Source FE** | `frontend/components/p2/templates/55-workflows-new.tsx` |
| **Endpoint** | `POST /api/v1/workflows` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 (P2-S15 — 45 node catalog mig 068) |

---

## Mục tiêu test

Visual workflow builder: drag-drop 45 node types từ palette (mig 068) vào canvas, connect edges, configure properties, save.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Render builder

**Expected**
- ✅ 3-pane layout: Palette (left, 45 node types nhóm theo category) · Canvas (center) · Properties (right).
- ✅ Title input "Workflow name" trên top + status (draft / published).

### TC-2 · Drag node

**Expected**
- ✅ Drag node "AI Insight" vào canvas → node card xuất hiện.
- ✅ Properties panel update với node config.

### TC-3 · Connect edges

**Expected**
- ✅ Drag từ output port → input port khác → edge line vẽ.
- ✅ Edge có branch_path label (success/fallback/exception — mig 076).

### TC-4 · Configure node

**Expected**
- ✅ Click node → Properties panel: name, side_effect_class (K-17 enum), retry config, etc.

### TC-5 · Save draft

**Expected**
- ✅ Button "Lưu nháp" → POST → workflow_id.

### TC-6 · Publish

**Expected**
- ✅ Button "Publish" → validate (no orphan nodes, valid side_effect_class) → POST status=published.

### TC-7 · Workflow as Code export

**Expected**
- ✅ Button "Xuất YAML" → POST `/workflows/{id}/export.yaml` → download.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Visual builder Phase 2 — React Flow/Mermaid integration. | Phase 1 form-based. |

## Related screens

- **UAT-EN-055** hub.
- **UAT-EN-058** detail.
