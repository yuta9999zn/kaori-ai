"""Pure-function tests for seed_olist_into_kaori.py shape logic.

Doesn't touch the DB — just verifies the CSV → row mapping is correct.
Run from repo root:  python -m pytest scripts/test_seed_olist_shape.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

# Add scripts/ to path so the seed module imports clean.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from seed_olist_into_kaori import (  # type: ignore[import-not-found]
    OLIST_PLAN,
    SeedSummary,
    aggregate_finance_periods,
    iter_rows,
    project_customer_row,
    project_order_row,
    project_payment_row,
    project_review_row,
    sha256_of_file,
)


def test_olist_plan_covers_4_departments():
    """The 8 Olist CSVs should hit 4 of the 6 fixed departments."""
    depts = {p.dept_type for p in OLIST_PLAN}
    assert depts == {"sales", "customer_service", "warehouse", "finance"}


def test_olist_plan_file_count_per_dept():
    """Sales has the bulk of business data (4 files); CS + Finance have 1 each."""
    by_dept: dict[str, int] = {}
    for p in OLIST_PLAN:
        by_dept[p.dept_type] = by_dept.get(p.dept_type, 0) + 1
    assert by_dept["sales"] == 4              # customers + orders + items + sellers
    assert by_dept["customer_service"] == 1   # reviews
    assert by_dept["warehouse"] == 2          # products + geolocation
    assert by_dept["finance"] == 1            # payments


def test_olist_plan_filenames_match_kaggle_release():
    """Lock the exact CSV names — defends against typos when a Kaggle
    re-release changes naming."""
    names = {p.filename for p in OLIST_PLAN}
    assert names == {
        "olist_customers_dataset.csv",
        "olist_orders_dataset.csv",
        "olist_order_items_dataset.csv",
        "olist_sellers_dataset.csv",
        "olist_order_reviews_dataset.csv",
        "olist_products_dataset.csv",
        "olist_geolocation_dataset.csv",
        "olist_order_payments_dataset.csv",
    }


def test_olist_plan_dept_types_are_valid_enum():
    """dept_type values must match the CHECK constraint in mig 046."""
    valid = {"marketing", "sales", "customer_service",
             "warehouse", "hr", "finance", "custom"}
    for p in OLIST_PLAN:
        assert p.dept_type in valid, f"{p.filename}: bad dept_type {p.dept_type!r}"


def test_seed_summary_add_file_accumulates():
    s = SeedSummary()
    s.add_file("sales", row_count=100, size_bytes=1024)
    s.add_file("sales", row_count=50, size_bytes=512)
    s.add_file("warehouse", row_count=200, size_bytes=2048)
    assert s.files_by_dept == {"sales": 2, "warehouse": 1}
    assert s.rows_by_dept == {"sales": 150, "warehouse": 200}
    assert s.total_bytes == 1024 + 512 + 2048


def test_sha256_of_file_deterministic(tmp_path):
    f1 = tmp_path / "a.csv"
    f1.write_bytes(b"hello,world\n1,2\n")
    f2 = tmp_path / "b.csv"
    f2.write_bytes(b"hello,world\n1,2\n")
    # Same content → same hash.
    assert sha256_of_file(f1) == sha256_of_file(f2)
    # Different content → different hash.
    f3 = tmp_path / "c.csv"
    f3.write_bytes(b"hello,world\n3,4\n")
    assert sha256_of_file(f1) != sha256_of_file(f3)


def test_iter_rows_respects_sample_limit(tmp_path):
    csv = tmp_path / "small.csv"
    csv.write_text("col1,col2\nA,1\nB,2\nC,3\nD,4\nE,5\n", encoding="utf-8")
    rows = list(iter_rows(csv, sample_rows=3))
    assert len(rows) == 3
    assert rows[0] == {"col1": "A", "col2": "1"}


def test_iter_rows_sample_zero_reads_all(tmp_path):
    csv = tmp_path / "small.csv"
    csv.write_text("col1\nA\nB\nC\n", encoding="utf-8")
    rows = list(iter_rows(csv, sample_rows=0))
    assert len(rows) == 3


def test_iter_rows_preserves_strings_not_pandas_NaN(tmp_path):
    """We pass dtype=str + keep_default_na=False so empty cells stay
    as empty strings, not NaN (JSONB serialisation would choke)."""
    csv = tmp_path / "small.csv"
    csv.write_text("col1,col2\nA,\n,B\n", encoding="utf-8")
    rows = list(iter_rows(csv, sample_rows=0))
    assert rows[0] == {"col1": "A", "col2": ""}
    assert rows[1] == {"col1": "", "col2": "B"}


# ─── Silver projection (Bronze→Silver) shape tests ─────────────────────


def test_project_customer_row_happy_path():
    raw = {
        "customer_id": "abc",
        "customer_unique_id": "uniq-1",
        "customer_state": "SP",
    }
    out = project_customer_row(raw)
    assert out is not None
    assert out["customer_external_id"] == "uniq-1"
    assert out["segment"] == "SP"
    assert out["acquisition_channel"] == "olist_marketplace"


def test_project_customer_row_skips_when_no_id():
    assert project_customer_row({"customer_state": "SP"}) is None


def test_project_order_row_happy_path():
    raw = {
        "order_id": "ord-1",
        "customer_id": "cust-1",
        "order_status": "delivered",
        "order_purchase_timestamp": "2018-03-15 10:00:00",
        "order_delivered_customer_date": "2018-03-20 14:00:00",
    }
    out = project_order_row(raw)
    assert out is not None
    assert out["order_external_id"] == "ord-1"
    assert out["deal_status"] == "won"        # delivered → won
    assert out["created_at_source"].year == 2018
    assert out["closed_at"].month == 3


def test_project_order_row_maps_canceled_to_cancelled():
    out = project_order_row({"order_id": "x", "order_status": "canceled"})
    assert out["deal_status"] == "cancelled"


def test_project_order_row_maps_unknown_status_to_pending():
    out = project_order_row({"order_id": "x", "order_status": "weird"})
    assert out["deal_status"] == "pending"


def test_project_review_row_csat_2_or_lower_is_escalated():
    raw = {
        "review_id": "rev-1",
        "customer_id": "cust-1",
        "review_score": "1",
        "review_creation_date": "2018-04-01 09:00:00",
        "review_answer_timestamp": "2018-04-02 09:00:00",
    }
    out = project_review_row(raw)
    assert out is not None
    assert out["csat_rating"] == 1.0
    assert out["escalated"] is True


def test_project_review_row_csat_5_is_not_escalated():
    raw = {"review_id": "rev-2", "review_score": "5"}
    out = project_review_row(raw)
    assert out["csat_rating"] == 5.0
    assert out["escalated"] is False


def test_project_payment_row_returns_value():
    raw = {"order_id": "ord-1", "payment_value": "100.50"}
    out = project_payment_row(raw)
    assert out == {"order_id": "ord-1", "payment_value": 100.50}


def test_project_payment_row_skips_when_no_value():
    assert project_payment_row({"order_id": "ord-1"}) is None
    assert project_payment_row({"order_id": "ord-1", "payment_value": ""}) is None


def test_aggregate_finance_periods_rolls_by_month():
    """Two payments in same month accumulate; different months bucket separately."""
    from datetime import datetime, timezone
    payments = [
        {"order_id": "o1", "payment_value": 100.0},
        {"order_id": "o2", "payment_value": 200.0},
        {"order_id": "o3", "payment_value": 50.0},
    ]
    order_index = {
        "o1": datetime(2018, 3, 1, tzinfo=timezone.utc),
        "o2": datetime(2018, 3, 20, tzinfo=timezone.utc),
        "o3": datetime(2018, 4, 1, tzinfo=timezone.utc),
    }
    out = aggregate_finance_periods(payments, order_index)
    assert len(out) == 2
    march = next(r for r in out if r["period"] == "2018-03-01")
    april = next(r for r in out if r["period"] == "2018-04-01")
    assert march["revenue"] == 300.0
    assert april["revenue"] == 50.0
    # Other P&L columns are NULL — Build Week deliberately leaves them
    # for the Phase 2 ETL.
    assert march["cogs"] is None
    assert march["operating_expense"] is None


def test_aggregate_finance_periods_skips_unknown_orders():
    """Payment whose order_id isn't in the index is dropped (no period)."""
    out = aggregate_finance_periods(
        [{"order_id": "unknown", "payment_value": 99.0}],
        order_index={},
    )
    assert out == []
