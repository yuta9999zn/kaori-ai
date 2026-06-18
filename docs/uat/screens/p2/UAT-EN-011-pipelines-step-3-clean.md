# UAT-EN-011 · Pipeline Step 3 — Clean Data

| | |
|---|---|
| **Mã test** | UAT-EN-011 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/pipelines/[id]/step-3-clean` |
| **Source FE** | `frontend/components/p2/templates/22-data-pipeline-step-3-clean-data.tsx` |
| **Endpoints** | `GET /api/v1/clean/{pipelineId}/preview` · `POST /api/v1/clean/{pipelineId}/run` |
| **Auth required** | Có |
| **Phase** | Phase 1 ✅ |

---

## Mục tiêu test

Stage 3 cleaning preview với 3-layer rules: Universal + Domain + AI-detected. User review rules + confirm chạy Silver tier transformation.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Pipeline `<id>` đã pass step-2 schema confirm. |

## Test cases

### TC-1 · Render rules list

**Expected**
- ✅ Stepper step 3 active.
- ✅ 3 sections: Universal Rules · Domain Rules · AI-detected Rules.
- ✅ Mỗi rule: name + description + sample affected rows + toggle on/off.

### TC-2 · Disable rule

**Steps**
1. Toggle off rule "Trim whitespace".

**Expected**
- ✅ Preview impact: row count thay đổi.

### TC-3 · Run cleaning

**Expected**
- ✅ Button "Chạy Silver transformation".
- ✅ `POST /clean/{id}/run` 200.
- ✅ Progress streaming SSE.
- ✅ On complete navigate step-4.

### TC-4 · Preview sample

**Expected**
- ✅ Click rule → preview 10 row before/after.

### TC-5 · Loading + error

**Expected**
- ✅ Skeleton + ErrorBanner.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Turbopack 500. Test dùng webpack. | |

## Related screens

- **UAT-EN-010** previous · **UAT-EN-012** next.
