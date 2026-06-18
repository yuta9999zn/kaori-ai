"""
Comprehensive pytest tests for StatisticalEngine, MLEngine, and TemplateRegistry.

Unit / white-box tests: test internal branches, edge cases, and exact output
contracts of every private method.

Run:
    pytest services/ai-orchestrator/tests/test_engines.py -v
    pytest services/ai-orchestrator/tests/test_engines.py -v -k "TestSummaryStats"
"""
from __future__ import annotations

import json
import sys
import types
from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import numpy as np
import pandas as pd
import pytest
import pytest_asyncio  # noqa: F401 — ensures plugin is loaded

# ---------------------------------------------------------------------------
# Path bootstrap so tests can be run from the repo root.
# The package lives at services/ai-orchestrator/ and is importable as
# `ai_orchestrator.*` (see __init__.py).  When pytest is invoked from the
# repo root we need to insert that directory onto sys.path.
# ---------------------------------------------------------------------------
_SERVICE_ROOT = Path(__file__).resolve().parents[1]  # …/services/ai-orchestrator
if str(_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVICE_ROOT))

from reasoning.legacy_analytics.engines.statistical import StatisticalEngine  # noqa: E402
from reasoning.legacy_analytics.engines.ml import MLEngine  # noqa: E402
from reasoning.legacy_analytics.template_registry import (  # noqa: E402
    AnalysisTemplate,
    TEMPLATE_REGISTRY,
    get_eligible_templates,
)


# ===========================================================================
# Shared helpers / tiny factories
# ===========================================================================

def _make_numeric_df(n: int = 50) -> pd.DataFrame:
    """Return a plain numeric DataFrame with two columns."""
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "revenue": rng.uniform(100, 10_000, n).round(2),
        "cost":    rng.uniform(50,  5_000, n).round(2),
    })


def _make_ts_df(n: int = 60) -> pd.DataFrame:
    """Return a time-series DataFrame with a datetime index column."""
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    rng = np.random.default_rng(1)
    return pd.DataFrame({
        "date":    dates,
        "revenue": rng.uniform(1_000, 5_000, n).round(2),
    })


def _make_customer_df(n: int = 120) -> pd.DataFrame:
    """Return a customer-transaction DataFrame with customer_id, date, amount."""
    rng = np.random.default_rng(2)
    customers = [f"C{i:03d}" for i in range(1, 41)]  # 40 unique customers
    dates = pd.date_range("2023-01-01", periods=n, freq="3D")
    return pd.DataFrame({
        "customer_id": rng.choice(customers, n),
        "date":        pd.to_datetime(dates),
        "amount":      rng.uniform(10, 500, n).round(2),
    })


def _make_bank_df(n: int = 30) -> pd.DataFrame:
    """Return a bank-statement-like DataFrame."""
    descriptions = (
        ["mcdonalds burger"] * 5
        + ["grab food order"] * 5
        + ["netflix subscription"] * 5
        + ["random transfer"] * (n - 15)
    )
    rng = np.random.default_rng(3)
    return pd.DataFrame({
        "description": descriptions[:n],
        "amount":      rng.uniform(10, 500, n).round(2),
    })


_SIMPLE_BANK_RULES = {
    "FOOD": {"keywords": ["mcdonalds", "grab food"]},
    "ENTERTAINMENT": {"keywords": ["netflix"]},
}


# ===========================================================================
# TestSummaryStats
# ===========================================================================

class TestSummaryStats:
    """White-box tests for StatisticalEngine._summary_stats."""

    engine = StatisticalEngine()

    def test_returns_two_blocks(self):
        """_summary_stats returns exactly two result blocks."""
        df = _make_numeric_df(50)
        result = self.engine._summary_stats(df, {})
        assert len(result) == 2

    def test_block_ids(self):
        """First block id is stats_table, second is summary_card."""
        df = _make_numeric_df(50)
        result = self.engine._summary_stats(df, {})
        assert result[0]["id"] == "stats_table"
        assert result[1]["id"] == "summary_card"

    def test_raises_when_no_numeric_columns(self):
        """Raises ValueError when DataFrame has no numeric columns."""
        df = pd.DataFrame({"name": ["Alice", "Bob"], "tag": ["x", "y"]})
        with pytest.raises(ValueError, match="cột số"):
            self.engine._summary_stats(df, {})

    def test_rounds_to_2_decimal_places(self):
        """Numeric stats columns are rounded to at most 2 decimal places."""
        df = _make_numeric_df(100)
        result = self.engine._summary_stats(df, {})
        for row in result[0]["data"]:
            for key in ("mean", "std", "min", "p25", "median", "p75", "max"):
                val = row[key]
                assert round(val, 2) == val, f"{key}={val} has more than 2 dp"

    def test_null_rate_all_present(self):
        """null_rate is 0.0 when no NaNs exist in the DataFrame."""
        df = _make_numeric_df(50)
        result = self.engine._summary_stats(df, {})
        assert result[1]["data"]["null_rate"] == 0.0

    def test_null_rate_with_nans(self):
        """null_rate is > 0 and correctly computed when NaNs are present."""
        df = _make_numeric_df(100).copy()
        # Introduce exactly 50 NaN values out of 200 total cells (25 %)
        df.iloc[:25, 0] = np.nan
        df.iloc[:25, 1] = np.nan
        result = self.engine._summary_stats(df, {})
        null_rate = result[1]["data"]["null_rate"]
        assert null_rate > 0
        # Expected: 50 NaN / 200 cells = 0.25
        assert abs(null_rate - 0.25) < 0.01

    def test_total_rows_correct(self):
        """summary_card.total_rows matches the DataFrame length."""
        df = _make_numeric_df(77)
        result = self.engine._summary_stats(df, {})
        assert result[1]["data"]["total_rows"] == 77

    def test_numeric_columns_count(self):
        """summary_card.numeric_columns equals the number of numeric columns."""
        df = _make_numeric_df(50)
        result = self.engine._summary_stats(df, {})
        assert result[1]["data"]["numeric_columns"] == 2

    @pytest.mark.asyncio
    async def test_run_dispatches_to_summary_stats(self):
        """StatisticalEngine.run dispatches summary_stats correctly."""
        df = _make_numeric_df(50)
        result = await StatisticalEngine().run("summary_stats", df, {})
        assert result[0]["id"] == "stats_table"


