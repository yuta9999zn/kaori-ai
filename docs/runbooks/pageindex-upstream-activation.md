# PageIndex upstream activation

> **Status:** `UpstreamPageIndexTreeBuilder` ships in this commit, untested against a real PageIndex clone. Stub + Fixture builders shipped P15-S10 D7 (commit `bd0a2e2`+). This runbook is the procedure when anh wants real LLM-driven hierarchical retrieval to land for a tenant.
> **Severity:** P2 (opt-in per tenant; degrades gracefully to Stub/Fixture if upstream unavailable)
> **Reference:** ADR-0019 (vectorless tree retrieval) · `services/ai-orchestrator/reasoning/rag/pageindex/`

## What's currently shipped

| Component | State | Where |
|---|---|---|
| `StubPageIndexTreeBuilder` (deterministic 2-level synthetic tree) | Live | `pageindex/tree_builder.py` |
| `FixturePageIndexTreeBuilder` (load pre-computed JSON) | Live | same file |
| `UpstreamPageIndexTreeBuilder` (subprocess wrap of `run_pageindex.py`) | Live (untested vs real repo) | same file |
| `StubPageIndexRetriever` | Live | `pageindex/retriever.py` |
| `PageIndexEngine` (RAG router engine) | Live with stubs | `rag/engines/pageindex_engine.py` |
| `pageindex_trees` cache table (mig 045) | Live | `infrastructure/postgres/migrations/` |
| OPENAI_API_KEY plumbing through llm-gateway | **NOT** done — PageIndex calls OpenAI directly | requires Step 4 |

The new `UpstreamPageIndexTreeBuilder` is a thin subprocess wrap; it does not import the `pageindex` Python package (which is CLI-first per the README). Em invoke `python3 run_pageindex.py --pdf_path X --model Y` and parse the stdout JSON.

## When to activate

Trigger any of:
- A pilot customer ships a long PDF (>20 pages — contracts, policies, manuals) that DocSage Schema Discovery struggles to chunk well
- The default `StubPageIndexTreeBuilder` is showing up in production answers (synthetic citations like `[STUB] Document root`) — operator-visible degradation
- Customer requires page-range citations on legal/compliance docs (regulator expects "Article 5.2, p.12-14" format)

Otherwise keep Stub/Fixture — Phase 1.5+ pilot has shipped fine on Stub for 3 weeks.

## K-rule context (READ BEFORE activating)

| Rule | What this activation does |
|---|---|
| K-3 (LLM via llm-gateway only) | **VIOLATED** on the upstream path. PageIndex talks to OpenAI directly via its own SDK. This is acceptable ONLY for tenants who explicitly opt in to upstream PageIndex; em document the trade-off in the customer contract |
| K-4 (consent_external) | Tenant MUST have `consent_external=true` AND a per-tenant config flag `pageindex_upstream_enabled=true`. Caller-side check responsibility |
| K-5 (PII redaction) | PageIndex reads the PDF as-is. If the source PDF carries PII, the OpenAI SDK sees it. Tenants who require K-5 strict must NOT activate upstream — stay on Stub/Fixture |
| K-17 (side_effect_class) | `external` — declares LLM call. Caller wires the cache + idempotency per `pageindex_trees` table |

If anh can't say YES to all 4 invariants for a given tenant, **do not activate upstream for that tenant**. Stub/Fixture stays the default.

## Step 1 — Clone the PageIndex repo

```bash
# Pick a path that's mounted into the ai-orchestrator pod (em recommend
# /opt/pageindex on K8s; ~/.kaori/pageindex on docker-compose).
mkdir -p /opt/pageindex
git clone https://github.com/VectifyAI/PageIndex.git /opt/pageindex
cd /opt/pageindex

# Pin a known-good commit (em verified the README schema as of
# the doc em fetched 2026-05-19). Replace HEAD with the SHA you
# actually tested against.
git checkout <commit-sha-from-your-acceptance-run>

# Install upstream's deps (PageIndex requires pdfplumber, openai,
# tiktoken, etc — already in em's tree but upstream may have
# version pins).
pip install -r requirements.txt
```

## Step 2 — Provide OPENAI_API_KEY

Em do NOT keep OPENAI_API_KEY in the global env — that would expose
the key to every service in the pod. Instead, route it via Vault per
tenant (or per environment):

```bash
# Seed in prod Vault
vault kv put \
  -mount=secret \
  pageindex/openai_api_key \
  value=sk-prod-pageindex-...
```

Then ai-orchestrator reads from Vault when instantiating the builder
(em add this wire-up at activation time per tenant; default factory
in `pageindex_engine.py` continues to use Stub).

## Step 3 — Wire UpstreamPageIndexTreeBuilder per tenant

```python
# Pseudo-code — adapt to em's tenant-config bootstrapping
from reasoning.rag.pageindex import UpstreamPageIndexTreeBuilder
from reasoning.rag.engines.pageindex_engine import PageIndexEngine

if tenant.pageindex_upstream_enabled and tenant.consent_external:
    api_key = vault.read("secret/pageindex/openai_api_key")["value"]
    builder = UpstreamPageIndexTreeBuilder(
        repo_path="/opt/pageindex",
        openai_api_key=api_key,
        model="gpt-4o-mini",     # tune per tenant SLA
        timeout_seconds=300,
    )
    engine = PageIndexEngine(builder=builder)   # retriever stays stub today
else:
    engine = PageIndexEngine()   # all defaults — Stub builder + Stub retriever
```

