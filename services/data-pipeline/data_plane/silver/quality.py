"""
Stage 4 — Quality Scorecard (7 dimensions per PIPELINE_UNIFIED.md).

Replaces the naive `_compute_quality()` null-rate. Now a sheet-aggregate
score computed once per cleaning run, with per-dimension breakdown the FE
can drill into.

Dimensions (weight in parentheses):

  1. completeness  (25%) — % non-null on REQUIRED canonical columns
  2. validity      (20%) — % values matching the column's expected pattern
  3. uniqueness    (15%) — % unique on primary-key column(s) for the purpose
  4. consistency   (15%) — cross-column rules (date_to > date_from, qty ≥ 0, …)
  5. timeliness    (10%) — % rows whose date column is within the freshness window
  6. accuracy      (10%) — % rows within plausible range (no 10B VND outliers, …)
  7. integrity     (5%)  — % rows whose customer_id appears in any existing master

Weights sum to 1.0. Overall = Σ dim * weight.

Each dimension produces a 0-1 float + an `issues` list (RFC-7807-shaped
items the FE can render as a quality drill-down). When a dimension is
N/A for the dataset (e.g. no date column → can't compute timeliness),
we mark it `null` and re-distribute its weight across the others so the
overall score stays comparable.

This is Phase-1 deliberately simple: rules are deterministic Python, no
LLM. Stage 4 LLM analytics (anomaly detection) lives in ai-orchestrator.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import pandas as pd
from .bias import examine_bias


# ─── Patterns + ranges (Vietnamese-aware) ────────────────────────

_VN_PHONE_E164 = re.compile(r"^\+84\d{9,10}$")
_VN_PHONE_LOCAL = re.compile(r"^0\d{9,10}$")
_EMAIL         = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DATE_ISO      = re.compile(r"^\d{4}-\d{2}-\d{2}")  # YYYY-MM-DD prefix

# Plausible ranges for VN business data — anything outside is flagged
# accuracy. Tunable per tenant later.
_AMOUNT_VND_MAX = 10_000_000_000   # 10B VND single tx — anything larger is almost certainly bad
_AMOUNT_VND_MIN = 0
_AGE_MAX        = 120
_QTY_MAX        = 1_000_000

# Timeliness window — rows older than this lose timeliness points.
_FRESHNESS_DAYS = 365


# Default weights — fall back if dimension is N/A (its weight is re-allocated)
DEFAULT_WEIGHTS = {
    "completeness": 0.25,
    "validity":     0.20,
    "uniqueness":   0.15,
    "consistency":  0.15,
    "timeliness":   0.10,
    "accuracy":     0.10,
    "integrity":    0.05,
}

# Canonical columns that count as REQUIRED for completeness, by sheet purpose.
# Aligned with PIPELINE_UNIFIED.md Stage 2.2 "ESSENTIAL" matrix.
_REQUIRED_BY_PURPOSE: dict[str, list[str]] = {
    "transaction_list":      ["customer_id", "transaction_date", "amount"],
    "customer_master":       ["customer_id"],
    "product_master":        ["product_id"],
    "order_list":            ["order_id", "customer_id", "amount", "transaction_date"],
    "inventory_movement":    ["product_id", "quantity", "transaction_date"],
}

# Primary-key column (uniqueness) per purpose.
_PK_BY_PURPOSE: dict[str, str] = {
    "transaction_list":   "transaction_id",
    "customer_master":    "customer_id",
    "product_master":     "product_id",
    "order_list":         "order_id",
}


# ─── Public entry point ──────────────────────────────────────────


def compute_scorecard(
    df:           pd.DataFrame,
    data_types:   dict[str, str],
    purpose:      Optional[str],
    *,
    existing_customer_ids: Optional[set[str]] = None,
) -> dict[str, Any]:
    """Compute 7-dim scorecard for one cleaned sheet.

    Args:
        df: silver-stage DataFrame (canonical column names, post-cleaning).
        data_types: canonical_name → detected data_type from Stage 2.
        purpose: sheet purpose label (transaction_list, customer_master, …).
        existing_customer_ids: optional set of customer_ids known to the
            master table — used for integrity check. None → integrity N/A.

    Returns:
        dict with keys: dimensions, weights, overall, issues, row_count.
    """
    if df is None or len(df) == 0:
        return {
            "dimensions": {k: None for k in DEFAULT_WEIGHTS},
            "weights":    DEFAULT_WEIGHTS,
            "overall":    0.0,
            "issues":     [{"code": "EMPTY_SHEET", "dim": None,
                            "severity": "high",
                            "message": "Sheet trống — không có dòng nào để chấm điểm.",
                            "count": 0}],
            "row_count":  0,
            "bias":       {"checked_columns": [], "findings": [],
                           "status": "not_applicable", "row_count": 0},
        }

    issues: list[dict] = []
    dims: dict[str, Optional[float]] = {}

    dims["completeness"] = _completeness(df, purpose, issues)
    dims["validity"]     = _validity(df, data_types, issues)
    dims["uniqueness"]   = _uniqueness(df, purpose, issues)
    dims["consistency"]  = _consistency(df, data_types, issues)
    dims["timeliness"]   = _timeliness(df, data_types, issues)
    dims["accuracy"]     = _accuracy(df, data_types, issues)
    dims["integrity"]    = _integrity(df, existing_customer_ids, issues)

    overall = _weighted_overall(dims, DEFAULT_WEIGHTS)
    return {
        "dimensions": dims,
        "weights":    DEFAULT_WEIGHTS,
        "overall":    round(overall, 4),
        "issues":     issues,
        "row_count":  int(len(df)),
        "bias":       examine_bias(df, data_types),
    }


def _weighted_overall(
    dims:    dict[str, Optional[float]],
    weights: dict[str, float],
) -> float:
    """Σ dim * weight — N/A dimensions drop out, surviving weights rescale."""
    active = {k: v for k, v in dims.items() if v is not None}
    if not active:
        return 0.0
    used_weight = sum(weights[k] for k in active)
    if used_weight == 0:
        return 0.0
    return sum(active[k] * weights[k] for k in active) / used_weight


# ─── Per-dimension computations ──────────────────────────────────


def _completeness(df: pd.DataFrame, purpose: Optional[str], issues: list) -> Optional[float]:
    """% non-null on REQUIRED columns. N/A if no required cols defined."""
    required = _REQUIRED_BY_PURPOSE.get(purpose or "", [])
    cols = [c for c in required if c in df.columns]
    if not cols:
        return None
    scores: list[float] = []
    for c in cols:
        non_null = df[c].notna().sum()
        rate = non_null / len(df) if len(df) else 0.0
        scores.append(rate)
        missing = len(df) - non_null
        if missing > 0:
            issues.append({
                "code":     "COMPLETENESS_NULLS",
                "dim":      "completeness",
                "severity": "high" if rate < 0.7 else "medium",
                "message":  f"Cột bắt buộc '{c}' có {missing} dòng null ({(1-rate)*100:.1f}%).",
                "count":    int(missing),
            })
    return float(sum(scores) / len(scores))


def _validity(df: pd.DataFrame, data_types: dict[str, str], issues: list) -> Optional[float]:
    """% values matching the column's expected pattern."""
    checks: list[float] = []
    for col, dtype in data_types.items():
        if col not in df.columns:
            continue
        series = df[col].dropna()
        if len(series) == 0:
            continue
        rate, bad_count = _validity_for_type(series, dtype)
        if rate is None:
            continue
        checks.append(rate)
        if bad_count > 0:
            issues.append({
                "code":     "VALIDITY_PATTERN_FAIL",
                "dim":      "validity",
                "severity": "high" if rate < 0.85 else "medium",
                "message":  f"Cột '{col}' ({dtype}): {bad_count} giá trị không khớp pattern.",
                "count":    int(bad_count),
            })
    if not checks:
        return None
    return float(sum(checks) / len(checks))


