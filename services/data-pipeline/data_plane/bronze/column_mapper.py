"""
Column Mapper — 3-step cascade using config/language_dictionary.json.

Step 1: Exact keyword match → confidence 1.0
Step 2: Fuzzy substring match (rapidfuzz) → confidence 0.65–0.95
Step 3: LLM (Qwen) semantic inference → confidence 0.4–0.7

K-6: Every mapping decision logged to decision_audit_log.
"""
import json
import os
import uuid
from pathlib import Path
from typing import Optional

import structlog
from rapidfuzz import fuzz, process

log = structlog.get_logger()

# Load language dictionary once at import
_DICT_PATH = os.getenv("LANGUAGE_DICT_PATH", "/app/config/language_dictionary.json")
_LANGUAGE_DICT: dict = {}

try:
    with open(_DICT_PATH, encoding="utf-8") as f:
        _raw = json.load(f)
    # The on-disk schema is {version, description, fields: {canonical:
    # {description, data_type?, aliases: {en, vi, ...}}}}. _get_synonyms /
    # _exact_match below expect a flattened entry where lang codes live
    # at the top level alongside data_type/description, so we unfold
    # `aliases` once at load time.
    fields = _raw.get("fields", _raw) if isinstance(_raw, dict) else {}
    for canonical, field_data in fields.items():
        if not isinstance(field_data, dict):
            continue
        flat = {
            k: v for k, v in field_data.items() if k != "aliases"
        }
        flat.update(field_data.get("aliases", {}) or {})
        _LANGUAGE_DICT[canonical] = flat
    log.info("column_mapper.dict_loaded", path=_DICT_PATH,
             canonical_count=len(_LANGUAGE_DICT))
except FileNotFoundError:
    log.warning("column_mapper.dict_not_found", path=_DICT_PATH)

# Uncertainty flag constants
FLAG_LOW_CONFIDENCE = "LOW_CONFIDENCE"
FLAG_AMBIGUOUS_TOP2 = "AMBIGUOUS_TOP2"
FLAG_LANG_MISMATCH = "LANG_MISMATCH"
FLAG_LLM_FALLBACK = "LLM_FALLBACK_USED"
FLAG_NO_MATCH = "NO_CANONICAL_MATCH"


def map_columns(
    source_columns: list[str],
    detected_language: str = "unknown",
    run_id: Optional[str] = None,
    enterprise_id: Optional[str] = None,
) -> list[dict]:
    """
    Map source column names to canonical names.

    Returns list of mapping decisions, each:
    {
      source_column, canonical_name, data_type, confidence,
      method, uncertainty_flags, alternatives, sample_values
    }
    """
    mappings = []
    for col in source_columns:
        mapping = _map_single_column(col, detected_language)
        mappings.append(mapping)
    return mappings


def _map_single_column(source: str, detected_lang: str) -> dict:
    """Try 3-step cascade for a single column name."""
    normalized = _normalize(source)

    # Step 1: Exact match
    exact_result = _exact_match(normalized, detected_lang)
    if exact_result:
        return {
            "source_column": source,
            "canonical_name": exact_result["canonical"],
            "data_type": exact_result.get("data_type", "text"),
            "confidence": 1.0,
            "method": "exact_match",
            "uncertainty_flags": [],
            "alternatives": [],
        }

    # Step 2: Fuzzy match
    fuzzy_result = _fuzzy_match(normalized, detected_lang)
    if fuzzy_result and fuzzy_result["confidence"] >= 0.65:
        flags = []
        if fuzzy_result["confidence"] < 0.8:
            flags.append(FLAG_LOW_CONFIDENCE)
        if fuzzy_result.get("ambiguous"):
            flags.append(FLAG_AMBIGUOUS_TOP2)
        return {
            "source_column": source,
            "canonical_name": fuzzy_result["canonical"],
            "data_type": fuzzy_result.get("data_type", "text"),
            "confidence": fuzzy_result["confidence"],
            "method": "fuzzy_match",
            "uncertainty_flags": flags,
            "alternatives": fuzzy_result.get("alternatives", []),
        }

    # Step 3: No match found (LLM fallback done in ai-orchestrator)
    return {
        "source_column": source,
        "canonical_name": source.lower().replace(" ", "_"),  # passthrough
        "data_type": "text",
        "confidence": 0.0,
        "method": "no_match",
        "uncertainty_flags": [FLAG_NO_MATCH, FLAG_LLM_FALLBACK],
        "alternatives": [],
    }


def _exact_match(normalized: str, lang: str) -> Optional[dict]:
    """Check if normalized column matches any synonym exactly."""
    for canonical, entry in _LANGUAGE_DICT.items():
        synonyms_for_lang = _get_synonyms(entry, lang)
        synonyms_all = _get_synonyms(entry, None)  # all languages
        for syn in synonyms_for_lang + synonyms_all:
            if _normalize(syn) == normalized:
                return {"canonical": canonical, "data_type": entry.get("data_type", "text")}
    return None


