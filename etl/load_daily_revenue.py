"""
Bronze → Silver ETL: Daily Revenue
Source: Daily_revenue.xlsx (one file per month, one sheet per store, or all in one sheet)

Expected columns (flexible matching, not exact):
  Store, Date, Cash, Transfer, Card, Customer Count

Bronze: raw rows, all text
Silver: typed, deduplicated, upserted by (store, date)
"""

import sys
import os
from pathlib import Path
import pandas as pd
from utils.db import get_cursor, execute_values
from utils.logger import log, log_etl_run
from utils.excel_parser import iter_sheets

SCRIPT = "load_daily_revenue"

# Column spec for fuzzy matching — passed to excel_parser
COL_SPEC = {
    "store": [
        "store", "branch", "cua hang", "cửa hàng", "chi nhanh", "chi nhánh",
        "location", "ten chi nhanh", "tên chi nhánh",
    ],
    "date": [
        "date", "ngay", "ngày", "日付", "日", "time", "thoi gian", "thời gian",
        "ngay thang", "ngày tháng", "transaction date", "ngay gd",
    ],
    "cash": [
        "cash", "tien mat", "tiền mặt", "mat", "mặt", "tien mat thuc thu",
        "tiền mặt thực thu",
    ],
    "transfer": [
        "transfer", "chuyen khoan", "chuyển khoản", "ck", "banking",
        "chuyen khoan thuc thu",
    ],
    "card": [
        "card", "the", "thẻ", "visa", "mastercard", "credit", "debit",
    ],
    "amount": [
        "amount", "total", "revenue", "doanh thu", "tien", "tiền",
        "tong thu", "tổng thu", "so tien", "số tiền", "売上", "金額",
        "tong doanh thu", "tổng doanh thu",
    ],
    "customer_count": [
        "customer count", "customer", "khach", "khách", "so khach", "số khách",
        "luot khach", "lượt khách", "so luot", "qty", "count",
    ],
}

# Map raw store name strings → canonical store codes
STORE_CODES = {
    "nb main": "NB_MAIN",
    "nb": "NB_MAIN",
    "natural beauty": "NB_MAIN",
    "natural beauty japan": "NB_MAIN",
    "nb_main": "NB_MAIN",
    "nb fc": "NB_FC_1",
    "nb_fc": "NB_FC_1",
    "fc": "NB_FC_1",
    "rj bar": "RJ_BAR",
    "rj": "RJ_BAR",
    "rjbar": "RJ_BAR",
    "bar mini": "BAR_MINI",
    "barmini": "BAR_MINI",
    "bar_mini": "BAR_MINI",
}


def parse_amount(val) -> int:
    """Parse Vietnamese number formats: '1.200.000' or '1200000' or '1,200,000'."""
    if pd.isna(val) or str(val).strip() == "":
        return 0
    cleaned = str(val).replace(".", "").replace(",", "").strip()
    try:
        return int(float(cleaned))
    except ValueError:
        return 0


def canonical_store(raw: str) -> str:
    if pd.isna(raw):
        return "UNKNOWN"
    key = str(raw).strip().lower()
    return STORE_CODES.get(key, str(raw).strip().upper())


