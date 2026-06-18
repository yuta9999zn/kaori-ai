"""Tests for UpstreamPageIndexTreeBuilder — subprocess wrap of
VectifyAI/PageIndex's run_pageindex.py CLI.

subprocess is mocked via patching `asyncio.create_subprocess_exec` —
no real PageIndex install needed, no OpenAI calls. Validates:
  * Constructor fail-fast on missing repo / missing api key
  * pdf_path requirement in meta
  * Non-PDF doc_kind rejected
  * Subprocess timeout → RuntimeError
  * Non-zero exit → RuntimeError carrying stderr snippet
  * Malformed stdout → RuntimeError with first 200 chars
  * Happy path: upstream JSON → PageIndexNode tree
  * Field mapping (start_index → page_start; nodes → children)
  * Recursive node mapping with arbitrary depth
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from reasoning.rag.pageindex import (
    PageIndexNode,
    PageIndexTree,
    UpstreamPageIndexTreeBuilder,
    UpstreamPageIndexUnavailable,
)
from reasoning.rag.pageindex.tree_builder import (
    _extract_pageindex_json,
    _node_from_upstream,
)


# ─── Helpers ────────────────────────────────────────────────────────


def _fake_repo(tmp_path: Path) -> Path:
    """Create a fake PageIndex repo dir with a stub run_pageindex.py."""
    repo = tmp_path / "pageindex-repo"
    repo.mkdir()
    (repo / "run_pageindex.py").write_text("# stub runner — never executed in tests")
    return repo


def _fake_pdf(tmp_path: Path) -> Path:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%fake bytes")
    return pdf


def _make_proc_mock(*, returncode: int = 0, stdout: bytes = b"{}", stderr: bytes = b""):
    """Build a mock for asyncio.subprocess.Process."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    proc.kill = MagicMock()
    proc.wait = AsyncMock(return_value=None)
    return proc


def _upstream_payload() -> dict:
    """Sample upstream tree JSON matching the README schema."""
    return {
        "title": "Financial Stability Report",
        "node_id": "0001",
        "start_index": 1,
        "end_index": 80,
        "summary": "The Federal Reserve report on financial stability.",
        "nodes": [
            {
                "title": "Chapter 1 — Asset valuations",
                "node_id": "0002",
                "start_index": 1,
                "end_index": 25,
                "summary": "Asset valuation trends.",
                "nodes": [],
            },
            {
                "title": "Chapter 2 — Borrowing by businesses",
                "node_id": "0003",
                "start_index": 26,
                "end_index": 60,
                "summary": "Corporate borrowing levels.",
                "nodes": [
                    {
                        "title": "2.1 — Leveraged loans",
                        "node_id": "0004",
                        "start_index": 35,
                        "end_index": 45,
                        "summary": "Leveraged loan market trends.",
                        "nodes": [],
                    },
                ],
            },
        ],
    }


# ─── 1. Constructor fail-fast ───────────────────────────────────────


class TestConstructorFailFast:

    def test_missing_repo_raises(self, tmp_path):
        with pytest.raises(UpstreamPageIndexUnavailable, match="runner not found"):
            UpstreamPageIndexTreeBuilder(
                repo_path=tmp_path / "does-not-exist",
                openai_api_key="sk-test",
            )

    def test_missing_runner_in_repo_raises(self, tmp_path):
        empty_repo = tmp_path / "empty"
        empty_repo.mkdir()
        with pytest.raises(UpstreamPageIndexUnavailable, match="runner not found"):
            UpstreamPageIndexTreeBuilder(
                repo_path=empty_repo,
                openai_api_key="sk-test",
            )

    def test_empty_api_key_raises(self, tmp_path):
        repo = _fake_repo(tmp_path)
        with pytest.raises(UpstreamPageIndexUnavailable, match="openai_api_key is empty"):
            UpstreamPageIndexTreeBuilder(repo_path=repo, openai_api_key="")

    def test_happy_construction(self, tmp_path):
        repo = _fake_repo(tmp_path)
        b = UpstreamPageIndexTreeBuilder(
            repo_path=repo,
            openai_api_key="sk-test",
            timeout_seconds=120,
            model="gpt-4o",
        )
        assert b.timeout_seconds == 120
        assert b.model == "gpt-4o"
        assert b.python_executable == sys.executable


# ─── 2. build() validation ──────────────────────────────────────────


