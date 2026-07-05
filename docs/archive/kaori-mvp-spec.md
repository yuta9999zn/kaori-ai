# Kaori MVP Spec
**Status:** Build-ready  
**Date:** 2026-04-21  
**Customer:** Natural Beauty Japan (NB) + RJ Group (bar)  
**Team assumption:** 1–2 engineers  
**Hard deadline:** 6 weeks to working product in customer's hands

---

## 1. Critical Evaluation of Source Documents

### What the documents say vs. what is actually true

| Document | What it claims | Reality |
|---|---|---|
| BRD v2.0 | Target: 5 paying SME pilot customers, churn prediction SaaS | Actual customer hired a dedicated IT engineer — they did not buy SaaS |
| PRD v4.0 | Multi-tenant B2B platform, Kafka, Feature Store, SHAP, $2K–$30K/month USD | NB/RJ is a Vietnamese beauty salon + bar chain needing Excel replacement |
| Feature Tree v2.5 | 986 features across 67 modules | None of it is built. Zero lines of code exist. |
| IT Engineer JD | Defines exactly what NB/RJ needs in 6 weeks | This is the only grounded, validated requirement in the entire document set |

### Contradictions between documents

1. **BRD says "no-code churn wizard"** — NB/RJ JD says "bank statement auto-classification + daily revenue aggregation." These are completely different problems.
2. **BRD targets non-technical business owners who upload CSV** — NB/RJ has a dedicated IT engineer on payroll. They are not the self-service SaaS persona.
3. **PRD prices in USD at enterprise tiers** — NB/RJ is a 20–500 employee Vietnamese SME. These are not the same customer.
4. **PRD says Kafka is a core architectural principle** — NB/RJ needs a Python cron job and a Looker Studio dashboard.
5. **BRD says "churn prediction is the beachhead use case"** — NB/RJ JD never mentions churn. Their pain is: manual Excel consolidation, no morning visibility, no bank statement categorization.

### What is over-engineered and must be ignored

Cut everything. Start from the JD.

- Kafka, Feature Store, continuous learning loop → irrelevant
- SHAP/LIME explainability → irrelevant  
- Multi-tenant isolation → irrelevant (1 customer)
- Platform admin / billing engine → irrelevant
- No-code wizard → irrelevant (they have an IT engineer)
- Churn prediction → not the current pain, maybe week 7+
- Workflow builder, alert rules, AI agent system → irrelevant
- SOC 2, EU AI Act, ISO 27001 → irrelevant at this stage
- Finance / logistics verticals → irrelevant

---

## 2. The Real Problem (NB/RJ)

NB/RJ Group runs two businesses:
- **Natural Beauty Japan (NB)**: hair removal salon + FC franchise locations
- **RJ BAR + BAR MINI**: bar/entertainment venues

**Their actual pain, in order of urgency:**

1. **No daily visibility** — managers cannot see revenue numbers in the morning without manually compiling Excel files. Decision-making is delayed.
2. **Manual data consolidation** — daily revenue, bank statements, customer records, shift logs all live in separate Excel files maintained by different people. No single source of truth.
3. **Bank statement is unclassified** — LPBank exports are raw. No one knows which transactions are customer payments vs. cost vs. other income without manual review.
4. **No customer history database** — NB customer service records exist in Excel per session, not consolidated by customer. Cannot answer "how many customers came back this month?"
5. **No anomaly detection** — if one store's revenue drops or goes below break-even, no one knows until the monthly meeting.

**This is a data infrastructure and BI problem, not an AI/ML problem.**

---

## 3. What Is Validated vs. Unvalidated

### Validated (directly from NB/RJ JD — real customer, real requirement)
- Daily revenue visibility dashboard is needed
- Bank statement classification needs automation
- Customer master DB for NB needs to be built
- Morning auto-report to management (Zalo/Email) is needed
- Data is already in Excel files — no new data collection needed
- Customer has IT budget (they hired a full-time engineer)
- 6-week timeline is the customer's own expectation

