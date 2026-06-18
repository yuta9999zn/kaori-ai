"""
Issue #3 — LLM output validation + one-shot repair.

When a caller supplies an ``output_schema`` on POST /v1/infer, this
module:

  1. Extracts the JSON payload from the model's free-text completion
     (handles ```json fences, bare JSON, JSON nested inside prose).
  2. Validates against the schema using ``jsonschema``.
  3. On failure, builds a ``repair_prompt`` that re-states the
     original request + the validation error + the schema, asks the
     model to return ONLY JSON matching the schema, and re-invokes
     the provider. Single retry; if the second attempt also fails,
     raises ``StructuredOutputError``.

Design notes
============
* **Pure function, takes a callable** — the validator stays decoupled
  from ``providers.invoke`` / ``invoke_chat``. Router constructs a
  closure ``async def retry(prompt) -> str`` that captures the
  original model_id / method / max_tokens, hands it in, and the
  validator never knows which provider is on the other end. This is
  what lets the same validator work on both single-prompt and chat
  paths (the chat closure builds a synthetic message list with the
  augmented prompt).

* **Single retry only** — multi-round repair burns tokens fast and
  rarely converges. One repair handles the typical "model wrapped
  the JSON in markdown fences" case; deeper failures usually mean
  the schema is too strict for the model's capability, which is a
  caller-side problem ("use a bigger model", "loosen the schema").

* **Returns parsed dict, not string** — saves the caller a
  ``json.loads`` and guarantees the value matches the schema (which
  the caller would have to revalidate anyway).
"""
from __future__ import annotations

import json
import re
from typing import Awaitable, Callable, Optional

import structlog

try:
    from jsonschema import Draft202012Validator, ValidationError
    from jsonschema.exceptions import SchemaError
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "jsonschema is required for LLM output validation. "
        "Add `jsonschema` to services/llm-gateway/requirements.txt."
    ) from e

log = structlog.get_logger()


# ─── Errors ──────────────────────────────────────────────────────

class StructuredOutputError(Exception):
    """Raised when the gateway cannot produce a payload that matches
    ``output_schema`` after the repair attempt. Carries enough context
    for the router to build a useful 502 RFC 7807 body and for the
    caller log to be actionable."""

    def __init__(
        self,
        reason: str,
        *,
        attempts: int,
        last_completion: str,
        last_error: Optional[str] = None,
    ):
        super().__init__(reason)
        self.reason = reason
        self.attempts = attempts
        self.last_completion = last_completion
        self.last_error = last_error


# ─── JSON extraction ─────────────────────────────────────────────

# Models love to wrap JSON in markdown fences, occasionally with a
# language tag. Match either ```json ... ``` or bare ``` ... ```;
# tolerate leading/trailing whitespace.
_FENCE_RE = re.compile(
    r"```(?:json|JSON)?\s*\n?(?P<body>.*?)\n?```",
    re.DOTALL,
)


def extract_json(completion: str) -> tuple[Optional[dict], Optional[str]]:
    """Return ``(parsed_dict, error_message)``. Exactly one is non-None.

    Strategy (tried in order, first success wins):

      1. The whole completion parses as JSON object. Hot path for
         well-behaved models that just return the dict.
      2. A ```json``` fenced block exists and parses. Most common
         fallback — Qwen 2.5 wraps non-trivial outputs.
      3. The first ``{...}`` substring (greedy match across newlines)
         parses. Last resort for "explanation text + JSON" responses;
         risky if the model nests braces in prose, but the schema
         validator will catch shape mismatches.

    Arrays at the top level are valid JSON but not what we want — the
    rest of the system treats LLM-structured outputs as objects. An
    explicit error helps the caller spot a schema design bug fast.
    """
    if not completion or not completion.strip():
        return None, "empty completion"

    text = completion.strip()

    # 1. Whole completion is JSON.
    parsed = _try_parse(text)
    if parsed is not None:
        if not isinstance(parsed, dict):
            return None, (
                f"top-level JSON is {type(parsed).__name__}, not object — "
                "Issue #3 schemas always describe JSON objects"
            )
        return parsed, None

    # 2. Fenced block.
    fence_match = _FENCE_RE.search(text)
    if fence_match:
        body = fence_match.group("body").strip()
        parsed = _try_parse(body)
        if parsed is not None:
            if not isinstance(parsed, dict):
                return None, (
                    f"fenced JSON is {type(parsed).__name__}, not object"
                )
            return parsed, None

    # 3. First {...} block. Greedy match across newlines so nested
    #    objects survive. We don't try to handle multiple top-level
    #    objects — the model should pick one.
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if 0 <= brace_start < brace_end:
        candidate = text[brace_start : brace_end + 1]
        parsed = _try_parse(candidate)
        if parsed is not None and isinstance(parsed, dict):
            return parsed, None

    return None, "no JSON object found in completion"


