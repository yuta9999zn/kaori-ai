"""
Stage 1: Ingest any messy Excel/CSV file.

What this does:
  1. Opens the file as-is (no assumptions about structure)
  2. Detects header row per sheet
  3. Writes ALL raw rows to Bronze (nothing is dropped)
  4. Tries to detect column meanings with confidence scores
  5. Produces a mapping report — JSON file + printed summary

What it does NOT do:
  - Write Silver (that's apply_mappings.py)
  - Drop or ignore unknown columns
  - Fail silently

Usage:
  python etl/ingest.py Daily_revenue.xlsx
  python etl/ingest.py data/ --pattern "*.xlsx"
  python etl/ingest.py report.xlsx --show-samples   # print sample values

After running:
  → config/mappings/<filename>_mapping.json is created
  → If all columns are HIGH confidence: run apply_mappings.py to write Silver
  → If any column is MEDIUM/LOW/UNKNOWN: review the JSON, fill in user_override,
    then run apply_mappings.py
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

import pandas as pd
from utils.db import execute_values, get_cursor
from utils.logger import log, log_etl_run
from utils.excel_parser import iter_sheets, ColumnMatch

# ---------------------------------------------------------------------------
# Universal column spec — covers all tables (revenue, customers, bank, etc.)
# Each ETL loader can pass a narrower spec; ingest uses the full spec.
# ---------------------------------------------------------------------------

UNIVERSAL_COL_SPEC = {
    "date": [
        "date", "ngay", "ngày", "日付", "日", "time", "thoi gian", "thời gian",
        "ngay thang", "ngày tháng", "transaction date", "ngay gd", "ngay giao dich",
        "ngay kham", "ngày khám", "visit date", "ngay tao", "ngay lap",
    ],
    "amount": [
        "amount", "total", "revenue", "doanh thu", "tien", "tiền",
        "so tien", "số tiền", "tong thu", "tổng thu", "gia tri", "giá trị",
        "thanh toan", "thanh toán", "売上", "金額", "income", "thu nhap",
        "tong doanh thu", "tổng doanh thu",
    ],
    "cash": [
        "cash", "tien mat", "tiền mặt", "mat", "mặt",
        "tien mat thuc thu", "tiền mặt thực thu",
    ],
    "transfer": [
        "transfer", "chuyen khoan", "chuyển khoản", "ck", "banking",
        "chuyen khoan thuc thu",
    ],
    "card": [
        "card", "the", "thẻ", "visa", "mastercard", "credit", "debit",
    ],
    "store": [
        "store", "branch", "cua hang", "cửa hàng", "chi nhanh", "chi nhánh",
        "location", "ten chi nhanh", "tên chi nhánh",
    ],
    "customer_count": [
        "customer count", "customer", "khach", "khách", "so khach", "số khách",
        "luot khach", "lượt khách", "count", "qty",
    ],
    "name": [
        "name", "customer name", "ten khach", "tên khách", "khach hang",
        "khách hàng", "ho ten", "họ tên", "ten", "tên",
    ],
    "phone": [
        "phone", "so dien thoai", "số điện thoại", "sdt", "dien thoai",
        "điện thoại", "mobile", "tel",
    ],
    "service": [
        "service", "dich vu", "dịch vụ", "product", "san pham", "item",
    ],
    "body_area": [
        "body area", "vung", "vùng", "vung dieu tri", "vùng điều trị",
        "area", "khu vuc",
    ],
    "staff": [
        "staff", "nhan vien", "nhân viên", "ky thuat vien", "kỹ thuật viên",
        "cast", "employee", "nv",
    ],
    "description": [
        "description", "noi dung", "nội dung", "mo ta", "mô tả",
        "dien giai", "diễn giải", "ghi chu", "note",
    ],
    "ref": [
        "reference", "ref", "so tham chieu", "số tham chiếu",
        "ma gd", "mã gd", "transaction id",
    ],
}

MAPPINGS_DIR = Path(__file__).parent.parent / "config" / "mappings"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ColumnReport:
    raw_name: str
    canonical: str | None          # auto-detected
    confidence: str                # HIGH | MEDIUM | LOW | UNKNOWN
    sample_values: list[str]
    reason: str
    user_override: str | None = None   # filled in by user after review


@dataclass
class SheetReport:
    sheet_name: str
    status: str                    # ok | needs_review | skipped
    skip_reason: str | None
    header_row: int | None         # 0-based
    row_count: int
    columns: list[ColumnReport] = field(default_factory=list)

    @property
    def needs_review(self) -> bool:
        return any(c.confidence in ("MEDIUM", "LOW", "UNKNOWN")
                   and c.user_override is None
                   for c in self.columns)

    @property
    def effective_mapping(self) -> dict[str, str]:
        """canonical → raw_name, applying user_override where set."""
        result = {}
        for c in self.columns:
            effective = c.user_override or c.canonical
            if effective:
                result[effective] = c.raw_name
        return result


@dataclass
class IngestReport:
    filepath: str
    ingested_at: str
    sheets: list[SheetReport] = field(default_factory=list)

    @property
    def needs_review(self) -> bool:
        return any(s.needs_review for s in self.sheets if s.status != "skipped")

    @property
    def mapping_path(self) -> Path:
        stem = Path(self.filepath).stem
        return MAPPINGS_DIR / f"{stem}_mapping.json"


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _report_to_dict(report: IngestReport) -> dict:
    return {
        "file": report.filepath,
        "ingested_at": report.ingested_at,
        "needs_review": report.needs_review,
        "sheets": [
            {
                "sheet_name": s.sheet_name,
                "status": s.status,
                "skip_reason": s.skip_reason,
                "header_row": s.header_row,
                "row_count": s.row_count,
                "needs_review": s.needs_review,
                "columns": [
                    {
                        "raw_name": c.raw_name,
                        "canonical": c.canonical,
                        "confidence": c.confidence,
                        "sample_values": c.sample_values,
                        "reason": c.reason,
                        "user_override": c.user_override,
                    }
                    for c in s.columns
                ],
            }
            for s in report.sheets
        ],
    }


def load_mapping_file(path: Path) -> IngestReport:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    report = IngestReport(filepath=data["file"], ingested_at=data["ingested_at"])
    for s in data["sheets"]:
        sheet = SheetReport(
            sheet_name=s["sheet_name"],
            status=s["status"],
            skip_reason=s.get("skip_reason"),
            header_row=s.get("header_row"),
            row_count=s["row_count"],
        )
        for c in s["columns"]:
            sheet.columns.append(ColumnReport(
                raw_name=c["raw_name"],
                canonical=c.get("canonical"),
                confidence=c["confidence"],
                sample_values=c.get("sample_values", []),
                reason=c.get("reason", ""),
                user_override=c.get("user_override"),
            ))
        report.sheets.append(sheet)
    return report


# ---------------------------------------------------------------------------
# Bronze writers — one per table type
# ---------------------------------------------------------------------------

def _write_bronze_generic(source_file: str, sheet_name: str,
                           df: pd.DataFrame, col_map: dict[str, str]):
    """
    Write raw rows to bronze_daily_revenue (revenue-type sheets) or a
    generic fallback.  col_map = {canonical → actual_col_in_df}.
    """
    def _get(row, canonical: str, default="") -> str:
        col = col_map.get(canonical)
        return str(row[col]) if col and col in row.index else default

    rows = []
    for _, row in df.iterrows():
        rows.append((
            source_file,
            _get(row, "store", sheet_name),
            _get(row, "date"),
            _get(row, "cash", _get(row, "amount")),   # use amount as cash fallback
            _get(row, "transfer"),
            _get(row, "card"),
            _get(row, "customer_count"),
            "",   # notes_raw
        ))

    if rows:
        execute_values("""
            INSERT INTO bronze_daily_revenue
                (source_file, store_raw, date_raw, cash_raw, transfer_raw,
                 card_raw, customer_count_raw, notes_raw)
            VALUES %s
        """, rows)
        log.info(f"  Bronze: {len(rows)} rows written (sheet='{sheet_name}')")


def _write_bronze_customers(source_file: str, sheet_name: str,
                             df: pd.DataFrame, col_map: dict[str, str]):
    def _get(row, canonical: str) -> str:
        col = col_map.get(canonical)
        return str(row[col]) if col and col in row.index else ""

    rows = [
        (
            source_file,
            _get(row, "name"),
            _get(row, "phone"),
            _get(row, "date"),
            _get(row, "service"),
            _get(row, "body_area"),
            _get(row, "amount"),
            _get(row, "staff"),
        )
        for _, row in df.iterrows()
    ]
    if rows:
        execute_values("""
            INSERT INTO bronze_nb_customer_sessions
                (source_file, customer_name_raw, phone_raw, visit_date_raw,
                 service_raw, body_area_raw, amount_raw, staff_raw)
            VALUES %s
        """, rows)
        log.info(f"  Bronze customers: {len(rows)} rows written (sheet='{sheet_name}')")


def _write_bronze_inventory(source_file: str, sheet_name: str,
                            df: pd.DataFrame, col_map: dict[str, str]):
    """Write pivoted inventory rows to bronze_inventory_raw."""
    def _get(row, canonical: str) -> str:
        col = col_map.get(canonical)
        return str(row[col]).strip() if col and col in row.index else ""

    rows = [
        (
            source_file,
            sheet_name,
            _get(row, "date") or str(row.iloc[0]),   # raw day value
            _get(row, "product"),
            _get(row, "inventory"),
            _get(row, "usage"),
            _get(row, "remaining"),
            _get(row, "quantity"),
            _get(row, "amount"),
        )
        for _, row in df.iterrows()
    ]
    if rows:
        execute_values("""
            INSERT INTO bronze_inventory_raw
                (source_file, sheet_name_raw, date_raw, product_name,
                 inventory_raw, usage_raw, remaining_raw, quantity_raw, amount_raw)
            VALUES %s
        """, rows)
        log.info(f"  Bronze inventory: {len(rows)} rows written (sheet='{sheet_name}')")
                       df: pd.DataFrame, col_map: dict[str, str]):
    def _get(row, canonical: str) -> str:
        col = col_map.get(canonical)
        return str(row[col]) if col and col in row.index else ""

    rows = [
        (
            source_file,
            _get(row, "date"),
            _get(row, "amount"),
            "",                          # direction_raw — determined by classify_bank
            _get(row, "description"),
            "",                          # balance_raw
            _get(row, "ref"),
        )
        for _, row in df.iterrows()
    ]
    if rows:
        execute_values("""
            INSERT INTO bronze_bank_transactions
                (source_file, txn_date_raw, amount_raw, direction_raw,
                 description_raw, balance_raw, ref_raw)
            VALUES %s
        """, rows)
        log.info(f"  Bronze bank: {len(rows)} rows written (sheet='{sheet_name}')")


# ---------------------------------------------------------------------------
# Ingest one file
# ---------------------------------------------------------------------------

def ingest_file(filepath: str, show_samples: bool = False) -> IngestReport:
    """
    Stage 1: Extract raw data to Bronze + produce mapping report.
    Never fails silently. Returns IngestReport regardless of data quality.
    """
    source = Path(filepath).name
    report = IngestReport(
        filepath=filepath,
        ingested_at=datetime.now().isoformat(timespec="seconds"),
    )

    log.info(f"\n{'='*60}")
    log.info(f"  INGESTING: {source}")
    log.info(f"{'='*60}")

    total_rows = 0

    for sheet_name, df, col_matches, header_row, pivot_info in iter_sheets(
        filepath, UNIVERSAL_COL_SPEC, logger=log
    ):
        col_map = {}
        col_reports = []

        for match in col_matches:
            effective = match.canonical
            col_reports.append(ColumnReport(
                raw_name=match.raw_name,
                canonical=match.canonical,
                confidence=match.confidence,
                sample_values=match.sample_values,
                reason=match.reason,
            ))
            if effective:
                col_map[effective] = match.raw_name

        sheet_report = SheetReport(
            sheet_name=sheet_name,
            status="ok" if not any(
                c.confidence in ("UNKNOWN", "LOW") for c in col_reports
            ) else "needs_review",
            skip_reason=None,
            header_row=header_row,
            row_count=len(df),
            columns=col_reports,
        )
        report.sheets.append(sheet_report)

        # Route Bronze write: pivoted inventory → bronze_inventory_raw
        #                     everything else  → bronze_daily_revenue
        if pivot_info is not None:
            _write_bronze_inventory(source, sheet_name, df, col_map)
        else:
            _write_bronze_generic(source, sheet_name, df, col_map)
        total_rows += len(df)

        log_etl_run("ingest", source, len(df), len(df), 0)

    if not report.sheets:
        log.warning(f"  No usable sheets found in {source}")

    log.info(f"\n  Total Bronze rows written: {total_rows}")
    return report


# ---------------------------------------------------------------------------
# Print report
# ---------------------------------------------------------------------------

CONF_ICON = {"HIGH": "✓", "MEDIUM": "?", "LOW": "?", "UNKNOWN": "✗"}
CONF_LABEL = {
    "HIGH":    "HIGH    — safe to use",
    "MEDIUM":  "MEDIUM  — review recommended",
    "LOW":     "LOW     — review required",
    "UNKNOWN": "UNKNOWN — user must define",
}


def print_report(report: IngestReport, show_samples: bool = False):
    print(f"\n{'='*65}")
    print(f"  INGEST REPORT: {Path(report.filepath).name}")
    print(f"  Generated: {report.ingested_at}")
    print(f"{'='*65}")

    for s in report.sheets:
        if s.status == "skipped":
            print(f"\n  [SKIP] Sheet '{s.sheet_name}': {s.skip_reason}")
            continue

        status_icon = "✓" if not s.needs_review else "!"
        print(f"\n  [{status_icon}] Sheet '{s.sheet_name}'  "
              f"({s.row_count} rows, header row {(s.header_row or 0) + 1})")

        for c in s.columns:
            icon = CONF_ICON.get(c.confidence, "?")
            override_note = f"  [user: {c.user_override}]" if c.user_override else ""
            canonical_str = c.user_override or c.canonical or "???"
            samples = f"  e.g. {c.sample_values[:2]}" if show_samples and c.sample_values else ""
            print(f"    {icon}  {c.raw_name:<30} → {canonical_str:<18} "
                  f"[{c.confidence}]{override_note}{samples}")

        if s.needs_review:
            unknown_cols = [c.raw_name for c in s.columns
                            if c.confidence in ("UNKNOWN", "LOW") and not c.user_override]
            print(f"\n    ⚠  Columns needing definition: {unknown_cols}")

    print(f"\n{'='*65}")

    if report.needs_review:
        print(f"  STATUS: ⚠  NEEDS REVIEW")
        print(f"\n  Mapping file written to:")
        print(f"    {report.mapping_path}")
        print(f"\n  Steps:")
        print(f"    1. Open the mapping file and fill in 'user_override' for")
        print(f"       any column showing UNKNOWN or LOW confidence.")
        print(f"       Valid values: date | amount | cash | transfer | card |")
        print(f"                     store | customer_count | name | phone |")
        print(f"                     service | body_area | staff | skip")
        print(f"    2. Re-run:")
        print(f"       python etl/apply_mappings.py {report.mapping_path}")
    else:
        print(f"  STATUS: ✓  ALL COLUMNS IDENTIFIED")
        print(f"\n  Run to write Silver layer:")
        print(f"    python etl/apply_mappings.py {report.mapping_path}")
    print()


# ---------------------------------------------------------------------------
# Save mapping file
# ---------------------------------------------------------------------------

def save_mapping(report: IngestReport):
    MAPPINGS_DIR.mkdir(parents=True, exist_ok=True)
    path = report.mapping_path
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_report_to_dict(report), f, ensure_ascii=False, indent=2)
    log.info(f"  Mapping file: {path}")
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Ingest any Excel/CSV file → Bronze + mapping report"
    )
    parser.add_argument("target", help="File or directory to ingest")
    parser.add_argument("--pattern", default="*.xlsx",
                        help="Glob pattern when target is a directory (default: *.xlsx)")
    parser.add_argument("--show-samples", action="store_true",
                        help="Print sample column values in report")
    args = parser.parse_args()

    target = Path(args.target)

    if target.is_dir():
        files = list(target.glob(f"**/{args.pattern}"))
        if not files:
            log.warning(f"No files matching '{args.pattern}' in {target}")
            return
    elif target.is_file():
        files = [target]
    else:
        log.error(f"Not found: {target}")
        sys.exit(1)

    for filepath in sorted(files):
        report = ingest_file(str(filepath), show_samples=args.show_samples)
        save_mapping(report)
        print_report(report, show_samples=args.show_samples)


if __name__ == "__main__":
    main()