`StubPageIndexRetriever` is still in use even when the upstream builder
is wired — RAG-PAGEINDEX-002 (real retrieval over the upstream tree)
is a separate ship, gated behind acceptance of this Step 3 path.

## Step 4 — Smoke test against a real PDF

```bash
# Pick a tenant with consent_external=true + pageindex_upstream_enabled=true
# Write a known-good PDF to a tempfile reachable from the ai-orch process
TENANT=11111111-1111-1111-1111-111111111111
PDF=/tmp/sample-contract.pdf

# Trigger the upstream path via /rag/answer with the upstream-engine
# flag (en/whichever the router exposes once Step 3 lands)
curl -X POST https://api.kaori.io/api/v1/rag/answer \
  -H "Authorization: Bearer <admin-jwt>" \
  -H "X-Enterprise-ID: $TENANT" \
  -H "Content-Type: application/json" \
  -d '{
    "query_text": "What is the liability cap?",
    "engine_hint": "pageindex",
    "doc_path": "'"$PDF"'"
  }'
```

Watch ai-orchestrator logs:

```bash
docker logs kaori-ai-orchestrator-1 --tail 100 | grep -i pageindex
# Expect:
#   pageindex.build.start tenant=...
#   pageindex.subprocess.ok exit=0 stdout_chars=...
#   pageindex.tree.built nodes=...
```

Citation in the response should reference real pages (e.g. `p.12-14`),
NOT `[STUB]` text.

## Step 5 — Monitor cost + latency

```bash
# In Grafana, watch:
#   kaori_pageindex_build_seconds (NEW — em add the histogram when
#                                   activating; today it doesn't exist
#                                   because Stub is instant)
#   OpenAI billing dashboard
```

PageIndex on a 50-page PDF at gpt-4o-mini ≈ ~$0.05 per build. Cache
in `pageindex_trees` (mig 045) means em pay this once per
(tenant_id, doc_sha256). For pilot Olist with ~20 long docs, total
cost ≈ $1; production at 100 customers × ~50 docs each ≈ $250-500.

## Holster (rollback to Stub)

```python
# Tenant config flip — no code change needed
tenant.pageindex_upstream_enabled = False
# Restart ai-orchestrator pod or wait for next config refresh
```

If anh wants a global rollback (e.g. OpenAI billing spike), set the
env var `PAGEINDEX_FORCE_STUB=true` in the ai-orchestrator deployment
— em add the check at the factory level (TODO when activating
production). Cache rows in `pageindex_trees` survive the rollback +
become valid again when anh re-flip.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `UpstreamPageIndexUnavailable: runner not found at /opt/pageindex/run_pageindex.py` | Repo not cloned / wrong path | Re-run Step 1; confirm `ls /opt/pageindex/run_pageindex.py` |
| `UpstreamPageIndexUnavailable: openai_api_key is empty` | Vault read returned empty / wrong path | Step 2 — confirm `vault kv get secret/pageindex/openai_api_key` returns value |
| `RuntimeError: PageIndex exited 1 ... openai.AuthenticationError` | Wrong / expired OpenAI key | Rotate in Vault per Step 2; restart ai-orch |
| `RuntimeError: PageIndex build timed out after 300s` | Huge PDF (>200 pages) or slow OpenAI | Bump `timeout_seconds` on the per-tenant builder; or pre-build via offline script |
| `RuntimeError: did not contain parseable JSON` | PageIndex upstream version changed output format | Pin commit at Step 1; em's `_node_from_upstream` handles common variations but a major bump may need a code patch |
| Citation still says `[STUB]` | Tenant didn't actually get the upstream builder wired | Re-check Step 3; log `engine_used` in `/rag/answer` response |
| OpenAI cost spike alert | Cache miss rate too high — tenant uploading new PDFs faster than em can pin trees | Check `pageindex_trees` row count; verify cache key (tenant_id, doc_sha256) collisions absent |

## What this runbook does NOT cover

- **RAG-PAGEINDEX-002** (real retrieval over upstream tree) — separate ship, gated behind this activation
- **Per-tenant OPENAI_API_KEY** (one customer brings their own key) — Phase 3, requires Vault per-tenant path
- **Streaming response** — PageIndex synchronous; first byte time = full build time + retrieval. Not ideal for interactive UI; acceptable for batch QA
- **Vendor swap to Claude** — PageIndex hardcodes OpenAI today. If em want Claude-via-PageIndex, would need upstream PR or a fork (out of scope per ADR-0025 "don't fork" sibling pattern)

## Related

- ADR-0019 — vectorless tree retrieval decision
- ADR-0025 — em's MinerU "borrow patterns" sibling decision (PageIndex is the opposite call: em DO wrap upstream, not port — because PageIndex's algorithm = LLM traversal, not pure heuristic, can't reasonably re-implement)
- mig 045 — `pageindex_trees` cache schema
- `services/ai-orchestrator/reasoning/rag/pageindex/tree_builder.py` — implementation
- `services/ai-orchestrator/tests/test_pageindex_upstream_builder.py` — 25 tests pinning subprocess contract + node mapping
- VectifyAI/PageIndex — <https://github.com/VectifyAI/PageIndex>
