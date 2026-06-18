# UAT-EN-058 · Workflow Detail (dynamic [id])

| | |
|---|---|
| **Mã test** | UAT-EN-058 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/workflows/[id]` |
| **Source FE** | `frontend/components/p2/templates/60-workflow-detail.tsx` |
| **Endpoint** | `GET /api/v1/workflows/{id}` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

Detail 1 workflow: visualization (tree/graph) + nodes config + recent runs + edit mode toggle.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |
| P2 | Workflow ID hợp lệ. |

## Test cases

### TC-1 · Render visualization

**Expected**
- ✅ Header: name + status + last updated + edit button.
- ✅ Canvas: nodes + edges rendered (cream/gold style).
- ✅ Mig 076: swimlane bands, mandatory flag, branch_path colors.
- ✅ Sidebar: node count / edge count / version history.

### TC-2 · Edit mode

**Expected**
- ✅ Click "Edit" → open visual builder (UAT-EN-056) với pre-fill.

### TC-3 · Recent runs

**Expected**
- ✅ Section dưới: table runs + status + duration + per-node execution_state (mig 076 8-value enum).

### TC-4 · Run workflow

**Expected**
- ✅ Button "Run now" → POST /workflows/{id}/run → toast + new run row.

### TC-5 · Comments + locks (P2-S16)

**Expected**
- ✅ Section "Bình luận": list comments + reply.
- ✅ Lock indicator nếu workflow đang được edit bởi user khác (mig 072).

### TC-6 · Turbopack 500

**Expected**
- ✅ Note dynamic [id] — dùng webpack.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Turbopack 500. | webpack. |

## Related screens

- **UAT-EN-054** list.
- **UAT-EN-056** new/edit.
