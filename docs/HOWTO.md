# HOWTO — Adding New Features (v4-aware)

> Tách từ `CLAUDE.md` §12 ngày 2026-05-22. Đọc khi thêm template / rule / node / connector / metric mới.

## Step 0 — locate feature in v4 catalog

1. Tìm code v4 của feature (ví dụ `P2-M26-043` Framework picker) trong `docs/BACKLOG_V4.md`.
2. Xem layer (L0..L5 + L4.5) trong `docs/strategic/SAD_SKELETON_V2.md` Phần 3.
3. Xem API trong `docs/API_CATALOG_V4.md`.

## New analysis template (L3 reasoning)

1. Add to `services/ai-orchestrator/reasoning/...` (Phase B) hoặc `services/ai-orchestrator/analytics/template_registry.py` (Phase 1 legacy).
2. Update `docs/BACKLOG_V4.md` status.
3. Update `docs/api-specs/ai-orchestrator.openapi.json` via `python scripts/dump_openapi.py`.
4. FE — đợi anh restructure.

## New cleaning rule (L2 Silver)

1. Add function in `services/data-pipeline/data_plane/silver/rule_catalog.py` (Phase B path) hoặc `services/data-pipeline/silver/rule_catalog.py` (Phase 1 legacy).
2. Register in `RULE_CATALOG` under category (UNIVERSAL/BY_TYPE/BY_PURPOSE/AI_DETECTED).

## New workflow node (L4)

1. Declare `side_effect_class` (K-17). Pure / read_only / write_idempotent / write_non_idempotent / external.
2. Add activity in `services/ai-orchestrator/workflow_runtime/activities/` (Phase B).
3. Declare retry policy + compensation (if `external`).
4. Add to YAML schema test fixture.
5. Register in `node_executor.py` REGISTRY + add catalog row in next mig number.

## New connector (L1 ingestion, Phase 1)

1. Add in `services/data-pipeline/ingestion/connectors/{name}/` (Phase B path).
2. Implement contract: `extract_events()` → normalized event stream → Bronze.
3. PII redaction before publish (K-5).

## New observability metric (Cross-cutting)

1. Counter / histogram trong service code.
2. Tag `tenant_id` (K-19), `workflow_id`, `service_name`.
3. Add Grafana dashboard JSON in `infrastructure/grafana/dashboards/`.

## New endpoint — drift artefacts checklist (BLOCKER trước first push)

1. Wire router in `services/{service}/routers/{name}.py`.
2. Tests `tests/test_{name}.py` (happy + 4-case negative per NFRS §13.3).
3. Update `RouteConfigTest` if Java-side.
4. Regen `docs/api-specs/{service}.openapi.json` via `python scripts/dump_openapi.py`.
5. Regen `frontend/src/types/{service}.d.ts` (FE TypeScript types).
6. Update `docs/API_CATALOG_V4.md` row.
7. Update `docs/specs/MESSAGE_DEFINITIONS.md` if new error code introduced.

Failing to refresh any of the 7 = green CI now, red drift detection next sprint.
