"""
Rule Catalog — general-purpose data cleaning rules.

Categories:
  UNIVERSAL: Applied to all data (trim, normalize, empty row removal)
  BY_TYPE: Applied based on detected data type (date, phone, currency, text)
  BY_PURPOSE: Applied based on sheet purpose (transaction_list, customer_master, etc.)
  AI_DETECTED: Suggested by LLM analysis (outliers, fuzzy duplicates, etc.)

K-2: Rules applied non-destructively to Silver layer. Bronze unchanged.
"""
import os
import re
import unicodedata
from typing import Any, Optional

import pandas as pd
import structlog

log = structlog.get_logger()


# ============================================================
# UNIVERSAL RULES (always safe, always applied)
# ============================================================

def rule_trim_whitespace(df: pd.DataFrame, col: str, **_) -> tuple[pd.DataFrame, int]:
    """Remove leading/trailing whitespace from string columns. Preserves None/NaN.

    Bug history: the previous implementation used ``.astype(str).str.strip()``
    which forced None/NaN through Python ``str()`` and stringified them to the
    literal ``'None'`` (caught by test_none_values_preserved). The replace-back
    line only normalised the legacy ``'nan'`` literal — ``'None'`` slipped past
    and showed up in silver. We now strip element-wise so non-strings pass
    through untouched.
    """
    if df[col].dtype == object:
        before = df[col].notna().sum()
        df = df.copy()

        def _strip_or_keep(v):
            if isinstance(v, str):
                stripped = v.strip()
                # Empty string + the legacy ``'nan'`` literal collapse to NaN so
                # downstream notna()/quality_score reflects the cleanup.
                if stripped == "" or stripped == "nan":
                    return None
                return stripped
            return v  # None / NaN / non-string objects preserved

        df[col] = df[col].apply(_strip_or_keep)
        after = df[col].notna().sum()
        return df, int(before - after)  # rows changed
    return df, 0


def rule_normalize_unicode(df: pd.DataFrame, col: str, **_) -> tuple[pd.DataFrame, int]:
    """NFC normalization + NBSP removal."""
    if df[col].dtype == object:
        df = df.copy()
        df[col] = df[col].apply(
            lambda v: unicodedata.normalize("NFC", str(v)).replace(" ", " ").strip()
            if pd.notna(v) else v
        )
        return df, 0
    return df, 0


def rule_remove_empty_rows(df: pd.DataFrame, **_) -> tuple[pd.DataFrame, int]:
    """Remove rows where all canonical columns are null."""
    before = len(df)
    df = df.dropna(how="all").reset_index(drop=True)
    return df, before - len(df)


def rule_remove_header_duplicates(df: pd.DataFrame, **_) -> tuple[pd.DataFrame, int]:
    """Remove rows that are exact copies of the header (common in poorly exported files)."""
    if df.empty:
        return df, 0
    header_values = set(str(c).lower().strip() for c in df.columns)
    mask = df.apply(
        lambda row: set(str(v).lower().strip() for v in row.values) == header_values,
        axis=1
    )
    removed = mask.sum()
    return df[~mask].reset_index(drop=True), int(removed)


def rule_flag_outliers(df: pd.DataFrame, **_) -> tuple[pd.DataFrame, int]:
    """Flag EXTREME numeric outliers (placeholder 9999, fat-finger values) by
    nulling them so they don't silently skew Gold aggregates (sum/avg). The
    cell becomes missing → the quality scorecard's null-rate reflects it and
    downstream aggregates skip it. Non-destructive to Bronze (K-2 — Silver
    only) and a JUDGEMENT (``safe=False``) surfaced for the user to opt into,
    never auto-applied.

    Conservative on purpose: only fires beyond Q1−3·IQR / Q3+3·IQR (Tukey
    "far out") on a column that is genuinely numeric (≥70% of non-null cells
    coerce to a number and ≥8 numeric values), and skips columns with no
    spread (IQR≤0). Percentile bounds are robust to a lone giant value, so a
    single 9999 doesn't hide itself by inflating its own threshold.
    """
    df = df.copy()
    flagged = 0
    for col in df.columns:
        s = pd.to_numeric(df[col], errors="coerce")
        n_num = int(s.notna().sum())
        n_present = int(df[col].notna().sum())
        if n_num < 8 or n_present == 0 or n_num < 0.7 * n_present:
            continue  # not a numeric column
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        if iqr <= 0:
            continue  # constant / degenerate spread → nothing to flag
        lo, hi = q1 - 3 * iqr, q3 + 3 * iqr
        mask = s.notna() & ((s < lo) | (s > hi))
        k = int(mask.sum())
        if k:
            df.loc[mask, col] = None
            flagged += k
            log.info("rule_flag_outliers.applied", col=col, flagged=k,
                     lo=round(float(lo), 4), hi=round(float(hi), 4))
    return df, flagged


