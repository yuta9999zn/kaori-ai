"""
Wide-format Excel layout detection and pivot.

Handles sheets where the same group of metrics is repeated horizontally
for each product, e.g.:

  Row 0 (product labels, merged):  | Sake A       | Sake B       |
  Row 1 (header):  No | Get | 在庫 | 使う | nokoru | total | Get | 在庫 | ...
  Row 2:            1 |   5 |  -1 |    0 |      4 | 2850000 | 1 |   2 | ...

Pandas flattens this into duplicate column names:
  Get, 在庫, 使う, nokoru, total, Get(Mua).1, 在庫(Tổng).1, ...

This module detects that pattern and pivots to long format:
  [No, product, Get, 在庫, 使う, nokoru, total]
  [1, "Sake A",  5,  -1,   0,    4,  2850000]
  [1, "Sake B",  1,   2,   0,    3,  1140000]

After pivoting, detect_columns() maps:
  在庫   → inventory
  使う   → usage
  nokoru → remaining
  total  → amount
  Get    → quantity
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Column name normalisation
# ---------------------------------------------------------------------------

def _strip_annotation(s: str) -> str:
    """Remove parenthetical annotations: 'Get(Mua)' → 'Get', '在庫(Tổng)' → '在庫'."""
    return re.sub(r'[\(（][^)）]*[\)）]', '', str(s)).strip()


def _strip_pandas_suffix(s: str) -> str:
    """Remove pandas duplicate suffix: 'total.3' → 'total', '在庫.1' → '在庫'."""
    return re.sub(r'\.\d+$', '', str(s)).strip()


def base_name(col) -> str:
    """Canonical base name: strip annotation, then strip pandas suffix."""
    s = _strip_annotation(str(col))
    s = _strip_pandas_suffix(s)
    return s


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class WideFormatInfo:
    standalone_cols: list[str]       # columns NOT part of any repeating group (e.g. row index)
    metric_names: list[str]          # ordered base metric names in a single group
    group_count: int                 # number of product groups
    groups: list[list[str]]          # groups[i] = list of raw column names for group i
    product_labels: list[str]        # product_labels[i] = label for group i


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def detect_wide_format(df: pd.DataFrame, min_repeats: int = 3) -> WideFormatInfo | None:
    """
    Detect if a DataFrame has repeating column groups.

    A "repeating group" is identified when ≥ 2 base metric names each appear
    at least min_repeats times in the column list.

    Returns WideFormatInfo (without product_labels) or None.
    """
    cols = list(df.columns)
    bases = [base_name(c) for c in cols]

    counts = Counter(b for b in bases if b)  # ignore empty base names
    repeating = {name: cnt for name, cnt in counts.items() if cnt >= min_repeats}

    if len(repeating) < 2:
        return None   # Need at least 2 repeating metrics to form a group

    # Sanity check: all repeating metrics should appear a similar number of times
    freq = list(repeating.values())
    if max(freq) - min(freq) > max(3, max(freq) * 0.2):
        # Counts diverge too much — probably not a clean repeating layout
        return None

    num_groups = max(freq)
    group_size = len(repeating)

    # Separate standalone columns from repeating ones
    standalone = [col for col, b in zip(cols, bases) if b not in repeating]

    # Assign each repeating column to a group by tracking occurrence order
    base_occurrence: dict[str, int] = {}
    groups: list[list[str]] = [[] for _ in range(num_groups)]

    for col, b in zip(cols, bases):
        if b not in repeating:
            continue
        occ = base_occurrence.get(b, 0)
        if occ < num_groups:
            groups[occ].append(col)
        base_occurrence[b] = occ + 1

    # Determine metric names from the first complete group (in column order)
    # Sort first group's columns by their original position
    first_group = groups[0] if groups else []
    metric_names = [base_name(col) for col in first_group]

    return WideFormatInfo(
        standalone_cols=standalone,
        metric_names=metric_names,
        group_count=num_groups,
        groups=groups,
        product_labels=[],   # filled by read_label_row() + enrich_labels()
    )


# ---------------------------------------------------------------------------
# Product label extraction
# ---------------------------------------------------------------------------

def read_label_row(
    filepath: str,
    sheet_name: str,
    header_row_idx: int,
) -> pd.Series | None:
    """
    Read the row immediately above the detected header row.
    Returns a Series aligned to column positions (0-based integers), or None
    if header_row_idx == 0 (nothing above).

    Merged cells are forward-filled: the first cell of a merged range holds
    the value, subsequent cells are NaN → ffill propagates the label.
    """
    if header_row_idx < 1:
        return None

    try:
        raw = pd.read_excel(
            filepath,
            sheet_name=sheet_name,
            header=None,
            dtype=str,
            engine="openpyxl",
        )
    except Exception:
        return None

    if header_row_idx - 1 >= len(raw):
        return None

    label_row = raw.iloc[header_row_idx - 1].ffill()
    return label_row


def enrich_labels(
    info: WideFormatInfo,
    df: pd.DataFrame,
    label_row: pd.Series | None,
) -> WideFormatInfo:
    """
    Fill info.product_labels by mapping each group's first column position
    to the label row.

    If label_row is None or a group has no label, uses "Product_N" fallback.
    """
    # Map column name → integer position in df
    col_pos: dict[str, int] = {col: i for i, col in enumerate(df.columns)}

    labels: list[str] = []
    for i, group_cols in enumerate(info.groups):
        label = f"Product_{i + 1}"   # fallback
        if label_row is not None and group_cols:
            first_col = group_cols[0]
            pos = col_pos.get(first_col)
            if pos is not None and pos < len(label_row):
                raw_label = str(label_row.iloc[pos]).strip()
                if raw_label and raw_label.lower() not in ("nan", "none", ""):
                    label = raw_label
        labels.append(label)

    info.product_labels = labels
    return info


# ---------------------------------------------------------------------------
# Pivot: wide → long
# ---------------------------------------------------------------------------

def pivot_wide_to_long(
    df: pd.DataFrame,
    info: WideFormatInfo,
) -> pd.DataFrame:
    """
    Convert a wide-format DataFrame (repeating metric groups) to long format.

    Input:  each row has N groups × M metrics laid out horizontally
    Output: each row represents one group per original row

    Output columns:
      [standalone_cols...] + [product] + [metric_names...]

    Metric column names are the base names (annotation + suffix stripped),
    so detect_columns() can map them via the language dictionary:
        在庫   → inventory
        使う   → usage
        nokoru → remaining
        total  → amount
        Get    → quantity
    """
    rows: list[dict] = []

    for _, src_row in df.iterrows():
        # Values from standalone columns (shared across all groups in this row)
        standalone_vals = {col: src_row.get(col, "") for col in info.standalone_cols}

        for i, group_cols in enumerate(info.groups):
            product = (info.product_labels[i]
                       if i < len(info.product_labels)
                       else f"Product_{i + 1}")
            out_row = dict(standalone_vals)
            out_row["product"] = product

            # Map metric base_name → value for this group
            for col, metric in zip(group_cols, info.metric_names):
                out_row[metric] = src_row.get(col, "")

            rows.append(out_row)

    if not rows:
        return df   # Fallback: return original if pivot produces nothing

    result = pd.DataFrame(rows)

    # Enforce column order: standalone → product → metrics
    ordered_cols = (
        [c for c in info.standalone_cols if c in result.columns]
        + ["product"]
        + [m for m in info.metric_names if m in result.columns]
    )
    extra = [c for c in result.columns if c not in ordered_cols]
    return result[ordered_cols + extra]


# ---------------------------------------------------------------------------
# Convenience: detect + enrich + pivot in one call
# ---------------------------------------------------------------------------

def maybe_pivot(
    df: pd.DataFrame,
    filepath: str,
    sheet_name: str,
    header_row_idx: int,
    logger=None,
    min_repeats: int = 3,
) -> tuple[pd.DataFrame, WideFormatInfo | None]:
    """
    Attempt wide-format detection and pivot.

    Returns (df, info):
      - If wide format detected: (pivoted_df, WideFormatInfo)
      - Otherwise:               (original_df, None)
    """
    def _log(msg: str) -> None:
        if logger:
            logger.info(msg)

    info = detect_wide_format(df, min_repeats=min_repeats)
    if info is None:
        return df, None

    _log(f"  [WIDE] Sheet '{sheet_name}': detected {info.group_count} repeating groups "
         f"of {len(info.metric_names)} metrics ({info.metric_names})")

    label_row = read_label_row(filepath, sheet_name, header_row_idx)
    info = enrich_labels(info, df, label_row)

    _log(f"  [WIDE] Product labels: {info.product_labels[:5]}"
         f"{'...' if len(info.product_labels) > 5 else ''}")

    pivoted = pivot_wide_to_long(df, info)
    _log(f"  [WIDE] Pivoted: {len(df)} source rows × {info.group_count} groups "
         f"→ {len(pivoted)} long rows  columns={list(pivoted.columns)}")

    return pivoted, info


# ---------------------------------------------------------------------------
# Inventory metric canonical names
# After pivoting, detect_columns() maps raw metric cols to these values.
# melt_to_silver_schema() uses this set to identify which columns to melt.
# ---------------------------------------------------------------------------

INVENTORY_METRICS = {"inventory", "usage", "remaining", "quantity", "amount"}


# ---------------------------------------------------------------------------
# Final melt: pivoted intermediate → Silver target schema
#
# Input (pivoted):
#   [Unnamed: 0, product, Get, 在庫, 使う, nokoru, total]  ← raw col names
#
# After applying effective_mapping (canonical → raw):
#   effective_mapping = {
#       "quantity":  "Get",
#       "inventory": "在庫",
#       "usage":     "使う",
#       "remaining": "nokoru",
#       "amount":    "total",
#       "product":   "product",    ← added automatically by pivot
#   }
#
# Output (melted Silver schema):
#   [date, product_name, metric_type, value, store, source_file]
#   ["1",  "Sake_A",     "inventory", "-1",  "CH_A", "..."]
#   ["1",  "Sake_A",     "usage",     "0",   "CH_A", "..."]
#   ...
# ---------------------------------------------------------------------------

def melt_to_silver_schema(
    df: pd.DataFrame,
    effective_mapping: dict[str, str],
    store: str,
    source_file: str,
) -> pd.DataFrame:
    """
    Transform a pivoted intermediate df into Silver inventory schema.

    effective_mapping: canonical → raw_col_name  (from SheetReport.effective_mapping)
    store:             store code, e.g. "CH_A"
    source_file:       original filename for traceability

    Returns a DataFrame with columns:
      [date, product_name, metric_type, value, store, source_file]
    One row per (source_row × metric_type).
    Returns empty DataFrame (same schema) if no metric columns can be found.
    """
    # Invert: raw_col → canonical  (only keep metrics + date + product)
    raw_to_canonical: dict[str, str] = {}
    for canonical, raw in effective_mapping.items():
        if raw in df.columns:
            raw_to_canonical[raw] = canonical

    # Identify id columns (date/row_id and product)
    date_raw   = effective_mapping.get("date")
    # Fallback: any standalone column that isn't product or a metric
    if not date_raw:
        metric_raws = {effective_mapping.get(m) for m in INVENTORY_METRICS}
        product_raw = effective_mapping.get("product", "product")
        for col in df.columns:
            if col not in metric_raws and col != product_raw:
                date_raw = col
                break

    product_raw = effective_mapping.get("product", "product")

    # Identify metric columns: raw col names whose canonical is in INVENTORY_METRICS
    metric_cols = [
        raw for raw, can in raw_to_canonical.items()
        if can in INVENTORY_METRICS and raw in df.columns
    ]

    if not metric_cols:
        return pd.DataFrame(
            columns=["date", "product_name", "metric_type", "value", "store", "source_file"]
        )

    # Build a working subset: [date_col, product_col, metric_col_1, ...]
    id_vars_raw = [c for c in [date_raw, product_raw] if c and c in df.columns]
    value_vars  = metric_cols

    # Rename metric columns to their canonical names before melting
    # so metric_type values are English (inventory, usage, …) not raw JA/VI
    rename_map = {raw: raw_to_canonical[raw] for raw in value_vars}
    work = df[id_vars_raw + value_vars].copy()
    work = work.rename(columns=rename_map)

    canonical_value_vars = [rename_map[r] for r in value_vars]

    melted = work.melt(
        id_vars=[c for c in id_vars_raw],   # original raw names still in work df
        value_vars=canonical_value_vars,
        var_name="metric_type",
        value_name="value",
    )

    # Standardise id column names regardless of what the raw file called them
    rename_final: dict[str, str] = {}
    if date_raw and date_raw in melted.columns:
        rename_final[date_raw] = "date"
    if product_raw and product_raw in melted.columns:
        rename_final[product_raw] = "product_name"
    melted = melted.rename(columns=rename_final)

    # Attach metadata
    melted["store"]       = store
    melted["source_file"] = source_file

    # Drop empty / null values — no point writing blank rows to Silver
    melted = melted[
        melted["value"].notna()
        & (melted["value"].astype(str).str.strip() != "")
        & (melted["value"].astype(str).str.lower() != "nan")
    ].reset_index(drop=True)

    return melted[["date", "product_name", "metric_type", "value", "store", "source_file"]]
