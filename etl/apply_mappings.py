"""
Stage 2: Apply confirmed mappings → write Silver layer.

Reads the mapping JSON produced by ingest.py (after user review).
Queries Bronze tables, applies confirmed column → canonical mappings,
writes clean data to Silver tables.

Usage:
  python etl/apply_mappings.py config/mappings/Daily_revenue_April_mapping.json
  python etl/apply_mappings.py config/mappings/Daily_revenue_April_mapping.json --force
    (--force skips the needs_review check — use when you've reviewed and accepted)

The mapping JSON can be:
  - Auto-accepted (all HIGH confidence) — apply immediately
  - Needs review   — requires user to fill in 'user_override' fields

Mapping JSON example (user fills in user_override for unknown columns):
  {
    "columns": [
      {"raw_name": "Cột D", "canonical": null, "confidence": "UNKNOWN",
       "user_override": "transfer"},   ← user adds this
      {"raw_name": "Some col", "canonical": null, "confidence": "UNKNOWN",
       "user_override": "skip"}        ← or explicitly skip it
    ]
  }
"""

import os
import sys
import argparse
import hashlib
import re
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

import pandas as pd
from utils.db import get_cursor, execute_values
from utils.logger import log, log_etl_run
from utils.excel_parser import load_sheet_smart, ColumnMatch
from utils.wide_format import melt_to_silver_schema, WideFormatInfo
from etl.ingest import load_mapping_file, SheetReport, IngestReport


# ---------------------------------------------------------------------------
# Amount / date parsers
# ---------------------------------------------------------------------------

def _parse_amount(val) -> int:
    if val is None or str(val).strip() in ("", "nan", "none", "-"):
        return 0
    cleaned = re.sub(r"[,.\s]", "", str(val))
    try:
        return int(float(cleaned))
    except ValueError:
        return 0


def _parse_date(val):
    if val is None or str(val).strip() in ("", "nan", "none"):
        return None
    try:
        return pd.to_datetime(str(val), dayfirst=True).date()
    except Exception:
        return None


def _clean_phone(raw) -> str | None:
    if not raw or str(raw).strip() in ("", "nan"):
        return None
    digits = "".join(c for c in str(raw) if c.isdigit())
    if len(digits) < 9:
        return None
    if digits.startswith("84") and len(digits) == 11:
        digits = "0" + digits[2:]
    return digits[-10:]


def _make_customer_id(phone: str | None, name: str | None) -> str:
    key = (phone or "") + "|" + (name or "")
    return "NB_" + hashlib.md5(key.encode()).hexdigest()[:12].upper()


# ---------------------------------------------------------------------------
# Silver writers
# ---------------------------------------------------------------------------

STORE_CODES = {
    "nb main": "NB_MAIN", "nb": "NB_MAIN", "natural beauty": "NB_MAIN",
    "natural beauty japan": "NB_MAIN", "nb_main": "NB_MAIN",
    "nb fc": "NB_FC_1", "nb_fc": "NB_FC_1", "fc": "NB_FC_1",
    "rj bar": "RJ_BAR", "rj": "RJ_BAR", "rjbar": "RJ_BAR",
    "bar mini": "BAR_MINI", "barmini": "BAR_MINI",
}


def _canonical_store(raw: str, fallback: str = "UNKNOWN") -> str:
    key = str(raw).strip().lower()
    return STORE_CODES.get(key, raw.strip().upper() or fallback)


# ---------------------------------------------------------------------------
# Filename helpers — extract month/year and store from filename
# Handles patterns like:  "RJ Katamono 4.2026.xlsx"
#                          "NB Daily_revenue_April_2026.xlsx"
# ---------------------------------------------------------------------------

def _store_from_filename(filename: str) -> str:
    """Guess store code from the filename prefix."""
    stem = Path(filename).stem.lower()
    for key, code in sorted(STORE_CODES.items(), key=lambda kv: -len(kv[0])):
        if stem.startswith(key.replace(" ", "")) or stem.startswith(key.replace(" ", "_")):
            return code
    # Try first token
    first = re.split(r"[\s_\-]", stem)[0]
    return STORE_CODES.get(first, first.upper())


