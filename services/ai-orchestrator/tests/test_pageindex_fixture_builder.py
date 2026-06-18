"""Tests for FixturePageIndexTreeBuilder — P15-S11 Build Week prep.

The Fixture builder loads a pre-computed JSON tree (no LLM call at
runtime) so the Build Week demo path stays deterministic. Tests use
a small inline JSON fixture written to a tmp_path; no external service
involved.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from reasoning.rag.pageindex import (
    FixtureNotFoundError,
    FixturePageIndexTreeBuilder,
    PageIndexNode,
    PageIndexTree,
    node_to_dict,
)


@pytest.fixture
def fixture_dir(tmp_path: Path) -> Path:
    """Write a deterministic 2-level fixture to tmp dir and return path."""
    d = tmp_path / "trees"
    d.mkdir()
    sample_root = PageIndexNode(
        title="KPI Dashboard Design",
        summary="Chương 3 — thiết kế dashboard KPI cho retail SME.",
        page_start=42,
        page_end=78,
        children=(
            PageIndexNode(
                title="Color choice",
                summary="Quy tắc chọn màu sao cho phân biệt được KPI tốt/xấu.",
                page_start=42,
                page_end=55,
            ),
            PageIndexNode(
                title="Layout grid",
                summary="Bố cục 12-cột cho dashboard executive.",
                page_start=56,
                page_end=78,
            ),
        ),
    )
    payload = {
        "schema_version": 1,
        "doc_filename": "tableau_book.pdf",
        "source_backend": "test_fixture",
        "root": node_to_dict(sample_root),
    }
    sha = "a" * 64
    out_file = d / f"{sha}.json"
    with out_file.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    return d


def test_fixture_builder_loads_json_tree(fixture_dir: Path):
    builder = FixturePageIndexTreeBuilder(fixture_dir)
    sha = "a" * 64
    tree = asyncio.run(
        builder.build(
            tenant_id="tenant-demo",
            doc_sha256=sha,
            doc_text="ignored",
            doc_kind="pdf",
        )
    )
    assert isinstance(tree, PageIndexTree)
    assert tree.tenant_id == "tenant-demo"
    assert tree.doc_sha256 == sha
    assert tree.schema_version == 1
    assert tree.root.title == "KPI Dashboard Design"
    assert tree.root.page_start == 42
    assert tree.root.page_end == 78
    assert len(tree.root.children) == 2
    assert tree.root.children[0].title == "Color choice"
    assert tree.root.children[1].title == "Layout grid"


def test_fixture_builder_raises_when_missing(fixture_dir: Path):
    builder = FixturePageIndexTreeBuilder(fixture_dir)
    with pytest.raises(FixtureNotFoundError):
        asyncio.run(
            builder.build(
                tenant_id="tenant-demo",
                doc_sha256="b" * 64,  # not present
                doc_text="",
                doc_kind="pdf",
            )
        )


def test_fixture_builder_raises_when_dir_missing(tmp_path: Path):
    nonexistent = tmp_path / "does_not_exist"
    with pytest.raises(ValueError, match="fixture_dir does not exist"):
        FixturePageIndexTreeBuilder(nonexistent)


def test_node_to_dict_round_trip_preserves_shape(fixture_dir: Path):
    """node_to_dict must invert _node_from_dict — round-trip identity."""
    builder = FixturePageIndexTreeBuilder(fixture_dir)
    sha = "a" * 64
    tree = asyncio.run(
        builder.build(tenant_id="t", doc_sha256=sha, doc_text="", doc_kind="pdf")
    )
    rt = node_to_dict(tree.root)
    assert rt["title"] == tree.root.title
    assert rt["summary"] == tree.root.summary
    assert rt["page_start"] == tree.root.page_start
    assert rt["page_end"] == tree.root.page_end
    assert len(rt["children"]) == len(tree.root.children)
    assert rt["children"][0]["title"] == tree.root.children[0].title


def test_fixture_builder_handles_unicode_titles(tmp_path: Path):
    """Vietnamese diacritics + special chars in titles → preserved."""
    d = tmp_path / "trees"
    d.mkdir()
    sha = "c" * 64
    payload = {
        "schema_version": 1,
        "root": {
            "title": "Phân tích khách hàng — Phần 1",
            "summary": "Đánh giá hành vi khách hàng qua 6 tháng.",
            "page_start": 1,
            "page_end": 20,
            "children": [],
        },
    }
    with (d / f"{sha}.json").open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    builder = FixturePageIndexTreeBuilder(d)
    tree = asyncio.run(
        builder.build(tenant_id="t", doc_sha256=sha, doc_text="", doc_kind="pdf")
    )
    assert tree.root.title == "Phân tích khách hàng — Phần 1"
    assert "khách hàng" in tree.root.summary
