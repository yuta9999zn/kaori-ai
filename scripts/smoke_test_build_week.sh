#!/bin/bash
# P15-S11 Tuần 1 — end-to-end smoke test for Build Week demo paths.
#
# Hits gateway:8080 with the vingroup@kaori.local / Admin@kaori1 user
# and walks the demo flow: org tree → create workflow → add cards →
# clone template → cross-link → folder → stats.
#
# Run: bash scripts/smoke_test_build_week.sh
# Exit 0 = all pass. Non-zero = first failure line printed.

set -u

GATEWAY=${GATEWAY:-http://localhost:8080}
EMAIL=${EMAIL:-vingroup@kaori.local}
PASSWORD=${PASSWORD:-Admin@kaori1}

red()   { printf "\033[31m%s\033[0m\n" "$*" >&2; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
blue()  { printf "\033[34m%s\033[0m\n" "$*"; }

pass=0
fail=0
fail_msgs=()

check() {
    local label="$1"
    local actual="$2"
    local expected="$3"
    if [[ "$actual" == "$expected" ]]; then
        green "  ✓ $label ($actual)"
        pass=$((pass + 1))
    else
        red "  ✗ $label (got $actual, expected $expected)"
        fail=$((fail + 1))
        fail_msgs+=("$label")
    fi
}

idem() { python -c 'import uuid; print(uuid.uuid4())'; }

# ─── 1. Login ────────────────────────────────────────────────────────

blue "=== Step 1 — login + get JWT ==="
LOGIN_RESP=$(curl -sf -X POST "$GATEWAY/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}") || {
    red "login failed"; exit 2;
}
JWT=$(echo "$LOGIN_RESP" | python -c "import sys,json; print(json.load(sys.stdin).get('accessToken',''))")
[[ -z "$JWT" ]] && { red "no JWT in response"; exit 2; }
green "  ✓ JWT received (${#JWT} chars)"

AUTH="-H \"Authorization: Bearer $JWT\""

# ─── 2. Corporate tree (smoke test 0 — baseline) ─────────────────────

blue "=== Step 2 — corporate-tree returns Vingroup ==="
CT_COUNT=$(curl -sf -H "Authorization: Bearer $JWT" "$GATEWAY/api/v1/corporate-tree" | python -c "import sys,json; print(len(json.load(sys.stdin)))")
check "tree nodes" "$CT_COUNT" "25"

# ─── 3. Workflow templates ───────────────────────────────────────────

blue "=== Step 3 — workflow-templates ==="
TPL_COUNT=$(curl -sf -H "Authorization: Bearer $JWT" "$GATEWAY/api/v1/workflow-templates" | python -c "import sys,json; print(len(json.load(sys.stdin)))")
check "template count" "$TPL_COUNT" "18"

# ─── 4. Smoke 6 — clone template ─────────────────────────────────────

blue "=== Step 4 — clone Lead Qualification template into Vinhomes Sales ==="
TPL_ID=$(curl -sf -H "Authorization: Bearer $JWT" "$GATEWAY/api/v1/workflow-templates" | python -c "import sys,json; ts=json.load(sys.stdin); print(next(t['template_id'] for t in ts if t['display_name']=='Lead Qualification Workflow'))")
VINHOMES_SALES=$(docker exec kaorisystem-postgres-1 psql -U kaori -d kaori -t -A -c "SELECT d.department_id FROM departments d JOIN enterprises e ON e.enterprise_id=d.enterprise_id WHERE e.name='Vinhomes' AND d.dept_type='sales' LIMIT 1")
CLONE_RESP=$(curl -s -w "\n%{http_code}" -X POST "$GATEWAY/api/v1/workflows/from-template" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(idem)" \
  -d "{\"template_id\":\"$TPL_ID\",\"department_id\":\"$VINHOMES_SALES\",\"custom_name\":\"SMOKE- Vinhomes Sales pipeline\"}")
CLONE_BODY=$(echo "$CLONE_RESP" | head -n -1)
CLONE_CODE=$(echo "$CLONE_RESP" | tail -n 1)
check "clone HTTP" "$CLONE_CODE" "201"
CLONED_WF=$(echo "$CLONE_BODY" | python -c "import sys,json; print(json.load(sys.stdin).get('workflow_id',''))" 2>/dev/null)
[[ -n "$CLONED_WF" ]] && green "  ✓ cloned workflow_id = $CLONED_WF"

# ─── 5. Smoke 5 — tree on cloned workflow ────────────────────────────

blue "=== Step 5 — tree on cloned workflow ==="
TREE_RESP=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer $JWT" "$GATEWAY/api/v1/workflows/$CLONED_WF/tree")
TREE_BODY=$(echo "$TREE_RESP" | head -n -1)
TREE_CODE=$(echo "$TREE_RESP" | tail -n 1)
check "tree HTTP" "$TREE_CODE" "200"
NODE_CNT=$(echo "$TREE_BODY" | python -c "import sys,json; print(len(json.load(sys.stdin).get('nodes',[])))" 2>/dev/null)
EDGE_CNT=$(echo "$TREE_BODY" | python -c "import sys,json; print(len(json.load(sys.stdin).get('edges',[])))" 2>/dev/null)
check "cloned nodes" "$NODE_CNT" "5"
check "cloned edges" "$EDGE_CNT" "4"

# ─── 6. Smoke 1 — workflow CRUD: create blank + delete ───────────────

blue "=== Step 6 — create blank workflow ==="
BLANK_RESP=$(curl -s -w "\n%{http_code}" -X POST "$GATEWAY/api/v1/workflows" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(idem)" \
  -d "{\"name\":\"SMOKE- blank\",\"department_id\":\"$VINHOMES_SALES\"}")
BLANK_BODY=$(echo "$BLANK_RESP" | head -n -1)
BLANK_CODE=$(echo "$BLANK_RESP" | tail -n 1)
check "blank create HTTP" "$BLANK_CODE" "201"
BLANK_WF=$(echo "$BLANK_BODY" | python -c "import sys,json; print(json.load(sys.stdin).get('workflow_id',''))" 2>/dev/null)

# ─── 7. Smoke 2 — node CRUD on blank workflow ────────────────────────

blue "=== Step 7 — add 3 cards to blank workflow ==="
NODE_IDS=()
for i in 1 2 3; do
    N_RESP=$(curl -s -w "\n%{http_code}" -X POST "$GATEWAY/api/v1/workflows/$BLANK_WF/nodes" \
      -H "Authorization: Bearer $JWT" \
      -H "Content-Type: application/json" \
      -H "Idempotency-Key: $(idem)" \
      -d "{\"title\":\"Step $i\",\"title_vi\":\"Step $i\",\"sequence_order\":$i,\"position_x\":$((100 + i*220)),\"position_y\":100}")
    N_CODE=$(echo "$N_RESP" | tail -n 1)
    N_BODY=$(echo "$N_RESP" | head -n -1)
    check "node $i HTTP" "$N_CODE" "201"
    NID=$(echo "$N_BODY" | python -c "import sys,json; print(json.load(sys.stdin).get('node_id',''))" 2>/dev/null)
    NODE_IDS+=("$NID")
done

blue "=== Step 7b — Path B node types (wait/sla/parallel/subworkflow) ==="
PATHB_TYPES=("wait_event" "sla_timer" "parallel_split" "subworkflow")
PATHB_NODE_IDS=()
for nt in "${PATHB_TYPES[@]}"; do
    PB_RESP=$(curl -s -w "\n%{http_code}" -X POST "$GATEWAY/api/v1/workflows/$BLANK_WF/nodes" \
      -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" -H "Idempotency-Key: $(idem)" \
      -d "{\"title\":\"PathB $nt\",\"title_vi\":\"PathB $nt\",\"node_type\":\"$nt\",\"sequence_order\":10,\"position_x\":50,\"position_y\":50}")
    PB_CODE=$(echo "$PB_RESP" | tail -n 1)
    PB_BODY=$(echo "$PB_RESP" | head -n -1)
    check "Path B $nt create HTTP" "$PB_CODE" "201"
    PB_NID=$(echo "$PB_BODY" | python -c "import sys,json; print(json.load(sys.stdin).get('node_id',''))" 2>/dev/null)
    PATHB_NODE_IDS+=("$PB_NID")
    # Verify node_type round-trips on read.
    PB_READ_TYPE=$(echo "$PB_BODY" | python -c "import sys,json; print(json.load(sys.stdin).get('node_type',''))" 2>/dev/null)
    check "Path B $nt round-trip" "$PB_READ_TYPE" "$nt"
done

blue "=== Step 8 — update node 1 title + hashtags ==="
U_RESP=$(curl -s -w "\n%{http_code}" -X PUT "$GATEWAY/api/v1/workflows/$BLANK_WF/nodes/${NODE_IDS[0]}" \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" -H "Idempotency-Key: $(idem)" \
  -d '{"title":"Tiep nhan lead","hashtags":["prospect_data","q1_campaign"]}')
U_CODE=$(echo "$U_RESP" | tail -n 1)
check "node update HTTP" "$U_CODE" "200"

# ─── 9. Smoke 3 — cross-workflow link ─────────────────────────────────

blue "=== Step 9 — cross-link cloned wf → blank wf ==="
CL_RESP=$(curl -s -w "\n%{http_code}" -X POST "$GATEWAY/api/v1/workflow-cross-links" \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" -H "Idempotency-Key: $(idem)" \
  -d "{\"source_workflow_id\":\"$CLONED_WF\",\"target_workflow_id\":\"$BLANK_WF\",\"link_type\":\"triggers\",\"label\":\"smoke-link\"}")
CL_CODE=$(echo "$CL_RESP" | tail -n 1)
check "cross-link HTTP" "$CL_CODE" "201"

# ─── 10. Smoke 4 — folder under a card ────────────────────────────────

blue "=== Step 10 — create folder under node 1 ==="
F_RESP=$(curl -s -w "\n%{http_code}" -X POST "$GATEWAY/api/v1/workflow-step-folders" \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" -H "Idempotency-Key: $(idem)" \
  -d "{\"workflow_id\":\"$BLANK_WF\",\"node_id\":\"${NODE_IDS[0]}\",\"name\":\"Q1-contracts\"}")
F_CODE=$(echo "$F_RESP" | tail -n 1)
check "folder HTTP" "$F_CODE" "201"

# ─── 11. Smoke 5 — stats endpoint on blank workflow ──────────────────

blue "=== Step 11 — workflow stats ==="
S_RESP=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer $JWT" "$GATEWAY/api/v1/workflows/$BLANK_WF/stats")
S_CODE=$(echo "$S_RESP" | tail -n 1)
S_BODY=$(echo "$S_RESP" | head -n -1)
check "stats HTTP" "$S_CODE" "200"
N_FROM_STATS=$(echo "$S_BODY" | python -c "import sys,json; print(json.load(sys.stdin).get('node_count',0))" 2>/dev/null)
F_FROM_STATS=$(echo "$S_BODY" | python -c "import sys,json; print(json.load(sys.stdin).get('folder_count',0))" 2>/dev/null)
CL_FROM_STATS=$(echo "$S_BODY" | python -c "import sys,json; print(json.load(sys.stdin).get('cross_links',{}).get('outgoing',0))" 2>/dev/null)
check "stats.node_count" "$N_FROM_STATS" "7"   # 3 step + 4 Path B nodes
check "stats.folder_count" "$F_FROM_STATS" "1"
# blank is the cross-link TARGET (incoming) from cloned, so outgoing should be 0
CL_IN=$(echo "$S_BODY" | python -c "import sys,json; print(json.load(sys.stdin).get('cross_links',{}).get('incoming',0))" 2>/dev/null)
check "stats.cross_links.incoming" "$CL_IN" "1"

# ─── 12. Cleanup ─────────────────────────────────────────────────────

blue "=== Step 12 — cleanup smoke workflows ==="
for wf in "$CLONED_WF" "$BLANK_WF"; do
    DEL_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$GATEWAY/api/v1/workflows/$wf" \
      -H "Authorization: Bearer $JWT" -H "Idempotency-Key: $(idem)")
    check "delete $wf" "$DEL_CODE" "204"
done

# ─── Final ───────────────────────────────────────────────────────────

echo
if (( fail == 0 )); then
    green "═══════════════════════════════"
    green "  SMOKE PASS: $pass / $pass"
    green "═══════════════════════════════"
    exit 0
else
    red "═══════════════════════════════"
    red "  SMOKE FAIL: $fail of $((pass + fail))"
    for m in "${fail_msgs[@]}"; do red "    - $m"; done
    red "═══════════════════════════════"
    exit 1
fi
