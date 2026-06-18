# UAT-EN-048 · Strategy Review Meetings

| | |
|---|---|
| **Mã test** | UAT-EN-048 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/strategy/review-meeting` |
| **Source FE** | `frontend/components/p2/templates/fnew40-strategy-review.tsx` |
| **Endpoint** | `GET/POST /api/v1/strategy/review-meetings` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

Schedule + record OKR review meetings. Auto-generate agenda từ OKR check-in state. Notes + action items capture.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Render meeting list

**Expected**
- ✅ Table: Date · Title · Attendees · Status (planned/done) · Actions.

### TC-2 · Create meeting

**Expected**
- ✅ Modal: title + date + attendees + auto-agenda toggle.
- ✅ POST → meeting_id.

### TC-3 · Capture notes (live during meeting)

**Expected**
- ✅ Open meeting → notes editor + action items checklist.

### TC-4 · Generate summary AI

**Expected**
- ✅ Button "AI tổng kết" → LLM summarize notes + extract action items.

### TC-5 · Export minutes

**Expected**
- ✅ Export PDF / email recipients.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-046** OKR.
