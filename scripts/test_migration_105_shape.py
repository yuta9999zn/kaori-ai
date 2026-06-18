"""Shape tests for migration 105 — admin_bypass_enterprises RLS drift fix."""
from __future__ import annotations

import re
from pathlib import Path

REPO    = Path(__file__).resolve().parent.parent
MIG_DIR = REPO / "infrastructure" / "postgres" / "migrations"
MIG_105 = (MIG_DIR / "105_admin_bypass_enterprises.sql").read_text(encoding="utf-8")


def _strip(sql: str) -> str:
    out, in_block = [], False
    for line in sql.splitlines():
        if in_block:
            end = line.find("*/")
            if end == -1:
                continue
            line = line[end + 2:]
            in_block = False
        while True:
            start = line.find("/*")
            if start == -1:
                break
            end = line.find("*/", start + 2)
            if end == -1:
                line = line[:start]
                in_block = True
                break
            line = line[:start] + line[end + 2:]
        out.append(line.split("--", 1)[0])
    return "\n".join(out)


M = _strip(MIG_105)


def test_creates_admin_bypass_enterprises_policy():
    assert re.search(
        r"CREATE\s+POLICY\s+admin_bypass_enterprises\s+ON\s+enterprises",
        M, re.IGNORECASE,
    )


def test_policy_uses_is_admin_guc():
    """Mirror mig 025 pattern: USING (current_setting('app.is_admin', true) = 'true')."""
    assert re.search(
        r"current_setting\(\s*'app\.is_admin'\s*,\s*true\s*\)\s*=\s*'true'",
        M,
    )


def test_policy_has_both_using_and_with_check():
    """Without WITH CHECK, INSERT/UPDATE still gets blocked even when USING permits
    (Postgres falls back to USING for WITH CHECK only when no WITH CHECK clause was
    given, but mig 025 pattern is USING-only — we add WITH CHECK explicitly here
    because the bug surfaced on INSERT path)."""
    assert re.search(r"\bUSING\s*\(", M, re.IGNORECASE)
    assert re.search(r"\bWITH\s+CHECK\s*\(", M, re.IGNORECASE)


def test_idempotent_guard():
    """Re-running the migration must not error if the policy already exists."""
    assert re.search(r"IF NOT EXISTS", M, re.IGNORECASE)
    assert re.search(r"FROM pg_policies", M, re.IGNORECASE)


def test_wrapped_in_begin_commit():
    assert re.search(r"\bBEGIN\s*;", M)
    assert re.search(r"\bCOMMIT\s*;", M)
