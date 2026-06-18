# UAT-EN-059 · Workflow ID Test Run

| | |
|---|---|
| **Mã test** | UAT-EN-059 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/workflows/id-test` (literal mock — test playground) |
| **Source FE** | `frontend/components/p2/templates/57-workflows-id-test.tsx` |
| **Endpoint** | `POST /api/v1/workflows/{id}/test-run` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

Playground: chạy thử workflow với sample input, xem từng node execute step-by-step, debug.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Render

**Expected**
- ✅ Input panel: sample JSON / form.
- ✅ Canvas workflow + step markers.

### TC-2 · Run step-by-step

**Expected**
- ✅ Button "Run" → từng node light up (executing → completed) theo thứ tự.
- ✅ Inspector hiện input/output mỗi node.

### TC-3 · Breakpoint

**Expected**
- ✅ Click node → toggle breakpoint → run dừng tại đó.

### TC-4 · Reset

**Expected**
- ✅ Button "Reset" → clear state, ready for next test.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Test playground Phase 2 advanced. | Phase 1 stub. |

## Related screens

- **UAT-EN-058** detail.
