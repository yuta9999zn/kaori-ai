# API codegen pipeline

> Sprint 6.5 (Phase 1 close-out) · Updated 2026-04-27

## What this is

A two-step pipeline that turns the backend's OpenAPI specs into TypeScript types the frontend can import. Goal: a BE signature change becomes a `tsc --noEmit` error in the FE at the next regen, instead of a 500 / wrong-shape silent breakage at runtime.

```
+----------+   dump     +-------------------+   gen    +--------------------------------+
| FastAPI  | ─────────► | docs/api-specs/   | ──────► | frontend/lib/api/types/*.d.ts  |
| / Spring |  scripts/  | *.openapi.json    |  npm    | (committed; consumed by typed  |
|  apps    |  dump_*    | (committed)       |  run    |  wrappers in lib/api/*.ts)     |
+----------+            +-------------------+  gen:api+--------------------------------+
```

Both spec files **and** generated `.d.ts` files are committed. CI uses `--check` modes to fail on drift — that gates BE-only PRs from accidentally desyncing the FE typing surface.

---

## Refresh workflow

After changing a backend handler signature (new query param, renamed body field, etc.):

```bash
# 1. Regenerate the FastAPI specs offline (no service boot required)
python scripts/dump_openapi.py                 # both pipeline + orchestrator
python scripts/dump_openapi.py pipeline        # one only

# 2. Regenerate the FE types from the specs
cd frontend && npm run gen:api                 # writes lib/api/types/*.d.ts

# 3. Fix any tsc errors that surface in FE callers
cd frontend && npm run typecheck

# 4. Commit both: the spec JSON AND the generated .d.ts
git add docs/api-specs/ frontend/lib/api/types/
```

---

## auth-service spec (special case)

Spring Boot's `springdoc-openapi-starter-webmvc-ui:2.5.0` exposes the spec at runtime — but unlike FastAPI we can't import-and-dump in a single Python process. Two ways to refresh `docs/api-specs/auth.openapi.json`:

### Option A — boot the service then curl

```bash
cd services/auth-service
mvn spring-boot:run                            # in one shell
curl -s http://localhost:8091/v3/api-docs \
  | python -m json.tool --sort-keys           \
  > ../../docs/api-specs/auth.openapi.json    # in another
# Ctrl-C the mvn shell when done
```

### Option B (Phase 2 follow-up) — wire `springdoc-openapi-maven-plugin`

Add the plugin to `auth-service/pom.xml`'s `<build>` block; it forks Spring Boot during `mvn verify`, hits `/v3/api-docs`, dumps to `target/openapi.json`, and stops the process. The FE codegen then reads from `target/` instead of `docs/api-specs/`. Skipped here because: it adds ~30 s to every `mvn verify`, and Phase 1 only has one auth-service consumer in the FE (login). Pick this up when there's a critical mass of typed `lib/api/auth*.ts` wrappers to keep in sync.

Until that lands, treat the auth spec as **manually refreshed** before each release. The pipeline + orchestrator specs are fully automated.

---

## Why types-only (NOT orval / hooks generation)

`openapi-typescript` produces ZERO runtime code — just `paths`, `components`, `operations` interfaces. We keep using the existing `api()` helper + react-query, which means:

1. **No vendor lock-in on the HTTP layer.** Today it's our hand-rolled `fetch` wrapper; tomorrow it could be axios, SWR, or whatever — the typed wrappers in `lib/api/*.ts` stay valid.
2. **Smaller bundle.** No generated mutation hooks per endpoint = less code to ship.
3. **Easier to adopt incrementally.** The `app/(app)/pipeline/page.tsx` PoC uses `pipelinesApi.list()` from `lib/api/pipelines.ts`; nothing else has to change at once.

When we hit the size where hand-writing wrappers becomes friction (probably mid-Phase 2 with 60+ endpoints), revisit and consider orval or react-query-codegen.

---

## What's checked in

| Path | Source of truth | Generator |
|---|---|---|
| `docs/api-specs/pipeline.openapi.json` | data-pipeline FastAPI app | `scripts/dump_openapi.py pipeline` |
| `docs/api-specs/orchestrator.openapi.json` | ai-orchestrator FastAPI app | `scripts/dump_openapi.py orchestrator` |
| `docs/api-specs/auth.openapi.json` | auth-service springdoc (manual) | curl, see Option A above |
| `frontend/lib/api/types/pipeline.d.ts` | `pipeline.openapi.json` | `npm run gen:api` |
| `frontend/lib/api/types/orchestrator.d.ts` | `orchestrator.openapi.json` | `npm run gen:api` |
| `frontend/lib/api/pipelines.ts` | hand-written wrapper using generated types | n/a |

---

## CI gates (current)

| Step | What | When it fails |
|---|---|---|
| `python scripts/dump_openapi.py --check` | regenerates spec to a tmp file, diffs against committed | a BE handler signature changed but the dev forgot to commit the new spec |
| `cd frontend && node scripts/gen-api-types.mjs --check` | regenerates types in memory, diffs against committed `.d.ts` | a spec changed but the dev forgot to commit refreshed types |
| `cd frontend && npm run typecheck` | runs `tsc --noEmit` against the FE tree | a typed wrapper (`lib/api/*.ts`) references a path/method/param the spec no longer exposes |

These three combined give us "BE-only PRs that desync the FE types" detection without requiring running services in CI.

---

## Escape hatch — when codegen breaks

If `openapi-typescript` chokes on a handler (rare; mostly happens with un-annotated FastAPI return types that translate to `dict`), the workflow is:

1. Open the offending spec; remove or simplify the schema for that endpoint by hand.
2. Re-run `npm run gen:api`.
3. **File a follow-up** in BACKLOG.md to add a Pydantic `response_model` to the BE handler so the next regen produces a clean schema.

Hand-editing the spec is OK as a temporary workaround — but it leaves a drift risk. The follow-up ticket is non-negotiable.

---

## Phase 2 roadmap

- Wire `springdoc-openapi-maven-plugin` for auth-service (Option B above) → fully automate all 3 services.
- Add Pydantic `response_model` to every FastAPI handler so response shapes are typed too (currently only request params are typed).
- Optionally: switch to orval once the typed-wrapper count crosses ~30 endpoints.
- Optionally: emit a single `paths` union and let callers `client.GET("/pipelines", { params })` — but only after MSW handlers are also typed against the same spec.