def _validity_for_type(series: pd.Series, dtype: str) -> tuple[Optional[float], int]:
    """Return (valid_rate, bad_count) for the column type, or (None, 0) if no checker."""
    n = len(series)
    if dtype == "phone":
        bad = sum(
            1 for v in series
            if not (_VN_PHONE_E164.match(str(v)) or _VN_PHONE_LOCAL.match(str(v)))
        )
    elif dtype == "email":
        bad = sum(1 for v in series if not _EMAIL.match(str(v).lower()))
    elif dtype == "date":
        bad = 0
        for v in series:
            if isinstance(v, (pd.Timestamp, datetime)):
                continue
            s = str(v).strip()
            try:
                pd.to_datetime(s)
            except Exception:
                bad += 1
    elif dtype in ("amount", "amount_vnd", "numeric", "integer"):
        bad = 0
        for v in series:
            try:
                float(str(v).replace(",", "").replace(".", "", str(v).count(".") - 1 if str(v).count(".") > 1 else 0))
            except (ValueError, TypeError):
                bad += 1
    else:
        return None, 0
    return (1 - bad / n) if n else 1.0, bad


def _uniqueness(df: pd.DataFrame, purpose: Optional[str], issues: list) -> Optional[float]:
    """% unique on the primary-key column for the purpose."""
    pk = _PK_BY_PURPOSE.get(purpose or "")
    if not pk or pk not in df.columns:
        return None
    series = df[pk].dropna()
    if len(series) == 0:
        return None
    unique_count = series.nunique()
    total = len(series)
    rate = unique_count / total
    dup_count = total - unique_count
    if dup_count > 0:
        issues.append({
            "code":     "UNIQUENESS_DUPLICATES",
            "dim":      "uniqueness",
            "severity": "high" if rate < 0.95 else "medium",
            "message":  f"Khóa chính '{pk}' có {dup_count} dòng trùng.",
            "count":    int(dup_count),
        })
    return float(rate)


