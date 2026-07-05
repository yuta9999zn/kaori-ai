"""
Bronze → Silver ETL: Staff Shifts
Source: Shift_Management_NB.xlsm or .xlsx
"""

import os
from pathlib import Path
import pandas as pd
from utils.db import get_cursor, execute_values
from utils.logger import log, log_etl_run

SCRIPT = "load_staff_shifts"

COLUMN_ALIASES = {
    "store": "store",
    "cua hang": "store",
    "chi nhanh": "store",
    "staff": "staff_name",
    "staff name": "staff_name",
    "nhan vien": "staff_name",
    "nhân viên": "staff_name",
    "ten nv": "staff_name",
    "date": "shift_date",
    "shift date": "shift_date",
    "ngay": "shift_date",
    "ngày": "shift_date",
    "hours": "hours_worked",
    "hours worked": "hours_worked",
    "gio lam": "hours_worked",
    "giờ làm": "hours_worked",
    "so gio": "hours_worked",
    "role": "role",
    "chuc vu": "role",
    "chức vụ": "role",
    "vi tri": "role",
    "vị trí": "role",
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {}
    for col in df.columns:
        key = col.strip().lower()
        if key in COLUMN_ALIASES:
            mapping[col] = COLUMN_ALIASES[key]
    return df.rename(columns=mapping)


def load_file(filepath: str) -> tuple[int, int, int]:
    source = Path(filepath).name
    log.info(f"Loading: {filepath}")

    try:
        # xlsm files need openpyxl explicitly
        df = pd.read_excel(filepath, dtype=str, engine="openpyxl")
    except Exception as e:
        log.error(f"Cannot open {filepath}: {e}")
        log_etl_run(SCRIPT, source, 0, 0, 0, "ERROR", str(e))
        return 0, 0, 0

    df = df.dropna(how="all")
    df = normalize_columns(df)
    rows_read = len(df)

    if "staff_name" not in df.columns or "shift_date" not in df.columns:
        log.error(f"Missing required columns in {source}. Found: {list(df.columns)}")
        log_etl_run(SCRIPT, source, 0, 0, 0, "ERROR", "Missing staff_name or shift_date")
        return 0, 0, 0

    # --- Bronze ---
    bronze_sql = """
        INSERT INTO bronze_staff_shifts
            (source_file, store_raw, staff_name_raw, shift_date_raw, hours_raw, role_raw)
        VALUES %s
    """
    execute_values(bronze_sql, [
        (source,
         str(r.get("store", "NB_MAIN")),
         str(r.get("staff_name", "")),
         str(r.get("shift_date", "")),
         str(r.get("hours_worked", "")),
         str(r.get("role", "")))
        for _, r in df.iterrows()
    ])

    # --- Silver ---
    silver_sql = """
        INSERT INTO silver_staff_shifts
            (store, staff_name, shift_date, hours_worked, role, source_file)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (store, staff_name, shift_date) DO NOTHING
    """
    inserted = skipped = 0
    with get_cursor() as cur:
        for _, row in df.iterrows():
            try:
                shift_date = pd.to_datetime(row.get("shift_date", ""), dayfirst=True).date()
                store = str(row.get("store", "NB_MAIN")).strip().upper()
                staff = str(row.get("staff_name", "")).strip()
                if not staff:
                    skipped += 1
                    continue
                hours_raw = str(row.get("hours_worked", "")).strip()
                hours = float(hours_raw) if hours_raw.replace(".", "").isdigit() else None
                role = str(row.get("role", "")).strip() or None
                cur.execute(silver_sql, (store, staff, shift_date, hours, role, source))
                inserted += 1
            except Exception as e:
                log.debug(f"  Skipped: {e}")
                skipped += 1

    log.info(f"  {inserted} inserted, {skipped} skipped — {source}")
    log_etl_run(SCRIPT, source, rows_read, inserted, skipped)
    return rows_read, inserted, skipped


def main(data_dir: str = None):
    if data_dir is None:
        data_dir = os.getenv("NB_DATA_DIR", ".")

    files = (
        list(Path(data_dir).glob("**/Shift_*.xlsm")) +
        list(Path(data_dir).glob("**/Shift_*.xlsx")) +
        list(Path(data_dir).glob("**/*ca_lam*.xlsx"))
    )

    if not files:
        log.warning(f"No shift files found in {data_dir}")
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
