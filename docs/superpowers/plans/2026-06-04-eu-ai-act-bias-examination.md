# EU AI Act Bias Examination (Art 10) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic representativeness bias examination (EU AI Act Art 10) to the Stage-4 quality gate: detect sensitive/proxy columns and flag distributional imbalance, surfaced as a separate `bias` report on the scorecard (not folded into the weighted 7-dim `overall`). ADR-0041, Layer 3 final slice.

**Architecture:** A new pure module `data_plane/silver/bias.py` (`detect_sensitive_columns` + `examine_bias`, env-configurable thresholds) mirroring `quality.py`'s deterministic-Python ethos. `compute_scorecard` attaches `result["bias"] = examine_bias(df, data_types)`. No DB, no endpoint, no LLM.

**Tech Stack:** Python + pandas (data-pipeline). pytest.

**Branch:** `feat/eu-ai-act-bias-examination` (off `main`, independent — data-pipeline only).

**Invariants:** No K-1/K-12/K-21 surface (pure compute). Tenet 7 (VN messages). No-hardcode (env-configurable thresholds).

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `services/data-pipeline/data_plane/silver/bias.py` | pure `detect_sensitive_columns` + `examine_bias` + env thresholds | Create |
| `services/data-pipeline/tests/test_bias.py` | unit tests | Create |
| `services/data-pipeline/data_plane/silver/quality.py` | attach `result["bias"]` (2 spots: empty-sheet branch + main return) | Modify |
| `services/data-pipeline/tests/test_quality_scorecard.py` | one integration assertion that scorecard carries `bias` | Modify (append) |
| pipeline OpenAPI | drift (only if scorecard is typed) | Maybe |

**Test import convention (from `tests/test_quality_scorecard.py`):** tests insert service-root + repo-root into `sys.path`, then `from data_plane.silver.<mod> import ...`. Run tests from `services/data-pipeline`.

---

## Task 1: Pure `bias.py`

**Files:**
- Create: `services/data-pipeline/data_plane/silver/bias.py`
- Test: `services/data-pipeline/tests/test_bias.py`

- [ ] **Step 1: Write the failing test.** Create `services/data-pipeline/tests/test_bias.py`:

```python
"""Tests for Stage-4 bias examination (EU AI Act Art 10)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_SERVICE_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _SERVICE_ROOT.parent.parent
for _p in (_SERVICE_ROOT, _REPO_ROOT):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from data_plane.silver.bias import detect_sensitive_columns, examine_bias


def test_detect_sensitive_columns_vn_and_en():
    cols = ["customer_id", "gioi_tinh", "Age", "amount", "tinh_thanh", "note"]
    found = detect_sensitive_columns(cols)
    assert "gioi_tinh" in found
    assert "Age" in found            # 'age' substring, case-insensitive
    assert "tinh_thanh" in found     # 'tinh'
    assert "customer_id" not in found
    assert "amount" not in found


def test_skewed_sensitive_column_flagged():
    # 96 'Nam' + 4 'Nu' = 96% dominant share over 100 rows (>= min rows)
    df = pd.DataFrame({"gioi_tinh": ["Nam"] * 96 + ["Nu"] * 4})
    rep = examine_bias(df, data_types={"gioi_tinh": "categorical"})
    assert rep["status"] == "flagged"
    assert "gioi_tinh" in rep["checked_columns"]
    assert len(rep["findings"]) == 1
    f = rep["findings"][0]
    assert f["code"] == "BIAS_REPRESENTATION_IMBALANCE"
    assert f["column"] == "gioi_tinh"
    assert f["dominant_value"] == "Nam"
    assert abs(f["dominant_share"] - 0.96) < 1e-6
    assert f["severity"] == "high"   # > 0.95


def test_balanced_sensitive_column_ok():
    df = pd.DataFrame({"gioi_tinh": (["Nam", "Nu"] * 50)})  # 50/50, 100 rows
    rep = examine_bias(df, data_types={"gioi_tinh": "categorical"})
    assert rep["status"] == "ok"
    assert rep["findings"] == []
    assert "gioi_tinh" in rep["checked_columns"]


def test_no_sensitive_columns_not_applicable():
    df = pd.DataFrame({"customer_id": list(range(100)), "amount": [10] * 100})
    rep = examine_bias(df, data_types={})
    assert rep["status"] == "not_applicable"
    assert rep["checked_columns"] == []
    assert rep["findings"] == []


def test_below_min_rows_skipped():
    df = pd.DataFrame({"gioi_tinh": ["Nam"] * 5})  # < default 30
    rep = examine_bias(df, data_types={})
    assert rep["status"] == "not_applicable"   # the only sensitive col was skipped
    assert rep["checked_columns"] == []


def test_threshold_env_override(monkeypatch):
    # 70% dominant — below default 0.8 (ok) but above an override of 0.6 (flagged)
    df = pd.DataFrame({"gioi_tinh": ["Nam"] * 70 + ["Nu"] * 30})
    assert examine_bias(df, {})["status"] == "ok"
    monkeypatch.setenv("KAORI_BIAS_DOMINANT_SHARE", "0.6")
    assert examine_bias(df, {})["status"] == "flagged"


def test_empty_df_not_applicable():
    rep = examine_bias(pd.DataFrame(), data_types={})
    assert rep["status"] == "not_applicable"
    assert rep["row_count"] == 0
```

