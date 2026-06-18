"""
PageIndex tree builder — RAG-PAGEINDEX-001 contract surface.

Phase 1.5 P15-S10 D7. The real implementation wraps the upstream
PageIndex package (PyPI `pageindex` 0.2.8, MIT licensed) which calls
an LLM to traverse the source document and emit a hierarchical
Table-of-Contents tree. This module ships:

  * Tree + Node dataclasses — the wire shape that the retriever
    (D8 RAG-PAGEINDEX-002) and the persistence layer
    (migration 045 pageindex_trees) consume.
  * Abstract `PageIndexTreeBuilder` base — extracts the contract so
    StubPageIndexTreeBuilder (this file) and the future
    UpstreamPageIndexTreeBuilder share an interface for the router.
  * `StubPageIndexTreeBuilder` — deterministic synthetic tree so
    end-to-end tests of the RAG router (D6) and downstream consumers
    don't need an LLM call until the upstream wrap lands.

Build is async because the upstream wrap will be I/O-bound (LLM
HTTPS round-trips); the stub matches that signature so swap-in is
zero-friction.

Side-effect class (per K-17 declaration once wired into Temporal
in D7 follow-up): `external` — LLM calls during build. Idempotency
key derived per `sha256(tenant_id || doc_sha256)`; same input
deterministic same tree (per upstream contract).
"""
from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Wire shapes — frozen so the tree is hashable + persistable as JSONB
# without surprises (a mutating consumer would silently invalidate the
# cache key).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PageIndexNode:
    """One node in the PageIndex hierarchical tree.

    Fields mirror the upstream PageIndex schema (per
    https://github.com/VectifyAI/PageIndex):

      title         — section/chapter title as discovered by the LLM
      summary       — 1-3 sentence node summary (what's in this branch)
      page_start    — 1-indexed first page of this node's content
      page_end      — 1-indexed last page (inclusive)
      children      — child nodes; empty tuple at leaves
      doc_offset_start  — character offset into source text (markdown only;
                          PDFs report page numbers and leave offsets None)
      doc_offset_end    — same
    """

    title: str
    summary: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    children: tuple["PageIndexNode", ...] = field(default_factory=tuple)
    doc_offset_start: Optional[int] = None
    doc_offset_end: Optional[int] = None

    def page_range(self) -> str:
        """Human-friendly page range string for citations."""
        if self.page_start is None and self.page_end is None:
            return ""
        if self.page_start == self.page_end:
            return f"p.{self.page_start}"
        return f"p.{self.page_start}-{self.page_end}"


@dataclass(frozen=True)
class PageIndexTree:
    """Top-level tree wrapper. Carries tenant + doc identity for
    persistence + cache-key derivation."""

    tenant_id: str
    doc_sha256: str          # SHA-256 of the source document bytes
    schema_version: int      # bump when PageIndexNode shape changes
    root: PageIndexNode

    def cache_key(self) -> str:
        """Idempotency key per K-17 + REL-005 spirit. Same source
        document for same tenant deterministically yields the same key
        so a retry of the build workflow lands on the same row."""
        raw = f"{self.tenant_id}|{self.doc_sha256}|{self.schema_version}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------------------
# Builder contract
# ---------------------------------------------------------------------------


class PageIndexTreeBuilder(ABC):
    """Async tree builder. Implementations:

      StubPageIndexTreeBuilder    — deterministic synthetic tree (this file)
      UpstreamPageIndexTreeBuilder — wraps PyPI pageindex==0.2.8 (P15-S10
                                     D7 follow-up; needs LLM creds + sample
                                     corpus + migration 045)
    """

    schema_version: int = 1

    @abstractmethod
    async def build(
        self,
        *,
        tenant_id: str,
        doc_sha256: str,
        doc_text: str,
        doc_kind: str,                     # 'pdf' | 'markdown'
        meta: Optional[dict[str, Any]] = None,
    ) -> PageIndexTree:
        """Build the hierarchical TOC tree for a single document.

        Implementations MUST be deterministic for a given (tenant_id,
        doc_sha256, doc_text, schema_version) tuple so the cache key
        stays valid under retry.
        """
        ...


