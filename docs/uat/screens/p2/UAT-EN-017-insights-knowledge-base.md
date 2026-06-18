# UAT-EN-017 · Insights Knowledge Base

| | |
|---|---|
| **Mã test** | UAT-EN-017 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/insights/knowledge-base` |
| **Source FE** | `frontend/components/p2/templates/28-insight-knowledge-base.tsx` |
| **Endpoint** | `GET /api/v1/insights/knowledge-base?q=` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 (F-NEW27) |

---

## Mục tiêu test

Knowledge base search across all bookmarked insights + RAG retrieval. Vector search by question, return top-k với confidence.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |
| P2 | Workspace có ≥ 5 insights bookmarked. |

## Test cases

### TC-1 · Render search bar

**Expected**
- ✅ PageHeader "Kiến thức tích luỹ".
- ✅ Search input lớn ở giữa.
- ✅ Suggestions chip dưới: "Doanh thu tháng này", "Top khách hàng rời bỏ", "Sản phẩm bán chạy".

### TC-2 · Submit search

**Steps**
1. Type "Vì sao doanh thu giảm?" → Enter.

**Expected**
- ✅ `GET /insights/knowledge-base?q=...` 200.
- ✅ Results list: mỗi item title + snippet + confidence + nguồn insight ID.

### TC-3 · Click result

**Expected**
- ✅ Navigate `/p2/insights/{id}` (detail).

### TC-4 · Empty results

**Expected**
- ✅ "Không tìm thấy insight nào khớp." + CTA generate mới.

### TC-5 · Loading

**Expected**
- ✅ Skeleton 3 result cards.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Phase 2 — vector search engine cần Pinecone/Qdrant. | Phase 1 fallback BM25. |

## Related screens

- **UAT-EN-014** list.
