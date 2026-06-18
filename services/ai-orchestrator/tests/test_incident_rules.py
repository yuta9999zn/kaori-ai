import pytest
from ai_orchestrator.reasoning import incident_rules as ir


def test_severities_tuple():
    assert ir.SEVERITIES == ("low", "medium", "high", "serious")


def test_statuses_tuple():
    assert ir.INCIDENT_STATUSES == ("open", "investigating", "resolved")


def test_validate_severity_normalises():
    assert ir.validate_severity(" SERIOUS ") == "serious"
    with pytest.raises(ValueError):
        ir.validate_severity("catastrophic")


def test_validate_status_normalises():
    assert ir.validate_status(" Resolved ") == "resolved"
    with pytest.raises(ValueError):
        ir.validate_status("closed")
