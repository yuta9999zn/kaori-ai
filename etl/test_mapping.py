"""
Demonstrates multilingual column detection against synthetic SME data.

Run from project root:
  python etl/test_mapping.py

Simulates three realistic messy sheets:
  1. RJ inventory sheet — Japanese + Vietnamese mixed
  2. NB customer session sheet — Vietnamese with inconsistent headers
  3. Mixed EN/JA revenue sheet
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
from utils.excel_parser import detect_columns, _norm

# ANSI colour codes for terminal output
_R  = "\033[91m"   # red   — UNKNOWN
_Y  = "\033[93m"   # yellow — LOW / MEDIUM
_G  = "\033[92m"   # green  — HIGH
_B  = "\033[94m"   # blue   — header
_RS = "\033[0m"    # reset

CONF_COLOR = {"HIGH": _G, "MEDIUM": _Y, "LOW": _Y, "UNKNOWN": _R}
CONF_ICON  = {"HIGH": "✓", "MEDIUM": "?", "LOW": "?", "UNKNOWN": "✗"}


def _print_table(title: str, df: pd.DataFrame, matches: list):
    print(f"\n{_B}{'='*68}{_RS}")
    print(f"{_B}  {title}{_RS}")
    print(f"{_B}  Columns found: {list(df.columns)}{_RS}")
    print(f"{'='*68}")
    print(f"  {'Raw column':<28} {'→ Canonical':<18} {'Conf':<8} {'Score':>5}  Reason")
    print(f"  {'-'*28} {'-'*18} {'-'*8} {'-'*5}  {'-'*30}")

    for m in matches:
        color = CONF_COLOR[m.confidence]
        icon  = CONF_ICON[m.confidence]
        canonical = m.canonical or "???"
        lang_note = f"[{m.matched_lang}]" if m.matched_lang else ""
        alias_note = f" via '{m.matched_alias}'" if m.matched_alias else ""
        reason_short = f"{lang_note}{alias_note}" if m.canonical else "— needs user_override"
        print(f"  {color}{icon}{_RS} {m.raw_name:<27} "
              f"{canonical:<18} {m.confidence:<8} {m.score:>5}  {reason_short}")

    high    = sum(1 for m in matches if m.confidence == "HIGH")
    medium  = sum(1 for m in matches if m.confidence == "MEDIUM")
    low     = sum(1 for m in matches if m.confidence == "LOW")
    unknown = sum(1 for m in matches if m.confidence == "UNKNOWN")

    print(f"\n  Summary: {_G}{high} HIGH{_RS}  {_Y}{medium} MEDIUM  {low} LOW{_RS}  "
          f"{_R}{unknown} UNKNOWN{_RS}")

    if unknown:
        needs = [m.raw_name for m in matches if m.confidence == "UNKNOWN"]
        print(f"  {_R}→ Set user_override for: {needs}{_RS}")


# ---------------------------------------------------------------------------
# Test 1: RJ inventory sheet (Japanese primary, some Vietnamese)
# ---------------------------------------------------------------------------

def test_rj_inventory():
    data = {
        "日付":      ["2026-04-01", "2026-04-02", "2026-04-03"],
        "商品名":    ["セラム A", "クリーム B", "オイル C"],
        "在庫":      ["100", "80", "60"],
        "使う":      ["10",  "15",  "5"],
        "残り":      ["90",  "65",  "55"],
        "売上":      ["500000", "750000", "250000"],
        "担当":      ["Yamada", "Tanaka", "Yamada"],
        "備考":      ["", "補充予定", ""],
    }
    df = pd.DataFrame(data)
    matches = detect_columns(df)
    _print_table("TEST 1: RJ Inventory Sheet (Japanese)", df, matches)


# ---------------------------------------------------------------------------
# Test 2: NB customer session (Vietnamese, inconsistent headers)
# ---------------------------------------------------------------------------

def test_nb_customers():
    data = {
        "Ngày":           ["01/04/2026", "02/04/2026", "02/04/2026"],
        "Tên KH":         ["Nguyen Thi A", "Tran Van B", "Le Thi C"],
        "SDT":            ["0901234567", "0912345678", ""],
        "Dịch vụ":        ["Triệt lông nách", "Trị nám", "Triệt lông chân"],
        "Vùng điều trị":  ["Nách", "Mặt", "Chân"],
        "Thanh toán":     ["500000", "800000", "600000"],
        "KTV":            ["Hoa", "Mai", "Hoa"],
        "Còn lại":        ["2", "0", "3"],         # remaining sessions
        "Ghi chú":        ["", "VIP", ""],
    }
    df = pd.DataFrame(data)
    matches = detect_columns(df)
    _print_table("TEST 2: NB Customer Session Sheet (Vietnamese)", df, matches)


# ---------------------------------------------------------------------------
# Test 3: Mixed EN/JA revenue + inventory
# ---------------------------------------------------------------------------

def test_mixed_revenue():
    data = {
        "Date":           ["2026-04-01", "2026-04-02"],
        "店舗":           ["RJ BAR", "BAR MINI"],
        "売上高":         ["1500000", "900000"],
        "Cash":           ["800000", "400000"],
        "Chuyển khoản":   ["500000", "300000"],
        "Card":           ["200000", "200000"],
        "客数":           ["12", "8"],
        "在庫残":         ["50", "30"],
        "Nhân viên":      ["Minh", "Lan"],
        "Column_Z":       ["???", "???"],   # completely unknown column
    }
    df = pd.DataFrame(data)
    matches = detect_columns(df)
    _print_table("TEST 3: Mixed EN/JA/VI Revenue + Inventory Sheet", df, matches)


# ---------------------------------------------------------------------------
# Test 4: Worst-case — headers are unusual/abbreviated
# ---------------------------------------------------------------------------

def test_edge_cases():
    data = {
        "DT":          ["2026-04-01", "2026-04-02"],   # abbreviated date
        "TM":          ["500000", "300000"],            # abbreviated cash (tiền mặt)
        "CK":          ["200000", "100000"],            # abbreviated transfer (chuyển khoản)
        "SL KH":       ["5", "3"],                     # abbreviated customer count
        "NV":          ["Hoa", "Mai"],                  # abbreviated staff
        "DỊCH VỤ":     ["Triệt lông", "Nám"],
        "DT1":         ["700000", "400000"],            # ambiguous — revenue? date?
        "tong":        ["700000", "400000"],            # truncated Vietnamese
    }
    df = pd.DataFrame(data)
    matches = detect_columns(df)
    _print_table("TEST 4: Abbreviated / Edge-Case Headers", df, matches)


# ---------------------------------------------------------------------------
# Test 5: Korean inventory
# ---------------------------------------------------------------------------

def test_korean_inventory():
    data = {
        "날짜":     ["2026-04-01", "2026-04-02"],
        "제품명":   ["세럼 A", "크림 B"],
        "재고":     ["100", "85"],
        "사용량":   ["15", "10"],
        "잔여":     ["85", "75"],
        "매출":     ["450000", "300000"],
        "직원":     ["Kim", "Lee"],
    }
    df = pd.DataFrame(data)
    matches = detect_columns(df)
    _print_table("TEST 5: Korean Inventory Sheet", df, matches)


# ---------------------------------------------------------------------------
# Test 6: Zaike Osake-style wide format (repeating metric groups)
# ---------------------------------------------------------------------------

def test_wide_format_pivot():
    from utils.wide_format import detect_wide_format, pivot_wide_to_long, enrich_labels

    # Simulate what pandas produces when it reads the Zaike Osake sheet:
    # 5-column groups: Get(Mua), 在庫(Tổng), 使う(Sử Dụng), nokoru(Còn Lại), total
    # pandas appends .1, .2, ... for duplicates; later groups drop the annotations
    data = {
        "Unnamed: 0":          ["1", "2", "3"],
        "Get(Mua)":            ["5",  "2", "2"],
        "在庫(Tổng)":          ["-1", "4", "4"],
        "使う(Sử Dụng)":       ["0",  "2", "2"],
        "nokoru(Còn Lại)":     ["4",  "4", "2"],
        "total":               ["2850000", "1140000", "1140000"],
        # pandas-renamed group 2
        "Get(Mua).1":          ["1",  "1", "0"],
        "在庫(Tổng).1":        ["2",  "3", "2"],
        "使う(Sử Dụng).1":     ["0",  "1", "0"],
        "nokoru(Còn Lại).1":   ["3",  "2", "2"],
        "total.1":             ["1140000", "1140000", "0"],
        # pandas-renamed group 3 (annotations dropped in source file)
        "Get":                 ["1",  "0", "1"],
        "在庫":                ["3",  "3", "3"],
        "使う":                ["0",  "0", "1"],
        "nokoru":              ["3",  "3", "2"],
        "total.2":             ["1300000", "1300000", "1300000"],
    }
    df = pd.DataFrame(data)

    print(f"\n{_B}{'='*68}{_RS}")
    print(f"{_B}  TEST 6: Wide-Format Detection + Pivot (Zaike Osake pattern){_RS}")
    print(f"  Input: {len(df.columns)} columns, {len(df)} rows (wide format){_RS}")
    print(f"{'='*68}")

    # Step 1: detection
    info = detect_wide_format(df, min_repeats=3)
    if info is None:
        print(f"  {_R}✗ FAIL: Wide format NOT detected{_RS}")
        return

    print(f"  {_G}✓ Wide format detected{_RS}")
    print(f"    Groups: {info.group_count}")
    print(f"    Metrics per group: {info.metric_names}")
    print(f"    Standalone cols: {info.standalone_cols}")

    # Simulate label enrichment without a real file (use synthetic labels)
    info.product_labels = ["Sake_A", "Sake_B", "Whisky_C"]

    # Step 2: pivot
    long_df = pivot_wide_to_long(df, info)
    print(f"\n  After pivot: {len(long_df)} rows × {len(long_df.columns)} columns")
    print(f"  Columns: {list(long_df.columns)}")
    print(f"\n  First 6 rows:")
    for i, row in long_df.head(6).iterrows():
        print(f"    {dict(row)}")

    # Step 3: column detection on pivoted df
    print(f"\n  Column detection on pivoted output:")
    matches = detect_columns(long_df)
    _print_table("TEST 6 (pivoted df)", long_df, matches)

    # ------------------------------------------------------------------
    # Step 4: melt_to_silver_schema — final transformation
    # Build effective_mapping exactly as SheetReport.effective_mapping does:
    #   canonical → raw_col_name (using detection results)
    # ------------------------------------------------------------------
    from utils.wide_format import melt_to_silver_schema

    effective_mapping: dict[str, str] = {}
    for m in matches:
        canon = m.canonical
        if canon:
            effective_mapping[canon] = m.raw_name
    # "product" col is added by pivot_wide_to_long, not by detect_columns
    if "product" not in effective_mapping and "product" in long_df.columns:
        effective_mapping["product"] = "product"

    print(f"\n  {'='*68}")
    print(f"  STEP 4 — melt_to_silver_schema()")
    print(f"  {'='*68}")
    print(f"  effective_mapping = {effective_mapping}")

    silver_df = melt_to_silver_schema(long_df, effective_mapping, "RJ_BAR", "RJ_Katamono_4.2026.xlsx")

    print(f"\n  Output schema: {list(silver_df.columns)}")
    print(f"  Total rows: {len(silver_df)}  "
          f"({info.group_count} products × {len([k for k in effective_mapping if k in ['inventory','usage','remaining','quantity','amount']])} metrics "
          f"× {len(long_df) // info.group_count} source rows)")
    print(f"\n  First 10 rows:")
    print(f"  {'date':<6}  {'product_name':<12}  {'metric_type':<12}  {'value':>10}  {'store':<8}")
    print(f"  {'-'*6}  {'-'*12}  {'-'*12}  {'-'*10}  {'-'*8}")
    for _, row in silver_df.head(10).iterrows():
        print(f"  {str(row['date']):<6}  {str(row['product_name']):<12}  "
              f"{str(row['metric_type']):<12}  {str(row['value']):>10}  {str(row['store']):<8}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"\n{_B}Kaori — Multilingual Column Detection Test{_RS}")
    print(f"{_B}Language dictionary: config/language_dictionary.json{_RS}")
    print(f"{_B}Fields covered: EN / VI / JA / KO / ZH{_RS}")

    test_rj_inventory()
    test_nb_customers()
    test_mixed_revenue()
    test_edge_cases()
    test_korean_inventory()
    test_wide_format_pivot()

    print(f"\n{_B}{'='*68}{_RS}")
    print(f"{_B}  All tests complete.{_RS}")
    print(f"  Columns marked UNKNOWN need user_override in the mapping JSON.")
    print(f"  To improve detection: add aliases to config/language_dictionary.json")
    print(f"{_B}{'='*68}{_RS}\n")
