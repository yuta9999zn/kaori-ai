"use client";

/**
 * F-022 — Pipeline Run History.
 *
 * Reads from ``GET /api/v1/pipelines?cursor=&limit=`` (cursor pagination,
 * envelope ``{data, meta:{cursor, has_more, ...}}``). The previous mock
 * endpoint ``/api/v1/pipeline/runs`` (page-based) is kept in MSW for the
 * legacy upload wizard polling but the list page now consumes the real
 * shape end-to-end.
 */

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useInfiniteQuery } from "@tanstack/react-query";
import { Plus, FileText } from "lucide-react";
import { pipelinesApi } from "@/lib/api/pipelines";
import { DataTable, type Column } from "@/components/ui/data-table";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useT } from "@/lib/i18n/provider";
import { fmtDateTime } from "@/lib/format";

// Backend status set — canonical per 002_pipeline.sql:16-20 CHECK.
// Sprint 7 PR C: dropped the legacy `analysis_running` alias (FE-only,
// never matched what the BE emitted). `cleaning_pending` is BE-emitted
// from routers/schema.py but not in the original CHECK; tracked.
type RunStatus =
  | "uploading" | "bronze_complete" | "schema_review"
  | "cleaning_pending"
  | "silver_complete"
  | "analyzing"
  | "analysis_complete" | "failed" | "cancelled"
  | string;

interface PipelineRun {
  run_id: string;
  status: RunStatus;
  filename: string | null;
  original_size_bytes: number | null;
  detected_language: string | null;
  sheet_count: number | null;
  row_count_bronze: number | null;
  row_count_silver: number | null;
  quality_score: number | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

interface PipelineListPage {
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

const PAGE_SIZE = 50;

function statusMeta(s: RunStatus): { tone: BadgeTone; labelKey: string | null; label: string | null } {
  switch (s) {
    case "analysis_complete": return { tone: "success", labelKey: "pipelinePage.statusComplete",        label: null };
    case "failed":            return { tone: "danger",  labelKey: "pipelinePage.statusFailed",          label: null };
    case "cancelled":         return { tone: "neutral", labelKey: "pipelinePage.statusCancelled",       label: null };
    case "uploading":         return { tone: "info",    labelKey: "pipelinePage.statusUploading",       label: null };
    case "bronze_complete":   return { tone: "info",    labelKey: "pipelinePage.statusBronzeComplete",  label: null };
    case "schema_review":     return { tone: "warning", labelKey: "pipelinePage.statusSchemaReview",    label: null };
    case "cleaning_pending":  return { tone: "warning", labelKey: "pipelinePage.statusCleaningPending", label: null };
    case "silver_complete":   return { tone: "info",    labelKey: "pipelinePage.statusSilverComplete",  label: null };
    case "analyzing":         return { tone: "info",    labelKey: "pipelinePage.statusAnalyzing",       label: null };
    default:                  return { tone: "neutral", labelKey: null, label: String(s) };
  }
}

export default function PipelineListPage() {
  const t = useT();
  const router = useRouter();

  // Sprint 7 PR C — row click jumps back into the wizard at the right step
  // for the run's current status. Reuses the existing `?run_id=&step=`
  // params the wizard already understands. No new page needed.
  function navigateToRun(row: PipelineRun) {
    const step =
      row.status === "schema_review"   ? "schema"  :
      row.status === "cleaning_pending"? "clean"   :
      row.status === "silver_complete" ? "analyze" :
      "results";
    router.push(`/pipeline/new?run_id=${row.run_id}&step=${step}`);
  }

  // Sprint 6.5 — PoC for the OpenAPI codegen pipeline. Uses the typed
  // `pipelinesApi.list()` wrapper (lib/api/pipelines.ts), whose query
  // params are validated against the BE spec at compile time. A BE
  // signature change shows up as a tsc error at the next codegen run.
  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useInfiniteQuery<PipelineListPage>({
      queryKey: ["pipelines"],
      initialPageParam: null as string | null,
      queryFn: ({ pageParam }) =>
        pipelinesApi.list({
          limit:  PAGE_SIZE,
          cursor: pageParam as string | undefined,
        }),
      getNextPageParam: (last) => (last.meta.has_more ? last.meta.cursor : undefined),
      staleTime: 30_000,
    });

  const rows: PipelineRun[] = (data?.pages ?? []).flatMap((p) => p.data);

  const COLUMNS: Column<PipelineRun>[] = [
    {
      key: "filename",
      header: t("pipelinePage.colFilename"),
      render: (row) => (
        <div className="flex items-center gap-2.5 min-w-0">
          <FileText className="w-4 h-4 text-brand-400 shrink-0" strokeWidth={1.5} />
          <span className="text-body-strong text-ink truncate">
            {row.filename ?? t("pipelinePage.noFilename")}
          </span>
        </div>
      ),
    },
    {
      key: "row_count_bronze",
      header: t("pipelinePage.colRowCount"),
      render: (row) => {
        const n = row.row_count_silver ?? row.row_count_bronze;
        return (
          <span className="text-small text-ink-muted tabular-nums">
            {n != null ? n.toLocaleString("vi-VN") : "—"}
          </span>
        );
      },
    },
    {
      key: "status",
      header: t("pipelinePage.colStatus"),
      render: (row) => {
        const { tone, labelKey, label } = statusMeta(row.status);
        return <Badge tone={tone}>{labelKey ? t(labelKey) : label}</Badge>;
      },
    },
    {
      key: "created_at",
      header: t("pipelinePage.colCreatedAt"),
      render: (row) => (
        <span className="text-tiny text-[#B0A698] tabular-nums">{fmtDateTime(row.created_at)}</span>
      ),
    },
  ];

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-h1 font-serif text-ink">{t("nav.pipeline")}</h1>
          <p className="text-small text-ink-muted mt-1">{t("pipelinePage.description")}</p>
        </div>
        <Button asChild>
          <Link href="/pipeline/new">
            <Plus className="w-4 h-4 mr-1.5" />
            {t("pipelinePage.newPipeline")}
          </Link>
        </Button>
      </div>

      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12" />)}
        </div>
      )}

      {isError && (
        <Card className="border-danger-200 bg-danger-50/30">
          <CardContent className="pt-6 text-small text-danger-700">{t("error.generic")}</CardContent>
        </Card>
      )}

      {!isLoading && !isError && rows.length === 0 && (
        <EmptyState
          icon={FileText}
          title={t("pipelinePage.emptyTitle")}
          description={t("pipelinePage.emptyDescription")}
          action={{ href: "/pipeline/new", label: t("pipelinePage.emptyActionLabel") }}
        />
      )}

      {!isLoading && !isError && rows.length > 0 && (
        <>
          <DataTable<PipelineRun>
            columns={COLUMNS}
            rows={rows}
            page={1}
            pageSize={rows.length}
            total={rows.length}
            onPageChange={() => {}}
            onRowClick={navigateToRun}
            emptyMessage={t("pipelinePage.tableEmptyMessage")}
          />
          {hasNextPage && (
            <div className="flex justify-center">
              <Button
                variant="outline"
                onClick={() => fetchNextPage()}
                disabled={isFetchingNextPage}
              >
                {isFetchingNextPage ? t("pipelinePage.loadingMore") : t("pipelinePage.loadMore")}
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
