"""Tests for Stage-4 bias examination (EU AI Act Art 10)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_SERVICE_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _SERVICE_ROOT.parent.parent
for _p in (_SERVICE_ROOT, _REPO_ROOT):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from data_plane.silver.bias import detect_sensitive_columns, examine_bias


def test_detect_sensitive_columns_vn_and_en():
    cols = ["customer_id", "gioi_tinh", "Age", "amount", "tinh_thanh", "note"]
    found = detect_sensitive_columns(cols)
    assert "gioi_tinh" in found
    assert "Age" in found
    assert "tinh_thanh" in found
    assert "customer_id" not in found
    assert "amount" not in found


def test_skewed_sensitive_column_flagged():
    df = pd.DataFrame({"gioi_tinh": ["Nam"] * 96 + ["Nu"] * 4})
    rep = examine_bias(df, data_types={"gioi_tinh": "categorical"})
    assert rep["status"] == "flagged"
    assert "gioi_tinh" in rep["checked_columns"]
    assert len(rep["findings"]) == 1
    f = rep["findings"][0]
    assert f["code"] == "BIAS_REPRESENTATION_IMBALANCE"
    assert f["column"] == "gioi_tinh"
    assert f["dominant_value"] == "Nam"
    assert abs(f["dominant_share"] - 0.96) < 1e-6
    assert f["severity"] == "high"


def test_balanced_sensitive_column_ok():
    df = pd.DataFrame({"gioi_tinh": (["Nam", "Nu"] * 50)})
    rep = examine_bias(df, data_types={"gioi_tinh": "categorical"})
    assert rep["status"] == "ok"
    assert rep["findings"] == []
    assert "gioi_tinh" in rep["checked_columns"]


def test_no_sensitive_columns_not_applicable():
    df = pd.DataFrame({"customer_id": list(range(100)), "amount": [10] * 100})
    rep = examine_bias(df, data_types={})
    assert rep["status"] == "not_applicable"
    assert rep["checked_columns"] == []
    assert rep["findings"] == []


def test_below_min_rows_skipped():
    df = pd.DataFrame({"gioi_tinh": ["Nam"] * 5})
    rep = examine_bias(df, data_types={})
    assert rep["status"] == "not_applicable"
    assert rep["checked_columns"] == []


def test_threshold_env_override(monkeypatch):
    df = pd.DataFrame({"gioi_tinh": ["Nam"] * 70 + ["Nu"] * 30})
    assert examine_bias(df, {})["status"] == "ok"
    monkeypatch.setenv("KAORI_BIAS_DOMINANT_SHARE", "0.6")
    assert examine_bias(df, {})["status"] == "flagged"


def test_empty_df_not_applicable():
    rep = examine_bias(pd.DataFrame(), data_types={})
    assert rep["status"] == "not_applicable"
    assert rep["row_count"] == 0