### Unvalidated (from BRD/PRD — no customer evidence)
- Churn prediction is what SMEs want to pay for
- Non-technical business owners will use a 5-step wizard
- 60%+ pilot → paid conversion rate
- $2K–$30K/month USD pricing for Vietnam SMEs
- Continuous learning loop improves model accuracy in production
- The same platform works for retail, finance, and logistics

---

## 4. Correct Product Strategy

**Do not build a SaaS. Build a working data product for NB/RJ.**

The strategy is: solve NB/RJ's exact problems in 6 weeks, produce measurable results, use that proof to define what the next customer needs. If the next customer has the same problems, extract reusable components then. Do not extract them now.

**The question that matters at this stage:**  
"Does this customer use this product every day and find it valuable?"  
Not: "Could this scale to 100 tenants?"

---

## 5. MVP: Exact Features

### Include (must build)

**Module 1 — Data Ingestion Pipeline**
- Python ETL that reads NB/RJ's existing Excel files:
  - `Daily_revenue.xlsx` → daily revenue table (cash/transfer/card by store)
  - `Management_report.xlsx` → monthly P&L, costs, salary
  - `Balance.xlsx` → bank balances, receivables/payables
  - `NB_customer_history.xlsx` → customer service + payment records
  - `Equipment_usage.xlsx` → device usage by staff/area/day
  - `Shift_Management_NB.xlsm` → staff shift records
- Loads into PostgreSQL on each run (idempotent — re-running is safe)
- Runs manually first, cron later

**Module 2 — Bank Statement Classifier**
- Python script: reads LPBank CSV/Excel export
- Classifies each transaction row: `CUSTOMER_PAYMENT | OPERATING_COST | PAYROLL | TAX | OTHER`
- Rule-based first (regex on description field), ML upgrade later if needed
- Output: classified transactions table in PostgreSQL

**Module 3 — NB Customer Master DB**
- Deduplicate and consolidate NB customer records from `NB_customer_history.xlsx`
- One row per customer: `customer_id, name, phone, first_visit, last_visit, total_visits, total_spent, services_history[]`
- Incremental update: new session records append, existing customer records merge

**Module 4 — Dashboard (Looker Studio or simple web UI)**
- **NB Dashboard**: daily revenue (cash/transfer/card), customer count, new vs. returning ratio, BEP progress, monthly cumulative
- **RJ Dashboard**: revenue by cast/staff, fixed customer count, weekly growth rate
- One dashboard per business, both connected to same PostgreSQL
- Anomaly flag: highlight any day/week where revenue is >20% below 4-week average

**Module 5 — Morning Auto-Report**
- Python cron (runs 7:30 AM daily)
- Computes: yesterday's revenue, vs. same day last week, vs. BEP daily target
- Sends formatted message to Zalo group (via Zalo Bot API) OR email
- Format: plain text, no jargon — just numbers management cares about

### Cut completely (do not build)
- Churn prediction model
- No-code upload wizard
- User authentication / login system (IT engineer runs it directly)
- Billing / subscription management
- Multi-tenant anything
- Kafka, Redis, queues
- REST API (no external consumers yet)
- SHAP explainability
- Workflow builder
- Any React/Next.js frontend (use Looker Studio — zero build time)

### Delay to after validation
- Customer churn scoring (needs 6+ months of NB customer data first)
- RJ cast performance model
- Automated anomaly alerts (after dashboard is trusted)
- Web-based UI (only if Looker Studio is insufficient)
- Second customer onboarding

---

## 6. Success Metric

**The MVP works when:**
1. Managers open the dashboard every morning without being asked — no prompting needed
2. Morning auto-report arrives in Zalo before 8 AM, numbers match reality
3. IT engineer does not have to manually compile any Excel file to answer "how did we do yesterday?"
4. Bank statement classification accuracy ≥ 90% on a manual spot-check of 100 transactions
5. Customer master DB has zero duplicate customer entries for NB

**The MVP fails if:**
- Dashboard is opened less than 3x per week by any manager after week 2
- Auto-report is turned off or ignored
- Manager still asks IT engineer to manually pull numbers

---

## 7. System Design

### Architecture

