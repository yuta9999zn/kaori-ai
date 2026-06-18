"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Upload, CheckCircle2, AlertTriangle, BarChart2, ArrowRight, Loader2, RefreshCw } from "lucide-react";
import { dashboardApi } from "@/lib/api/client";
import { KpiCard } from "@/components/ui/kpi-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Progress } from "@/components/ui/progress";
import { useT } from "@/lib/i18n/provider";
import { fmtInt, fmtPct } from "@/lib/format";

// ── Types ──────────────────────────────────────────────────────────────────────

type DashboardState =
  | "no_data" | "first_upload" | "pending_review"
  | "analysis_ready" | "results_ready";

interface KpiItem { template: string; title: string; data: Record<string, unknown> }

interface StatePayload {
  state: DashboardState;
  run_id: string | null;
  pipeline_status?: string;
  analysis_run_id?: string | null;
  templates_run?: string[];
  kpis?: KpiItem[];
  metrics?: {
    datasets_processed?: number; datasets_delta?: number;
    analyses_run?: number;        analyses_delta?: number;
    insights_generated?: number;  insights_delta?: number;
    avg_data_quality?: number;
  };
  quota?: { used: number; total: number };
}

const POLLING_STATES: DashboardState[] = ["first_upload", "pending_review", "analysis_ready"];

// Sprint 7 PR C — canonicalized to the BE DB CHECK constraint (002_pipeline.sql:16-20).
// FE used to invent its own spellings (`schema_pending`, `analysis_running`,
// `analysis_done`) which never matched what /pipelines emitted; status filtering
// + DLQ replay on those keys silently dropped runs.
const STATUS_LABELS: Record<string, string> = {
  uploading:         "Đang tải lên…",
  processing:        "Đang xử lý file…",
  bronze_complete:   "Đọc dữ liệu xong",
  schema_review:     "Chờ xác nhận cột",
  cleaning_pending:  "Chờ làm sạch dữ liệu",
  silver_complete:   "Dữ liệu sẵn sàng",
  analyzing:         "Đang phân tích…",
  analysis_complete: "Phân tích hoàn tất",
};

const TEMPLATE_LABELS: Record<string, string> = {
  summary_stats: "Thống kê",   time_series: "Chuỗi TG",  distribution: "Phân phối",
  correlation:   "Tương quan", clustering:  "Phân cụm",  cohort:       "Cohort",
  churn:         "Churn",      anomaly:     "Dị thường",  regression:   "Hồi quy",
  bank_classify: "Giao dịch",
};

