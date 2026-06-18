# Platform Portal — Cream/Gold Re-skin Migration

> Generated: 2026-05-18 (Plan B: re-skin `/platform/*` in place)
> Production route tree: `/platform/*` under `frontend/app/platform/`
> Re-skinned: 1 page (workspaces) · Remaining: ~20 pages

## What this is

`/platform/*` is Kaori's production platform-admin portal. It already ships
21 routes wired to `auth-service` Java controllers via cursor-paginated
react-query. This sprint is **purely a visual layer migration** — swap the
v0 sidebar (`--color-*` token vocab) for the cream/gold/Playfair design
system the rest of the portals use (`--primary-gold` / `--bg-sidebar`
vocab from the platform-tenant templates).

A parallel `/p1/*` route tree was briefly scaffolded earlier in this
session — that was a duplicate of `/platform/*` em did not realise existed.
It was deleted in the same commit that landed Plan B.

## Shared infrastructure (kept from /p1 scaffolding)

| File | Purpose |
|---|---|
| `components/platform/foundation.tsx` | Re-export of `components/p2/foundation.tsx`. Both portals share the cream/gold/Playfair token set. |
| `components/platform/navigation.ts` | `NAV_TREE` for the platform-admin sidebar — all paths normalised to `/platform/*`. Role-gated children (SUPER_ADMIN). |
| `components/platform/shell.tsx` | Strict TS `<AppShell>` + `<PageHeader>`. Uses Next.js `<Link>` + `usePathname()` + `useAuth`. Logout redirects to `/platform/login`. |
| `components/platform/templates/` | 31 design-reference templates (auto-converted JSX→TSX). Carry `@ts-nocheck`. Not consumed at runtime — they are anh's design source. |

> **Rename complete 2026-05-23 (Step 4 of FE restructure sequence)** — `components/p1/`
> renamed to `components/platform/` via `git mv`. All 27 import call-sites + `globals.css`
> + this report updated to `@/components/platform/*`. URL/runtime impact: zero (no route
> change). History preserved through git mv detection.

## Platform layout

`frontend/app/platform/layout.tsx` (was 266 lines of inline sidebar →
now 50 lines):
- Auth gate preserved: redirect to `/platform/login` if user role ∉
  {SUPER_ADMIN, ADMIN, SUPPORT}.
- `/platform/login` renders without shell (public).
- Every other `/platform/*` path renders inside `<AppShell>` from
  `components/platform/shell`.
- Sub-layouts under `/platform/billing`, `/platform/security`, and
  `/platform/workspaces/[id]` keep rendering their own section headers
  and tab bars inside the AppShell's `<main>`.

## Graduated pages — all 21 done as of 2026-05-18

Every `/platform/*` route now uses the cream/gold `--primary-gold` /
`--bg-sidebar` / `--text-primary` token vocab via `components/platform/foundation`
+ `components/platform/shell`. Data fetching, mutations, react-query keys,
route logic preserved across the migration; only the visual layer
changed.

| Route group | Pages | Commit |
|---|---|---|
| Dashboard          | `/platform`                                                            | `065324a` |
| Workspaces detail  | `new` · `[id]` · `[id]/{audit,billing,edit,keys,members}` (+ `[id]/layout`) | `0c4c1c4` |
| Admins             | list · `invite` · `[id]` · `[id]/reset-password`                       | `9eebe01` |
| Billing            | `overview` · `quota` · `export` · `enterprises/[id]` (+ `layout`)      | `c0b272d` |
| Security           | `mfa` · `sessions` (+ `layout`)                                         | `c72a5de` |
| Login + MFA        | `login` · `login/mfa`                                                   | `89371fd` |

(plus `/platform/workspaces` list itself in earlier commit `2b0d164`.)

Anywhere the old code used `ui/data-table` / `ui/card` / `ui/skeleton`
/ `ui/badge` / `ui/modal` it now uses:
- inline `<table>` with cream/gold rows + hover
- `<section>` with `rounded-md-custom border bg-[var(--bg-card)] shadow-soft-sm`
- `animate-pulse` div tiles
- `Badge` (variant: operational / warning / error / current / info / default)
- one-off `<Modal>` component declared at the bottom of pages that need it

Plan code constants updated PILOT/ENT_BASIC/ENT_MID/ENT_MAX/ENT_ROI
across all touch points (matches CLAUDE.md §10 pricing matrix; replaces
the older TRIAL/STARTER/BUSINESS/ENTERPRISE strings).

## Login

Use the existing `/platform/login` page. Seed credentials live in two
scripts:

```
# Idempotent platform admin seed (run once)
kaori-seed-admin.bat
  superadmin@kaori.local / Kaori@Admin1 (SUPER_ADMIN, MFA off)

# Full pilot bootstrap (platform admin + Olist enterprise + manager)
python scripts/seed-pilot-olist.py
  Platform:   admin@kaori.platform / Admin@2026 (SUPER_ADMIN)
  Enterprise: cs@olist.local       / Pilot@2026 (MANAGER)
```

After login the JWT lands in `localStorage.kaori.access_token`. Navigate
to `/platform/workspaces` to see the cream/gold re-skin against real BE.

## Validation

`npx tsc --noEmit` exits 0 after every commit in this thread.

## Dev-loop gotcha — docker `frontend` container shadows `npm run dev` on port 3000