```
Excel Files (local / Google Drive)
         │
         ▼
  [ETL Scripts — Python]
  pandas + openpyxl
         │
         ▼
  [PostgreSQL — single DB]
  tables: daily_revenue, customers,
          bank_transactions, equipment_usage,
          staff_shifts, monthly_pnl
         │
         ├──────────────────────────────┐
         ▼                              ▼
  [Looker Studio]              [Morning Report — Python cron]
  Connected via pg connector   Runs 7:30 AM daily
  NB dashboard + RJ dashboard  → Zalo Bot API or SMTP
```

No web server. No API. No Docker required in week 1. Scripts run on the IT engineer's machine or a single small VPS.

### Stack

| Component | Choice | Reason |
|---|---|---|
| ETL / processing | Python 3.11 + pandas + openpyxl | IT engineer's JD lists Python as required skill |
| Database | PostgreSQL 15 | Free, reliable, works with Looker Studio |
| Dashboards | Looker Studio (Google) | Free, zero build time, connects directly to PostgreSQL |
| Scheduling | Windows Task Scheduler or cron (Linux VPS) | Simple, no infra needed |
| Reporting | Python + Zalo Bot API or SMTP | Zalo is what the team already uses |
| Version control | Git (GitHub private repo) | Standard |

### Data Flow

```
INPUT:
  Excel files → Python reads with openpyxl/pandas
  LPBank CSV export → Python classifier

PROCESSING:
  - Normalize column names to English snake_case
  - Parse dates to ISO format
  - Deduplicate on natural keys (store + date + type for revenue; customer phone for master DB)
  - Classify bank transactions with regex rules
  - Compute derived fields: daily_bep_gap, customer_return_rate, etc.

STORAGE:
  PostgreSQL tables (schema below)

OUTPUT:
  - Looker Studio reads from PostgreSQL (real-time query)
  - Morning report: Python queries PostgreSQL → formats → sends

```

### Database Schema (minimal)

```sql
-- Core revenue fact
CREATE TABLE daily_revenue (
  id SERIAL PRIMARY KEY,
  store VARCHAR(20),          -- 'NB_MAIN', 'NB_FC_1', 'RJ_BAR', 'BAR_MINI'
  date DATE,
  cash NUMERIC(12,0),
  transfer NUMERIC(12,0),
  card NUMERIC(12,0),
  total NUMERIC(12,0) GENERATED ALWAYS AS (cash + transfer + card) STORED,
  customer_count INTEGER,
  UNIQUE(store, date)
);

-- NB customer master
CREATE TABLE nb_customers (
  customer_id VARCHAR(50) PRIMARY KEY,
  phone VARCHAR(20),
  name VARCHAR(100),
  first_visit DATE,
  last_visit DATE,
  total_visits INTEGER,
  total_spent NUMERIC(12,0),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Bank transactions
CREATE TABLE bank_transactions (
  id SERIAL PRIMARY KEY,
  txn_date DATE,
  amount NUMERIC(12,0),
  direction VARCHAR(10),       -- 'IN' | 'OUT'
  description TEXT,
  category VARCHAR(30),        -- 'CUSTOMER_PAYMENT' | 'OPERATING_COST' | 'PAYROLL' | 'TAX' | 'OTHER'
  is_manual_override BOOLEAN DEFAULT FALSE,
  raw_description TEXT
);

-- Monthly P&L summary
CREATE TABLE monthly_pnl (
  id SERIAL PRIMARY KEY,
  store VARCHAR(20),
  year_month CHAR(7),          -- '2026-04'
  revenue NUMERIC(12,0),
  cost_goods NUMERIC(12,0),
  cost_salary NUMERIC(12,0),
  cost_rent NUMERIC(12,0),
  cost_other NUMERIC(12,0),
  net_profit NUMERIC(12,0),
  bep_target NUMERIC(12,0),
  UNIQUE(store, year_month)
);

-- Staff shifts (for utilization analysis later)
CREATE TABLE staff_shifts (
  id SERIAL PRIMARY KEY,
  store VARCHAR(20),
  staff_name VARCHAR(100),
  shift_date DATE,
  hours_worked NUMERIC(4,1)
);
```