def load_file(filepath: str) -> tuple[int, int, int]:
    """Load one Excel file. Returns (rows_read, rows_inserted, rows_skipped)."""
    source = Path(filepath).name
    log.info(f"Loading: {filepath}")

    all_rows = []

    for sheet, df, col_map in iter_sheets(filepath, COL_SPEC, logger=log):
        date_col = col_map.get("date")
        if not date_col:
            log.warning(f"  [SKIP] Sheet '{sheet}': no date column detected — "
                        f"found columns: {list(df.columns)[:10]}")
            continue

        # Amount: prefer explicit cash/transfer/card; fall back to generic "amount"
        cash_col     = col_map.get("cash")
        transfer_col = col_map.get("transfer")
        card_col     = col_map.get("card")
        amount_col   = col_map.get("amount")   # fallback total column

        # Determine store: from a store column, or use sheet name
        store_col = col_map.get("store")
        count_col = col_map.get("customer_count")

        for _, row in df.iterrows():
            all_rows.append({
                "source_file": source,
                "store_raw":          str(row.get(store_col, sheet)) if store_col else sheet,
                "date_raw":           str(row.get(date_col, "")),
                "cash_raw":           str(row.get(cash_col, "0")) if cash_col else "0",
                "transfer_raw":       str(row.get(transfer_col, "0")) if transfer_col else "0",
                "card_raw":           str(row.get(card_col, "0")) if card_col else "0",
                "amount_raw":         str(row.get(amount_col, "")) if amount_col else "",
                "customer_count_raw": str(row.get(count_col, "")) if count_col else "",
                "notes_raw":          "",
            })

    rows_read = len(all_rows)
    if rows_read == 0:
        log.warning(f"No data rows found in {filepath}")
        log_etl_run(SCRIPT, source, 0, 0, 0, "WARNING", "No rows found")
        return 0, 0, 0

    # --- Write to Bronze ---
    bronze_sql = """
        INSERT INTO bronze_daily_revenue
            (source_file, store_raw, date_raw, cash_raw, transfer_raw, card_raw,
             customer_count_raw, notes_raw)
        VALUES %s
    """
    bronze_rows = [
        (r["source_file"], r["store_raw"], r["date_raw"],
         r["cash_raw"], r["transfer_raw"], r["card_raw"],
         r["customer_count_raw"], r["notes_raw"])
        for r in all_rows
    ]
    execute_values(bronze_sql, bronze_rows)
    log.info(f"  Bronze: inserted {rows_read} raw rows")

    # --- Transform & upsert Silver ---
    inserted = skipped = 0
    silver_sql = """
        INSERT INTO silver_daily_revenue
            (store, date, cash, transfer, card, customer_count, source_file)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (store, date) DO UPDATE SET
            cash = EXCLUDED.cash,
            transfer = EXCLUDED.transfer,
            card = EXCLUDED.card,
            customer_count = EXCLUDED.customer_count,
            source_file = EXCLUDED.source_file,
            updated_at = NOW()
    """
    with get_cursor() as cur:
        for r in all_rows:
            try:
                date = pd.to_datetime(r["date_raw"], dayfirst=True).date()
                store = canonical_store(r["store_raw"])
                cash = parse_amount(r["cash_raw"])
                transfer = parse_amount(r["transfer_raw"])
                card = parse_amount(r["card_raw"])

                # If no breakdown columns were found, put the total in cash slot
                if cash == 0 and transfer == 0 and card == 0 and r["amount_raw"]:
                    cash = parse_amount(r["amount_raw"])

                count_raw = r["customer_count_raw"].strip()
                count = int(count_raw) if count_raw.isdigit() else None
                cur.execute(silver_sql, (store, date, cash, transfer, card, count, source))
                inserted += 1
            except Exception as e:
                log.debug(f"  Skipped row: {r} — {e}")
                skipped += 1

    log.info(f"  Silver: {inserted} upserted, {skipped} skipped")
    log_etl_run(SCRIPT, source, rows_read, inserted, skipped)
    return rows_read, inserted, skipped


def main(data_dir: str = None):
    if data_dir is None:
        data_dir = os.getenv("NB_DATA_DIR", ".")

    files = list(Path(data_dir).glob("**/Daily_*.xlsx")) + \
            list(Path(data_dir).glob("**/daily_*.xlsx")) + \
            list(Path(data_dir).glob("**/*doanh_thu*.xlsx"))

    if not files:
        log.warning(f"No revenue files found in {data_dir}. "
                    "Looking for: Daily_*.xlsx, *doanh_thu*.xlsx")
        return

    total_read = total_ins = total_skip = 0
    for f in sorted(files):
        r, i, s = load_file(str(f))
        total_read += r
        total_ins += i
        total_skip += s

    log.info(f"Done. Total: {total_read} read, {total_ins} inserted, {total_skip} skipped")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Load daily revenue Excel files")
    parser.add_argument("--dir", help="Directory containing revenue Excel files")
    parser.add_argument("--file", help="Load a single file")
    args = parser.parse_args()

    if args.file:
        load_file(args.file)
    else:
        main(args.dir)