# ============================================================
# BY_TYPE RULES
# ============================================================

# Ambiguous day/month-first date: D/M/Y or M/D/Y with 1-2 digit leading parts.
# Year-first ISO (2024-03-01) is excluded — its leading part is > 31.
_AMBIG_DATE_RE = re.compile(r"^\s*(\d{1,2})[/.\-](\d{1,2})[/.\-]\d{2,4}\s*$")

# Year-first formats are unambiguous and tried first; the day/month-first
# families are then ordered by the direction inferred from the column itself.
_ISO_DATE_FORMATS = ["%Y-%m-%d", "%Y/%m/%d"]
_DMY_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y"]
_MDY_FORMATS = ["%m/%d/%Y", "%m-%d-%Y", "%m.%d.%Y", "%m/%d/%y"]

# Tie-break direction for a column that gives NO disambiguating signal (every
# day/month part ≤ 12 → genuinely ambiguous). VN/ISO-region convention is
# day-first; env-overridable so the default is never silently baked in. The
# direction MEASURED from real data always overrides this — it only decides
# columns that carry no evidence either way.
_DEFAULT_DAYFIRST = os.environ.get("KAORI_DATE_DAYFIRST_DEFAULT", "true").lower() != "false"


def _infer_dayfirst(series: pd.Series) -> Optional[bool]:
    """Infer whether a date column is day-first (D/M/Y) or month-first (M/D/Y)
    by MEASURING it — not by assuming a locale. A value like ``27/12`` proves
    the first part is the day (>12 cannot be a month); ``12/27`` proves the
    second part is. Returns True (day-first), False (month-first), or None when
    the column carries no disambiguating value.

    Samples randomly (not the head) so a column whose first rows happen to
    cluster early in a month does not mislead the inference — the bug that
    made an all-early-December head read as day-first.
    """
    s = series.dropna()
    if len(s) == 0:
        return None
    if len(s) > 4000:
        s = s.sample(4000, random_state=0)
    dayfirst_votes = 0    # first part proven to be the day  (>12, ≤31)
    monthfirst_votes = 0  # second part proven to be the day (>12, ≤31)
    for v in s:
        m = _AMBIG_DATE_RE.match(str(v))
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2))
        if 12 < a <= 31 and b <= 12:
            dayfirst_votes += 1
        elif 12 < b <= 31 and a <= 12:
            monthfirst_votes += 1
    if dayfirst_votes and not monthfirst_votes:
        return True
    if monthfirst_votes and not dayfirst_votes:
        return False
    # No evidence, or contradictory (malformed mixed column) → caller's default.
    return None


def rule_parse_date(df: pd.DataFrame, col: str, **_) -> tuple[pd.DataFrame, int]:
    """Parse date strings to ISO format. Handles VI/JP/EN date formats.

    Day-first vs month-first is INFERRED from the column's own values
    (``_infer_dayfirst``) rather than assumed — so a US-style ``MM/DD/YYYY``
    export parses correctly and every row in a column is read the same way.
    A genuinely ambiguous column falls back to the documented, env-overridable
    default and the decision is logged for lineage.
    """
    df = df.copy()
    parsed = 0
    inferred = _infer_dayfirst(df[col])
    dayfirst = _DEFAULT_DAYFIRST if inferred is None else inferred
    log.debug(
        "rule_parse_date.direction",
        col=col,
        direction=("day_first" if dayfirst else "month_first"),
        source=("measured" if inferred is not None else "default"),
    )
    ambiguous = (_DMY_FORMATS + _MDY_FORMATS) if dayfirst else (_MDY_FORMATS + _DMY_FORMATS)
    formats = _ISO_DATE_FORMATS + ambiguous

    def try_parse(v):
        nonlocal parsed
        if pd.isna(v):
            return v
        s = str(v).strip()
        for fmt in formats:
            try:
                result = pd.to_datetime(s, format=fmt).strftime("%Y-%m-%d")
                parsed += 1
                return result
            except (ValueError, TypeError):
                continue
        # Pandas auto-detect as last resort, with the inferred direction.
        try:
            result = pd.to_datetime(s, dayfirst=dayfirst).strftime("%Y-%m-%d")
            parsed += 1
            return result
        except Exception:
            return v

    df[col] = df[col].apply(try_parse)
    return df, parsed


