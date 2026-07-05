"""
Bronze → Silver ETL: LPBank Statement Classifier

Reads LPBank CSV/Excel export → classifies each transaction by description →
writes to bronze_bank_transactions and silver_bank_transactions.

Classification is rule-based using config/bank_rules.json.
Unmatched rows are marked 'OTHER' and flagged for manual review.

Usage:
  python etl/classify_bank.py statement.csv
  python etl/classify_bank.py statement.xlsx
  python etl/classify_bank.py --dir /path/to/statements/
  python etl/classify_bank.py --review          # show all OTHER rows
  python etl/classify_bank.py --override 123 PAYROLL  # manually fix one row
"""

import os
import sys
import json
import re
import argparse
import unicodedata
from pathlib import Path
import pandas as pd
from utils.db import get_cursor, execute_values
from utils.logger import log, log_etl_run

SCRIPT = "classify_bank"
RULES_FILE = Path(__file__).parent.parent / "config" / "bank_rules.json"

# Expected columns in LPBank export (try several formats)
DATE_COLS = ["ngay giao dich", "ngày giao dịch", "transaction date", "date", "ngay", "ngày"]
AMOUNT_COLS = ["so tien", "số tiền", "amount", "credit", "debit", "phat sinh"]
DESC_COLS = ["noi dung", "nội dung", "description", "mo ta", "mô tả", "dien giai", "diễn giải"]
DIR_COLS = ["loai", "loại", "type", "direction", "ps co", "ps no"]
REF_COLS = ["so tham chieu", "số tham chiếu", "reference", "ref", "ma gd", "mã gd"]
BALANCE_COLS = ["so du", "số dư", "balance", "du cuoi", "dư cuối"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_rules() -> dict[str, list[str]]:
    with open(RULES_FILE, encoding="utf-8") as f:
        return json.load(f)


def normalize_text(text: str) -> str:
    """Lowercase, remove Vietnamese diacritics, collapse whitespace."""
    text = str(text).lower().strip()
    # Remove diacritics
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"\s+", " ", text)
    return text


def classify(description: str, rules: dict[str, list[str]]) -> str:
    norm = normalize_text(description)
    for category, keywords in rules.items():
        for kw in keywords:
            if normalize_text(kw) in norm:
                return category
    return "OTHER"


def find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Find first matching column name (case-insensitive, diacritic-stripped)."""
    normalized_cols = {normalize_text(c): c for c in df.columns}
    for candidate in candidates:
        key = normalize_text(candidate)
        if key in normalized_cols:
            return normalized_cols[key]
    return None


def infer_direction(row: pd.Series, amount_col: str, dir_col: str | None) -> str:
    """Return 'IN' or 'OUT'."""
    if dir_col and dir_col in row:
        raw = normalize_text(str(row[dir_col]))
        if any(k in raw for k in ["co", "credit", "in", "ps co"]):
            return "IN"
        if any(k in raw for k in ["no", "debit", "out", "ps no"]):
            return "OUT"

    # Fallback: positive = IN, negative = OUT
    try:
        val = float(str(row[amount_col]).replace(",", "").replace(".", "").strip())
        return "IN" if val >= 0 else "OUT"
    except ValueError:
        return "IN"


def parse_amount(val) -> int:
    if pd.isna(val) or str(val).strip() in ("", "-"):
        return 0
    cleaned = re.sub(r"[^\d]", "", str(val))
    try:
        return int(cleaned)
    except ValueError:
        return 0


# ---------------------------------------------------------------------------
# Load one file
# ---------------------------------------------------------------------------

def load_file(filepath: str) -> tuple[int, int, int]:
    source = Path(filepath).name
    log.info(f"Classifying: {filepath}")

    rules = load_rules()

    # Read file
    try:
        if filepath.endswith(".csv"):
            # Try common encodings for Vietnamese bank exports
            for enc in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
                try:
                    df = pd.read_csv(filepath, dtype=str, encoding=enc, sep=None, engine="python")
                    break
                except Exception:
                    continue
            else:
                raise ValueError("Could not decode CSV with any known encoding")
        else:
            df = pd.read_excel(filepath, dtype=str)
    except Exception as e:
        log.error(f"Cannot open {filepath}: {e}")
        log_etl_run(SCRIPT, source, 0, 0, 0, "ERROR", str(e))
        return 0, 0, 0

    df = df.dropna(how="all")
    rows_read = len(df)
    log.info(f"  {rows_read} rows, columns: {list(df.columns)}")

    # Identify key columns
    date_col = find_col(df, DATE_COLS)
    amount_col = find_col(df, AMOUNT_COLS)
    desc_col = find_col(df, DESC_COLS)
    dir_col = find_col(df, DIR_COLS)
    ref_col = find_col(df, REF_COLS)
    bal_col = find_col(df, BALANCE_COLS)

    if not date_col:
        log.error(f"  No date column found. Columns: {list(df.columns)}")
        log_etl_run(SCRIPT, source, rows_read, 0, rows_read, "ERROR", "No date column")
        return rows_read, 0, rows_read

    if not amount_col:
        log.error(f"  No amount column found.")
        log_etl_run(SCRIPT, source, rows_read, 0, rows_read, "ERROR", "No amount column")
        return rows_read, 0, rows_read

    log.info(f"  Mapped: date={date_col}, amount={amount_col}, "
             f"desc={desc_col}, dir={dir_col}")

    # --- Bronze: store raw rows ---
    bronze_sql = """
        INSERT INTO bronze_bank_transactions
            (source_file, txn_date_raw, amount_raw, direction_raw,
             description_raw, balance_raw, ref_raw)
        VALUES %s
    """
    execute_values(bronze_sql, [
        (
            source,
            str(row.get(date_col, "")),
            str(row.get(amount_col, "")),
            str(row.get(dir_col, "")) if dir_col else "",
            str(row.get(desc_col, "")) if desc_col else "",
            str(row.get(bal_col, "")) if bal_col else "",
            str(row.get(ref_col, "")) if ref_col else "",
        )
        for _, row in df.iterrows()
    ])
    log.info(f"  Bronze: {rows_read} rows written")

    # --- Silver: classify and upsert ---
    silver_sql = """
        INSERT INTO silver_bank_transactions
            (txn_date, amount, direction, description, category, ref, source_file)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    inserted = skipped = other_count = 0
    with get_cursor() as cur:
        for _, row in df.iterrows():
            try:
                txn_date = pd.to_datetime(row[date_col], dayfirst=True).date()
                amount = parse_amount(row[amount_col])
                if amount == 0:
                    skipped += 1
                    continue
                direction = infer_direction(row, amount_col, dir_col)
                description = str(row[desc_col]).strip() if desc_col else ""
                category = classify(description, rules)
                ref = str(row[ref_col]).strip() if ref_col else None

                if category == "OTHER":
                    other_count += 1

                cur.execute(silver_sql, (
                    txn_date, abs(amount), direction, description,
                    category, ref, source
                ))
                inserted += 1
            except Exception as e:
                log.debug(f"  Skipped row: {e}")
                skipped += 1

    pct_classified = round((inserted - other_count) / max(inserted, 1) * 100, 1)
    log.info(f"  Silver: {inserted} inserted, {skipped} skipped")
    log.info(f"  Classified: {inserted - other_count}/{inserted} ({pct_classified}%)")
    if other_count:
        log.warning(f"  OTHER (unclassified): {other_count} rows — run --review to inspect")

    log_etl_run(SCRIPT, source, rows_read, inserted, skipped)
    return rows_read, inserted, skipped