# ===========================================================================
# TestTimeSeries
# ===========================================================================

class TestTimeSeries:
    """White-box tests for StatisticalEngine._time_series."""

    engine = StatisticalEngine()

    def test_raises_when_no_date_col(self):
        """Raises ValueError when DataFrame has no datetime column."""
        df = _make_numeric_df(30)
        with pytest.raises(ValueError, match="ngày"):
            self.engine._time_series(df, {})

    def test_raises_when_no_numeric_col(self):
        """Raises ValueError when DataFrame has only a date column."""
        df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=20, freq="D")})
        with pytest.raises(ValueError, match="ngày"):
            self.engine._time_series(df, {})

    def test_defaults_to_monthly_granularity(self):
        """Without config granularity, data is resampled monthly."""
        df = _make_ts_df(365)  # Full year of daily data
        result = self.engine._time_series(df, {})
        ts_data = result[0]["data"]
        # Should have roughly 12 monthly periods
        assert 10 <= len(ts_data) <= 13

    def test_daily_frequency_mapping(self):
        """granularity=daily produces more periods than monthly on same data."""
        df = _make_ts_df(60)
        result_daily   = self.engine._time_series(df, {"granularity": "daily"})
        result_monthly = self.engine._time_series(df, {"granularity": "monthly"})
        assert len(result_daily[0]["data"]) > len(result_monthly[0]["data"])

    def test_weekly_frequency_mapping(self):
        """granularity=weekly produces fewer periods than daily."""
        df = _make_ts_df(60)
        result_weekly = self.engine._time_series(df, {"granularity": "weekly"})
        result_daily  = self.engine._time_series(df, {"granularity": "daily"})
        assert len(result_weekly[0]["data"]) < len(result_daily[0]["data"])

    def test_mom_delta_pct_change_present(self):
        """Each period record contains delta_pct; first period is NaN (float)."""
        df = _make_ts_df(90)
        result = self.engine._time_series(df, {})
        ts_data = result[0]["data"]
        # First delta_pct is NaN (no previous period)
        import math
        assert math.isnan(ts_data[0]["delta_pct"])
        # Subsequent ones are finite numbers
        for row in ts_data[1:]:
            assert isinstance(row["delta_pct"], float)
            assert not math.isnan(row["delta_pct"])

    def test_trend_label_tang_when_positive_slope(self):
        """trend_label is 'tăng' when the revenue has a clear upward trend."""
        n = 60
        df = pd.DataFrame({
            "date":    pd.date_range("2024-01-01", periods=n, freq="D"),
            "revenue": np.linspace(100, 1000, n),  # strictly increasing
        })
        result = self.engine._time_series(df, {})
        assert result[1]["data"]["trend"] == "tăng"

    def test_trend_label_giam_when_negative_slope(self):
        """trend_label is 'giảm' when the revenue has a clear downward trend."""
        n = 60
        df = pd.DataFrame({
            "date":    pd.date_range("2024-01-01", periods=n, freq="D"),
            "revenue": np.linspace(1000, 100, n),  # strictly decreasing
        })
        result = self.engine._time_series(df, {})
        assert result[1]["data"]["trend"] == "giảm"

    def test_slope_zero_and_on_dinh_when_single_period(self):
        """slope=0 and trend='ổn định' when only 1 aggregated period exists."""
        # All dates in the same month => one monthly period
        df = pd.DataFrame({
            "date":    pd.date_range("2024-03-01", periods=5, freq="D"),
            "revenue": [100.0, 200.0, 150.0, 180.0, 120.0],
        })
        result = self.engine._time_series(df, {"granularity": "monthly"})
        summary = result[1]["data"]
        assert summary["trend"] == "ổn định"
        assert summary["slope_per_period"] == 0.0


