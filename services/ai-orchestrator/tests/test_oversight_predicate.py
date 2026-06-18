from ai_orchestrator.workflow_runtime.oversight import oversight_applies, IMPACTFUL_CLASSES


def test_impactful_classes():
    assert IMPACTFUL_CLASSES == ("write_non_idempotent", "external")


def test_high_risk_external_not_granted_requires_oversight():
    assert oversight_applies("external", "high", already_granted=False) is True


def test_high_risk_write_non_idempotent_requires_oversight():
    assert oversight_applies("write_non_idempotent", "high", already_granted=False) is True


def test_granted_does_not_require_again():
    assert oversight_applies("external", "high", already_granted=True) is False


def test_reversible_classes_never_require():
    for sec in ("pure", "read_only", "write_idempotent"):
        assert oversight_applies(sec, "high", already_granted=False) is False


def test_non_high_risk_never_requires():
    for tier in ("limited", "minimal", "prohibited", None):
        assert oversight_applies("external", tier, already_granted=False) is False
