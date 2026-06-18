"""
Pilot UAT seed — Olist Brazilian E-commerce as the reference dataset.

What this script does
=====================
1. Creates a platform admin (`admin@kaori.platform`) so anh can log in to
   the P1 portal at `/platform/login`.
2. Creates a workspace named **"Olist Store"** + a single enterprise
   inside it, mirroring how the real Olist company would onboard.
3. Creates an enterprise admin user (`cs@olist.local`) with the MANAGER
   role so anh can switch from P1 down into P2 immediately.
4. Loads a curated subset of the Olist CSV bundle through the Bronze →
   Silver → Gold layers as if the wizard had already run end-to-end:
     - Bronze: raw JSONB rows kept verbatim (K-2 immutability).
     - Silver: column-renamed to canonical names + typed (K-9 NUMERIC
       precision for money), one row per Bronze row. RLS policies stay
       in force — every INSERT carries enterprise_id.
     - Gold: per-customer `revenue_at_risk` aggregate computed from the
       order timestamps (mirrors what Phase 1 F-032 cron produces).
5. Sprinkles a few sample `decision_audit_log` rows so `/p2/decisions`
   isn't empty + F-041 explainability has something to explain.

Why direct DB seed (not API-driven)
====================================
Going through `POST /api/v1/upload` for 4 files would require
auth-service + data-pipeline + Kafka all running, and the parser then
mock-sleeps before the row would appear. The pilot UAT goal is
"login → see clean data" — direct INSERT gets there in seconds.

Subset chosen
=============
We sample 500 customers + their orders/items/products/sellers — keeps
the seed runtime under ~30s on a 16 GB pilot laptop while still giving
enough data for cohort retention + at-risk + framework analyses. Skip
the 61 MB geolocation file entirely (not used by any feature today)
and the reviews + payments files (Phase 2 F-035/F-039 don't need them
yet).

Usage
=====
   python scripts/seed-pilot-olist.py [--reset]

Required env (defaults match docker-compose.yml):
   DATABASE_URL   postgresql://kaori_app:kaori_dev_password@localhost:5432/kaori
                  (or any user with INSERT on the seeded tables)

Idempotent: re-running with the same input is a no-op for the
admin/workspace/enterprise/user rows (UPSERT). Pipeline rows are
re-inserted with fresh UUIDs so a re-run always doubles the data —
pass `--reset` to wipe the existing Olist artefacts first.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import psycopg2
    import psycopg2.extras
    from psycopg2.extras import Json, execute_values
except ImportError:
    sys.stderr.write(
        "psycopg2-binary missing — install with:\n"
        "  python -m pip install psycopg2-binary bcrypt\n"
    )
    raise

try:
    import bcrypt
except ImportError:
    sys.stderr.write(
        "bcrypt missing — install with:\n"
        "  python -m pip install bcrypt\n"
    )
    raise


# ─── Config ──────────────────────────────────────────────────────


REPO_ROOT       = Path(__file__).resolve().parent.parent
OLIST_DIR       = REPO_ROOT / "infrastructure" / "seed" / "olist"


def _load_env_file() -> None:
    """Tiny .env parser — reads `KEY=VALUE` lines from repo root .env
    into os.environ if not already set. Avoids the python-dotenv
    dependency for a one-shot seed script."""
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_load_env_file()

# Connect as the superuser `kaori` so RLS is bypassed during seeding —
# we write rows for a tenant whose `app.enterprise_id` GUC is not set
# on this connection, so the kaori_app role (NOBYPASSRLS post-migration
# 025) would block them. Superuser path is the right choice for a
# one-off seed; no production code should ever run this script.
#
# Override with DATABASE_URL env var if needed (full control), else
# we build the URL from POSTGRES_PASSWORD in .env.
_default_pw = os.environ.get("POSTGRES_PASSWORD", "kaori_dev_password")
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"postgresql://kaori:{_default_pw}@localhost:5432/kaori",
)

# Stable IDs so re-runs upsert. The 011577 suffix is a visual marker
# (looks like "OLIST" in leetspeak) so anh can spot seed rows in psql.
WORKSPACE_ID    = uuid.UUID("00000000-0000-0000-0001-000000011577")
ENTERPRISE_ID   = uuid.UUID("00000000-0000-0000-0002-000000011577")
ENT_USER_ID     = uuid.UUID("00000000-0000-0000-0003-000000011577")

PLATFORM_ADMIN_EMAIL    = "admin@kaori.platform"
PLATFORM_ADMIN_PASSWORD = "Admin@2026"
PLATFORM_ADMIN_NAME     = "Kaori Platform Admin"

ENT_USER_EMAIL          = "cs@olist.local"
ENT_USER_PASSWORD       = "Pilot@2026"
ENT_USER_NAME           = "Olist Customer Success"

WORKSPACE_NAME          = "Olist Store"
ENTERPRISE_NAME         = "Olist Store"
ENTERPRISE_INDUSTRY     = "E-commerce / Marketplace"

# Subset size — keeps the script fast for pilot UAT seed.
SAMPLE_CUSTOMERS = 500


# ─── Helpers ─────────────────────────────────────────────────────


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames or [], list(reader)


def parse_money(v: str) -> float | None:
    """Olist prices are ASCII decimals — no thousand separators."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def parse_dt(v: str) -> datetime | None:
    if not v or v.strip() == "":
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(v, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


# ─── Step 1: Platform admin + workspace + enterprise + user ──────


def seed_identity(cur) -> None:
    print("[1/5] Seeding identity (admin + workspace + enterprise + user)")

    # Platform admin (P1 portal). Schema from migration 011.
    cur.execute(
        """
        INSERT INTO platform_admins
            (email, password_hash, full_name, role, is_active, mfa_enabled,
             invited_at, activated_at)
        VALUES (%s, %s, %s, 'SUPER_ADMIN', TRUE, FALSE, NOW(), NOW())
        ON CONFLICT (email) DO UPDATE SET
            password_hash = EXCLUDED.password_hash,
            full_name     = EXCLUDED.full_name,
            updated_at    = NOW()
        RETURNING admin_id
        """,
        (PLATFORM_ADMIN_EMAIL, hash_password(PLATFORM_ADMIN_PASSWORD), PLATFORM_ADMIN_NAME),
    )
    admin_id = cur.fetchone()[0]
    print(f"      platform_admin    {PLATFORM_ADMIN_EMAIL}  ({admin_id})")

    # Subscription plan — TRIAL must exist (seeded by 007 already).
    cur.execute(
        """
        INSERT INTO subscription_plans (plan_code, display_name, monthly_quota, price_vnd)
        VALUES ('TRIAL', 'Trial (free)', 100, 0)
        ON CONFLICT (plan_code) DO NOTHING
        """,
    )

    # Workspace
    cur.execute(
        """
        INSERT INTO workspaces (workspace_id, name, plan_code, status)
        VALUES (%s, %s, 'TRIAL', 'active')
        ON CONFLICT (workspace_id) DO UPDATE SET
            name       = EXCLUDED.name,
            updated_at = NOW()
        """,
        (str(WORKSPACE_ID), WORKSPACE_NAME),
    )
    print(f"      workspace         {WORKSPACE_NAME}  ({WORKSPACE_ID})")

    # Enterprise
    cur.execute(
        """
        INSERT INTO enterprises
            (enterprise_id, workspace_id, name, industry, timezone, locale, status)
        VALUES (%s, %s, %s, %s, 'America/Sao_Paulo', 'pt-BR', 'active')
        ON CONFLICT (enterprise_id) DO UPDATE SET
            name       = EXCLUDED.name,
            industry   = EXCLUDED.industry,
            updated_at = NOW()
        """,
        (str(ENTERPRISE_ID), str(WORKSPACE_ID), ENTERPRISE_NAME, ENTERPRISE_INDUSTRY),
    )
    print(f"      enterprise        {ENTERPRISE_NAME}  ({ENTERPRISE_ID})")

    # Enterprise user — MANAGER so all flows including F-033 advanced
    # approve are reachable.
    cur.execute(
        """
        INSERT INTO enterprise_users
            (user_id, enterprise_id, email, password_hash, full_name, role, status)
        VALUES (%s, %s, %s, %s, %s, 'MANAGER', 'active')
        ON CONFLICT (enterprise_id, email) DO UPDATE SET
            password_hash = EXCLUDED.password_hash,
            full_name     = EXCLUDED.full_name,
            updated_at    = NOW()
        """,
        (str(ENT_USER_ID), str(ENTERPRISE_ID), ENT_USER_EMAIL,
         hash_password(ENT_USER_PASSWORD), ENT_USER_NAME),
    )
    print(f"      enterprise_user   {ENT_USER_EMAIL}  (MANAGER)")


# ─── Step 2: Olist subset → Bronze/Silver ────────────────────────


# Per-file canonical mappings used to populate silver_rows.row_data
# with cleaned + canonicalised keys. Mirrors what
# config/language_dictionary.json + bronze/column_mapper would produce
# for Olist's English column names.

CANONICAL = {
    "olist_orders_dataset.csv": {
        "purpose": "transaction_list",
        "rename": {
            "order_id":           "order_id",
            "customer_id":        "customer_external_id",
            "order_status":       "status",
            "order_purchase_timestamp":         "purchase_date",
            "order_approved_at":                "approved_at",
            "order_delivered_carrier_date":     "shipped_at",
            "order_delivered_customer_date":    "delivered_at",
            "order_estimated_delivery_date":    "estimated_delivery",
        },
        "datetime_cols": [
            "order_purchase_timestamp", "order_approved_at",
            "order_delivered_carrier_date", "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
        "numeric_cols": [],
    },
    "olist_customers_dataset.csv": {
        "purpose": "customer_master",
        "rename": {
            "customer_id":              "customer_external_id",
            "customer_unique_id":       "person_unique_id",
            "customer_zip_code_prefix": "zip_prefix",
            "customer_city":            "city",
            "customer_state":           "state",
        },
        "datetime_cols": [],
        "numeric_cols": [],
    },
    "olist_order_items_dataset.csv": {
        "purpose": "order_lines",
        "rename": {
            "order_id":            "order_id",
            "order_item_id":       "line_no",
            "product_id":          "product_external_id",
            "seller_id":           "seller_external_id",
            "shipping_limit_date": "shipping_limit",
            "price":               "unit_price",
            "freight_value":       "shipping_fee",
        },
        "datetime_cols": ["shipping_limit_date"],
        "numeric_cols":  ["price", "freight_value"],
    },
    "olist_products_dataset.csv": {
        "purpose": "product_master",
        "rename": {
            "product_id":                "product_external_id",
            "product_category_name":     "category",
            "product_name_lenght":       "name_length",
            "product_description_lenght":"description_length",
            "product_photos_qty":        "photos_count",
            "product_weight_g":          "weight_grams",
            "product_length_cm":         "length_cm",
            "product_height_cm":         "height_cm",
            "product_width_cm":          "width_cm",
        },
        "datetime_cols": [],
        "numeric_cols": [
            "product_name_lenght", "product_description_lenght",
            "product_photos_qty", "product_weight_g",
            "product_length_cm", "product_height_cm", "product_width_cm",
        ],
    },
}


def load_file(cur, csv_name: str, rows_subset: list[dict]) -> None:
    """Insert pipeline_run + bronze_file + bronze_rows + silver_rows
    for one Olist CSV. status='analysis_complete' so it shows up in
    every "completed pipelines" list immediately."""
    spec  = CANONICAL[csv_name]
    path  = OLIST_DIR / csv_name
    sha   = file_sha256(path)
    size  = path.stat().st_size
    headers = list(rows_subset[0].keys()) if rows_subset else []

    run_id  = uuid.uuid4()
    file_id = uuid.uuid4()

    print(f"      -> {csv_name:<40s}  {len(rows_subset):>5d} rows  "
          f"purpose={spec['purpose']}")

    cur.execute(
        """
        INSERT INTO pipeline_runs
            (run_id, enterprise_id, uploaded_by, filename,
             original_size_bytes, file_sha256, mime_type,
             detected_language, sheet_count, row_count_bronze,
             row_count_silver, quality_score, status)
        VALUES (%s, %s, %s, %s, %s, %s, 'text/csv', 'pt', 1,
                %s, %s, 0.92, 'analysis_complete')
        """,
        (str(run_id), str(ENTERPRISE_ID), str(ENT_USER_ID),
         csv_name, size, sha, len(rows_subset), len(rows_subset)),
    )

    cur.execute(
        """
        INSERT INTO bronze_files
            (file_id, run_id, enterprise_id, sheet_name, sheet_index,
             detected_purpose, detected_language, header_row, row_count,
             col_count, file_format, metadata)
        VALUES (%s, %s, %s, %s, 0, %s, 'pt', 0, %s, %s, 'csv', %s)
        """,
        (str(file_id), str(run_id), str(ENTERPRISE_ID),
         csv_name.replace(".csv", ""), spec["purpose"],
         len(rows_subset), len(headers),
         Json({"source": "olist-kaggle", "subset": SAMPLE_CUSTOMERS})),
    )

    # Bronze rows — raw verbatim
    bronze_values = [
        (
            str(file_id),
            str(ENTERPRISE_ID),
            i,
            Json(row),
            hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest(),
        )
        for i, row in enumerate(rows_subset)
    ]
    execute_values(
        cur,
        """
        INSERT INTO bronze_rows
            (file_id, enterprise_id, row_index, raw_data, row_hash)
        VALUES %s
        RETURNING row_id
        """,
        bronze_values,
        page_size=1000,
    )
    bronze_ids = [r[0] for r in cur.fetchall()]

    # Silver rows — canonical rename + typing.
    silver_values = []
    for i, (row, bronze_id) in enumerate(zip(rows_subset, bronze_ids)):
        clean: dict = {}
        for src, dst in spec["rename"].items():
            v = row.get(src, "")
            if src in spec["datetime_cols"]:
                dt = parse_dt(v)
                clean[dst] = dt.isoformat() if dt else None
            elif src in spec["numeric_cols"]:
                clean[dst] = parse_money(v)
            else:
                clean[dst] = v if v != "" else None
        silver_values.append((
            str(file_id), str(ENTERPRISE_ID), bronze_id,
            i, Json(clean), ["normalize_dates", "rename_canonical"], 0.94,
            str(run_id),
        ))

    execute_values(
        cur,
        """
        INSERT INTO silver_rows
            (file_id, enterprise_id, bronze_row_id, row_index,
             row_data, applied_rules, quality_score, run_id)
        VALUES %s
        """,
        silver_values,
        page_size=1000,
    )


def seed_olist_files(cur) -> None:
    print("[2/5] Loading Olist CSVs through Bronze + Silver")

    if not OLIST_DIR.exists():
        sys.stderr.write(
            f"Olist dataset not found at {OLIST_DIR}\n"
            "Run first:\n"
            "  export KAGGLE_API_TOKEN=…\n"
            "  kaggle datasets download -d olistbr/brazilian-ecommerce "
            f"-p {OLIST_DIR.relative_to(REPO_ROOT)} --unzip\n"
        )
        sys.exit(1)

    # Pick a stable subset of customers + only their orders/items.
    cust_headers, cust_rows = read_csv(OLIST_DIR / "olist_customers_dataset.csv")
    cust_subset_rows = cust_rows[:SAMPLE_CUSTOMERS]
    customer_ids = {r["customer_id"] for r in cust_subset_rows}

    ord_headers, ord_rows = read_csv(OLIST_DIR / "olist_orders_dataset.csv")
    ord_subset_rows = [r for r in ord_rows if r["customer_id"] in customer_ids]
    order_ids = {r["order_id"] for r in ord_subset_rows}

    item_headers, item_rows = read_csv(OLIST_DIR / "olist_order_items_dataset.csv")
    item_subset_rows = [r for r in item_rows if r["order_id"] in order_ids]
    product_ids = {r["product_id"] for r in item_subset_rows}

    prod_headers, prod_rows = read_csv(OLIST_DIR / "olist_products_dataset.csv")
    prod_subset_rows = [r for r in prod_rows if r["product_id"] in product_ids]

    load_file(cur, "olist_customers_dataset.csv", cust_subset_rows)
    load_file(cur, "olist_orders_dataset.csv",    ord_subset_rows)
    load_file(cur, "olist_order_items_dataset.csv", item_subset_rows)
    load_file(cur, "olist_products_dataset.csv",  prod_subset_rows)


# ─── Step 3: Gold — per-customer revenue_at_risk ─────────────────


def seed_gold(cur) -> None:
    print("[3/5] Computing Gold: revenue_at_risk per customer")

    # Aggregate from silver rows the lazy way: join orders + items by
    # order_id at the JSONB layer. Postgres handles 500*~3 row joins
    # in <100ms — no need to push pandas back into Python.
    cur.execute(
        """
        WITH order_lines AS (
            SELECT s.row_data->>'order_id'             AS order_id,
                   (s.row_data->>'unit_price')::NUMERIC + COALESCE((s.row_data->>'shipping_fee')::NUMERIC, 0) AS line_total
              FROM silver_rows s
              JOIN bronze_files bf ON bf.file_id = s.file_id
             WHERE s.enterprise_id = %s
               AND bf.detected_purpose = 'order_lines'
        ),
        order_totals AS (
            SELECT order_id, SUM(line_total) AS order_total
              FROM order_lines GROUP BY order_id
        ),
        customer_orders AS (
            SELECT s.row_data->>'customer_external_id' AS customer_id,
                   (s.row_data->>'purchase_date')::TIMESTAMPTZ AS purchase_at,
                   ot.order_total
              FROM silver_rows s
              JOIN bronze_files bf ON bf.file_id = s.file_id
              JOIN order_totals ot ON ot.order_id = s.row_data->>'order_id'
             WHERE s.enterprise_id = %s
               AND bf.detected_purpose = 'transaction_list'
        ),
        agg AS (
            SELECT customer_id,
                   MAX(purchase_at)              AS last_purchase_at,
                   SUM(order_total)              AS total_purchases,
                   COUNT(*)                      AS purchase_count,
                   AVG(order_total)              AS avg_purchase_value
              FROM customer_orders
             WHERE customer_id IS NOT NULL
             GROUP BY customer_id
        )
        INSERT INTO gold_features
            (enterprise_id, customer_external_id,
             revenue_at_risk, last_purchase_at, total_purchases,
             purchase_count, avg_purchase_value, computed_at)
        SELECT %s, customer_id,
               -- F-032 rule: revenue_at_risk = avg purchase × 1, ONLY
               -- if the customer hasn't bought in 90+ days. Olist data
               -- is from 2017-2018 so anchor "today" at 2018-09-01 to
               -- yield realistic at-risk distribution against the
               -- dataset's natural cutoff.
               CASE WHEN last_purchase_at < ('2018-09-01'::TIMESTAMPTZ - INTERVAL '90 days')
                    THEN COALESCE(avg_purchase_value, 0)
                    ELSE 0
               END,
               last_purchase_at, total_purchases, purchase_count,
               avg_purchase_value, NOW()
          FROM agg
        ON CONFLICT (enterprise_id, customer_external_id) DO UPDATE SET
            revenue_at_risk    = EXCLUDED.revenue_at_risk,
            last_purchase_at   = EXCLUDED.last_purchase_at,
            total_purchases    = EXCLUDED.total_purchases,
            purchase_count     = EXCLUDED.purchase_count,
            avg_purchase_value = EXCLUDED.avg_purchase_value,
            computed_at        = NOW()
        """,
        (str(ENTERPRISE_ID), str(ENTERPRISE_ID), str(ENTERPRISE_ID)),
    )

    cur.execute(
        """
        SELECT COUNT(*),
               COUNT(*) FILTER (WHERE revenue_at_risk > 0),
               COALESCE(SUM(revenue_at_risk), 0)
          FROM gold_features
         WHERE enterprise_id = %s
        """,
        (str(ENTERPRISE_ID),),
    )
    total, at_risk, sum_revenue = cur.fetchone()
    print(f"      gold_features rows  {total:>5d}  (at-risk: {at_risk}, "
          f"revenue_at_risk total: {float(sum_revenue):.2f} R$)")


# ─── Step 4: Decision audit log seed (for /p2/decisions + F-041) ─


def seed_audit(cur) -> None:
    print("[4/5] Seeding sample decision_audit_log rows")

    samples = [
        {
            "decision_type":     "schema.column_map",
            "subject":            "customer_id",
            "chosen_value":       "customer_external_id",
            "confidence":         0.94,
            "method":             "fuzzy",
            "llm_provider":       None,
            "reasoning":          "Levenshtein 0.94 với 'customer_external_id' trong language_dictionary EN-PT.",
            "alternatives":       [{"value": "person_id", "score": 0.62}],
            "uncertainty_flags":  [],
        },
        {
            "decision_type":     "schema.column_map",
            "subject":            "order_purchase_timestamp",
            "chosen_value":       "purchase_date",
            "confidence":         0.88,
            "method":             "llm",
            "llm_provider":       "qwen-internal",
            "reasoning":          "LLM nhận diện cụm 'purchase_timestamp' là date của transaction.",
            "alternatives":       [{"value": "created_at", "score": 0.71}, {"value": "ordered_at", "score": 0.66}],
            "uncertainty_flags":  ["timezone_unspecified"],
        },
        {
            "decision_type":     "cleaning.rule_applied",
            "subject":            "rename_canonical@order_lines",
            "chosen_value":       "applied",
            "confidence":         0.99,
            "method":             "rule",
            "llm_provider":       None,
            "reasoning":          "Rule UNIVERSAL — rename per canonical schema confirmed by user.",
            "alternatives":       [],
            "uncertainty_flags":  [],
        },
        {
            "decision_type":     "analysis.intermediate",
            "subject":            "(seeded SWOT bootstrap)",
            "chosen_value":       "swot",
            "confidence":         0.82,
            "method":             "llm",
            "llm_provider":       "qwen-internal",
            "reasoning":          "Frame chiến lược cho mảng order_lines + customers — picked SWOT default.",
            "alternatives":       [{"value": "fishbone", "score": 0.55}],
            "uncertainty_flags":  [],
        },
        {
            "decision_type":     "schema.column_map",
            "subject":            "product_category_name",
            "chosen_value":       "category",
            "confidence":         0.71,
            "method":             "fuzzy",
            "llm_provider":       None,
            "reasoning":          "Match 'category' với token 'product_category_name' (normalised).",
            "alternatives":       [{"value": "tag", "score": 0.51}],
            "uncertainty_flags":  ["pt_translation_pending"],
        },
    ]
    rows = [
        (
            str(uuid.uuid4()), str(ENTERPRISE_ID), None,
            s["decision_type"], s["subject"], s["chosen_value"], s["confidence"],
            s["method"], Json(s["alternatives"]), s["uncertainty_flags"],
            s.get("llm_provider"), s["reasoning"],
        )
        for s in samples
    ]
    execute_values(
        cur,
        """
        INSERT INTO decision_audit_log
            (decision_id, enterprise_id, run_id, decision_type, subject,
             chosen_value, confidence, method, alternatives, uncertainty_flags,
             llm_provider, reasoning)
        VALUES %s
        """,
        rows,
        page_size=10,
    )
    print(f"      decision_audit_log rows  {len(rows)}")


# ─── --reset path ────────────────────────────────────────────────


def reset_olist(cur) -> None:
    """Drop the Olist artefacts so a fresh run is reproducible. Keeps
    the platform admin / workspace / enterprise / user (those upsert
    cleanly)."""
    print("[--reset] Wiping prior Olist seed artefacts (safe - keeps identity rows)")

    cur.execute(
        "DELETE FROM gold_features WHERE enterprise_id = %s",
        (str(ENTERPRISE_ID),),
    )
    # silver_rows + bronze_rows + bronze_files cascade off pipeline_runs.
    cur.execute(
        "DELETE FROM pipeline_runs WHERE enterprise_id = %s",
        (str(ENTERPRISE_ID),),
    )
    cur.execute(
        "DELETE FROM decision_audit_log WHERE enterprise_id = %s",
        (str(ENTERPRISE_ID),),
    )


# ─── Main ────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Seed pilot UAT with Olist data.")
    parser.add_argument("--reset", action="store_true",
                        help="Wipe prior Olist artefacts before seeding")
    args = parser.parse_args()

    print(f"Pilot seed - Olist Brazilian E-commerce")
    print(f"DATABASE_URL: {DATABASE_URL.split('@')[-1]}")  # don't log creds
    print()

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            if args.reset:
                reset_olist(cur)
            seed_identity(cur)
            seed_olist_files(cur)
            seed_gold(cur)
            seed_audit(cur)
        conn.commit()
        print()
        print("[5/5] DONE - login credentials")
        print("      Platform (P1):    " + PLATFORM_ADMIN_EMAIL + "  /  " + PLATFORM_ADMIN_PASSWORD)
        print("      Enterprise (P2):  " + ENT_USER_EMAIL + "  /  " + ENT_USER_PASSWORD)
        print(f"      Workspace:        {WORKSPACE_NAME}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
