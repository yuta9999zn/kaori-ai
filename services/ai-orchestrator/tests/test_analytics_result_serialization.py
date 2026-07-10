"""
Tests for NaN/Infinity-safe analysis result serialization.

Incident 2026-07-10 (demo AABW, run b067818e): time_series returns
delta_pct = value.pct_change() whose FIRST row is NaN; json.dumps emits
the bare token `NaN`, which Postgres JSONB rejects ("invalid input
syntax for type json — Token NaN"), flipping an otherwise-successful
template run to status='error'. Results must be sanitized at the
serialization boundary: non-finite floats become JSON null.
"""
import json
import math

import numpy as np
import pytest

from ai_orchestrator.reasoning.legacy_analytics.runner import _dump_result_json


def test_nan_becomes_null():
    payload = [{"id": "trend", "data": [{"date": "2026-01-31", "delta_pct": float("nan")}]}]
    out = json.loads(_dump_result_json(payload))
    assert out[0]["data"][0]["delta_pct"] is None


def test_numpy_nan_and_infinity_become_null():
    payload = {"a": np.float64("nan"), "b": float("inf"), "c": -math.inf}
    out = json.loads(_dump_result_json(payload))
    assert out == {"a": None, "b": None, "c": None}


def test_finite_values_and_structure_preserved():
    payload = [{"id": "stats", "values": [1, 2.5, "text", None, True],
                "nested": {"x": 0.0}}]
    out = json.loads(_dump_result_json(payload))
    assert out == payload


def test_output_is_valid_strict_json():
    # Postgres JSONB parses strict JSON — the dumped string must not
    # contain bare NaN/Infinity tokens anywhere.
    payload = {"series": [float("nan"), math.inf, 1.5]}
    dumped = _dump_result_json(payload)
    assert "NaN" not in dumped
    assert "Infinity" not in dumped