# ---------------------------------------------------------------------------
# Stub implementation — used by RAG router unit tests until the upstream
# wrap lands. Zero LLM calls; pure function.
# ---------------------------------------------------------------------------


class StubPageIndexTreeBuilder(PageIndexTreeBuilder):
    """Deterministic synthetic 2-level tree.

    Returns a fixed shape (1 root + 2 children) so consumers can verify
    they handle the tree contract without paying for LLM calls. The
    summary fields explicitly say [STUB] so an operator who sees this
    in a real RAG response knows the upstream wrap hasn't been wired
    for the calling tenant yet.

    Doc text is hashed into the cache key path verifies determinism;
    the shape itself is the same across docs.
    """

    schema_version = 1

    async def build(
        self,
        *,
        tenant_id: str,
        doc_sha256: str,
        doc_text: str,
        doc_kind: str,
        meta: Optional[dict[str, Any]] = None,
    ) -> PageIndexTree:
        # Two-child synthetic tree. Page numbers chosen to look plausible
        # but obviously fake: 1-50 + 51-100. An operator checking why a
        # citation says "p.1-50" sees the synthetic shape immediately.
        root = PageIndexNode(
            title=f"[STUB] Document root ({doc_kind})",
            summary=f"[STUB] Synthetic PageIndex root — wraps {len(doc_text)} chars of source.",
            page_start=1,
            page_end=100,
            children=(
                PageIndexNode(
                    title="[STUB] First half",
                    summary="[STUB] First half of the document (synthetic).",
                    page_start=1,
                    page_end=50,
                ),
                PageIndexNode(
                    title="[STUB] Second half",
                    summary="[STUB] Second half of the document (synthetic).",
                    page_start=51,
                    page_end=100,
                ),
            ),
        )
        return PageIndexTree(
            tenant_id=tenant_id,
            doc_sha256=doc_sha256,
            schema_version=self.schema_version,
            root=root,
        )


# ---------------------------------------------------------------------------
# Fixture implementation — load pre-computed tree from JSON. Production-
# presentable for Build Week demo without runtime LLM dependency.
# ---------------------------------------------------------------------------


class FixturePageIndexTreeBuilder(PageIndexTreeBuilder):
    """Load PageIndex tree from a pre-computed JSON file.

    Workflow:
      1. Operator runs `scripts/pageindex_offline_build.py` once with
         an OpenAI key + source PDF to produce a JSON fixture.
      2. This builder reads that JSON at runtime — zero LLM cost, no
         external service dependency on the demo path.
      3. Same source PDF → same fixture file → deterministic.

    Used for Build Week demo with `Data Visualization and Storytelling
    With Tableau` book corpus. Post-Build-Week, swap to
    UpstreamPageIndexTreeBuilder (vendored OSS fork) for fully live
    builds per K-4/K-5.

    Args:
      fixture_dir: directory containing `{doc_sha256}.json` files.
                   When `build()` is called, the builder looks up
                   `{fixture_dir}/{doc_sha256}.json` and parses it.

    Raises FixtureNotFoundError if the doc has no fixture — operator
    must pre-build before demo.
    """

    schema_version = 1

    def __init__(self, fixture_dir: Path | str) -> None:
        self.fixture_dir = Path(fixture_dir)
        if not self.fixture_dir.exists():
            raise ValueError(
                f"fixture_dir does not exist: {self.fixture_dir} — "
                "run scripts/pageindex_offline_build.py first to generate fixtures."
            )

    async def build(
        self,
        *,
        tenant_id: str,
        doc_sha256: str,
        doc_text: str,
        doc_kind: str,
        meta: Optional[dict[str, Any]] = None,
    ) -> PageIndexTree:
        # doc_text is intentionally unused — fixture is keyed on doc_sha256.
        del doc_text, doc_kind, meta
        fixture_path = self.fixture_dir / f"{doc_sha256}.json"
        if not fixture_path.exists():
            raise FixtureNotFoundError(
                f"No pre-computed PageIndex tree for doc_sha256={doc_sha256[:12]}…"
                f" at {fixture_path}. Run scripts/pageindex_offline_build.py to generate."
            )
        with fixture_path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        root = _node_from_dict(payload["root"])
        return PageIndexTree(
            tenant_id=tenant_id,
            doc_sha256=doc_sha256,
            schema_version=int(payload.get("schema_version", self.schema_version)),
            root=root,
        )


