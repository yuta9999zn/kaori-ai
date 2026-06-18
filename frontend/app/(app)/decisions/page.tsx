"use client";

/**
 * F-029 — AI Decision Log.
 *
 * Reads from cursor-paginated ``GET /api/v1/decisions?cursor=&limit=&type=&q=``
 * (envelope ``{data, meta:{cursor, has_more, ...}}``). Search is debounced
 * 300ms before triggering a new query. CSV export hits
 * ``GET /api/v1/decisions/export.csv`` and downloads the streamed file —
 * the BE caps at 10 000 rows and sets ``X-Export-Truncated`` if exceeded.
 *
 * Sprint 7 PR A — export uses ``fetch`` + Blob + anchor-click instead of
 * ``window.open(?access_token=…)``. Smuggling the JWT through a query
 * string leaks it to referer headers, browser history, and access logs;
 * the Blob pattern keeps the bearer token in the Authorization header
 * where it belongs (K-7 spirit).
 */

import { useEffect, useMemo, useState } from "react";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Brain, Search, Download } from "lucide-react";
import { api, getAccessToken } from "@/lib/api";
import { DataTable, type Column } from "@/components/ui/data-table";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useT } from "@/lib/i18n/provider";
import { fmtDateTime } from "@/lib/format";

// ── Types ──────────────────────────────────────────────────────────────────

type DecisionMethod =
  | "exact" | "fuzzy" | "llm" | "heuristic" | "user_confirmed" | "internal" | "orchestrator"
  | string;

interface DecisionAudit {
  id:                  string;
  decision_id?:        string;
  decision_type:       string;
  entity_ref?:         string;
  subject?:            string;
  chosen_value?:       string;
  confidence:          number;
  method:              DecisionMethod;
  needs_user_confirm:  boolean;
  uncertainty_flags?:  string[];
  reasoning?:          string | null;
  alternatives?:       unknown[];
  run_id?:             string | null;
  created_at:          string;
  /** Sprint 7 PR D — North Star manual toggle. */
  is_actioned?:        boolean;
  actioned_at?:        string | null;
}

interface DecisionListPage {
  data: DecisionAudit[];
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

// ── Helpers ────────────────────────────────────────────────────────────────

const METHOD_TONE: Record<string, BadgeTone> = {
  exact:          "success",
  user_confirmed: "success",
  fuzzy:          "info",
  internal:       "info",
  orchestrator:   "info",
  heuristic:      "neutral",
  llm:            "warning",
};
const METHOD_LABEL: Record<string, string> = {
  exact:          "Chính xác",
  user_confirmed: "Đã xác nhận",
  fuzzy:          "Gần đúng",
  internal:       "Nội bộ",
  orchestrator:   "Orchestrator",
  heuristic:      "Heuristic",
  llm:            "LLM",
};

const TYPE_LABEL: Record<string, string> = {
  // Real types written by BE today (Sprint 0.5 audit wire-up)
  column_map:        "Ánh xạ cột",
  cleaning_rule:     "Rule làm sạch",
  template_analysis: "Phân tích template",
  // Forward-compatible types from BACKLOG
  language_detect:   "Nhận diện ngôn ngữ",
  purpose_classify:  "Phân loại mục đích",
  rule_trigger:      "Kích hoạt rule",
  preflight_go_nogo: "Preflight check",
  model_select:      "Chọn mô hình",
  framework_select:  "Chọn framework",
};

function confidenceTone(c: number): BadgeTone {
  if (c >= 0.85) return "success";
  if (c >= 0.65) return "warning";
  return "danger";
}

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs]);
  return debounced;
}

const PAGE_SIZE = 50;
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

// ── Page ───────────────────────────────────────────────────────────────────