- [ ] **Step 2: Run to verify it fails.** Run: `cd services/data-pipeline && python -m pytest tests/test_bias.py -v` — Expected: FAIL (ModuleNotFoundError: bias).

- [ ] **Step 3: Implement.** Create `services/data-pipeline/data_plane/silver/bias.py`:

```python
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


# Sensitive / proxy attribute name hints (VN + EN), matched as a substring on
# the lower-cased column name.
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
            continue   # too few rows to judge representativeness
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
```

- [ ] **Step 4: Run to verify it passes.** Run: `cd services/data-pipeline && python -m pytest tests/test_bias.py -v` — Expected: 7 passed.

- [ ] **Step 5: Commit.**
```bash
git add services/data-pipeline/data_plane/silver/bias.py services/data-pipeline/tests/test_bias.py
git commit -m "feat(compliance): Stage-4 representativeness bias examination (EU AI Act Art 10)"
```

---

## Task 2: Attach `bias` to the scorecard

**Files:**
- Modify: `services/data-pipeline/data_plane/silver/quality.py`
- Test: `services/data-pipeline/tests/test_quality_scorecard.py` (append one test)

- [ ] **Step 1: Write the failing integration test.** Append to `services/data-pipeline/tests/test_quality_scorecard.py`:

```python
class TestBiasAttached:
    def test_scorecard_carries_bias_report(self):
        df = pd.DataFrame({
            "customer_id": list(range(100)),
            "gioi_tinh":   ["Nam"] * 96 + ["Nu"] * 4,
        })
        sc = compute_scorecard(df, data_types={"customer_id": "integer"},
                               purpose="customer_master")
        assert "bias" in sc
        assert sc["bias"]["status"] == "flagged"
        assert sc["bias"]["findings"][0]["column"] == "gioi_tinh"
        # bias must NOT be folded into the weighted overall (still a 0-1 quality score)
        assert 0.0 <= sc["overall"] <= 1.0

    def test_empty_sheet_has_bias_not_applicable(self):
        sc = compute_scorecard(pd.DataFrame(), data_types={}, purpose="transaction_list")
        assert sc["bias"]["status"] == "not_applicable"
```

- [ ] **Step 2: Run to verify it fails.** Run: `cd services/data-pipeline && python -m pytest tests/test_quality_scorecard.py::TestBiasAttached -v` — Expected: FAIL (KeyError: 'bias').

- [ ] **Step 3: Import + attach in `quality.py`.** Add the import near the top of `quality.py` (after `import pandas as pd`):

```python
from .bias import examine_bias
```

In `compute_scorecard`, the **empty-sheet early return** (the `if df is None or len(df) == 0:` block) — add a `bias` key to its returned dict:

```python
            "row_count":  0,
            "bias":       {"checked_columns": [], "findings": [],
                           "status": "not_applicable", "row_count": 0},
        }
```

