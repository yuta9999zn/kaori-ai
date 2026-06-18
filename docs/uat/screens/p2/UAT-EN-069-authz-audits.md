# UAT-EN-069 · Authz Audits

| | |
|---|---|
| **Mã test** | UAT-EN-069 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/authz/audits` |
| **Source FE** | `frontend/components/p2/templates/69-authz-audits.tsx` |
| **Endpoint** | `GET /api/v1/authz/audits?cursor=&limit=` |
| **Auth required** | Có (MANAGER) |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

Audit log mọi permission check (allow + deny). Filter user / resource / outcome / date range.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login MANAGER. |

## Test cases

### TC-1 · Render table

**Expected**
- ✅ Filters: User / Action / Outcome (allow/deny) / Date range.
- ✅ Table: Time · User · Resource · Action · Outcome badge · Reason · Policy ID.

### TC-2 · Filter deny only

**Expected**
- ✅ Table chỉ rows deny — flag suspicious access patterns.

### TC-3 · Click row → detail

**Expected**
- ✅ Drawer hiện full context: subject attrs, resource attrs, policy chain evaluated.

### TC-4 · Export

**Expected**
- ✅ Export CSV cho compliance review.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-067** ABAC builder.
- **UAT-EN-068** simulate.