def _fuzzy_match(normalized: str, lang: str) -> Optional[dict]:
    """Fuzzy substring match using rapidfuzz."""
    if not _LANGUAGE_DICT:
        return None

    best_score = 0.0
    best_canonical = None
    best_dtype = "text"
    second_best = 0.0

    for canonical, entry in _LANGUAGE_DICT.items():
        synonyms = _get_synonyms(entry, lang) + _get_synonyms(entry, None)
        for syn in synonyms:
            syn_norm = _normalize(syn)
            score = fuzz.token_set_ratio(normalized, syn_norm) / 100.0
            if score > best_score:
                second_best = best_score
                best_score = score
                best_canonical = canonical
                best_dtype = entry.get("data_type", "text")
            elif score > second_best:
                second_best = score

    if best_canonical is None or best_score < 0.5:
        return None

    ambiguous = (best_score - second_best) < 0.15
    return {
        "canonical": best_canonical,
        "data_type": best_dtype,
        "confidence": round(best_score * 0.95, 4),  # discount to 0.65–0.95 range
        "ambiguous": ambiguous,
        "alternatives": [],
    }


def _get_synonyms(entry: dict, lang: Optional[str]) -> list[str]:
    """Extract synonyms from language_dictionary entry for a given language."""
    if lang and lang in entry:
        v = entry[lang]
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            return [v]
    if lang is None:
        # Return all synonyms from all language keys
        synonyms = []
        for key, val in entry.items():
            if key in ("data_type", "description", "examples"):
                continue
            if isinstance(val, list):
                synonyms.extend(val)
            elif isinstance(val, str):
                synonyms.append(val)
        return synonyms
    return []


def _normalize(text: str) -> str:
    """Lowercase, strip whitespace, remove special chars."""
    import unicodedata
    text = text.lower().strip()
    text = unicodedata.normalize("NFC", text)
    # Remove common separators
    text = text.replace("_", " ").replace("-", " ").replace(".", " ")
    return " ".join(text.split())


# ── Value-based type sniffing ────────────────────────────────────────────────
# The name-based cascade (exact/fuzzy/llm) yields a semantic data_type ONLY
# when the column NAME is in language_dictionary.json — and today every dict
# entry omits data_type, so unmatched columns default to "text" even when the
# cells are obviously numbers/dates. Sniffing the actual values closes that
# gap so step-2 shows the right "Định dạng" and Silver gets the right cast.

import re as _re
from datetime import datetime as _dt

# Accept these date layouts before giving up (DD/MM/YYYY is VN-default).
_DATE_FORMATS = (
    "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y",
    "%Y/%m/%d", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S",
)


def _parses_as_number(s: str) -> tuple[bool, bool]:
    """(is_number, is_integer). Leading-zero multi-digit strings are treated
    as identifiers (phone/zip/id), NOT numbers — to_numeric would mangle them."""
    s = s.strip().replace(",", "")  # tolerate thousands separators
    if not s:
        return False, False
    if len(s) > 1 and s[0] == "0" and s[1].isdigit():
        return False, False
    try:
        float(s)
    except (ValueError, TypeError):
        return False, False
    return True, ("." not in s and "e" not in s.lower())


def _parses_as_date(s: str) -> bool:
    s = s.strip()
    if not s or s.isdigit():       # bare integers are numbers, not dates
        return False
    for fmt in _DATE_FORMATS:
        try:
            _dt.strptime(s, fmt)
            return True
        except (ValueError, TypeError):
            continue
    return False


# Tolerate a small fraction of noise (a stray "N/A", a typo) instead of letting
# a SINGLE bad cell collapse the guess to text. The old all-or-nothing rule left
# real numeric/date columns typed as text — the root of PR #257 ("Silver stores
# numerics as strings → analyze: no numeric column"). Thresholds are deliberately
# high, so a genuinely mixed column (e.g. 1/3 garbage) still returns None.
# Ported in spirit from NNL-Harness profiler date_score / money_score.
_SNIFF_DATE_MIN = 0.90
_SNIFF_NUM_MIN = 0.95


def sniff_value_type(values: list) -> Optional[str]:
    """Infer a column's type from sample cell values, tolerating light noise.

    Returns ``"date"`` / ``"integer"`` / ``"numeric"`` when the share of
    conforming non-empty samples clears the threshold, else ``None`` (caller
    keeps the name-based type). A mostly-numeric column with the odd "N/A" is
    now typed numeric; a genuinely mixed column still collapses to None — still
    biased toward under-detection over mistyping.
    """
    cells = [str(v).strip() for v in values if v not in (None, "")]
    cells = [c for c in cells if c]
    if not cells:
        return None
    n = len(cells)

    date_frac = sum(_parses_as_date(c) for c in cells) / n
    if date_frac >= _SNIFF_DATE_MIN:
        return "date"

    num_flags = [_parses_as_number(c) for c in cells]
    num_frac = sum(is_num for is_num, _ in num_flags) / n
    if num_frac >= _SNIFF_NUM_MIN:
        # integer only if EVERY parsed number is integral (non-numbers ignored)
        ints = [is_int for is_num, is_int in num_flags if is_num]
        return "integer" if all(ints) else "numeric"
    return None


def is_unnamed(name: str) -> bool:
    """True for pandas auto-generated names of blank columns ("Unnamed: 3")
    or columns whose header was itself empty/whitespace."""
    n = (name or "").strip()
    return n == "" or bool(_re.match(r"^Unnamed:?\s*\d*$", n, _re.IGNORECASE))


def header_looks_like_data(name: str) -> bool:
    """True when the column NAME is itself a date or number — a strong sign a
    data row was mistaken for the header (e.g. a header cell '2024-04-17')."""
    n = (name or "").strip()
    if not n or is_unnamed(n):
        return False
    return _parses_as_date(n) or _parses_as_number(n)[0]
