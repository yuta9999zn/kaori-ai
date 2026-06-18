"""
REL-002 (P1-S6) — Workflow YAML schema + validator.

Every workflow definition lives as YAML. This module:
  1. Holds the JSONSchema (Draft 2020-12) for the YAML.
  2. Exposes ``validate_workflow_yaml(doc)`` which runs the schema check
     PLUS the K-17 enforcement (every node MUST declare side_effect_class).
  3. Per-class extra requirements:
       * external → must declare 'compensation' (REL-012)
       * write_non_idempotent → must declare 'lock' policy (REL-006)
       * any class needing dedup → idempotency_key derivation is
         automatic via :func:`derive_idempotency_key`; no YAML field needed.

The validator is intentionally NOT tied to Temporal SDK — it runs at
ingest time (workflow upload, builder save) so a bad YAML never reaches
the worker. Temporal-specific checks (activity registration, queue
exists) happen in a second pass at deploy time (P1-S7+).

See:
  * docs/strategic/WORKFLOW_SYSTEM.md Phần 1 (Workflow Schema)
  * docs/adr/0014-at-least-once-plus-idempotency.md
"""
from __future__ import annotations

from typing import Any

from .side_effect import (
    SideEffectClass,
    needs_compensation,
    validate_side_effect_class,
)


class WorkflowSchemaError(ValueError):
    """Raised when a workflow YAML doc fails schema or K-17 checks.

    Carries the offending node_id (or top-level marker) so the caller
    can surface a useful error to the workflow author, not just a
    generic "validation failed".
    """

    def __init__(self, message: str, *, node_id: str | None = None):
        super().__init__(message)
        self.node_id = node_id


def workflow_yaml_schema() -> dict[str, Any]:
    """Return the JSONSchema (Draft 2020-12) for a workflow YAML doc.

    Single source of truth — also exported via
    :func:`get_workflow_yaml_schema_json` for the docs/api-specs feed.
    """
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Kaori Workflow YAML v1",
        "type": "object",
        "required": ["workflow_id", "name", "nodes"],
        "properties": {
            "workflow_id": {"type": "string", "minLength": 1, "maxLength": 100},
            "name": {"type": "string", "minLength": 1, "maxLength": 200},
            "description": {"type": "string", "maxLength": 2000},
            "version": {"type": "string", "maxLength": 32},
            "nodes": {
                "type": "array",
                "minItems": 1,
                "items": {"$ref": "#/$defs/node"},
            },
            "edges": {
                "type": "array",
                "items": {"$ref": "#/$defs/edge"},
            },
        },
        "$defs": {
            "node": {
                "type": "object",
                "required": ["node_id", "type", "side_effect_class"],
                "properties": {
                    "node_id": {"type": "string", "minLength": 1, "maxLength": 100},
                    "type": {"type": "string", "minLength": 1, "maxLength": 100},
                    "side_effect_class": {
                        "type": "string",
                        "enum": sorted(SideEffectClass.all_values()),
                        "description": "K-17: side-effect taxonomy. Drives retry + idempotency + compensation strategy.",
                    },
                    "retry": {
                        "type": "object",
                        "properties": {
                            "max_attempts": {"type": "integer", "minimum": 0, "maximum": 100},
                            "initial_backoff_ms": {"type": "integer", "minimum": 0},
                            "max_backoff_ms": {"type": "integer", "minimum": 0},
                            "multiplier": {"type": "number", "minimum": 1.0, "maximum": 10.0},
                        },
                        "additionalProperties": False,
                    },
                    "timeout_ms": {"type": "integer", "minimum": 1, "maximum": 86_400_000},
                    "compensation": {
                        "type": "object",
                        "description": "REL-012: required for external side effects (saga rollback).",
                        "properties": {
                            "node_id": {"type": "string"},
                            "reason_template": {"type": "string"},
                        },
                        "additionalProperties": True,
                    },
                    "lock": {
                        "type": "object",
                        "description": "REL-006: required for write_non_idempotent (distributed serialisation).",
                        "properties": {
                            "ttl_seconds": {"type": "integer", "minimum": 1},
                            "key_template": {"type": "string"},
                        },
                        "additionalProperties": True,
                    },
                    "input": {"type": "object", "additionalProperties": True},
                },
                "additionalProperties": True,
            },
            "edge": {
                "type": "object",
                "required": ["from", "to"],
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "condition": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        "additionalProperties": True,
    }


def validate_workflow_yaml(doc: dict[str, Any]) -> None:
    """Validate a workflow YAML doc against the schema + K-17 rules.

    Raises :class:`WorkflowSchemaError` on the first violation. Aborting
    early is the right call: a malformed workflow never reaches a worker
    so partial validation = silent acceptance.

    Two layers:
      1. JSONSchema validation (delegated to jsonschema lib).
      2. K-17 + REL-012/006 cross-field checks that JSONSchema can't
         express cleanly (per-class required fields).

    Why not pure JSONSchema: oneOf/if-then on nested objects is hard to
    write, harder to read, and produces opaque error messages. A 30-line
    Python guard is clearer than a 200-line schema branch.
    """
    # Lazy import — jsonschema is heavy and many call sites only need
    # the schema dict (export, doc generation). Importing here keeps
    # the module-level cost zero for those cases.
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover — dep is in requirements.txt
        raise WorkflowSchemaError(
            "jsonschema package not installed; cannot validate workflow YAML."
        ) from exc

    try:
        jsonschema.validate(doc, workflow_yaml_schema())
    except jsonschema.ValidationError as exc:
        # Build a node_id hint when the failing path includes it.
        node_id = None
        if exc.path and exc.path[0] == "nodes" and len(exc.path) >= 2:
            try:
                node_idx = int(exc.path[1])
                node_id = doc.get("nodes", [{}])[node_idx].get("node_id")
            except (ValueError, IndexError, TypeError):
                node_id = None
        raise WorkflowSchemaError(
            f"YAML schema validation failed: {exc.message}",
            node_id=node_id,
        ) from exc

    # K-17 + per-class checks. JSONSchema enforced presence + enum,
    # this loop adds the class-aware required fields.
    for node in doc.get("nodes", []):
        node_id = node.get("node_id")
        try:
            klass = validate_side_effect_class(node.get("side_effect_class"))
        except ValueError as exc:
            raise WorkflowSchemaError(str(exc), node_id=node_id) from exc

        if needs_compensation(klass) and not node.get("compensation"):
            raise WorkflowSchemaError(
                f"REL-012: node {node_id!r} has side_effect_class={klass.value!r}; "
                "must declare 'compensation' for saga rollback.",
                node_id=node_id,
            )

        if klass == SideEffectClass.WRITE_NON_IDEMPOTENT and not node.get("lock"):
            raise WorkflowSchemaError(
                f"REL-006: node {node_id!r} has side_effect_class='write_non_idempotent'; "
                "must declare 'lock' for distributed serialisation.",
                node_id=node_id,
            )
