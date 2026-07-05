"""
Master ETL runner — two-stage pipeline.

STAGE 1 — Ingest (Bronze + mapping report):
  python etl/ingest.py <file_or_dir>
  → Reads any Excel/CSV file as-is
  → Writes ALL raw rows to Bronze (never drops data)
  → Generates config/mappings/<file>_mapping.json with column detection report
  → Prints what was understood and what needs human review

STAGE 2 — Apply mappings (Silver):
  python etl/apply_mappings.py config/mappings/<file>_mapping.json
  → Reads confirmed mappings (user fills in 'user_override' for unknown columns)
  → Writes clean data to Silver tables
  → Gold views update automatically

This script (load_all.py) runs BOTH stages for files that are already known
and have confirmed mappings. Use it for re-loading after data updates.

Usage:
  python etl/load_all.py                          # uses dirs from .env
  python etl/load_all.py --nb-dir /path           # override NB dir
  python etl/load_all.py --rj-dir /path           # override RJ dir
  python etl/load_all.py --skip-rj                # skip RJ (data not ready)
  python etl/load_all.py --ingest-only            # run Stage 1 only
"""

import sys
import os
import argparse
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from utils.logger import log
from etl.ingest import ingest_file, save_mapping, print_report, MAPPINGS_DIR


def run_stage1(label: str, filepath: str, show_samples: bool = False) -> bool:
    log.info(f"\n{'='*50}\n  INGEST: {label}\n{'='*50}")
    try:
        report = ingest_file(filepath, show_samples=show_samples)
        save_mapping(report)
        print_report(report, show_samples=show_samples)
        return not report.needs_review
    except Exception:
        log.error(f"  FAILED: {label}\n{traceback.format_exc()}")
        return False


def run_stage2(label: str, mapping_path: Path, force: bool = False) -> bool:
    from etl.apply_mappings import apply_mappings
    log.info(f"\n{'='*50}\n  APPLY MAPPINGS: {label}\n{'='*50}")
    try:
        apply_mappings(mapping_path, force=force)
        return True
    except SystemExit:
        log.warning(f"  Needs review: {mapping_path}")
        return False
    except Exception:
        log.error(f"  FAILED: {label}\n{traceback.format_exc()}")
        return False


def collect_files(data_dir: str, patterns: list[str]) -> list[Path]:
    files = []
    for pattern in patterns:
        files.extend(Path(data_dir).glob(f"**/{pattern}"))
    return sorted(set(files))


def main():
    parser = argparse.ArgumentParser(description="Run Kaori full ETL pipeline")
    parser.add_argument("--nb-dir",     help="NB data dir (overrides NB_DATA_DIR in .env)")
    parser.add_argument("--rj-dir",     help="RJ data dir (overrides RJ_DATA_DIR in .env)")
    parser.add_argument("--skip-rj",    action="store_true")
    parser.add_argument("--ingest-only", action="store_true",
                        help="Only run Stage 1 (Bronze + mapping report), skip Stage 2")
    parser.add_argument("--force",      action="store_true",
                        help="Apply mappings even if some columns are unreviewed")
    parser.add_argument("--show-samples", action="store_true")
    args = parser.parse_args()

    nb_dir = args.nb_dir or os.getenv("NB_DATA_DIR", ".")
    rj_dir = args.rj_dir or os.getenv("RJ_DATA_DIR", ".")

    start = datetime.now()
    log.info(f"Kaori ETL started at {start.strftime('%Y-%m-%d %H:%M:%S')}")

    nb_patterns = [
        "Daily_*.xlsx", "daily_*.xlsx", "*doanh_thu*.xlsx",
        "*customer*.xlsx", "*khach*.xlsx", "*NB_*lich_su*.xlsx",
        "*management_report*.xlsx", "*bao_cao*.xlsx", "*P&L*.xlsx",
        "Shift_*.xlsm", "Shift_*.xlsx", "*ca_lam*.xlsx",
    ]
    rj_patterns = ["*RJ*.xlsx", "*rj*.xlsx", "*bar*.xlsx"]

    nb_files = collect_files(nb_dir, nb_patterns)
    rj_files = [] if args.skip_rj else collect_files(rj_dir, rj_patterns)
    all_files = nb_files + rj_files

    if not all_files:
        log.warning(f"No Excel files found in {nb_dir} (and {rj_dir})")
        return

    log.info(f"Found {len(all_files)} file(s) to process")

    stage1_results = {}
    stage2_results = {}

    # --- Stage 1: Ingest all files to Bronze ---
    for filepath in all_files:
        label = filepath.name
        ok = run_stage1(label, str(filepath), show_samples=args.show_samples)
        stage1_results[label] = ok

    if args.ingest_only:
        log.info("\nStage 1 complete. Review mapping files before running Stage 2.")
        _print_summary(stage1_results, {})
        return

    # --- Stage 2: Apply confirmed mappings ---
    for filepath in all_files:
        label = filepath.name
        stem = Path(filepath).stem
        mapping_path = MAPPINGS_DIR / f"{stem}_mapping.json"

        if not mapping_path.exists():
            log.warning(f"  No mapping file for {label} — run ingest.py first")
            stage2_results[label] = False
            continue

        ok = run_stage2(label, mapping_path, force=args.force)
        stage2_results[label] = ok

    elapsed = (datetime.now() - start).total_seconds()
    log.info(f"\nTotal time: {elapsed:.1f}s")
    _print_summary(stage1_results, stage2_results)


def _print_summary(stage1: dict, stage2: dict):
    all_keys = set(stage1) | set(stage2)
    log.info(f"\n{'='*50}\n  SUMMARY\n{'='*50}")
    for key in sorted(all_keys):
        s1 = "OK" if stage1.get(key) else ("REVIEW" if key in stage1 else "—")
        s2 = "OK" if stage2.get(key) else ("FAILED" if key in stage2 else "—")
        log.info(f"  {key:<40} Stage1={s1:<8} Stage2={s2}")

    needs_review = [k for k, v in stage1.items() if not v]
    if needs_review:
        log.info(f"\n  Files needing mapping review ({len(needs_review)}):")
        for f in needs_review:
            log.info(f"    config/mappings/{Path(f).stem}_mapping.json")
        log.info(f"\n  After editing, re-run Stage 2:")
        log.info(f"    python etl/apply_mappings.py config/mappings/<file>_mapping.json")


if __name__ == "__main__":
    main()