def _consistency(df: pd.DataFrame, data_types: dict[str, str], issues: list) -> Optional[float]:
    """Cross-column rules: amount > 0, date_to > date_from, quantity ≥ 0."""
    rules_ran   = 0
    rules_passed = 0
    # Rule 1: amount ≥ 0 on transactional columns
    for col, dtype in data_types.items():
        if dtype in ("amount", "amount_vnd") and col in df.columns:
            series = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(series) == 0:
                continue
            rules_ran += 1
            negatives = int((series < 0).sum())
            if negatives == 0:
                rules_passed += 1
            else:
                issues.append({
                    "code":     "CONSISTENCY_NEGATIVE_AMOUNT",
                    "dim":      "consistency",
                    "severity": "medium",
                    "message":  f"Cột '{col}': {negatives} dòng có amount âm. Refund chăng?",
                    "count":    negatives,
                })
    # Rule 2: quantity ≥ 0
    for col in df.columns:
        if "quantity" in col.lower() or "qty" in col.lower():
            series = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(series) == 0:
                continue
            rules_ran += 1
            negatives = int((series < 0).sum())
            if negatives == 0:
                rules_passed += 1
            else:
                issues.append({
                    "code":     "CONSISTENCY_NEGATIVE_QUANTITY",
                    "dim":      "consistency",
                    "severity": "medium",
                    "message":  f"Cột '{col}': {negatives} dòng có quantity âm.",
                    "count":    negatives,
                })
    # Rule 3: date_to ≥ date_from when both present
    date_cols = [c for c in df.columns if "date_from" in c.lower() or "start_date" in c.lower()]
    end_cols  = [c for c in df.columns if "date_to" in c.lower() or "end_date" in c.lower()]
    if date_cols and end_cols:
        rules_ran += 1
        s_from = pd.to_datetime(df[date_cols[0]], errors="coerce")
        s_to   = pd.to_datetime(df[end_cols[0]],  errors="coerce")
        both   = s_from.notna() & s_to.notna()
        bad    = int(((s_to < s_from) & both).sum())
        if bad == 0:
            rules_passed += 1
        else:
            issues.append({
                "code":     "CONSISTENCY_DATE_ORDER",
                "dim":      "consistency",
                "severity": "high",
                "message":  f"{bad} dòng có ngày kết thúc < ngày bắt đầu.",
                "count":    bad,
            })
    if rules_ran == 0:
        return None
    return float(rules_passed / rules_ran)


