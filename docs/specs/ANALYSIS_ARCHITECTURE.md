# ANALYSIS ARCHITECTURE — General-Purpose Templates

> Kiến trúc quyết định **template nào** được đề xuất cho data upload.
> Key insight: Templates không hardcode theo ngành — chúng **detect từ cột canonical + data profile**.

---

## 1. Mô hình quyết định 4 tầng

```
User data upload → Silver layer complete
        │
        ▼
Q1: Templates nào eligible?
    (check canonical columns + min_rows + data types)
        │
        ▼
Q2: Config defaults?
    (không có industry preset — Kaori agnostic)
    (defaults = min thresholds, recommended features)
        │
        ▼
Q3: Model router — chọn algorithm tốt nhất
    (statistical vs ML vs LLM, based on data volume)
        │
        ▼
Q4: Preflight validation — 6 layers
    (GO / NO-GO, margin to threshold)
        │
        ▼
User chọn templates (multi-select) → POST /analyze
```

---

## 2. Registry — 10 General-Purpose Templates

### Template: `summary_stats`
```python
AnalysisTemplate(
    id='summary_stats',
    name='Thống kê tổng quan',
    description='Phân phối, trung bình, ngoại lệ cho cột số',
    required_canonical=['*any_numeric*'],
    min_rows=5,
    model_router=lambda vol, tier: 'statistical',  # always
    output_blocks=['mean_table', 'distribution_histogram', 'outlier_list'],
)
```

### Template: `time_series`
```python
AnalysisTemplate(
    id='time_series',
    name='Chuỗi thời gian',
    description='Xu hướng, seasonality, forecast 30 ngày',
    required_canonical=['date', '*any_numeric*'],
    min_rows=14,
    model_router=lambda vol, tier: 'prophet' if vol >= 365 else 'linear_trend',
    output_blocks=['trend_line', 'seasonality_chart', 'forecast_line', 'mom_delta'],
)
```

### Template: `distribution`
```python
AnalysisTemplate(
    id='distribution',
    name='Phân phối & ngoại lệ',
    description='Histogram, box plot, outlier detection (IQR)',
    required_canonical=['*any_numeric*'],
    min_rows=30,
    output_blocks=['histogram', 'box_plot', 'outlier_table'],
)
```

### Template: `correlation`
```python
AnalysisTemplate(
    id='correlation',
    name='Tương quan',
    description='Ma trận tương quan Pearson + scatter giữa 2 biến',
    required_canonical=['*min_2_numeric*'],
    min_rows=20,
    output_blocks=['correlation_matrix_heatmap', 'scatter_2d', 'top_pairs_list'],
)
```

### Template: `clustering`
```python
AnalysisTemplate(
    id='clustering',
    name='Phân nhóm (Clustering)',
    description='K-means phân nhóm khách hàng / sản phẩm',
    required_canonical=['*min_3_numeric*'],
    min_rows=50,
    model_router=lambda vol, tier: 'kmeans',
    output_blocks=['cluster_scatter', 'cluster_summary_table', 'cluster_profiles'],
)
```

### Template: `cohort`
```python
AnalysisTemplate(
    id='cohort',
    name='Cohort Retention',
    description='Tỷ lệ giữ chân khách theo tháng đăng ký',
    required_canonical=['customer_external_id', 'date'],
    min_rows=100,
    output_blocks=['cohort_heatmap', 'retention_rate_line', 'cohort_summary'],
)
```

### Template: `churn`
```python
AnalysisTemplate(
    id='churn',
    name='Dự đoán Churn (RFM)',
    description='Phân loại khách có nguy cơ rời bỏ dựa trên RFM',
    required_canonical=['customer_external_id', 'date'],
    min_rows=100,
    model_router=lambda vol, tier: 'gradient_boosting' if vol >= 500 else 'rfm_heuristic',
    output_blocks=['risk_histogram', 'customer_risk_list', 'rfm_scatter', 'retention_recommendations'],
)
```

### Template: `anomaly`
```python
AnalysisTemplate(
    id='anomaly',
    name='Phát hiện bất thường',
    description='Detect spike/drop bất thường trong chuỗi số theo thời gian',
    required_canonical=['*any_numeric*', 'date'],
    min_rows=30,
    model_router=lambda vol, tier: 'isolation_forest' if vol >= 200 else 'iqr_zscore',
    output_blocks=['anomaly_timeline', 'anomaly_table', 'severity_distribution'],
)
```

