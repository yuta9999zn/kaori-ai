# UAT-EN-013 · Pipeline Step 5 — Results

| | |
|---|---|
| **Mã test** | UAT-EN-013 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/pipelines/[id]/step-5-results` |
| **Source FE** | `frontend/components/p2/templates/24-data-pipeline-step-5-results.tsx` |
| **Endpoint** | `GET /analyze/{pipelineId}/results` |
| **Auth required** | Có |
| **Phase** | Phase 1 ✅ |
| **Dynamic** | `force-dynamic` (uses `useSearchParams` cho `?run_id=`) |

---

## Mục tiêu test

Stage 5 hiển thị kết quả analysis: insights, decisions, alternatives_considered (K-6), confidence per insight, action buttons.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Pipeline `<id>` qua step-4 analysis complete. |

## Test cases

### TC-1 · Render results

**Expected**
- ✅ Stepper step 5 active.
- ✅ Header card: pipeline summary (framework / time / token usage / cost VND).
- ✅ Insights list: mỗi insight có title, description, confidence badge, framework tag.
- ✅ Decisions section: mỗi decision có rationale + alternatives_considered + action (override/accept).

### TC-2 · Drill insight

**Expected**
- ✅ Click insight → drawer/modal hiện full prompt + LLM response + provider/version (K-20).

### TC-3 · Create decision action

**Steps**
1. Click "Accept" trên 1 decision.

**Expected**
- ✅ `POST /decisions/{id}/action` body `{is_actioned: true}` 200.
- ✅ Row update badge "Đã hành động".

### TC-4 · Override decision

**Steps**
1. Click "Override".

**Expected**
- ✅ Modal nhập lý do override.
- ✅ `POST /decisions/{id}/feedback` body `{override_reason}` (F-036 retrain trigger).

### TC-5 · Export results

**Expected**
- ✅ Button "Xuất PDF" / "Xuất CSV" → download.

### TC-6 · Loading + error

**Expected**
- ✅ Skeleton + ErrorBanner.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Turbopack 500. Test dùng webpack. | |

## Related screens

- **UAT-EN-012** previous.
- **UAT-EN-021..025** /p2/insights — view insights riêng.
- **UAT-EN-028** /p2/decisions — log decisions.
