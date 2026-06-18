"""
Tests for workflow_runtime — P1-S6 (REL-001/002/004/005, K-17).

Three layers:

  test_side_effect.py — taxonomy enum + per-class capability helpers
  test_idempotency.py — derive_idempotency_key determinism + canonicalisation
  test_yaml_schema.py — schema + K-17 + per-class required field checks

Bundled in one file for now (Phase 1 scope is small); split when each
section grows past ~10 tests.
"""
from __future__ import annotations

from uuid import UUID

import pytest

from ai_orchestrator.workflow_runtime import (
    SideEffectClass,
    derive_idempotency_key,
    validate_side_effect_class,
)
from ai_orchestrator.workflow_runtime.side_effect import (
    needs_compensation,
    needs_distributed_lock,
    needs_idempotency_dedup,
)
from ai_orchestrator.workflow_runtime.yaml_schema import (
    WorkflowSchemaError,
    validate_workflow_yaml,
    workflow_yaml_schema,
)


# ─── REL-001 — SideEffectClass taxonomy ─────────────────────────────


def test_side_effect_class_enum_has_exactly_5_classes():
    """K-17 explicit count — adding a 6th class is a contract change.
    Test fails loud so a careless PR can't sneak in a new class without
    updating the YAML schema enum + audit migration CHECK."""
    assert len(SideEffectClass) == 5
    assert SideEffectClass.all_values() == {
        "pure", "read_only", "write_idempotent", "write_non_idempotent", "external",
    }


def test_validate_side_effect_class_accepts_canonical_strings():
    assert validate_side_effect_class("pure") == SideEffectClass.PURE
    assert validate_side_effect_class("write_idempotent") == SideEffectClass.WRITE_IDEMPOTENT
    assert validate_side_effect_class("external") == SideEffectClass.EXTERNAL


def test_validate_side_effect_class_strips_whitespace():
    """YAML loaders sometimes leave trailing whitespace on string scalars
    — accept anyway, the intent is clear."""
    assert validate_side_effect_class("  pure  ") == SideEffectClass.PURE


def test_validate_side_effect_class_rejects_missing_with_k17_message():
    """Empty/None should raise with K-17 mention so the error message
    points readers at the right invariant in CLAUDE.md."""
    for bad in (None, "", "   "):
        with pytest.raises(ValueError, match="K-17"):
            validate_side_effect_class(bad)


def test_validate_side_effect_class_rejects_unknown_value():
    with pytest.raises(ValueError, match="not in taxonomy"):
        validate_side_effect_class("write_maybe_safe")


# ─── REL-003/006/012 — per-class capability helpers ─────────────────


def test_needs_idempotency_dedup_only_for_write_classes():
    """pure + read_only retry freely. write_idempotent uses natural-key
    dedup. write_non_idempotent + external need explicit dedup."""
    assert not needs_idempotency_dedup(SideEffectClass.PURE)
    assert not needs_idempotency_dedup(SideEffectClass.READ_ONLY)
    assert not needs_idempotency_dedup(SideEffectClass.WRITE_IDEMPOTENT)
    assert needs_idempotency_dedup(SideEffectClass.WRITE_NON_IDEMPOTENT)
    assert needs_idempotency_dedup(SideEffectClass.EXTERNAL)


def test_needs_distributed_lock_only_for_write_non_idempotent():
    """external uses provider-side dedup key (REL-007), not Redis lock."""
    for klass in SideEffectClass:
        if klass == SideEffectClass.WRITE_NON_IDEMPOTENT:
            assert needs_distributed_lock(klass)
        else:
            assert not needs_distributed_lock(klass)


def test_needs_compensation_only_for_external():
    """Saga compensation is only needed when the side effect can't be
    undone in-process — that's the external case."""
    for klass in SideEffectClass:
        if klass == SideEffectClass.EXTERNAL:
            assert needs_compensation(klass)
        else:
            assert not needs_compensation(klass)


# ─── REL-004 — derive_idempotency_key ────────────────────────────────


RUN_ID = UUID("11111111-1111-1111-1111-111111111111")


def test_derive_idempotency_key_is_deterministic():
    a = derive_idempotency_key(
        workflow_id="churn-detect", node_id="send-zalo", run_id=RUN_ID,
        input_data={"customer_id": "c-7", "msg": "hi"},
    )
    b = derive_idempotency_key(
        workflow_id="churn-detect", node_id="send-zalo", run_id=RUN_ID,
        input_data={"customer_id": "c-7", "msg": "hi"},
    )
    assert a == b
    assert len(a) == 64  # sha256 hex


def test_derive_idempotency_key_input_order_does_not_matter():
    """Sort-keys JSON ensures dict order doesn't change the hash."""
    a = derive_idempotency_key(
        workflow_id="wf", node_id="n1", run_id=RUN_ID,
        input_data={"a": 1, "b": 2, "c": 3},
    )
    b = derive_idempotency_key(
        workflow_id="wf", node_id="n1", run_id=RUN_ID,
        input_data={"c": 3, "b": 2, "a": 1},
    )
    assert a == b


def test_derive_idempotency_key_changes_when_input_changes():
    a = derive_idempotency_key(
        workflow_id="wf", node_id="n1", run_id=RUN_ID,
        input_data={"x": 1},
    )
    b = derive_idempotency_key(
        workflow_id="wf", node_id="n1", run_id=RUN_ID,
        input_data={"x": 2},
    )
    assert a != b