# ---------------------------------------------------------------------------
# Review & manual override
# ---------------------------------------------------------------------------

def review_others():
    """Print all unclassified transactions for manual inspection."""
    sql = """
        SELECT id, txn_date, amount, direction, description
        FROM silver_bank_transactions
        WHERE category = 'OTHER' AND is_manual_override = FALSE
        ORDER BY txn_date DESC
        LIMIT 100
    """
    with get_cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()

    if not rows:
        log.info("No unclassified transactions.")
        return

    print(f"\n{'='*70}")
    print(f"  UNCLASSIFIED TRANSACTIONS ({len(rows)} shown, max 100)")
    print(f"{'='*70}")
    print(f"{'ID':>6}  {'Date':>12}  {'Dir':>4}  {'Amount':>14}  Description")
    print("-" * 70)
    for r in rows:
        amt = f"{r['amount']:,.0f}"
        print(f"{r['id']:>6}  {str(r['txn_date']):>12}  {r['direction']:>4}  {amt:>14}  {r['description'][:35]}")

    print(f"\nTo fix: python etl/classify_bank.py --override <ID> <CATEGORY>")
    print(f"Categories: CUSTOMER_PAYMENT | PAYROLL | OPERATING_COST | TAX | BANK_FEE | OTHER")


def apply_override(txn_id: int, category: str):
    valid = {"CUSTOMER_PAYMENT", "PAYROLL", "OPERATING_COST", "TAX", "BANK_FEE", "OTHER"}
    if category not in valid:
        log.error(f"Invalid category '{category}'. Valid: {valid}")
        sys.exit(1)

    sql = """
        UPDATE silver_bank_transactions
        SET category = %s, is_manual_override = TRUE
        WHERE id = %s
    """
    with get_cursor() as cur:
        cur.execute(sql, (category, txn_id))
        if cur.rowcount == 0:
            log.error(f"No transaction found with id={txn_id}")
            sys.exit(1)
    log.info(f"Transaction {txn_id} → {category} (manual override)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Classify LPBank transactions")
    parser.add_argument("file", nargs="?", help="Bank statement file (CSV or Excel)")
    parser.add_argument("--dir", help="Directory of bank statement files")
    parser.add_argument("--review", action="store_true", help="Show unclassified rows")
    parser.add_argument("--override", nargs=2, metavar=("ID", "CATEGORY"),
                        help="Manually set category for a transaction ID")
    args = parser.parse_args()

    if args.review:
        review_others()
        return

    if args.override:
        apply_override(int(args.override[0]), args.override[1])
        return

    if args.file:
        load_file(args.file)
    elif args.dir:
        files = (
            list(Path(args.dir).glob("**/*lpbank*.csv")) +
            list(Path(args.dir).glob("**/*lpbank*.xlsx")) +
            list(Path(args.dir).glob("**/*sao_ke*.csv")) +
            list(Path(args.dir).glob("**/*sao_ke*.xlsx")) +
            list(Path(args.dir).glob("**/*bank_statement*.csv"))
        )
        if not files:
            log.warning(f"No bank statement files found in {args.dir}")
            return
        for f in sorted(files):
            load_file(str(f))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
