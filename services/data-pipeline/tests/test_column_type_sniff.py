"""
Unit tests for the value-based column helpers in column_mapper:
sniff_value_type / is_unnamed / header_looks_like_data.

These close the "every column detects as text" gap (the language dictionary
omits data_type on every field) and let /schema flag the blank "Unnamed: N"
columns + data-as-header rows that overwhelm step-2.
"""
from data_pipeline.data_plane.bronze.column_mapper import (
    sniff_value_type, is_unnamed, header_looks_like_data,
)


# ── sniff_value_type ─────────────────────────────────────────────────────────

def test_sniff_integers():
    assert sniff_value_type(["1000", "2000", "3000"]) == "integer"


def test_sniff_floats_are_numeric():
    assert sniff_value_type(["12.5", "0.25", "100.0"]) == "numeric"


def test_sniff_thousands_separator_still_numeric():
    assert sniff_value_type(["1,000", "2,500", "3,750"]) == "integer"


def test_sniff_dates():
    assert sniff_value_type(["2024-04-17", "2024-05-01"]) == "date"
    assert sniff_value_type(["17/04/2024", "01/05/2024"]) == "date"


def test_sniff_datetime_with_time():
    assert sniff_value_type(["2024-04-17 00:00:00", "2024-05-01 13:30:00"]) == "date"


def test_sniff_mixed_returns_none():
    # one non-numeric value collapses the guess
    assert sniff_value_type(["10", "20", "N/A"]) is None


def test_sniff_text_returns_none():
    assert sniff_value_type(["R0", "R1", "R2"]) is None


def test_sniff_empty_returns_none():
    assert sniff_value_type([]) is None
    assert sniff_value_type([None, "", "  "]) is None


def test_sniff_leading_zero_id_not_a_number():
    # phone / zip / id — must NOT be coerced to numeric
    assert sniff_value_type(["0901234567", "0912345678"]) is None


def test_sniff_ignores_blanks_among_values():
    assert sniff_value_type(["5", None, "9", ""]) == "integer"


# ── is_unnamed ───────────────────────────────────────────────────────────────

def test_is_unnamed_pandas_autoname():
    assert is_unnamed("Unnamed: 3") is True
    assert is_unnamed("Unnamed: 17") is True
    assert is_unnamed("unnamed:5") is True


def test_is_unnamed_blank():
    assert is_unnamed("") is True
    assert is_unnamed("   ") is True


def test_is_unnamed_real_column():
    assert is_unnamed("amount") is False
    assert is_unnamed("Mã KH") is False


# ── header_looks_like_data ───────────────────────────────────────────────────

def test_header_looks_like_data_date():
    assert header_looks_like_data("2024-04-17 00:00:00") is True
    assert header_looks_like_data("17/04/2024") is True


def test_header_looks_like_data_number():
    assert header_looks_like_data("1000") is True


def test_header_real_name_is_not_data():
    assert header_looks_like_data("amount") is False
    assert header_looks_like_data("Mã KH") is False


def test_header_unnamed_is_not_flagged_as_data():
    assert header_looks_like_data("Unnamed: 3") is False
