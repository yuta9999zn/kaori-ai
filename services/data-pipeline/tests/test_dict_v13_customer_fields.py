"""Regression — language_dictionary v1.3 customer/transaction fields.

Loads the REAL config/language_dictionary.json (not the mocked fixture dict the
whitebox tests use) and asserts the four fields added in v1.3 resolve. These
were the live B2 schema-mapping bugs from the pilot pipeline test:

  • email / gender  → previously "Chưa nhận diện" (no canonical entry)
  • age             → previously fuzzy-stole canonical 'usage' (u-s-AGE)
  • payment_method  → previously fuzzy-stole canonical 'amount' (alias 'payment'),
                      double-mapping with the real line-total column.

The fix is data, not code: exact-match (cascade step 1) now wins for all four,
and payment_method being its OWN category resolves the amount double-map.
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest

# config/language_dictionary.json sits at the repo root: services/data-pipeline/tests → ../../../config
_REAL_DICT = Path(__file__).resolve().parents[3] / "config" / "language_dictionary.json"


@pytest.fixture(scope="module")
def real_mapper():
    """Reimport column_mapper bound to the REAL dictionary file."""
    if not _REAL_DICT.exists():
        pytest.skip(f"real dict not found at {_REAL_DICT}")
    prev = os.environ.get("LANGUAGE_DICT_PATH")
    os.environ["LANGUAGE_DICT_PATH"] = str(_REAL_DICT)
    import data_plane.bronze.column_mapper as cm
    cm = importlib.reload(cm)
    yield cm
    # restore env + module state for other tests
    if prev is None:
        os.environ.pop("LANGUAGE_DICT_PATH", None)
    else:
        os.environ["LANGUAGE_DICT_PATH"] = prev
    importlib.reload(cm)


def _by_source(mappings):
    return {m["source_column"]: m for m in mappings}


def test_four_new_fields_exact_match_en(real_mapper):
    cols = ["email", "gender", "age", "payment_method"]
    out = _by_source(real_mapper.map_columns(cols, detected_language="en"))
    assert out["email"]["canonical_name"] == "email"
    assert out["gender"]["canonical_name"] == "gender"
    assert out["age"]["canonical_name"] == "age"
    assert out["payment_method"]["canonical_name"] == "payment_method"
    # all exact (cascade step 1) → confidence 1.0, no LLM fallback needed
    assert all(out[c]["method"] == "exact_match" for c in cols)
    assert all(out[c]["confidence"] == 1.0 for c in cols)


def test_payment_method_no_longer_steals_amount(real_mapper):
    """The original false positive: payment_method must NOT map to amount, and
    the real line-total column keeps 'amount' (no double-map conflict)."""
    out = _by_source(real_mapper.map_columns(
        ["payment_method", "total_amount"], detected_language="en"))
    assert out["payment_method"]["canonical_name"] == "payment_method"
    assert out["total_amount"]["canonical_name"] == "amount"


def test_age_does_not_steal_usage(real_mapper):
    out = _by_source(real_mapper.map_columns(["age"], detected_language="en"))
    assert out["age"]["canonical_name"] == "age"
    assert out["age"]["data_type"] == "integer"


def test_category_data_types(real_mapper):
    out = _by_source(real_mapper.map_columns(
        ["gender", "payment_method"], detected_language="en"))
    assert out["gender"]["data_type"] == "category"
    assert out["payment_method"]["data_type"] == "category"


def test_vietnamese_aliases_resolve(real_mapper):
    out = _by_source(real_mapper.map_columns(
        ["giới tính", "tuổi", "phương thức thanh toán"], detected_language="vi"))
    assert out["giới tính"]["canonical_name"] == "gender"
    assert out["tuổi"]["canonical_name"] == "age"
    assert out["phương thức thanh toán"]["canonical_name"] == "payment_method"