class FixtureNotFoundError(LookupError):
    """Raised when FixturePageIndexTreeBuilder cannot locate a pre-computed JSON."""


class UpstreamPageIndexUnavailable(RuntimeError):
    """Raised by UpstreamPageIndexTreeBuilder when the cloned repo, the
    OPENAI_API_KEY env, or the Python executable can't be reached. Fail-
    closed: em refuse to silently fall back to Stub when caller asked
    for real upstream."""


# ---------------------------------------------------------------------------
# Upstream implementation — wraps VectifyAI/PageIndex via subprocess.
#
# PageIndex (MIT, https://github.com/VectifyAI/PageIndex) is CLI-first —
# the public surface is `python3 run_pageindex.py --pdf_path <path>`.
# Em invoke it via subprocess, parse the stdout JSON, and map upstream
# fields (title / summary / start_index / end_index / nodes) onto em's
# PageIndexNode shape (title / summary / page_start / page_end /
# children).
#
# Why subprocess instead of importing pageindex as a Python module:
#   1. PageIndex README documents the CLI, not a stable Python API. A
#      module import would couple em to private internals that may
#      change between minor versions.
#   2. PageIndex needs OPENAI_API_KEY — em route that through the
#      subprocess env, NOT through em's process env, so the secret
#      never lives in ai-orchestrator's memory space.
#   3. Repo stays out-of-tree per ADR-0025 sibling pattern (em "borrow"
#      the integration, em do not vendor the code).
#
# K-rules
# -------
# K-3 N/A — PageIndex talks to OpenAI directly via its own SDK. Em
#          accept this for the upstream-wrap path only; tenants that
#          require K-3 strict (LLM-gateway only) must stay on
#          StubPageIndexTreeBuilder or FixturePageIndexTreeBuilder.
# K-4    — Upstream usage REQUIRES tenant.consent_external=true. The
#          caller (router.py) is responsible for the consent check
#          before instantiating UpstreamPageIndexTreeBuilder; this class
#          assumes the check has already run.
# K-5    — PII redaction MUST be performed by the caller before passing
#          the PDF; PageIndex sees the bytes as-is.
# ---------------------------------------------------------------------------


