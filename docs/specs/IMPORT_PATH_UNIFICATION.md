# ai-orchestrator import-path unification — analysis + fix plan

> **Status:** ANALYZED, not yet executed (2026-05-24). This is the "item 4" of
> anh's 4-item post-merge plan. Attempted a quick fix, found it is a pervasive
> refactor that **must not be done piecemeal** (that is exactly the PR #247
> trap), reverted, and captured the proper plan here for a dedicated effort.

## The bug (latent, not active)

`services/ai-orchestrator/Dockerfile` sets `PYTHONPATH=/app:/app/ai_orchestrator`
and launches `uvicorn ai_orchestrator.main:app`. Because **both** roots are on
the path, the same file `shared/db.py` can be imported under **two different
module identities**:

- `ai_orchestrator.shared.db`  (via `/app` root — what app relative imports `from ..shared.db` resolve to)
- `shared.db`                  (via `/app/ai_orchestrator` root — top-level)

Two module objects for one file → duplicated module-level state (connection
pools, registered classes, singletons). When code on one identity hands an
object to code on the other, `isinstance` fails / a second pool is opened.
This is the class-duplication crash from PR #247 (memory
`feedback_python_module_identity_pythonpath`).

## Why it's pervasive (and why piecemeal makes it worse)

The two identities are **both in active use** and entangled:

| Surface | Current convention |
|---|---|
| App code (36 files) | relative `from ..shared.x` → `ai_orchestrator.shared.x` |
| **Intra-`shared/`** modules (ai_governance, lineage, policy_engine, tenant_quotas, log_context) | top-level `from shared.x` |
| App-local function imports (routers/lineage, reasoning/ontology/governance, reasoning/memory/postgres_l3) | top-level `from shared.x` |
| **Chaos tests** (≈10 files) | `import shared.db as _db; _db.fn = mock` — monkeypatch targets the **top-level** `shared.db` identity |
| Most unit tests | `from ai_orchestrator.shared.x` |

Changing only some files (e.g. flipping 6 `from shared.` → `from ..shared.`)
leaves a single file mixed and shifts which identity a given symbol resolves
to — silently breaking a chaos test's monkeypatch or a pool's sharing. The fix
is only safe **all-at-once, with the full chaos suite as the gate**.

## The fix (one canonical identity)

Two coherent options — pick one, convert **everything**, run the whole suite:

**Option A — canonical = top-level `shared` (recommended, least churn).**
- Make the app boot with `shared` as the top-level identity: `WORKDIR /app/ai_orchestrator`, `PYTHONPATH=/app/ai_orchestrator`, `CMD uvicorn main:app`.
- Convert the 36 app files' `from ..shared.x` → `from shared.x`; convert unit tests' `from ai_orchestrator.shared.x` → `from shared.x`; conftest registers `shared`/`routers`/… directly (drop the `ai_orchestrator` synthetic).
- Chaos-test monkeypatches (`import shared.db`) already match — **no change**, which is the big risk reducer.

**Option B — canonical = `ai_orchestrator.shared`.**
- Drop `/app/ai_orchestrator` from `PYTHONPATH` (keep only `/app`).
- Convert every top-level `from shared.x` / `import shared.db` (intra-shared + app-local + chaos tests) → `ai_orchestrator.shared.x`. This rewrites the chaos monkeypatch targets — higher risk.

## Verification gate (mandatory)

```bash
cd services/ai-orchestrator
python -m pytest tests/ -q           # full suite, ALL ~2273 tests
python -m pytest tests/ -k chaos -q  # chaos subset especially — monkeypatch identity
# + rebuild the image and smoke the running container (pools initialise once).
```

Do not merge on a partial pass. The whole point is that the two identities
must collapse to one with **zero** behavioural change.

## Recommendation

Schedule as a **dedicated PR**. It is mechanical but wide; the value is removing
a latent prod-crash, not a feature, so it can wait for a low-traffic window. Do
NOT fold it into an unrelated PR.

## ✅ RESOLVED — shipped 2026-05-24 (PR #251, Option B)

Done via **Option B** (canonical `ai_orchestrator.shared`), not the originally
floated Option A. Re-analysis showed Option A was *not* least-churn: 64 app
files already use relative `from ..shared` which resolves to
`ai_orchestrator.shared`, so converging there left those untouched and avoided
changing the Docker boot (`WORKDIR`/`PYTHONPATH`/`CMD`) — lower risk than
rewriting 64 imports + the boot. The `/app/ai_orchestrator` PYTHONPATH entry was
**kept** (reasoning/workflow_runtime/org_intel still use top-level), so a
`tests/test_no_toplevel_shared_import.py` guard locks `shared` against
regression instead.

- Scope: **`shared` only** (the proven PR #247 crash). 43 files converted +
  guard test.
- Verified 0 behaviour change: baseline 2565 passed/1 skipped == after-refactor
  2565/1; chaos subset 69/69; CI service-env (python/ai-orchestrator) green.
- **Follow-up still open:** `reasoning` / `workflow_runtime` / `org_intel` carry
  the same latent dual pattern (top-level + relative imports). Not yet unified —
  bounded out of #251 to keep blast radius small. Same playbook applies when
  scheduled.
