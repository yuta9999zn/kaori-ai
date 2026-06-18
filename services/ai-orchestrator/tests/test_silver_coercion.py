"""
Tests for reasoning.legacy_analytics.runner._coerce_numeric.

Silver ``row_data`` is JSONB and the schema dictionary types every column
as ``text`` (no per-field data_type yet), so numeric values arrive as
JSON strings ("8395"). The statistical engines select numeric columns via
``select_dtypes(include="number")`` and would see none. _coerce_numeric
restores numeric dtype on read while leaving identifier-like text alone.
"""
import pandas as pd
import pytest

from ai_orchestrator.reasoning.legacy_analytics.runner import (
    _coerce_numeric, _drop_empty_columns,
)


# ── _drop_empty_columns ──────────────────────────────────────────────────────

def test_drop_fully_empty_column():
    df = _drop_empty_columns(pd.DataFrame({
        "amount":     ["100", "200", "300"],
        "ghi_chu":    [None, None, None],   # fully empty
        "unnamed_5":  ["", "  ", ""],        # blank/whitespace only
    }))
    assert "amount" in df.columns
    assert "ghi_chu" not in df.columns
    assert "unnamed_5" not in df.columns


def test_keep_column_with_any_data():
    # a sparse column with even one real value is kept (carries data)
    df = _drop_empty_columns(pd.DataFrame({
        "sparse": [None, "", "42"],
        "region": ["R0", "R1", "R2"],
    }))
    assert list(df.columns) == ["sparse", "region"]


def test_drop_empty_does_not_explode_on_all_empty():
    # degenerate frame — return as-is rather than an empty frame
    df = _drop_empty_columns(pd.DataFrame({"a": [None], "b": [""]}))
    assert len(df.columns) >= 1


def test_integer_string_column_becomes_numeric():
    df = _coerce_numeric(pd.DataFrame({"amount": ["8395", "5052", "5059"]}))
    assert pd.api.types.is_numeric_dtype(df["amount"])
    assert df["amount"].tolist() == [8395, 5052, 5059]


def test_float_string_column_becomes_numeric():
    df = _coerce_numeric(pd.DataFrame({"rate": ["12.5", "0.25", "100.0"]}))
    assert pd.api.types.is_numeric_dtype(df["rate"])
    assert df["rate"].tolist() == [12.5, 0.25, 100.0]


def test_non_numeric_text_stays_text():
    df = _coerce_numeric(pd.DataFrame({"region": ["R0", "R1", "R2"]}))
    assert df["region"].dtype == object
    assert df["region"].tolist() == ["R0", "R1", "R2"]


def test_mixed_numeric_and_text_stays_text():
    # A single non-numeric value keeps the whole column as text.
    df = _coerce_numeric(pd.DataFrame({"col": ["10", "20", "N/A"]}))
    assert df["col"].dtype == object


def test_leading_zero_identifier_stays_text():
    # Phone / zip / id columns are all-digits but must NOT be coerced —
    # to_numeric would strip the leading zero and mangle the identifier.
    df = _coerce_numeric(pd.DataFrame({"phone": ["0901234567", "0912345678"]}))
    assert df["phone"].dtype == object
    assert df["phone"].tolist() == ["0901234567", "0912345678"]


def test_numeric_column_with_nulls_is_coerced_and_nulls_kept():
    df = _coerce_numeric(pd.DataFrame({"qty": ["5", None, "9"]}))
    assert pd.api.types.is_numeric_dtype(df["qty"])
    assert df["qty"].iloc[0] == 5
    assert pd.isna(df["qty"].iloc[1])
    assert df["qty"].iloc[2] == 9


def test_already_numeric_column_unchanged():
    df = _coerce_numeric(pd.DataFrame({"n": [1, 2, 3]}))
    assert pd.api.types.is_numeric_dtype(df["n"])
    assert df["n"].tolist() == [1, 2, 3]


def test_mixed_dataframe_only_numeric_columns_coerced():
    df = _coerce_numeric(pd.DataFrame({
        "amount":   ["100", "200", "300"],
        "region":   ["R0", "R1", "R2"],
        "phone":    ["0901111111", "0902222222", "0903333333"],
        "quantity": ["3", "7", "11"],
    }))
    assert pd.api.types.is_numeric_dtype(df["amount"])
    assert pd.api.types.is_numeric_dtype(df["quantity"])
    assert df["region"].dtype == object
    assert df["phone"].dtype == object
    # Exactly the two real numeric columns are visible to the engine.
    assert df.select_dtypes(include="number").columns.tolist() == ["amount", "quantity"]
