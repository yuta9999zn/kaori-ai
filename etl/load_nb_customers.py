"""
Bronze → Silver ETL: NB Customer Sessions + Master DB
Source: NB_customer_history.xlsx (one row per session/visit)

Builds two silver tables:
  silver_nb_customers     — deduplicated master (one row per person)
  silver_nb_customer_sessions — individual visit records
"""

import sys
import os
import hashlib
from pathlib import Path
import pandas as pd
from utils.db import get_cursor, execute_values
from utils.logger import log, log_etl_run

SCRIPT = "load_nb_customers"

COLUMN_ALIASES = {
    "customer name": "name",
    "ten khach": "name",
    "tên khách": "name",
    "khach hang": "name",
    "khách hàng": "name",
    "ho ten": "name",
    "họ tên": "name",
    "phone": "phone",
    "so dien thoai": "phone",
    "số điện thoại": "phone",
    "sdt": "phone",
    "dien thoai": "phone",
    "điện thoại": "phone",
    "date": "visit_date",
    "visit date": "visit_date",
    "ngay": "visit_date",
    "ngày": "visit_date",
    "ngay kham": "visit_date",
    "ngày khám": "visit_date",
    "service": "service",
    "dich vu": "service",
    "dịch vụ": "service",
    "body area": "body_area",
    "vung": "body_area",
    "vùng": "body_area",
    "vung dieu tri": "body_area",
    "vùng điều trị": "body_area",
    "amount": "amount",
    "thanh toan": "amount",
    "thanh toán": "amount",
    "tien": "amount",
    "tiền": "amount",
    "so tien": "amount",
    "staff": "staff",
    "nhan vien": "staff",
    "nhân viên": "staff",
    "ky thuat vien": "staff",
    "kỹ thuật viên": "staff",
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {}
    for col in df.columns:
        key = col.strip().lower()
        if key in COLUMN_ALIASES:
            mapping[col] = COLUMN_ALIASES[key]
    return df.rename(columns=mapping)


def clean_phone(raw) -> str | None:
    if pd.isna(raw) or str(raw).strip() == "":
        return None
    digits = "".join(c for c in str(raw) if c.isdigit())
    if len(digits) >= 9:
        # Normalize to 10-digit Vietnamese format
        if digits.startswith("84") and len(digits) == 11:
            digits = "0" + digits[2:]
        return digits[-10:]
    return None


def make_customer_id(phone: str | None, name: str | None) -> str:
    key = (phone or "") + "|" + (name or "")
    return "NB_" + hashlib.md5(key.encode()).hexdigest()[:12].upper()


def parse_amount(val) -> int:
    if pd.isna(val) or str(val).strip() == "":
        return 0
    cleaned = str(val).replace(".", "").replace(",", "").strip()
    try:
        return int(float(cleaned))
    except ValueError:
        return 0


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

    required = {"name", "visit_date"}
    missing = required - set(df.columns)
    if missing:
        msg = f"Missing required columns: {missing}. Found: {list(df.columns)}"
        log.error(msg)
        log_etl_run(SCRIPT, source, 0, 0, 0, "ERROR", msg)
        return 0, 0, 0

    rows_read = len(df)

    # --- Write to Bronze ---
    bronze_sql = """
        INSERT INTO bronze_nb_customer_sessions
            (source_file, customer_name_raw, phone_raw, visit_date_raw,
             service_raw, body_area_raw, amount_raw, staff_raw)
        VALUES %s
    """
    bronze_rows = [
        (
            source,
            str(row.get("name", "")),
            str(row.get("phone", "")),
            str(row.get("visit_date", "")),
            str(row.get("service", "")),
            str(row.get("body_area", "")),
            str(row.get("amount", "")),
            str(row.get("staff", "")),
        )
        for _, row in df.iterrows()
    ]
    execute_values(bronze_sql, bronze_rows)
    log.info(f"  Bronze: {rows_read} raw rows inserted")

    # --- Transform & upsert Silver ---
    # Collect all unique customers first, then upsert master
    customers: dict[str, dict] = {}
    sessions: list[dict] = []
    skipped = 0

    for _, row in df.iterrows():
        try:
            visit_date = pd.to_datetime(row.get("visit_date", ""), dayfirst=True).date()
        except Exception:
            skipped += 1
            continue

        phone = clean_phone(row.get("phone"))
        name = str(row.get("name", "")).strip() or None
        if not name and not phone:
            skipped += 1
            continue

        customer_id = make_customer_id(phone, name)
        amount = parse_amount(row.get("amount"))

        # Accumulate per-customer stats
        if customer_id not in customers:
            customers[customer_id] = {
                "customer_id": customer_id,
                "phone": phone,
                "name": name,
                "first_visit": visit_date,
                "last_visit": visit_date,
                "total_visits": 0,
                "total_spent": 0,
                "main_service": str(row.get("service", "")).strip() or None,
            }
        c = customers[customer_id]
        c["total_visits"] += 1
        c["total_spent"] += amount
        c["first_visit"] = min(c["first_visit"], visit_date)
        c["last_visit"] = max(c["last_visit"], visit_date)

        sessions.append({
            "customer_id": customer_id,
            "visit_date": visit_date,
            "service": str(row.get("service", "")).strip() or None,
            "body_area": str(row.get("body_area", "")).strip() or None,
            "amount": amount,
            "staff": str(row.get("staff", "")).strip() or None,
            "source_file": source,
        })

    # Upsert customer master
    cust_sql = """
        INSERT INTO silver_nb_customers
            (customer_id, phone, name, first_visit, last_visit,
             total_visits, total_spent, main_service)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (customer_id) DO UPDATE SET
            phone        = COALESCE(EXCLUDED.phone, silver_nb_customers.phone),
            name         = COALESCE(EXCLUDED.name, silver_nb_customers.name),
            first_visit  = LEAST(EXCLUDED.first_visit, silver_nb_customers.first_visit),
            last_visit   = GREATEST(EXCLUDED.last_visit, silver_nb_customers.last_visit),
            total_visits = silver_nb_customers.total_visits + EXCLUDED.total_visits,
            total_spent  = silver_nb_customers.total_spent + EXCLUDED.total_spent,
            updated_at   = NOW()
    """
    with get_cursor() as cur:
        for c in customers.values():
            cur.execute(cust_sql, (
                c["customer_id"], c["phone"], c["name"],
                c["first_visit"], c["last_visit"],
                c["total_visits"], c["total_spent"], c["main_service"],
            ))
    log.info(f"  Silver customers: {len(customers)} upserted")

    # Upsert sessions
    sess_sql = """
        INSERT INTO silver_nb_customer_sessions
            (customer_id, visit_date, service, body_area, amount, staff, source_file)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (customer_id, visit_date, service) DO NOTHING
    """
    sess_inserted = 0
    with get_cursor() as cur:
        for s in sessions:
            cur.execute(sess_sql, (
                s["customer_id"], s["visit_date"], s["service"],
                s["body_area"], s["amount"], s["staff"], s["source_file"],
            ))
            sess_inserted += 1

    log.info(f"  Silver sessions: {sess_inserted} inserted, {skipped} skipped")
    log_etl_run(SCRIPT, source, rows_read, sess_inserted, skipped)
    return rows_read, sess_inserted, skipped


def main(data_dir: str = None):
    if data_dir is None:
        data_dir = os.getenv("NB_DATA_DIR", ".")

    files = (
        list(Path(data_dir).glob("**/*customer*.xlsx")) +
        list(Path(data_dir).glob("**/*khach*.xlsx")) +
        list(Path(data_dir).glob("**/*NB_*lich_su*.xlsx"))
    )

    if not files:
        log.warning(f"No customer files found in {data_dir}")
        return

    for f in sorted(files):
        load_file(str(f))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Load NB customer session history")
    parser.add_argument("--dir", help="Directory containing customer Excel files")
    parser.add_argument("--file", help="Load a single file")
    args = parser.parse_args()

    if args.file:
        load_file(args.file)
    else:
        main(args.dir)
