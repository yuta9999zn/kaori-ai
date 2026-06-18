"""
F-061 — workflow registry + input validation.

Pure unit tests — no LLM, no DB. Verifies:
  * the static catalog has exactly the workflow we ship in v0
  * unknown workflow_id raises KeyError with a friendly message
  * input that satisfies the schema passes
  * input that violates the schema fails with a useful message
"""
from __future__ import annotations

import pytest

from ai_orchestrator.agents.orchestrator import (
    WorkflowInputError,
    _parse_actor,
    _validate_input,
)
from ai_orchestrator.agents.workflows import WORKFLOWS, get_workflow


def test_catalog_ships_expected_workflows():
    """The catalog is a deliberate, code-defined set — guards against accidental
    drift. insight-to-action (v0) + grounded-advisory (RAG×harness e2e)."""
    assert set(WORKFLOWS.keys()) == {"insight-to-action", "grounded-advisory"}
    assert WORKFLOWS["grounded-advisory"].requires_grounding is True


def test_get_workflow_unknown_id_raises_keyerror():
    with pytest.raises(KeyError) as exc:
        get_workflow("does-not-exist")
    msg = str(exc.value)
    assert "does-not-exist" in msg
    # Helpful message must list the known workflows so the caller can
    # show "Có sẵn: insight-to-action" in the 404 response.
    assert "insight-to-action" in msg


def test_input_validation_passes_with_uuid_insight_id():
    wf = get_workflow("insight-to-action")
    # Valid UUID v4 — should not raise.
    _validate_input(
        {"insight_id": "11111111-1111-1111-1111-111111111111"},
        wf,
    )


def test_input_validation_rejects_missing_insight_id():
    wf = get_workflow("insight-to-action")
    with pytest.raises(WorkflowInputError) as exc:
        _validate_input({}, wf)
    assert "insight_id" in str(exc.value)


def test_input_validation_rejects_extra_keys():
    """additionalProperties: false in the schema. Extra keys =
    rejection (covers a planner accidentally injecting tenant_id /
    enterprise_id at the workflow input layer)."""
    wf = get_workflow("insight-to-action")
    with pytest.raises(WorkflowInputError):
        _validate_input(
            {
                "insight_id": "11111111-1111-1111-1111-111111111111",
                "enterprise_id": "deadbeef-...",  # forbidden
            },
            wf,
        )


def test_input_validation_rejects_non_uuid_insight_id():
    wf = get_workflow("insight-to-action")
    with pytest.raises(WorkflowInputError):
        _validate_input({"insight_id": "not-a-uuid"}, wf)


def test_parse_actor_rejects_malformed_uuid():
    """A malformed X-User-ID forwarded as actor_user_id must surface as a
    clean WorkflowInputError (→ 400 RFC7807), not a raw ValueError that
    escapes the router and becomes a 500 SYSTEM.INTERNAL_ERROR."""
    with pytest.raises(WorkflowInputError):
        _parse_actor("not-a-uuid")


def test_parse_actor_accepts_none_and_valid_uuid():
    from uuid import UUID
    assert _parse_actor(None) is None
    valid = "11111111-1111-1111-1111-111111111111"
    assert _parse_actor(valid) == UUID(valid)


def test_workflow_allowed_tools_match_v0_set():
    """v0 'insight-to-action' allowlist:
    read tools (from chat layer): summarize_recent_decisions, get_top_at_risk_customers
    action tools (this PR): draft_followup_email, mark_customer_for_review
    """
    wf = get_workflow("insight-to-action")
    assert wf.allowed_tools == frozenset({
        "summarize_recent_decisions",
        "get_top_at_risk_customers",
        "draft_followup_email",
        "mark_customer_for_review",
    })
