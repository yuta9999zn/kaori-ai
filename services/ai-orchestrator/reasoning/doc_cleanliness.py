"""
Doc cleanliness gate — "file bảng này đã sạch chưa?" (demo AABW 11/07).

Khi người dùng nộp file bảng (csv/xlsx) vào Cây tài liệu mà KHÔNG chọn
chạy 5 bước làm sạch, hệ thống chấm độ sạch bằng heuristics tất định
(mirror các quy tắc Bước 3 của pipeline); LLM chỉ viết nhận xét tiếng
Việt, KHÔNG quyết định verdict. Bẩn → đề nghị chạy 5 bước; sạch → cho
phân tích thẳng.

Ngưỡng env-configurable: KAORI_DOC_CLEAN_THRESHOLD (default 0.8),
KAORI_DOC_CLEAN_NULL_RATE (default 0.3).
"""
from __future__ import annotations

import os
import re

import pandas as pd

_ISO_RE   = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DMY_RE   = re.compile(r"^\d{1,2}[/-]\d{1,2}[/-]\d{4}$")
# "11.475.000" / "3,000,000" / "15000" / "12.5" — parseable money/number shapes
_NUMBERY_RE = re.compile(r"^-?[\d.,]+$")


def _date_like(series: pd.Series) -> pd.Series:
    s = series.dropna().astype(str).str.strip()
    return s[s.str.match(_ISO_RE) | s.str.match(_DMY_RE)]


def assess_cleanliness(df: pd.DataFrame) -> dict:
    """Deterministic cleanliness verdict for a tabular file.

    Returns {score, is_clean, issues[], recommendation} where
    recommendation ∈ {"analyze", "run_pipeline"}. Blocker issues
    (mixed date formats / unparseable numbers / duplicates) force
    run_pipeline regardless of score.
    """
    issues: list[dict] = []
    n_rows = len(df)

    if n_rows == 0 or len(df.columns) == 0:
        return {
            "score": 0.0, "is_clean": False, "recommendation": "run_pipeline",
            "issues": [{"code": "empty_file", "label": "File rỗng hoặc không đọc được bảng", "count": 0}],
        }

    dirty_cells = 0
    total_cells = int(df.size)

    # 1. Duplicate full rows (Bước 3: dedup)
    dup_count = int(df.duplicated().sum())
    if dup_count:
        issues.append({"code": "duplicate_rows",
                       "label": f"{dup_count} dòng trùng lặp hoàn toàn",
                       "count": dup_count})
        dirty_cells += dup_count * len(df.columns)

    # 2. Null / blank rate per column (Bước 3: null handling)
    null_rate_cap = float(os.getenv("KAORI_DOC_CLEAN_NULL_RATE", "0.3"))
    for col in df.columns:
        s = df[col]
        blank = int((s.isna() | (s.astype(str).str.strip() == "")).sum())
        if n_rows and blank / n_rows > null_rate_cap:
            issues.append({"code": "high_null_rate",
                           "label": f"Cột '{col}' trống {blank}/{n_rows} ô",
                           "count": blank})
        dirty_cells += blank

    for col in df.columns:
        s = df[col]
        non_null = s.dropna().astype(str).str.strip()
        non_null = non_null[non_null != ""]
        if non_null.empty:
            continue

        # 3. Mixed date formats (Bước 3: parse dates to ISO)
        dates = _date_like(s)
        if len(dates) >= max(2, int(0.5 * len(non_null))):
            iso = int(dates.str.match(_ISO_RE).sum())
            dmy = int(dates.str.match(_DMY_RE).sum())
            if iso and dmy:
                issues.append({"code": "mixed_date_formats",
                               "label": f"Cột '{col}' lẫn nhiều định dạng ngày ({iso} ISO / {dmy} d/m/y)",
                               "count": min(iso, dmy)})
                dirty_cells += min(iso, dmy)
            continue

        # 4. Numeric-ish column with unparseable tokens ("2tr7", "12.000₫")
        numbery = non_null.str.match(_NUMBERY_RE)
        n_num = int(numbery.sum())
        if 0 < n_num < len(non_null) and n_num >= int(0.5 * len(non_null)):
            bad = non_null[~numbery]
            issues.append({"code": "unparseable_numbers",
                           "label": f"Cột '{col}' có {len(bad)} giá trị không phải số thuần "
                                    f"(vd: {', '.join(bad.head(2).tolist())})",
                           "count": int(len(bad))})
            dirty_cells += int(len(bad))

        # 5. Negative values in an otherwise-positive numeric column
        if n_num == len(non_null):
            nums = pd.to_numeric(non_null.str.replace(r"[.,]", "", regex=True),
                                 errors="coerce").dropna()
            if len(nums) >= 3:
                neg = int((nums < 0).sum())
                if 0 < neg <= 0.2 * len(nums):
                    issues.append({"code": "negative_values",
                                   "label": f"Cột '{col}' có {neg} giá trị âm bất thường",
                                   "count": neg})
                    dirty_cells += neg
                med = float(nums.abs().median())
                if med > 0:
                    outliers = int((nums.abs() > 100 * med).sum())
                    if outliers:
                        issues.append({"code": "extreme_outliers",
                                       "label": f"Cột '{col}' có {outliers} giá trị cực đoan (>100× trung vị)",
                                       "count": outliers})
                        dirty_cells += outliers

    score = max(0.0, round(1.0 - (dirty_cells / total_cells), 4)) if total_cells else 0.0
    threshold = float(os.getenv("KAORI_DOC_CLEAN_THRESHOLD", "0.8"))
    blockers = {"duplicate_rows", "mixed_date_formats", "unparseable_numbers"}
    has_blocker = any(i["code"] in blockers for i in issues)
    is_clean = (score >= threshold) and not has_blocker

    return {
        "score": score,
        "is_clean": is_clean,
        "recommendation": "analyze" if is_clean else "run_pipeline",
        "issues": issues,
    }