def rule_parse_currency(df: pd.DataFrame, col: str, **_) -> tuple[pd.DataFrame, int]:
    """Parse VND/USD currency strings to numeric (NUMERIC(14,4) compatible)."""
    df = df.copy()
    parsed = 0
    def clean_currency(v):
        nonlocal parsed
        if pd.isna(v):
            return v
        # Keep only the numeric skeleton — digits, separators, sign. One pass
        # strips ₫ đ $ € ¥ £, currency words (VND/USD), and whitespace.
        s = re.sub(r"[^0-9.,\-]", "", str(v))
        if s in ("", "-", ".", ","):
            return v
        # Disambiguate thousand- vs decimal-separator by RELATIVE POSITION
        # (locale-aware), so we no longer mangle US-format money:
        #   1.234,56 (EU)  ·  1,234.56 (US)  ·  1.500.000 (VN thousands)
        # Ported from the NNL-Harness profiler.parse_money.
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):       # comma is the decimal mark (EU)
                s = s.replace(".", "").replace(",", ".")
            else:                                  # dot is the decimal mark (US)
                s = s.replace(",", "")
        elif "," in s:
            # comma only: a single trailing 1–2 digit group is a decimal
            # (500,00); anything else (1,234 / 1,234,567) is thousand grouping.
            s = (s.replace(",", ".") if re.fullmatch(r"\d+,\d{1,2}", s)
                 else s.replace(",", ""))
        elif "." in s:
            # dot only: multiple dots = thousands (1.500.000); a single 3-digit
            # trailing group = thousands (1.500); a 1–2 digit trail = decimal.
            if s.count(".") > 1 or re.fullmatch(r"\d{1,3}\.\d{3}", s):
                s = s.replace(".", "")
        try:
            result = float(s)
            parsed += 1
            return result
        except ValueError:
            return v
    df[col] = df[col].apply(clean_currency)
    return df, parsed


def rule_normalize_phone_vn(df: pd.DataFrame, col: str, **_) -> tuple[pd.DataFrame, int]:
    """Normalize Vietnamese phone numbers to 10-digit format (09xx, 03xx, etc.)."""
    df = df.copy()
    normalized = 0
    def normalize(v):
        nonlocal normalized
        if pd.isna(v):
            return v
        s = re.sub(r"[^\d+]", "", str(v))
        # +84xxxxxxxxx → 0xxxxxxxxx
        if s.startswith("+84"):
            s = "0" + s[3:]
        elif s.startswith("84") and len(s) == 11:
            s = "0" + s[2:]
        if re.match(r"^0[3-9]\d{8}$", s):
            normalized += 1
            return s
        return v
    df[col] = df[col].apply(normalize)
    return df, normalized


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def rule_standardize_email(df: pd.DataFrame, col: str, **_) -> tuple[pd.DataFrame, int]:
    """Standardize email cells: trim + lowercase; clear malformed values so an
    invalid email is treated consistently as MISSING (flagged via null-rate),
    not counted as a real contact. Row-safe — never drops a row. Returns the
    count of cells changed (normalized or cleared)."""
    if df[col].dtype != object:
        return df, 0
    df = df.copy()
    changed = 0
    def fix(v):
        nonlocal changed
        if pd.isna(v):
            return v
        s = str(v).strip().lower()
        if s == "":
            return v
        if _EMAIL_RE.match(s):
            if s != str(v):
                changed += 1
            return s
        changed += 1          # malformed → clear (flag as missing)
        return pd.NA
    df[col] = df[col].apply(fix)
    return df, changed


def rule_normalize_fullwidth(df: pd.DataFrame, col: str, **_) -> tuple[pd.DataFrame, int]:
    """Convert Japanese/Korean fullwidth characters to ASCII where appropriate."""
    if df[col].dtype != object:
        return df, 0
    df = df.copy()
    df[col] = df[col].apply(
        lambda v: unicodedata.normalize("NFKC", str(v)) if pd.notna(v) else v
    )
    return df, 0


# ============================================================
# BY_PURPOSE RULES
# ============================================================

def rule_dedup_by_phone(df: pd.DataFrame, phone_col: str = "phone", **_) -> tuple[pd.DataFrame, int]:
    """Deduplicate customer rows by phone number, keeping most recent."""
    if phone_col not in df.columns:
        return df, 0
    before = len(df)
    df = df.sort_index(ascending=False).drop_duplicates(
        subset=[phone_col], keep="first"
    ).sort_index().reset_index(drop=True)
    return df, before - len(df)