def _month_year_from_filename(filename: str) -> tuple[int, int] | None:
    """
    Extract (month, year) from a filename.
    Matches patterns:  "4.2026"  "04_2026"  "April_2026"  "2026-04"
    Returns None if nothing found.
    """
    stem = Path(filename).stem
    # Numeric: 4.2026 / 04.2026 / 4_2026 / 04-2026
    m = re.search(r'(\d{1,2})[._\-](\d{4})', stem)
    if m:
        month, year = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 2000 <= year <= 2100:
            return month, year
    # Year-month: 2026-04 / 2026_04
    m = re.search(r'(\d{4})[._\-](\d{1,2})', stem)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 2000 <= year <= 2100:
            return month, year
    # Month name: April_2026
    month_names = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    for name, num in month_names.items():
        m = re.search(rf'{name}\w*[_\-.\s](\d{{4}})', stem.lower())
        if m:
            return num, int(m.group(1))
    return None


def _build_date(day_raw: str, month: int, year: int) -> date | None:
    """Combine a raw day string ('1', '01', '31') with month+year → date."""
    try:
        day = int(str(day_raw).strip().split("/")[0].split("-")[0])
        return date(year, month, day)
    except (ValueError, TypeError):
        return None


def write_silver_revenue(source_file: str, sheet: SheetReport, df: pd.DataFrame):
    """Write silver_daily_revenue from a revenue-type sheet."""
    em = sheet.effective_mapping  # canonical → raw_col_name
    date_col = em.get("date")
    if not date_col:
        log.warning(f"  [Silver] Sheet '{sheet.sheet_name}': no date column — skipping Silver write")
        return 0, 0

    store_col    = em.get("store")
    cash_col     = em.get("cash")
    transfer_col = em.get("transfer")
    card_col     = em.get("card")
    amount_col   = em.get("amount")
    count_col    = em.get("customer_count")

    sql = """
        INSERT INTO silver_daily_revenue
            (store, date, cash, transfer, card, customer_count, source_file)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (store, date) DO UPDATE SET
            cash = EXCLUDED.cash, transfer = EXCLUDED.transfer,
            card = EXCLUDED.card, customer_count = EXCLUDED.customer_count,
            source_file = EXCLUDED.source_file, updated_at = NOW()
    """
    inserted = skipped = 0
    with get_cursor() as cur:
        for _, row in df.iterrows():
            dt = _parse_date(row.get(date_col, ""))
            if not dt:
                skipped += 1
                continue

            store_raw = str(row.get(store_col, sheet.sheet_name)) if store_col else sheet.sheet_name
            store = _canonical_store(store_raw)

            cash     = _parse_amount(row.get(cash_col)) if cash_col else 0
            transfer = _parse_amount(row.get(transfer_col)) if transfer_col else 0
            card     = _parse_amount(row.get(card_col)) if card_col else 0

            # Fallback: if no breakdown, use total amount as cash
            if cash == 0 and transfer == 0 and card == 0 and amount_col:
                cash = _parse_amount(row.get(amount_col))

            count_raw = str(row.get(count_col, "")).strip() if count_col else ""
            count = int(count_raw) if count_raw.isdigit() else None

            try:
                cur.execute(sql, (store, dt, cash, transfer, card, count, source_file))
                inserted += 1
            except Exception as e:
                log.debug(f"  Row skip: {e}")
                skipped += 1

    return inserted, skipped


