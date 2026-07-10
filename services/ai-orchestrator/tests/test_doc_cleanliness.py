"""
Tests for reasoning.doc_cleanliness.assess_cleanliness — the "Qwen chấm
sạch/bẩn" gate for tabular files nộp vào Cây tài liệu (demo AABW 11/07).

Contract: deterministic heuristics decide the verdict (LLM chỉ viết nhận
xét, không quyết định); a dirty file routes to the 5-step pipeline, a
clean one routes straight to analysis.
"""
import pandas as pd
import pytest

from ai_orchestrator.reasoning.doc_cleanliness import assess_cleanliness


def _clean_df() -> pd.DataFrame:
    return pd.DataFrame({
        "ma_lo":    [f"LO-{i}" for i in range(1, 11)],
        "ngay":     [f"2026-07-{i:02d}" for i in range(1, 11)],
        "mat_hang": ["Cà chua"] * 10,
        "kg":       [100 + i for i in range(10)],
        "gia":      [15000] * 10,
    })


def _dirty_df() -> pd.DataFrame:
    return pd.DataFrame({
        "ma_lo": ["LO-1", "LO-2", "LO-2", "LO-4", "LO-5", "LO-6"],
        "ngay":  ["2026-05-02", "03/05/2026", "03/05/2026", "05-05-2026", None, "2026-05-08"],
        "kg":    ["850", "-50", "-50", "9999", "600", ""],
        "tien":  ["11.475.000", "2tr7", "2tr7", "129.987.000", '"5,280,000"', "1.600.000"],
    })


def test_clean_dataframe_passes():
    v = assess_cleanliness(_clean_df())
    assert v["is_clean"] is True
    assert v["recommendation"] == "analyze"
    assert v["score"] >= 0.8


def test_dirty_dataframe_fails_and_routes_to_pipeline():
    v = assess_cleanliness(_dirty_df())
    assert v["is_clean"] is False
    assert v["recommendation"] == "run_pipeline"
    codes = {i["code"] for i in v["issues"]}
    assert "duplicate_rows" in codes
    assert "mixed_date_formats" in codes
    assert "unparseable_numbers" in codes


def test_issues_carry_counts_and_labels():
    v = assess_cleanliness(_dirty_df())
    dup = next(i for i in v["issues"] if i["code"] == "duplicate_rows")
    assert dup["count"] >= 1
    assert dup["label"]  # human-readable Vietnamese label


def test_high_null_rate_is_flagged():
    df = pd.DataFrame({
        "a": ["x"] * 10,
        "b": [None] * 8 + ["1", "2"],
    })
    v = assess_cleanliness(df)
    assert any(i["code"] == "high_null_rate" for i in v["issues"])


def test_empty_dataframe_is_not_clean():
    v = assess_cleanliness(pd.DataFrame())
    assert v["is_clean"] is False
