"""
ML analysis engine — clustering, churn (RFM classification), regression.
Falls back gracefully to statistical methods when data is insufficient.
"""
import warnings
from typing import Any

import numpy as np
import pandas as pd
import structlog

log = structlog.get_logger()


class MLEngine:
    def __init__(self, mode: str):
        self.mode = mode

    async def run(self, template_id: str, df: pd.DataFrame, config: dict) -> list[dict]:
        dispatch = {
            "clustering":     self._clustering,
            "churn":          self._churn,
            "regression":     self._regression,
        }
        fn = dispatch.get(template_id)
        if fn is None:
            raise ValueError(f"MLEngine({self.mode}) cannot handle: {template_id}")
        return fn(df, config)

    # ── clustering (K-means) ───────────────────────────────────────────────────
    def _clustering(self, df: pd.DataFrame, config: dict) -> list[dict]:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import silhouette_score

        num_cols = df.select_dtypes(include="number").columns.tolist()
        if len(num_cols) < 2:
            raise ValueError("Cần ≥2 cột số để phân nhóm.")

        X = df[num_cols].dropna()
        if len(X) < 10:
            raise ValueError("Cần ít nhất 10 hàng để phân nhóm.")

        k = config.get("k", min(4, len(X) // 10))
        k = max(2, min(k, 8))  # Clamp 2-8

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            km = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = km.fit_predict(X_scaled)

        sil = round(float(silhouette_score(X_scaled, labels)), 3) if k > 1 else None

        result_df = X.copy()
        result_df["cluster"] = labels.astype(str)

        cluster_summary = (
            result_df.groupby("cluster")[num_cols]
            .mean()
            .round(2)
            .reset_index()
        )
        cluster_counts = (
            result_df["cluster"].value_counts().rename("count").reset_index()
        )
        cluster_counts.columns = ["cluster", "count"]

        # Scatter for first 2 numeric cols
        scatter_data = result_df.rename(
            columns={num_cols[0]: "x", num_cols[1]: "y"}
        )[["x", "y", "cluster"]].head(500).to_dict("records")

        return [
            {
                "id": "cluster_scatter",
                "type": "chart",
                "title": f"Phân nhóm ({k} nhóm)",
                "data_shape": "scatter_2d",
                "default_chart": "scatter",
                "data": scatter_data,
            },
            {
                "id": "cluster_summary",
                "type": "chart",
                "title": "Đặc điểm từng nhóm",
                "data_shape": "multi_dimensional",
                "default_chart": "radar",
                "data": cluster_summary.to_dict("records"),
            },
            {
                "id": "cluster_sizes",
                "type": "chart",
                "title": "Kích thước nhóm",
                "data_shape": "categorical_count",
                "default_chart": "donut",
                "data": cluster_counts.to_dict("records"),
            },
            {
                "id": "cluster_stats",
                "type": "stats_card",
                "title": "K-Means",
                "data": {
                    "k": k,
                    "silhouette_score": sil,
                    "rows_clustered": len(X),
                },
            },
        ]

    # ── churn (RFM + classifier) ───────────────────────────────────────────────
    def _churn(self, df: pd.DataFrame, config: dict) -> list[dict]:
        date_col = _find_date_col(df)
        cust_col = _find_col_by_name(df, ["customer_id", "customer_external_id",
                                          "ma_khach", "khach_hang_id"])
        val_col  = _find_col_by_name(df, ["amount", "so_tien", "revenue",
                                          "doanh_thu", "value"])
        if not date_col or not cust_col:
            raise ValueError("Cần cột customer_id và date cho Churn RFM.")

        df2 = df.copy()
        df2[date_col] = pd.to_datetime(df2[date_col], errors="coerce")
        df2 = df2.dropna(subset=[date_col])
        as_of = df2[date_col].max()

        # RFM computation
        rfm = df2.groupby(cust_col).agg(
            recency=(date_col, lambda x: (as_of - x.max()).days),
            frequency=(date_col, "count"),
            **({"monetary": (val_col, "sum")} if val_col else {}),
        ).reset_index()

        # RFM score (1-5 per dimension)
        for dim in ["recency", "frequency"] + (["monetary"] if val_col else []):
            labels = [5, 4, 3, 2, 1] if dim == "recency" else [1, 2, 3, 4, 5]
            try:
                scores = pd.qcut(rfm[dim], q=5, labels=labels, duplicates="drop")
            except ValueError:
                # Fewer than 5 unique values — assign neutral mid-score
                scores = pd.Series(3.0, index=rfm.index)
            rfm[f"{dim}_score"] = scores.astype(float).fillna(3)

        score_cols = [c for c in rfm.columns if c.endswith("_score")]
        rfm["rfm_total"] = rfm[score_cols].sum(axis=1)

        # Segment
        max_score = 5 * len(score_cols)
        rfm["churn_risk"] = rfm["rfm_total"].apply(
            lambda s: "Cao" if s <= max_score * 0.4
            else ("Trung bình" if s <= max_score * 0.65 else "Thấp")
        )

        risk_counts = rfm["churn_risk"].value_counts().rename("count").reset_index()
        risk_counts.columns = ["risk_level", "count"]

        at_risk = rfm[rfm["churn_risk"] == "Cao"].nlargest(
            20, "recency"
        )[[cust_col, "recency", "frequency"] + (["monetary"] if val_col else []) + ["churn_risk"]]

        return [
            {
                "id": "risk_distribution",
                "type": "chart",
                "title": "Phân bố nguy cơ churn",
                "data_shape": "categorical_count",
                "default_chart": "donut",
                "data": risk_counts.to_dict("records"),
            },
            {
                "id": "at_risk_customers",
                "type": "chart",
                "title": "Khách hàng nguy cơ cao",
                "data_shape": "ranked_list",
                "default_chart": "horizontal_bar",
                "data": at_risk.to_dict("records"),
            },
            {
                "id": "rfm_scatter",
                "type": "chart",
                "title": "RFM — Recency vs Frequency",
                "data_shape": "scatter_2d",
                "default_chart": "scatter",
                "data": rfm[["recency", "frequency", "churn_risk"]].rename(
                    columns={"recency": "x", "frequency": "y",
                             "churn_risk": "cluster"}
                ).head(500).to_dict("records"),
            },
            {
                "id": "churn_summary",
                "type": "stats_card",
                "title": "Churn RFM",
                "data": {
                    "total_customers": len(rfm),
                    "high_risk": int((rfm["churn_risk"] == "Cao").sum()),
                    "medium_risk": int((rfm["churn_risk"] == "Trung bình").sum()),
                    "low_risk": int((rfm["churn_risk"] == "Thấp").sum()),
                    "as_of_date": str(as_of.date()),
                    "method": "RFM heuristic",
                },
            },
        ]

    # ── regression ────────────────────────────────────────────────────────────
    def _regression(self, df: pd.DataFrame, config: dict) -> list[dict]:
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.linear_model import LinearRegression
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import r2_score, mean_absolute_error
        from sklearn.preprocessing import StandardScaler

        num_cols = df.select_dtypes(include="number").columns.tolist()
        if len(num_cols) < 2:
            raise ValueError("Cần ≥2 cột số cho hồi quy.")

        target = config.get("target_col") or num_cols[-1]
        features = [c for c in num_cols if c != target]

        X = df[features].dropna()
        y = df.loc[X.index, target].dropna()
        X = X.loc[y.index]

        if len(X) < 20:
            raise ValueError("Cần ít nhất 20 hàng cho hồi quy.")

        use_gbm = len(X) >= 200
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s  = scaler.transform(X_test)

        if use_gbm:
            model = GradientBoostingRegressor(n_estimators=100, random_state=42)
            model.fit(X_train, y_train)
            preds = model.predict(X_test)
            importances = model.feature_importances_
        else:
            model = LinearRegression()
            model.fit(X_train_s, y_train)
            preds = model.predict(X_test_s)
            importances = np.abs(model.coef_) / (np.abs(model.coef_).sum() + 1e-9)

        r2  = round(float(r2_score(y_test, preds)), 4)
        mae = round(float(mean_absolute_error(y_test, preds)), 2)

        feature_imp = sorted(
            [{"feature": f, "importance": round(float(imp), 4)}
             for f, imp in zip(features, importances)],
            key=lambda x: x["importance"], reverse=True,
        )

        actual_vs_pred = [
            {"actual": round(float(a), 2), "predicted": round(float(p), 2)}
            for a, p in zip(y_test[:100], preds[:100])
        ]

        return [
            {
                "id": "feature_importance",
                "type": "chart",
                "title": "Tầm quan trọng biến",
                "data_shape": "ranked_list",
                "default_chart": "horizontal_bar",
                "data": feature_imp,
            },
            {
                "id": "actual_vs_predicted",
                "type": "chart",
                "title": "Thực tế vs Dự đoán",
                "data_shape": "scatter_2d",
                "default_chart": "scatter",
                "data": actual_vs_pred,
            },
            {
                "id": "regression_summary",
                "type": "stats_card",
                "title": "Hồi quy",
                "data": {
                    "target": target,
                    "features": features,
                    "r2_score": r2,
                    "mae": mae,
                    "model": "GradientBoosting" if use_gbm else "LinearRegression",
                    "train_size": len(X_train),
                    "test_size": len(X_test),
                },
            },
        ]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_date_col(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if df[col].dtype.name.startswith("datetime64"):
            return col
    candidates = ["date", "ngay", "ngày", "time", "created_at",
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
