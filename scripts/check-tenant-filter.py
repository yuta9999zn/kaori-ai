#!/usr/bin/env python3
"""
Phase 2 error-handling B3 PR #7 — multi-tenant data leak guard (#9).

Scans Python (``.py``) and Java (``.java``) source files for SQL string
literals that touch a **tenant-scoped** table without an
``enterprise_id`` predicate. Emits a non-zero exit code when any
violation is found, suitable for use as a CI gate.

How it works
------------
1. Walks ``services/`` (and any extra root passed on the CLI) for source
   files. Skips tests, migrations, build outputs, and any file matching
   ``PATH_ALLOWLIST``.
2. For each file, scans line-by-line for SQL fragments that reference one
   of the known tenant tables in a ``FROM`` / ``JOIN`` / ``UPDATE`` /
   ``INTO`` / ``DELETE FROM`` clause.
3. For each match, checks a ±15-line window around the line for the
   token ``enterprise_id``. If absent, the match is reported.
4. ``# tenant-filter-lint: allow`` (Python) or ``// tenant-filter-lint:
   allow`` (Java) on the SAME line as the SQL silences a single match —
   the inline magic comment is the documented override for the rare
   legitimate cross-tenant case (e.g. cron iterating every tenant).
5. DDL statements (``CREATE TABLE``, ``ALTER TABLE``, ``DROP``, etc.)
   are exempt — they don't take a tenant predicate.

Why this is a heuristic, not a parser
-------------------------------------
Real production SQL is built from concatenations, f-strings, JPQL
fragments, jOOQ DSL calls, etc. A perfect parse is not feasible. The
window-based heuristic catches the common shape of "string literal
references a tenant table; nearby code never mentions enterprise_id"
which is exactly the bug class #9 in the error-handling spec is trying
to prevent. False positives are silenced with the inline comment;
false negatives (e.g. SQL spread over a 30+ line span with no tenant
keyword) are accepted as the cost of the heuristic.

Usage
-----
::

    python scripts/check-tenant-filter.py              # full scan
    python scripts/check-tenant-filter.py --root .     # explicit root
    python scripts/check-tenant-filter.py --quiet      # only print on violation

Exit code
---------
``0`` when no violations, ``1`` when at least one violation is found
(or on a CLI usage error).
"""

from __future__ import annotations

import argparse
import fnmatch
import io
import re
import sys
from dataclasses import dataclass
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)


# ----------------------------------------------------------------------
# Tenant-scoped tables (every read/write must filter by enterprise_id).
# Keep in sync with infrastructure/postgres/migrations/005_rls.sql +
# 015/017/018/019/022.
# ----------------------------------------------------------------------
TENANT_TABLES = {
    "pipeline_runs",
    "bronze_files",
    "bronze_rows",
    "canonical_schemas",
    "decision_audit_log",
    "silver_rows",
    "cleaning_rules_applied",
    "analysis_runs",
    "analysis_results",
    "enterprise_users",
    "enterprise_monthly_billing",
    "etl_run_log",
    "decision_outcomes",
    "event_outbox",
    "tenant_settings",
    "gold_features",
    "gold_aggregates",
    "decision_actions",
    "subscription_change_requests",
    "api_request_log",
}


# ----------------------------------------------------------------------
# Path allow-list — files that legitimately query tenant tables across
# every tenant (cron jobs that iterate all enterprises, platform-admin
# aggregation endpoints, the outbox publisher, etc.). Glob patterns
# relative to the repo root, fnmatch semantics.
# ----------------------------------------------------------------------
PATH_ALLOWLIST = [
    # Tests + migrations + build outputs are never tenant-scoped code.
    "**/test/**",
    "**/tests/**",
    "**/__tests__/**",
    "**/conftest.py",
    "**/*_test.py",
    "**/test_*.py",
    "**/target/**",
    "**/build/**",
    "**/node_modules/**",
    "**/.venv/**",
    "**/venv/**",
    "infrastructure/postgres/migrations/**",
    "scripts/**",
    # Cross-tenant aggregation crons (iterate every enterprise inside
    # one job; tenant filter is per-iteration, not per-statement).
    "services/auth-service/src/main/java/com/kaorisystem/auth/job/**",
    # Platform-admin aggregation services — explicitly read across
    # tenants because that IS the platform-admin job.
    "services/auth-service/src/main/java/com/kaorisystem/auth/service/PlatformBillingService.java",
    "services/auth-service/src/main/java/com/kaorisystem/auth/service/PlatformAdminService.java",
    "services/auth-service/src/main/java/com/kaorisystem/auth/service/PlatformAdminAuditService.java",
    # Outbox publisher reads ALL tenants' pending rows then routes them.
    "services/*/outbox/publisher.py",
    "services/*/outbox/relay.py",
    "services/*/shared/outbox.py",
    "services/*/shared/outbox_publisher.py",
    # Platform-admin chat tool registry — by design queries across every
    # tenant; role gate sits in the chat agent, not at the SQL boundary.
    "services/ai-orchestrator/chat/tools/platform.py",
    # Platform stats dashboard service — same shape as the chat platform tools.
    "services/auth-service/src/main/java/com/kaorisystem/auth/service/PlatformStatsService.java",
]


