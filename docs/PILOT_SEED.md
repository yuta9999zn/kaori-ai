# Pilot UAT Seed — Olist Brazilian E-commerce

> Goal: anh login P1 platform → switch xuống P2 enterprise → đã có data sạch để xem (Bronze + Silver + Gold + decision audit log) — không cần chạy wizard.
>
> Created: 2026-05-04 — references the live `main` branch.

---

## What anh gets after running

| Surface | What's there |
|---|---|
| **P1 platform login** (`/platform/login`) | `admin@kaori.platform` / `Admin@2026` — SUPER_ADMIN |
| **P1 workspaces list** (`/platform/workspaces`) | One workspace **"Olist Store"** with its enterprise + 1 user |
| **P2 enterprise login** (`/login`) | `cs@olist.local` / `Pilot@2026` — MANAGER role |
| **P2 pipelines** (`/p2/pipelines`) | 4 pipeline runs (customers, orders, order_items, products) all `analysis_complete` |
| **P2 data hub** (`/p2/data`) | Bronze / Silver / Gold cards populated; lineage drill-down works |
| **P2 customer at-risk** (`/p2/customers/at-risk`) | Filterable customer table + North Star tile (revenue_at_risk computed) |
| **P2 decisions** (`/p2/decisions`) | 5 sample audit rows (column mapping, cleaning, intermediate analysis) |
| **F-041 explainability** | Click any decision → "Tạo giải thích" works against the seeded reasoning fields |
| **F-035 cohort retention** | `/p2/analysis/basic` → pick "Cohort Retention" template + the orders pipeline → real heatmap from Olist data |

---

## Why Olist

Olist is a Brazilian e-commerce platform (founded 2015) — they published their full 2017–2018 marketplace dataset on Kaggle. CC BY-NC-SA 4.0 license. We use a 500-customer subset (~3000 orders, ~5000 line items, ~2000 unique products) — enough to drive every Sprint 2.1 feature without making the seed slow.

The dataset has:
- Real-shaped multi-table schema (customers / orders / order_items / products / sellers / payments / reviews / geolocation / category translations).
- Real timestamps spanning Sept 2016 → Aug 2018, so cohort retention pivots produce a meaningful M0/M1/M2/... matrix.
- Customer-id stability (`customer_id` per order vs. `customer_unique_id` person identity) — a realistic friction Kaori has to handle.

---

## One-time setup

### 1. Get a Kaggle API token

Go to https://www.kaggle.com/settings/account → API → "Create New Token". Kaggle prints `KAGGLE_API_TOKEN=KGAT_…`. Copy it.

### 2. Download the dataset

```powershell
# Windows PowerShell
$env:KAGGLE_API_TOKEN = "KGAT_…"           # paste your token
cd "D:\Kaori System"
kaggle datasets download -d olistbr/brazilian-ecommerce `
    -p infrastructure/seed/olist --unzip
```

```bash
# Linux / macOS / Git Bash
export KAGGLE_API_TOKEN=KGAT_…
cd /d/Kaori\ System
kaggle datasets download -d olistbr/brazilian-ecommerce \
    -p infrastructure/seed/olist --unzip
```

The download is ~42 MB compressed → 9 CSV files in `infrastructure/seed/olist/`. The folder is `.gitignore`'d (CC BY-NC-SA 4.0 — don't redistribute via the repo).

### 3. Install Python deps

```bash
python -m pip install psycopg2-binary bcrypt
```

### 4. Bring up Postgres

The seed needs only Postgres — auth-service / data-pipeline / etc. don't need to be running. Easiest:

```bash
docker compose up postgres -d
# Wait ~5s for the container to be ready
```

The default `docker-compose.yml` exposes `:5432` with creds `kaori_app / kaori_dev_password` (database `kaori`). The script reads `DATABASE_URL` env var; the default value matches compose:

```bash
# Default — already used if you don't set anything
DATABASE_URL=postgresql://kaori_app:kaori_dev_password@localhost:5432/kaori
```

If your local Postgres uses different creds (your phiên trước reported `kaori_dev_password` failed) set `DATABASE_URL` explicitly:

```bash
export DATABASE_URL="postgresql://<your_user>:<your_password>@localhost:5432/kaori"
```

### 5. Apply migrations (if not done already)

If anh chưa ever booted auth-service against this Postgres, the Flyway migrations haven't run yet. Either:

```bash
# Option a — boot auth-service once so it auto-applies migrations 001..036
docker compose up auth-service -d
# Wait ~30s for the migrations to land, then docker compose stop auth-service.

