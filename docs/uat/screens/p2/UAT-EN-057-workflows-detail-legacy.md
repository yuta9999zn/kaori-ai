# UAT-EN-057 · Workflow Detail (legacy 307 redirect)

| | |
|---|---|
| **Mã test** | UAT-EN-057 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/workflows/detail` (literal — 307 redirect tới hub) |
| **Source FE** | `frontend/components/p2/templates/56-workflow-detail-legacy.tsx` |
| **Endpoint** | (redirect) |
| **Auth required** | Có |
| **Phase** | Phase 1 (legacy) |

---

## Mục tiêu test

Legacy route /p2/workflows/detail tự redirect tới /p2/workflows/hub. Bookmarks cũ không broken.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Navigate

**Expected**
- ✅ HTTP 307 redirect.
- ✅ URL bar đổi `/p2/workflows/hub`.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Legacy redirect — không cần test sâu. | |

## Related screens

- **UAT-EN-055** /p2/workflows/hub.
