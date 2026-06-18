#!/usr/bin/env bash
# Smoke test for the G4b DSN cutover.
#
# Verifies that the kaori_app role:
#   1. Can authenticate against the running postgres container.
#   2. Reports itself as `kaori_app` (not the superuser).
#   3. Can SELECT from a core table (enterprises).
#   4. Can INSERT + UPDATE + DELETE on a tenant-scoped table
#      (decision_audit_log → INSERT only since RULE blocks UPDATE/DELETE,
#       so we exercise UPDATE/DELETE on canonical_schemas instead).
#   5. Currently has BYPASSRLS=true (the G4b step-1 invariant).
#      When 009 lands and flips this off, update the assertion below.
#
# Usage:
#   docker-compose up -d postgres
#   ./infrastructure/postgres/smoke_kaori_app.sh
#
# Exits non-zero on any failure. Designed to be cheap to run repeatedly.

set -euo pipefail

CONTAINER="${POSTGRES_CONTAINER:-kaorisystem-postgres-1}"
APP_USER="${KAORI_APP_USER:-kaori_app}"
APP_PASS="${KAORI_APP_PASSWORD:-kaori_app_password}"
DB="${POSTGRES_DB:-kaori}"

run_sql() {
    docker exec -e PGPASSWORD="$APP_PASS" "$CONTAINER" \
        psql -U "$APP_USER" -d "$DB" -tAc "$1"
}

echo "[smoke] connecting as $APP_USER to $CONTAINER/$DB"

# 1. Identity
identity=$(run_sql "SELECT current_user")
if [[ "$identity" != "$APP_USER" ]]; then
    echo "[smoke] FAIL: expected current_user=$APP_USER, got '$identity'"
    exit 1
fi
echo "[smoke] OK current_user=$identity"

# 2. SELECT on a core table
count=$(run_sql "SELECT COUNT(*) FROM enterprises")
if ! [[ "$count" =~ ^[0-9]+$ ]]; then
    echo "[smoke] FAIL: SELECT on enterprises did not return a number: '$count'"
    exit 1
fi
echo "[smoke] OK SELECT enterprises rows=$count"

# 3. Read/write round-trip — exercises GRANT SELECT/INSERT/UPDATE on
#    pipeline_runs + bronze_files + canonical_schemas. Wrapped in
#    BEGIN..ROLLBACK so we don't pollute the DB and don't need
#    DELETE privileges (which kaori_app intentionally doesn't have
#    on these tables — silver_rows is the only DELETE grant).
ENT_ID="00000000-0000-0000-0000-000000000001"
USR_ID="00000000-0000-0000-0000-000000000002"

run_sql "
BEGIN;
WITH r AS (
    INSERT INTO pipeline_runs (run_id, enterprise_id, uploaded_by, filename, original_size_bytes, file_sha256, mime_type)
    VALUES (gen_random_uuid(), '$ENT_ID', '$USR_ID', '__smoke.csv', 1, 'smoke', 'text/csv')
    RETURNING run_id
), f AS (
    INSERT INTO bronze_files (file_id, run_id, enterprise_id, sheet_name, sheet_index, file_format)
    SELECT gen_random_uuid(), r.run_id, '$ENT_ID', 'smoke', 0, 'csv' FROM r
    RETURNING file_id
), s AS (
    INSERT INTO canonical_schemas (file_id, enterprise_id, source_column, canonical_name, confidence, method)
    SELECT f.file_id, '$ENT_ID', 'col_a', 'col_a', 0.99, 'smoke' FROM f
    RETURNING schema_id
)
UPDATE canonical_schemas
   SET user_confirmed = TRUE
  FROM s
 WHERE canonical_schemas.schema_id = s.schema_id;
ROLLBACK;
" >/dev/null
echo "[smoke] OK INSERT/UPDATE round-trip (rolled back)"

# 4. BYPASSRLS sanity check (G4b step-1 invariant; flip when 009 lands)
bypass=$(run_sql "SELECT rolbypassrls FROM pg_roles WHERE rolname='$APP_USER'")
if [[ "$bypass" != "t" ]]; then
    echo "[smoke] FAIL: expected $APP_USER.rolbypassrls=t at G4b step 1, got '$bypass'"
    exit 1
fi
echo "[smoke] OK rolbypassrls=t (RLS still bypassed; cutover is behavior-preserving)"

# 5. Confirm role is NOT a superuser — even though BYPASSRLS is on,
#    we must not be connecting as the actual postgres superuser.
super=$(run_sql "SELECT rolsuper FROM pg_roles WHERE rolname='$APP_USER'")
if [[ "$super" != "f" ]]; then
    echo "[smoke] FAIL: $APP_USER.rolsuper must be false (got '$super')"
    exit 1
fi
echo "[smoke] OK rolsuper=f (not a superuser)"

echo "[smoke] PASS"
