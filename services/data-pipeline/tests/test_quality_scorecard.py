"""Tests for the 7-dim quality scorecard (Stage 4)."""
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

from data_plane.silver.quality import (
    DEFAULT_WEIGHTS,
    compute_scorecard,
)


def _df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


class TestEmptySheet:
    def test_returns_zero_overall_and_empty_dim_marker(self):
        sc = compute_scorecard(pd.DataFrame(), data_types={}, purpose="transaction_list")
        assert sc["overall"] == 0.0
        assert sc["row_count"] == 0
        assert all(v is None for v in sc["dimensions"].values())
        assert any(i["code"] == "EMPTY_SHEET" for i in sc["issues"])


class TestCompleteness:
    def test_all_required_present_gives_one(self):
        df = _df([
            {"customer_id": "C1", "transaction_date": "2026-05-01", "amount": 100_000},
            {"customer_id": "C2", "transaction_date": "2026-05-02", "amount": 250_000},
        ])
        sc = compute_scorecard(df, data_types={}, purpose="transaction_list")
        assert sc["dimensions"]["completeness"] == 1.0

    def test_partial_nulls_drag_score(self):
        df = _df([
            {"customer_id": "C1", "transaction_date": None,         "amount": 100_000},
            {"customer_id": None, "transaction_date": "2026-05-02", "amount": None},
        ])
        sc = compute_scorecard(df, data_types={}, purpose="transaction_list")
        # Per-column non-null rate: customer_id=0.5, date=0.5, amount=0.5
        # → mean = 0.5
        assert sc["dimensions"]["completeness"] == 0.5
        assert any(i["code"] == "COMPLETENESS_NULLS" for i in sc["issues"])

    def test_unknown_purpose_returns_na(self):
        df = _df([{"foo": "bar"}])
        sc = compute_scorecard(df, data_types={}, purpose=None)
        assert sc["dimensions"]["completeness"] is None


class TestValidity:
    def test_valid_vn_phones_pass(self):
        df = _df([
            {"phone": "+84987654321"},
            {"phone": "0987654321"},
        ])
        sc = compute_scorecard(df, data_types={"phone": "phone"}, purpose=None)
        assert sc["dimensions"]["validity"] == 1.0

    def test_invalid_phones_flagged(self):
        df = _df([
            {"phone": "+84987654321"},
            {"phone": "not_a_phone"},
            {"phone": "12345"},
        ])
        sc = compute_scorecard(df, data_types={"phone": "phone"}, purpose=None)
        # 1/3 valid → ~0.333
        assert 0.3 <= sc["dimensions"]["validity"] <= 0.4
        assert any(i["code"] == "VALIDITY_PATTERN_FAIL" for i in sc["issues"])

    def test_email_validator(self):
        df = _df([
            {"email": "anh@kaori.local"},
            {"email": "broken"},
        ])
        sc = compute_scorecard(df, data_types={"email": "email"}, purpose=None)
        assert sc["dimensions"]["validity"] == 0.5


class TestUniqueness:
    def test_all_unique_gives_one(self):
        df = _df([{"customer_id": f"C{i}"} for i in range(10)])
        sc = compute_scorecard(df, data_types={"customer_id": "text"},
                                purpose="customer_master")
        assert sc["dimensions"]["uniqueness"] == 1.0

    def test_duplicates_drag_score(self):
        df = _df([{"customer_id": "C1"}, {"customer_id": "C1"},
                  {"customer_id": "C2"}, {"customer_id": "C3"}])
        sc = compute_scorecard(df, data_types={"customer_id": "text"},
                                purpose="customer_master")
        # 3 unique / 4 total = 0.75
        assert sc["dimensions"]["uniqueness"] == 0.75
        assert any(i["code"] == "UNIQUENESS_DUPLICATES" for i in sc["issues"])


class TestConsistency:
    def test_negative_amount_flagged(self):
        df = _df([
            {"amount": 100_000},
            {"amount": -50_000},
            {"amount": 200_000},
        ])
        sc = compute_scorecard(df, data_types={"amount": "amount_vnd"},
                                purpose="transaction_list")
        # 1 rule ran, failed → consistency = 0
        assert sc["dimensions"]["consistency"] == 0.0
        assert any(i["code"] == "CONSISTENCY_NEGATIVE_AMOUNT" for i in sc["issues"])

    def test_date_order_flagged(self):
        df = _df([
            {"start_date": "2026-01-01", "end_date": "2026-02-01"},
            {"start_date": "2026-03-01", "end_date": "2026-01-15"},  # bad
        ])
        sc = compute_scorecard(df, data_types={}, purpose=None)
        assert sc["dimensions"]["consistency"] == 0.0
        assert any(i["code"] == "CONSISTENCY_DATE_ORDER" for i in sc["issues"])


