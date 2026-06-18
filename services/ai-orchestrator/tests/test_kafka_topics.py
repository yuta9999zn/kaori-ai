"""
Regression guards for Kafka topic naming (G2) — ai-orchestrator side.

Same shape as services/data-pipeline/tests/test_kafka_topics.py.
"""
import re
from pathlib import Path

import pytest

from ai_orchestrator.shared import kafka_topics


# ─── Constant-shape assertions ───────────────────────────────────────────────

ALL_CONSTANTS = {
    name: getattr(kafka_topics, name)
    for name in dir(kafka_topics)
    if name.isupper() and not name.startswith("_")
}


@pytest.mark.parametrize("name,value", list(ALL_CONSTANTS.items()))
def test_topic_constant_uses_kaori_prefix(name: str, value: str):
    assert isinstance(value, str), f"{name} is not a string"
    assert value.startswith("kaori."), (
        f"{name}={value!r} does not start with 'kaori.'"
    )


def test_topic_constants_are_unique():
    values = list(ALL_CONSTANTS.values())
    assert len(values) == len(set(values))


def test_pipeline_topics_match_data_pipeline_side():
    """ai-orchestrator and data-pipeline maintain *separate* copies of
    kafka_topics; the actual string values must stay identical or
    producer/consumer pairs go out of sync.

    This test imports the data-pipeline copy too and asserts equality
    on the four pipeline.* topic constants.
    """
    import sys
    repo_root = Path(__file__).resolve().parents[3]
    services_root = repo_root / "services"
    if str(services_root) not in sys.path:
        sys.path.insert(0, str(services_root))

    # data-pipeline directory has a hyphen so we can't `import data-pipeline...`.
    # Locate the file and exec it in an empty namespace; we only need
    # the four PIPELINE_* string constants.
    dp_topics = services_root / "data-pipeline" / "shared" / "kafka_topics.py"
    if not dp_topics.exists():
        pytest.skip("data-pipeline/shared/kafka_topics.py not present")

    ns: dict = {}
    exec(dp_topics.read_text(encoding="utf-8"), ns)

    for name in ("PIPELINE_UPLOAD_RECEIVED",
                 "PIPELINE_BRONZE_COMPLETE",
                 "PIPELINE_SILVER_COMPLETE",
                 "PIPELINE_ANALYSIS_COMPLETE"):
        assert ns[name] == getattr(kafka_topics, name), (
            f"{name} value mismatch between data-pipeline and "
            f"ai-orchestrator kafka_topics.py — producer and "
            f"consumer would talk to different topics."
        )


# ─── Source-grep regression ──────────────────────────────────────────────────

@pytest.fixture(scope="module")
def service_root() -> Path:
    return Path(__file__).resolve().parent.parent


_LEGACY_PATTERN = re.compile(
    r'"pipeline\.(upload|bronze|silver|analysis)\.[a-z]+"'
)


def test_no_legacy_topic_literals_in_service_code(service_root: Path):
    offenders: list[tuple[Path, int, str]] = []
    for py_file in service_root.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        if py_file.name in {"kafka_topics.py", "test_kafka_topics.py"}:
            continue
        for lineno, line in enumerate(py_file.read_text(encoding="utf-8").splitlines(), 1):
            if _LEGACY_PATTERN.search(line):
                offenders.append((py_file.relative_to(service_root), lineno, line.strip()))

    assert not offenders, (
        "Legacy 'pipeline.X.Y' literals found:\n"
        + "\n".join(f"  {p}:{ln}  {src}" for p, ln, src in offenders)
    )
