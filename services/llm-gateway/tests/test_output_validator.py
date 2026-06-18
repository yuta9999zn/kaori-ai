"""
Tests for ``output_validator.py`` — Issue #3 LLM output validation +
one-shot repair.

Three layers under test:

  1. ``extract_json`` — pure function, edge cases around how models
     wrap JSON (raw, ``` fences, prose + JSON, top-level array, etc.)
  2. ``_validate`` — JSONSchema check, including the caller-bug case
     where the schema itself is invalid.
  3. ``validate_or_repair`` — orchestrator, with the ``retry_fn``
     callable mocked so we can drive both the "repair succeeds" and
     "repair still fails" branches without a real LLM.

The ``retry_fn`` is intentionally an async callable in the production
signature, so each test passes an ``AsyncMock`` (or a tiny coroutine
function) that returns a canned completion.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from llm_gateway.output_validator import (
    StructuredOutputError,
    _validate,
    extract_json,
    repair_prompt,
    validate_or_repair,
)


_SIMPLE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["canonical", "confidence"],
    "properties": {
        "canonical":  {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}


# ─── extract_json ────────────────────────────────────────────────

def test_extract_returns_dict_when_completion_is_raw_json():
    out, err = extract_json('{"canonical":"revenue","confidence":0.91}')
    assert err is None
    assert out == {"canonical": "revenue", "confidence": 0.91}


def test_extract_handles_leading_and_trailing_whitespace():
    out, _ = extract_json('  \n {"x": 1}\n  ')
    assert out == {"x": 1}


def test_extract_strips_json_fenced_block():
    completion = (
        "Here is the answer:\n"
        "```json\n"
        '{"canonical": "revenue", "confidence": 0.85}\n'
        "```\n"
        "Hope that helps."
    )
    out, err = extract_json(completion)
    assert err is None
    assert out == {"canonical": "revenue", "confidence": 0.85}


def test_extract_strips_unlabeled_fence():
    completion = "```\n{\"x\": 1}\n```"
    out, _ = extract_json(completion)
    assert out == {"x": 1}


def test_extract_falls_back_to_first_brace_block_in_prose():
    """Last-resort path — model wrote a paragraph then the JSON. The
    extractor finds {first... last} and tries to parse it. Schema
    validator catches shape mismatches downstream so this path is OK
    to be loose."""
    completion = (
        "Tôi đã phân tích cột này và đây là kết quả:\n\n"
        '{"canonical": "revenue", "confidence": 0.7}\n\n'
        "Cần thêm sample data để chính xác hơn."
    )
    out, err = extract_json(completion)
    assert err is None
    assert out == {"canonical": "revenue", "confidence": 0.7}


def test_extract_handles_nested_braces_in_brace_fallback():
    completion = (
        "Result: {\"outer\": {\"inner\": 1}, \"k\": [1,2,3]}"
    )
    out, _ = extract_json(completion)
    assert out == {"outer": {"inner": 1}, "k": [1, 2, 3]}


def test_extract_rejects_top_level_array_with_explicit_error():
    """All Issue #3 schemas describe JSON OBJECTS. A top-level array
    is valid JSON but not what the validator expects — better to
    surface the type mismatch with a clear message than to crash
    deeper in jsonschema with an obscure error."""
    out, err = extract_json('[1, 2, 3]')
    assert out is None
    assert err is not None
    assert "list" in err or "array" in err.lower() or "object" in err


def test_extract_returns_error_when_no_json_present():
    out, err = extract_json("I cannot answer this question.")
    assert out is None
    assert err and "no JSON" in err


def test_extract_returns_error_on_empty_completion():
    out, err = extract_json("")
    assert out is None
    assert err == "empty completion"

    out, err = extract_json("   \n  ")
    assert out is None
    assert err == "empty completion"


def test_extract_returns_error_on_unparseable_garbage():
    out, err = extract_json("{not valid json at all")
    assert out is None
    assert err is not None


# ─── _validate ───────────────────────────────────────────────────

def test_validate_returns_none_for_matching_payload():
    err = _validate({"canonical": "revenue", "confidence": 0.5}, _SIMPLE_SCHEMA)
    assert err is None


def test_validate_returns_path_for_missing_required():
    err = _validate({"canonical": "revenue"}, _SIMPLE_SCHEMA)
    assert err is not None
    assert "confidence" in err


def test_validate_returns_path_for_wrong_type():
    err = _validate(
        {"canonical": "revenue", "confidence": "high"}, _SIMPLE_SCHEMA
    )
    assert err is not None
    assert "confidence" in err or "number" in err


def test_validate_rejects_extra_field_when_schema_locks_additional():
    err = _validate(
        {"canonical": "revenue", "confidence": 0.5, "extra": "leak"},
        _SIMPLE_SCHEMA,
    )
    assert err is not None
    assert "extra" in err or "additional" in err.lower()


def test_validate_returns_caller_bug_message_for_bad_schema():
    """Caller passed a schema that isn't a valid JSONSchema — surface
    a different message so the router can return 400 instead of
    burning a repair round."""
    bad_schema = {"type": "object", "properties": {"x": {"type": "not-a-type"}}}
    err = _validate({}, bad_schema)
    assert err is not None
    assert "invalid JSONSchema" in err


# ─── repair_prompt ───────────────────────────────────────────────

def test_repair_prompt_includes_original_schema_and_error():
    rp = repair_prompt(
        original_prompt="Map column 'doanh thu' to canonical English name.",
        schema=_SIMPLE_SCHEMA,
        error="'confidence' is a required property",
        bad_completion="The canonical is revenue.",
    )
    assert "Map column 'doanh thu'" in rp
    assert "'confidence' is a required property" in rp
    assert '"required":["canonical","confidence"]' in rp
    assert "Return ONLY a JSON object" in rp


def test_repair_prompt_truncates_long_bad_completion():
    """A runaway model could spill 4 KB of explanation. We cap the
    "your previous response" section so the augmented prompt doesn't
    push past the model's context window."""
    big = "x" * 5000
    rp = repair_prompt(
        original_prompt="prompt", schema=_SIMPLE_SCHEMA,
        error="err", bad_completion=big,
    )
    assert "...[truncated]" in rp
    # The truncated section is at most 1000 chars + marker; the rest
    # of the prompt (instructions + schema) is small + bounded.
    assert len(rp) < 2500


