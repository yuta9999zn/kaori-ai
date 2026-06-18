# UAT-EN-073 · Subscription Quota Screen

| | |
|---|---|
| **Mã test** | UAT-EN-073 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/subscription/quota-screen` |
| **Source FE** | `frontend/components/p2/templates/33-subscription-quota-screen.tsx` |
| **Endpoint** | `GET /api/v1/subscription/quota` |
| **Auth required** | Có |
| **Phase** | Phase 1 ✅ (K-11) |

---

## Mục tiêu test

Workspace user xem quota tháng hiện tại: plan + unique customers used / limit + threshold + remaining days.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Render

**Expected**
- ✅ PageHeader "Gói cước & Hạn mức".
- ✅ Card lớn: plan badge + counter "N / M unique customers".
- ✅ QuotaBar với % + threshold markers (80% warn / 95% critical).
- ✅ Cards bổ sung: ngày còn lại trong kỳ / projected end-of-month / overage prediction.

### TC-2 · Threshold warn

**Steps**
1. Usage ≥ 80%.

**Expected**
- ✅ Yellow banner "Cảnh báo: gần hết quota — cân nhắc nâng cấp.".
- ✅ Link sang /p2/subscription/upgrade (UAT-EN-074).

### TC-3 · Threshold critical

**Steps**
1. Usage ≥ 95%.

**Expected**
- ✅ Red banner + persistent toast notification.

### TC-4 · Overage prediction

**Expected**
- ✅ Box "Dự kiến vượt hạn mức: X đơn vị → Y VND phụ phí".

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-074** upgrade.
