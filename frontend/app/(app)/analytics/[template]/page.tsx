"use client";

import { use } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Loader2, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useT } from "@/lib/i18n/provider";
import { fmtDateTime } from "@/lib/format";

// Inline FlexibleChart — reuses existing Recharts setup from the pipeline
import FlexibleChart from "@/components/charts/FlexibleChart";

interface AnalysisResult {
  id: string;
  template_id: string;
  status: "done" | "running" | "error";
  created_at: string;
  results_payload?: {
    narrative?: string;
    blocks?: Array<{
      type: "chart" | "stats_card" | "narrative";
      title?: string;
      chart_kind?: string;
      data?: unknown[];
      columns?: string[];
      value?: string | number;
      label?: string;
      body?: string;
    }>;
    kpis?: Array<{ key: string; value: unknown }>;
  };
}

const TEMPLATE_LABEL: Record<string, string> = {
  summary_stats:  "Thống kê tổng quan",   time_series:   "Chuỗi thời gian",
  distribution:   "Phân phối dữ liệu",     correlation:   "Tương quan",
  clustering:     "Phân cụm",              cohort:        "Cohort",
  churn:          "Churn",                 anomaly:       "Dị thường",
  regression:     "Hồi quy",               bank_classify: "Giao dịch",
};

export default function AnalysisTemplatePage({
  params,
}: {
  params: Promise<{ template: string }>;
}) {
  const { template } = use(params);
  const t = useT();

  const { data, isLoading, isError } = useQuery<{ data: AnalysisResult[] }>({
    queryKey: ["analytics-runs", template],
    queryFn:  () => api(`/api/v1/analytics/runs?template_id=${template}&limit=1`),
    staleTime: 20_000,
  });

  const run = data?.data?.[0];

  return (
    <div className="space-y-6">
      {/* Back + title */}
      <div className="flex items-center gap-3">
        <Link href="/analytics" className="text-ink-muted hover:text-ink transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-h2 font-serif text-ink">
            {TEMPLATE_LABEL[template] ?? template}
          </h1>
          {run && (
            <p className="text-tiny text-[#B0A698] mt-0.5">
              Lần chạy gần nhất: {fmtDateTime(run.created_at)}
            </p>
          )}
        </div>
        {run && (
          <Badge tone={run.status === "done" ? "success" : run.status === "error" ? "danger" : "info"}>
            {run.status === "done" ? "Hoàn tất" : run.status === "error" ? "Lỗi" : "Đang chạy"}
          </Badge>
        )}
      </div>

      {/* Loading skeleton */}
      {isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-64" />
          <div className="grid grid-cols-3 gap-4">
            <Skeleton className="h-24" /><Skeleton className="h-24" /><Skeleton className="h-24" />
          </div>
        </div>
      )}

      {/* Error */}
      {isError && (
        <Card className="border-danger-200 bg-danger-50/30">
          <CardContent className="pt-6 flex items-center gap-3 text-danger-700">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <p className="text-small">{t("error.generic")}</p>
          </CardContent>
        </Card>
      )}

      {/* Running */}
      {run?.status === "running" && (
        <Card>
          <CardContent className="py-12 flex flex-col items-center gap-3">
            <Loader2 className="w-8 h-8 text-brand-400 animate-spin" />
            <p className="text-small text-ink-muted">Phân tích đang chạy, vui lòng chờ…</p>
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {run?.status === "done" && run.results_payload && (
        <ResultBlocks payload={run.results_payload} />
      )}

      {/* Error run */}
      {run?.status === "error" && (
        <Card className="border-danger-200">
          <CardContent className="pt-6">
            <p className="text-small text-danger-700">Phân tích gặp lỗi. Vui lòng chạy lại.</p>
          </CardContent>
        </Card>
      )}

      {/* No runs */}
      {!isLoading && !isError && !run && (
        <Card>
          <CardContent className="py-10 text-center text-small text-ink-muted">
            Chưa có lần phân tích nào cho template này.{" "}
            <Link href="/pipeline/new" className="text-brand-600 hover:underline">
              Tạo pipeline mới →
            </Link>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ── Result block renderer ──────────────────────────────────────────────────────

function ResultBlocks({ payload }: { payload: NonNullable<AnalysisResult["results_payload"]> }) {
  const blocks = payload.blocks ?? [];
  if (blocks.length === 0 && payload.narrative) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-body text-ink whitespace-pre-wrap leading-relaxed">
            {payload.narrative}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {blocks.map((block, i) => {
        if (block.type === "chart" && block.data && block.columns) {
          return (
            <Card key={i}>
              {block.title && (
                <CardHeader><CardTitle>{block.title}</CardTitle></CardHeader>
              )}
              <CardContent className="pb-6">
                <FlexibleChart
                  block={{
                    id: `block-${i}`,
                    type: "chart",
                    title: block.title,
                    default_chart: (block.chart_kind as any) ?? "bar",
                    data: (block.data as any) ?? [],
                  }}
                />
              </CardContent>
            </Card>
          );
        }
        if (block.type === "stats_card") {
          return (
            <Card key={i}>
              <CardContent className="pt-5">
                <p className="text-label text-[#B0A698]">{block.label}</p>
                <p className="text-kpi font-serif text-ink tabular-nums mt-1">
                  {block.value ?? "—"}
                </p>
              </CardContent>
            </Card>
          );
        }
        if (block.type === "narrative") {
          return (
            <Card key={i}>
              {block.title && (
                <CardHeader><CardTitle>{block.title}</CardTitle></CardHeader>
              )}
              <CardContent className="pb-6">
                <p className="text-body text-ink whitespace-pre-wrap leading-relaxed">
                  {block.body}
                </p>
              </CardContent>
            </Card>
          );
        }
        return null;
      })}
    </div>
  );
}