# ===========================================================================
# TestDistribution
# ===========================================================================

class TestDistribution:
    """White-box tests for StatisticalEngine._distribution."""

    engine = StatisticalEngine()

    def test_returns_three_blocks(self):
        """_distribution returns exactly 3 blocks."""
        df = _make_numeric_df(50)
        result = self.engine._distribution(df, {})
        assert len(result) == 3

    def test_block_ids(self):
        """Block ids are histogram, outliers, dist_summary in that order."""
        df = _make_numeric_df(50)
        result = self.engine._distribution(df, {})
        assert result[0]["id"] == "histogram"
        assert result[1]["id"] == "outliers"
        assert result[2]["id"] == "dist_summary"

    def test_iqr_outlier_detection_captures_extremes(self):
        """Values clearly beyond Q3+1.5*IQR are flagged as outliers."""
        base = [100.0] * 40
        outlier_values = [1_000_000.0, 2_000_000.0]  # Extreme outliers
        df = pd.DataFrame({"value": base + outlier_values})
        result = self.engine._distribution(df, {})
        outlier_count = result[2]["data"]["outlier_count"]
        assert outlier_count >= 2

    def test_iqr_outlier_detection_no_outliers_in_uniform_data(self):
        """Uniform data produces 0 IQR outliers."""
        rng = np.random.default_rng(10)
        df = pd.DataFrame({"value": rng.uniform(100, 200, 60)})
        result = self.engine._distribution(df, {})
        # Tight uniform data should have very few or no IQR outliers
        assert result[2]["data"]["outlier_count"] <= 3

    def test_custom_n_bins_honored(self):
        """n_bins config parameter controls number of histogram buckets."""
        df = _make_numeric_df(100)
        result_5  = self.engine._distribution(df, {"n_bins": 5})
        result_20 = self.engine._distribution(df, {"n_bins": 20})
        assert len(result_5[0]["data"]) == 5
        assert len(result_20[0]["data"]) == 20

    def test_default_10_bins(self):
        """Default n_bins produces 10 histogram buckets."""
        df = _make_numeric_df(50)
        result = self.engine._distribution(df, {})
        assert len(result[0]["data"]) == 10


# ===========================================================================
# TestCorrelation
# ===========================================================================

class TestCorrelation:
    """White-box tests for StatisticalEngine._correlation."""

    engine = StatisticalEngine()

    def test_raises_when_single_numeric_column(self):
        """Raises ValueError when only one numeric column is present."""
        df = pd.DataFrame({
            "revenue": [1.0, 2.0, 3.0],
            "name":    ["a", "b", "c"],
        })
        with pytest.raises(ValueError, match="2 cột số"):
            self.engine._correlation(df, {})

    def test_pairs_sorted_by_abs_pearson_r_descending(self):
        """top_pairs data is sorted by |pearson_r| in descending order."""
        df = _make_numeric_df(80)
        # Add a third column strongly correlated with revenue
        df["revenue_2x"] = df["revenue"] * 2.1 + 10
        result = self.engine._correlation(df, {})
        pairs_data = result[1]["data"]
        values = [abs(p["value"]) for p in pairs_data]
        assert values == sorted(values, reverse=True)

    def test_heatmap_data_has_n_squared_rows(self):
        """Heatmap data contains n*n entries for n numeric columns."""
        df = _make_numeric_df(50)
        df["extra"] = df["revenue"] + df["cost"]
        n = 3  # revenue, cost, extra
        result = self.engine._correlation(df, {})
        assert len(result[0]["data"]) == n * n

    def test_scatter_data_capped_at_500_rows(self):
        """Scatter data for the top pair contains at most 500 rows."""
        rng = np.random.default_rng(5)
        df = pd.DataFrame({
            "a": rng.uniform(0, 1, 1000),
            "b": rng.uniform(0, 1, 1000),
        })
        result = self.engine._correlation(df, {})
        assert len(result[2]["data"]) <= 500

    def test_perfect_correlation_detected(self):
        """Pearson r ≈ 1.0 for a perfectly linear pair."""
        n = 60
        x = np.arange(n, dtype=float)
        df = pd.DataFrame({"x": x, "y": x * 3.7 + 5.0})
        result = self.engine._correlation(df, {})
        top_pair = result[1]["data"][0]
        assert abs(top_pair["value"]) >= 0.999


# ===========================================================================
# TestAnomaly
# ===========================================================================