def write_silver_customers(source_file: str, sheet: SheetReport, df: pd.DataFrame):
    """Write silver_nb_customers + silver_nb_customer_sessions."""
    em = sheet.effective_mapping
    date_col  = em.get("date")
    name_col  = em.get("name")

    if not date_col:
        log.warning(f"  [Silver] Sheet '{sheet.sheet_name}': no date column — skipping")
        return 0, 0

    phone_col   = em.get("phone")
    amount_col  = em.get("amount")
    service_col = em.get("service")
    area_col    = em.get("body_area")
    staff_col   = em.get("staff")

    customers: dict[str, dict] = {}
    sessions: list[tuple] = []
    skipped = 0

    for _, row in df.iterrows():
        dt = _parse_date(row.get(date_col, ""))
        if not dt:
            skipped += 1
            continue

        name  = str(row.get(name_col, "")).strip() if name_col else None
        phone = _clean_phone(row.get(phone_col)) if phone_col else None
        if not name and not phone:
            skipped += 1
            continue

        customer_id = _make_customer_id(phone, name)
        amount = _parse_amount(row.get(amount_col)) if amount_col else 0
        service = str(row.get(service_col, "")).strip() if service_col else None
        area    = str(row.get(area_col, "")).strip() if area_col else None
        staff   = str(row.get(staff_col, "")).strip() if staff_col else None

        if customer_id not in customers:
            customers[customer_id] = {
                "id": customer_id, "phone": phone, "name": name,
                "first": dt, "last": dt,
                "visits": 0, "spent": 0, "service": service,
            }
        c = customers[customer_id]
        c["visits"] += 1
        c["spent"] += amount
        c["first"] = min(c["first"], dt)
        c["last"]  = max(c["last"], dt)

        sessions.append((customer_id, dt, service, area, amount, staff, source_file))

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
    sess_sql = """
        INSERT INTO silver_nb_customer_sessions
            (customer_id, visit_date, service, body_area, amount, staff, source_file)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (customer_id, visit_date, service) DO NOTHING
    """
    with get_cursor() as cur:
        for c in customers.values():
            cur.execute(cust_sql, (
                c["id"], c["phone"], c["name"], c["first"], c["last"],
                c["visits"], c["spent"], c["service"],
            ))
        for s in sessions:
            cur.execute(sess_sql, s)

    log.info(f"  Silver: {len(customers)} customers, {len(sessions)} sessions upserted")
    return len(sessions), skipped


def write_silver_inventory(
    source_file: str,
    sheet: SheetReport,
    df: pd.DataFrame,
    pivot_info: WideFormatInfo | None,
):
    """
    Write silver_inventory_daily from a wide-format pivoted sheet.

    df is already pivoted (columns: row_id, product, Get/在庫/使う/nokoru/total).
    We melt those metric columns into (date, product_name, metric_type, value).
    Date is constructed from the row_id + month/year extracted from the filename.
    """
    em = sheet.effective_mapping

    store = _store_from_filename(source_file)
    my = _month_year_from_filename(source_file)

    melted = melt_to_silver_schema(df, em, store, source_file)

    if melted.empty:
        log.warning(f"  [Silver/Inv] Sheet '{sheet.sheet_name}': melt produced 0 rows")
        return 0, 0

    sql = """
        INSERT INTO silver_inventory_daily
            (store, date, product_name, metric_type, value, source_file)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (store, date, product_name, metric_type) DO UPDATE SET
            value       = EXCLUDED.value,
            source_file = EXCLUDED.source_file,
            loaded_at   = NOW()
    """

    inserted = skipped = 0
    with get_cursor() as cur:
        for _, row in melted.iterrows():
            # Build full date from day-of-month + filename month/year
            if my:
                dt = _build_date(row["date"], my[0], my[1])
            else:
                dt = _parse_date(row["date"])   # fallback: try direct parse

            if not dt:
                skipped += 1
                continue

            try:
                val_str = str(row["value"]).replace(",", "").strip()
                value = float(val_str) if val_str else None
            except (ValueError, TypeError):
                value = None

            product = str(row.get("product_name", "")).strip() or None
            metric  = str(row.get("metric_type", "")).strip() or None

            if not product or not metric:
                skipped += 1
                continue

            try:
                cur.execute(sql, (store, dt, product, metric, value, source_file))
                inserted += 1
            except Exception as e:
                log.debug(f"  Inv row skip: {e}")
                skipped += 1

    return inserted, skipped


# ---------------------------------------------------------------------------
# Detect what kind of data a sheet contains
# ---------------------------------------------------------------------------

def _infer_table_type(sheet: SheetReport, pivot_info: WideFormatInfo | None = None) -> str:
    """
    Guess whether this sheet is inventory, revenue, customer, or bank data.
    pivot_info being set is the strongest signal for inventory.
    """
    if pivot_info is not None:
        return "inventory"

    em = sheet.effective_mapping
    # Also detect inventory by canonical fields even without a pivot (future-proofing)
    inv_fields = {"inventory", "usage", "remaining"}
    if len(inv_fields & set(em.keys())) >= 2:
        return "inventory"

    has_name_or_phone = bool(em.get("name") or em.get("phone"))
    has_service = bool(em.get("service") or em.get("body_area"))
    has_revenue  = bool(em.get("cash") or em.get("transfer") or em.get("card") or em.get("amount"))
    has_desc = bool(em.get("description"))
    has_ref  = bool(em.get("ref"))

    if has_name_or_phone and has_service:
        return "customer"
    if has_desc and has_ref:
        return "bank"
    if has_revenue:
        return "revenue"
    if has_name_or_phone:
        return "customer"
    return "revenue"   # default