def rule_fill_forward_date(df: pd.DataFrame, col: str = "date", **_) -> tuple[pd.DataFrame, int]:
    """Fill forward missing dates (common in merged cell Excel exports)."""
    if col not in df.columns:
        return df, 0
    df = df.copy()
    missing_before = df[col].isna().sum()
    df[col] = df[col].ffill()
    filled = missing_before - df[col].isna().sum()
    return df, int(filled)


def rule_dedup_transactions(df: pd.DataFrame, **_) -> tuple[pd.DataFrame, int]:
    """Remove exact duplicate transaction rows (same date + amount + description)."""
    key_cols = [c for c in ["date", "amount", "description", "reference"]
                if c in df.columns]
    if not key_cols:
        return df, 0
    before = len(df)
    df = df.drop_duplicates(subset=key_cols).reset_index(drop=True)
    return df, before - len(df)


def _safe_median(s: pd.Series) -> Optional[float]:
    s = s.dropna()
    return round(float(s.median()), 4) if len(s) else None


def measure_amount_signals(df: pd.DataFrame) -> dict:
    """MEASURE (never decide) whether a transaction's monetary column is a
    per-unit price or an already-computed line total. Returns plain numbers so
    the LLM column-mapper / the user at schema-confirm can make the call with
    the evidence in front of them — this function picks nothing.

    Every signal is derived from the data, none hard-coded:
      - ``has_quantity`` / ``has_unit_price`` / ``has_explicit_total`` — which
        canonicals the source actually provides.
      - ``unit_price_median`` / ``quantity_median`` / ``implied_line_total_median``
        (= unit_price × quantity) so a reviewer can sanity-check magnitude.
      - ``total_matches_unit_times_qty`` — when an explicit ``amount``/``revenue``
        total ALSO exists, the share of rows where total ≈ unit_price × quantity
        (±1%). A high share is strong evidence the per-unit column really is
        per-unit (and the explicit total is the true line total).
    """
    cols = set(df.columns)
    qty = pd.to_numeric(df["quantity"], errors="coerce") if "quantity" in cols else None
    up = pd.to_numeric(df["unit_price"], errors="coerce") if "unit_price" in cols else None
    total_col = "revenue" if "revenue" in cols else ("amount" if "amount" in cols else None)
    total = pd.to_numeric(df[total_col], errors="coerce") if total_col else None

    sig: dict[str, Any] = {
        "has_quantity": qty is not None,
        "has_unit_price": up is not None,
        "has_explicit_total": total is not None,
        "explicit_total_col": total_col,
    }
    if qty is not None:
        sig["quantity_median"] = _safe_median(qty)
    if up is not None:
        sig["unit_price_median"] = _safe_median(up)
    if up is not None and qty is not None:
        implied = up * qty
        sig["implied_line_total_median"] = _safe_median(implied)
        if total is not None:
            both = implied.notna() & total.notna() & (total != 0)
            n = int(both.sum())
            if n:
                close = (implied[both] - total[both]).abs() <= (total[both].abs() * 0.01)
                sig["total_matches_unit_times_qty"] = round(float(close.sum()) / n, 4)
                sig["compared_rows"] = n
    return sig


def rule_derive_line_total(df: pd.DataFrame, **_) -> tuple[pd.DataFrame, int]:
    """Derive the canonical line-total ``amount`` = unit_price × quantity.

    Gold reads ``amount``/``revenue`` as the LINE TOTAL and never multiplies
    (Medallion contract: normalize at Silver, keep Gold strict). When a source
    gives a per-unit ``unit_price`` plus ``quantity``, the total must be
    computed here. ``safe=False``: this is a judgement, so it is SURFACED at
    the cleaning-review step (with ``measure_amount_signals`` as the evidence)
    and only runs when the user selects it — never silently, never hard-coded.

    No-op when there is no unit_price+quantity pair, or when a genuine total
    column already exists (the explicit total is trusted, not overwritten).
    """
    if "unit_price" not in df.columns or "quantity" not in df.columns:
        return df, 0
    if "revenue" in df.columns or "amount" in df.columns:
        return df, 0  # explicit total present → trust it, derive nothing
    df = df.copy()
    up = pd.to_numeric(df["unit_price"], errors="coerce")
    qty = pd.to_numeric(df["quantity"], errors="coerce")
    line_total = up * qty
    mask = line_total.notna()
    df["amount"] = line_total.where(mask)
    derived = int(mask.sum())
    log.info("rule_derive_line_total.applied", rows=derived)
    return df, derived