def _try_parse(text: str):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


# ─── Validation ──────────────────────────────────────────────────

def _validate(payload: dict, schema: dict) -> Optional[str]:
    """Return None on success, an error message on failure. We don't
    surface the full ``ValidationError`` because the caller (router)
    needs a one-line reason to put in the audit log + RFC 7807 body."""
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as e:
        # Caller bug — they passed an invalid schema. Return the
        # error so the router can 400 instead of 502.
        return f"output_schema is invalid JSONSchema: {e.message}"

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    if not errors:
        return None
    first = errors[0]
    path = "/" + "/".join(str(p) for p in first.path) if first.path else "/"
    return f"{first.message} at {path}"


# ─── Repair-prompt construction ──────────────────────────────────

def repair_prompt(*, original_prompt: str, schema: dict, error: str,
                  bad_completion: str) -> str:
    """Build the augmented prompt for the second attempt.

    Format chosen for Qwen 2.5 (default internal model) — bullet-point
    sections + an explicit "Return ONLY JSON" instruction reduces the
    "I tried but here's some explanation" failure mode. Anthropic /
    OpenAI accept the same shape, so we don't branch by provider.

    The schema is dumped in compact JSON, not pretty-printed — gives
    the model fewer line-break tokens to imitate, which helps it
    return a single-line JSON response.
    """
    # Truncate the bad completion shown in the prompt so we don't burn
    # context on a runaway model spilling 4000 tokens of explanation.
    bad = bad_completion if len(bad_completion) <= 1000 else (
        bad_completion[:1000] + "...[truncated]"
    )
    return (
        "Your previous response failed JSON schema validation.\n"
        "\n"
        f"Original request:\n{original_prompt}\n"
        "\n"
        f"Required JSON schema:\n{json.dumps(schema, separators=(',', ':'))}\n"
        "\n"
        f"Validation error:\n{error}\n"
        "\n"
        "Your previous (invalid) response:\n"
        f"{bad}\n"
        "\n"
        "Return ONLY a JSON object that matches the schema. No prose, "
        "no markdown fences, no explanation. Just the JSON."
    )


# ─── Orchestrator ────────────────────────────────────────────────

async def validate_or_repair(
    *,
    completion: str,
    schema: dict,
    original_prompt: str,
    retry_fn: Callable[[str], Awaitable[str]],
) -> tuple[dict, bool]:
    """Validate ``completion`` against ``schema``; on failure, run
    one repair round via ``retry_fn`` and validate again.

    Returns ``(parsed_dict, was_repaired)``.

    Raises:
      StructuredOutputError: when the second attempt also fails, OR
        when ``schema`` itself is malformed JSONSchema (caller bug).
    """
    # First attempt — extract + validate.
    parsed, extract_error = extract_json(completion)
    if parsed is not None:
        validate_error = _validate(parsed, schema)
        if validate_error is None:
            return parsed, False
        first_error = validate_error
    else:
        first_error = extract_error or "could not parse JSON"

    log.info(
        "llm_gateway.output.repair_attempt",
        first_error=first_error,
        completion_chars=len(completion),
    )

    # Repair attempt — single retry only. Multi-round repair burns
    # tokens fast and rarely converges; deeper failures point at a
    # mismatched schema, which is a caller problem.
    augmented = repair_prompt(
        original_prompt=original_prompt,
        schema=schema,
        error=first_error,
        bad_completion=completion,
    )
    try:
        repaired_completion = await retry_fn(augmented)
    except Exception as exc:
        # The retry call itself failed (provider down, timeout). We
        # can't tell the caller "schema invalid" because we don't
        # know — re-raise as StructuredOutputError carrying both the
        # original validation failure and the retry failure so logs
        # have both signals.
        raise StructuredOutputError(
            reason=f"repair attempt failed: {exc}",
            attempts=2,
            last_completion=completion,
            last_error=first_error,
        ) from exc

    parsed, extract_error = extract_json(repaired_completion)
    if parsed is None:
        raise StructuredOutputError(
            reason="repaired completion did not contain a JSON object",
            attempts=2,
            last_completion=repaired_completion,
            last_error=extract_error,
        )

    validate_error = _validate(parsed, schema)
    if validate_error is not None:
        raise StructuredOutputError(
            reason="repaired completion did not match schema",
            attempts=2,
            last_completion=repaired_completion,
            last_error=validate_error,
        )

    return parsed, True
