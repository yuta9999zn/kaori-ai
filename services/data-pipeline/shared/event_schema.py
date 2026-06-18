"""
Issue #4 — Kafka event schema validator.

Loads JSON Schema files from ``infrastructure/kafka/schemas/`` and
validates Kafka event payloads against them on both sides of the
pipe:

  Producer side
  -------------
  ``shared.outbox.enqueue_event`` calls ``validate_event(topic,
  payload)`` BEFORE writing the outbox row. A missing required field
  raises ``InvalidEventError`` and the caller's transaction rolls
  back — the bug surfaces immediately at the producer site, not three
  hops later in a consumer log.

  Consumer side
  -------------
  Each consumer wraps the dispatch in
  ``raise_or_dlq(topic, payload, dlq_producer)``. Bad payloads go to
  ``kaori.dlq.<topic>`` with the original key + a ``schema_error``
  header; the consumer commits the offset and moves on, so one bad
  payload never blocks the rest of the partition.

Caching
=======
Schemas are loaded once per process and kept in module state. Pre-
loading the bundle at import time would lengthen cold-start by ~40 ms
for no benefit (most Phase-1 callers only ever produce one or two
topics); lazy load with a dict cache keeps the cost on the first call
and zero thereafter.

Schema discovery
================
The schemas live at ``infrastructure/kafka/schemas/<topic>.json`` at
the repo root. We walk up from this file's location until we hit the
``infrastructure`` directory — works for tests run from the service
root, for in-Docker installs (where the file is mounted at a fixed
path), and for ad-hoc CLI invocations.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import structlog

try:
    # jsonschema is a small dep (~80 KB) and the format-specifier
    # extras (date-time, uri) ship with the base wheel since 4.x.
    from jsonschema import Draft202012Validator, ValidationError
    from jsonschema.exceptions import SchemaError
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "jsonschema is required for Kafka event validation. "
        "Add `jsonschema` to services/<svc>/requirements.txt."
    ) from e

log = structlog.get_logger()


# ─── Errors ──────────────────────────────────────────────────────

class InvalidEventError(Exception):
    """Raised when a payload fails validation against its topic
    schema. ``topic`` and ``reason`` are surfaced so the structured
    log is grep-able by either dimension."""

    def __init__(self, topic: str, reason: str, payload: Optional[dict] = None):
        super().__init__(f"{topic}: {reason}")
        self.topic = topic
        self.reason = reason
        self.payload = payload


class UnknownTopicError(Exception):
    """Raised when ``validate_event`` is called with a topic that has
    no committed schema. We fail closed: an unknown topic means the
    schema PR didn't ship, OR the producer typo'd the topic constant."""


# ─── Schema discovery + cache ────────────────────────────────────

_SCHEMA_DIR_NAME = Path("infrastructure") / "kafka" / "schemas"
_validator_cache: dict[str, Draft202012Validator] = {}
_schema_root: Optional[Path] = None


def _find_schema_root() -> Path:
    """Locate ``infrastructure/kafka/schemas`` by walking up from this
    file. Cached across calls because the answer can't change at run
    time."""
    global _schema_root
    if _schema_root is not None:
        return _schema_root

    here = Path(__file__).resolve()
    for ancestor in [here, *here.parents]:
        candidate = ancestor / _SCHEMA_DIR_NAME
        if candidate.is_dir():
            _schema_root = candidate
            return candidate

    raise RuntimeError(
        f"Could not locate {_SCHEMA_DIR_NAME} when walking up from "
        f"{here}. Schema directory must exist at the repo root."
    )


def _load_validator(topic: str) -> Draft202012Validator:
    """Return a cached validator for the given topic. Raises
    ``UnknownTopicError`` when the file is missing — never logs and
    swallows, because a missing file is a deploy-time bug we want
    loud."""
    cached = _validator_cache.get(topic)
    if cached is not None:
        return cached

    schema_path = _find_schema_root() / f"{topic}.json"
    if not schema_path.is_file():
        raise UnknownTopicError(
            f"No schema file at {schema_path}. Add a JSON schema for "
            f"topic '{topic}' under infrastructure/kafka/schemas/ — "
            f"see the README in that directory."
        )

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise RuntimeError(
            f"Failed to load schema {schema_path}: {e}"
        ) from e

    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as e:
        raise RuntimeError(
            f"Schema at {schema_path} is itself invalid: {e}"
        ) from e

    validator = Draft202012Validator(schema)
    _validator_cache[topic] = validator
    return validator


def _clear_cache_for_tests() -> None:
    """Test hook — pytest occasionally needs a fresh load (e.g., a
    test mutates a temp schema dir). Production code never calls this."""
    _validator_cache.clear()
    global _schema_root
    _schema_root = None


# ─── Public API ──────────────────────────────────────────────────

def validate_event(topic: str, payload: dict) -> None:
    """Validate ``payload`` against the schema for ``topic``. Raises
    ``InvalidEventError`` on the first violation (jsonschema
    ``Draft202012Validator.validate`` semantics) or
    ``UnknownTopicError`` if no schema file exists.

    Producers should let both exceptions propagate so the caller's
    transaction rolls back.

    Consumers should catch ``InvalidEventError`` and route to a
    DLQ — see ``raise_or_dlq`` below.
    """
    validator = _load_validator(topic)
    try:
        validator.validate(payload)
    except ValidationError as e:
        # ValidationError.message is the human-readable reason, e.g.
        # "'enterprise_id' is a required property". Combined with the
        # topic name + JSON pointer (e.path) it reads cleanly in logs.
        path = "/" + "/".join(str(p) for p in e.path) if e.path else "/"
        raise InvalidEventError(
            topic=topic,
            reason=f"{e.message} at {path}",
            payload=payload,
        ) from e


async def raise_or_dlq(
    topic: str,
    payload: dict,
    dlq_producer: Any,
    *,
    consumer_group: str,
    headers: Optional[list[tuple[str, bytes]]] = None,
    key: Optional[bytes] = None,
) -> bool:
    """Validate ``payload``; on failure, ship it to the DLQ topic and
    return ``False`` so the consumer can SKIP the business work but
    still commit the Kafka offset.

    Returns ``True`` when the payload is valid (consumer should
    continue) and ``False`` when it was DLQ'd.

    DLQ topic name follows the convention ``kaori.dlq.<topic>`` (per
    CLAUDE.md §7). The DLQ message includes the original payload + a
    header naming the consumer group that detected the violation, so
    the redrive tool can route a fix back to the same group.
    """
    try:
        validate_event(topic, payload)
        return True
    except (InvalidEventError, UnknownTopicError) as e:
        log.warning(
            "event.schema.invalid",
            topic=topic,
            consumer_group=consumer_group,
            reason=str(e),
        )
        dlq_topic = f"kaori.dlq.{topic}"
        dlq_headers = list(headers or [])
        dlq_headers.append(("schema_error", str(e).encode("utf-8")))
        dlq_headers.append(("consumer_group", consumer_group.encode("utf-8")))
        try:
            await dlq_producer.send_and_wait(
                dlq_topic,
                value=payload,
                key=key,
                headers=dlq_headers,
            )
        except Exception as send_exc:
            # If even the DLQ send fails we have no good option — log
            # the original validation failure + the DLQ failure so ops
            # can manually replay from offset position. We still
            # return False so the consumer commits the offset and
            # moves on, rather than spinning on the bad row.
            log.error(
                "event.schema.dlq_send_failed",
                topic=topic,
                dlq_topic=dlq_topic,
                original_reason=str(e),
                send_error=str(send_exc),
            )
        return False
