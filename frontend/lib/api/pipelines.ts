/**
 * Sprint 6.5 — typed wrapper for the data-pipeline service.
 *
 * **PoC for the OpenAPI codegen pipeline.** Refactored from inline `api()`
 * calls in `app/(app)/pipeline/page.tsx`. The query-parameter shape comes
 * from the generated `paths`/`operations` types in `./types/pipeline.d.ts`,
 * so a backend signature change (e.g. renaming `?status=` to `?state=`)
 * surfaces as a TypeScript error here at the next `tsc --noEmit` run.
 *
 * The response body is hand-typed because FastAPI's `dict` return shape
 * doesn't get translated to an OpenAPI schema by default — that's a Phase 2
 * tightening (add Pydantic response_model to each handler so the codegen
 * picks it up). Until then the runtime contract is documented inline below
 * and matches `routers/enterprise_pipelines.py::list_pipelines`.
 */

import { api } from "@/lib/api";
import type { paths } from "./types/pipeline";

/** Query params for `GET /api/v1/pipelines` — generated from BE spec. */
export type ListPipelinesQuery =
  paths["/pipelines"]["get"] extends { parameters: { query?: infer Q } }
    ? Exclude<Q, undefined>
    : never;

/** Hand-typed runtime shape for one pipeline_run row. Source of truth:
 *  `services/data-pipeline/routers/enterprise_pipelines.py::_serialise_row`. */
export interface PipelineRun {
  run_id:              string;
  status:              string;
  filename:            string | null;
  original_size_bytes: number | null;
  mime_type:           string | null;
  detected_language:   string | null;
  sheet_count:         number | null;
  row_count_bronze:    number | null;
  row_count_silver:    number | null;
  quality_score:       number | null;
  error_message:       string | null;
  created_at:          string;
  updated_at:          string;
}

export interface PipelineListPage {
  data: PipelineRun[];
  meta: {
    cursor:      string | null;
    limit:       number;
    count:       number;
    has_more:    boolean;
    request_id?: string;
    trace_id?:   string | null;
    server_time?: string;
  };
}

/** Build the query string from the generated query type. Knowing the
 *  shape statically means a typo in `cursor` / `limit` / `status` becomes
 *  a compile error rather than a 200 with the wrong rows. */
function buildQuery(q: ListPipelinesQuery): string {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(q ?? {})) {
    if (v === undefined || v === null) continue;
    params.set(k, String(v));
  }
  const s = params.toString();
  return s ? `?${s}` : "";
}

export const pipelinesApi = {
  /** Cursor-paginated history (F-022). */
  list(q: ListPipelinesQuery = {}): Promise<PipelineListPage> {
    return api<PipelineListPage>(`/api/v1/pipelines${buildQuery(q)}`);
  },
};
