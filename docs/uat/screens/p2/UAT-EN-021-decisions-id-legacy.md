# UAT-EN-021 · Decision Detail (legacy mock)

| | |
|---|---|
| **Mã test** | UAT-EN-021 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/decisions/id` (literal — legacy dev-mode mock) |
| **Source FE** | `frontend/components/p2/templates/32-decisions-id.tsx` |
| **Endpoint** | `GET /api/v1/decisions/{id}` |
| **Auth required** | Có |
| **Phase** | Phase 1 ✅ |
| **Fix** | commit `399a629` — window.location → usePathname() |

---

## Mục tiêu test

Decision detail panel: rationale, alternatives_considered, confidence, prompt_hash, llm_provider, action toggle, SHAP placeholder (Phase 2).

> Route `/decisions/id` là literal (dev mock). Production link đi `/p2/decisions/[id]` dynamic (UAT-EN-031).

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |

## Test cases

### TC-1 · Render

**Expected**
- ✅ Decision ID extracted từ pathname.
- ✅ Header: title + framework + confidence + provider badge.
- ✅ Sections: Rationale / Alternatives / Linkages (insight, pipeline, audit log) / Action toggle (is_actioned checkbox) / Phase 2 placeholders (SHAP / Override / Feedback retrain).

### TC-2 · Toggle is_actioned

**Expected**
- ✅ Click → `POST /decisions/{id}/action` 200.
- ✅ Badge "Đã hành động" appear.

### TC-3 · Override Phase 2

**Expected**
- ✅ Button "Override" → modal + reason form (F-036).
- ✅ Submit → `POST /decisions/{id}/feedback`.

### TC-4 · SHAP panel Phase 2

**Expected**
- ✅ Placeholder "Phase 2 — đang phát triển".

### TC-5 · Link insight source

**Expected**
- ✅ Click insight link → `/p2/insights/{id}`.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Trang legacy. Production dùng /decisions/[id]. | UAT-EN-031. |

## Related screens

- **UAT-EN-020** log.
- **UAT-EN-031** wired version.