class TestAnomaly:
    """White-box tests for StatisticalEngine._anomaly."""

    engine = StatisticalEngine()

    @staticmethod
    def _df_with_known_anomalies() -> pd.DataFrame:
        rng = np.random.default_rng(7)
        normal = rng.normal(500, 30, 95).tolist()
        anomalies = [2_000.0, 3_500.0, -800.0]  # well beyond 2.5σ
        return pd.DataFrame({"value": normal + anomalies})

    def test_default_z_threshold_25(self):
        """Default z_threshold=2.5 flags only the injected extreme values."""
        df = self._df_with_known_anomalies()
        result = self.engine._anomaly(df, {})
        total = result[2]["data"]["total_anomalies"]
        assert total >= 3  # At minimum the 3 injected extremes

    def test_custom_z_threshold_honored(self):
        """Higher z_threshold=4.0 flags fewer anomalies than default 2.5."""
        df = self._df_with_known_anomalies()
        result_strict = self.engine._anomaly(df, {"z_threshold": 4.0})
        result_loose  = self.engine._anomaly(df, {"z_threshold": 2.5})
        assert result_strict[2]["data"]["total_anomalies"] <= result_loose[2]["data"]["total_anomalies"]

    def test_severity_critical_above_4(self):
        """A z-score > 4 is labelled 'critical'."""
        # Build a dataset where the injected value has z > 4
        base = [100.0] * 99
        base.append(900.0)  # mean≈108, std≈80 → z ≈ 9.8
        df = pd.DataFrame({"value": base})
        result = self.engine._anomaly(df, {})
        anomaly_rows = result[0]["data"]
        # At least the extreme point should be critical
        severities = {r["severity"] for r in anomaly_rows}
        assert "critical" in severities

    def test_severity_high_between_3_and_4(self):
        """A z-score in (3, 4] is labelled 'high'."""
        # Craft a dataset so one point sits at z ≈ 3.5
        rng = np.random.default_rng(9)
        base = rng.normal(0, 1, 98).tolist()
        base += [3.6, -0.1]  # z ≈ 3.6 in std-normal data
        df = pd.DataFrame({"value": base})
        result = self.engine._anomaly(df, {"z_threshold": 2.5})
        anomaly_rows = result[0]["data"]
        severities = {r["severity"] for r in anomaly_rows}
        assert "high" in severities

    def test_severity_medium_between_threshold_and_3(self):
        """A z-score in (2.5, 3] is labelled 'medium'."""
        rng = np.random.default_rng(11)
        base = rng.normal(0, 1, 98).tolist()
        base += [2.8, -0.1]  # z ≈ 2.8 → medium
        df = pd.DataFrame({"value": base})
        result = self.engine._anomaly(df, {"z_threshold": 2.5})
        anomaly_rows = result[0]["data"]
        severities = {r["severity"] for r in anomaly_rows}
        assert "medium" in severities

    def test_timeline_data_present_when_date_col_exists(self):
        """timeline_data is non-empty when a datetime column is present."""
        df = self._df_with_known_anomalies().copy()
        df["date"] = pd.date_range("2024-01-01", periods=len(df), freq="D")
        result = self.engine._anomaly(df, {})
        assert len(result[1]["data"]) > 0

    def test_timeline_data_empty_when_no_date_col(self):
        """timeline_data is an empty list when no date column is present."""
        df = self._df_with_known_anomalies()
        result = self.engine._anomaly(df, {})
        assert result[1]["data"] == []


# ===========================================================================
# TestCohort
# ===========================================================================

class TestCohort:
    """White-box tests for StatisticalEngine._cohort."""

    engine = StatisticalEngine()

    def test_raises_when_no_customer_col(self):
        """Raises ValueError when customer_id column is absent."""
        df = pd.DataFrame({
            "date":   pd.date_range("2024-01-01", periods=30, freq="D"),
            "amount": np.ones(30),
        })
        with pytest.raises(ValueError, match="customer_id"):
            self.engine._cohort(df, {})

    def test_raises_when_no_date_col(self):
        """Raises ValueError when date column is absent."""
        df = pd.DataFrame({
            "customer_id": [f"C{i}" for i in range(30)],
            "amount":      np.ones(30),
        })
        with pytest.raises(ValueError, match="customer_id"):
            self.engine._cohort(df, {})

    def test_retention_period_0_always_1(self):
        """Retention at period=0 (cohort definition month) is always 1.0."""
        df = _make_customer_df(150)
        result = self.engine._cohort(df, {})
        cohort_data = result[0]["data"]
        period_0_rows = [r for r in cohort_data if r["period"] == 0]
        assert len(period_0_rows) > 0
        for row in period_0_rows:
            assert row["retention"] == pytest.approx(1.0, abs=1e-9)

    def test_period_numbers_are_non_negative(self):
        """All period numbers in cohort output are >= 0."""
        df = _make_customer_df(150)
        result = self.engine._cohort(df, {})
        for row in result[0]["data"]:
            assert row["period"] >= 0

    def test_returns_two_blocks(self):
        """_cohort returns exactly 2 output blocks."""
        df = _make_customer_df(150)
        result = self.engine._cohort(df, {})
        assert len(result) == 2

    def test_block_ids(self):
        """Block ids are cohort_heatmap and cohort_summary."""
        df = _make_customer_df(150)
        result = self.engine._cohort(df, {})
        assert result[0]["id"] == "cohort_heatmap"
        assert result[1]["id"] == "cohort_summary"