---

## 8. Build Plan — Week by Week

### Week 1: Data Inventory + ETL Foundation
**Goal:** All existing Excel data is in PostgreSQL. No dashboard yet.

- [ ] Clone repo, set up Python project structure (`/etl`, `/reports`, `/sql`)
- [ ] Create PostgreSQL schema (run `schema.sql`)
- [ ] Write ETL: `load_daily_revenue.py` — reads all Daily_revenue Excel files, loads to `daily_revenue`
- [ ] Write ETL: `load_monthly_pnl.py` — reads Management_report.xlsx → `monthly_pnl`
- [ ] Write ETL: `load_nb_customers.py` — reads NB customer history, deduplicates by phone → `nb_customers`
- [ ] Write ETL: `load_staff_shifts.py` — reads Shift_Management_NB.xlsm → `staff_shifts`
- [ ] All ETLs are idempotent (safe to re-run)
- [ ] Verify row counts match source Excel manually

**Deliverable:** Run `python etl/load_all.py` → all data in PostgreSQL, verified.

---

### Week 2: Bank Statement Classifier + Customer DB Polish
**Goal:** LPBank statements are auto-classified. Customer master DB is clean.

- [ ] Write `classify_bank.py`:
  - Reads LPBank CSV export
  - Rule engine: regex match on description → category
  - Rules: keywords for each category (e.g., "LUONG", "TIEN LUONG" → PAYROLL; store name patterns → CUSTOMER_PAYMENT)
  - Unmatched rows → `OTHER` with flag for manual review
  - Load to `bank_transactions`
- [ ] Build rule file: `bank_rules.json` (easy to edit without code changes)
- [ ] Spot-check 100 transactions manually → target ≥90% correct
- [ ] Fix any duplicate customer issues in `nb_customers`
- [ ] Add `customer_return_rate` computed view: customers with >1 visit in last 90 days / total customers

**Deliverable:** IT engineer can run `python etl/classify_bank.py bank_export.csv` and get classified output.

---

### Week 3: NB Dashboard in Looker Studio
**Goal:** NB managers can see live numbers without opening Excel.

- [ ] Connect Looker Studio to PostgreSQL (via Community Connector or direct BigQuery import if needed)
- [ ] Build NB Dashboard:
  - Card: Today's revenue (total + breakdown cash/transfer/card)
  - Card: Today's customer count
  - Card: New vs. returning customers this month (%)
  - Bar chart: daily revenue last 30 days vs. BEP daily target line
  - Line chart: monthly revenue cumulative vs. BEP monthly target
  - Table: last 7 days revenue by store
- [ ] Anomaly highlight: days where revenue < 80% of 4-week daily average → red
- [ ] Share dashboard link with NB manager — get first feedback

**Deliverable:** NB manager opens dashboard on phone/laptop and reads numbers without asking IT engineer.

---

### Week 4: RJ Dashboard + Morning Auto-Report
**Goal:** RJ bar data is visible. Management gets auto-report every morning.

- [ ] Collect RJ data structure (RJ BAR + BAR MINI Excel files — JD says "details will be shared later")
- [ ] Write ETL for RJ: `load_rj_revenue.py` → same `daily_revenue` table with store = 'RJ_BAR' / 'BAR_MINI'
- [ ] Build RJ Dashboard in Looker Studio:
  - Revenue by cast/staff (bar chart)
  - Fixed customer count trend (weekly)
  - Week-over-week growth rate
- [ ] Write `morning_report.py`:
  - Query yesterday's `daily_revenue` for all stores
  - Compare vs. same day last week + vs. daily BEP target
  - Format as plain Vietnamese text:
    ```
    [NB Báo cáo sáng - 21/04/2026]
    Doanh thu hôm qua: 12.5tr (↑8% vs tuần trước)
    Khách: 23 người | Mới: 5 | Quay lại: 18
    BEP hôm nay: 10tr → ĐẠT ✓

    [RJ BAR]
    Doanh thu: 8.2tr (↓3% vs tuần trước)
    BEP: 7tr → ĐẠT ✓
    ```
  - Send via Zalo Bot API (or SMTP fallback)
