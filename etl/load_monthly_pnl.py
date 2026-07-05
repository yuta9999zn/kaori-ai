"""
Bronze → Silver ETL: Monthly P&L
Source: Management_report.xlsx (one row per store per month)
"""

import os
from pathlib import Path
import pandas as pd
from utils.db import get_cursor, execute_values
from utils.logger import log, log_etl_run

SCRIPT = "load_monthly_pnl"

COLUMN_ALIASES = {
    "store": "store",
    "cua hang": "store",
    "chi nhanh": "store",
    "year_month": "year_month",
    "month": "year_month",
    "thang": "year_month",
    "tháng": "year_month",
    "nam thang": "year_month",
    "revenue": "revenue",
    "doanh thu": "revenue",
    "cost goods": "cost_goods",
    "gia von": "cost_goods",
    "giá vốn": "cost_goods",
    "cost salary": "cost_salary",
    "luong": "cost_salary",
    "lương": "cost_salary",
    "chi phi luong": "cost_salary",
    "chi phí lương": "cost_salary",
    "cost rent": "cost_rent",
    "thue mat bang": "cost_rent",
    "thuê mặt bằng": "cost_rent",
    "tien thue": "cost_rent",
    "cost other": "cost_other",
    "chi phi khac": "cost_other",
    "chi phí khác": "cost_other",
    "net profit": "net_profit",
    "loi nhuan": "net_profit",
    "lợi nhuận": "net_profit",
    "bep": "bep_target",
    "bep target": "bep_target",
    "diem hoa von": "bep_target",
    "điểm hòa vốn": "bep_target",
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {}
    for col in df.columns:
        key = col.strip().lower()
        if key in COLUMN_ALIASES:
            mapping[col] = COLUMN_ALIASES[key]
    return df.rename(columns=mapping)


def parse_amount(val) -> int | None:
    if pd.isna(val) or str(val).strip() in ("", "-"):
        return None
    cleaned = str(val).replace(".", "").replace(",", "").strip()
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def normalize_year_month(raw) -> str | None:
    """Accepts: 'Apr 2026', '04/2026', '2026-04', date objects."""
    if pd.isna(raw):
        return None
    try:
        dt = pd.to_datetime(raw)
        return dt.strftime("%Y-%m")
    except Exception:
        s = str(raw).strip()
        # Already in YYYY-MM
        if len(s) == 7 and s[4] == "-":
            return s
        return None


def load_file(filepath: str) -> tuple[int, int, int]:
    source = Path(filepath).name
    log.info(f"Loading: {filepath}")

    try:
        df = pd.read_excel(filepath, dtype=str)
    except Exception as e:
        log.error(f"Cannot open {filepath}: {e}")
        log_etl_run(SCRIPT, source, 0, 0, 0, "ERROR", str(e))
        return 0, 0, 0

    df = df.dropna(how="all")
    df = normalize_columns(df)
    rows_read = len(df)

    # --- Bronze ---
    bronze_sql = """
        INSERT INTO bronze_monthly_pnl
            (source_file, store_raw, year_month_raw, revenue_raw,
             cost_goods_raw, cost_salary_raw, cost_rent_raw, cost_other_raw,
             net_profit_raw, bep_target_raw)
        VALUES %s
    """
    bronze_rows = [
        (
            source,
            str(row.get("store", "")),
            str(row.get("year_month", "")),
            str(row.get("revenue", "")),
            str(row.get("cost_goods", "")),
            str(row.get("cost_salary", "")),
            str(row.get("cost_rent", "")),
            str(row.get("cost_other", "")),
            str(row.get("net_profit", "")),
            str(row.get("bep_target", "")),
        )
        for _, row in df.iterrows()
    ]
    execute_values(bronze_sql, bronze_rows)

    # --- Silver ---
    silver_sql = """
        INSERT INTO silver_monthly_pnl
            (store, year_month, revenue, cost_goods, cost_salary,
             cost_rent, cost_other, net_profit, bep_target, source_file)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (store, year_month) DO UPDATE SET
            revenue     = EXCLUDED.revenue,
            cost_goods  = EXCLUDED.cost_goods,
            cost_salary = EXCLUDED.cost_salary,
            cost_rent   = EXCLUDED.cost_rent,
            cost_other  = EXCLUDED.cost_other,
            net_profit  = EXCLUDED.net_profit,
            bep_target  = EXCLUDED.bep_target,
            source_file = EXCLUDED.source_file,
            updated_at  = NOW()
    """
    inserted = skipped = 0
    with get_cursor() as cur:
        for _, row in df.iterrows():
            try:
                store = str(row.get("store", "")).strip().upper() or "UNKNOWN"
                ym = normalize_year_month(row.get("year_month"))
                if not ym:
                    skipped += 1
                    continue
                cur.execute(silver_sql, (
                    store, ym,
                    parse_amount(row.get("revenue")),
                    parse_amount(row.get("cost_goods")),
                    parse_amount(row.get("cost_salary")),
                    parse_amount(row.get("cost_rent")),
                    parse_amount(row.get("cost_other")),
                    parse_amount(row.get("net_profit")),
                    parse_amount(row.get("bep_target")),
                    source,
                ))
                inserted += 1
            except Exception as e:
                log.debug(f"  Skipped row: {e}")
                skipped += 1

    log.info(f"  {inserted} upserted, {skipped} skipped — {source}")
    log_etl_run(SCRIPT, source, rows_read, inserted, skipped)
    return rows_read, inserted, skipped


def main(data_dir: str = None):
    if data_dir is None:
        data_dir = os.getenv("NB_DATA_DIR", ".")

    files = (
        list(Path(data_dir).glob("**/*management_report*.xlsx")) +
        list(Path(data_dir).glob("**/*bao_cao*.xlsx")) +
        list(Path(data_dir).glob("**/*P&L*.xlsx")) +
        list(Path(data_dir).glob("**/*pnl*.xlsx"))
    )

    if not files:
        log.warning(f"No P&L files found in {data_dir}")
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