# ============================================================
# RULE CATALOG REGISTRY
# ============================================================

RULE_CATALOG = {
    "UNIVERSAL": [
        {
            "rule_id": "TRIM_WHITESPACE",
            "name": "Trim whitespace",
            "description": "Remove leading/trailing whitespace from text columns",
            "category": "UNIVERSAL",
            "applies_to_col": True,
            "fn": rule_trim_whitespace,
            "safe": True,
        },
        {
            "rule_id": "NORMALIZE_UNICODE",
            "name": "Normalize Unicode",
            "description": "NFC normalization, remove non-breaking spaces",
            "category": "UNIVERSAL",
            "applies_to_col": True,
            "fn": rule_normalize_unicode,
            "safe": True,
        },
        {
            "rule_id": "REMOVE_EMPTY_ROWS",
            "name": "Remove empty rows",
            "description": "Remove rows where all columns are null",
            "category": "UNIVERSAL",
            "applies_to_col": False,
            "fn": rule_remove_empty_rows,
            "safe": True,
        },
        {
            "rule_id": "REMOVE_HEADER_DUPES",
            "name": "Remove repeated header rows",
            "description": "Remove rows that duplicate the header (Excel export artifact)",
            "category": "UNIVERSAL",
            "applies_to_col": False,
            "fn": rule_remove_header_duplicates,
            "safe": True,
        },
        {
            "rule_id": "OUTLIER_FLAG",
            "name": "Đánh dấu giá trị bất thường (outlier)",
            "description": "Phát hiện giá trị số cực đoan (vd: 9.999 placeholder, nhập nhầm) ở cột số và đánh dấu là trống để không làm lệch tổng/trung bình. Không xoá dòng, không đụng Bronze.",
            "category": "UNIVERSAL",
            "applies_to_col": False,
            "fn": rule_flag_outliers,
            "safe": False,  # Judgement — surfaced for user approval, not auto-applied
        },
    ],
    "BY_TYPE": {
        "date": [
            {
                "rule_id": "PARSE_DATE",
                "name": "Parse dates to ISO format",
                "description": "Convert DD/MM/YYYY and other formats to YYYY-MM-DD",
                "category": "BY_TYPE",
                "applies_to_col": True,
                "fn": rule_parse_date,
                "safe": True,
            },
            {
                "rule_id": "FILL_FORWARD_DATE",
                "name": "Fill forward missing dates",
                "description": "Propagate date values through merged-cell gaps",
                "category": "BY_TYPE",
                "applies_to_col": True,
                "fn": rule_fill_forward_date,
                "safe": True,
            },
        ],
        "currency": [
            {
                "rule_id": "PARSE_CURRENCY",
                "name": "Parse currency to numeric",
                "description": "Remove ₫/VND/$ symbols and parse to float",
                "category": "BY_TYPE",
                "applies_to_col": True,
                "fn": rule_parse_currency,
                "safe": True,
            },
        ],
        "phone": [
            {
                "rule_id": "NORMALIZE_PHONE_VN",
                "name": "Normalize Vietnamese phone numbers",
                "description": "Standardize to 10-digit 0xxx format",
                "category": "BY_TYPE",
                "applies_to_col": True,
                "fn": rule_normalize_phone_vn,
                "safe": True,
            },
        ],
        "text": [
            {
                "rule_id": "NORMALIZE_FULLWIDTH",
                "name": "Normalize fullwidth characters",
                "description": "Convert JP/KO fullwidth chars to ASCII equivalents",
                "category": "BY_TYPE",
                "applies_to_col": True,
                "fn": rule_normalize_fullwidth,
                "safe": True,
            },
        ],
        "email": [
            {
                "rule_id": "STANDARDIZE_EMAIL",
                "name": "Chuẩn hoá email",
                "description": "Bỏ khoảng trắng + viết thường; email sai định dạng được đánh dấu là trống để không bị tính là liên hệ hợp lệ",
                "category": "BY_TYPE",
                "applies_to_col": True,
                "fn": rule_standardize_email,
                "safe": True,
            },
        ],
    },
    "BY_PURPOSE": {
        "customer_master": [
            {
                "rule_id": "DEDUP_BY_PHONE",
                "name": "Deduplicate customers by phone",
                "description": "Keep most recent row when phone number is duplicated",
                "category": "BY_PURPOSE",
                "fn": rule_dedup_by_phone,
                "safe": False,  # Destructive — requires user approval
            },
        ],
        "transaction_list": [
            {
                "rule_id": "DERIVE_LINE_TOTAL",
                "name": "Derive line total (unit price × quantity)",
                "description": "Compute amount = unit_price × quantity when the source gives a per-unit price + quantity but no total column",
                "category": "BY_PURPOSE",
                "fn": rule_derive_line_total,
                "safe": False,  # Judgement — surfaced for user approval with measured signals
            },
            {
                "rule_id": "DEDUP_TRANSACTIONS",
                "name": "Remove duplicate transactions",
                "description": "Remove rows with identical date + amount + description",
                "category": "BY_PURPOSE",
                "fn": rule_dedup_transactions,
                "safe": False,
            },
            {
                "rule_id": "FILL_DATE_TRANSACTION",
                "name": "Fill forward date column",
                "description": "Fill empty date cells from previous non-empty value",
                "category": "BY_PURPOSE",
                "fn": rule_fill_forward_date,
                "safe": True,
            },
        ],
    },
}


