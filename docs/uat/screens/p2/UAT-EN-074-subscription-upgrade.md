# UAT-EN-074 · Subscription Upgrade

| | |
|---|---|
| **Mã test** | UAT-EN-074 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/subscription/upgrade` |
| **Source FE** | `frontend/components/p2/templates/34-subscription-upgrade.tsx` |
| **Endpoint** | `POST /api/v1/subscription/upgrade` |
| **Auth required** | Có (MANAGER) |
| **Phase** | Phase 1 ✅ |

---

## Mục tiêu test

Upgrade plan: chọn plan mới + confirm + capture intent. Phase 1 stub — Phase 2 wire Stripe / VNPay.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login MANAGER. |

## Test cases

### TC-1 · Render plan comparison

**Expected**
- ✅ Grid 4-5 plan cards: PILOT / ENT_BASIC / ENT_MID / ENT_MAX / ENT_ROI.
- ✅ Mỗi card: price VND + unique customers limit + features list + "Chọn" button.
- ✅ Current plan có badge "Plan hiện tại" (disabled button).

### TC-2 · Click upgrade

**Expected**
- ✅ Modal confirm: target plan + new price + effective date + prorate calculation.
- ✅ Button "Xác nhận nâng cấp" → POST 200.
- ✅ Toast "Đã ghi nhận yêu cầu nâng cấp. Team Kaori sẽ liên hệ trong 24h.".

### TC-3 · Downgrade flow

**Expected**
- ✅ Tương tự, banner cảnh báo "Downgrade có thể mất feature X".
- ✅ Confirm modal extra step.

### TC-4 · ROI Share plan special

**Expected**
- ✅ Plan ENT_ROI có note "Cần ≥ 3 tháng ENT_MAX trước. Liên hệ team".
- ✅ Click → modal contact form thay vì auto-upgrade.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Payment integration Phase 2 — Phase 1 chỉ capture intent. | Team Kaori contact manual. |

## Related screens

- **UAT-EN-073** quota.
