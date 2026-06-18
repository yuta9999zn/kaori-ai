# UAT-EN-072 · Branding Email Templates

| | |
|---|---|
| **Mã test** | UAT-EN-072 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/branding/email` |
| **Source FE** | `frontend/components/p2/templates/71-branding-email.tsx` |
| **Endpoint** | `GET/PATCH /api/v1/branding/email-templates` |
| **Auth required** | Có (MANAGER) |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

Customize email templates: subject + body + variables (workspace_name, user_name, ...). Categories: invite / alert / report / password reset.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login MANAGER. |

## Test cases

### TC-1 · Render list templates

**Expected**
- ✅ Tabs: Invite · Alert · Report · Password reset.
- ✅ Mỗi tab: Subject input + Body rich text editor.

### TC-2 · Variable picker

**Expected**
- ✅ Sidebar variables list: `{{user_name}}`, `{{workspace_name}}`, `{{alert_title}}` ...
- ✅ Click variable → insert vào cursor position.

### TC-3 · Preview

**Expected**
- ✅ Button "Xem trước" → rendered email với fake data substituted.

### TC-4 · Send test

**Expected**
- ✅ Input email + button "Gửi thử" → POST → email arrives in inbox.

### TC-5 · Save

**Expected**
- ✅ PATCH → toast.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-071** branding hub.