def test_derive_idempotency_key_changes_per_run():
    """Two runs of the same workflow on the same input get different
    keys — that's how a re-run actually re-fires the side effect."""
    other_run = UUID("22222222-2222-2222-2222-222222222222")
    a = derive_idempotency_key(
        workflow_id="wf", node_id="n1", run_id=RUN_ID,
        input_data={"x": 1},
    )
    b = derive_idempotency_key(
        workflow_id="wf", node_id="n1", run_id=other_run,
        input_data={"x": 1},
    )
    assert a != b


def test_derive_idempotency_key_accepts_string_run_id():
    """Caller may have run_id as string from an HTTP header."""
    a = derive_idempotency_key(
        workflow_id="wf", node_id="n1",
        run_id="11111111-1111-1111-1111-111111111111",
        input_data={"x": 1},
    )
    b = derive_idempotency_key(
        workflow_id="wf", node_id="n1", run_id=RUN_ID,
        input_data={"x": 1},
    )
    assert a == b


def test_derive_idempotency_key_empty_input_is_stable():
    """Some nodes have no per-call input — empty/None should produce
    the same baseline key."""
    a = derive_idempotency_key(workflow_id="wf", node_id="n1", run_id=RUN_ID)
    b = derive_idempotency_key(
        workflow_id="wf", node_id="n1", run_id=RUN_ID, input_data={},
    )
    c = derive_idempotency_key(
        workflow_id="wf", node_id="n1", run_id=RUN_ID, input_data=None,
    )
    assert a == b == c


# ─── REL-002 — workflow YAML schema validation ──────────────────────


def _minimal_workflow():
    return {
        "workflow_id": "wf-1",
        "name": "Test workflow",
        "nodes": [
            {
                "node_id": "n1",
                "type": "compute",
                "side_effect_class": "pure",
            },
        ],
    }


def test_minimal_workflow_passes_validation():
    validate_workflow_yaml(_minimal_workflow())  # no raise


def test_workflow_with_all_5_classes_passes():
    """Each side_effect_class with the right per-class fields validates
    cleanly. Smoke that the schema accepts every taxonomy member."""
    doc = {
        "workflow_id": "wf-all",
        "name": "All classes",
        "nodes": [
            {"node_id": "n_pure", "type": "compute", "side_effect_class": "pure"},
            {"node_id": "n_ro",   "type": "select",  "side_effect_class": "read_only"},
            {"node_id": "n_wi",   "type": "upsert",  "side_effect_class": "write_idempotent"},
            {
                "node_id": "n_wni", "type": "insert",
                "side_effect_class": "write_non_idempotent",
                "lock": {"ttl_seconds": 30, "key_template": "wf-all/n_wni/{customer_id}"},
            },
            {
                "node_id": "n_ext", "type": "send_email",
                "side_effect_class": "external",
                "compensation": {
                    "node_id": "n_ext_compensate",
                    "reason_template": "Original send failed downstream",
                },
            },
        ],
    }
    validate_workflow_yaml(doc)  # no raise


def test_workflow_missing_side_effect_class_raises_k17():
    doc = _minimal_workflow()
    del doc["nodes"][0]["side_effect_class"]
    with pytest.raises(WorkflowSchemaError) as exc:
        validate_workflow_yaml(doc)
    # JSONSchema fires first since the field is in the required[] list.
    assert "side_effect_class" in str(exc.value)


def test_workflow_invalid_side_effect_class_value_rejected():
    doc = _minimal_workflow()
    doc["nodes"][0]["side_effect_class"] = "write_maybe"
    with pytest.raises(WorkflowSchemaError):
        validate_workflow_yaml(doc)


def test_external_node_without_compensation_raises_rel012():
    doc = _minimal_workflow()
    doc["nodes"][0]["side_effect_class"] = "external"
    doc["nodes"][0]["type"] = "send_email"
    with pytest.raises(WorkflowSchemaError, match="REL-012"):
        validate_workflow_yaml(doc)


def test_write_non_idempotent_without_lock_raises_rel006():
    doc = _minimal_workflow()
    doc["nodes"][0]["side_effect_class"] = "write_non_idempotent"
    doc["nodes"][0]["type"] = "insert_order"
    with pytest.raises(WorkflowSchemaError, match="REL-006"):
        validate_workflow_yaml(doc)


def test_write_non_idempotent_with_lock_passes():
    doc = _minimal_workflow()
    doc["nodes"][0]["side_effect_class"] = "write_non_idempotent"
    doc["nodes"][0]["type"] = "insert_order"
    doc["nodes"][0]["lock"] = {"ttl_seconds": 30}
    validate_workflow_yaml(doc)  # no raise


def test_workflow_with_no_nodes_raises():
    doc = _minimal_workflow()
    doc["nodes"] = []
    with pytest.raises(WorkflowSchemaError):
        validate_workflow_yaml(doc)


def test_workflow_yaml_schema_includes_all_taxonomy_values():
    """The exported schema's enum MUST stay in sync with SideEffectClass.
    A divergence would make the YAML accept a value the runtime rejects
    (or vice versa)."""
    schema = workflow_yaml_schema()
    enum_values = set(schema["$defs"]["node"]["properties"]["side_effect_class"]["enum"])
    assert enum_values == SideEffectClass.all_values()


def test_workflow_yaml_schema_error_carries_node_id_hint():
    """When the validation failure points at a specific node, the
    WorkflowSchemaError carries node_id so the caller can highlight
    the right line in the workflow builder UI."""
    doc = _minimal_workflow()
    doc["nodes"].append({
        "node_id": "n_bad",
        "type": "send_email",
        "side_effect_class": "external",
        # missing compensation
    })
    with pytest.raises(WorkflowSchemaError) as exc:
        validate_workflow_yaml(doc)
    assert exc.value.node_id == "n_bad"
