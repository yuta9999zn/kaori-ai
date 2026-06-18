# UAT-EN-012 · Pipeline Step 4 — Analyze

| | |
|---|---|
| **Mã test** | UAT-EN-012 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/pipelines/[id]/step-4-analyze` |
| **Source FE** | `frontend/components/p2/templates/23-data-pipeline-step-4-analyze.tsx` |
| **Endpoints** | `GET /analytics/templates` · `POST /analyze/{pipelineId}/run` |
| **Auth required** | Có |
| **Phase** | Phase 1 ✅ |

---

## Mục tiêu test

Stage 4 chọn analysis framework + run. Hiện 1 primary framework + optional secondary (K-10). Consent modal nếu chọn external LLM (K-4).

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Pipeline `<id>` qua step-3 Silver complete. |

## Test cases

### TC-1 · Render template chooser

**Expected**
- ✅ Stepper step 4 active.
- ✅ Grid framework cards: SWOT / 6W / Fishbone / MoM/YoY / Custom.
- ✅ Mỗi card: icon + description + estimated tokens.

### TC-2 · Select framework

**Expected**
- ✅ Click card → highlight gold border.
- ✅ Optional secondary chooser appear (K-10 multi-framework).

### TC-3 · Consent external LLM

**Steps**
1. Tenant có `consent_external = true`.
2. Toggle "Prefer external (Claude)" trên panel.

**Expected**
- ✅ Modal consent appear: "Phân tích này sẽ gửi data qua Anthropic Claude. Dữ liệu sẽ được redact PII trước khi gửi."
- ✅ Confirm → set `prefer_external: true` trong POST body.
- ✅ Tenant `consent_external = false` → toggle disabled + tooltip "Workspace chưa bật consent external".

### TC-4 · Run analysis

**Expected**
- ✅ `POST /analyze/{id}/run` body `{framework, secondary?, prefer_external?}` 200.
- ✅ Progress SSE.
- ✅ On complete → navigate step-5.

### TC-5 · Data residency strict

**Steps**
1. Tenant `data_residency_strict = true`.

**Expected**
- ✅ Toggle external **vô hiệu hoàn toàn** với note "Workspace bắt buộc on-prem LLM (K-4)".

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Turbopack 500. Test dùng webpack. | |

## Related screens

- **UAT-EN-011** previous · **UAT-EN-013** next.