# ---------------------------------------------------------------------------
# Apply one mapping file
# ---------------------------------------------------------------------------

def apply_mappings(mapping_path: Path, force: bool = False):
    log.info(f"\nApplying mappings: {mapping_path}")

    report = load_mapping_file(mapping_path)
    source = Path(report.filepath).name

    if report.needs_review and not force:
        log.error(
            "\n  ✗ This mapping file has columns that still need review.\n"
            "  Fill in 'user_override' for all UNKNOWN/LOW columns in:\n"
            f"    {mapping_path}\n"
            "  Valid values: date | amount | cash | transfer | card | store |\n"
            "                customer_count | name | phone | service |\n"
            "                body_area | staff | description | ref | skip\n\n"
            "  Or re-run with --force to apply anyway (unknown cols will be ignored)."
        )
        sys.exit(1)

    # Re-read the actual Excel file with the confirmed header rows
    for sheet in report.sheets:
        if sheet.status == "skipped":
            log.info(f"  Skipping sheet '{sheet.sheet_name}' (marked skipped)")
            continue

        if sheet.header_row is None:
            log.warning(f"  Sheet '{sheet.sheet_name}': no header_row in mapping — skipping")
            continue

        log.info(f"\n  Processing sheet '{sheet.sheet_name}' "
                 f"(header row {sheet.header_row + 1})")

        # Log the effective mapping being used
        em = sheet.effective_mapping
        unknown = [c.raw_name for c in sheet.columns
                   if (c.user_override or c.canonical) is None
                   or (c.user_override or c.canonical) == "skip"]
        if unknown:
            log.info(f"  Columns being ignored: {unknown}")
        log.info(f"  Effective mapping: {em}")

        # ── STEP 1: use load_sheet_smart so wide-format pivot runs ──────────
        # This returns the same pivoted df that ingest saw, so column names
        # in the mapping JSON align with what we receive here.
        result = load_sheet_smart(report.filepath, sheet.sheet_name, logger=log)
        if result is None:
            log.warning(f"  Sheet '{sheet.sheet_name}': load_sheet_smart returned None — skipping")
            continue
        df, _col_matches, _hdr, pivot_info = result
        # ────────────────────────────────────────────────────────────────────

        df = df.dropna(how="all").reset_index(drop=True)

        table_type = _infer_table_type(sheet, pivot_info)
        log.info(f"  Detected table type: {table_type}"
                 + (f"  [WIDE FORMAT: {pivot_info.group_count} product groups]"
                    if pivot_info else ""))

        if table_type == "inventory":
            ins, skip = write_silver_inventory(source, sheet, df, pivot_info)
        elif table_type == "revenue":
            ins, skip = write_silver_revenue(source, sheet, df)
        elif table_type == "customer":
            ins, skip = write_silver_customers(source, sheet, df)
        elif table_type == "bank":
            log.info(f"  Bank sheet detected — use classify_bank.py for full classification")
            ins, skip = write_silver_revenue(source, sheet, df)   # best-effort
        else:
            log.warning(f"  Unknown table type for sheet '{sheet.sheet_name}' — skipping Silver")
            ins, skip = 0, 0

        log.info(f"  Silver: {ins} inserted, {skip} skipped")
        log_etl_run("apply_mappings", source, sheet.row_count, ins, skip)

    log.info("\nDone.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Apply confirmed mappings from ingest.py → write Silver layer"
    )
    parser.add_argument("mapping_file", help="Path to _mapping.json file from ingest.py")
    parser.add_argument("--force", action="store_true",
                        help="Apply even if some columns are unreviewed (unknown cols ignored)")
    args = parser.parse_args()

    path = Path(args.mapping_file)
    if not path.exists():
        log.error(f"Mapping file not found: {path}")
        sys.exit(1)

    apply_mappings(path, force=args.force)


if __name__ == "__main__":
    main()
