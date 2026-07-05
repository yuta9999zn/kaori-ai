#!/usr/bin/env python3
"""Mirror the private kaori-system tree into the public kaori-ai working copy.

Why this exists: earlier mirrors were done by hand and silently dropped files
(utils/ once, then etl/ + config/), so the public repo — the AABW submission
link — was incomplete. This makes the mirror reproducible: it copies EVERY
tracked file from the private repo, so nothing gets left behind.

Rules:
  • Source of truth = the private repo's tracked files (`git ls-files`).
  • Copy add/update only — never delete — so public-only, intentional files
    survive: LICENSE, docs/ci-workflows/*, and the curated .github/workflows.
  • EXCLUDE `.github/` — the public repo keeps its own CI (a single ci.yml);
    mirroring the private workflows would run Actions we don't want on the fork.

Usage:
    python scripts/mirror-to-public.py [--public DIR] [--dry-run]

Defaults: --public D:/kaori-public-build. Run from the private repo root on the
branch/commit you want to publish. After it runs: cd into the public repo,
review `git status`, commit, and push.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# Path prefixes NOT mirrored (public curates its own copy of these).
EXCLUDE_PREFIXES = (".github/",)


def tracked_files(repo: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(repo), "ls-files"],
        capture_output=True, text=True, check=True,
    ).stdout
    return [line for line in out.splitlines() if line]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--private", default=".", help="private repo root (default: cwd)")
    ap.add_argument("--public", default="D:/kaori-public-build", help="public repo working copy")
    ap.add_argument("--dry-run", action="store_true", help="report only, copy nothing")
    args = ap.parse_args()

    priv = Path(args.private).resolve()
    pub = Path(args.public).resolve()
    if not (pub / ".git").exists():
        print(f"ERROR: {pub} is not a git working copy", file=sys.stderr)
        return 2

    added = updated = skipped = excluded = 0
    for rel in tracked_files(priv):
        if any(rel.startswith(p) for p in EXCLUDE_PREFIXES):
            excluded += 1
            continue
        src = priv / rel
        dst = pub / rel
        if not src.exists():          # tracked but absent on disk — skip
            skipped += 1
            continue
        exists = dst.exists()
        same = exists and dst.read_bytes() == src.read_bytes()
        if same:
            continue
        if args.dry_run:
            print(("UPDATE " if exists else "ADD    ") + rel)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        updated += 1 if exists else 0
        added += 0 if exists else 1

    print(f"\n{'DRY-RUN ' if args.dry_run else ''}mirror: "
          f"+{added} added, ~{updated} updated, {excluded} excluded (.github), "
          f"{skipped} tracked-but-missing")
    print(f"public copy: {pub}\nNext: cd there, `git status`, commit, push.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
