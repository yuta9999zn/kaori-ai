#!/usr/bin/env python3
"""
Strip <AppShell currentPath="..."> wrap from P2 templates.

Each template in `frontend/components/p2/templates/*.tsx` historically
wrapped its content in:

    <AppShell currentPath="/p2/...">
      ...content...
    </AppShell>

After P2-shell-consolidation 2026-05-18 the AppShell lives at
`app/(app)/p2/layout.tsx` and reads usePathname() itself. Templates
should render content only.

This script:
  1. Removes the <AppShell currentPath="..."> opening tag.
  2. Removes the matching </AppShell> closing tag.
  3. Drops `AppShell` from the `@/components/p2/shell` import (keeps
     PageHeader and other named imports).

Run from the repo root:
    python scripts/strip_p2_appshell.py            # write
    python scripts/strip_p2_appshell.py --dry-run  # preview only
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path

# Force UTF-8 stdout for Vietnamese filenames + diff output on Windows.
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

REPO_ROOT  = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "frontend" / "components" / "p2" / "templates"

# `<AppShell currentPath="..." >` (string), `<AppShell currentPath={expr}>`
# (plain JSX expr), or `<AppShell currentPath={`tpl ${id}`}>` (template literal
# whose `${...}` interpolations contain nested braces). The braces alternation
# `(?:[^{}]|\{[^{}]*\})*` allows ONE level of nested `{...}`, which is
# enough for `${...}` inside a backtick.
OPEN_RE  = re.compile(
    r'<AppShell(?:\s+currentPath=(?:"[^"]*"|\{(?:[^{}]|\{[^{}]*\})*\}))?\s*>',
    re.MULTILINE,
)
CLOSE_RE = re.compile(r'</AppShell>')

# Import line: `import { AppShell, PageHeader, ... } from '@/components/p2/shell'`
# We keep every named import EXCEPT AppShell. If only AppShell was imported,
# the whole line is dropped.
IMPORT_RE = re.compile(
    r"import\s*\{\s*([^}]*?)\s*\}\s*from\s*'@/components/p2/shell'\s*;?\s*\n",
)


def fix_import(match: re.Match[str]) -> str:
    names = [n.strip() for n in match.group(1).split(",")]
    names = [n for n in names if n and n != "AppShell"]
    if not names:
        return ""  # whole import line removed
    return f"import {{ {', '.join(names)} }} from '@/components/p2/shell';\n"


def transform(text: str) -> tuple[str, dict[str, int]]:
    """Replace AppShell wrap with a JSX fragment <>…</> so the page still
    has a single root element. Removing the tags outright leaves multiple
    siblings at return-level — TS / Next compile fails on that."""
    counts = {"open": 0, "close": 0, "imports": 0}
    new = OPEN_RE.sub(lambda m: (counts.__setitem__("open", counts["open"] + 1), "<>")[1], text)
    new = CLOSE_RE.sub(lambda m: (counts.__setitem__("close", counts["close"] + 1), "</>")[1], new)
    new = IMPORT_RE.sub(
        lambda m: (counts.__setitem__("imports", counts["imports"] + 1), fix_import(m))[1],
        new,
    )
    return new, counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="Print summary without touching files.")
    ap.add_argument("--only", help="Process only this template basename (for testing).")
    args = ap.parse_args()

    if not TEMPLATE_DIR.is_dir():
        print(f"FATAL: template dir not found: {TEMPLATE_DIR}", file=sys.stderr)
        return 2

    files = sorted(TEMPLATE_DIR.glob("*.tsx"))
    if args.only:
        files = [f for f in files if f.name == args.only]
        if not files:
            print(f"No template matched --only={args.only}", file=sys.stderr)
            return 1

    touched = 0
    skipped = 0
    no_match = 0
    for f in files:
        text = f.read_text(encoding="utf-8")
        if "<AppShell" not in text and "AppShell" not in text:
            no_match += 1
            continue
        new_text, counts = transform(text)
        if new_text == text:
            skipped += 1
            continue
        if args.dry_run:
            print(f"[DRY] {f.name}  open={counts['open']} close={counts['close']} imports={counts['imports']}")
        else:
            f.write_text(new_text, encoding="utf-8")
            print(f"  wrote {f.name}  open={counts['open']} close={counts['close']} imports={counts['imports']}")
        touched += 1

    print(f"\nSummary — total {len(files)} files · touched {touched} · skipped {skipped} · no AppShell {no_match}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
