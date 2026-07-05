# ADR-0042 — Confluence-style document structure: doc-type templates + typed metadata + labels + auto-index

> **Status:** accepted (building — BE + FE shipped 2026-07-05, mig 139)
> **Date:** 2026-07-05
> **Deciders:** Nguyen Truong An
> **Related:** ADR-0039 (Document Repository/DMS, mig 132) · mig 138 (`doc_date`/`period_kind`) · mig 131 (`document_analysis`, ADR-0040) · mig 119/120 (doc requirements + lifecycle, ADR-0037) · mig 121/122 (`approval_chains`) · mig 123/126 (dept + ABAC RESTRICTIVE) · mig 106 (global-seed RLS pattern) · mig 133 (`bronze_file_embeddings`) · K-1/K-8/K-9/K-21/K-25 · Tenet 13 (per-item failure ≠ abort)

## Context

Reference model (2026-07-05, anh's direction): **Confluence/Jira document organisation** — studied live at `yuta9999k.atlassian.net` ("Project plan" blueprint page). Confluence makes documents *manageable objects* through six structural layers:

| # | Confluence concept | What it buys |
|---|---|---|
| 1 | **Space → page tree** | Hierarchical container per team/person; parent pages act as indexes for children |
| 2 | **Blueprint/template per doc type** | Every "Project plan" has the same shape — sections + metadata are predictable |
| 3 | **Page Properties table** (top of page) | Typed key–value metadata: `@mention` people, `//` typed dates, **status lozenges from a controlled vocabulary** (`NOT STARTED / IN PROGRESS / COMPLETE`) |
| 4 | **Page Properties Report** | A parent page auto-aggregates all children of a type into an index table (name, owner, deadline, status) — nobody maintains it by hand |
| 5 | **Labels** (e.g. `PROJECTPLAN`) | Cross-cutting retrieval by type/process regardless of tree position |
| 6 | **Comments / versions / audit** | Every change has a trace |

Kaori's DMS (ADR-0039) already covers **layer 1** (folder tree + ABAC dept), **layer 6** (version chain + soft delete), and time-as-metadata (mig 138). What's missing is **layers 2–5**: today `document_repository_file.doc_type` is a free `VARCHAR(40)`, there is no metadata schema per type, no controlled status vocabulary, no labels, and no auto-index. Consequence: an uploaded file is an opaque blob with a name — Kaori cannot manage documents *theo phòng ban + theo quy trình nghiệp vụ*, and the 5-step pipeline cannot be re-run over a meaningful slice of the repository ("mọi hợp đồng phòng Mua hàng đang chờ duyệt") because no query can express that slice.

## Decision (proposed)

Add a **document-type template layer** over the existing DMS — Confluence blueprints, Kaori-shaped. Additive only: 1 new table + 1 ALTER (mig 139), no engine changes, everything driven by DB-stored schemas (no hardcode — templates are data, per tenet and `feedback_no_arbitrary_hardcode`).

### 1. Data model (mig 139, K-21 + RLS)

**`document_type_template`** — the blueprint registry:

- `template_id UUID PK DEFAULT gen_uuid_v7()` (K-21), `external_ref TEXT DEFAULT gen_ulid()`.
- `enterprise_id UUID NULL` — **NULL = global Kaori-curated seed** readable by every tenant (mirror the mig 106 `knowledge_documents` RLS pattern exactly); non-NULL = tenant-custom template. `department_id UUID NULL` — optional owning dept.
- `type_key VARCHAR(40)` (`ke_hoach_du_an`, `bien_ban_hop`, `hop_dong`, `sop`, `bao_cao_ngay`…), `name_vi VARCHAR(200)`, `icon VARCHAR(16)` (emoji), `description TEXT`.
- `metadata_schema JSONB NOT NULL` — **ordered** field definitions, the Page Properties table:
  ```json
  [
    {"key": "nguoi_phu_trach", "label_vi": "Người phụ trách", "kind": "user",   "required": true},
    {"key": "nguoi_duyet",     "label_vi": "Người duyệt",     "kind": "user",   "required": true},
    {"key": "muc_tieu",        "label_vi": "Mục tiêu",        "kind": "text",   "required": false},
    {"key": "han_chot",        "label_vi": "Hạn chót",        "kind": "date",   "required": true},
    {"key": "trang_thai",      "label_vi": "Trạng thái",      "kind": "status", "required": true,
     "options": ["chua_bat_dau", "dang_thuc_hien", "hoan_thanh"], "default": "chua_bat_dau"}
  ]
  ```
  `kind ∈ {text, long_text, number, money, date, user, department, select, status}` — `user` stores a `user_id` validated against enterprise users (people are first-class data, not text); `money` renders per the VND format rule; `status` is the controlled-vocabulary lozenge. Status lives **inside the schema as a field**, not as a new column — one mechanism, no special cases.
- `section_outline JSONB NOT NULL DEFAULT '[]'` — ordered `[{heading_vi, icon, hint_vi, body_kind: prose|table|checklist}]`. For Kaori-authored docs it drives the editor skeleton; for binary uploads (PDF/DOCX) it *guides extraction and completeness checks* — it is never enforced as a hard gate on a file's internal layout.
- `default_labels TEXT[] NOT NULL DEFAULT '{}'` — auto-applied on classification (Confluence's blueprint auto-label, e.g. `loai:ke-hoach-du-an`).
- `requires_approval BOOLEAN NOT NULL DEFAULT FALSE` + `approval_chain_id UUID NULL REFERENCES approval_chains` — a template can demand sign-off; publishing such a doc opens the mig 121/122 chain (Confluence's `@Approver`, made executable).
- `is_active BOOLEAN`, `created_at/updated_at`. UNIQUE `(COALESCE(enterprise_id, uuid_nil), type_key)`.

**ALTER `document_folder` — folder = nghiệp vụ *page*** (anh's refinement 2026-07-05, sharpened same day: follow Confluence's actual mechanics — in Confluence there is no dumb folder; every tree node is a page that is *both content and container*. Creating a department creates one page per nghiệp vụ; the page describes the documents, defines their required sections/fields, carries the sample file, and versions its own definition):

- `body_md TEXT NULL` — the page body (Markdown): mô tả nghiệp vụ, tài liệu nào thuộc về đây, cadence, quy ước. Rendered as the folder's page header in FE; also injected as context into extraction prompts (§4).
- `default_template_id UUID NULL REFERENCES document_type_template ON DELETE SET NULL` — the doc-type definition *surfaced and edited on this page* ("tài liệu ở đây cần các mục gì"): the page's editing UI writes the bound template's `metadata_schema` + `section_outline`. Docs uploaded into the folder inherit it (override allowed at Bước 1; subfolders inherit from the nearest ancestor with a value, resolved app-layer via `path`).
- `sample_file_id UUID NULL REFERENCES bronze_files(file_id) ON DELETE SET NULL` — the **file upload mẫu** attached on the page (Confluence blank-template attachment; same concept as mig 119's `template_file_id`, reused at folder scope). Users download it, fill it, upload back.
- `default_labels TEXT[] NOT NULL DEFAULT '{}'` — auto-applied to every doc filed here (e.g. folder "Mua hàng" carries `quy-trinh:mua-hang`), merged with the template's `default_labels`.
- `page_version INTEGER NOT NULL DEFAULT 1` — current definition version (below).

**`document_folder_version`** — Confluence page-version history for the *definition* (mirror the mig 111 / ADR-0033 version-history pattern; append-only):

- `version_id UUID PK gen_uuid_v7()`, `folder_id FK`, `enterprise_id` (RLS), `version_no INTEGER`.
- Snapshot columns: `body_md`, `template_snapshot JSONB` (the bound template's schema+outline at that moment), `sample_file_id`.
- `edited_by UUID`, `edited_at TIMESTAMPTZ`, `change_note TEXT`. UNIQUE `(folder_id, version_no)`.
- Every save of the page (body, schema, sample file) appends a row → FE offers history list, diff (app-layer), and restore (restore = new version copying an old snapshot — never rewrite history, K-2 spirit). Docs uploaded earlier record the `page_version` they were validated against, so a definition edit never silently re-judges old docs.

**Attachment versioning by name (Confluence behavior, adopted):** uploading a file whose `name_vi` matches an existing `is_current` doc in the same folder does **not** create a sibling — it proposes a new version of that doc (mig 132 chain: `version+1`, `supersedes`, prompt for `change_reason`); the user confirms or chooses "đây là tài liệu khác" (then a `(2)`-suffixed sibling is created). This replaces today's dup-fallback with Confluence's same-name-stacks rule.

**Department creation flow:** tạo phòng ban → wizard seeds its nghiệp vụ pages (one folder-page per process, from the industry pack — ADR-0026 3-tier bootstrap supplies the per-industry page set + templates + sample files).

**ALTER `document_repository_file`** (additive, nullable):

- `template_id UUID NULL REFERENCES document_type_template ON DELETE SET NULL` — supersedes the free-text `doc_type` going forward (column kept; optional backfill maps legacy values to seeded templates).
- `metadata JSONB NOT NULL DEFAULT '{}'` — the filled Page Properties, values keyed by `metadata_schema[].key`. GIN index `(metadata jsonb_path_ops)` — enough at SME volumes; no EAV table.
- `labels TEXT[] NOT NULL DEFAULT '{}'` + GIN index — layer-5 cross-cutting retrieval. Convention: namespaced slugs — `loai:hop-dong`, `quy-trinh:mua-hang`, `phong-ban:tai-chinh` (namespaces are convention, not schema — same freedom Confluence gives).
- `metadata_completeness NUMERIC(5,4) NULL` (K-9) — computed on every metadata write, **the K-25 `model_card_completeness` pattern reused**: trust-first, an incomplete doc is recorded + flagged (badge "thiếu 2 trường"), never hard-blocked (Tenet 13).

### 2. Validation (`shared/doc_metadata.py`, mirrored per service as needed)

`validate_metadata(schema, values, enterprise_users) → (normalized_values, completeness, warnings[])`:
- kind checks (date ISO, number/money numeric, `status`/`select` value ∈ `options`, `user` ∈ enterprise users);
- wrong-typed values → warning + field dropped from normalized set (degraded envelope, not 4xx);
- missing required → lowers `completeness`, emits warning;
- unknown keys preserved under `metadata._extra` (additive-contract spirit — a template edit never destroys data).

Thresholds/knobs env-configurable (`KAORI_DOCMETA_*`), consistent with the `KAORI_MEM_*`/`KAORI_KB_*` convention.

### 3. Auto-index — the Page Properties Report (no new table)

- `GET /p2/documents/index?template_id=&folder_id=&labels=&status_key=&status_value=&doc_date_from=&doc_date_to=&cursor=&limit=` — returns `is_current` docs of a template as rows, **columns taken from `metadata_schema`** (so the endpoint is generic; adding a field to a template instantly adds a column to every index).
- FE: a folder gets an "Index" view mode — when its documents share a template, render the aggregated table (name · người phụ trách · hạn chót · trạng thái lozenge) exactly like Confluence's report under a parent page. Sort/filter server-side via the GIN index.

Retrieval is then **4 đường**, all existing infra + these two indexes: tree (mig 132 `path`) · title (`idx_drf_name`) · **labels (GIN)** · **type + metadata (GIN)** — plus semantic (mig 133 embeddings) as the fifth, free.

### 4. Extraction bridge (Bước 2 của pipeline — see mapping below)

`document_analysis` (mig 131) gains template awareness: when a doc has a `template_id`, the analyze prompt embeds that template's `metadata_schema` (keys + labels + kinds) so `key_fields` extraction **targets the schema** instead of free-form guessing. FE pre-fills the metadata form from the latest analysis; the user confirms/edits (human-in-the-loop — extraction suggests, never silently writes). K-3 via llm-gateway, Qwen local (K-4: documents carry PII → local only).

### 5. Insight — 3 granularities (doc / group / folder)

Once metadata is typed and folders carry nghiệp vụ, analysis works at three scopes with **one mechanism** — a *slice descriptor* (the same filter shape as the index endpoint: `{folder_id? , template_id?, labels?, doc_date_from/to?, status?}`; folder scope = subtree via `path LIKE`):

- **Per-doc** — exists today: `document_analysis` (mig 131), now schema-guided (§4).
- **Group / folder** — new table **`document_collection_insight`** (K-21, RLS mirror mig 131, append-only history):
  - `scope_kind ∈ {group, folder}`, `scope JSONB` (the slice descriptor, resolvable any time later — re-runnable), `doc_count`, `model`.
  - `stats JSONB` — deterministic aggregates computed from metadata first (dumb baseline first, Tenet 1): counts by status/label, overdue vs `han_chot`, completeness distribution, timeline by `doc_date`.
  - `summary TEXT` + `findings JSONB` — grounded Qwen synthesis **over the per-doc summaries + stats** (never raw bytes of N files), K-3 via llm-gateway, Qwen local (K-4 PII).
  - Runs **async as a job** (LLM never unbounded in the request path — `feedback_llm_in_request_path_bound`): `POST /p2/documents/insights` returns 202 + insight_id; FE polls/streams. Doc-count cap env-configurable (`KAORI_DOCINS_MAX_DOCS`); over-cap → stats-only + warning (degraded envelope, Tenet 13).
- FE: folder header gets "Phân tích folder này"; index view gets multi-select → "Phân tích nhóm đã chọn". Answers questions like *"quý này phòng Mua hàng có bao nhiêu hợp đồng chờ duyệt quá hạn, rủi ro chung là gì"* from the folder page itself.

### 6. Seeds

Global templates (enterprise_id NULL, seeded in mig 139 or an admin path): `ke_hoach_du_an` (the Confluence Project plan shape: phụ trách/duyệt/mục tiêu/hạn chót/trạng thái + sections Vấn đề → Phạm vi → Timeline → Cột mốc → Liên kết), `bien_ban_hop`, `hop_dong` (wired to `contracts` mig 124 semantics), `bao_cao_ngay` (uses `doc_date`/`period_kind` mig 138), `sop`. Tenants clone-and-edit; industry bootstrap (ADR-0026 3-tier) can ship industry template packs later.

## Mapping to the 5-step pipeline (upload → schema → clean → analyze → results)

The FE wizard's five steps (`frontend/app/(app)/pipeline/new/page.tsx`) map 1-to-1 onto document intake — same mental model for data files and documents:

| Bước | Data pipeline (today) | Document pipeline (this ADR) | Mechanism |
|---|---|---|---|
| **1 Upload** | file → Bronze, SHA-256 | file → Bronze (K-8 dedup, reused) + chọn folder → **template + labels thừa hưởng từ folder** (`default_template_id`); folder chưa cấu hình thì classifier suggest (tên file + first-page text); user confirms | mig 132 + folder binding + `document_type_template` |
| **2 Schema** | detect columns/dtypes | **metadata form theo template** — the Page Properties table; pre-filled by guided extraction, user confirm/sửa | §4 extraction bridge + `metadata_schema` |
| **3 Clean** | 8-step cleaning | **validate + chuẩn hoá metadata**: kind checks, controlled status, required→completeness, PII flag, version chain (`supersedes`) if replacing | §2 validator + mig 132 version chain |
| **4 Analyze** | quality scorecard + insights | risk keywords + grounded Qwen summary (mig 131) + Stage-6 knowledge extraction + embedding (mig 133) | existing modules, now schema-guided |
| **5 Results** | Gold + dashboards | **publish**: doc lands in tree with status; index view updates itself; labels live; `requires_approval` templates open the approval chain | §3 index + mig 121/122 |

**"Pipeline theo 5 bước bất cứ khi nào"** — the payoff of typed metadata is that the pipeline stops being an upload-time-only event. Any query slice the new indexes can express — *một folder, một label (`quy-trinh:mua-hang`), một template, một khoảng `doc_date`* — becomes a re-runnable batch: re-enter at Bước 3 (re-validate after a template edit) or Bước 4 (re-analyze with a newer model/knowledge base) over that slice. Department + process management falls out of the same three axes: **phòng ban** = ABAC `department_id` (already RESTRICTIVE, mig 126/132) · **quy trình nghiệp vụ** = labels + `requires_approval`/chains · **loại nghiệp vụ** = template.

## Phase 2 — Authored documents (mig 140, shipped 2026-07-05)

Reference: **Message Definition.pdf** (chuẩn BA của anh, Downloads) — a document is a
*skeleton*: metadata header + numbered sections, each an intro paragraph + a
fixed-column bilingual table (+ link attachments). Kaori now authors such
documents natively:

- **`document_repository_file.content JSONB` + `doc_kind ∈ {file, authored}`** —
  authored docs have no bytes; content = `{"sections": [{key, body_md, rows[], links[]}]}`.
  `body_md` supports headings/sub-headings/bold/lists/checklist/**`==highlight==`**.
- **Table sections declare columns**: `section_outline[].columns = [{key, label_vi,
  label_en?, kind}]` — kind reuses the metadata vocabulary **+ `link`**
  (`{text, url}`, http(s) only — scheme-checked in `validate_content`).
- **Ngôn ngữ (5 locales)**: every label/heading supports `label_<locale>` /
  `heading_<locale>`; FE resolves `locale → en → vi` (`pickLabel`). Screen chrome
  uses the existing 5-locale dictionary.
- **Editing = version stacking** (PATCH …/content creates v+1, supersedes) —
  the PDF's *History Changes* table is **auto-rendered from the version chain**,
  never hand-written.
- **AI generation** (`reasoning/document_author.py`): user prompt (mô tả + yêu cầu)
  → Qwen drafts **per-section** against the skeleton (small bounded prompts,
  Tenet 13 per-section degrade), JSON forced to the section's columns then
  passed through `validate_content`; **links are grounded** — any URL not present
  verbatim in the user prompt is stripped. Runs as a background job
  (`status='generating'` → `active`); knobs `KAORI_DOCGEN_MAX_ROWS/MAX_TOKENS`.
- Global seed **`message_definition`** (bilingual vi/en) mirrors the PDF:
  glossary + link-attachments + system/user/business-logic error tables + other
  messages.

## Consequences

- **+** Documents become structured objects: per-type predictable shape, machine-readable metadata, controlled status, cross-cutting labels, self-maintaining indexes — the Confluence properties that make dept/process management possible.
- **+** Still contained: 3 tables (`document_type_template`, `document_folder_version`, `document_collection_insight`) + 2 ALTERs (folder-as-page, file metadata) + 2 GIN indexes (mig 139), one validator module, one generic index endpoint, one async insight job, template-aware prompt in an existing analyzer. Everything else (tree, doc version chain, dedup, ABAC, approval chains, embeddings, doc_date, mig 111 version-history pattern) is reused.
- **+** Trust-first consistency: completeness mirrors K-25's pattern; degraded-envelope validation mirrors Tenet 13.
- **−** FE surface is the bigger half: template picker in upload, metadata form renderer (schema-driven), index view mode, label chips + filter UI. Gated on FE bandwidth like the rest of the DMS FE.
- **−** Template evolution semantics: editing a schema does not rewrite existing docs' metadata (additive contract; `_extra` preserves orphans). A `completeness` recompute job handles re-scoring; no data migration.
- **⚠** JSONB metadata is deliberately schema-on-read; if per-field analytics ever dominate (unlikely at SME volume), revisit with generated columns — same "revisit only if" posture as ADR-0039's ltree decision.

## Alternatives considered

- **EAV table (`document_metadata_value` row per field)** — rejected: joins for every read, no gain at SME volume; JSONB + GIN is the codebase's established pattern (`config_schema`/`ui_schema` ADR-0034, `key_fields` mig 131).
- **Hard-enforce `section_outline` on uploads** — rejected: most SME docs arrive as PDF/DOCX authored elsewhere; blocking on internal layout would make the DMS unusable. Outline guides extraction + authoring only.
- **Status as a dedicated column with a global vocabulary** — rejected: vocabularies differ per doc type (hợp đồng ≠ kế hoạch); a `status`-kind schema field keeps one mechanism and per-template control, and the GIN index still filters it.
- **Folder-per-department-per-process physical tree** — rejected: same lesson as mig 138 (time) — process and type are metadata, not tree depth; a physical tree explodes combinatorially and weekly/cross-dept docs never fit one branch.