// ── Component ──────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const router    = useRouter();
  const t         = useT();
  const [payload, setPayload] = useState<StatePayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(false);
  const timerRef  = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let alive = true;
    async function poll() {
      try {
        const { data } = await dashboardApi.getState();
        if (!alive) return;
        setPayload(data);
        setLoading(false);
        setError(false);
        if (POLLING_STATES.includes(data.state)) {
          timerRef.current = setTimeout(poll, 3000);
        }
      } catch {
        if (!alive) return;
        setError(true);
        setLoading(false);
        timerRef.current = setTimeout(poll, 5000);
      }
    }
    poll();
    return () => { alive = false; if (timerRef.current) clearTimeout(timerRef.current); };
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center py-32">
      <Loader2 className="w-8 h-8 text-brand-500 animate-spin" />
    </div>
  );

  if (error && !payload) return (
    <div className="flex flex-col items-center justify-center py-32 gap-4 text-ink-muted">
      <p className="text-body">{t('error.network')}</p>
      <Button variant="outline" size="sm" onClick={() => { setLoading(true); setError(false); }}>
        <RefreshCw className="w-4 h-4 mr-2" />{t('common.retry')}
      </Button>
    </div>
  );

  const state = payload?.state ?? "no_data";
  const m     = payload?.metrics;
  const quota = payload?.quota;
  const quotaPct = quota ? Math.round((quota.used / quota.total) * 100) : 0;

  const showMetrics = state === "results_ready" && m;

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-h1 font-serif text-ink">{t('dashboard.title')}</h1>
          <p className="text-small text-ink-muted mt-1">{t('dashboard.subtitle')}</p>
        </div>
        <Button asChild size="sm">
          <Link href="/pipeline/new">
            <Upload className="w-4 h-4 mr-1.5" />
            {t('dashboard.cta.upload')}
          </Link>
        </Button>
      </div>

      {/* KPI row — only show when we have metrics */}
      {showMetrics && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard label={t('dashboard.kpi.datasets')} value={fmtInt(m!.datasets_processed)}
            trendPct={m!.datasets_delta} tone="brand" />
          <KpiCard label={t('dashboard.kpi.analyses')} value={fmtInt(m!.analyses_run)}
            trendPct={m!.analyses_delta} tone="success" />
          <KpiCard label={t('dashboard.kpi.insights')} value={fmtInt(m!.insights_generated)}
            trendPct={m!.insights_delta} tone="info" />
          <KpiCard label={t('dashboard.kpi.quality')} value={fmtPct((m!.avg_data_quality ?? 0) / 100)}
            tone={m!.avg_data_quality && m.avg_data_quality >= 70 ? "success" : "warning"} />
        </div>
      )}

      {/* State-driven main area */}
      {state === "no_data" && <NoDataState t={t} />}
      {state === "first_upload" && <ProcessingState status={payload?.pipeline_status} />}
      {state === "pending_review" && (
        <PendingReviewState runId={payload?.run_id} status={payload?.pipeline_status} />
      )}
      {state === "analysis_ready" && <AnalysisReadyState runId={payload?.run_id} />}
      {state === "results_ready" && (
        <ResultsReadyState
          analysisRunId={payload?.analysis_run_id ?? null}
          templatesRun={payload?.templates_run ?? []}
          kpis={payload?.kpis ?? []}
          onViewResults={() => router.push(`/pipeline?analysis_run_id=${payload?.analysis_run_id}`)}
        />
      )}

      {/* Quota bar */}
      {quota && (
        <Card>
          <CardContent className="pt-5 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-small font-medium text-ink">{t('dashboard.quota.title')}</span>
              <span className="text-small text-ink-muted">{quotaPct}% đã dùng</span>
            </div>
            <Progress value={quotaPct} tone={quotaPct > 80 ? "warning" : "brand"} />
            <div className="flex items-center justify-between text-tiny text-[#B0A698]">
              <span>{fmtInt(quota.used)} / {fmtInt(quota.total)} bộ dữ liệu</span>
              <Link href="/subscription" className="text-brand-600 hover:text-brand-700">
                {t('dashboard.quota.upgrade')}
              </Link>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ── State views ────────────────────────────────────────────────────────────────

function NoDataState({ t }: { t: (k: string) => string }) {
  return (
    <EmptyState
      icon={Upload}
      title="Chưa có dữ liệu"
      description="Bắt đầu bằng cách tải lên file Excel, CSV, ODS hoặc ZIP. Hệ thống tự động nhận diện, làm sạch và phân tích."
      action={{ href: "/pipeline/new", label: t("dashboard.cta.upload") }}
    />
  );
}

function ProcessingState({ status }: { status?: string }) {
  return (
    <Card>
      <CardContent className="pt-8 pb-8 text-center">
        <Loader2 className="w-10 h-10 text-brand-400 animate-spin mx-auto mb-4" />
        <p className="text-body-strong text-ink">
          {STATUS_LABELS[status ?? ""] ?? "Đang xử lý…"}
        </p>
        <p className="text-small text-ink-muted mt-1">Trang tự động cập nhật mỗi 3 giây</p>
      </CardContent>
    </Card>
  );
}

function PendingReviewState({ runId, status }: { runId?: string | null; status?: string }) {
  const isSchema = status === "schema_review";
  const href = runId
    ? `/pipeline?run_id=${runId}&step=${isSchema ? "schema" : "clean"}`
    : "/pipeline/new";
  return (
    <Card className="border-warning-200 bg-warning-50/40">
      <CardContent className="pt-6 flex items-start gap-5">
        <div className="rounded-xl bg-warning-100 text-warning-600 p-2.5 shrink-0">
          <AlertTriangle className="w-5 h-5" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <p className="text-body-strong text-warning-800">
              {isSchema ? "Cần xác nhận cột dữ liệu" : "Cần xác nhận làm sạch dữ liệu"}
            </p>
            <Badge tone="warning">Chờ xử lý</Badge>
          </div>
          <p className="text-small text-warning-700">
            {isSchema
              ? "Hệ thống đã nhận diện cột. Vui lòng kiểm tra và xác nhận trước khi tiếp tục."
              : "Hệ thống đề xuất các quy tắc làm sạch. Vui lòng chọn và xác nhận."}
          </p>
          <Button asChild size="sm" className="mt-4">
            <Link href={href}>
              {isSchema ? "Xem lại cột" : "Xem lại làm sạch"}
              <ArrowRight className="w-4 h-4 ml-1.5" />
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function AnalysisReadyState({ runId }: { runId?: string | null }) {
  const href = runId ? `/pipeline?run_id=${runId}&step=analyze` : "/pipeline/new";
  return (
    <Card className="border-success-200 bg-success-50/30">
      <CardContent className="pt-6 flex items-start gap-5">
        <div className="rounded-xl bg-success-100 text-success-600 p-2.5 shrink-0">
          <CheckCircle2 className="w-5 h-5" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <p className="text-body-strong text-success-800">Dữ liệu Silver đã sẵn sàng</p>
            <Badge tone="success">Sẵn sàng</Badge>
          </div>
          <p className="text-small text-success-700">
            Chọn 1 hoặc nhiều template phân tích. Các template chạy đồng thời.
          </p>
          <Button asChild size="sm" className="mt-4">
            <Link href={href}>
              Chọn phân tích <ArrowRight className="w-4 h-4 ml-1.5" />
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function ResultsReadyState({
  analysisRunId, templatesRun, kpis, onViewResults,
}: {
  analysisRunId: string | null;
  templatesRun: string[];
  kpis: KpiItem[];
  onViewResults: () => void;
}) {
  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-h2 font-serif text-ink">Kết quả phân tích</h2>
          <p className="text-small text-ink-muted mt-0.5">{templatesRun.length} phân tích hoàn tất</p>
        </div>
        <Button onClick={onViewResults}>
          Xem chi tiết <ArrowRight className="w-4 h-4 ml-1.5" />
        </Button>
      </div>

      {/* Template chips */}
      <div className="flex flex-wrap gap-2">
        {templatesRun.map((t) => (
          <Badge key={t} tone="brand">{TEMPLATE_LABELS[t] ?? t}</Badge>
        ))}
      </div>

      {/* KPI cards from analysis results */}
      {kpis.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {kpis.slice(0, 6).map((kpi, i) => {
            const entries = Object.entries(kpi.data).slice(0, 3);
            return (
              <Card key={i}>
                <CardContent className="pt-5">
                  <p className="text-label text-[#B0A698] mb-3">
                    {TEMPLATE_LABELS[kpi.template] ?? kpi.template} · {kpi.title}
                  </p>
                  <div className="space-y-2">
                    {entries.map(([k, v]) => (
                      <div key={k} className="flex justify-between items-baseline gap-3">
                        <span className="text-small text-ink-muted capitalize truncate">{k}</span>
                        <span className="text-body-strong text-ink tabular-nums shrink-0">
                          {v == null ? "—" : String(v)}
                        </span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      ) : (
        <Card>
          <CardContent className="py-8 text-center">
            <BarChart2 className="w-8 h-8 text-brand-300 mx-auto mb-3" strokeWidth={1.5} />
            <p className="text-small text-ink-muted">
              Nhấn "Xem chi tiết" để xem biểu đồ và phân tích đầy đủ.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
