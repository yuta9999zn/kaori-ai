# UAT-EN-018 · Chart Picker

| | |
|---|---|
| **Mã test** | UAT-EN-018 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/charts/picker` |
| **Source FE** | `frontend/components/p2/templates/29-chart-picker.tsx` |
| **Endpoint** | (FE only) |
| **Auth required** | Có |
| **Phase** | Phase 1 ✅ |

---

## Mục tiêu test

Smart chart type picker: user mô tả mục đích → recommend chart type (bar / line / pie / scatter / heatmap).

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Render quiz

**Expected**
- ✅ PageHeader "Chart Picker".
- ✅ Form 3-4 question multiple-choice: "Bạn muốn gì?" (comparison / trend / composition / relationship / distribution).

### TC-2 · Recommend

**Steps**
1. Trả lời từng câu.

**Expected**
- ✅ Sau câu cuối → preview chart recommended với sample data.
- ✅ Alt recommendations (top 3).

### TC-3 · Apply recommendation

**Expected**
- ✅ Button "Dùng chart này" → save preference cho workspace.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-019** /p2/charts/categories.
