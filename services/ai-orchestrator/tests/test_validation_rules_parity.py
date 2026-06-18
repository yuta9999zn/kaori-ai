"""
Validation-rules parity test — the BE half of the check VALIDATION_RULES.md
promised but never had.

Loads the shared fixture contract (``tests/fixtures/validation_rules_fixtures.json``)
and runs every case through ``shared/validators.py``, asserting the outcome
(valid/invalid) and the exact ``USR-ERR*`` code match the spec. Adding a row
to VALIDATION_RULES.md → add a fixture case → this fails until the validator
implements it. When the FE restructure resumes (CLAUDE.md §2) the FE form
validator consumes the *same* JSON, so FE↔BE drift becomes a test failure on
whichever side falls behind.

See ``shared/validators.py`` for the field-type → function registry.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_orchestrator.shared import validators

_FIXTURES = json.loads(
    (Path(__file__).parent / "fixtures" / "validation_rules_fixtures.json").read_text(
        encoding="utf-8"
    )
)


def _cases():
    """Flatten the fixture file into (field_type, case) params, skipping _meta."""
    for field_type, cases in _FIXTURES.items():
        if field_type.startswith("_"):
            continue
        for case in cases:
            yield pytest.param(
                field_type,
                case,
                id=f"{field_type}:{case['input']!r}:{'ok' if case['valid'] else case['errcode']}",
            )


def test_every_field_type_has_a_validator():
    """Every fixture field_type must map to a validator (and vice-versa) —
    catches a spec field added to fixtures but not implemented, or drift in
    the registry keys."""
    fixture_types = {k for k in _FIXTURES if not k.startswith("_")}
    assert fixture_types == set(validators.VALIDATORS), (
        f"fixture types {fixture_types} != validator registry {set(validators.VALIDATORS)}"
    )


@pytest.mark.parametrize("field_type, case", list(_cases()))
def test_validation_rule_parity(field_type, case):
    fn = validators.VALIDATORS[field_type]
    opts = case.get("opts", {})
    result = fn(case["input"], **opts)

    assert result.ok is case["valid"], (
        f"{field_type}({case['input']!r}) expected valid={case['valid']} "
        f"but got {result} (reason={result.reason})"
    )
    if not case["valid"]:
        assert result.errcode == case["errcode"], (
            f"{field_type}({case['input']!r}) expected {case['errcode']} "
            f"but got {result.errcode} (reason={result.reason})"
        )


def test_usr_err_codes_map_to_machine_codes():
    """Every USR-ERR* a validator can emit must have a VALIDATION.* mapping
    for RFC 7807 emission (K-14)."""
    emitted = {
        validators.USR_ERR_REQUIRED,
        validators.USR_ERR_FORMAT,
        validators.USR_ERR_LENGTH,
        validators.USR_ERR_RANGE,
    }
    assert emitted <= set(validators.USR_TO_VALIDATION_CODE)