@pytest.mark.asyncio
class TestBuildValidation:

    async def test_non_pdf_doc_kind_rejected(self, tmp_path):
        repo = _fake_repo(tmp_path)
        b = UpstreamPageIndexTreeBuilder(repo_path=repo, openai_api_key="sk-test")
        with pytest.raises(ValueError, match="doc_kind='pdf'"):
            await b.build(
                tenant_id="t1", doc_sha256="x" * 64,
                doc_text="content", doc_kind="markdown",
            )

    async def test_missing_pdf_path_in_meta_rejected(self, tmp_path):
        repo = _fake_repo(tmp_path)
        b = UpstreamPageIndexTreeBuilder(repo_path=repo, openai_api_key="sk-test")
        with pytest.raises(ValueError, match="meta\\['pdf_path'\\]"):
            await b.build(
                tenant_id="t1", doc_sha256="x" * 64,
                doc_text="", doc_kind="pdf",
            )

    async def test_nonexistent_pdf_path_rejected(self, tmp_path):
        repo = _fake_repo(tmp_path)
        b = UpstreamPageIndexTreeBuilder(repo_path=repo, openai_api_key="sk-test")
        with pytest.raises(ValueError, match="is not a readable file"):
            await b.build(
                tenant_id="t1", doc_sha256="x" * 64,
                doc_text="", doc_kind="pdf",
                meta={"pdf_path": str(tmp_path / "no-such-file.pdf")},
            )


# ─── 3. Subprocess failure modes ────────────────────────────────────


@pytest.mark.asyncio
class TestSubprocessFailures:

    async def test_timeout_kills_subprocess_and_raises(self, tmp_path):
        repo = _fake_repo(tmp_path)
        pdf = _fake_pdf(tmp_path)
        b = UpstreamPageIndexTreeBuilder(
            repo_path=repo, openai_api_key="sk-test", timeout_seconds=1,
        )

        proc = _make_proc_mock()
        # Make communicate hang forever — wait_for triggers TimeoutError
        proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch("asyncio.create_subprocess_exec",
                    new=AsyncMock(return_value=proc)):
            with pytest.raises(RuntimeError, match="timed out after 1s"):
                await b.build(
                    tenant_id="t1", doc_sha256="x" * 64,
                    doc_text="", doc_kind="pdf",
                    meta={"pdf_path": str(pdf)},
                )
        proc.kill.assert_called_once()

    async def test_non_zero_exit_carries_stderr_snippet(self, tmp_path):
        repo = _fake_repo(tmp_path)
        pdf = _fake_pdf(tmp_path)
        b = UpstreamPageIndexTreeBuilder(repo_path=repo, openai_api_key="sk-test")
        proc = _make_proc_mock(
            returncode=1, stdout=b"", stderr=b"openai.AuthenticationError: invalid key"
        )
        with patch("asyncio.create_subprocess_exec",
                    new=AsyncMock(return_value=proc)):
            with pytest.raises(RuntimeError, match="exited 1.*AuthenticationError"):
                await b.build(
                    tenant_id="t1", doc_sha256="x" * 64,
                    doc_text="", doc_kind="pdf",
                    meta={"pdf_path": str(pdf)},
                )

    async def test_malformed_stdout_raises_with_snippet(self, tmp_path):
        repo = _fake_repo(tmp_path)
        pdf = _fake_pdf(tmp_path)
        b = UpstreamPageIndexTreeBuilder(repo_path=repo, openai_api_key="sk-test")
        proc = _make_proc_mock(returncode=0, stdout=b"no json here just prose")
        with patch("asyncio.create_subprocess_exec",
                    new=AsyncMock(return_value=proc)):
            with pytest.raises(RuntimeError, match="did not contain parseable JSON"):
                await b.build(
                    tenant_id="t1", doc_sha256="x" * 64,
                    doc_text="", doc_kind="pdf",
                    meta={"pdf_path": str(pdf)},
                )

    async def test_filenotfound_on_python_exec_raises_unavailable(self, tmp_path):
        repo = _fake_repo(tmp_path)
        pdf = _fake_pdf(tmp_path)
        b = UpstreamPageIndexTreeBuilder(repo_path=repo, openai_api_key="sk-test")
        with patch("asyncio.create_subprocess_exec",
                    new=AsyncMock(side_effect=FileNotFoundError("python3 not on PATH"))):
            with pytest.raises(UpstreamPageIndexUnavailable, match="Could not exec"):
                await b.build(
                    tenant_id="t1", doc_sha256="x" * 64,
                    doc_text="", doc_kind="pdf",
                    meta={"pdf_path": str(pdf)},
                )


# ─── 4. Happy path ──────────────────────────────────────────────────


