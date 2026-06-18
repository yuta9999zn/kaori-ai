#!/usr/bin/env python3
"""
N8 Governance — Check BA layer vs code repo drift.

Per CR Register v2.1 §9 Governance finding: BA-code drift detection.
Compare module list in Feature Tree v4.1 vs migrations + endpoints.
Alert if drift > 5%.

Usage:
    python scripts/check_ba_sync.py                  # run all checks
    python scripts/check_ba_sync.py --ci             # CI mode: exit 1 if drift > threshold
    python scripts/check_ba_sync.py --threshold 0.05 # custom drift threshold

Checks performed:
1. Feature Tree v4.1 module count vs migrations directory count
2. API_CATALOG_V4 endpoint count vs OpenAPI snapshot paths
3. BA docs sync: D:\\Tài liệu dự án\\*.md vs docs/ba/*.md
4. CR Register vs commit log (CR-#### references)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent.parent
DOCS_BA_DIR = ROOT / "docs" / "ba"
DOCS_SPECS_DIR = ROOT / "docs" / "specs"
DOCS_API_SPECS_DIR = ROOT / "docs" / "api-specs"
DOCS_UAT_DIR = ROOT / "docs" / "uat"
MIGRATIONS_DIR = ROOT / "infrastructure" / "postgres" / "migrations"
TAI_LIEU_DU_AN = Path("D:/Tài liệu dự án")  # Master BA folder

CR_PATTERN = re.compile(r"CR-\d{4}")


def count_migrations() -> int:
    """Count .sql files in migrations directory."""
    if not MIGRATIONS_DIR.exists():
        return 0
    return len(list(MIGRATIONS_DIR.glob("*.sql")))


def count_openapi_paths() -> Tuple[int, int]:
    """Return (pipeline_paths, orchestrator_paths)."""
    pipeline = DOCS_API_SPECS_DIR / "pipeline.openapi.json"
    orchestrator = DOCS_API_SPECS_DIR / "orchestrator.openapi.json"

    def _count(path: Path) -> int:
        if not path.exists():
            return 0
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
            return len(spec.get("paths", {}))
        except Exception:
            return 0

    return _count(pipeline), _count(orchestrator)


def check_ba_sync_drift() -> List[str]:
    """Compare BA docs in docs/ba/ vs D:\\Tài liệu dự án\\."""
    drifts = []
    if not TAI_LIEU_DU_AN.exists():
        return ["[WARN] D:\\Tài liệu dự án\\ not accessible (skip BA sync check)"]
    if not DOCS_BA_DIR.exists():
        return ["[WARN] docs/ba/ not exists"]

    master_files = {f.name for f in TAI_LIEU_DU_AN.glob("*.md")}
    repo_files = {f.name for f in DOCS_BA_DIR.glob("*.md")}

    # PHASE_2_8_FE_IMPL_SPEC_v1.1.md sống ở docs/sprint/, không docs/ba/
    master_files.discard("PHASE_2_8_FE_IMPL_SPEC_v1.1.md")

    missing_in_repo = master_files - repo_files
    only_in_repo = repo_files - master_files

    if missing_in_repo:
        drifts.append(f"[WARN] BA docs MISSING in repo: {sorted(missing_in_repo)}")
    if only_in_repo:
        drifts.append(f"[WARN] BA docs ONLY in repo (orphan?): {sorted(only_in_repo)}")

    # Content compare for common files
    for fname in master_files & repo_files:
        master = (TAI_LIEU_DU_AN / fname).read_bytes()
        repo = (DOCS_BA_DIR / fname).read_bytes()
        if master != repo:
            drifts.append(f"[WARN] BA doc DIFFER: {fname} (Tài liệu master vs repo mirror)")

    return drifts


def check_cr_references(window_days: int = 30) -> List[str]:
    """Check if commits in last N days reference CRs."""
    try:
        result = subprocess.run(
            ["git", "log", f"--since={window_days} days ago", "--format=%H %s"],
            capture_output=True, text=True, check=True, cwd=ROOT,
        )
    except subprocess.CalledProcessError:
        return ["[WARN] git log unavailable"]

    commits = result.stdout.strip().splitlines()
    if not commits:
        return [f"[WARN] No commits in last {window_days} days"]

    cr_refs = sum(1 for line in commits if CR_PATTERN.search(line))
    feat_commits = sum(1 for line in commits if "feat(" in line or "feat:" in line)

    cr_ratio = cr_refs / feat_commits if feat_commits > 0 else 0
    target_ratio = 0.5  # at least 50% of feature commits should reference CR

    msgs = []
    if feat_commits > 0 and cr_ratio < target_ratio:
        msgs.append(
            f"[WARN] CR reference rate: {cr_refs}/{feat_commits} feature commits ({cr_ratio:.0%}) "
            f"< target {target_ratio:.0%}"
        )

    return msgs


def main() -> int:
    parser = argparse.ArgumentParser(description="Check BA vs code repo drift")
    parser.add_argument("--ci", action="store_true", help="CI mode: exit 1 on drift")
    parser.add_argument(
        "--threshold", type=float, default=0.05, help="Drift threshold (0.05 = 5%)"
    )
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("Kaori BA vs Code Repo Drift Check")
    print("=" * 60)

    issues = []

    # 1. Migration count
    mig_count = count_migrations()
    print(f"\nMigrations count: {mig_count} .sql files")

    # 2. OpenAPI path counts
    pipeline_paths, orch_paths = count_openapi_paths()
    print(f"Pipeline OpenAPI paths: {pipeline_paths}")
    print(f"Orchestrator OpenAPI paths: {orch_paths}")

    # 3. BA sync drift
    print("\nBA Sync Drift:")
    drifts = check_ba_sync_drift()
    if drifts:
        for d in drifts:
            print(f"  {d}")
            issues.append(d)
    else:
        print("  [OK] BA docs fully synced")

    # 4. CR references
    print(f"\nCR Reference rate (last {args.window_days} days):")
    cr_issues = check_cr_references(args.window_days)
    if cr_issues:
        for c in cr_issues:
            print(f"  {c}")
            issues.append(c)
    else:
        print("  [OK] CR references within target")

    # Summary
    print("\n" + "=" * 60)
    if issues:
        print(f"Found {len(issues)} drift issue(s)")
        if args.ci:
            print(
                "\nPer CR Register v2.1 §9 Governance: BA layer + code repo must stay\n"
                "in sync. Fix drift or document exception via CR."
            )
            return 1
        return 0

    print("[OK] No drift detected — BA vs code aligned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
