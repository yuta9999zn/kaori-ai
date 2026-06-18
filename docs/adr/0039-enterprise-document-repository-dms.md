# ADR-0039 — Enterprise Document Repository (DMS) — 10-year hierarchical store (additive)

> **Status:** accepted (building, BE foundation) — 2026-06-01
> **Date:** 2026-06-01
> **Deciders:** Nguyen Truong An
> **Related:** ADR-0037 (Tier-3 doc tree) · mig 053 (`workflow_step_documents`) · 058 (`workflow_step_folders`) · 119/120 (doc requirements + lifecycle) · 002 (`bronze_files`) · `shared/blob_store.py` (ADR-0037 Phase 0) · ADR-0013 (RLS) · K-1/K-2/K-8/K-12/K-21

## Context

UAT 2026-06-01 surfaced a real enterprise need: a business keeps **~10 years of documents across many folders** (Năm → Quý → Loại hồ sơ), expandable. Today Kaori only has **per-workflow-step** document organisation:

- `workflow_step_document_requirements` (119) — what a *step* needs (📥/📤/📎).
- `workflow_step_documents` (053+120) — file instances attached to a *node*, with version chain (`supersedes`/`superseded_by`/`is_current`), 7-state status, `file_id → bronze_files`, SHA-256 dedup (K-8).
- `workflow_step_folders` (058) — a self-referential (`parent_folder_id`) folder tree, but **scoped to a single workflow node**, soft-delete (`status='archived'`), CRUD endpoints exist.

What's **missing**: an **enterprise-wide** document repository independent of any workflow — where a workflow step *references / files into* the repository, and users browse/search ~50k+ documents across years. ADR-0037 did **not** spec this; it is genuinely new scope. The good news (per 2026-06-01 investigation): the byte store, dedup, versioning, RLS, and a folder pattern all already exist — the DMS is **additive reconciliation + a new enterprise-scoped folder axis**, not a greenfield store.

## Decision (proposed)

Add an **enterprise Document Repository** module. **Reuse** the existing byte/version/dedup substrate; add only a folder hierarchy + a repository-file table + a lazy/virtualized FE.

### Data model (additive, K-21 + RLS-compliant)

**`document_folder`** — enterprise-wide hierarchical folders (NOT per-workflow):
- `folder_id UUID PK DEFAULT gen_uuid_v7()` (K-21), `external_ref TEXT DEFAULT gen_ulid()` for URLs.
- `enterprise_id UUID NOT NULL`, `department_id UUID NOT NULL` — RLS K-1 + ABAC dept-scope (mirror mig 119 policies exactly).
- `parent_id UUID NULL REFERENCES document_folder(folder_id)` — adjacency list, **consistent with `workflow_step_folders` (058)** (NOT ltree — codebase has no ltree extension; path resolution is app-layer today).
- `path TEXT NOT NULL` — materialized slug path (e.g. `tai_chinh/2024/q1/`) + `idx ON (enterprise_id, path text_pattern_ops)` for subtree queries `WHERE path LIKE 'tai_chinh/2024/%'` without recursion.
- `name_vi`, `sort_order`, `deleted_at TIMESTAMPTZ` (soft delete — K-2 spirit, never hard-delete financial records), `archive_after TIMESTAMPTZ` (lifecycle).
- UNIQUE `(enterprise_id, COALESCE(parent_id, uuid_nil), name_vi)` (sibling uniqueness, same pattern as 058).

**`document_repository_file`** — file instances in the repository (separate from `workflow_step_documents` so "kho" ≠ "đính kèm bước"; cross-FK when a step files into the repo):
- `doc_id UUID PK DEFAULT gen_uuid_v7()`, `enterprise_id`, `department_id` (RLS).
- `folder_id UUID NOT NULL REFERENCES document_folder`.
- `file_id UUID REFERENCES bronze_files(file_id)` — **reuse Bronze byte store + SHA-256 dedup (K-8) + blob_store**; no parallel byte store.
- Version chain mirroring 120 / 111: `version`, `supersedes`, `superseded_by`, `is_current`, `change_reason`.
- `name_vi`, `doc_type`, `status` (reuse the 7-state machine), `valid_until`, `storage_tier TEXT DEFAULT 'hot'` (hot/warm/cold), `uploaded_by`, `uploaded_at`, `sha256` (denorm for dedup/search).