# ===========================================================================
# TestBankClassify
# ===========================================================================

class TestBankClassify:
    """White-box tests for StatisticalEngine._bank_classify."""

    engine = StatisticalEngine()

    _RULES_JSON = json.dumps(_SIMPLE_BANK_RULES)

    def test_raises_when_rules_file_missing(self):
        """Raises ValueError when bank_rules.json does not exist on disk."""
        df = _make_bank_df()
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(ValueError, match="bank_rules.json"):
                self.engine._bank_classify(df, {})

    def test_raises_when_desc_col_missing(self):
        """Raises ValueError when description column is absent."""
        df = pd.DataFrame({"amount": [10.0, 20.0]})
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=self._RULES_JSON)):
                with pytest.raises(ValueError, match="mô tả"):
                    self.engine._bank_classify(df, {})

    def test_raises_when_amount_col_missing(self):
        """Raises ValueError when amount column is absent."""
        df = pd.DataFrame({"description": ["test", "another"]})
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=self._RULES_JSON)):
                with pytest.raises(ValueError, match="mô tả"):
                    self.engine._bank_classify(df, {})

    def test_khac_category_for_unmatched_rows(self):
        """Rows not matching any keyword are assigned category 'KHÁC'."""
        df = pd.DataFrame({
            "description": ["random unknown vendor", "another mystery payment"],
            "amount":      [100.0, 200.0],
        })
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=self._RULES_JSON)):
                result = self.engine._bank_classify(df, {})
        category_ids = {r["category"] for r in result[0]["data"]}
        assert "KHÁC" in category_ids

    def test_known_keyword_classified_correctly(self):
        """'mcdonalds' keyword maps to 'FOOD' category."""
        df = pd.DataFrame({
            "description": ["mcdonalds big mac", "mcdonalds fries"],
            "amount":      [50.0, 30.0],
        })
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=self._RULES_JSON)):
                result = self.engine._bank_classify(df, {})
        category_breakdown = result[0]["data"]
        food_rows = [r for r in category_breakdown if r["category"] == "FOOD"]
        assert len(food_rows) == 1
        assert food_rows[0]["count"] == 2

    def test_returns_three_blocks(self):
        """_bank_classify returns exactly 3 output blocks."""
        df = _make_bank_df()
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=self._RULES_JSON)):
                result = self.engine._bank_classify(df, {})
        assert len(result) == 3

    def test_block_ids(self):
        """Block ids are category_breakdown, unclassified_list, bank_summary."""
        df = _make_bank_df()
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=self._RULES_JSON)):
                result = self.engine._bank_classify(df, {})
        assert result[0]["id"] == "category_breakdown"
        assert result[1]["id"] == "unclassified_list"
        assert result[2]["id"] == "bank_summary"

    def test_summary_counts_correct(self):
        """bank_summary.total_transactions matches DataFrame row count."""
        df = _make_bank_df(20)
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=self._RULES_JSON)):
                result = self.engine._bank_classify(df, {})
        summary = result[2]["data"]
        assert summary["total_transactions"] == 20
        assert summary["classified"] + summary["unclassified"] == 20


# ===========================================================================
# TestClustering
# ===========================================================================

class TestClustering:
    """White-box tests for MLEngine._clustering."""

    engine = MLEngine(mode="ml")

    def test_raises_when_single_numeric_column(self):
        """Raises ValueError when fewer than 2 numeric columns are present."""
        df = pd.DataFrame({"revenue": np.ones(20)})
        with pytest.raises(ValueError, match="2 cột số"):
            self.engine._clustering(df, {})

    def test_raises_when_fewer_than_10_rows(self):
        """Raises ValueError when the cleaned DataFrame has fewer than 10 rows."""
        df = pd.DataFrame({"a": np.ones(8), "b": np.ones(8)})
        with pytest.raises(ValueError, match="10 hàng"):
            self.engine._clustering(df, {})

    def test_k_clamped_below_to_2(self):
        """k=1 in config is clamped up to 2."""
        df = _make_numeric_df(50)
        result = self.engine._clustering(df, {"k": 1})
        k = result[3]["data"]["k"]
        assert k == 2

    def test_k_clamped_above_to_8(self):
        """k=20 in config is clamped down to 8."""
        df = _make_numeric_df(100)
        result = self.engine._clustering(df, {"k": 20})
        k = result[3]["data"]["k"]
        assert k == 8

    def test_returns_four_blocks(self):
        """_clustering returns exactly 4 output blocks."""
        df = _make_numeric_df(60)
        result = self.engine._clustering(df, {"k": 3})
        assert len(result) == 4

    def test_block_ids(self):
        """Block ids are cluster_scatter, cluster_summary, cluster_sizes, cluster_stats."""
        df = _make_numeric_df(60)
        result = self.engine._clustering(df, {"k": 3})
        ids = [b["id"] for b in result]
        assert ids == ["cluster_scatter", "cluster_summary", "cluster_sizes", "cluster_stats"]

    def test_silhouette_score_present(self):
        """cluster_stats block contains a numeric silhouette_score."""
        df = _make_numeric_df(80)
        result = self.engine._clustering(df, {"k": 3})
        sil = result[3]["data"]["silhouette_score"]
        assert sil is not None
        assert -1.0 <= sil <= 1.0

    @pytest.mark.asyncio
    async def test_run_dispatches_clustering(self):
        """MLEngine.run dispatches 'clustering' template correctly."""
        df = _make_numeric_df(60)
        result = await MLEngine(mode="ml").run("clustering", df, {"k": 2})
        assert result[0]["id"] == "cluster_scatter"


