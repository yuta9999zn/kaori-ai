"""
Statistical analysis engine — summary_stats, time_series, distribution,
correlation, anomaly. No ML dependencies.
"""
import warnings
from typing import Any

import numpy as np
import pandas as pd
import structlog

log = structlog.get_logger()


class StatisticalEngine:
    async def run(self, template_id: str, df: pd.DataFrame, config: dict) -> list[dict]:
        dispatch = {
            "summary_stats":  self._summary_stats,
            "time_series":    self._time_series,
            "distribution":   self._distribution,
            "correlation":    self._correlation,
            "anomaly":        self._anomaly,
            "cohort":         self._cohort,
            "bank_classify":  self._bank_classify,
        }
        fn = dispatch.get(template_id)
        if fn is None:
            raise ValueError(f"StatisticalEngine cannot handle: {template_id}")
        return fn(df, config)

    # ── summary_stats ──────────────────────────────────────────────────────────
    def _summary_stats(self, df: pd.DataFrame, config: dict) -> list[dict]:
        num_cols = df.select_dtypes(include="number").columns.tolist()
        if not num_cols:
            raise ValueError("Không tìm thấy cột số để thống kê.")

        desc = df[num_cols].describe().T.reset_index()
        desc.columns = ["column", "count", "mean", "std", "min",
                        "p25", "median", "p75", "max"]

        # Round floats for clean display
        for col in ["mean", "std", "min", "p25", "median", "p75", "max"]:
            desc[col] = desc[col].round(2)

        return [
            {
                "id": "stats_table",
                "type": "chart",
                "title": "Thống kê mô tả",
                "data_shape": "ranked_list",
                "default_chart": "horizontal_bar",
                "data": desc.to_dict("records"),
            },
            {
                "id": "summary_card",
                "type": "stats_card",
                "title": "Tổng quan",
                "data": {
                    "total_rows": len(df),
                    "numeric_columns": len(num_cols),
                    "null_rate": round(df.isnull().mean().mean(), 3),
                },
            },
        ]

    # ── time_series ────────────────────────────────────────────────────────────
    def _time_series(self, df: pd.DataFrame, config: dict) -> list[dict]:
        date_col = _find_col(df, "datetime64")
        num_cols = df.select_dtypes(include="number").columns.tolist()
        if date_col is None or not num_cols:
            raise ValueError("Cần cột ngày và ít nhất 1 cột số.")

        target = config.get("target_col") or num_cols[0]
        granularity = config.get("granularity", "monthly")
        freq = {"daily": "D", "weekly": "W", "monthly": "ME"}.get(granularity, "ME")

        df2 = df[[date_col, target]].dropna()
        df2[date_col] = pd.to_datetime(df2[date_col], errors="coerce")
        df2 = df2.dropna(subset=[date_col])
        ts = df2.set_index(date_col).resample(freq)[target].sum().reset_index()
        ts.columns = ["date", "value"]
        ts["date"] = ts["date"].dt.strftime("%Y-%m-%d")

        # MoM delta
        ts["delta_pct"] = ts["value"].pct_change().round(4)

        # Simple linear trend
        if len(ts) >= 2:
            x = np.arange(len(ts))
            slope = float(np.polyfit(x, ts["value"].values, 1)[0])
            trend_label = "tăng" if slope > 0 else "giảm"
        else:
            slope, trend_label = 0.0, "ổn định"

        forecast_days = config.get("forecast_days", 30)

        return [
            {
                "id": "trend_line",
                "type": "chart",
                "title": f"Xu hướng {target}",
                "data_shape": "time_series",
                "default_chart": "area",
                "data": ts.to_dict("records"),
            },
            {
                "id": "trend_summary",
                "type": "stats_card",
                "title": "Xu hướng",
                "data": {
                    "trend": trend_label,
                    "slope_per_period": round(slope, 2),
                    "periods_analysed": len(ts),
                    "forecast_horizon_days": forecast_days,
                },
            },
        ]

    # ── distribution ───────────────────────────────────────────────────────────
    def _distribution(self, df: pd.DataFrame, config: dict) -> list[dict]:
        num_cols = df.select_dtypes(include="number").columns.tolist()
        if not num_cols:
            raise ValueError("Không tìm thấy cột số.")

        target = config.get("target_col") or num_cols[0]
        series = df[target].dropna()

        # Histogram buckets (Freedman–Diaconis-ish: 10 bins default)
        n_bins = config.get("n_bins", 10)
        counts, edges = np.histogram(series, bins=n_bins)
        buckets = [
            {
                "label": f"{edges[i]:.1f}–{edges[i+1]:.1f}",
                "count": int(counts[i]),
            }
            for i in range(len(counts))
        ]

        # IQR outliers
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        outliers_df = df[
            (df[target] < q1 - 1.5 * iqr) | (df[target] > q3 + 1.5 * iqr)
        ][[target]].head(20)

        return [
            {
                "id": "histogram",
                "type": "chart",
                "title": f"Phân phối {target}",
                "data_shape": "categorical_count",
                "default_chart": "bar",
                "data": buckets,
            },
            {
                "id": "outliers",
                "type": "chart",
                "title": "Ngoại lệ (IQR)",
                "data_shape": "ranked_list",
                "default_chart": "horizontal_bar",
                "data": outliers_df.to_dict("records"),
            },
            {
                "id": "dist_summary",
                "type": "stats_card",
                "title": "Phân phối",
                "data": {
                    "q1": round(float(q1), 2),
                    "median": round(float(series.median()), 2),
                    "q3": round(float(q3), 2),
                    "outlier_count": len(outliers_df),
                },
            },
        ]

    # ── correlation ────────────────────────────────────────────────────────────
    def _correlation(self, df: pd.DataFrame, config: dict) -> list[dict]:
        num_cols = df.select_dtypes(include="number").columns.tolist()
        if len(num_cols) < 2:
            raise ValueError("Cần ít nhất 2 cột số để tính tương quan.")

        corr = df[num_cols].corr(method="pearson").round(3)

        # Flatten to list of pairs
        pairs = []
        seen = set()
        for c1 in num_cols:
            for c2 in num_cols:
                if c1 != c2 and (c2, c1) not in seen:
                    pairs.append({"col_a": c1, "col_b": c2,
                                  "pearson_r": corr.loc[c1, c2]})
                    seen.add((c1, c2))
        pairs.sort(key=lambda x: abs(x["pearson_r"]), reverse=True)

        # Scatter for top pair
        top = pairs[0] if pairs else None
        scatter_data = []
        if top:
            scatter_data = df[[top["col_a"], top["col_b"]]].dropna().rename(
                columns={top["col_a"]: "x", top["col_b"]: "y"}
            ).head(500).to_dict("records")

        # Heatmap matrix
        heatmap_data = [
            {"row": c1, "col": c2, "value": corr.loc[c1, c2]}
            for c1 in num_cols for c2 in num_cols
        ]

        return [
            {
                "id": "correlation_heatmap",
                "type": "chart",
                "title": "Ma trận tương quan",
                "data_shape": "scatter_2d",
                "default_chart": "heatmap",
                "data": heatmap_data,
                "meta": {"columns": num_cols},
            },
            {
                "id": "top_pairs",
                "type": "chart",
                "title": "Cặp tương quan mạnh nhất",
                "data_shape": "ranked_list",
                "default_chart": "horizontal_bar",
                "data": [
                    {"name": f"{p['col_a']} ↔ {p['col_b']}",
                     "value": p["pearson_r"]}
                    for p in pairs[:10]
                ],
            },
            {
                "id": "scatter_top",
                "type": "chart",
                "title": f"Scatter: {top['col_a']} vs {top['col_b']}" if top else "Scatter",
                "data_shape": "scatter_2d",
                "default_chart": "scatter",
                "data": scatter_data,
            },
        ]

    # ── anomaly ────────────────────────────────────────────────────────────────
    def _anomaly(self, df: pd.DataFrame, config: dict) -> list[dict]:
        num_cols = df.select_dtypes(include="number").columns.tolist()
        if not num_cols:
            raise ValueError("Không có cột số để detect bất thường.")

        target = config.get("target_col") or num_cols[0]
        series = df[target].dropna()

        # Z-score method
        mean, std = series.mean(), series.std()
        threshold = config.get("z_threshold", 2.5)
        z_scores = ((series - mean) / std).abs()
        anomaly_mask = z_scores > threshold

        anomalies = df[anomaly_mask][[target]].copy()
        anomalies["z_score"] = z_scores[anomaly_mask].round(2)
        anomalies["severity"] = anomalies["z_score"].apply(
            lambda z: "critical" if z > 4.0 else "high" if z > 3.0 else "medium"
        )

        date_col = _find_col(df, "datetime64")
        timeline_data = []
        if date_col:
            timeline_df = df[[date_col, target]].copy()
            timeline_df["is_anomaly"] = anomaly_mask.values
            timeline_df[date_col] = pd.to_datetime(
                timeline_df[date_col], errors="coerce"
            ).dt.strftime("%Y-%m-%d")
            timeline_data = timeline_df.dropna(
                subset=[date_col]
            ).to_dict("records")

        severity_counts = anomalies["severity"].value_counts().to_dict()

        return [
            {
                "id": "anomaly_table",
                "type": "chart",
                "title": f"Điểm bất thường — {target}",
                "data_shape": "ranked_list",
                "default_chart": "horizontal_bar",
                "data": anomalies.reset_index(drop=True).to_dict("records"),
            },
            {
                "id": "anomaly_timeline",
                "type": "chart",
                "title": "Timeline bất thường",
                "data_shape": "time_series",
                "default_chart": "line",
                "data": timeline_data,
            },
            {
                "id": "anomaly_summary",
                "type": "stats_card",
                "title": "Tổng kết bất thường",
                "data": {
                    "total_anomalies": int(anomaly_mask.sum()),
                    "critical": severity_counts.get("critical", 0),
                    "high": severity_counts.get("high", 0),
                    "medium": severity_counts.get("medium", 0),
                    "method": f"Z-score (threshold={threshold})",
                },
            },
        ]

    # ── cohort ─────────────────────────────────────────────────────────────────
    def _cohort(self, df: pd.DataFrame, config: dict) -> list[dict]:
        date_col = _find_col(df, "datetime64") or _find_date_col(df)
        cust_col = _find_col_by_name(df, ["customer_id", "customer_external_id",
                                          "khach_hang_id", "ma_khach"])
        if not date_col or not cust_col:
            raise ValueError("Cần cột customer_id và date cho Cohort.")

        df2 = df[[cust_col, date_col]].dropna().copy()
        df2[date_col] = pd.to_datetime(df2[date_col], errors="coerce")
        df2 = df2.dropna(subset=[date_col])
        df2["cohort_month"] = df2.groupby(cust_col)[date_col].transform("min").dt.to_period("M")
        df2["order_month"] = df2[date_col].dt.to_period("M")
        df2["period_num"] = (
            (df2["order_month"] - df2["cohort_month"]).apply(lambda x: x.n)
        )

        cohort_data = df2.groupby(["cohort_month", "period_num"])[cust_col].nunique()
        cohort_sizes = cohort_data.xs(0, level="period_num")
        retention = cohort_data.div(cohort_sizes, level="cohort_month").round(3)

        retention_list = [
            {"cohort": str(cohort), "period": int(period), "retention": float(val)}
            for (cohort, period), val in retention.items()
        ]

        return [
            {
                "id": "cohort_heatmap",
                "type": "chart",
                "title": "Cohort Retention",
                "data_shape": "scatter_2d",
                "default_chart": "heatmap",
                "data": retention_list,
                "meta": {"x_axis": "period", "y_axis": "cohort", "value": "retention"},
            },
            {
                "id": "cohort_summary",
                "type": "stats_card",
                "title": "Tổng kết Cohort",
                "data": {
                    "cohorts_analysed": len(cohort_sizes),
                    "avg_month1_retention": round(
                        float(retention.xs(1, level="period_num").mean()), 3
                    ) if 1 in retention.index.get_level_values("period_num") else None,
                },
            },
        ]

    # ── bank_classify ──────────────────────────────────────────────────────────
    def _bank_classify(self, df: pd.DataFrame, config: dict) -> list[dict]:
        import json
        import pathlib

        rules_path = pathlib.Path("/app/config/bank_rules.json")
        if not rules_path.exists():
            raise ValueError("config/bank_rules.json không tìm thấy.")

        with open(rules_path) as f:
            rules: dict = json.load(f)

        desc_col = _find_col_by_name(df, ["description", "mo_ta", "noi_dung",
                                          "narration", "detail"])
        amt_col  = _find_col_by_name(df, ["amount", "so_tien", "credit", "debit"])
        if not desc_col or not amt_col:
            raise ValueError("Cần cột mô tả và số tiền.")

        def classify(row):
            desc = str(row[desc_col]).lower()
            for cat, cfg in rules.items():
                for kw in cfg.get("keywords", []):
                    if kw.lower() in desc:
                        return cat
            return "KHÁC"

        df2 = df.copy()
        df2["category"] = df2.apply(classify, axis=1)
        df2[amt_col] = pd.to_numeric(df2[amt_col], errors="coerce").fillna(0)

        cat_summary = (
            df2.groupby("category")[amt_col]
            .agg(["sum", "count"])
            .rename(columns={"sum": "total_amount", "count": "count"})
            .reset_index()
        )
        cat_summary["total_amount"] = cat_summary["total_amount"].round(0)
        cat_summary.sort_values("total_amount", ascending=False, inplace=True)

        unclassified = df2[df2["category"] == "KHÁC"][[desc_col, amt_col]].head(20)

        return [
            {
                "id": "category_breakdown",
                "type": "chart",
                "title": "Phân loại giao dịch",
                "data_shape": "percentage_breakdown",
                "default_chart": "donut",
                "data": cat_summary.to_dict("records"),
            },
            {
                "id": "unclassified_list",
                "type": "chart",
                "title": "Chưa phân loại",
                "data_shape": "ranked_list",
                "default_chart": "horizontal_bar",
                "data": unclassified.to_dict("records"),
            },
            {
                "id": "bank_summary",
                "type": "stats_card",
                "title": "Tổng kết",
                "data": {
                    "total_transactions": len(df2),
                    "classified": int((df2["category"] != "KHÁC").sum()),
                    "unclassified": int((df2["category"] == "KHÁC").sum()),
                    "categories": len(cat_summary),
                },
            },
        ]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_col(df: pd.DataFrame, dtype_prefix: str) -> str | None:
    for col in df.columns:
        if df[col].dtype.name.startswith(dtype_prefix):
            return col
    return None


def _find_date_col(df: pd.DataFrame) -> str | None:
    candidates = ["date", "ngay", "ngày", "time", "thoi_gian", "created_at",
                  "order_date", "transaction_date"]
    for col in df.columns:
        if col.lower() in candidates:
            return col
    return None


def _find_col_by_name(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in df.columns:
        if col.lower() in [c.lower() for c in candidates]:
            return col
    return None
