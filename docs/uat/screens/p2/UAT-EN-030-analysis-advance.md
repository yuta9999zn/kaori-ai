# UAT-EN-030 · Analysis Advanced

| | |
|---|---|
| **Mã test** | UAT-EN-030 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/analysis/advance` |
| **Source FE** | `frontend/components/p2/templates/38-analysis-advance.tsx` |
| **Endpoint** | `POST /api/v1/analysis/advance` |
| **Auth required** | Có |
| **Phase** | Phase 2 🔵 |

---

## Mục tiêu test

Advanced analysis: clustering (k-means, DBSCAN), classification (logistic), anomaly detection (z-score, isolation forest).

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login. |
| P2 | Workspace có dataset với ≥ 100 rows + numeric cols. |

## Test cases

### TC-1 · Render method chooser

**Expected**
- ✅ Tabs: Clustering / Classification / Anomaly.

### TC-2 · K-means clustering

**Steps**
1. Tab Clustering → chọn k=3 + features.

**Expected**
- ✅ Submit → cluster labels + 2D scatter (PCA reduced).
- ✅ Silhouette score hiển thị.

### TC-3 · Logistic classification

**Steps**
1. Tab Classification → target binary + features.

**Expected**
- ✅ Accuracy / Precision / Recall / F1 + confusion matrix.

### TC-4 · Anomaly detection

**Expected**
- ✅ Method z-score / iforest → list outliers + score histogram.

### TC-5 · Loading + error

**Expected**
- ✅ Standard.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Advanced methods Phase 2 — BE chưa fully wired. | Phase 1 placeholder. |

## Related screens

- **UAT-EN-029** intermediate.