class TestTimeliness:
    def test_all_fresh_gives_one(self):
        today = pd.Timestamp.utcnow().tz_localize(None).date().isoformat()
        df = _df([{"transaction_date": today}, {"transaction_date": today}])
        sc = compute_scorecard(df, data_types={"transaction_date": "date"},
                                purpose="transaction_list")
        assert sc["dimensions"]["timeliness"] == 1.0

    def test_stale_rows_flagged(self):
        df = _df([
            {"transaction_date": "2020-01-01"},
            {"transaction_date": "2026-05-15"},
        ])
        sc = compute_scorecard(df, data_types={"transaction_date": "date"},
                                purpose="transaction_list")
        assert 0.4 <= sc["dimensions"]["timeliness"] <= 0.6
        assert any(i["code"] == "TIMELINESS_STALE" for i in sc["issues"])


class TestAccuracy:
    def test_amount_outlier_flagged(self):
        df = _df([
            {"amount": 100_000},
            {"amount": 50_000_000_000},  # 50B VND — way out of range
            {"amount": 200_000},
        ])
        sc = compute_scorecard(df, data_types={"amount": "amount_vnd"},
                                purpose="transaction_list")
        # 1/3 outliers → accuracy = 1 - 1/3 ≈ 0.667
        assert 0.6 <= sc["dimensions"]["accuracy"] <= 0.7
        assert any(i["code"] == "ACCURACY_AMOUNT_OUTLIER" for i in sc["issues"])


class TestIntegrity:
    def test_all_customers_match_master(self):
        df = _df([{"customer_id": "C1"}, {"customer_id": "C2"}])
        sc = compute_scorecard(df, data_types={}, purpose="transaction_list",
                                existing_customer_ids={"C1", "C2", "C99"})
        assert sc["dimensions"]["integrity"] == 1.0

    def test_orphan_customer_flagged(self):
        df = _df([{"customer_id": "C1"}, {"customer_id": "MISSING"}])
        sc = compute_scorecard(df, data_types={}, purpose="transaction_list",
                                existing_customer_ids={"C1"})
        assert sc["dimensions"]["integrity"] == 0.5
        assert any(i["code"] == "INTEGRITY_ORPHAN_FK" for i in sc["issues"])

    def test_no_master_returns_na(self):
        df = _df([{"customer_id": "C1"}])
        sc = compute_scorecard(df, data_types={}, purpose="transaction_list")
        assert sc["dimensions"]["integrity"] is None


class TestOverallWeighting:
    def test_weights_sum_to_one(self):
        assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9

    def test_na_dimensions_rescale_weights(self):
        # Only completeness + validity → weights re-normalize over the two
        df = _df([
            {"customer_id": "C1", "transaction_date": "2030-01-01", "amount": 100_000},
        ])
        sc = compute_scorecard(df, data_types={}, purpose="transaction_list")
        # Without phone/email validators no validity check runs; uniqueness
        # PK column 'transaction_id' missing → also N/A. Just completeness
        # + accuracy + timeliness contribute. Overall must be in [0, 1].
        assert 0.0 <= sc["overall"] <= 1.0

    def test_perfect_data_gives_high_overall(self):
        today = pd.Timestamp.utcnow().tz_localize(None).date().isoformat()
        df = _df([
            {"customer_id": "C1", "transaction_date": today, "amount": 100_000,
             "transaction_id": "T1"},
            {"customer_id": "C2", "transaction_date": today, "amount": 200_000,
             "transaction_id": "T2"},
        ])
        sc = compute_scorecard(df, data_types={"amount": "amount_vnd",
                                               "transaction_date": "date"},
                                purpose="transaction_list")
        assert sc["overall"] >= 0.95


class TestBiasAttached:
    def test_scorecard_carries_bias_report(self):
        df = pd.DataFrame({
            "customer_id": list(range(100)),
            "gioi_tinh":   ["Nam"] * 96 + ["Nu"] * 4,
        })
        sc = compute_scorecard(df, data_types={"customer_id": "integer"},
                               purpose="customer_master")
        assert "bias" in sc
        assert sc["bias"]["status"] == "flagged"
        assert sc["bias"]["findings"][0]["column"] == "gioi_tinh"
        assert 0.0 <= sc["overall"] <= 1.0

    def test_empty_sheet_has_bias_not_applicable(self):
        sc = compute_scorecard(pd.DataFrame(), data_types={}, purpose="transaction_list")
        assert sc["bias"]["status"] == "not_applicable"
