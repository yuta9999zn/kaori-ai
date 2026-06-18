#!/usr/bin/env python3
"""
PageIndex offline tree builder — P15-S11 Build Week prep (Tuần 2).

Pre-computes the PageIndex hierarchical TOC tree for a source PDF/Markdown
ONCE on the operator's machine, then writes a JSON fixture that
`FixturePageIndexTreeBuilder` loads at runtime. This means the demo path
has zero runtime external service dependency — no OpenAI key, no PageIndex
Cloud API key needed during the 8/7 Build Week presentation.

Why offline + fixture instead of runtime wrap:
- PyPI `pageindex==0.2.8` is a thin SDK for PageIndex Cloud (`pageindex.ai`),
  not a local tree-builder. Calling it at runtime would send the source PDF
  to an external service — violating K-4 (consent_external) and K-5 (PII
  redaction before external API call).
- The OSS GitHub repo (`run_pageindex.py`) is CLI-only and needs OpenAI
  directly. Wrapping it into a Kaori-internal LLM gateway call is a 3-5d
  task that lands post-Build-Week.
- Fixture approach: 0.5d, deterministic, no runtime external dependency.

Usage (operator runs locally, ONE TIME per source doc):

    # Option 1: via PageIndex Cloud SDK (requires PAGEINDEX_API_KEY env)
    python scripts/pageindex_offline_build.py \\
        --pdf "D:/Kaori Document/Book/876924133-Data-Visualization-and-Storytelling-With-Tableau-Mamta-Mittal.pdf" \\
        --out "services/ai-orchestrator/tests/fixtures/pageindex_trees/" \\
        --backend cloud

    # Option 2: via OSS run_pageindex.py CLI (requires OPENAI_API_KEY env +
    # clone of github.com/VectifyAI/PageIndex locally)
    python scripts/pageindex_offline_build.py \\
        --pdf "..." \\
        --out "..." \\
        --backend oss \\
        --oss-repo "D:/code/PageIndex"

The output is `{doc_sha256}.json` matching the PageIndexTree schema used by
`FixturePageIndexTreeBuilder`. Same input PDF → same SHA-256 → same fixture
file name (idempotent).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

# Allow importing from services/ai-orchestrator when run from repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "services" / "ai-orchestrator"))

from reasoning.rag.pageindex import PageIndexNode, node_to_dict  # noqa: E402


def compute_doc_sha256(pdf_path: Path) -> str:
    """SHA-256 of source bytes — keys the fixture file name."""
    h = hashlib.sha256()
    with pdf_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def build_via_pageindex_cloud(pdf_path: Path, api_key: str) -> dict[str, Any]:
    """Use PyPI pageindex==0.2.8 SDK to submit + fetch tree from cloud.

    Returns the raw tree dict from the cloud response. Cloud SDK is fine
    for offline pre-compute (operator's machine, source PDF is the
    operator's own book) — only RUNTIME calls violate K-4/K-5.
    """
    try:
        from pageindex import PageIndexClient  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "pageindex package not installed. Run:\n"
            "    pip install pageindex==0.2.8\n"
            f"(import error: {exc})"
        )
    client = PageIndexClient(api_key=api_key)
    result = client.submit_document(str(pdf_path))
    doc_id = result.get("doc_id") or result.get("id")
    if not doc_id:
        raise SystemExit(f"PageIndex cloud submit failed — no doc_id in response: {result}")
    tree_response = client.get_tree(doc_id)
    return _coerce_cloud_tree_to_kaori_schema(tree_response, pdf_path)


def build_via_oss_cli(pdf_path: Path, oss_repo: Path) -> dict[str, Any]:
    """Shell out to VectifyAI/PageIndex `run_pageindex.py --pdf_path`.

    Requires the operator to have cloned the OSS repo locally + set
    OPENAI_API_KEY in env. The OSS path writes a tree.json next to the
    PDF; we parse + re-shape it.
    """
    import subprocess

    if not oss_repo.exists():
        raise SystemExit(f"--oss-repo path not found: {oss_repo}")
    runner = oss_repo / "run_pageindex.py"
    if not runner.exists():
        raise SystemExit(f"run_pageindex.py not found at {runner}")
    cmd = [sys.executable, str(runner), "--pdf_path", str(pdf_path)]
    print(f"[oss] running: {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=str(oss_repo))
    if result.returncode != 0:
        raise SystemExit(
            f"OSS run_pageindex.py exited {result.returncode}\n"
            f"stderr: {result.stderr[:2000]}"
        )
    # OSS writes results/{pdf_stem}.json typically.
    output_json = oss_repo / "results" / f"{pdf_path.stem}.json"
    if not output_json.exists():
        raise SystemExit(f"OSS run did not produce expected output at {output_json}")
    with output_json.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return _coerce_oss_tree_to_kaori_schema(raw, pdf_path)


def _coerce_cloud_tree_to_kaori_schema(
    cloud_tree: dict[str, Any], pdf_path: Path
) -> dict[str, Any]:
    """Map PageIndex Cloud SDK response → Kaori PageIndexTree dict shape.

    Cloud response keys (per docs.pageindex.ai/sdk/tree):
      title, summary, start_page, end_page, nodes (list of children)

    Kaori schema (PageIndexNode dataclass): title, summary, page_start,
    page_end, children. Empty summary → fallback to title.
    """

    def _convert(node_raw: dict[str, Any]) -> PageIndexNode:
        title = str(node_raw.get("title") or "(untitled)").strip()
        summary = str(node_raw.get("summary") or node_raw.get("text") or title).strip()
        children_raw = node_raw.get("nodes") or node_raw.get("children") or []
        children = tuple(_convert(c) for c in children_raw)
        return PageIndexNode(
            title=title,
            summary=summary,
            page_start=_to_int_or_none(node_raw.get("start_page") or node_raw.get("page_start")),
            page_end=_to_int_or_none(node_raw.get("end_page") or node_raw.get("page_end")),
            children=children,
        )

    root_node = _convert(cloud_tree)
    return {
        "schema_version": 1,
        "doc_filename": pdf_path.name,
        "source_backend": "pageindex_cloud_sdk_0_2_8",
        "root": node_to_dict(root_node),
    }


def build_via_local_toc(pdf_path: Path) -> dict[str, Any]:
    """Extract PDF outline (Table of Contents bookmarks) — no LLM, no network.

    Uses pypdf to read the embedded outline metadata. Works for any PDF
    that was authored with proper TOC bookmarks (most published books +
    most LaTeX/Word exports). Fallback to per-page chunking when the PDF
    has no outline.

    Why this is defensible for Build Week:
    - K-4 / K-5 fully respected (zero external traffic).
    - Deterministic per PDF (no LLM randomness).
    - Real chapter titles + page ranges from the document's own metadata.
    - 0 cost, runs in seconds.

    Limitation: relies on the PDF having an outline. Books from publishers
    usually do. Scanned-and-OCRd PDFs typically don't — fallback chunker
    kicks in to produce 10-page synthetic sections so the tree is at
    least usable.
    """
    try:
        import pypdf  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "pypdf not installed. Run:\n    pip install pypdf\n"
            f"(import error: {exc})"
        )

    reader = pypdf.PdfReader(str(pdf_path))
    total_pages = len(reader.pages)
    print(f"[local-toc] {pdf_path.name}: {total_pages} pages")

    # pypdf.outline is a nested list of `Destination` objects + sub-lists.
    raw_outline = getattr(reader, "outline", None) or []

    def _page_of(dest: Any) -> Optional[int]:
        """Resolve a Destination → 1-indexed page number, None if unresolvable."""
        try:
            page_index = reader.get_destination_page_number(dest)
            return int(page_index) + 1 if page_index is not None else None
        except Exception:
            return None

    flat: list[dict[str, Any]] = []

    def _walk(items: Any, depth: int = 0) -> None:
        i = 0
        while i < len(items):
            entry = items[i]
            if isinstance(entry, list):
                _walk(entry, depth + 1)
                i += 1
                continue
            title = getattr(entry, "title", None) or "(untitled)"
            page = _page_of(entry)
            flat.append(
                {
                    "title": str(title).strip(),
                    "page_start": page,
                    "depth": depth,
                }
            )
            # Next item might be a sub-list (children).
            i += 1

    _walk(raw_outline)

    # Fallback: no outline → synthetic 10-page chunks.
    if not flat:
        print(
            f"[local-toc] {pdf_path.name} has no outline metadata — "
            "falling back to per-10-page chunks."
        )
        chunk_size = 10
        for start in range(1, total_pages + 1, chunk_size):
            end = min(start + chunk_size - 1, total_pages)
            flat.append(
                {
                    "title": f"Pages {start}-{end}",
                    "page_start": start,
                    "depth": 0,
                }
            )

    # Compute page_end for each entry as (page_start of next sibling - 1),
    # last entry → total_pages.
    for i, entry in enumerate(flat):
        if i + 1 < len(flat):
            next_start = flat[i + 1]["page_start"]
            if next_start is not None and entry["page_start"] is not None:
                entry["page_end"] = max(entry["page_start"], next_start - 1)
            else:
                entry["page_end"] = entry["page_start"]
        else:
            entry["page_end"] = total_pages

    # Build hierarchical tree from flat depth-tagged list.
    top: list[PageIndexNode] = []
    stack: list[tuple[int, list[PageIndexNode]]] = [(0, top)]  # (depth, children_list)

    for entry in flat:
        node = PageIndexNode(
            title=entry["title"],
            summary=(
                f"{entry['title']} "
                f"(p.{entry['page_start']}-{entry['page_end']})"
                if entry["page_start"] is not None
                else entry["title"]
            ),
            page_start=entry["page_start"],
            page_end=entry["page_end"],
        )
        depth = entry["depth"]
        # Pop stack until we find the parent depth.
        while stack and stack[-1][0] >= depth:
            stack.pop()
        if not stack:
            top.append(node)
            stack.append((depth, []))  # synthetic
        else:
            # Mutate the previous sibling at the parent level by replacing it
            # with a copy that has this node as a child. Because PageIndexNode
            # is frozen we collect children separately, then rebuild on emit.
            parent_children = stack[-1][1]
            parent_children.append(node)
        # Push this node's child-list onto the stack so deeper entries become its children.
        stack.append((depth, []))  # placeholder for children of `node`
        # Re-link: the just-pushed list IS where deeper entries land. To keep
        # references coherent we mutate the dict-based intermediate first.
        # (See finaliser below.)

    # Simpler rebuild — use mutable dict intermediate, then convert to PageIndexNode.
    # Re-do the algorithm with dicts because frozen dataclass + mutation is awkward.
    root_dict: dict[str, Any] = {
        "title": pdf_path.stem,
        "summary": f"Local-TOC extracted index for {pdf_path.name} ({total_pages} pages).",
        "page_start": 1,
        "page_end": total_pages,
        "children": [],
    }
    parent_stack: list[tuple[int, dict[str, Any]]] = [(-1, root_dict)]

    for entry in flat:
        depth = entry["depth"]
        while parent_stack and parent_stack[-1][0] >= depth:
            parent_stack.pop()
        parent = parent_stack[-1][1] if parent_stack else root_dict
        node_dict = {
            "title": entry["title"],
            "summary": (
                f"{entry['title']} "
                f"(p.{entry['page_start']}-{entry['page_end']})"
                if entry["page_start"] is not None
                else entry["title"]
            ),
            "page_start": entry["page_start"],
            "page_end": entry["page_end"],
            "children": [],
        }
        parent["children"].append(node_dict)
        parent_stack.append((depth, node_dict))

    return {
        "schema_version": 1,
        "doc_filename": pdf_path.name,
        "source_backend": "pypdf_local_toc",
        "root": root_dict,
    }


def _coerce_oss_tree_to_kaori_schema(
    oss_raw: Any, pdf_path: Path
) -> dict[str, Any]:
    """Map OSS run_pageindex.py output → Kaori PageIndexTree dict shape.

    OSS output is typically a list of top-level nodes (no synthetic root)
    or a dict with `result` key. We wrap in a synthetic root if needed.
    """
    if isinstance(oss_raw, dict) and "result" in oss_raw:
        nodes = oss_raw["result"]
    elif isinstance(oss_raw, list):
        nodes = oss_raw
    else:
        nodes = [oss_raw] if isinstance(oss_raw, dict) else []

    def _convert(node_raw: dict[str, Any]) -> PageIndexNode:
        title = str(node_raw.get("title") or "(untitled)").strip()
        summary = str(node_raw.get("summary") or node_raw.get("text") or title).strip()
        children_raw = node_raw.get("nodes") or node_raw.get("children") or []
        children = tuple(_convert(c) for c in children_raw)
        return PageIndexNode(
            title=title,
            summary=summary,
            page_start=_to_int_or_none(node_raw.get("start_page") or node_raw.get("page_start")),
            page_end=_to_int_or_none(node_raw.get("end_page") or node_raw.get("page_end")),
            children=children,
        )

    children = tuple(_convert(n) for n in nodes) if nodes else ()
    root_node = PageIndexNode(
        title=pdf_path.stem,
        summary=f"Pre-computed PageIndex tree for {pdf_path.name} (OSS backend).",
        page_start=None,
        page_end=None,
        children=children,
    )
    return {
        "schema_version": 1,
        "doc_filename": pdf_path.name,
        "source_backend": "vectifyai_pageindex_oss",
        "root": node_to_dict(root_node),
    }


def _to_int_or_none(val: Any) -> int | None:
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pdf", required=True, type=Path, help="Source PDF or Markdown path.")
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Output directory — fixture written as {doc_sha256}.json here.",
    )
    parser.add_argument(
        "--backend",
        choices=("cloud", "oss", "local-toc"),
        default="local-toc",
        help=(
            "cloud = PyPI pageindex SDK (PAGEINDEX_API_KEY); "
            "oss = clone of VectifyAI/PageIndex (OPENAI_API_KEY); "
            "local-toc = pypdf outline (no key, no network) — Build Week default."
        ),
    )
    parser.add_argument(
        "--oss-repo",
        type=Path,
        help="Path to local clone of github.com/VectifyAI/PageIndex (required when --backend=oss).",
    )
    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"ERROR: --pdf not found: {args.pdf}", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)

    doc_sha = compute_doc_sha256(args.pdf)
    print(f"doc_sha256 = {doc_sha}")
    out_file = args.out / f"{doc_sha}.json"

    if args.backend == "cloud":
        import os

        api_key = os.environ.get("PAGEINDEX_API_KEY")
        if not api_key:
            print("ERROR: PAGEINDEX_API_KEY env var not set.", file=sys.stderr)
            return 3
        print(f"[cloud] submitting {args.pdf.name} to PageIndex Cloud …")
        payload = build_via_pageindex_cloud(args.pdf, api_key)
    elif args.backend == "oss":
        if not args.oss_repo:
            print("ERROR: --oss-repo required when --backend=oss", file=sys.stderr)
            return 4
        payload = build_via_oss_cli(args.pdf, args.oss_repo)
    else:  # local-toc
        payload = build_via_local_toc(args.pdf)

    with out_file.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print(f"Wrote fixture: {out_file}")
    print("Use it from Python:")
    print("    from reasoning.rag.pageindex import FixturePageIndexTreeBuilder")
    print(f"    builder = FixturePageIndexTreeBuilder('{args.out}')")
    print(f"    tree = await builder.build(tenant_id='...', doc_sha256='{doc_sha}', "
          f"doc_text='', doc_kind='pdf')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