@pytest.mark.asyncio
class TestHappyPath:

    async def test_upstream_json_maps_to_pageindex_tree(self, tmp_path):
        repo = _fake_repo(tmp_path)
        pdf = _fake_pdf(tmp_path)
        b = UpstreamPageIndexTreeBuilder(repo_path=repo, openai_api_key="sk-test")

        payload = _upstream_payload()
        proc = _make_proc_mock(
            returncode=0,
            stdout=(b"Building tree...\n"   # progress noise
                    + json.dumps(payload).encode("utf-8")
                    + b"\nTree saved to /tmp/x.json\n"),  # trailing noise
        )

        with patch("asyncio.create_subprocess_exec",
                    new=AsyncMock(return_value=proc)):
            tree = await b.build(
                tenant_id="tenant-abc", doc_sha256="d" * 64,
                doc_text="", doc_kind="pdf",
                meta={"pdf_path": str(pdf)},
            )

        assert isinstance(tree, PageIndexTree)
        assert tree.tenant_id == "tenant-abc"
        assert tree.doc_sha256 == "d" * 64
        # Root mapped
        assert tree.root.title == "Financial Stability Report"
        assert tree.root.page_start == 1
        assert tree.root.page_end == 80
        # 2 children mapped
        assert len(tree.root.children) == 2
        # Recursive: chapter 2 has 1 child of its own
        ch2 = tree.root.children[1]
        assert ch2.title.startswith("Chapter 2")
        assert ch2.page_start == 26
        assert len(ch2.children) == 1
        assert ch2.children[0].title.startswith("2.1")
        assert ch2.children[0].page_start == 35

    async def test_subprocess_env_carries_api_key_not_kaori_secrets(self, tmp_path):
        """OPENAI_API_KEY routes via subprocess env only; em never
        leak ai-orchestrator's other env vars to PageIndex."""
        repo = _fake_repo(tmp_path)
        pdf = _fake_pdf(tmp_path)
        b = UpstreamPageIndexTreeBuilder(
            repo_path=repo, openai_api_key="sk-test-secret",
        )

        proc = _make_proc_mock(returncode=0, stdout=b'{"title":"x","start_index":1,"end_index":2,"nodes":[]}')
        captured = {}

        async def fake_exec(*args, **kwargs):
            captured["env"] = kwargs.get("env")
            captured["cwd"] = kwargs.get("cwd")
            captured["args"] = args
            return proc

        with patch("asyncio.create_subprocess_exec", new=fake_exec):
            await b.build(
                tenant_id="t1", doc_sha256="d" * 64,
                doc_text="", doc_kind="pdf",
                meta={"pdf_path": str(pdf)},
            )

        env = captured["env"]
        assert env["OPENAI_API_KEY"] == "sk-test-secret"
        # PATH and PYTHONUNBUFFERED present; no other ai-orch secrets
        assert "PATH" in env
        assert env["PYTHONUNBUFFERED"] == "1"
        # cwd is the repo so run_pageindex.py resolves relative
        assert captured["cwd"] == str(repo)
        # CLI args include --pdf_path
        assert "--pdf_path" in captured["args"]


# ─── 5. JSON extraction + node mapping helpers ──────────────────────


class TestExtractPageindexJson:

    def test_clean_json(self):
        out = _extract_pageindex_json('{"title": "x"}')
        assert out == {"title": "x"}

    def test_json_with_progress_noise(self):
        text = ('Loading model...\n'
                'Building tree...\n'
                '{"title": "x", "nodes": []}\n'
                'Tree saved.\n')
        out = _extract_pageindex_json(text)
        assert out["title"] == "x"

    def test_no_braces_raises(self):
        with pytest.raises(ValueError, match="no '\\{...\\}'"):
            _extract_pageindex_json("no json at all")

    def test_only_open_brace_raises(self):
        with pytest.raises(ValueError):
            _extract_pageindex_json("{partial without close")

    def test_malformed_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _extract_pageindex_json("{not valid json}")


class TestNodeFromUpstream:

    def test_minimal_node(self):
        n = _node_from_upstream({"title": "t", "summary": "s"})
        assert n.title == "t"
        assert n.summary == "s"
        assert n.page_start is None
        assert n.page_end is None
        assert n.children == ()

    def test_start_index_maps_to_page_start(self):
        n = _node_from_upstream({"title": "t", "start_index": 5, "end_index": 10})
        assert n.page_start == 5
        assert n.page_end == 10

    def test_legacy_page_start_field_also_works(self):
        """If a fixture/upstream variant uses em's field name natively,
        em accept that too (forwards-compatibility)."""
        n = _node_from_upstream({"title": "t", "page_start": 7, "page_end": 8})
        assert n.page_start == 7
        assert n.page_end == 8

    def test_string_page_numbers_coerced_to_int(self):
        n = _node_from_upstream({"title": "t", "start_index": "5", "end_index": "10"})
        assert n.page_start == 5
        assert n.page_end == 10

    def test_unparseable_page_becomes_none(self):
        n = _node_from_upstream({"title": "t", "start_index": "Roman ii"})
        assert n.page_start is None

    def test_recursive_children(self):
        payload = {
            "title": "root",
            "nodes": [
                {"title": "a", "nodes": [
                    {"title": "a.1", "nodes": []},
                ]},
                {"title": "b"},
            ],
        }
        n = _node_from_upstream(payload)
        assert n.title == "root"
        assert len(n.children) == 2
        assert n.children[0].title == "a"
        assert n.children[0].children[0].title == "a.1"
        assert n.children[1].children == ()

    def test_missing_title_defaults_empty(self):
        n = _node_from_upstream({"start_index": 1})
        assert n.title == ""