`docker-compose.yml` defines a `frontend` service that builds from
`./frontend/Dockerfile` and maps `3000:3000`. When you bring up the
stack via `.\kaori-start.bat`, this container starts with whatever
code was bundled at last `docker compose build` time and **silently
holds port 3000 for the rest of the session**.

The trap:
1. You edit FE code and run `npm run dev`.
2. Next.js sees port 3000 is taken, auto-falls back to 3002 (or
   whatever is free) and prints `- Local: http://localhost:3002` in
   the dev terminal.
3. You open `http://localhost:3000` (the URL you always use) → that
   request hits the **docker container**, not the dev server.
4. Code edits never show up. New routes return 404. Auth-store
   hydration bugs you already fixed still "reproduce" because the
   container has the old layout.

Spotting it:
- Browser DevTools → Network tab → response header. A live dev server
  emits `link:` preload headers for Turbopack-built fonts; the docker
  container's pre-built bundle does not.
- Powershell `Get-NetTCPConnection -LocalPort 3000 -State Listen`
  returns `com.docker.backend` as `ProcessName` when the container is
  the one listening.

Fix (every time you start FE dev):
```powershell
docker compose stop frontend
cd frontend
npm run dev          # binds 3000 cleanly
```

Or test on whatever port Next.js falls back to (look at the dev
terminal banner — it always prints `Local: http://localhost:<port>`).

## Token aliases for public pages

`components/platform/foundation` re-exports from `p2/foundation`, which uses
template tokens (`--primary-gold`, `--bg-sidebar`, `--text-primary`,
etc.). These are injected at runtime by `<GlobalStyles />` — but that
component renders only inside `<AppShell>`.

Public pages outside the shell (the `/login`, `/forgot-password`,
`/reset-password` family, plus `/platform/login` and `/platform/login/
mfa`) therefore had a transparent button background and missing card
borders.

Fix landed in `globals.css :root`: alias each template token to the
corresponding global token (`--primary-gold: var(--brand-500)` etc.).
Now every page renders cream/gold regardless of whether the shell is
mounted.

## P2 portal shell consolidation — landed 2026-05-18 (commit `9d26d95`)

Same architectural shift as `/platform/*` (commit `2b0d164`) applied to
the 84 P2 enterprise templates. `components/p2/shell.tsx` `AppShell`
now reads `usePathname()` itself when no `currentPath` prop passed.
`app/(app)/p2/layout.tsx` wraps every `/p2/*` page in `<AppShell>`.
82 of 84 templates had their `<AppShell currentPath="...">…</AppShell>`
wrap stripped to a `<></>` fragment via `scripts/strip_p2_appshell.py`
(the script handles three currentPath forms — string, plain expr,
template literal with nested `${...}`).

Smoke test results (75 /p2/* routes):
- **62/75 pass** (83%)
- 13 fail, classified:
  - **Pre-existing (3)**: `/p2/decisions/id`, `/p2/insights/id-detail`,
    `/p2/users/id-detail` — legacy mock templates access
    `window.location.pathname` at module scope. `force-dynamic` set on
    each page.tsx but still throws on render. Unchanged from
    pre-consolidation.
  - **Dynamic `[id]` jest-worker crash (9)**: all routes that resolve
    a UUID param through `Promise<{...}>` + `use(params)` (the
    Next.js 15+/16 pattern). Same symptom as the /platform/* bug but
    NOT fully reproduced — `/platform/workspaces/[id]` passes under
    `--webpack`, while `/p2/risks/[riskId]` etc. still crash. Likely
    a heavier compile graph in /p2 templates tipping the jest-worker
    child process over memory or stack limits. Unknown if reproducible
    after `rm -rf .next && npm run dev` cold start — needs follow-up.
  - **307 redirect (1)**: `/p2/workflows/detail` — looks intentional
    (probably bounces to `/p2/workflows/hub` or similar). Not a
    failure; HTTP 200 check just doesn't count 307.

Action items deferred:
  - File upstream Next.js issue for /p2 dynamic [id] jest-worker
    crash with minimal reproducer.
  - Migrate 3 window-access templates to either `useEffect` (read on
    client) or pull pathname from `usePathname()` prop.

## Turbopack 500 on dynamic routes — `dev` script switched to webpack

Smoke-testing the 21 platform routes uncovered a Next.js 16.2.4
Turbopack bug: every `[id]` dynamic route under `/platform/*` returned
HTTP 500 with `"Jest worker encountered 2 child process exceptions,
exceeding retry limit"` in the dev log. The worker crash hides the
real error so there is nothing actionable to grep for.

Reproducer:
```
curl -o /dev/null -w "%{http_code}\n" \
  http://localhost:3000/platform/workspaces/00000000-0000-0000-0000-000000000001
# → 500 (with Turbopack)
# → 200 (with webpack)
```

The 14 static routes compile fine under Turbopack; only routes that
combine `params: Promise<{id}>` + `use(params)` + react-query inside a
sub-layout trip the worker.

Fix: `package.json` `dev` script now defaults to `next dev --webpack`.
Slower cold compile but stable. Turbopack remains available as the
`dev:turbo` script for occasional benchmarking once upstream stabilises
(track `vercel/next.js` issue queue under the "Turbopack" label).

Production builds (`npm run build`) do not use Turbopack and are
unaffected.
