"""
Bronze → Silver ETL: RJ Bar Revenue
Source: RJ revenue Excel files (structure TBD — will be shared by customer)

This loader mirrors load_daily_revenue.py but defaults store codes to RJ_BAR / BAR_MINI.
Update COLUMN_ALIASES and STORE_CODES when actual file is received.
"""

import os
from pathlib import Path
import pandas as pd
from utils.db import get_cursor, execute_values
from utils.logger import log, log_etl_run

SCRIPT = "load_rj_revenue"

COLUMN_ALIASES = {
    "store": "store",
    "cua hang": "store",
    "date": "date",
    "ngay": "date",
    "ngày": "date",
    "revenue": "revenue",
    "doanh thu": "revenue",
    "cash": "cash",
    "tien mat": "cash",
    "tiền mặt": "cash",
    "transfer": "transfer",
    "chuyen khoan": "transfer",
    "card": "card",
    "the": "card",
    "cast": "cast_name",
    "cast name": "cast_name",
    "nhan vien": "cast_name",
    "nhân viên": "cast_name",
    "customer type": "customer_type",
    "loai khach": "customer_type",
    "loại khách": "customer_type",
    "customer count": "customer_count",
    "so khach": "customer_count",
    "số khách": "customer_count",
}

STORE_CODES = {
    "rj bar": "RJ_BAR",
    "rj": "RJ_BAR",
    "rjbar": "RJ_BAR",
    "bar mini": "BAR_MINI",
    "barmini": "BAR_MINI",
    "bar_mini": "BAR_MINI",
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {}
    for col in df.columns:
        key = col.strip().lower()
        if key in COLUMN_ALIASES:
            mapping[col] = COLUMN_ALIASES[key]
    return df.rename(columns=mapping)


def parse_amount(val) -> int:
    if pd.isna(val) or str(val).strip() == "":
        return 0
    cleaned = str(val).replace(".", "").replace(",", "").strip()
    try:
        return int(float(cleaned))
    except ValueError:
        return 0


def canonical_store(raw: str, sheet_name: str = "") -> str:
    key = (str(raw).strip().lower() if not pd.isna(raw) else "") or sheet_name.lower()
    return STORE_CODES.get(key, "RJ_BAR")


def load_file(filepath: str) -> tuple[int, int, int]:
    source = Path(filepath).name
    log.info(f"Loading: {filepath}")

    try:
        xls = pd.ExcelFile(filepath)
    except Exception as e:
        log.error(f"Cannot open {filepath}: {e}")
        log_etl_run(SCRIPT, source, 0, 0, 0, "ERROR", str(e))
        return 0, 0, 0

    all_bronze = []
    all_silver = []

    for sheet in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet, dtype=str)
        df = df.dropna(how="all")
        df = normalize_columns(df)

        if "date" not in df.columns:
            log.warning(f"  Sheet '{sheet}': no date column, skipping")
            continue

        for _, row in df.iterrows():
            store = canonical_store(row.get("store", ""), sheet)
            all_bronze.append((
                source,
                str(row.get("store", sheet)),
                str(row.get("date", "")),
                str(row.get("revenue", "")),
                str(row.get("cast_name", "")),
                str(row.get("customer_type", "")),
                str(row.get("customer_count", "")),
            ))
            all_silver.append({
                "store": store,
                "date_raw": str(row.get("date", "")),
                "cash_raw": str(row.get("cash", row.get("revenue", "0"))),
                "transfer_raw": str(row.get("transfer", "0")),
                "card_raw": str(row.get("card", "0")),
                "customer_count_raw": str(row.get("customer_count", "")),
            })

    rows_read = len(all_bronze)
    if rows_read == 0:
        log.warning(f"No rows in {filepath}")
        return 0, 0, 0

    # --- Bronze ---
    bronze_sql = """
        INSERT INTO bronze_rj_revenue
            (source_file, store_raw, date_raw, revenue_raw,
             cast_name_raw, customer_type_raw, notes_raw)
        VALUES %s
    """
    execute_values(bronze_sql, all_bronze)
    log.info(f"  Bronze: {rows_read} rows")

    # --- Silver (reuses silver_daily_revenue, same table as NB) ---
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
    inserted = skipped = 0
    with get_cursor() as cur:
        for r in all_silver:
            try:
                date = pd.to_datetime(r["date_raw"], dayfirst=True).date()
                cash = parse_amount(r["cash_raw"])
                transfer = parse_amount(r["transfer_raw"])
                card = parse_amount(r["card_raw"])
                count_raw = r["customer_count_raw"]
                count = int(count_raw) if count_raw.isdigit() else None
                cur.execute(silver_sql, (
                    r["store"], date, cash, transfer, card, count, source
                ))
                inserted += 1
            except Exception as e:
                log.debug(f"  Skipped: {e}")
                skipped += 1

    log.info(f"  Silver: {inserted} upserted, {skipped} skipped")
    log_etl_run(SCRIPT, source, rows_read, inserted, skipped)
    return rows_read, inserted, skipped


def main(data_dir: str = None):
    if data_dir is None:
        data_dir = os.getenv("RJ_DATA_DIR", ".")

    files = (
        list(Path(data_dir).glob("**/*RJ*.xlsx")) +
        list(Path(data_dir).glob("**/*rj*.xlsx")) +
        list(Path(data_dir).glob("**/*bar*.xlsx"))
    )

    if not files:
        log.warning(f"No RJ revenue files found in {data_dir}")
        return

    for f in sorted(files):
        load_file(str(f))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir")
    parser.add_argument("--file")
    args = parser.parse_args()
    if args.file:
        load_file(args.file)
    else:
        main(args.dir)
