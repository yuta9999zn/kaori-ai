"""Stage 4 bias examination — EU AI Act Art 10 (ADR-0041, Layer 3).

Deterministic representativeness check: detect sensitive/proxy attributes by
name and flag distributional imbalance (one category dominating). Pure, no LLM,
no I/O — mirrors quality.py. Attached to the scorecard as a separate `bias`
report (NOT folded into the weighted 7-dim overall).

Thresholds env-configurable (no-hardcode):
  KAORI_BIAS_DOMINANT_SHARE  default 0.8  — dominant category share that flags imbalance
  KAORI_BIAS_MIN_ROWS        default 30   — below this, representativeness is not meaningful
"""
from __future__ import annotations

import os
from typing import Any

import pandas as pd


SENSITIVE_ATTRIBUTE_HINTS: tuple[str, ...] = (
    "gender", "sex", "gioi_tinh", "gioitinh",
    "age", "tuoi", "do_tuoi",
    "region", "province", "tinh", "thanh_pho", "thanhpho", "city",
    "marital", "hon_nhan", "honnhan",
    "ethnic", "dan_toc", "dantoc",
    "religion", "ton_giao", "tongiao",
    "disab", "khuyet_tat", "khuyettat",
    "national", "quoc_tich", "quoctich",
)


def _dominant_share_threshold() -> float:
    try:
        return float(os.getenv("KAORI_BIAS_DOMINANT_SHARE", "0.8"))
    except (TypeError, ValueError):
        return 0.8


def _min_rows() -> int:
    try:
        return int(os.getenv("KAORI_BIAS_MIN_ROWS", "30"))
    except (TypeError, ValueError):
        return 30


def detect_sensitive_columns(columns) -> list:
    """Return columns whose name matches a sensitive/proxy hint (substring,
    case-insensitive). Pure."""
    out: list = []
    for c in columns:
        name = str(c).lower()
        if any(h in name for h in SENSITIVE_ATTRIBUTE_HINTS):
            out.append(c)
    return out


def examine_bias(df: pd.DataFrame, data_types: dict) -> dict[str, Any]:
    """Representativeness bias examination (Art 10). Flags sensitive columns
    whose dominant category share exceeds the threshold. Total — never raises.

    `data_types` is accepted for signature symmetry with the other Stage-4
    functions + reserved for future proxy-detection; representativeness uses
    value-counts directly so it does not need it today.
    """
    threshold = _dominant_share_threshold()
    min_rows = _min_rows()

    if df is None or len(df) == 0:
        return {"checked_columns": [], "findings": [], "status": "not_applicable",
                "row_count": 0}

    sensitive = [c for c in detect_sensitive_columns(df.columns) if c in df.columns]
    if not sensitive:
        return {"checked_columns": [], "findings": [], "status": "not_applicable",
                "row_count": int(len(df))}

    checked: list = []
    findings: list[dict] = []
    for col in sensitive:
        series = df[col].dropna()
        if len(series) < min_rows:
            continue
        checked.append(col)
        counts = series.astype(str).value_counts()
        if len(counts) == 0:
            continue
        top_value = str(counts.index[0])
        top_count = int(counts.iloc[0])
        n = int(len(series))
        dominant_share = top_count / n
        if dominant_share > threshold:
            findings.append({
                "column":          col,
                "code":            "BIAS_REPRESENTATION_IMBALANCE",
                "severity":        "high" if dominant_share > 0.95 else "medium",
                "message":         (
                    f"Cột nhạy cảm '{col}': giá trị '{top_value}' chiếm "
                    f"{dominant_share*100:.1f}% — dữ liệu mất cân bằng đại diện, "
                    f"có thể gây thiên lệch (EU AI Act Art 10)."
                ),
                "dominant_value":  top_value,
                "dominant_share":  round(dominant_share, 4),
                "distinct_values": int(len(counts)),
            })

    if not checked:
        status = "not_applicable"
    elif findings:
        status = "flagged"
    else:
        status = "ok"
    return {"checked_columns": checked, "findings": findings,
            "status": status, "row_count": int(len(df))}
