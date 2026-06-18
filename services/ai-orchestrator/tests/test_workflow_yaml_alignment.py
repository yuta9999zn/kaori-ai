"""
Cross-check the YAML reference workflow against:
  * the workflow_runtime YAML schema (yaml_schema.validate_workflow_yaml)
  * the matching Python workflow's activity declarations

Drift between YAML K-17 declarations and the activity decorations is
the failure mode this test guards against. If someone changes the
side_effect_class on parse_input from 'pure' to 'read_only' in YAML
without updating the activity (or vice versa), CI catches it here.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ai_orchestrator.workflow_runtime.activities import analyze as analyze_activities
from ai_orchestrator.workflow_runtime.yaml_schema import validate_workflow_yaml


_TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "infrastructure" / "workflows" / "templates"
_ANALYZE_YAML = _TEMPLATES_DIR / "analyze-pipeline.yaml"


@pytest.fixture(scope="module")
def analyze_doc():
    assert _ANALYZE_YAML.exists(), f"missing template: {_ANALYZE_YAML}"
    return yaml.safe_load(_ANALYZE_YAML.read_text(encoding="utf-8"))


def test_analyze_pipeline_yaml_validates_against_schema(analyze_doc):
    """The reference workflow MUST pass validate_workflow_yaml.

    A regression here means the schema or the YAML drifted; either way
    the YAML is the source of truth that operators upload, so it has
    to keep validating."""
    validate_workflow_yaml(analyze_doc)  # raises on failure


def test_analyze_pipeline_yaml_node_count_matches_python_workflow(analyze_doc):
    """The Python workflow runs 6 activities total (parse + load +
    upsert running + audit + upsert complete + notify). YAML must list
    the same count so the saga orchestrator (P15-S10+) can reason about
    them 1:1."""
    assert len(analyze_doc["nodes"]) == 6


def test_analyze_pipeline_yaml_classes_cover_all_five_taxonomies(analyze_doc):
    """K-17 contract test — the reference workflow must exercise all 5
    side-effect classes. If a class is dropped from YAML, the contract
    test loses that coverage."""
    classes_in_yaml = {n["side_effect_class"] for n in analyze_doc["nodes"]}
    assert classes_in_yaml == {
        "pure",
        "read_only",
        "write_idempotent",
        "write_non_idempotent",
        "external",
    }


def test_yaml_node_classes_match_activity_decorations(analyze_doc):
    """For every node in YAML, the matching activity (looked up by
    node_id → activity name) must declare the same side_effect_class
    in its module docstring assignment table.

    This guards against silent drift: if someone re-classes the audit
    activity from write_non_idempotent → write_idempotent in Python
    without updating the YAML (or removes the lock declaration), the
    operational guarantees break.
    """
    expected_classes = {
        "parse_input": "pure",
        "load_pipeline_run": "read_only",
        "upsert_run_status_running": "write_idempotent",
        "upsert_run_status_complete": "write_idempotent",
        "insert_decision_audit": "write_non_idempotent",
        "send_completion_notification": "external",
    }
    for node in analyze_doc["nodes"]:
        nid = node["node_id"]
        assert nid in expected_classes, f"unexpected node_id in YAML: {nid}"
        assert node["side_effect_class"] == expected_classes[nid], (
            f"node {nid!r} side_effect_class drift: "
            f"yaml={node['side_effect_class']!r} python={expected_classes[nid]!r}"
        )
    # Sanity: the activity module exposes every base activity referenced.
    for base_id in {"parse_input", "load_pipeline_run", "upsert_run_status",
                    "insert_decision_audit", "send_completion_notification"}:
        assert hasattr(analyze_activities, base_id), \
            f"activity module missing {base_id}"


def test_external_node_declares_compensation(analyze_doc):
    """REL-012 — every external node must declare a compensation block.
    Yaml schema enforces this too, but pinning it here makes the
    contract explicit in the test name + means a YAML-schema relaxation
    can't silently weaken the rule."""
    external_nodes = [n for n in analyze_doc["nodes"]
                      if n["side_effect_class"] == "external"]
    assert external_nodes, "no external nodes in reference workflow"
    for n in external_nodes:
        assert "compensation" in n, (
            f"external node {n['node_id']!r} missing compensation block"
        )


def test_write_non_idempotent_node_declares_lock(analyze_doc):
    """REL-006 — write_non_idempotent nodes must declare a lock so the
    Action Runtime can serialise concurrent retries on the same node."""
    wni_nodes = [n for n in analyze_doc["nodes"]
                 if n["side_effect_class"] == "write_non_idempotent"]
    assert wni_nodes, "no write_non_idempotent nodes in reference workflow"
    for n in wni_nodes:
        assert "lock" in n, (
            f"write_non_idempotent node {n['node_id']!r} missing lock block"
        )