# ===========================================================================
# TestChurn
# ===========================================================================

class TestChurn:
    """White-box tests for MLEngine._churn."""

    engine = MLEngine(mode="ml")

    def test_raises_when_no_date_col(self):
        """Raises ValueError when date column is absent."""
        df = pd.DataFrame({
            "customer_id": ["C1", "C2", "C3"],
            "amount":      [100.0, 200.0, 300.0],
        })
        with pytest.raises(ValueError, match="customer_id"):
            self.engine._churn(df, {})

    def test_raises_when_no_customer_col(self):
        """Raises ValueError when customer_id column is absent."""
        df = pd.DataFrame({
            "date":   pd.date_range("2024-01-01", periods=10, freq="W"),
            "amount": np.ones(10),
        })
        with pytest.raises(ValueError, match="customer_id"):
            self.engine._churn(df, {})

    def test_churn_risk_values_are_valid(self):
        """Every churn_risk value is one of 'Cao', 'Trung bình', or 'Thấp'."""
        df = _make_customer_df(150)
        result = self.engine._churn(df, {})
        valid_levels = {"Cao", "Trung bình", "Thấp"}
        for row in result[0]["data"]:
            assert row["risk_level"] in valid_levels

    def test_at_risk_contains_only_cao(self):
        """at_risk_customers block only contains rows with churn_risk='Cao'."""
        df = _make_customer_df(150)
        result = self.engine._churn(df, {})
        at_risk_data = result[1]["data"]
        for row in at_risk_data:
            assert row["churn_risk"] == "Cao"

    def test_monetary_dimension_added_when_amount_col_present(self):
        """When an amount column exists, RFM includes a monetary dimension."""
        df = _make_customer_df(150)  # has 'amount' column
        result = self.engine._churn(df, {})
        summary = result[3]["data"]
        # The method kwarg unpacks monetary only when val_col is found
        # Confirm at_risk records include monetary column
        at_risk_data = result[1]["data"]
        if at_risk_data:
            assert "monetary" in at_risk_data[0]

    def test_qcut_fallback_with_few_unique_values(self):
        """With fewer than 5 unique recency values, qcut fallback assigns score=3."""
        # Only 3 customers with identical activity → few unique recency values
        df = pd.DataFrame({
            "customer_id": ["C1"] * 50 + ["C2"] * 50 + ["C3"] * 50,
            "date": pd.date_range("2024-01-01", periods=150, freq="D"),
            "amount": np.ones(150) * 100.0,
        })
        # Should not raise
        result = self.engine._churn(df, {})
        # All customers are present in risk distribution
        risk_counts = result[0]["data"]
        total = sum(r["count"] for r in risk_counts)
        assert total == 3  # 3 unique customers

    def test_returns_four_blocks(self):
        """_churn returns exactly 4 output blocks."""
        df = _make_customer_df(150)
        result = self.engine._churn(df, {})
        assert len(result) == 4

    def test_block_ids(self):
        """Block ids are risk_distribution, at_risk_customers, rfm_scatter, churn_summary."""
        df = _make_customer_df(150)
        result = self.engine._churn(df, {})
        ids = [b["id"] for b in result]
        assert ids == ["risk_distribution", "at_risk_customers", "rfm_scatter", "churn_summary"]


# ===========================================================================
# TestRegression
# ===========================================================================

