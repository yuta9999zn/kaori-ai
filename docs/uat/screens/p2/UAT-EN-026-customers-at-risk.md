# UAT-EN-026 · Customers At-Risk (North Star)

| | |
|---|---|
| **Mã test** | UAT-EN-026 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/customers/at-risk` |
| **Source FE** | `frontend/components/p2/templates/f060-customers-at-risk.tsx` |
| **Endpoint** | `GET /api/v1/customers/at-risk` |
| **Auth required** | Có |
| **Phase** | Phase 1 ✅ (F-060 North Star metric) |

---

## Mục tiêu test

North Star: `SUM(revenue_at_risk WHERE churn_risk_label='HIGH' AND is_actioned=true)`. Hiển thị customers HIGH risk + revenue tại risk + actioned status.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |
| P2 | Pipeline đã sinh churn_risk_label cho customers. |

## Test cases

### TC-1 · Render hero KPI

**Expected**
- ✅ PageHeader "Khách hàng rủi ro".
- ✅ Hero KPI lớn: "Revenue tại risk đã hành động: 1.234.567.890₫".
- ✅ Sub KPI: Total HIGH-risk count / Actioned ratio %.

### TC-2 · Render table

**Expected**
- ✅ Table: customer_external_id · Name · Revenue at risk · Churn label (HIGH/MED/LOW) · Last decision · Actioned · Actions.
- ✅ Actioned checkbox per row.

### TC-3 · Toggle actioned

**Expected**
- ✅ Click checkbox → `PATCH /customers/{id}/action` → Hero KPI update.

### TC-4 · Filter HIGH only

**Expected**
- ✅ Dropdown filter → table HIGH only.

### TC-5 · Click row → customer detail

**Expected**
- ✅ Drawer: decisions liên kết + insights + revenue history.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-020** /p2/decisions/log — decisions liên kết.