**Workflow ↔ repository link**: add nullable `folder_id` to `workflow_step_document_requirements` (a step can target a repo folder) and allow a step upload to also register a `document_repository_file` row.

### Lifecycle (10 years)
Infra cron sets `storage_tier hot→cold` by `uploaded_at` age (e.g. >3y → cold/MinIO-Glacier-class); metadata always stays in Postgres for instant lookup. Soft-delete only (`deleted_at`) for legal/audit integrity.

### API (lazy — never return the whole tree)
- `GET /document-folders/{id}/children?cursor=&limit=` — direct children only, **cursor-based** (not offset), max 500 (§6 convention).
- `GET /document-folders/search?q=&doc_type=&year=&status=` — indexed on `name_vi` + `path`.
- `POST /document-folders`, `PATCH`, soft `DELETE` — mirror `workflow_step_folders` CRUD in `workflow_builder.py`.
- Upload: reuse `POST /api/v1/upload` + a new `X-Folder-ID` header (ingestor writes `document_repository_file` like it writes `workflow_step_documents` today).

### Frontend
- New P2 nav module **"Kho tài liệu"**.
- **Lazy-load + virtualization** tree: fetch children on folder-open; render only viewport rows. Add `@tanstack/react-virtual` (not yet a dep); use **`@tanstack/react-query`** (already installed, currently unused) for cache + invalidation (the same stale-badge class of bug otherwise recurs).
- Breadcrumb, drag-drop move, per-node count + status badges, search/filter (year/type/status) prioritised over manual tree-walking at 10-year scale.
- Multi-file + folder upload; chunked/resumable (tus-style) for large files — wires into the existing `/api/v1/upload`.

### Reuse (do NOT rebuild)
`blob_store` (byte store) · `bronze_files` (K-8 dedup) · the `workflow_step_documents` version-chain semantics · the 7-state status machine · `acquire_for_tenant` RLS (K-1/K-12) · the adjacency-list folder pattern of `workflow_step_folders` (058) · DocSage extraction for PDF/DOCX.

## Consequences
- **+**: enterprise-scale document organisation; workflow steps can pull/file into a shared repository; reuses proven byte/version/RLS plumbing → low new-surface risk.
- **−**: a sizeable epic — new migration (2 tables + 1 ALTER), ~4 BE endpoints + ingestor branch, a new FE module with virtualization + a new dep. Multi-day; warrants its own sprint slot + approval (hence design-only here).
- **RESOLVED (2026-06-01) — adjacency-list + materialized `path TEXT`, NOT ltree.** Deep analysis: both designs need (a) `parent_id` adjacency for direct-children lazy-load (the actual product UX — open a folder, fetch its children), and (b) a slugified path + a separate Vietnamese display name (folder names like "Tài chính / Quý 1" can't be raw ltree labels — labels are `[A-Za-z0-9_]` only, so ltree needs slugging too). The ONLY real differentiator is cross-subtree analytics: ltree `path <@ 'tai_chinh.2024'` vs `path LIKE 'tai_chinh/2024/%'`. With a `text_pattern_ops` index the LIKE-prefix scan is an index range scan — fast enough for "all docs under Tài chính". ltree's lquery/GIST power doesn't justify a NEW extension dependency (CREATE EXTENSION at provision on FPT Cloud / managed PG + backup/restore complexity), and adjacency+app-layer-path is the established codebase convention (`workflow_step_folders` 058). Revisit ltree only if subtree analytics become dominant.

## Alternatives considered
- **Extend `workflow_step_folders` to enterprise scope** — rejected: conflates "kho doanh nghiệp" with "đính kèm bước"; the per-step semantics (node_id NOT NULL) don't fit a workflow-independent archive.
- **A parallel byte store / `document_version` table** (as first sketched) — rejected: duplicates `bronze_files` + `blob_store` + the 120 version chain and breaks K-8 dedup.