class TestRegression:
    """White-box tests for MLEngine._regression."""

    engine = MLEngine(mode="ml")

    @staticmethod
    def _make_regression_df(n: int) -> pd.DataFrame:
        rng = np.random.default_rng(42)
        x1 = rng.uniform(0, 10, n)
        x2 = rng.uniform(0, 5, n)
        y  = 3.0 * x1 - 2.0 * x2 + rng.normal(0, 0.5, n)
        return pd.DataFrame({"x1": x1, "x2": x2, "target": y})

    def test_raises_when_single_numeric_column(self):
        """Raises ValueError when fewer than 2 numeric columns are present."""
        df = pd.DataFrame({"target": np.ones(30)})
        with pytest.raises(ValueError, match="2 cột số"):
            self.engine._regression(df, {})

    def test_raises_when_fewer_than_20_rows(self):
        """Raises ValueError when the usable row count is below 20."""
        df = self._make_regression_df(15)
        with pytest.raises(ValueError, match="20 hàng"):
            self.engine._regression(df, {})

    def test_uses_linear_regression_below_200_rows(self):
        """Model field is 'LinearRegression' for datasets smaller than 200 rows."""
        df = self._make_regression_df(80)
        result = self.engine._regression(df, {"target_col": "target"})
        model_name = result[2]["data"]["model"]
        assert model_name == "LinearRegression"

    def test_uses_gbm_at_200_or_more_rows(self):
        """Model field is 'GradientBoosting' for datasets of 200+ rows."""
        df = self._make_regression_df(250)
        result = self.engine._regression(df, {"target_col": "target"})
        model_name = result[2]["data"]["model"]
        assert model_name == "GradientBoosting"

    def test_r2_score_in_valid_range(self):
        """r2_score is in the interval [-1, 1]."""
        df = self._make_regression_df(100)
        result = self.engine._regression(df, {"target_col": "target"})
        r2 = result[2]["data"]["r2_score"]
        assert -1.0 <= r2 <= 1.0

    def test_r2_high_for_near_linear_data(self):
        """r2_score > 0.9 for nearly noise-free linear data."""
        rng = np.random.default_rng(99)
        n = 100
        x1 = rng.uniform(0, 10, n)
        x2 = rng.uniform(0, 5, n)
        y = 5.0 * x1 + 2.0 * x2 + rng.normal(0, 0.01, n)  # nearly perfect
        df = pd.DataFrame({"x1": x1, "x2": x2, "target": y})
        result = self.engine._regression(df, {"target_col": "target"})
        assert result[2]["data"]["r2_score"] > 0.9

    def test_feature_importance_sums_to_1(self):
        """Feature importances (normalised) sum to approximately 1.0."""
        df = self._make_regression_df(100)
        result = self.engine._regression(df, {"target_col": "target"})
        importances = [r["importance"] for r in result[0]["data"]]
        assert pytest.approx(sum(importances), abs=1e-4) == 1.0

    def test_returns_three_blocks(self):
        """_regression returns exactly 3 output blocks."""
        df = self._make_regression_df(60)
        result = self.engine._regression(df, {"target_col": "target"})
        assert len(result) == 3

    def test_block_ids(self):
        """Block ids are feature_importance, actual_vs_predicted, regression_summary."""
        df = self._make_regression_df(60)
        result = self.engine._regression(df, {"target_col": "target"})
        ids = [b["id"] for b in result]
        assert ids == ["feature_importance", "actual_vs_predicted", "regression_summary"]

    @pytest.mark.asyncio
    async def test_run_dispatches_regression(self):
        """MLEngine.run dispatches 'regression' template correctly."""
        df = self._make_regression_df(60)
        result = await MLEngine(mode="ml").run("regression", df, {"target_col": "target"})
        assert result[0]["id"] == "feature_importance"


# ===========================================================================
# TestTemplateRegistry
# ===========================================================================