# ----------------------------------------------------------------------
# Regexes
# ----------------------------------------------------------------------
# Match `FROM/JOIN/UPDATE/INTO <table>` or `DELETE FROM <table>`.
# Allows optional `public.` schema prefix and optional double-quoting.
SQL_TENANT_PATTERN = re.compile(
    r'\b(?:FROM|JOIN|UPDATE|INTO|DELETE\s+FROM)\s+'
    r'(?:public\.)?'
    r'"?(' + "|".join(sorted(TENANT_TABLES, key=len, reverse=True)) + r')"?'
    r'\b',
    re.IGNORECASE,
)

# Substring match (no \b) so we also recognise `x_enterprise_id`,
# `tenant_enterprise_id`, etc. — common shapes for predicate parameters
# in router/service code. The token is unique enough that the false-
# positive surface from substring matching is negligible.
ENTERPRISE_ID_PATTERN = re.compile(r"enterprise_id|enterpriseId", re.IGNORECASE)

# DDL statements never filter by tenant.
DDL_PATTERN = re.compile(
    r"\b(?:CREATE|ALTER|DROP|TRUNCATE|GRANT|REVOKE|COMMENT\s+ON)\s+"
    r"(?:TABLE|INDEX|VIEW|TRIGGER|RULE|POLICY|MATERIALIZED|SEQUENCE|EXTENSION)\b",
    re.IGNORECASE,
)

ALLOW_INLINE = "tenant-filter-lint: allow"

WINDOW = 15


@dataclass
class Violation:
    path: Path
    line_number: int
    table: str
    line: str

    def render(self, root: Path) -> str:
        rel = self.path.relative_to(root)
        return f"  {rel}:{self.line_number}  [{self.table}]\n      {self.line.strip()}"


# ----------------------------------------------------------------------
# Scanning
# ----------------------------------------------------------------------
def matches_allowlist(rel_path: str) -> bool:
    rel_norm = rel_path.replace("\\", "/")
    return any(fnmatch.fnmatch(rel_norm, pat) for pat in PATH_ALLOWLIST)


def lint_file(path: Path, root: Path) -> list[Violation]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    violations: list[Violation] = []
    lines = text.split("\n")

    for idx, line in enumerate(lines):
        match = SQL_TENANT_PATTERN.search(line)
        if not match:
            continue
        if ALLOW_INLINE in line:
            continue
        if DDL_PATTERN.search(line):
            continue

        # Look at ±WINDOW lines for enterprise_id (Python f-strings, multi-
        # line triple quotes, Java string concatenation all stay within
        # a small line distance of their predicate).
        start = max(0, idx - WINDOW)
        end = min(len(lines), idx + WINDOW + 1)
        window_text = "\n".join(lines[start:end])
        if ENTERPRISE_ID_PATTERN.search(window_text):
            continue

        violations.append(
            Violation(
                path=path,
                line_number=idx + 1,
                table=match.group(1).lower(),
                line=line,
            )
        )

    return violations


def iter_source_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for pat in ("services/**/*.py", "services/**/*.java"):
        for p in root.glob(pat):
            if not p.is_file():
                continue
            rel = str(p.relative_to(root))
            if matches_allowlist(rel):
                continue
            out.append(p)
    out.sort()
    return out


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repository root to scan (defaults to the parent of this script).",
    )
    ap.add_argument(
        "--quiet",
        action="store_true",
        help="Only print output when a violation is found.",
    )
    args = ap.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        print(f"error: --root {root} is not a directory", file=sys.stderr)
        return 1

    files = iter_source_files(root)
    if not args.quiet:
        print(f"check-tenant-filter: scanning {len(files)} file(s) under {root}")

    violations: list[Violation] = []
    for path in files:
        violations.extend(lint_file(path, root))

    if violations:
        print(
            f"\n[FAIL] tenant-filter lint found {len(violations)} suspect SQL "
            f"reference(s) on tenant-scoped tables without an enterprise_id filter:\n"
        )
        for v in violations:
            print(v.render(root))
        print(
            "\nFix options:\n"
            "  1. Add `WHERE enterprise_id = ...` (or `enterpriseId` for JPA) to the query.\n"
            "  2. If the cross-tenant access is intentional, add the inline comment\n"
            "     `# tenant-filter-lint: allow` (Python) or `// tenant-filter-lint: allow`\n"
            "     (Java) on the SAME line, with a brief justification on the line above.\n"
            "  3. If the file is a platform-admin / cron path, extend PATH_ALLOWLIST in\n"
            "     scripts/check-tenant-filter.py.\n"
        )
        return 1

    if not args.quiet:
        print("[PASS] every tenant-table access in scanned sources filters by enterprise_id.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
