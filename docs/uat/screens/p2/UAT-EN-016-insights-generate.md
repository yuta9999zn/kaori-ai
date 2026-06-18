# UAT-EN-016 · Generate Insight (manual)

| | |
|---|---|
| **Mã test** | UAT-EN-016 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/insights/generate` |
| **Source FE** | `frontend/components/p2/templates/27-insights-generate.tsx` |
| **Endpoint** | `POST /api/v1/insights/generate` |
| **Auth required** | Có |
| **Phase** | Phase 1 ✅ |

---

## Mục tiêu test

Form generate insight ad-hoc: chọn dataset + framework + custom question + consent external (K-4). BE chạy LLM → return insight.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |
| P2 | ≥ 1 Gold view tồn tại. |

## Test cases

### TC-1 · Render form

**Expected**
- ✅ PageHeader "Tạo insight".
- ✅ Form: Dataset select (Gold views) + Framework chooser + Custom question textarea + Consent toggle + Generate button.

### TC-2 · Submit thành công

**Expected**
- ✅ Button spinner.
- ✅ `POST /insights/generate` 200 body `{insight_id}`.
- ✅ Navigate `/p2/insights/{insight_id}` (detail).

### TC-3 · Consent external

**Expected**
- ✅ Toggle ON → confirm modal về PII redaction.
- ✅ Tenant residency strict → toggle disabled.

### TC-4 · Question validation

**Expected**
- ✅ Question < 10 chars → button disabled.
- ✅ Question > 1000 chars → error "Quá dài".

### TC-5 · LLM cost preview

**Expected**
- ✅ Hint dưới form: "Ước tính tokens: N, chi phí: M VND".

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-014** list.