export default function DecisionsPage() {
  const t = useT();
  const [searchInput, setSearchInput] = useState("");
  const debouncedSearch = useDebouncedValue(searchInput.trim(), 300);
  const [exporting,   setExporting]   = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const queryKey = useMemo(
    () => ["decisions", { q: debouncedSearch }],
    [debouncedSearch],
  );

  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useInfiniteQuery<DecisionListPage>({
      queryKey,
      initialPageParam: null as string | null,
      queryFn: ({ pageParam }) => {
        const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
        if (pageParam)        params.set("cursor", pageParam as string);
        if (debouncedSearch)  params.set("q",      debouncedSearch);
        return api(`/api/v1/decisions?${params.toString()}`);
      },
      getNextPageParam: (last) => (last.meta.has_more ? last.meta.cursor : undefined),
      staleTime: 30_000,
    });

  const rows: DecisionAudit[] = (data?.pages ?? []).flatMap((p) => p.data);
  const totalKnown = rows.length + (hasNextPage ? 1 : 0); // "≥ rows.length"

  // Sprint 7 PR D — North Star manual toggle. POST /decisions/:id/action
  // upserts the side row (migration 019). Invalidate the list cache on
  // success so the row's checkbox re-derives from server state.
  const qc = useQueryClient();
  const actionMutation = useMutation({
    mutationFn: ({ id, isActioned }: { id: string; isActioned: boolean }) =>
      api(`/api/v1/decisions/${id}/action`, {
        method: "POST",
        body: JSON.stringify({ is_actioned: isActioned }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["decisions"] }),
  });

  const COLUMNS: Column<DecisionAudit>[] = [
    {
      key: "decision_type",
      header: "Loại quyết định",
      render: (row) => (
        <span className="text-body-strong text-ink">
          {TYPE_LABEL[row.decision_type] ?? row.decision_type}
        </span>
      ),
    },
    {
      key: "entity_ref",
      header: "Đối tượng",
      render: (row) => (
        <span className="text-small text-ink-muted max-w-[180px] truncate block"
              title={row.entity_ref ?? row.subject ?? undefined}>
          {row.entity_ref ?? row.subject ?? "—"}
        </span>
      ),
    },
    {
      key: "confidence",
      header: "Độ tin cậy",
      render: (row) => (
        <Badge tone={confidenceTone(row.confidence)}>
          {(row.confidence * 100).toFixed(0)}%
        </Badge>
      ),
    },
    {
      key: "method",
      header: "Phương pháp",
      render: (row) => (
        <Badge tone={METHOD_TONE[row.method] ?? "neutral"}>
          {METHOD_LABEL[row.method] ?? row.method}
        </Badge>
      ),
    },
    {
      key: "needs_user_confirm",
      header: "Trạng thái",
      render: (row) =>
        row.needs_user_confirm ? (
          <div className="flex items-center gap-1.5 text-warning-600">
            <AlertTriangle className="w-4 h-4" />
            <span className="text-small">Cần xem lại</span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 text-success-600">
            <CheckCircle2 className="w-4 h-4" />
            <span className="text-small">Tự động</span>
          </div>
        ),
    },
    {
      key: "is_actioned",
      header: "Đã xử lý",
      // Sprint 7 PR D — manual toggle. Stops row click bubbling so the
      // checkbox doesn't trigger a navigate. Optimistic UI not used yet
      // (mutation is fast enough); we rely on the invalidate→refetch.
      render: (row) => (
        <input
          type="checkbox"
          aria-label="Đánh dấu quyết định đã được xử lý"
          checked={!!row.is_actioned}
          disabled={actionMutation.isPending}
          onClick={(e) => e.stopPropagation()}
          onChange={(e) =>
            actionMutation.mutate({
              id: row.decision_id ?? row.id,
              isActioned: e.target.checked,
            })
          }
          className="w-4 h-4 rounded border-[var(--color-subtle)] text-brand-500 focus:ring-2 focus:ring-brand-300 focus:ring-offset-0 cursor-pointer accent-brand-500"
        />
      ),
    },
    {
      key: "created_at",
      header: "Thời gian",
      render: (row) => (
        <span className="text-tiny text-[#B0A698] tabular-nums">{fmtDateTime(row.created_at)}</span>
      ),
    },
  ];

  async function handleExport() {
    const params = new URLSearchParams();
    if (debouncedSearch) params.set("q", debouncedSearch);
    const qs = params.toString() ? `?${params.toString()}` : "";
    const token = getAccessToken();

    setExportError(null);
    setExporting(true);
    try {
      // Fetch with bearer in the Authorization header (vs. JWT-in-URL),
      // then Blob → anchor-click to drive the browser download with
      // Content-Disposition's filename. Caps the held memory at the
      // BE's EXPORT_MAX_ROWS (~10k rows ≈ a few MB) so this is safe.
      const resp = await fetch(`${BASE}/api/v1/decisions/export.csv${qs}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const truncated = resp.headers.get("X-Export-Truncated") === "true";
      const blob = await resp.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      const today = new Date().toISOString().slice(0, 10);
      a.href     = url;
      a.download = `kaori-decisions-${today}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      if (truncated) {
        setExportError("Đã xuất 10.000 dòng đầu — kết quả bị cắt. Hãy thu hẹp khoảng thời gian hoặc dùng bộ lọc để xuất nốt phần còn lại.");
      }
    } catch (e) {
      setExportError(`Không tải được CSV: ${e instanceof Error ? e.message : "lỗi không rõ"}.`);
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-h1 font-serif text-ink">Nhật ký quyết định AI</h1>
          <p className="text-small text-ink-muted mt-1">
            Mọi quyết định tự động đều được ghi lại — K-6 invariant.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {data && (
            <div className="flex items-center gap-2 text-small text-ink-muted bg-surface border border-subtle rounded-xl px-3 py-1.5">
              <Brain className="w-4 h-4 text-brand-500" />
              {totalKnown.toLocaleString("vi-VN")}{hasNextPage ? "+" : ""} quyết định
            </div>
          )}
          <Button variant="outline" onClick={handleExport} disabled={isLoading || exporting}>
            <Download className="w-4 h-4 mr-1.5" />
            {exporting ? "Đang xuất..." : "Xuất CSV"}
          </Button>
        </div>
      </div>

      {exportError && (
        <div className="rounded-md-custom border border-warning-100 bg-warning-50 px-4 py-3 text-small text-warning-700 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{exportError}</span>
        </div>
      )}

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[#B0A698]" />
        <input
          type="text"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder="Tìm theo đối tượng / lý do..."
          className="w-full pl-9 pr-3 py-2 rounded-xl border border-subtle bg-surface text-small focus:outline-none focus:ring-2 focus:ring-brand-300"
        />
      </div>

      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-12" />)}
        </div>
      )}

      {isError && (
        <Card className="border-danger-200 bg-danger-50/30">
          <CardContent className="pt-6 text-small text-danger-700">{t("error.generic")}</CardContent>
        </Card>
      )}

      {!isLoading && !isError && (
        <>
          <DataTable<DecisionAudit>
            columns={COLUMNS}
            rows={rows}
            page={1}
            pageSize={rows.length || PAGE_SIZE}
            total={rows.length}
            onPageChange={() => {}}
            emptyMessage="Chưa có quyết định nào được ghi lại."
          />
          {hasNextPage && (
            <div className="flex justify-center">
              <Button
                variant="outline"
                onClick={() => fetchNextPage()}
                disabled={isFetchingNextPage}
              >
                {isFetchingNextPage ? "Đang tải..." : "Tải thêm"}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