# ─── validate_or_repair (orchestrator) ───────────────────────────

@pytest.mark.asyncio
async def test_first_attempt_valid_returns_no_repair():
    """Hot path: model nailed the JSON on the first try. retry_fn
    must NOT be called."""
    retry = AsyncMock()
    parsed, was_repaired = await validate_or_repair(
        completion='{"canonical":"revenue","confidence":0.9}',
        schema=_SIMPLE_SCHEMA,
        original_prompt="Map column",
        retry_fn=retry,
    )
    assert was_repaired is False
    assert parsed == {"canonical": "revenue", "confidence": 0.9}
    retry.assert_not_called()


@pytest.mark.asyncio
async def test_first_fails_repair_succeeds_returns_was_repaired_true():
    """Common path — first attempt missing a field, second attempt
    (after repair prompt) returns valid JSON."""
    retry = AsyncMock(return_value='{"canonical":"revenue","confidence":0.85}')

    parsed, was_repaired = await validate_or_repair(
        completion='{"canonical":"revenue"}',  # missing confidence
        schema=_SIMPLE_SCHEMA,
        original_prompt="Map column 'doanh thu'.",
        retry_fn=retry,
    )

    assert was_repaired is True
    assert parsed == {"canonical": "revenue", "confidence": 0.85}
    retry.assert_awaited_once()
    # The augmented prompt (passed to retry_fn) must contain BOTH the
    # original prompt AND the validation error so the model has the
    # right signal to fix it.
    augmented = retry.await_args.args[0]
    assert "Map column 'doanh thu'" in augmented
    assert "confidence" in augmented