- [ ] Set up cron / Task Scheduler: runs at 7:30 AM daily

**Deliverable:** Managers receive Zalo message at 7:30 AM with yesterday's numbers. RJ dashboard live.

---

### Week 5: Stabilize + Handle Edge Cases
**Goal:** System runs reliably without IT engineer babysitting it.

- [ ] Handle missing data days gracefully (holiday, no sales → show 0, not error)
- [ ] Add logging: each ETL run logs to `etl_log` table (run_time, file_processed, rows_loaded, errors)
- [ ] Add data freshness indicator to dashboards: "Last updated: X hours ago"
- [ ] Fix any dashboard issues from manager feedback (Week 3–4 feedback)
- [ ] Document run procedure for IT engineer (1-page runbook)
- [ ] Test: what happens if Excel file format changes? Add column-name validation with clear error messages
- [ ] Manual bank statement review workflow: `OTHER` category transactions → simple CSV export for manager to reclassify → import override back to DB

**Deliverable:** System has been running for 2+ weeks with no manual intervention. Errors are caught and logged.

---

### Week 6: Validate + Decide Next Step
**Goal:** Confirm product is used, decide what to build next.

- [ ] Interview NB manager + RJ manager: what's missing, what's wrong, what they now want
- [ ] Count: how many times dashboard was opened this week (Looker Studio has usage stats)
- [ ] Count: was morning report read? (Zalo read receipt, or ask directly)
- [ ] Measure: did IT engineer have to manually pull any data this week? If yes, why?
- [ ] Decision gate:
  - If managers use dashboard daily → customer retention analysis is next (NB has the data)
  - If morning report is trusted → add anomaly alert (push notification on bad days)
  - If data quality issues dominate → fix pipeline before adding features
  - If customer wants a web UI instead of Looker Studio → build simple Next.js dashboard
- [ ] Write short internal retrospective: what worked, what did not, what the customer actually cares about

**Deliverable:** Written decision on what Phase 2 is, based on real usage data — not planning documents.

---

## 9. Project Structure

```
D:\Kaori System\
├── kaori-mvp-spec.md          ← this file
├── README.md
├── .env.example               ← DB_URL, ZALO_TOKEN, etc.
├── requirements.txt
│
├── sql/
│   └── schema.sql             ← all CREATE TABLE statements
│
├── etl/
│   ├── load_all.py            ← runs all loaders in order
│   ├── load_daily_revenue.py
│   ├── load_monthly_pnl.py
│   ├── load_nb_customers.py
│   ├── load_staff_shifts.py
│   ├── load_rj_revenue.py
│   └── classify_bank.py
│
├── config/
│   └── bank_rules.json        ← classification rules (editable)
│
├── reports/
│   └── morning_report.py      ← daily cron job
│
└── utils/
    ├── db.py                  ← DB connection helper
    └── logger.py              ← ETL run logging
```

---

## 10. What This Is NOT

This spec intentionally excludes:

- SaaS multi-tenancy
- User authentication / login
- REST API
- Kafka, Redis, queues
- Churn prediction model
- No-code wizard
- Billing or subscriptions
- Any cloud-specific infrastructure
- React/Next.js frontend (Looker Studio replaces it for now)

These may be relevant for a second customer or a productized version. They are not relevant today.

---

## 11. Risks

| Risk | Mitigation |
|---|---|
| RJ data structure is unknown (JD says "will be shared later") | Week 4 depends on this — get it in Week 1 even if RJ dashboard is Week 4 |
| LPBank export format changes | Rule file is external JSON, easy to update without code changes |
| Looker Studio can't connect to PostgreSQL directly | Use Google Cloud SQL proxy or export daily snapshot to Google Sheets as fallback |
| Excel files are inconsistently formatted month to month | Column-name validation at ETL entry point — fail loudly with clear message, not silently |
| Managers don't adopt the dashboard | Involve one manager in Week 3 review session — build what they actually look at |

---

*End of spec. Everything above this line is the MVP. Everything not in this file is Phase 2 or later.*