### Template: `regression`
```python
AnalysisTemplate(
    id='regression',
    name='Dự đoán / Hồi quy',
    description='Dự đoán 1 biến target từ nhiều features',
    required_canonical=['*min_3_numeric*'],
    min_rows=50,
    model_router=lambda vol, tier: 'linear' if vol < 200 else 'random_forest',
    output_blocks=['feature_importance', 'actual_vs_predicted', 'residual_plot', 'r2_score_card'],
)
```

### Template: `bank_classify`
```python
AnalysisTemplate(
    id='bank_classify',
    name='Phân loại giao dịch ngân hàng',
    description='Classify giao dịch thành các nhóm chi tiêu (dùng config/bank_rules.json)',
    required_canonical=['description', 'amount'],
    min_rows=10,
    model_router=lambda vol, tier: 'rule_based',   # uses config/bank_rules.json
    output_blocks=['category_breakdown_donut', 'top_expenses_bar', 'monthly_trend', 'unclassified_list'],
)
```

---

## 3. Template Eligibility Check

```python
def get_eligible_templates(
    canonical_output: CanonicalLayerResult,
    tier: str,
) -> list[TemplateEligibilityResult]:
    results = []
    for template in ANALYSIS_TEMPLATE_REGISTRY.values():
        # Check required columns
        has_required = template.check_required_columns(canonical_output.canonical_column_names)
        # Check row count
        rows_ok = canonical_output.total_rows >= template.min_rows
        # Check tier
        tier_ok = template.allowed_tiers is None or tier in template.allowed_tiers

        results.append(TemplateEligibilityResult(
            template=template,
            eligible=has_required and rows_ok and tier_ok,
            missing_canonical=template.get_missing(canonical_output),
            rows_delta=canonical_output.total_rows - template.min_rows,
            # Show margin: "99 rows, need 100 — 1 below threshold"
        ))
    return results
```

---

## 4. Preflight Validation — 6 Layers

```
Layer 1 — Existence
    required canonical columns hiện diện?
    ngày thiếu quá nhiều (null_rate > 80%) → warning

Layer 2 — Data Volume
    row_count ≥ template.min_rows?
    Margin: rows_delta → hiện cho user thấy còn thiếu bao nhiêu

Layer 3 — Data Quality
    avg null_rate < 0.40?
    type_consistency ≥ 0.85?
    quality_score ≥ 0.60?

Layer 4 — Schema Integrity
    Date column có liên tục? (no huge gap)
    Numeric column > 90% parseable?
    Join key consistent (nếu multi-sheet)?

Layer 5 — Statistical Power
    Đủ variance (std > 0)?
    Đủ distinct values cho categorical columns?
    (cohort/churn) Có ≥ 2 time periods?

Layer 6 — Cost / Tier Check
    Model phức tạp (gradient_boosting) → tier Enterprise+
    External LLM calls → consent_external = True required
```

Return:
```python
class PreflightResult:
    go: bool
    layers: list[LayerResult]
    blocking_issues: list[str]   # User-readable tiếng Việt
    warnings: list[str]
    margin_messages: dict[str, str]  # {"row_count": "99 hàng, cần 100 — thiếu 1"}
```

---

## 5. Feature Engineering Blocks (reusable)

```python
class RecencyFeature:
    """Ngày cuối cùng khách tương tác — số ngày từ hôm nay."""
    canonical_required = ['customer_external_id', 'date']

    def compute(self, df: pd.DataFrame) -> pd.Series:
        last_visit = df.groupby('customer_external_id')['date'].max()
        return (df.attrs['as_of_date'] - last_visit).dt.days

class FrequencyFeature:
    """Số lần giao dịch trong window_days."""
    canonical_required = ['customer_external_id', 'date']

    def compute(self, df: pd.DataFrame, window_days=90) -> pd.Series:
        cutoff = df.attrs['as_of_date'] - pd.Timedelta(days=window_days)
        recent = df[df['date'] >= cutoff]
        return recent.groupby('customer_external_id').size()

class MonetaryFeature:
    """Tổng giá trị giao dịch."""
    canonical_required = ['customer_external_id', 'amount']

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df.groupby('customer_external_id')['amount'].sum()

class TrendFeature:
    """Xu hướng tăng/giảm 3 tháng gần nhất (positive = tăng, negative = giảm)."""
    canonical_required = ['date', 'amount']

    def compute(self, df: pd.DataFrame) -> float:
        monthly = df.resample('ME', on='date')['amount'].sum()
        return np.polyfit(range(len(monthly)), monthly.values, 1)[0]  # slope
```

