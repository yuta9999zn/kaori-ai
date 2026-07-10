"""
General-purpose analysis template registry.
Templates are auto-selected based on detected column types.

Unlike Kise AI's hardcoded retail templates,
Kaori templates adapt to whatever data structure the user uploads.
"""
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class AnalysisTemplate:
    template_id: str
    display_name: str
    description: str
    required_types: list[str]          # Required canonical data types
    required_purposes: list[str]       # Required sheet purposes (empty = any)
    min_rows: int                      # Minimum rows needed
    optional_types: list[str] = field(default_factory=list)
    model_hint: str = "llm_narrative"  # "statistical", "ml_clustering", etc.
    # Default semantics: ``required_types`` is "any of" (one match is enough).
    # Some templates need *all* listed types simultaneously (e.g.
    # bank_classify needs both currency AND text). Setting this flag flips
    # the eligibility check from ``any`` to ``all``.
    require_all_types: bool = False

    def is_eligible(self, detected_types: set[str], detected_purpose: str | None, row_count: int) -> bool:
        if row_count < self.min_rows:
            return False
        if self.required_types:
            if self.require_all_types:
                if not all(t in detected_types for t in self.required_types):
                    return False
            else:
                if not any(t in detected_types for t in self.required_types):
                    return False
        if self.required_purposes and detected_purpose not in self.required_purposes:
            return False
        return True


TEMPLATE_REGISTRY: list[AnalysisTemplate] = [
    AnalysisTemplate(
        template_id="summary_stats",
        display_name="Thống kê tổng quan",
        description="Mean, median, std, min/max, quartiles cho tất cả cột số",
        required_types=["integer", "decimal", "currency"],
        required_purposes=[],
        min_rows=5,
        model_hint="statistical",
    ),
    AnalysisTemplate(
        template_id="time_series",
        display_name="Chuỗi thời gian",
        description="Xu hướng, mùa vụ, dự báo — cần cột ngày + số",
        required_types=["date"],
        optional_types=["integer", "decimal", "currency"],
        required_purposes=[],
        min_rows=14,
        model_hint="statistical",
    ),
    AnalysisTemplate(
        template_id="distribution",
        display_name="Phân phối dữ liệu",
        description="Histogram, outlier detection, skewness, kurtosis",
        required_types=["integer", "decimal", "currency"],
        required_purposes=[],
        min_rows=30,
        model_hint="statistical",
    ),
    AnalysisTemplate(
        template_id="correlation",
        display_name="Ma trận tương quan",
        description="Tương quan Pearson/Spearman giữa các biến số — cần ≥2 cột số",
        required_types=["integer", "decimal", "currency"],
        required_purposes=[],
        min_rows=20,
        model_hint="statistical",
    ),
    AnalysisTemplate(
        template_id="clustering",
        display_name="Phân nhóm (Clustering)",
        description="K-means segmentation, silhouette score — cần ≥3 cột số",
        required_types=["integer", "decimal", "currency"],
        required_purposes=[],
        min_rows=50,
        model_hint="ml_clustering",
    ),
    AnalysisTemplate(
        template_id="cohort",
        display_name="Cohort Retention",
        description="Bảng giữ chân khách hàng theo tháng",
        required_types=["date"],
        required_purposes=["customer_master", "transaction_list"],
        min_rows=100,
        model_hint="statistical",
    ),
    AnalysisTemplate(
        template_id="churn",
        display_name="Nguy cơ rời bỏ (Churn)",
        description="RFM + dự đoán churn — cần customer_id + date + value",
        required_types=["date"],
        required_purposes=["customer_master", "transaction_list"],
        min_rows=100,
        model_hint="ml_classification",
    ),
    AnalysisTemplate(
        template_id="anomaly",
        display_name="Phát hiện bất thường",
        description="IQR + Z-score outliers, time-series anomaly detection",
        required_types=["integer", "decimal", "currency", "date"],
        required_purposes=[],
        min_rows=30,
        model_hint="statistical",
    ),
    AnalysisTemplate(
        template_id="regression",
        display_name="Hồi quy dự đoán",
        description="Linear/gradient boosting regression — cần target column + features",
        required_types=["integer", "decimal", "currency"],
        required_purposes=[],
        min_rows=50,
        model_hint="ml_regression",
    ),
    AnalysisTemplate(
        template_id="bank_classify",
        display_name="Phân loại giao dịch ngân hàng",
        description="Phân loại sao kê theo danh mục chi tiêu",
        # Both types are mandatory: currency for the amount column, text for
        # the description column (the thing being classified). Without text,
        # there is nothing to assign to a category.
        required_types=["currency", "text"],
        require_all_types=True,
        required_purposes=["transaction_list", "bank_statement"],
        min_rows=10,
        model_hint="statistical",
    ),
]


def profile_from_df(df) -> tuple[set[str], str | None, int]:
    """Derive (detected_types, detected_purpose, row_count) from a loaded
    Silver DataFrame so /analytics/templates?run_id= can compute eligibility
    server-side (the FE picker has no profile of its own — incident
    2026-07-10, every template showed "chưa đủ điều kiện" on clean data).

    Canonical types mirror the registry vocabulary: datetime64 → "date",
    integer → "integer", float → "decimal", anything else → "text".
    Purpose is a shape heuristic, not Stage-2 semantics: a date axis plus a
    numeric measure is the transaction-list shape the churn/cohort
    templates ask for; without a date axis we claim nothing.
    """
    import pandas as pd

    types: set[str] = set()
    for col in df.columns:
        dtype = df[col].dtype
        if pd.api.types.is_datetime64_any_dtype(dtype):
            types.add("date")
        elif pd.api.types.is_integer_dtype(dtype):
            types.add("integer")
        elif pd.api.types.is_float_dtype(dtype):
            types.add("decimal")
        else:
            types.add("text")

    has_numeric = bool(types & {"integer", "decimal", "currency"})
    purpose = "transaction_list" if ("date" in types and has_numeric) else None
    return types, purpose, len(df)


def get_eligible_templates(
    detected_types: set[str],
    detected_purpose: str | None,
    row_count: int,
) -> list[dict]:
    """Return list of eligible templates with eligibility reason."""
    return [
        {
            "template_id": t.template_id,
            "display_name": t.display_name,
            "description": t.description,
            "eligible": t.is_eligible(detected_types, detected_purpose, row_count),
            "min_rows": t.min_rows,
            "model_hint": t.model_hint,
        }
        for t in TEMPLATE_REGISTRY
    ]