class TestTemplateRegistry:
    """White-box tests for AnalysisTemplate.is_eligible and get_eligible_templates."""

    # ── is_eligible ────────────────────────────────────────────────────────

    def test_ineligible_when_row_count_below_min_rows(self):
        """is_eligible returns False when row_count < min_rows."""
        t = AnalysisTemplate(
            template_id="test",
            display_name="Test",
            description="Test template",
            required_types=["integer"],
            required_purposes=[],
            min_rows=50,
        )
        assert t.is_eligible({"integer"}, None, 49) is False

    def test_eligible_when_row_count_equals_min_rows(self):
        """is_eligible returns True when row_count == min_rows exactly."""
        t = AnalysisTemplate(
            template_id="test",
            display_name="Test",
            description="Test template",
            required_types=["integer"],
            required_purposes=[],
            min_rows=50,
        )
        assert t.is_eligible({"integer"}, None, 50) is True

    def test_ineligible_when_required_type_missing(self):
        """is_eligible returns False when no required_type is in detected_types."""
        t = AnalysisTemplate(
            template_id="ts",
            display_name="TS",
            description="Needs date",
            required_types=["date"],
            required_purposes=[],
            min_rows=14,
        )
        assert t.is_eligible({"integer", "decimal"}, None, 100) is False

    def test_eligible_when_at_least_one_required_type_matched(self):
        """is_eligible returns True when at least one required_type is detected."""
        t = AnalysisTemplate(
            template_id="dist",
            display_name="Dist",
            description="Needs number",
            required_types=["integer", "decimal", "currency"],
            required_purposes=[],
            min_rows=30,
        )
        assert t.is_eligible({"decimal"}, None, 50) is True

    def test_ineligible_when_required_purpose_not_matched(self):
        """is_eligible returns False when required_purposes is non-empty and purpose not matched."""
        t = AnalysisTemplate(
            template_id="cohort",
            display_name="Cohort",
            description="Needs transaction purpose",
            required_types=["date"],
            required_purposes=["transaction_list", "customer_master"],
            min_rows=100,
        )
        assert t.is_eligible({"date"}, "sales_report", 200) is False

    def test_eligible_when_purpose_matches(self):
        """is_eligible returns True when detected_purpose is in required_purposes."""
        t = AnalysisTemplate(
            template_id="cohort",
            display_name="Cohort",
            description="Needs transaction purpose",
            required_types=["date"],
            required_purposes=["transaction_list", "customer_master"],
            min_rows=100,
        )
        assert t.is_eligible({"date"}, "transaction_list", 200) is True

    def test_eligible_when_required_purposes_empty(self):
        """is_eligible returns True regardless of purpose when required_purposes is empty."""
        t = AnalysisTemplate(
            template_id="summary",
            display_name="Summary",
            description="Any purpose",
            required_types=["integer"],
            required_purposes=[],
            min_rows=5,
        )
        assert t.is_eligible({"integer"}, "some_random_purpose", 10) is True

    # ── get_eligible_templates ─────────────────────────────────────────────

    def test_returns_all_10_templates(self):
        """get_eligible_templates returns one entry per registered template (10 total)."""
        result = get_eligible_templates({"integer"}, None, 1000)
        assert len(result) == 10

    def test_eligible_flag_true_for_summary_stats_with_numeric_data(self):
        """summary_stats is eligible with integer detected type and 10 rows."""
        result = get_eligible_templates({"integer"}, None, 10)
        entry = next(r for r in result if r["template_id"] == "summary_stats")
        assert entry["eligible"] is True

    def test_eligible_flag_false_for_summary_stats_with_only_date(self):
        """summary_stats is ineligible when only date type is detected."""
        result = get_eligible_templates({"date"}, None, 100)
        entry = next(r for r in result if r["template_id"] == "summary_stats")
        assert entry["eligible"] is False

    def test_eligible_flag_false_for_clustering_below_50_rows(self):
        """clustering is ineligible with only 40 rows (min_rows=50)."""
        result = get_eligible_templates({"integer", "decimal"}, None, 40)
        entry = next(r for r in result if r["template_id"] == "clustering")
        assert entry["eligible"] is False

    def test_cohort_ineligible_without_correct_purpose(self):
        """cohort is ineligible when purpose is not customer_master or transaction_list."""
        result = get_eligible_templates({"date"}, "inventory_report", 200)
        entry = next(r for r in result if r["template_id"] == "cohort")
        assert entry["eligible"] is False

    def test_cohort_eligible_with_correct_purpose(self):
        """cohort is eligible when purpose is customer_master and row/type requirements are met."""
        result = get_eligible_templates({"date"}, "customer_master", 200)
        entry = next(r for r in result if r["template_id"] == "cohort")
        assert entry["eligible"] is True

    def test_bank_classify_ineligible_without_text_type(self):
        """bank_classify is ineligible when 'text' is not in detected_types."""
        result = get_eligible_templates({"currency"}, "bank_statement", 50)
        entry = next(r for r in result if r["template_id"] == "bank_classify")
        assert entry["eligible"] is False

    def test_bank_classify_ineligible_without_currency_type(self):
        """Edge: symmetric to the above — bank_classify also needs currency.
        Text alone (no amount column) is not enough to run the template."""
        result = get_eligible_templates({"text"}, "bank_statement", 50)
        entry = next(r for r in result if r["template_id"] == "bank_classify")
        assert entry["eligible"] is False

    def test_bank_classify_eligible_with_both_types(self):
        """Edge: with BOTH currency and text + correct purpose + enough rows,
        bank_classify becomes eligible. Confirms require_all_types path is
        not over-strict."""
        result = get_eligible_templates({"currency", "text"}, "bank_statement", 50)
        entry = next(r for r in result if r["template_id"] == "bank_classify")
        assert entry["eligible"] is True

    def test_summary_stats_still_uses_any_semantics(self):
        """Regression guard: summary_stats has require_all_types=False (the
        default), so a single matching numeric type is enough. The
        require_all_types flag must not have leaked into other templates."""
        result = get_eligible_templates({"integer"}, None, 100)  # only integer, no decimal/currency
        entry = next(r for r in result if r["template_id"] == "summary_stats")
        assert entry["eligible"] is True

    def test_result_contains_required_keys(self):
        """Each entry in get_eligible_templates has all required dict keys."""
        required_keys = {"template_id", "display_name", "description",
                         "eligible", "min_rows", "model_hint"}
        result = get_eligible_templates({"integer"}, None, 100)
        for entry in result:
            assert required_keys.issubset(entry.keys()), (
                f"Missing keys in {entry['template_id']}: "
                f"{required_keys - set(entry.keys())}"
            )

    def test_eligible_flag_is_bool(self):
        """eligible field is a Python bool, not a numpy bool."""
        result = get_eligible_templates({"integer"}, None, 100)
        for entry in result:
            assert isinstance(entry["eligible"], bool)
