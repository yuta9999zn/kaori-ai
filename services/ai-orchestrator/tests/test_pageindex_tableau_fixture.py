"""Smoke test for the Tableau book fixture — P15-S11 Build Week.

Verifies that the committed local-toc fixture for the
"Data Visualization and Storytelling With Tableau" book loads via
FixturePageIndexTreeBuilder and produces a sane tree. Skipped if the
fixture file is absent (e.g. clean checkout that hasn't run the
offline build script).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from reasoning.rag.pageindex import (
    FixturePageIndexTreeBuilder,
    PageIndexTree,
)

# Committed by Build Week prep. SHA-256 of the source PDF.
_TABLEAU_BOOK_SHA = "0572777beef3ea9a93de3b5ffea5759890263d92693b24e08bf62fc386cb9167"
_FIXTURE_DIR = (
    Path(__file__).resolve().parent / "fixtures" / "pageindex_trees"
)
_FIXTURE_FILE = _FIXTURE_DIR / f"{_TABLEAU_BOOK_SHA}.json"


@pytest.mark.skipif(
    not _FIXTURE_FILE.exists(),
    reason="Tableau book fixture not present — run scripts/pageindex_offline_build.py",
)
def test_tableau_book_fixture_loads_with_real_chapters():
    builder = FixturePageIndexTreeBuilder(_FIXTURE_DIR)
    tree = asyncio.run(
        builder.build(
            tenant_id="11111111-1111-1111-1111-111111111111",
            doc_sha256=_TABLEAU_BOOK_SHA,
            doc_text="",
            doc_kind="pdf",
        )
    )
    assert isinstance(tree, PageIndexTree)
    # Root is the PDF filename.
    assert "Tableau" in tree.root.title or "tableau" in tree.root.title.lower()
    # Real published book → expect ≥ 5 top-level outline entries.
    assert len(tree.root.children) >= 5
    # Page range spans the document.
    assert tree.root.page_start == 1
    assert tree.root.page_end > 100  # 477 expected, but loose bound
    # No [STUB] marker in any title — this is real data.
    for child in tree.root.children:
        assert "[STUB]" not in child.title