---

## 6. Output Composers (per template)

```python
class SummaryStatsComposer:
    """Sinh output JSON cho template summary_stats."""

    def compose(self, analysis_result: AnalysisResult) -> dict:
        return {
            'blocks': [
                {
                    'type': 'stats_table',
                    'data_shape': 'ranked_list',
                    'default_chart': 'horizontal_bar',
                    'data': analysis_result.describe_df.to_dict('records'),
                },
                {
                    'type': 'distribution_histogram',
                    'data_shape': 'categorical_count',
                    'default_chart': 'bar',
                    'data': analysis_result.histogram_buckets,
                },
                {
                    'type': 'outlier_list',
                    'data_shape': 'ranked_list',
                    'default_chart': 'horizontal_bar',
                    'data': analysis_result.outliers,
                },
                {
                    'type': 'ai_narrative',
                    'text': analysis_result.narrative_vi,
                    'provider': analysis_result.llm_provider,  # 'qwen' / 'claude'
                },
            ]
        }
```

---

## 7. Multi-template run (Silver data reuse)

```python
# POST /api/v1/analyze
{
    "run_id": "uuid",
    "templates": ["time_series", "distribution", "anomaly"],
    "config": {
        "time_series": {"forecast_days": 30},
        "anomaly": {"sensitivity": 0.95}
    }
}
```

- Silver data read once, shared across all templates
- Kafka: `pipeline.silver.complete` → ai-orchestrator spawns 1 task per template
- Results gộp vào tab-based dashboard

---

## 8. Analysis Persistence

```sql
-- analysis_runs: mỗi lần user bấm "Phân tích"
SELECT * FROM analysis_runs
WHERE enterprise_id = $1  -- K-1
ORDER BY created_at DESC;

-- Bookmarkable URL: /analytics/time_series?run_id={uuid}
-- Tab "Tổng quan" → cross-template KPIs
-- Tab "Chuỗi thời gian" → time_series tab results
```

---

## 9. Dashboard State Machine (5 states)

```typescript
type DashboardState =
  | 'no_data'           // chưa upload file nào
  | 'pipeline_running'  // file đang xử lý
  | 'pending_review'    // cần user review schema / rules
  | 'analysis_ready'    // Silver ready, có thể chạy analysis
  | 'results_ready'     // analysis xong, có kết quả
```

Frontend check state mỗi 5s (polling) hoặc SSE khi `pipeline.analysis.complete` Kafka event đến.

---

## 10. Implementation Status (2026-04-22)

| Thành phần | Status | File |
|---|---|---|
| Template registry (10 templates) | ✅ Done | `ai-orchestrator/analytics/template_registry.py` |
| Eligibility check logic | ✅ Skeleton | `ai-orchestrator/analytics/template_registry.py` |
| **Statistical analysis functions** | ⚠️ Pending | `ai-orchestrator/analytics/engines/statistical.py` |
| **ML analysis (clustering, churn RFM)** | ⚠️ Pending | `ai-orchestrator/analytics/engines/ml.py` |
| **Bank classify (wiring to bank_rules.json)** | ⚠️ Pending | wrapper around `etl/classify_bank.py` |
| **Preflight 6-layer validation** | ⚠️ Pending | `ai-orchestrator/analytics/preflight.py` |
| **Feature engineering blocks** | ⚠️ Pending | `ai-orchestrator/analytics/features/` |
| **Output composers** | ⚠️ Pending | `ai-orchestrator/analytics/composers/` |
| **Kafka consumer (silver.complete → run analysis)** | ⚠️ Pending | `ai-orchestrator/consumers/pipeline_consumer.py` |
| ai-orchestrator `main.py` entry point | ⚠️ Pending | `ai-orchestrator/main.py` |
