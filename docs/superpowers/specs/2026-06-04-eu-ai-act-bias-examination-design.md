# EU AI Act Layer 3 — Bias Examination (Art 10, slice 4 / final) — Design

> **Status:** design, pending approval → writing-plans
> **Date:** 2026-06-04
> **Part of:** EU AI Act Layer 3 (final slice), ADR-0041. K-22 #347, K-23 #348, K-24 #349, K-26 #350 done.
> **Branch:** `feat/eu-ai-act-bias-examination`, off `main` (independent — data-pipeline only).

## Goal

EU AI Act Art 10 requires data used by high-risk AI to be examined "in view of possible biases". Add a deterministic **bias examination** to the Medallion Stage-4 quality gate that flags **representativeness imbalance** on sensitive/proxy attributes in input data, surfaced as a separate report alongside (not folded into) the 7-dimension quality score.

## Decisions (confirmed with anh, 2026-06-04)

1. **Attach as a separate report** (`result["bias"]`), NOT an 8th weighted dimension — bias (Art 10) is distinct from data-quality; conflating would distort the `overall` score and force reweighting the 7 dims (which sum to 1.0).
2. **Scope = input-data representativeness only:** detect sensitive/proxy columns by name heuristic, compute category distribution, flag when the dominant category's share exceeds a threshold.
3. **Out of scope (YAGNI):** proxy-correlation (needs a correlation matrix); outcome/label bias + statistical parity (needs protected attribute AND model predictions — that's model-eval, not the data-governance stage Art 10 targets); intersectional bias; auto-remediation.

## Architecture

Mirrors the existing `quality.py` ethos — deterministic pure Python, no LLM, no I/O.

### `data_plane/silver/bias.py` (new, pure)
- `SENSITIVE_ATTRIBUTE_HINTS`: name substrings (VN + EN) that mark a column as a sensitive/proxy attribute — e.g. `gender`, `sex`, `gioi_tinh`, `gioitinh`, `age`, `tuoi`, `region`, `province`, `tinh`, `thanh_pho`, `marital`, `hon_nhan`, `ethnicity`, `dan_toc`, `religion`, `ton_giao`, `disability`, `khuyet_tat`, `nationality`, `quoc_tich`. (Substring match on lower-cased column name.)
- `detect_sensitive_columns(columns) -> list[str]` — pure, returns the matched column names.
- `_dominant_share_threshold() -> float` — reads env `KAORI_BIAS_DOMINANT_SHARE` (default `0.8`); the no-hardcode rule. Also `KAORI_BIAS_MIN_ROWS` (default `30`) — below this row count, representativeness checks are statistically meaningless → skipped.
- `examine_bias(df, data_types) -> dict` returning:
  ```
  {
    "checked_columns": [..],         # sensitive columns examined
    "findings": [                    # one per flagged column
      {"column", "code": "BIAS_REPRESENTATION_IMBALANCE",
       "severity", "message", "dominant_value", "dominant_share", "distinct_values"}
    ],
    "status": "ok" | "flagged" | "not_applicable",   # not_applicable = no sensitive cols or too few rows
    "row_count": int,
  }
  ```
  For each detected sensitive column: drop nulls; if `< KAORI_BIAS_MIN_ROWS` rows → skip (contributes to not_applicable); compute value-counts; `dominant_share = top_count / n`; if `dominant_share > threshold` → append a finding (severity `high` if share > 0.95 else `medium`). Status = `flagged` if any findings, `ok` if columns checked but balanced, `not_applicable` if no sensitive columns detected.

### `quality.py` — attach the report
In `compute_scorecard(...)`, after computing the 7 dims, add `result["bias"] = examine_bias(df, data_types)`. The `bias` block is NOT included in `_weighted_overall`. One import + one line. The empty-sheet early-return also gets `"bias": {"status": "not_applicable", "checked_columns": [], "findings": [], "row_count": 0}` for shape consistency.

## Data flow
Stage 4 cleaning run → `compute_scorecard(df, data_types, purpose)` → returns `{dimensions, weights, overall, issues, bias, row_count}`. The `bias` report flows out with the existing scorecard response; the FE/consumer can render a "representativeness" panel. No new endpoint — it rides whatever already returns the scorecard.

## Error handling
- `examine_bias` is pure and total: any non-categorical / unparseable column is simply examined by value-counts on its string form; a column with all-null → skipped. Never raises (a malformed column degrades to skipped, not an exception) so it can't break the cleaning run.

## Testing
- **Unit (`tests/test_bias.py`):**
  - `detect_sensitive_columns` matches VN + EN hints, ignores non-sensitive names.
  - `examine_bias`: a skewed `gender` column (95% one value, ≥ min rows) → one `BIAS_REPRESENTATION_IMBALANCE` finding, status `flagged`, `dominant_share` ≈ 0.95.
  - a balanced sensitive column (≈50/50) → no finding, status `ok`.
  - no sensitive columns → status `not_applicable`, empty findings.
  - below `KAORI_BIAS_MIN_ROWS` rows → that column skipped (not_applicable if it was the only sensitive col).
  - env override of `KAORI_BIAS_DOMINANT_SHARE` changes the flag boundary.
- **Integration:** `compute_scorecard(...)` output contains a `bias` key with the expected shape; the 7-dim `overall` is unchanged by adding bias (regression: existing `test_quality_scorecard.py` still passes — bias is additive to the dict, not the weighting).

## Drift artefacts
- No DB migration (pure compute). No schema_snapshot change. No new endpoint/route.
- The scorecard response gains a `bias` key — if the scorecard is modelled in the data-pipeline OpenAPI (`pipeline.openapi.json`) as a typed response, regen `scripts/dump_openapi.py pipeline`; if the scorecard is returned as an untyped dict, no spec change. The plan confirms.
- No new error code → no FE i18n.

## Invariants
No K-1/K-12/K-21 surface (no new tenant-scoped DB, no IDs). K-3 n/a (no LLM — deterministic). Tenet 7 (Vietnamese business language) — finding messages in VN. No-hardcode (Tenet) — threshold + min-rows env-configurable.

## File structure (anticipated — finalised in plan)
- `services/data-pipeline/data_plane/silver/bias.py` (new, pure) + `tests/test_bias.py`
- `services/data-pipeline/data_plane/silver/quality.py` (attach `result["bias"]`)
- drift: pipeline OpenAPI only if the scorecard is typed there

## Open risk
The scorecard's consumers may assume a fixed set of keys; adding `bias` is additive (new key) and shouldn't break dict consumers, but the plan verifies no consumer does strict-key validation on the scorecard dict.
