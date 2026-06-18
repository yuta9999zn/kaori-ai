"""
Regression guard for the `shared`-package dual-identity bug (PR #247).

`PYTHONPATH=/app:/app/ai_orchestrator` makes the same file `shared/x.py`
importable under two module names — `shared.x` (top-level) and
`ai_orchestrator.shared.x` — which Python treats as two distinct modules.
Module-level state (connection pools, classes used in `isinstance` /
`except`) then duplicates → the crash documented in PR #247 and exercised by
the chaos tests.

The fix (2026-05-24) converged the whole codebase on the single canonical
identity `ai_orchestrator.shared.*` (matching the 64 relative `from ..shared`
app imports). This test fails the moment a top-level `from shared.` /
`import shared.` is reintroduced anywhere in the service, so the dual identity
can't creep back. Use `from ..shared.x` (relative) or
`from ai_orchestrator.shared.x` (absolute) instead.

See docs/specs/IMPORT_PATH_UNIFICATION.md. The same latent pattern still
exists for `reasoning` / `workflow_runtime` / `org_intel` (tracked there as a
follow-up); this guard covers `shared`, the one with a proven crash.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_SERVICE_ROOT = Path(__file__).resolve().parent.parent
# Matches a top-level `from shared.` / `from shared ` / `import shared.` /
# `import shared ` at the start of a (possibly indented) line. Relative
# imports (`from ..shared`, `from .shared`) and the canonical
# `ai_orchestrator.shared` are NOT matched.
_TOPLEVEL_SHARED = re.compile(r"^[ \t]*(from|import)[ \t]+shared([. \t]|$)")


def _python_files():
    for p in _SERVICE_ROOT.rglob("*.py"):
        if "__pycache__" in p.parts or ".venv" in p.parts:
            continue
        if p.name == Path(__file__).name:  # don't scan this guard's own docstring
            continue
        yield p


def test_no_toplevel_shared_imports():
    offenders: list[str] = []
    for path in _python_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _TOPLEVEL_SHARED.match(line):
                rel = path.relative_to(_SERVICE_ROOT)
                offenders.append(f"{rel}:{lineno}: {line.strip()}")

    assert not offenders, (
        "Top-level `shared` imports reintroduce the PR #247 dual-identity bug. "
        "Use `from ..shared.x` or `from ai_orchestrator.shared.x` instead:\n  "
        + "\n  ".join(offenders)
    )