def _build_rule_by_id() -> dict[str, dict]:
    """Flat {rule_id → rule_dict} lookup including the fn reference."""
    index: dict[str, dict] = {}
    for rule in RULE_CATALOG["UNIVERSAL"]:
        index[rule["rule_id"]] = rule
    for rules in RULE_CATALOG["BY_TYPE"].values():
        for rule in rules:
            index[rule["rule_id"]] = rule
    for rules in RULE_CATALOG["BY_PURPOSE"].values():
        for rule in rules:
            index[rule["rule_id"]] = rule
    return index


RULE_BY_ID: dict[str, dict] = _build_rule_by_id()


def apply_rules_to_df(
    df: pd.DataFrame,
    rule_ids: list[str],
    data_types: dict[str, str],
) -> tuple[pd.DataFrame, list[tuple[str, str | None, int]]]:
    """
    Apply a list of rules (by rule_id) to a DataFrame.
    Returns (cleaned_df, [(rule_id, col_or_None, rows_changed), ...]).
    """
    audit: list[tuple[str, str | None, int]] = []
    for rule_id in rule_ids:
        rule = RULE_BY_ID.get(rule_id)
        if not rule or rule.get("fn") is None:
            continue
        fn = rule["fn"]
        applies_to_col = rule.get("applies_to_col", False)
        if applies_to_col:
            # Determine target columns based on category
            if rule["category"] == "UNIVERSAL":
                target_cols = [c for c in df.columns if df[c].dtype == object]
            else:
                # BY_TYPE: apply to columns whose type matches
                col_type_needed = None
                for dtype, rules_for_type in RULE_CATALOG["BY_TYPE"].items():
                    if any(r["rule_id"] == rule_id for r in rules_for_type):
                        col_type_needed = dtype
                        break
                target_cols = [
                    c for c, t in data_types.items() if t == col_type_needed and c in df.columns
                ] if col_type_needed else []
            for col in target_cols:
                try:
                    df, changed = fn(df, col=col)
                    audit.append((rule_id, col, changed))
                except Exception as exc:
                    log.warning("rule_apply_error", rule_id=rule_id, col=col, error=str(exc))
        else:
            # Row-level rule (no col argument)
            try:
                df, changed = fn(df)
                audit.append((rule_id, None, changed))
            except Exception as exc:
                log.warning("rule_apply_error", rule_id=rule_id, error=str(exc))
    return df, audit


def get_applicable_rules(data_types: dict[str, str], purpose: Optional[str]) -> list[dict]:
    """
    Build list of applicable rules for a given schema.

    Args:
        data_types: {canonical_name: data_type} mapping
        purpose: detected sheet purpose

    Returns: list of rule dicts with metadata (no fn — for UI display)
    """
    rules = []

    # Always add universal rules
    for rule in RULE_CATALOG["UNIVERSAL"]:
        rules.append({**rule, "fn": None})

    # Add type-specific rules for each detected type
    seen_types = set(data_types.values())
    for dtype in seen_types:
        for rule in RULE_CATALOG["BY_TYPE"].get(dtype, []):
            rules.append({**rule, "fn": None, "target_columns": [
                c for c, t in data_types.items() if t == dtype
            ]})

    # Add purpose-specific rules
    if purpose and purpose in RULE_CATALOG["BY_PURPOSE"]:
        for rule in RULE_CATALOG["BY_PURPOSE"][purpose]:
            rules.append({**rule, "fn": None})

    return rules
