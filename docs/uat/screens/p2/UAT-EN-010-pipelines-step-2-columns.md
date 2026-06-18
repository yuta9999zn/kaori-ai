# UAT-EN-010 · Pipeline Step 2 — Configure Columns

| | |
|---|---|
| **Mã test** | UAT-EN-010 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/pipelines/[id]/step-2-columns` |
| **Source FE** | `frontend/components/p2/templates/21-data-pipeline-step-2-configure-columns.tsx` |
| **Endpoints** | `GET /api/v1/schema/{pipelineId}` · `POST /api/v1/schema/{pipelineId}/confirm` |
| **Auth required** | Có |
| **Phase** | Phase 1 ✅ |

---

## Mục tiêu test

Auto-detected schema từ upload (Stage 2: exact match → fuzzy → LLM fallback). User review + chỉnh column type / role / unit / nullable / pii. Confirm → pipeline chuyển stage 3 (cleaning).

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |
| P2 | Pipeline `<id>` đã hoàn thành stage 1 upload + stage 2 schema detection. |

## Test cases

### TC-1 · Render schema

**Expected**
- ✅ Stepper 5 pills (step 2 active).
- ✅ Table columns: # · Tên cột · Type detected · Type override · Role · Unit · Nullable · PII · Confidence · Source method.
- ✅ Mỗi row: confidence badge (green ≥ 0.8, yellow 0.6-0.8, red < 0.6).
- ✅ Source method badge: "exact" / "fuzzy" / "llm".

### TC-2 · Override column type

**Steps**
1. Click cell "Type override" của row → select đổi từ VARCHAR sang INTEGER.

**Expected**
- ✅ Row update `source: 'manual'` (badge đổi grey).

### TC-3 · Toggle PII flag

**Steps**
1. Toggle PII column (email).

**Expected**
- ✅ K-5 masking sẽ apply ở Silver tier.

### TC-4 · Confirm schema

**Expected**
- ✅ Button "Xác nhận & chuyển bước 3".
- ✅ `POST /schema/{id}/confirm` body `{mappings}` 200.
- ✅ Navigate `/p2/pipelines/{id}/step-3-clean` (UAT-EN-011).

### TC-5 · BE 404 / pipeline không tồn tại

**Expected**
- ✅ ErrorBanner.

### TC-6 · Low confidence threshold

**Expected**
- ✅ Banner cảnh báo nếu > 30% columns có confidence < 0.6.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Pipeline step pages bị Turbopack jest-worker crash. Test dùng `--webpack`. | Documented in MIGRATION_REPORT_P1.md. |

## Related screens

- **UAT-EN-009** previous step.
- **UAT-EN-011** next step.