def _timeliness(df: pd.DataFrame, data_types: dict[str, str], issues: list) -> Optional[float]:
    """% rows whose date column is within the freshness window."""
    date_col = next((c for c, t in data_types.items() if t == "date" and c in df.columns), None)
    if not date_col:
        return None
    parsed = pd.to_datetime(df[date_col], errors="coerce")
    valid = parsed.dropna()
    if len(valid) == 0:
        return None
    # Ensure timezone-naive comparison: strip tz from parsed if present.
    if valid.dt.tz is not None:
        valid = valid.dt.tz_convert(None)
    cutoff = pd.Timestamp.utcnow().tz_localize(None) - timedelta(days=_FRESHNESS_DAYS)
    fresh = int((valid >= cutoff).sum())
    rate  = fresh / len(valid)
    stale = len(valid) - fresh
    if stale > 0:
        issues.append({
            "code":     "TIMELINESS_STALE",
            "dim":      "timeliness",
            "severity": "low" if rate > 0.8 else "medium",
            "message":  f"{stale} dòng cũ hơn {_FRESHNESS_DAYS} ngày — có thể là dữ liệu lịch sử backfill.",
            "count":    stale,
        })
    return float(rate)


def _accuracy(df: pd.DataFrame, data_types: dict[str, str], issues: list) -> Optional[float]:
    """% rows within plausible ranges (no 10B VND outliers, age < 120, qty < 1M)."""
    rules_ran    = 0
    total_rows   = 0
    bad_rows     = 0
    for col, dtype in data_types.items():
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(series) == 0:
            continue
        if dtype in ("amount", "amount_vnd"):
            rules_ran += 1
            total_rows += len(series)
            out = int(((series < _AMOUNT_VND_MIN) | (series > _AMOUNT_VND_MAX)).sum())
            bad_rows += out
            if out > 0:
                issues.append({
                    "code":     "ACCURACY_AMOUNT_OUTLIER",
                    "dim":      "accuracy",
                    "severity": "medium",
                    "message":  f"Cột '{col}': {out} dòng có amount ngoài khoảng [0, {_AMOUNT_VND_MAX:,}] VND.",
                    "count":    out,
                })
        elif "age" in col.lower():
            rules_ran += 1
            total_rows += len(series)
            out = int(((series < 0) | (series > _AGE_MAX)).sum())
            bad_rows += out
            if out > 0:
                issues.append({
                    "code":     "ACCURACY_AGE_OUTLIER",
                    "dim":      "accuracy",
                    "severity": "low",
                    "message":  f"Cột '{col}': {out} dòng có age > {_AGE_MAX} hoặc âm.",
                    "count":    out,
                })
        elif "quantity" in col.lower() or "qty" in col.lower():
            rules_ran += 1
            total_rows += len(series)
            out = int((series > _QTY_MAX).sum())
            bad_rows += out
            if out > 0:
                issues.append({
                    "code":     "ACCURACY_QTY_OUTLIER",
                    "dim":      "accuracy",
                    "severity": "low",
                    "message":  f"Cột '{col}': {out} dòng có quantity > {_QTY_MAX:,}.",
                    "count":    out,
                })
    if rules_ran == 0 or total_rows == 0:
        return None
    return float(1 - bad_rows / total_rows)


def _integrity(df: pd.DataFrame, existing_ids: Optional[set[str]], issues: list) -> Optional[float]:
    """% rows whose customer_id is in the master table. N/A if no master provided."""
    if existing_ids is None or "customer_id" not in df.columns:
        return None
    series = df["customer_id"].dropna().astype(str)
    if len(series) == 0:
        return None
    matched = sum(1 for v in series if v in existing_ids)
    rate    = matched / len(series)
    missing = len(series) - matched
    if missing > 0:
        issues.append({
            "code":     "INTEGRITY_ORPHAN_FK",
            "dim":      "integrity",
            "severity": "high" if rate < 0.8 else "medium",
            "message":  f"{missing} dòng có customer_id không có trong master.",
            "count":    int(missing),
        })
    return float(rate)