class UpstreamPageIndexTreeBuilder(PageIndexTreeBuilder):
    """Invoke VectifyAI/PageIndex's `run_pageindex.py` via subprocess.

    Args:
      repo_path:        Filesystem path to a clone of
                        https://github.com/VectifyAI/PageIndex.
                        Anh clones it once per environment + pins the
                        commit SHA in ops docs for reproducibility.
      openai_api_key:   OPENAI_API_KEY value. Passed via subprocess env
                        only — never written to em's process env.
      python_executable: Python interpreter to run `run_pageindex.py`
                        with. Default: same interpreter ai-orchestrator
                        runs under (sys.executable).
      timeout_seconds:  Cap subprocess runtime. Large PDFs at gpt-4o
                        speed ≈ 30-90s per ~100 pages; em default 300s.
      model:            OpenAI model name passed via `--model`. Default
                        'gpt-4o-mini' — cheap + good enough per PageIndex
                        benchmarks. Override per tenant if SLA needs.

    The build() method requires `meta['pdf_path']` — PageIndex operates
    on file paths, not raw bytes. The caller is responsible for writing
    Bronze bytes to a tempfile + passing the path. Em chose this over
    "accept bytes here + write tempfile internally" so the caller
    controls tempfile cleanup + can reuse the same path across multiple
    engine calls.

    Raises:
      UpstreamPageIndexUnavailable — repo missing / API key missing /
                                      python executable missing
      ValueError — meta['pdf_path'] missing or not a readable file
      RuntimeError — subprocess timeout / non-zero exit / non-JSON stdout
    """

    schema_version = 1

    def __init__(
        self,
        *,
        repo_path: Path | str,
        openai_api_key: str,
        python_executable: Optional[str] = None,
        timeout_seconds: int = 300,
        model: str = "gpt-4o-mini",
    ) -> None:
        import os
        import sys

        self.repo_path = Path(repo_path)
        runner = self.repo_path / "run_pageindex.py"
        if not runner.is_file():
            raise UpstreamPageIndexUnavailable(
                f"PageIndex runner not found at {runner}. Clone "
                "https://github.com/VectifyAI/PageIndex into repo_path "
                "before activating UpstreamPageIndexTreeBuilder."
            )
        if not openai_api_key:
            raise UpstreamPageIndexUnavailable(
                "openai_api_key is empty. PageIndex requires an OpenAI "
                "key for LLM calls during tree build."
            )

        self.openai_api_key = openai_api_key
        self.python_executable = python_executable or sys.executable
        self.timeout_seconds = timeout_seconds
        self.model = model

        # Sanity-check python_executable resolves to something runnable.
        # We do NOT exec --version here because that would slow every
        # ai-orch boot when the class is instantiated; rely on subprocess
        # failure at build() time to surface env issues.
        if not Path(self.python_executable).exists() and not os.environ.get("PATH"):
            raise UpstreamPageIndexUnavailable(
                f"python_executable {self.python_executable!r} not found + PATH unset"
            )

    async def build(
        self,
        *,
        tenant_id: str,
        doc_sha256: str,
        doc_text: str,
        doc_kind: str,
        meta: Optional[dict[str, Any]] = None,
    ) -> PageIndexTree:
        import asyncio
        import os

        # PageIndex is PDF-first; markdown support varies by version.
        # Em fail loud rather than silently degrading.
        if doc_kind != "pdf":
            raise ValueError(
                f"UpstreamPageIndexTreeBuilder requires doc_kind='pdf'; got {doc_kind!r}. "
                "Markdown support depends on the cloned PageIndex revision — "
                "test before wiring."
            )

        meta = meta or {}
        pdf_path_raw = meta.get("pdf_path")
        if not pdf_path_raw:
            raise ValueError(
                "UpstreamPageIndexTreeBuilder requires meta['pdf_path']. "
                "Caller writes Bronze bytes to a tempfile + passes the path."
            )
        pdf_path = Path(pdf_path_raw)
        if not pdf_path.is_file():
            raise ValueError(
                f"meta['pdf_path']={pdf_path} is not a readable file."
            )

        # doc_text is intentionally unused on this path — PageIndex
        # parses the PDF itself; caller's text extraction is irrelevant
        # to the tree structure.
        del doc_text

        cmd = [
            self.python_executable,
            "run_pageindex.py",
            "--pdf_path", str(pdf_path),
            "--model", self.model,
        ]

        # Subprocess env: include OPENAI_API_KEY without leaking other
        # ai-orchestrator secrets. PATH is required so the python
        # interpreter can find shared libs.
        sub_env = {
            "PATH": os.environ.get("PATH", ""),
            "OPENAI_API_KEY": self.openai_api_key,
            # PYTHONUNBUFFERED so the upstream's stdout writes flush
            # promptly + em can timeout cleanly.
            "PYTHONUNBUFFERED": "1",
        }

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.repo_path),
                env=sub_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=self.timeout_seconds
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise RuntimeError(
                    f"PageIndex build timed out after {self.timeout_seconds}s "
                    f"for doc_sha256={doc_sha256[:12]}…"
                ) from None
        except FileNotFoundError as e:
            raise UpstreamPageIndexUnavailable(
                f"Could not exec {self.python_executable}: {e}"
            ) from e

        if proc.returncode != 0:
            stderr_text = stderr_b.decode("utf-8", errors="replace")[:500]
            raise RuntimeError(
                f"PageIndex exited {proc.returncode} for "
                f"doc_sha256={doc_sha256[:12]}…: {stderr_text}"
            )

        stdout_text = stdout_b.decode("utf-8", errors="replace")
        try:
            payload = _extract_pageindex_json(stdout_text)
        except ValueError as e:
            raise RuntimeError(
                f"PageIndex stdout did not contain parseable JSON: {e}\n"
                f"First 200 chars: {stdout_text[:200]!r}"
            ) from e

        root = _node_from_upstream(payload)
        return PageIndexTree(
            tenant_id=tenant_id,
            doc_sha256=doc_sha256,
            schema_version=self.schema_version,
            root=root,
        )


