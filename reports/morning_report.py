"""
Daily Morning Report
Runs at 07:30, queries gold_morning_report view, sends to Zalo group or email.

Usage:
  python reports/morning_report.py            # send report for yesterday
  python reports/morning_report.py --dry-run  # print to terminal, do not send
  python reports/morning_report.py --date 2026-04-20  # specific date
"""

import os
import sys
import argparse
import smtplib
import json
import requests
from datetime import date, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dotenv import load_dotenv
load_dotenv()

from utils.db import get_cursor
from utils.logger import log


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_report_data(report_date: date) -> list[dict]:
    """Query gold_morning_report for a specific date. Returns one row per store."""
    sql = """
        SELECT
            store,
            date,
            total,
            customer_count,
            bep_daily_target,
            bep_gap,
            bep_achieved,
            total_same_day_last_week,
            wow_change_pct,
            rolling_avg_28d
        FROM gold_morning_report
        WHERE date = %s
        ORDER BY store
    """
    with get_cursor() as cur:
        cur.execute(sql, (report_date,))
        return [dict(r) for r in cur.fetchall()]


def fetch_nb_customer_summary(report_date: date) -> dict:
    """Today's NB customer stats from silver layer."""
    sql = """
        SELECT
            COUNT(DISTINCT customer_id)                             AS total_customers,
            COUNT(DISTINCT CASE WHEN total_visits = 1
                  THEN customer_id END)                             AS new_customers,
            COUNT(DISTINCT CASE WHEN total_visits > 1
                  THEN customer_id END)                             AS returning_customers
        FROM silver_nb_customer_sessions s
        JOIN silver_nb_customers c USING (customer_id)
        WHERE visit_date = %s
    """
    with get_cursor() as cur:
        cur.execute(sql, (report_date,))
        row = cur.fetchone()
        return dict(row) if row else {}


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def fmt_money(amount) -> str:
    """Format VND: 12500000 → '12.5tr'"""
    if amount is None:
        return "N/A"
    try:
        val = float(amount)
        if val >= 1_000_000:
            return f"{val / 1_000_000:.1f}tr"
        if val >= 1_000:
            return f"{val / 1_000:.0f}k"
        return f"{val:.0f}"
    except (TypeError, ValueError):
        return "N/A"


def fmt_pct(val) -> str:
    if val is None:
        return ""
    sign = "↑" if float(val) >= 0 else "↓"
    return f"{sign}{abs(float(val)):.1f}%"


def fmt_bep(achieved: bool, gap) -> str:
    if achieved:
        return f"ĐẠT ✓ (+{fmt_money(gap)})"
    return f"CHƯA ĐẠT ✗ ({fmt_money(gap)})"


def build_message(report_date: date, rows: list[dict], nb_customers: dict) -> str:
    """Build plain-text Vietnamese message."""
    day_str = report_date.strftime("%d/%m/%Y")
    lines = [f"📊 BÁO CÁO NGÀY {day_str}"]
    lines.append("=" * 35)

    if not rows:
        lines.append("⚠️  Không có dữ liệu doanh thu cho ngày này.")
        lines.append("Kiểm tra lại file Excel đã được tải chưa.")
        return "\n".join(lines)

    for r in rows:
        store = r["store"]
        total = r["total"] or 0
        wow = r["wow_change_pct"]
        bep_ok = r["bep_achieved"]
        bep_gap = r["bep_gap"]
        count = r["customer_count"]

        # Store display name
        store_names = {
            "NB_MAIN": "🌸 NATURAL BEAUTY",
            "NB_FC_1": "🌸 NB FRANCHISE",
            "RJ_BAR": "🍸 RJ BAR",
            "BAR_MINI": "🍹 BAR MINI",
        }
        label = store_names.get(store, store)

        lines.append(f"\n{label}")
        lines.append(f"  Doanh thu: {fmt_money(total)}", )
        if wow is not None:
            lines.append(f"  So tuần trước: {fmt_pct(wow)}")
        if count:
            lines.append(f"  Lượt khách: {count}")
        lines.append(f"  BEP: {fmt_bep(bep_ok, bep_gap)}")

        # NB-specific: customer breakdown
        if store == "NB_MAIN" and nb_customers:
            new = nb_customers.get("new_customers", 0) or 0
            ret = nb_customers.get("returning_customers", 0) or 0
            if new + ret > 0:
                lines.append(f"  Mới: {new} | Quay lại: {ret}")

    lines.append("\n" + "=" * 35)

    # Check if any store missed BEP
    missed = [r["store"] for r in rows if not r["bep_achieved"] and r["total"] is not None]
    if missed:
        missed_names = ", ".join(missed)
        lines.append(f"⚠️  Chưa đạt BEP: {missed_names}")
    else:
        lines.append("✅ Tất cả cơ sở đã đạt BEP!")

    lines.append(f"\n🤖 Kaori Report · {report_date.strftime('%H:%M %d/%m')}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------

def send_zalo(message: str):
    token = os.getenv("ZALO_ACCESS_TOKEN")
    group_id = os.getenv("ZALO_GROUP_ID")
    if not token or not group_id:
        raise ValueError("ZALO_ACCESS_TOKEN and ZALO_GROUP_ID must be set in .env")

    url = "https://openapi.zalo.me/v2.0/oa/message"
    payload = {
        "recipient": {"group_id": group_id},
        "message": {"text": message},
    }
    headers = {
        "access_token": token,
        "Content-Type": "application/json",
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=10)
    resp.raise_for_status()
    result = resp.json()
    if result.get("error") != 0:
        raise RuntimeError(f"Zalo API error: {result}")
    log.info("Zalo message sent successfully")


def send_email(message: str):
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    recipients_raw = os.getenv("REPORT_RECIPIENTS", "")
    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]

    if not smtp_user or not smtp_pass:
        raise ValueError("SMTP_USER and SMTP_PASSWORD must be set in .env")
    if not recipients:
        raise ValueError("REPORT_RECIPIENTS must be set in .env")

    today_str = date.today().strftime("%d/%m/%Y")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Báo cáo Kaori — {today_str}"
    msg["From"] = smtp_user
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(message, "plain", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, recipients, msg.as_string())
    log.info(f"Email sent to: {recipients}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Send Kaori morning report")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print message to terminal, do not send")
    parser.add_argument("--date", help="Report date (YYYY-MM-DD, default: yesterday)")
    parser.add_argument("--method", choices=["zalo", "email", "both"],
                        help="Override REPORT_SEND_METHOD from .env")
    args = parser.parse_args()

    if args.date:
        from datetime import datetime
        report_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        report_date = date.today() - timedelta(days=1)

    log.info(f"Building report for: {report_date}")

    rows = fetch_report_data(report_date)
    nb_customers = fetch_nb_customer_summary(report_date)
    message = build_message(report_date, rows, nb_customers)

    if args.dry_run:
        print("\n" + "=" * 50)
        print(message)
        print("=" * 50)
        print("\n[DRY RUN] Message not sent.")
        return

    method = args.method or os.getenv("REPORT_SEND_METHOD", "zalo")
    sent = False

    if method in ("zalo", "both"):
        try:
            send_zalo(message)
            sent = True
        except Exception as e:
            log.error(f"Zalo send failed: {e}")

    if method in ("email", "both"):
        try:
            send_email(message)
            sent = True
        except Exception as e:
            log.error(f"Email send failed: {e}")

    if not sent:
        log.error("Report was not sent by any method. Check .env configuration.")
        sys.exit(1)


if __name__ == "__main__":
    main()
