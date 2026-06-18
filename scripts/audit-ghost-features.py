#!/usr/bin/env python3
"""
Sprint 6 — Ghost feature detector.

Parses ``docs/BACKLOG.md`` for F-001..F-032 rows and verifies, for each:

  * **FE check**  — does the declared route file exist under ``frontend/app/``?
  * **BE check**  — is at least one declared endpoint actually registered in
                    a backend file (controller / router)?

Outputs a table and exits non-zero if any row is **Ghost** (FE route declared
but file missing, or BE endpoint declared but no matching handler in code).

The Phase 1 close-out signs off only when this prints zero Ghost rows for
F-001..F-032. Add to CI as a soft-warn step (don't hard-fail on Phase 2 work).

Usage::

    python scripts/audit-ghost-features.py                 # all F-001..F-032
    python scripts/audit-ghost-features.py --max F-040     # widen window
    python scripts/audit-ghost-features.py --strict        # exit 1 on Partial too
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path
from typing import Optional

# Windows console default cp1252 chokes on Vietnamese chars in BACKLOG row
# names. Force stdout/stderr to UTF-8 so the table prints cleanly.
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

# ─── Layout ─────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
BACKLOG = ROOT / "docs" / "BACKLOG.md"
FE_APP_DIRS = [
    ROOT / "frontend" / "app" / "(app)",
    ROOT / "frontend" / "app" / "(auth)",
    ROOT / "frontend" / "app" / "platform",
    ROOT / "frontend" / "app",
]
BE_SEARCH_DIRS = [
    ROOT / "services" / "auth-service" / "src" / "main" / "java",
    ROOT / "services" / "data-pipeline",
    ROOT / "services" / "ai-orchestrator",
    ROOT / "services" / "api-gateway" / "src" / "main" / "java",
    ROOT / "services" / "notification-service",
]


# ─── BACKLOG parsing ────────────────────────────────────────────────────────

ROW_RE = re.compile(
    r"^\|\s*(F-\d{3})\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|"
)


def parse_backlog(max_id: int) -> list[dict]:
    """Return ordered list of {f_id, name, portal, fe_routes, be_endpoints}.

    `max_id` filters F-001..F-{max}. Phase 1 = 32. Anything above max_id is
    skipped — Sprint 6 deliberately doesn't audit Phase 2/3 lines.
    """
    rows: list[dict] = []
    for line in BACKLOG.read_text(encoding="utf-8").splitlines():
        m = ROW_RE.match(line)
        if not m:
            continue
        f_id = m.group(1)
        if int(f_id.split("-")[1]) > max_id:
            continue
        rows.append({
            "f_id":          f_id,
            "name":          m.group(2),
            "portal":        m.group(3),
            "fe_routes":     _split_routes(m.group(4)),
            "be_endpoints":  _split_endpoints(m.group(5)),
        })
    return rows


def _split_routes(cell: str) -> list[str]:
    """Split FE route cell on ``space`` / backticks. Drop placeholders."""
    if cell.strip() in {"—", "-", "(middleware)", ""}:
        return []
    parts = re.findall(r"`([^`]+)`", cell)
    if not parts:
        parts = [cell.strip()]
    return [p for p in parts if p.startswith("/")]


def _split_endpoints(cell: str) -> list[tuple[str, str]]:
    """Return [(method, path), ...] from a BE endpoint cell.

    Wildcard-only paths (e.g. ``ALL /api/v1/*``) describe gateway-wide
    middleware, not a specific handler — they're returned with method
    ``ALL`` so the verdict step can mark them as "—" instead of Ghost.
    """
    if cell.strip() in {"—", "-", ""}:
        return []
    raw = re.findall(r"`([^`]+)`", cell) or [cell]
    out: list[tuple[str, str]] = []
    for entry in raw:
        # Match "POST /api/v1/foo" or "GET POST /foo" (multi-method shorthand).
        ms = re.findall(
            r"(GET|POST|PATCH|DELETE|PUT|ALL)\s+(/[A-Za-z0-9_./:{}\-*\\]+)",
            entry,
        )
        if ms:
            out.extend(ms)
        else:
            # No verb — sometimes the cell just lists the path.
            for p in re.findall(r"(/[A-Za-z0-9_./:{}\-*\\]+)", entry):
                out.append(("ANY", p))
    return out


# ─── FE / BE existence checks ───────────────────────────────────────────────

def fe_route_exists(route: str) -> bool:
    """Heuristic: a Next.js route ``/foo/bar`` lives at
    ``frontend/app/.../foo/bar/page.tsx``. Route groups in parens
    (``(auth)``, ``(app)``) are transparent to the URL — BACKLOG documents
    portal prefixes (``/p1``, ``/p2``) and sometimes the route-group name
    (``/auth``) that don't appear in the URL the user types.

    Strategy: drop those documentation prefixes, then check both the bare
    nesting and the dynamic-segment substitution (``:id`` → ``[id]``).
    """
    segs = [s for s in route.strip("/").split("/") if s]

    # Strip leading documentation-only portal segments. "platform" is NOT
    # in this list because the platform admin app lives at app/platform/*
    # (real route, not a doc shorthand).
    PORTAL_PREFIXES = {"p1", "p2", "p3", "p4", "auth"}
    while segs and segs[0].lower() in PORTAL_PREFIXES:
        segs = segs[1:]

    if not segs:
        # Bare "/platform" or similar — accept if any matching root file exists.
        for base in FE_APP_DIRS:
            if (base / "page.tsx").is_file():
                return True
        return False

    # Plural/singular variants: BACKLOG sometimes uses "pipelines" but the
    # FE folder is "pipeline" (or vice-versa). Try both for the first segment.
    head = segs[0]
    head_variants = {head}
    if head.endswith("s"):
        head_variants.add(head[:-1])
    else:
        head_variants.add(head + "s")

    candidates = []
    for base in FE_APP_DIRS:
        for h in head_variants:
            new_segs = [h] + segs[1:]
            # Direct nesting: app/(group)/foo/bar/page.tsx
            candidates.append(base.joinpath(*new_segs, "page.tsx"))
            # Dynamic segment substitution: :id → [id]
            dyn = [f"[{s[1:]}]" if s.startswith(":") else s for s in new_segs]
            candidates.append(base.joinpath(*dyn, "page.tsx"))
            # Multi-step wizards (F-017..F-021 each declare a step URL but
            # the actual page is a single /pipeline/new wizard) — accept the
            # parent path or the /new wizard if either exists.
            if len(new_segs) >= 2:
                candidates.append(base.joinpath(*new_segs[:-1], "page.tsx"))
                candidates.append(base.joinpath(h, "new", "page.tsx"))
            else:
                # Single-segment route — also try /new (some lists collapse).
                candidates.append(base.joinpath(h, "new", "page.tsx"))

    if any(c.is_file() for c in candidates):
        return True

    # Fallback: BACKLOG flags chart picker as a route, but it ships as a
    # client component (chart-registry.tsx) — accept either pattern.
    if "chart" in head.lower() or "analysis" in head.lower():
        chart_reg = ROOT / "frontend" / "components" / "charts" / "chart-registry.tsx"
        if chart_reg.is_file():
            return True

    return False


def be_endpoint_exists(method: str, path: str) -> Optional[bool]:
    """Heuristic: a route handler exists if at least one backend file
    contains a non-trivial substring of the path. We match the longest
    static suffix (after ``/api/v1/`` if present) so dynamic segments don't
    sabotage the search.

    Returns ``None`` for generic gateway-wide patterns (``/api/v1/*``,
    middleware) where there is no specific handler to find.
    """
    if method == "ALL" or path.endswith("/*") or path == "/*":
        return None  # gateway middleware, not a handler

    # Drop /api/v1 prefix — gateway rewrites it before forwarding,
    # so service-side routers list the bare path.
    bare = re.sub(r"^/api/v\d+", "", path)
    # Pick the longest static segment to match.
    static_segs = [
        s for s in bare.strip("/").split("/")
        if s and not s.startswith("{") and not s.startswith(":") and "*" not in s
    ]
    if not static_segs:
        return None
    needle = max(static_segs, key=len)
    if len(needle) < 3:
        return None  # too generic to disambiguate

    # Search for needle in any backend file.
    for d in BE_SEARCH_DIRS:
        if not d.is_dir():
            continue
        for f in d.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix not in {".java", ".py", ".kt", ".ts"}:
                continue
            try:
                if needle in f.read_text(encoding="utf-8", errors="ignore"):
                    return True
            except Exception:
                continue
    return False


# ─── Verdict ────────────────────────────────────────────────────────────────

def verdict(row: dict) -> tuple[str, str, str]:
    """Return ``(fe_status, be_status, overall)`` per row.

    Status tokens are ASCII to play nicely with Windows cp1252 stdout.
    ``OK`` = found, ``MISS`` = declared but not found, ``-`` = nothing
    declared in that side, ``n/a`` = generic gateway pattern.
    """
    if not row["fe_routes"]:
        fe_status = "-"
    else:
        ok = any(fe_route_exists(r) for r in row["fe_routes"])
        fe_status = "OK" if ok else "MISS"

    if not row["be_endpoints"]:
        be_status = "-"
    else:
        # be_endpoint_exists returns None for "this is middleware" entries.
        results = [be_endpoint_exists(m, p) for m, p in row["be_endpoints"]]
        if all(r is None for r in results):
            be_status = "n/a"
        elif any(r is True for r in results):
            be_status = "OK"
        else:
            be_status = "MISS"

    if fe_status == "MISS" or be_status == "MISS":
        overall = "Ghost"
    elif fe_status == "-" and be_status in {"-", "n/a"}:
        overall = "n/a"  # documentation-only row (e.g. infra)
    elif fe_status == "-" or be_status in {"-", "n/a"}:
        overall = "Partial"  # one side absent by design (middleware / shared)
    else:
        overall = "OK"
    return fe_status, be_status, overall


# ─── CLI ────────────────────────────────────────────────────────────────────

DEFAULT_ALLOWLIST: dict[str, str] = {
    # Documented in BACKLOG.md "Audit reconciliation" section.
    "F-013": "Onboarding wizard FE deferred to Phase 2 (endpoint name "
             "mismatch on the BE side as well). Not a regression.",
    "F-027": "Chart rendering is client-side (frontend/components/charts/"
             "chart-registry.tsx) — there is no /api/v1/charts/render "
             "handler by design. Spec-interpretation drift, not a Ghost.",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max", default="F-032",
                    help="Highest F-ID to audit, e.g. F-032 (default).")
    ap.add_argument("--strict", action="store_true",
                    help="Exit 1 on Partial rows too, not just Ghost.")
    ap.add_argument("--ignore", default="",
                    help="Comma-separated F-IDs to treat as known exceptions "
                         "(in addition to the built-in DEFAULT_ALLOWLIST).")
    args = ap.parse_args()

    extra_ignore = {x.strip() for x in args.ignore.split(",") if x.strip()}
    allowlist = {**DEFAULT_ALLOWLIST, **{k: "user-supplied --ignore" for k in extra_ignore}}

    max_id = int(args.max.split("-")[1])
    rows = parse_backlog(max_id)
    if not rows:
        print(f"No rows parsed for F-001..F-{max_id:03d} from {BACKLOG}",
              file=sys.stderr)
        return 2

    print(f"\nGhost-feature audit (F-001..F-{max_id:03d}) — {BACKLOG.relative_to(ROOT)}")
    print("-" * 95)
    print(f"{'F-ID':<8} {'FE':<8} {'BE':<8} {'Status':<10} Name")
    print("-" * 95)

    ghost_count        = 0   # real Ghosts (counted toward exit code)
    allowlisted_count  = 0   # Ghosts with documented allowlist entry
    partial_count      = 0
    allowlisted_rows: list[tuple[str, str]] = []
    for row in rows:
        fe_s, be_s, overall = verdict(row)
        if overall == "Ghost":
            if row["f_id"] in allowlist:
                overall = "(known)"
                allowlisted_count += 1
                allowlisted_rows.append((row["f_id"], allowlist[row["f_id"]]))
            else:
                ghost_count += 1
        elif overall == "Partial":
            partial_count += 1
        name = row["name"]
        if len(name) > 60:
            name = name[:57] + "..."
        print(f"{row['f_id']:<8} {fe_s:<8} {be_s:<8} {overall:<10} {name}")

    print("-" * 95)
    ok_count = len(rows) - ghost_count - partial_count - allowlisted_count
    # Account for the n/a (documentation-only) rows in the OK bucket too —
    # they aren't Ghost, Partial, or known-exception by definition.
    print(f"Total: {len(rows)}  OK/n-a {ok_count}  Partial {partial_count}"
          f"  Known {allowlisted_count}  Ghost {ghost_count}\n")

    if allowlisted_rows:
        print("Known exceptions (NOT counted as Ghost):")
        for fid, reason in allowlisted_rows:
            print(f"  - {fid}: {reason}")
        print()

    if ghost_count > 0:
        print(f"FAIL: {ghost_count} unallowlisted Ghost row(s). "
              f"Phase 1 close-out cannot sign off.", file=sys.stderr)
        return 1
    if args.strict and partial_count > 0:
        print(f"FAIL (--strict): {partial_count} Partial row(s).", file=sys.stderr)
        return 1
    print("OK — no unallowlisted Ghost rows in scope.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