def _extract_pageindex_json(stdout_text: str) -> dict[str, Any]:
    """PageIndex prints progress lines + the final tree JSON to stdout.
    Em locate the first balanced JSON object and parse it.

    The upstream tool concatenates a "Tree saved to ..." line before
    the JSON in some versions; em scan from the first '{' to the last
    matching '}' and try to parse. Fail loud on malformed."""
    first = stdout_text.find("{")
    last = stdout_text.rfind("}")
    if first < 0 or last <= first:
        raise ValueError("no '{...}' found in stdout")
    candidate = stdout_text[first:last + 1]
    return json.loads(candidate)


def _node_from_upstream(payload: dict[str, Any]) -> PageIndexNode:
    """Map upstream PageIndex node shape onto em's PageIndexNode.

    Upstream fields (per VectifyAI/PageIndex README):
      title         → title
      summary       → summary
      start_index   → page_start (1-indexed page number)
      end_index     → page_end (1-indexed, inclusive)
      nodes         → children (recursion)
      node_id       → ignored (em doesn't carry it; can be added to
                       meta in a follow-up if needed for FE
                       highlight UX)

    Upstream may emit pages as int or string; em coerce. Missing
    fields default to None / "" so the tree still parses on partial
    output.
    """
    children_payload = payload.get("nodes") or payload.get("children") or []
    children = tuple(_node_from_upstream(c) for c in children_payload)

    def _to_int(v: Any) -> Optional[int]:
        if v is None:
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    return PageIndexNode(
        title=str(payload.get("title", "")),
        summary=str(payload.get("summary", "")),
        page_start=_to_int(payload.get("start_index")
                            or payload.get("page_start")),
        page_end=_to_int(payload.get("end_index")
                          or payload.get("page_end")),
        children=children,
    )


def _node_from_dict(payload: dict[str, Any]) -> PageIndexNode:
    """Deserialise PageIndexNode from JSON dict — recursive on children."""
    children_payload = payload.get("children") or []
    children = tuple(_node_from_dict(c) for c in children_payload)
    return PageIndexNode(
        title=str(payload["title"]),
        summary=str(payload.get("summary", "")),
        page_start=payload.get("page_start"),
        page_end=payload.get("page_end"),
        children=children,
        doc_offset_start=payload.get("doc_offset_start"),
        doc_offset_end=payload.get("doc_offset_end"),
    )


def node_to_dict(node: PageIndexNode) -> dict[str, Any]:
    """Serialise PageIndexNode → JSON-able dict — used by offline runner.

    Inverse of `_node_from_dict`. Public so the offline build script
    can call it directly without importing internals.
    """
    return {
        "title": node.title,
        "summary": node.summary,
        "page_start": node.page_start,
        "page_end": node.page_end,
        "doc_offset_start": node.doc_offset_start,
        "doc_offset_end": node.doc_offset_end,
        "children": [node_to_dict(c) for c in node.children],
    }