@pytest.mark.asyncio
async def test_repair_returns_invalid_json_raises_structured_output_error():
    """Second attempt also failed — surface a StructuredOutputError
    with attempts=2 so the router can return 502 + the audit log
    captures the bad outputs."""
    retry = AsyncMock(return_value="I really can't do this.")

    with pytest.raises(StructuredOutputError) as exc:
        await validate_or_repair(
            completion='{"canonical":"revenue"}',
            schema=_SIMPLE_SCHEMA,
            original_prompt="prompt",
            retry_fn=retry,
        )

    assert exc.value.attempts == 2
    assert "JSON object" in exc.value.reason or "did not contain" in exc.value.reason
    assert exc.value.last_completion == "I really can't do this."


@pytest.mark.asyncio
async def test_repair_returns_valid_json_but_wrong_shape_raises():
    """Edge case: repair returned parseable JSON, but it doesn't
    match the schema either. Different error path inside the
    orchestrator — pin so a regression doesn't silently accept the
    wrong shape."""
    retry = AsyncMock(return_value='{"foo": "bar"}')

    with pytest.raises(StructuredOutputError) as exc:
        await validate_or_repair(
            completion='{"canonical":"revenue"}',
            schema=_SIMPLE_SCHEMA,
            original_prompt="prompt",
            retry_fn=retry,
        )

    assert exc.value.attempts == 2
    assert "did not match schema" in exc.value.reason
    # last_error carries the validation message so caller logs are
    # self-explanatory. With additionalProperties=false on the test
    # schema, the first error is the unexpected 'foo' field rather
    # than the missing 'canonical' — pin whichever surfaces first via
    # jsonschema's iter_errors ordering.
    assert exc.value.last_error
    assert ("foo" in exc.value.last_error
            or "canonical" in exc.value.last_error
            or "Additional" in exc.value.last_error)


@pytest.mark.asyncio
async def test_retry_fn_raising_propagates_as_structured_output_error():
    """If the second provider call itself fails (network, timeout),
    we want the same exception class so the router has one branch to
    handle. Inner exception is preserved via __cause__ for tracing."""
    boom = RuntimeError("ollama timeout")
    retry = AsyncMock(side_effect=boom)

    with pytest.raises(StructuredOutputError) as exc:
        await validate_or_repair(
            completion='{"canonical":"revenue"}',  # invalid (missing confidence)
            schema=_SIMPLE_SCHEMA,
            original_prompt="p",
            retry_fn=retry,
        )

    assert exc.value.attempts == 2
    assert "repair attempt failed" in exc.value.reason
    assert exc.value.__cause__ is boom


@pytest.mark.asyncio
async def test_first_attempt_extract_failure_still_triggers_repair():
    """First attempt didn't even contain JSON (e.g., model just wrote
    prose). Repair round still runs; the augmented prompt explicitly
    asks for ONLY JSON. Pin the contract so a future "skip repair on
    extraction failure" optimisation has to be a deliberate change."""
    retry = AsyncMock(return_value='{"canonical":"revenue","confidence":0.6}')

    parsed, was_repaired = await validate_or_repair(
        completion="I don't know how to map this column.",
        schema=_SIMPLE_SCHEMA,
        original_prompt="Map column",
        retry_fn=retry,
    )

    assert was_repaired is True
    assert parsed == {"canonical": "revenue", "confidence": 0.6}
    retry.assert_awaited_once()


@pytest.mark.asyncio
async def test_returns_canonical_dict_not_string():
    """Caller is supposed to use parsed_json directly without a
    json.loads. Verify the orchestrator returns a real dict so a
    future regression that surfaces a string would fail this test
    instead of silently breaking every caller."""
    parsed, _ = await validate_or_repair(
        completion='{"canonical":"revenue","confidence":0.5}',
        schema=_SIMPLE_SCHEMA,
        original_prompt="p",
        retry_fn=AsyncMock(),
    )
    assert isinstance(parsed, dict)
    assert parsed["canonical"] == "revenue"
