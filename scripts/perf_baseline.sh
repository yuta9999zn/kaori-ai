#!/usr/bin/env bash
# Performance baseline — establishes p50/p95/p99 for key endpoints.
#
# Use this BEFORE shipping perf optimization work so regressions show
# up as numerical deltas, not subjective "feels slower". Run it on the
# pilot host (anh's 16 GB laptop) to capture the operating envelope
# customers will experience until Phase 3 K8s cluster lands.
#
# Why apache-bench (`ab`) — ubiquitous, no install. For richer load
# patterns Phase 3 swaps to k6 or vegeta. The numbers from `ab` are
# good enough for "did p95 just regress 20%?" detection at our scale.
#
# Usage
# -----
#   ./scripts/perf_baseline.sh              # default 100 reqs × 10 concurrent
#   PERF_N=500 PERF_C=20 ./scripts/perf_baseline.sh
#
# Output is plain text; pipe to a dated file:
#   ./scripts/perf_baseline.sh > docs/perf/baseline-$(date +%Y%m%d).txt

set -euo pipefail

PERF_N="${PERF_N:-100}"       # number of requests per endpoint
PERF_C="${PERF_C:-10}"        # concurrent clients
GATEWAY="${GATEWAY:-http://localhost:8080}"
ORCH="${ORCH:-http://localhost:8093}"

# Seed values — change to match anh's dev env if different.
ENT="${PERF_ENT_ID:-f90e0cdb-dc0c-4b91-b86a-92c824aa1103}"
USR="${PERF_USER_ID:-dafbd87e-533a-4320-b6ec-7b905f7bf6d6}"

if ! command -v ab >/dev/null 2>&1; then
    echo "ERROR: apache-bench (ab) not found."
    echo "  Ubuntu/Debian: sudo apt install apache2-utils"
    echo "  Mac:           brew install ab"
    echo "  Windows:       choco install apache-bench  (or use WSL)"
    exit 1
fi

echo "=========================================================="
echo "Kaori perf baseline — $PERF_N requests × $PERF_C concurrent"
echo "Captured: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Gateway:  $GATEWAY"
echo "Tenant:   $ENT"
echo "=========================================================="

run() {
    local name="$1"
    local method="$2"
    local url="$3"
    local extra="${4:-}"
    echo
    echo "--- [$name] $method $url"
    if [ "$method" = "GET" ]; then
        ab -n "$PERF_N" -c "$PERF_C" \
           -H "X-Enterprise-ID: $ENT" \
           -H "X-User-ID: $USR" \
           $extra \
           "$url" 2>&1 | grep -E "Time per request|Requests per second|Percentage|^  50%|^  95%|^  99%|^Failed"
    else
        # POST with empty JSON body for endpoints that accept it
        ab -n "$PERF_N" -c "$PERF_C" \
           -H "X-Enterprise-ID: $ENT" \
           -H "X-User-ID: $USR" \
           -H "Content-Type: application/json" \
           -p /dev/null \
           $extra \
           "$url" 2>&1 | grep -E "Time per request|Requests per second|Percentage|^  50%|^  95%|^  99%|^Failed"
    fi
}

# ---- Read-only paths -------------------------------------------------

run "health-check" GET "$GATEWAY/health"

# Direct ai-orchestrator calls bypass gateway JwtAuthFilter — useful
# for measuring the service itself without auth overhead.
run "orch-roi-subscription"    GET "$ORCH/economics/roi/subscription"
run "orch-reencrypt-status"    GET "$ORCH/p2/auth/field-key/reencrypt/status"
run "orch-sso-google-start"    GET "$ORCH/p2/auth/sso/google/start?return_url=http://localhost:3000/cb"

# ---- Gateway-routed (with JWT bypass on pre-auth paths) --------------

run "gw-sso-google-start"      GET "$GATEWAY/api/v1/p2/auth/sso/google/start?return_url=http://localhost:3000/cb"

# ---- LLM-gateway guardrails ------------------------------------------

LLMGW="${LLMGW:-http://localhost:8095}"
echo
echo "--- [llm-validate-input] POST $LLMGW/guardrails/validate-input"
ab -n "$PERF_N" -c "$PERF_C" \
   -H "X-Enterprise-ID: $ENT" \
   -H "X-User-ID: $USR" \
   -H "Content-Type: application/json" \
   -p <(echo '{"text":"Doanh thu thang 5 tang 12%"}') \
   "$LLMGW/guardrails/validate-input" 2>&1 \
   | grep -E "Time per request|Requests per second|Percentage|^  50%|^  95%|^  99%|^Failed"

echo
echo "=========================================================="
echo "Baseline complete."
echo
echo "Save to: docs/perf/baseline-$(date +%Y%m%d).txt"
echo "Compare future runs via: diff -u <old> <new>"
echo "=========================================================="
