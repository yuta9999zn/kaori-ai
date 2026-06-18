"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart2, TrendingUp, Layers, ScatterChart, PieChart,
  Users, Activity, Brain, GitBranch, Banknote,
  Clock, CheckCircle2, AlertCircle, ChevronRight,
} from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useT } from "@/lib/i18n/provider";
import { fmtDateTime } from "@/lib/format";

// ── Template metadata ──────────────────────────────────────────────────────────

const TEMPLATES = [
  { id: "summary_stats", icon: BarChart2,    descKey: "analytics.summary_stats.title",  minRows: 5  },
  { id: "time_series",   icon: TrendingUp,   descKey: "analytics.time_series.title",    minRows: 14 },
  { id: "distribution",  icon: Layers,       descKey: "analytics.distribution.title",   minRows: 30 },
  { id: "correlation",   icon: ScatterChart, descKey: "analytics.correlation.title",    minRows: 20 },
  { id: "clustering",    icon: PieChart,     descKey: "analytics.clustering.title",     minRows: 50 },
  { id: "cohort",        icon: Users,        descKey: "analytics.cohort.title",         minRows: 100 },
  { id: "churn",         icon: Activity,     descKey: "analytics.churn.title",          minRows: 100 },
  { id: "anomaly",       icon: Brain,        descKey: "analytics.anomaly.title",        minRows: 30 },
  { id: "regression",    icon: GitBranch,    descKey: "analytics.regression.title",     minRows: 50 },
  { id: "bank_classify", icon: Banknote,     descKey: "analytics.bank_classify.title",  minRows: 10 },
];

type RunStatus = "running" | "done" | "error";

interface AnalysisRun {
  id: string;
  template_id: string;
  status: RunStatus;
  created_at: string;
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function AnalyticsPage() {
  const t = useT();

  const { data: runsData, isLoading } = useQuery<{ data: AnalysisRun[] }>({
    queryKey: ["analytics-runs"],
    queryFn:  () => api("/api/v1/analytics/runs?limit=100"),
    staleTime: 30_000,
  });

  const lastRunByTemplate = (runsData?.data ?? []).reduce<Record<string, AnalysisRun>>((acc, r) => {
    if (!acc[r.template_id] || r.created_at > acc[r.template_id].created_at) acc[r.template_id] = r;
    return acc;
  }, {});

  const hasAnyRun = Object.keys(lastRunByTemplate).length > 0;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-h1 font-serif text-ink">{t("analytics.title")}</h1>
        <p className="text-small text-ink-muted mt-1">{t("analytics.subtitle")}</p>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {TEMPLATES.map((tmpl) => (
            <Skeleton key={tmpl.id} className="h-36" />
          ))}
        </div>
      ) : !hasAnyRun ? (
        <EmptyState
          icon={BarChart2}
          title="Chưa có phân tích nào"
          description="Tải dữ liệu lên và chọn template phân tích để bắt đầu."
          action={{ href: "/pipeline/new", label: "Tạo pipeline mới" }}
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {TEMPLATES.map((tmpl) => {
            const run  = lastRunByTemplate[tmpl.id];
            const Icon = tmpl.icon;
            return (
              <TemplateCard
                key={tmpl.id}
                id={tmpl.id}
                Icon={Icon}
                label={t(tmpl.descKey)}
                run={run}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── TemplateCard ───────────────────────────────────────────────────────────────

function TemplateCard({
  id, Icon, label, run,
}: {
  id: string;
  Icon: any;
  label: string;
  run?: AnalysisRun;
}) {
  const { tone, badgeLabel, StatusIcon } = runMeta(run?.status);
  const canNavigate = !!run;

  const inner = (
    <Card className={`group transition-shadow hover:shadow-card ${canNavigate ? "cursor-pointer" : ""}`}>
      <CardContent className="pt-5 flex items-start gap-4">
        <div className="rounded-xl bg-brand-50 text-brand-600 p-2.5 shrink-0">
          <Icon className="w-5 h-5" strokeWidth={1.75} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <p className="text-body-strong text-ink">{label}</p>
            {run && <Badge tone={tone}>{badgeLabel}</Badge>}
          </div>
          {run ? (
            <p className="text-tiny text-[#B0A698] mt-1">
              {run.status === "running" ? "Đang chạy…" : fmtDateTime(run.created_at)}
            </p>
          ) : (
            <p className="text-tiny text-[#C0B8A8] mt-1">Chưa có lần chạy nào</p>
          )}
        </div>
        {canNavigate && (
          <ChevronRight className="w-4 h-4 text-[#C0B8A8] mt-0.5 group-hover:text-brand-500 transition-colors shrink-0" />
        )}
      </CardContent>
    </Card>
  );

  return canNavigate
    ? <Link href={`/analytics/${id}`}>{inner}</Link>
    : inner;
}

function runMeta(status?: RunStatus): { tone: BadgeTone; badgeLabel: string; StatusIcon: any } {
  switch (status) {
    case "done":    return { tone: "success", badgeLabel: "Hoàn tất",    StatusIcon: CheckCircle2 };
    case "running": return { tone: "info",    badgeLabel: "Đang chạy",   StatusIcon: Clock };
    case "error":   return { tone: "danger",  badgeLabel: "Lỗi",         StatusIcon: AlertCircle };
    default:        return { tone: "neutral", badgeLabel: "Chưa chạy",   StatusIcon: Clock };
  }
}
