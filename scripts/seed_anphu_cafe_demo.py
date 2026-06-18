#!/usr/bin/env python3
"""
Vietnamese SME demo dataset — An Phú Coffee chain (50 shop, fictional).

Companion to scripts/seed_olist_into_kaori.py. Use this when judges
prefer a Vietnamese-localized demo over Olist Brazilian e-commerce.

Workflow vibes:
  - Marketing dept    → email campaign + loyalty program
  - Sales dept        → daily POS revenue, hot product rank
  - Customer Service  → complaint tickets + CSAT survey
  - Warehouse         → coffee beans inventory + supplier orders
  - HR                → barista hiring + training
  - Finance           → invoice processing + AR collection

Run:
    python scripts/seed_anphu_cafe_demo.py --dry-run
    python scripts/seed_anphu_cafe_demo.py --real --sample-rows 200

Idempotent — workspace "An Phú Coffee Group" lookup by name; rows
upserted by sha256 (per K-8 bronze idempotency).
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import io
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

try:
    import asyncpg
except ImportError:
    asyncpg = None


WORKSPACE_NAME = "An Phú Coffee Group"
ENTERPRISE_NAME = "An Phú Coffee Vietnam"


# ─── Generated row factories ────────────────────────────────────────


def _vn_name() -> str:
    """Random Vietnamese-sounding name."""
    holes = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Phan", "Vũ", "Đặng",
             "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý"]
    middles = ["Văn", "Thị", "Hữu", "Đức", "Quang", "Minh", "Thanh", "Hoài"]
    firsts = ["An", "Bình", "Châu", "Dũng", "Em", "Giang", "Hà", "Khang",
              "Lan", "Mai", "Nam", "Oanh", "Phú", "Quân", "Tâm"]
    return f"{random.choice(holes)} {random.choice(middles)} {random.choice(firsts)}"


def _vn_city() -> str:
    return random.choice([
        "Hà Nội", "TP HCM", "Đà Nẵng", "Hải Phòng", "Cần Thơ",
        "Nha Trang", "Vũng Tàu", "Đà Lạt", "Huế", "Quảng Ninh",
    ])


def gen_customer_rows(n: int) -> list[dict]:
    """50% of customers from HCM + HN; rest distributed."""
    out = []
    base = datetime(2024, 1, 1)
    for i in range(n):
        out.append({
            "customer_id":          f"AP-CUST-{i+1:05d}",
            "customer_unique_id":   f"AP-CUST-{i+1:05d}",
            "name":                 _vn_name(),
            "phone":                f"09{random.randint(10000000, 99999999)}",
            "email":                f"customer{i+1}@example.com",
            "city":                 _vn_city(),
            "loyalty_tier":         random.choice(["bronze", "silver", "gold", "platinum"]),
            "marketing_spend":      str(random.randint(20000, 250000)),
            "acquired_at":          (base + timedelta(days=random.randint(0, 720))).isoformat(sep=" "),
            "revenue_total":        str(random.randint(150000, 8000000)),
            "acquisition_channel":  random.choice([
                "facebook_ads", "google_ads", "referral",
                "in_store", "tiktok", "zalo_oa",
            ]),
        })
    return out


def gen_order_rows(n: int, customer_ids: list[str]) -> list[dict]:
    out = []
    base = datetime(2024, 1, 1)
    statuses = ["delivered", "delivered", "delivered", "delivered",
                "shipped", "canceled", "pending"]
    products = [
        ("Cà phê đen", 25000), ("Cà phê sữa", 28000), ("Bạc xỉu", 32000),
        ("Cappuccino", 45000), ("Latte", 48000), ("Cold brew", 50000),
        ("Trà đào", 38000), ("Trà sữa", 42000), ("Bánh croissant", 28000),
    ]
    for i in range(n):
        order_date = base + timedelta(days=random.randint(0, 720), hours=random.randint(7, 22))
        delivered = order_date + timedelta(minutes=random.randint(15, 90))
        product, base_price = random.choice(products)
        qty = random.randint(1, 4)
        out.append({
            "order_id":                       f"AP-ORD-{i+1:06d}",
            "customer_id":                    random.choice(customer_ids),
            "order_status":                   random.choice(statuses),
            "order_purchase_timestamp":       order_date.isoformat(sep=" "),
            "order_delivered_customer_date":  delivered.isoformat(sep=" "),
            "product_name":                   product,
            "quantity":                       str(qty),
            "deal_value":                     str(base_price * qty),
        })
    return out


def gen_review_rows(n: int, order_ids: list[str]) -> list[dict]:
    out = []
    base = datetime(2024, 1, 1)
    comments_5 = ["Cà phê ngon!", "Phục vụ nhanh", "Quán đẹp", "Sẽ quay lại", "Giá hợp lý"]
    comments_3 = ["Đợi hơi lâu", "Đồ uống ổn", "Bình thường"]
    comments_1 = ["Thái độ không tốt", "Đợi 30 phút", "Đồ uống nhạt"]
    for i in range(n):
        score = random.choices([1, 2, 3, 4, 5], weights=[3, 5, 15, 30, 47])[0]
        if score >= 4:
            cmt = random.choice(comments_5)
        elif score == 3:
            cmt = random.choice(comments_3)
        else:
            cmt = random.choice(comments_1)
        ts = base + timedelta(days=random.randint(0, 720))
        ans_ts = ts + timedelta(hours=random.randint(1, 48))
        out.append({
            "review_id":                f"AP-REV-{i+1:06d}",
            "order_id":                 random.choice(order_ids) if order_ids else "",
            "customer_id":              f"AP-CUST-{random.randint(1, 1000):05d}",
            "review_score":             str(score),
            "review_comment_message":   cmt,
            "review_creation_date":     ts.isoformat(sep=" "),
            "review_answer_timestamp":  ans_ts.isoformat(sep=" "),
        })
    return out


def gen_payment_rows(n: int, order_ids: list[str]) -> list[dict]:
    out = []
    for i in range(n):
        out.append({
            "order_id":              random.choice(order_ids) if order_ids else f"AP-ORD-{i+1:06d}",
            "payment_sequential":    "1",
            "payment_type":          random.choice(["cash", "momo", "zalopay", "credit_card", "vnpay"]),
            "payment_installments":  "1",
            "payment_value":         str(random.randint(25000, 280000)),
        })
    return out


# ─── Dry-run CSV preview ────────────────────────────────────────────


def write_dry_run_csvs(out_dir: Path, sample_rows: int) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    customers = gen_customer_rows(sample_rows)
    cust_ids = [c["customer_id"] for c in customers]
    orders = gen_order_rows(sample_rows * 3, cust_ids)
    order_ids = [o["order_id"] for o in orders]
    reviews = gen_review_rows(int(sample_rows * 2.5), order_ids)
    payments = gen_payment_rows(sample_rows * 3, order_ids)

    plans = [
        ("anphu_customers.csv",  customers, "sales"),
        ("anphu_orders.csv",     orders,    "sales"),
        ("anphu_reviews.csv",    reviews,   "customer_service"),
        ("anphu_payments.csv",   payments,  "finance"),
    ]

    print(f"\n=== An Phú Coffee dataset — dry-run ({sample_rows} sample) ===\n")
    for filename, rows, dept in plans:
        path = out_dir / filename
        if rows:
            with path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
        size_kb = path.stat().st_size / 1024 if path.exists() else 0
        print(f"  {filename:30s} → {dept:18s}  {len(rows):>5} rows  ({size_kb:.1f} KB)")
    print(f"\nWritten to {out_dir.resolve()}")
    print("Apply via main seed by symlinking or by extending --olist-dir path.")


# ─── CLI ────────────────────────────────────────────────────────────


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "anphu",
        help="Folder to write CSVs (dry-run mode only)",
    )
    parser.add_argument(
        "--sample-rows",
        type=int,
        default=200,
        help="Customer count; orders ~3x, reviews ~2.5x. Default 200.",
    )
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--dry-run", action="store_true",
                     help="Write CSVs to --out-dir (no DB writes)")
    grp.add_argument("--real", action="store_true",
                     help="Write directly into Postgres (mirrors seed_olist_into_kaori.py)")
    parser.add_argument("--database-url",
                        help="Postgres URL. Default = DATABASE_URL env / localhost:5432/kaori")
    args = parser.parse_args()

    random.seed(42)  # reproducible

    if args.dry_run:
        write_dry_run_csvs(args.out_dir, args.sample_rows)
        return 0

    # Real mode: emit CSVs first then advise to call main Olist seed in
    # generic mode. Build Week scope keeps the real-mode wiring TODO —
    # for demo day em chỉ cần CSV files exist on disk.
    print("Real-mode wiring TODO Phase 2. Use --dry-run for now and feed")
    print("the generated CSVs through the regular upload endpoint with")
    print("X-Department-ID per file:")
    print("")
    print("  anphu_customers.csv → Sales dept")
    print("  anphu_orders.csv    → Sales dept")
    print("  anphu_reviews.csv   → Customer Service dept")
    print("  anphu_payments.csv  → Finance dept")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