# Option b — apply manually with psql
for f in infrastructure/postgres/migrations/*.sql; do
    PGPASSWORD=kaori_dev_password psql -h localhost -U kaori_app -d kaori -f "$f"
done
```

### 6. Run the seed

```bash
python scripts/seed-pilot-olist.py
```

Expected output:

```
Pilot seed — Olist Brazilian E-commerce
DATABASE_URL: localhost:5432/kaori

[1/5] Seeding identity (admin + workspace + enterprise + user)
      platform_admin    admin@kaori.platform  (...)
      workspace         Olist Store  (00000000-...-000000011577)
      enterprise        Olist Store  (00000000-...-000000011577)
      enterprise_user   cs@olist.local  (MANAGER)
[2/5] Loading Olist CSVs through Bronze + Silver
      → olist_customers_dataset.csv             500 rows  purpose=customer_master
      → olist_orders_dataset.csv               5xx rows  purpose=transaction_list
      → olist_order_items_dataset.csv          7xx rows  purpose=order_lines
      → olist_products_dataset.csv             4xx rows  purpose=product_master
[3/5] Computing Gold: revenue_at_risk per customer
      gold_features rows  ~500  (at-risk: ~250, revenue_at_risk total: ~50000.00 R$)
[4/5] Seeding sample decision_audit_log rows
      decision_audit_log rows  5
[5/5] DONE — login credentials
      Platform (P1):    admin@kaori.platform  /  Admin@2026
      Enterprise (P2):  cs@olist.local  /  Pilot@2026
      Workspace:        Olist Store
```

Re-run safe: identity rows UPSERT; pipeline + audit rows would duplicate on re-run, so pass `--reset` to wipe the prior Olist artefacts first:

```bash
python scripts/seed-pilot-olist.py --reset
```

---

## Login flow check

1. **`http://localhost:3000/platform/login`** → `admin@kaori.platform` / `Admin@2026` → land on `/platform`
2. Click **Workspaces** → "Olist Store" row visible → click into the workspace
3. Click **Members** tab → see `cs@olist.local` (MANAGER)
4. Open a new incognito window → **`http://localhost:3000/login`** → `cs@olist.local` / `Pilot@2026`
5. Land on `/dashboard` of Olist Store enterprise
6. Click **Khám phá dữ liệu** (`/p2/data`) → 3 layer cards populated
7. Click **Khách hàng → Rủi ro** (`/p2/customers/at-risk`) → North Star tile + customer table

Then drive the rest of the UAT script in `docs/uat/SPRINT_2_1_CLOSEOUT.md` against this seeded data.

---

## Reset everything (full pilot reset)

```bash
# Drop the whole database and re-seed from scratch
docker compose down postgres
docker volume rm kaori-system_postgres-data    # name may differ — check `docker volume ls`
docker compose up postgres -d
# Re-apply migrations + re-run seed
```

Or surgical (keep other workspaces, just nuke Olist):

```bash
python scripts/seed-pilot-olist.py --reset
```

`--reset` wipes pipeline_runs / bronze_files / bronze_rows / silver_rows / gold_features / decision_audit_log scoped to the Olist enterprise; re-creates them on the same run. Identity rows (admin / workspace / enterprise / user) stay — they UPSERT idempotently.

---

## Security notes

- **Default passwords** (`Admin@2026`, `Pilot@2026`) are pilot-only. Rotate before pointing the seed at any non-localhost Postgres.
- **The CSV bundle** is CC BY-NC-SA 4.0. Fine for pilot demos; commercial productionisation needs a different dataset.
- **The Kaggle token** is in your local env only. Don't commit. Rotate after the seed if anh shared it on a shared screen.

---

## Future enhancements (not in this PR)

- Persist a few completed `analysis_runs` rows from F-033 multi-tier so `/p2/analysis` recent-runs section seeds populated (not just MSW fixture).
- Persist 2–3 framework runs (SWOT/Fishbone) from F-034.
- Persist a sample report from F-038 + an alert rule from F-037.

These are nice-to-have for a more complete demo; the current seed already drives every UAT scenario in `docs/uat/SPRINT_2_1_CLOSEOUT.md`. If pilot users ask "I clicked /p2/analysis but it's empty", come back and add them.
