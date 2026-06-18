"""
Regression guards for Kafka topic naming (G2).

Mirrors the ai-orchestrator suite. We assert:
  - all topic constants use the documented `kaori.` namespace prefix;
  - pipeline.* literals never re-appear in producer / consumer code;
  - constants are unique (a typo'd duplicate would silently break
    fan-out semantics).
"""
import re
import subprocess
from pathlib import Path

import pytest

from data_pipeline.shared import kafka_topics


# ─── Constant-shape assertions ───────────────────────────────────────────────

ALL_CONSTANTS = {
    name: getattr(kafka_topics, name)
    for name in dir(kafka_topics)
    if name.isupper() and not name.startswith("_")
}


@pytest.mark.parametrize("name,value", list(ALL_CONSTANTS.items()))
def test_topic_constant_uses_kaori_prefix(name: str, value: str):
    """Every public constant in kafka_topics must start with `kaori.`."""
    assert isinstance(value, str), f"{name} is not a string"
    assert value.startswith("kaori."), (
        f"{name}={value!r} does not start with 'kaori.' — "
        "topics must be namespaced (CLAUDE.md §7)."
    )


def test_topic_constants_are_unique():
    """Two constants pointing at the same string would silently merge fan-outs."""
    values = list(ALL_CONSTANTS.values())
    assert len(values) == len(set(values)), (
        f"duplicate topic name in kafka_topics: {values}"
    )


def test_audit_topic_present():
    """K-6 audit stream must be defined (used by shared.audit downstream)."""
    assert hasattr(kafka_topics, "AUDIT_DECISIONS")
    assert kafka_topics.AUDIT_DECISIONS == "kaori.audit.decisions"


# ─── Source-grep regression: no legacy pipeline.X.Y literals ─────────────────

@pytest.fixture(scope="module")
def service_root() -> Path:
    """services/data-pipeline/"""
    # tests/ → services/data-pipeline/
    return Path(__file__).resolve().parent.parent


_LEGACY_PATTERN = re.compile(
    r'"pipeline\.(upload|bronze|silver|analysis)\.[a-z]+"'
)


def test_no_legacy_topic_literals_in_service_code(service_root: Path):
    """No bare pipeline.X.Y string literals may appear in producer / consumer
    code. Constants live exclusively in kafka_topics.py.

    Catches the same regressions as arch-guards G2 in the CI workflow but
    runs locally on every test invocation.
    """
    offenders: list[tuple[Path, int, str]] = []
    for py_file in service_root.rglob("*.py"):
        # Skip caches + the constants module itself + test files
        if "__pycache__" in py_file.parts:
            continue
        if py_file.name == "kafka_topics.py":
            continue
        if py_file.name == "test_kafka_topics.py":
            continue

        for lineno, line in enumerate(py_file.read_text(encoding="utf-8").splitlines(), 1):
            if _LEGACY_PATTERN.search(line):
                offenders.append((py_file.relative_to(service_root), lineno, line.strip()))

    assert not offenders, (
        "Legacy 'pipeline.X.Y' literals found — should reference "
        "kafka_topics constants instead:\n"
        + "\n".join(f"  {p}:{ln}  {src}" for p, ln, src in offenders)
    )
