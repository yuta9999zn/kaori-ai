#!/usr/bin/env python3
"""
N8 Governance — Check CR-#### compliance in commit messages.

Per CR Register v2.1 §9 Governance finding lần 1+2 lesson: code shipped without
formal CR (CR-0009, CR-0010 post-facto). Lesson learned 2026-05-21: PR merge
cho feature module mới phải gắn `CR-####` trong commit message.

Usage:
    python scripts/check_cr_compliance.py                # check last commit
    python scripts/check_cr_compliance.py --since main   # check commits since main
    python scripts/check_cr_compliance.py --ci           # CI mode: exit 1 if violation

Scope (commits MUST include CR-####):
    - migrations/ new file (mig 100+)
    - routers/ new endpoint file
    - services/ new module file (not test edit)

Scope EXCLUDED (no CR required):
    - test edits / fix
    - docs/ changes
    - infra config tweaks (existing topology)

Pattern enforced: `CR-\\d{4}` (CR + 4-digit number) trong subject hoặc body.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import List

CR_PATTERN = re.compile(r"CR-\d{4}")

# Paths triggering CR requirement
TRIGGER_PATHS = [
    "infrastructure/postgres/migrations/",
    "services/ai-orchestrator/routers/",
    "services/data-pipeline/routers/",
    "services/llm-gateway/routers/",
    "services/auth-service/src/main/java/com/kaori/auth/controller/",
]

# Exception: changes to existing files are OK; new files only
# Exception: test files
EXCLUDED_PATTERNS = [
    "/tests/",
    "/test_",
    "_test.py",
    ".test.ts",
    "/docs/",
    "/scripts/",  # changes to scripts/ themselves are governance-related, exempt
    "README.md",
]


def get_commits_since(base: str) -> List[str]:
    """Return list of commit SHAs from base..HEAD."""
    result = subprocess.run(
        ["git", "rev-list", f"{base}..HEAD"],
        capture_output=True, text=True, check=True,
    )
    return [s.strip() for s in result.stdout.splitlines() if s.strip()]


def get_commit_message(sha: str) -> str:
    """Return full commit message (subject + body) for sha."""
    result = subprocess.run(
        ["git", "log", "-1", "--format=%B", sha],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def get_commit_files(sha: str) -> List[str]:
    """Return list of files changed in commit (added/modified/deleted)."""
    result = subprocess.run(
        ["git", "show", "--name-status", "--format=", sha],
        capture_output=True, text=True, check=True,
    )
    files = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # Format: "A\tfile/path" or "M\tfile/path" or "D\tfile/path"
        parts = line.split("\t", 1)
        if len(parts) == 2:
            status, path = parts
            # Only flag added files (new code = new CR territory)
            if status == "A":
                files.append(path)
    return files


def requires_cr(files: List[str]) -> List[str]:
    """Return subset of files that trigger CR requirement."""
    triggered = []
    for f in files:
        if any(excl in f for excl in EXCLUDED_PATTERNS):
            continue
        if any(f.startswith(trig) for trig in TRIGGER_PATHS):
            triggered.append(f)
    return triggered


def check_commit(sha: str, verbose: bool = False) -> List[str]:
    """Return list of violations (empty = compliant)."""
    msg = get_commit_message(sha)
    files = get_commit_files(sha)
    triggered = requires_cr(files)

    if not triggered:
        return []  # No triggering files, no CR needed

    if CR_PATTERN.search(msg):
        if verbose:
            print(f"[OK] {sha[:8]} compliant (CR ref found)")
        return []  # CR-#### in message
    return [
        f"[WARN] {sha[:8]} VIOLATION: {len(triggered)} triggering files but no CR-#### in message.\n"
        f"  Files: {', '.join(triggered[:3])}{' ...' if len(triggered) > 3 else ''}\n"
        f"  Subject: {msg.splitlines()[0] if msg else '(empty)'}"
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check CR-#### compliance in commit messages")
    parser.add_argument("--since", default="HEAD~1", help="Base ref (default: HEAD~1, last commit)")
    parser.add_argument("--ci", action="store_true", help="CI mode: exit 1 on any violation")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    try:
        commits = get_commits_since(args.since)
    except subprocess.CalledProcessError as e:
        print(f"git error: {e.stderr}", file=sys.stderr)
        return 2

    if not commits:
        if args.verbose:
            print(f"No commits since {args.since}")
        return 0

    violations = []
    for sha in commits:
        v = check_commit(sha, verbose=args.verbose)
        violations.extend(v)

    if violations:
        print(f"\n{len(violations)} CR compliance violation(s):", file=sys.stderr)
        for v in violations:
            print(v, file=sys.stderr)
        if args.ci:
            print(
                "\nPer CR Register v2.1 §9 Governance: PR merge cho feature module mới\n"
                "phải gắn CR-#### trong commit message. Submit CR via 4.1 §4.2 Re-baseline\n"
                "process trước khi merge.",
                file=sys.stderr,
            )
            return 1
        return 0

    if args.verbose:
        print(f"\n[OK] All {len(commits)} commit(s) compliant")
    return 0


if __name__ == "__main__":
    sys.exit(main())
