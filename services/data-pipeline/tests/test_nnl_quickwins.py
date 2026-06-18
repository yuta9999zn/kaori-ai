"""
Tests for the NNL-Harness robustness ports (Phase 1 quick-wins):

  A2  excel_parser._detect_encoding picks the right charset (no latin-1 mojibake)
  A3  sniff_value_type tolerates light noise instead of all-or-nothing
  A4  rule_parse_currency disambiguates thousand/decimal separators by locale

(A1 day-first/month-first inference already landed on main separately, so it is
not re-tested here.) The existing white-box suites (test_unit_whitebox,
test_column_type_sniff) lock in the unchanged common-case behaviour; this file
covers the new capabilities.
"""
import io

import pandas as pd

from data_pipeline.data_plane.silver.rule_catalog import rule_parse_currency
from data_pipeline.data_plane.bronze.column_mapper import sniff_value_type
from utils.excel_parser import ExcelParser, _detect_encoding


# ── A2: encoding detection ───────────────────────────────────────────────────

def test_detect_encoding_cp1252_pound_decodes_clean():
    raw = "price\n£100".encode("cp1252")
    enc = _detect_encoding(raw)
    assert "£" in raw.decode(enc)            # detected enc must NOT mangle £


def test_detect_encoding_utf8_bom_handled():
    raw = "tên,tiền\nAn,1000".encode("utf-8-sig")
    enc = _detect_encoding(raw)
    # utf-8-sig must be chosen so the leading BOM (﻿) is stripped on decode.
    first_field = raw.decode(enc).split(",")[0]
    assert first_field == "tên"


def test_parse_csv_cp1252_roundtrip():
    """End-to-end: a cp1252 file with £ survives ingest as £, not mojibake."""
    raw = "item,price\nbook,£100".encode("cp1252")
    sheets = ExcelParser().parse(io.BytesIO(raw), filename="x.csv")
    rows = sheets[0]["rows"]
    assert any("£" in str(v) for v in rows[0].values())


# ── A3: noise-tolerant value sniffing ────────────────────────────────────────

def test_sniff_mostly_numeric_with_noise_is_integer():
    vals = [str(i) for i in range(100)] + ["N/A"]      # 100/101 ≈ 0.99 ≥ 0.95
    assert sniff_value_type(vals) == "integer"


def test_sniff_mostly_decimal_with_noise_is_numeric():
    vals = [f"{i}.5" for i in range(100)] + ["n/a"]
    assert sniff_value_type(vals) == "numeric"


def test_sniff_still_none_when_genuinely_mixed():
    assert sniff_value_type(["10", "20", "N/A"]) is None    # 0.67 < 0.95 → text


def test_sniff_mostly_date_with_noise_is_date():
    vals = [f"2024-01-{d:02d}" for d in range(1, 29)] + ["??"]   # 28/29 ≈ 0.97
    assert sniff_value_type(vals) == "date"


# ── A4: locale-aware currency parsing ────────────────────────────────────────

def test_currency_us_decimal():
    out, parsed = rule_parse_currency(pd.DataFrame({"amount": ["$1,500.50"]}), "amount")
    assert out["amount"].iloc[0] == 1500.5 and parsed == 1


def test_currency_eu_decimal():
    out, _ = rule_parse_currency(pd.DataFrame({"amount": ["1.234,56"]}), "amount")
    assert out["amount"].iloc[0] == 1234.56


def test_currency_vn_dot_thousands():
    out, _ = rule_parse_currency(
        pd.DataFrame({"amount": ["1.500.000", "₫2.000.000"]}), "amount")
    assert out["amount"].tolist() == [1500000.0, 2000000.0]


def test_currency_single_dot_decimal_preserved():
    """A single dot with 1-2 trailing digits is a decimal, not VN thousands."""
    out, _ = rule_parse_currency(pd.DataFrame({"amount": ["12.50", "1.5"]}), "amount")
    assert out["amount"].tolist() == [12.5, 1.5]


def test_currency_comma_thousands_us():
    out, _ = rule_parse_currency(pd.DataFrame({"amount": ["1,234,567"]}), "amount")
    assert out["amount"].iloc[0] == 1234567.0
