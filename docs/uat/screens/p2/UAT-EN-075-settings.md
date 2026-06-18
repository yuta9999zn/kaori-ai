# UAT-EN-075 · Settings (Cài đặt)

| | |
|---|---|
| **Mã test** | UAT-EN-075 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/settings` |
| **Source FE** | (workspace settings hub — pending wire) |
| **Endpoint** | `GET/PATCH /api/v1/workspace/settings` |
| **Auth required** | Có (MANAGER) |
| **Phase** | Phase 1 ✅ |

---

## Mục tiêu test

Settings hub: general info / integrations / notifications / data residency / consent external / API keys.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login MANAGER. |

## Test cases

### TC-1 · Render

**Expected**
- ✅ Tabs: General · Integrations · Notifications · Data residency · API.
- ✅ General: workspace name / timezone / locale / fiscal year start.
- ✅ Data residency: toggle "Strict (chỉ Qwen local)" — K-4 override.
- ✅ Consent external LLM: toggle global.

### TC-2 · Toggle consent external

**Expected**
- ✅ Toggle on → confirm modal "Sẽ cho phép Claude/GPT khi user opt-in per-call. PII vẫn được masking trước khi gửi.".
- ✅ Save → PATCH.

### TC-3 · Toggle data residency strict

**Expected**
- ✅ Toggle on → confirm "Sẽ override consent external; workspace luôn dùng Qwen local. K-4 invariant.".

### TC-4 · Integrations

**Expected**
- ✅ List: Telegram bot / Zalo / Slack / Microsoft / Gmail — connect/disconnect per channel.

### TC-5 · Notifications

**Expected**
- ✅ Per-event channel preferences (email / Telegram / Zalo / in-app).

### TC-6 · API keys

**Expected**
- ✅ List enterprise-level API keys (khác workspace keys ở /platform).

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Trang settings chưa fully scaffolded (placeholder). | Phase 2 buildout. |

## Related screens

- (none)