And the **main return** dict (the one with `dimensions`/`weights`/`overall`/`issues`/`row_count`) — add the `bias` key (do NOT touch `_weighted_overall`):

```python
    return {
        "dimensions": dims,
        "weights":    DEFAULT_WEIGHTS,
        "overall":    round(overall, 4),
        "issues":     issues,
        "row_count":  int(len(df)),
        "bias":       examine_bias(df, data_types),
    }
```

- [ ] **Step 4: Run to verify it passes.** Run: `cd services/data-pipeline && python -m pytest tests/test_quality_scorecard.py -v` — Expected: all pass (the new `TestBiasAttached` + all pre-existing scorecard tests — `overall` is unchanged because `examine_bias` is additive to the dict, not the weighting).

- [ ] **Step 5: Commit.**
```bash
git add services/data-pipeline/data_plane/silver/quality.py services/data-pipeline/tests/test_quality_scorecard.py
git commit -m "feat(compliance): attach bias report to Stage-4 scorecard (Art 10)"
```

---

## Task 3: Drift artefacts

- [ ] **Step 1: Check if the scorecard is typed in the pipeline OpenAPI.** The scorecard is produced by `compute_scorecard` and returned by a cleaning endpoint. Determine whether that endpoint's response is a typed Pydantic model (which would put the scorecard shape in `docs/api-specs/pipeline.openapi.json`) or an untyped dict. Run: `cd D:\Kaori System && python scripts/dump_openapi.py pipeline`, then `git diff --stat docs/api-specs/pipeline.openapi.json`.
  - If it changed → the scorecard is typed; keep the regenerated file.
  - If it did NOT change → the scorecard flows as an untyped dict; the `bias` key is not modelled in OpenAPI → no spec change. Note this and move on.
  - If the script errors on import → report BLOCKED for this step (do NOT hand-edit JSON).

- [ ] **Step 2: Confirm no other drift surface.** No DB migration (no schema_snapshot change). No new endpoint/route (no RouteConfig change). No new error code (no FE i18n). Confirm by stating these explicitly.

- [ ] **Step 3: Commit (only if Step 1 changed the spec).**
```bash
git add docs/api-specs/pipeline.openapi.json
git commit -m "chore(compliance): refresh pipeline OpenAPI for scorecard bias key (Art 10)"
```
(If nothing changed, report "no drift commit needed — scorecard is an untyped dict; no migration/route/error-code surface.")

---

## Self-Review

**Spec coverage:**
- ✅ Pure `bias.py` (`detect_sensitive_columns` + `examine_bias`, env thresholds, VN+EN hints, representativeness flag) → Task 1.
- ✅ Attach `result["bias"]` separate from weighted overall (both empty + main return) → Task 2.
- ✅ Representativeness-only; never raises (total); status ok/flagged/not_applicable → Task 1.
- ✅ Drift (openapi only if typed; no migration/route) → Task 3.
- ✅ Out-of-scope (proxy-correlation, outcome bias) not implemented — honored.

**Placeholder scan:** No TBD/TODO. All production code given verbatim. The "is the scorecard typed?" check in Task 3 is a real conditional with both branches specified.

**Type consistency:** `examine_bias(df, data_types)` / `detect_sensitive_columns(columns)` signatures consistent between Task 1 def, Task 1 tests, and Task 2 call. The `bias` report keys (`checked_columns`, `findings`, `status`, `row_count`) + finding keys (`column`, `code`, `severity`, `message`, `dominant_value`, `dominant_share`, `distinct_values`) consistent between bias.py, test_bias.py, and the scorecard integration test. `BIAS_REPRESENTATION_IMBALANCE` code consistent.

**Scope:** One pure module + a 2-line scorecard attach + drift check. Smallest of the Layer-3 slices. Focused.

---

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-06-04-eu-ai-act-bias-examination.md`. Two options:
1. **Subagent-Driven (recommended)** — fresh subagent per task + spec/quality review.
2. **Inline Execution** — executing-plans, batch + checkpoints.

Which approach?
