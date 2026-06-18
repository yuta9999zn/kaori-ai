// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 24. /p2/pipelines/{id}/step-5-results — Step 5 Results (Executive redesign)
// ----------------------------------------------------------------------------
// GET /api/v1/analytics/runs/:id →
//   { id, run_id, templates[], status, overview, completed_at,
//     template_results:[{ template_id, status, results_payload, error_message }] }
// GET /api/v1/analytics/templates → [{ template_id, display_name, description }]
//
// Redesign goals (executive, not debug output):
//   1. Executive Summary card first — the run-level AI narrative (overview),
//      in business language. Degraded → calm "đang tổng hợp", never a red error.
//   2. KPI Highlight bar — the real computed summary stats, business-framed
//      (null_rate → "Dữ liệu đầy đủ %"). No fabricated numbers (K-3).
//   3. Per-template accordions — each analysis is a section; a skipped/failed
//      template shows WHY + a "Quay lại Bước 2" path, never a silent gap.
//   4. Charts with factual, data-derived captions + log-scale for mixed
//      magnitudes (chart-registry) + empty-chart collapse.
//   5. Next-Steps bar — CSV / PDF (print) / Share / Copy summary.
//
// Render is client-side via chart-registry (F-027). CSV export uses fetch+Blob
// (no JWT in URL — Sprint 7 PR A).
// ============================================================================

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import {
  ChevronLeft, ChevronDown, ChevronRight, Sparkles, Download, Share2,
  Lightbulb, AlertCircle, CheckCircle2, ShieldCheck, Globe, Lock, Loader2,
  Copy, Printer, BookOpen, ArrowLeftCircle,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, cn,
  api, formatVND,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { WizardStepper, PIPELINE_STATUS_BADGE, type PipelineStatus } from '@/components/p2/foundation-wizard';
import FlexibleChart from '@/components/charts/FlexibleChart';

interface ChartBlock {
  type: 'chart' | 'stats' | 'stats_card' | 'narrative' | 'table' | 'recommendation';
  id?:           string;
  title?:        string;
  chart_kind?:   'bar' | 'line' | 'pie' | 'scatter' | 'time_series' | 'area';
  data?:         any;
  kpis?:         Array<{ name: string; value: string; trend_pct?: number; trend_is_good?: boolean }>;
  text?:         string;
  confidence?:   number;
  degraded?:     boolean;   // narrative: LLM unavailable → text is a graceful notice, not an insight
  reason?:       string;    // why it degraded (timeout / provider down) — diagnostic only
  provider?:     string;
  columns?:      string[];
  rows?:         any[][];
  actions?:      Array<{ title: string; description: string; impact_vnd?: number }>;
}

interface TemplateResult {
  template_id:   string;
  display_name:  string;
  description?:  string;
  status:        'done' | 'error' | string;
  error_message?: string;
  blocks:        ChartBlock[];
}

interface Overview {
  narrative?:          string | null;
  row_count?:          number;
  col_count?:          number;
  knowledge_coverage?: number | null;
}

interface AnalysisRun {
  id:                string;
  status:            PipelineStatus;
  consent_external:  boolean;
  template_ids:      string[];
  overview:          Overview;
  templates:         TemplateResult[];
  decision_audit_log_id?: string;
  finished_at?:      string;
}

const NARRATIVE_PLACEHOLDER_PREFIX = 'Nhận xét AI tạm thời chưa khả dụng';

export default function PipelineStep5Results() {
  const params = useParams<{ id: string }>();
  const search = useSearchParams();
  const pipelineId = params?.id ?? '';
  const runId = search?.get('run_id') ?? pipelineId;

  const [run,     setRun]     = useState<AnalysisRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [exporting, setExporting] = useState(false);
  const [staleFinalizer, setStaleFinalizer] = useState(false);
  const [copied, setCopied] = useState(false);
  const catalogRef = useRef<Record<string, { display_name: string; description?: string }>>({});
  const startRef = useRef<number>(Date.now());

  // Real template names (not an id→label hardcode): fetch the catalog once so
  // each section header shows the BE's own display_name + required-data hint.
  async function loadCatalog() {
    try {
      const list = await api<any[]>(`/api/v1/analytics/templates`);
      const map: Record<string, { display_name: string; description?: string }> = {};
      (list ?? []).forEach((t: any) => {
        if (t?.template_id) map[t.template_id] = { display_name: t.display_name, description: t.description };
      });
      catalogRef.current = map;
    } catch { /* non-blocking — fall back to prettified id */ }
  }

  function prettyId(id: string) {
    return id.replace(/[_-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }

  async function load() {
    setLoading(true);
    setProblem(null);
    try {
      const raw = await api<any>(`/api/v1/analytics/runs/${runId}`);
      const be = String(raw.status || '');
      const trs = raw.template_results ?? [];

      // Best-effort finalizer-lag guard (unchanged): if every template settled
      // but the run-level status hasn't flipped after 60s, render anyway.
      const allSettled = trs.length > 0 &&
        trs.every((t: any) => ['done', 'failed', 'error'].includes(String(t.status)));
      const lagged = (be === 'running' || be === 'queued' || be === '') &&
        allSettled && (Date.now() - startRef.current > 60_000);
      setStaleFinalizer(lagged);

      // terminal status is 'analysis_complete' (PipelineStatus) — see history note.
      const status = (be === 'done' || be === 'analysis_complete' || be === 'completed' || lagged)
                       ? 'analysis_complete'
                   : be === 'failed' ? 'failed'
                   : 'analyzing';   // queued/running → keep polling

      const templates: TemplateResult[] = trs.map((tr: any) => {
        let p = tr.results_payload;
        if (typeof p === 'string') { try { p = JSON.parse(p); } catch { p = {}; } }
        const meta = catalogRef.current[tr.template_id];
        return {
          template_id:  tr.template_id,
          display_name: meta?.display_name ?? prettyId(tr.template_id),
          description:  meta?.description,
          status:       String(tr.status),
          error_message: tr.error_message ?? undefined,
          blocks:       (p && p.blocks) ? p.blocks : [],
        };
      });

      // overview is jsonb {narrative,row_count,col_count,knowledge_coverage}.
      let ov: Overview = raw.overview ?? {};
      if (typeof ov === 'string') { try { ov = JSON.parse(ov); } catch { ov = {}; } }

      setRun({
        id:               raw.id ?? runId,
        status,
        consent_external: false,
        template_ids:     raw.templates ?? [],
        overview:         ov ?? {},
        templates,
        finished_at:      raw.completed_at ?? undefined,
      });
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }

  // Reset the 60s clock + clear stale warning when runId changes (SPA nav).
  useEffect(() => {
    if (!runId) return;
    startRef.current = Date.now();
    setStaleFinalizer(false);
    loadCatalog().finally(load);
  }, [runId]);

  // Poll while still analyzing
  useEffect(() => {
    if (run?.status !== 'analyzing') return;
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [run?.status]);

  // ── derived: all blocks (for KPI bar) + executive summary text ──────────────
  const allBlocks = useMemo(
    () => (run?.templates ?? []).flatMap((t) => t.blocks),
    [run],
  );
  const summaryText = useMemo(() => {
    const n = run?.overview?.narrative;
    if (!n || !n.trim() || n.startsWith(NARRATIVE_PLACEHOLDER_PREFIX)) return null;
    return n.trim();
  }, [run]);

  async function exportCsv() {
    setExporting(true);
    try {
      const res = await fetch(`/api/v1/analytics/runs/${runId}/export.csv`, {
        headers: { Authorization: `Bearer ${window.localStorage.getItem('kaori.access_token') ?? ''}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = `analysis-${runId}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setProblem({ title: 'Xuất CSV thất bại', detail: String(err?.message ?? err) });
    } finally {
      setExporting(false);
    }
  }

  function copySummary() {
    if (!summaryText) return;
    navigator.clipboard.writeText(summaryText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const isDone = run?.status === 'analysis_complete';

  return (
    <>
      <PageHeader
        title="Kết quả phân tích"
        description="Bước 5 / 5 — tóm tắt điều hành, chỉ số chính, và chi tiết từng phân tích."
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-6">
        <WizardStepper current={5} pipelineId={pipelineId} />

        <ErrorBanner problem={problem} />

        {staleFinalizer && (
          <div className="rounded-md-custom bg-[var(--state-warning)]/10 border border-[var(--state-warning)]/30 p-3 flex items-start gap-3">
            <AlertCircle className="w-4 h-4 text-[var(--state-warning)] shrink-0 mt-0.5" />
            <p className="text-sm text-[#9E814D]">
              Các phân tích đã chạy xong và kết quả hiển thị bên dưới, nhưng hệ thống chưa kịp đánh dấu
              "hoàn tất". Đây là kết quả thật — bạn có thể tải lại trang sau ít phút nếu trạng thái chưa cập nhật.
            </p>
          </div>
        )}

        {/* Status strip */}
        {run && (
          <StatusStrip run={run} />
        )}

        {loading && !run ? (
          <div className="space-y-4">
            {[1,2,3].map((i) => <div key={i} className="h-40 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse" />)}
          </div>
        ) : run ? (
          <>
            {/* 1. Executive Summary */}
            <ExecutiveSummary
              status={run.status}
              text={summaryText}
              coverage={run.overview?.knowledge_coverage ?? null}
              rowCount={run.overview?.row_count}
              colCount={run.overview?.col_count}
              onCopy={copySummary}
              copied={copied}
            />

            {/* 2. KPI Highlight bar */}
            <KpiBar blocks={allBlocks} />

            {/* 3. Per-template sections */}
            {run.templates.length > 0 ? (
              <div className="space-y-4">
                {run.templates.map((t) => (
                  <TemplateSection key={t.template_id} template={t} pipelineId={pipelineId} />
                ))}
              </div>
            ) : isDone ? (
              <div className="p-12 text-center text-[var(--text-secondary)] bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)]">
                Pipeline hoàn tất nhưng không có kết quả phân tích nào. Vui lòng liên hệ hỗ trợ.
              </div>
            ) : null}

            {/* 5. Next-steps bar */}
            {isDone && (
              <NextStepsBar
                onExportCsv={exportCsv}
                exporting={exporting}
                onCopySummary={summaryText ? copySummary : null}
              />
            )}
          </>
        ) : null}

        <div className="flex items-start gap-3 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)] print:hidden">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            Biểu đồ render <span className="font-medium text-[var(--text-primary)]">client-side</span> qua chart-registry (F-027).
            Nhận xét bằng lời do AI nội bộ (Qwen) tổng hợp; số liệu và biểu đồ luôn đầy đủ kể cả khi nhận xét chưa sẵn sàng.
          </p>
        </div>

        <div className="flex items-center justify-between print:hidden">
          <Button
            variant="secondary"
            onClick={() => (window.location.href = `/p2/pipelines/${pipelineId}/step-4-analyze`)}
          >
            <ChevronLeft className="w-4 h-4 mr-1" />
            Quay lại Bước 4
          </Button>
          <Button onClick={() => (window.location.href = '/p2/pipelines')}>
            Về danh sách pipeline
          </Button>
        </div>
      </div>
    </>
  );
}

// ----------------------------------------------------------------------------
// Status strip
// ----------------------------------------------------------------------------

function StatusStrip({ run }: { run: AnalysisRun }) {
  const doneCount = run.templates.filter((t) => t.status === 'done').length;
  const failCount = run.templates.filter((t) => t.status === 'error' || t.status === 'failed').length;
  return (
    <div className="flex items-start gap-4 p-4 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] shadow-soft-sm">
      <div className={cn(
        'w-12 h-12 rounded-full flex items-center justify-center shrink-0',
        run.status === 'analysis_complete' ? 'bg-[var(--state-success)]/15 text-[var(--state-success)]'
        : run.status === 'failed'           ? 'bg-[var(--state-error)]/15 text-[var(--state-error)]'
        : 'bg-[var(--state-warning)]/15 text-[var(--state-warning)]',
      )}>
        {run.status === 'analysis_complete' ? <CheckCircle2 className="w-6 h-6" />
          : run.status === 'failed'         ? <AlertCircle  className="w-6 h-6" />
          : <Loader2 className="w-6 h-6 animate-spin" />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant={PIPELINE_STATUS_BADGE[run.status].variant}>
            {PIPELINE_STATUS_BADGE[run.status].label}
          </Badge>
          <Badge variant={run.consent_external ? 'warning' : 'success'}>
            {run.consent_external ? <><Globe className="w-3 h-3 mr-1 inline" /> AI bên ngoài</> : <><Lock className="w-3 h-3 mr-1 inline" /> Qwen nội bộ</>}
          </Badge>
          {run.templates.length > 0 && (
            <span className="text-xs text-[var(--text-secondary)]">
              {doneCount}/{run.templates.length} phân tích hoàn tất
              {failCount > 0 && <span className="text-[#9B5050]"> · {failCount} cần xem lại</span>}
            </span>
          )}
        </div>
        {run.status === 'analyzing' && (
          <p className="text-sm text-[var(--text-secondary)] mt-2">
            Đang chạy... Trang sẽ tự cập nhật mỗi 5 giây.
          </p>
        )}
        {run.status === 'analysis_complete' && run.finished_at && (
          <p className="text-xs text-[var(--text-secondary)] mt-1">
            Hoàn tất: {run.finished_at}
            {run.decision_audit_log_id && (
              <> · <a href={`/p2/decisions/${run.decision_audit_log_id}`} className="text-[var(--primary-gold-dark)] underline">Xem audit log</a></>
            )}
          </p>
        )}
      </div>
    </div>
  );
}

// ----------------------------------------------------------------------------
// 1. Executive Summary
// ----------------------------------------------------------------------------

function ExecutiveSummary({
  status, text, coverage, rowCount, colCount, onCopy, copied,
}: {
  status: PipelineStatus; text: string | null; coverage: number | null;
  rowCount?: number; colCount?: number; onCopy: () => void; copied: boolean;
}) {
  const analyzing = status === 'analyzing';
  return (
    <div className="rounded-lg-custom bg-gradient-to-br from-[var(--primary-gold)]/8 to-[var(--bg-card)] border border-[var(--primary-gold)]/25 p-5 shadow-soft-sm">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-full bg-[var(--primary-gold)]/20 flex items-center justify-center shrink-0">
            <Sparkles className="w-5 h-5 text-[var(--primary-gold-dark)]" />
          </div>
          <div>
            <h2 className="font-serif text-lg text-[var(--text-primary)]">Tóm tắt phân tích</h2>
            {(rowCount != null || colCount != null) && (
              <p className="text-xs text-[var(--text-secondary)]">
                {rowCount != null && <>{rowCount.toLocaleString('vi-VN')} dòng</>}
                {rowCount != null && colCount != null && ' · '}
                {colCount != null && <>{colCount} cột</>}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {coverage != null && (
            <Badge variant={coverage >= 0.6 ? 'success' : coverage >= 0.3 ? 'warning' : 'neutral'}>
              <BookOpen className="w-3 h-3 mr-1 inline" /> Nền tảng {(coverage * 100).toFixed(0)}%
            </Badge>
          )}
          {text && (
            <button
              onClick={onCopy}
              className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border-color)] rounded-md-custom px-2.5 py-1.5 transition-colors bg-[var(--bg-card)]"
            >
              {copied ? <CheckCircle2 className="w-3.5 h-3.5 text-[var(--state-success)]" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? 'Đã sao chép' : 'Sao chép'}
            </button>
          )}
        </div>
      </div>

      {text ? (
        <p className="text-[15px] text-[var(--text-primary)] leading-relaxed whitespace-pre-line">{text}</p>
      ) : (
        <div className="flex items-start gap-3 rounded-md-custom bg-[var(--bg-card)]/60 border border-dashed border-[var(--border-color)] p-3">
          <Loader2 className={cn('w-4 h-4 text-[var(--text-secondary)] shrink-0 mt-0.5', analyzing && 'animate-spin')} />
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
            {analyzing
              ? 'Trợ lý AI đang đọc dữ liệu và viết nhận xét tổng quan…'
              : 'Các chỉ số và biểu đồ bên dưới đã đầy đủ. Phần nhận xét bằng lời sẽ xuất hiện khi trợ lý AI sẵn sàng — bạn có thể tải lại trang sau ít phút.'}
          </p>
        </div>
      )}
    </div>
  );
}

// ----------------------------------------------------------------------------
// 2. KPI Highlight bar — real computed stats, business-framed
// ----------------------------------------------------------------------------

// Friendly VN labels + framing for the common BE stats_card keys.
const STAT_LABEL: Record<string, string> = {
  total_rows: 'Số dòng', numeric_columns: 'Cột số',
  trend: 'Xu hướng', slope_per_period: 'Độ dốc/kỳ', periods_analysed: 'Số kỳ',
  forecast_horizon_days: 'Dự báo (ngày)', q1: 'Q1', median: 'Trung vị', q3: 'Q3',
  outlier_count: 'Số ngoại lệ', k: 'Số nhóm', silhouette_score: 'Điểm phân nhóm',
  rows_clustered: 'Số dòng phân nhóm',
};

function buildKpis(blocks: ChartBlock[]) {
  const seen = new Set<string>();
  const out: Array<{ name: string; value: string; good?: boolean }> = [];
  const push = (key: string, name: string, value: string, good?: boolean) => {
    if (seen.has(key)) return;
    seen.add(key);
    out.push({ name, value, good });
  };
  for (const b of blocks) {
    if (b.type !== 'stats_card' && b.type !== 'stats') continue;
    const data = (b as any).data ?? {};
    // explicit kpis[] (FE shape) first
    for (const k of (b.kpis ?? [])) {
      push(k.name, k.name, k.value, k.trend_is_good ?? (k.trend_pct == null ? undefined : k.trend_pct >= 0));
    }
    for (const [key, v] of Object.entries(data)) {
      if (['id', 'type', 'title'].includes(key)) continue;
      if (v === null || typeof v === 'object') continue;
      if (key === 'null_rate') {
        // Reframe the technical "Tỷ lệ trống 0.012" as positive completeness.
        const pct = Math.max(0, Math.min(1, 1 - Number(v)));
        push('data_complete', 'Dữ liệu đầy đủ', `${(pct * 100).toFixed(1)}%`, pct >= 0.95);
        continue;
      }
      const name = STAT_LABEL[key] ?? key;
      const value = typeof v === 'number' ? v.toLocaleString('vi-VN') : String(v);
      push(key, name, value);
    }
  }
  return out.slice(0, 6);
}

function KpiBar({ blocks }: { blocks: ChartBlock[] }) {
  const kpis = useMemo(() => buildKpis(blocks), [blocks]);
  if (!kpis.length) return null;
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {kpis.map((k, i) => (
        <div key={i} className="rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-3.5 shadow-soft-sm">
          <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] truncate" title={k.name}>{k.name}</p>
          <p className={cn(
            'font-serif text-xl mt-1',
            k.good === true ? 'text-[#5C856A]' : k.good === false ? 'text-[#9B5050]' : 'text-[var(--text-primary)]',
          )}>{k.value}</p>
        </div>
      ))}
    </div>
  );
}

// ----------------------------------------------------------------------------
// 3. Per-template section (accordion)
// ----------------------------------------------------------------------------

function TemplateSection({ template: t, pipelineId }: { template: TemplateResult; pipelineId: string }) {
  const failed = t.status === 'error' || t.status === 'failed';
  const [open, setOpen] = useState<boolean>(!failed);   // failed sections start collapsed but flagged

  // Non-narrative, non-empty content blocks decide if there's anything to show.
  const contentBlocks = t.blocks.filter((b) => b.type !== 'narrative');
  const narrative = t.blocks.find((b) => b.type === 'narrative');

  return (
    <div className="rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
      <button
        onClick={() => setOpen((p) => !p)}
        className="w-full flex items-center gap-3 px-5 py-4 text-left hover:bg-[var(--bg-app)]/30 transition-colors"
      >
        {open ? <ChevronDown className="w-4 h-4 text-[var(--text-secondary)] shrink-0" />
              : <ChevronRight className="w-4 h-4 text-[var(--text-secondary)] shrink-0" />}
        <span className="font-serif text-base text-[var(--text-primary)] flex-1 min-w-0 truncate">
          {t.display_name}
        </span>
        {failed ? (
          <Badge variant="warning"><AlertCircle className="w-3 h-3 mr-1 inline" /> Chưa đủ điều kiện</Badge>
        ) : (
          <Badge variant="success"><CheckCircle2 className="w-3 h-3 mr-1 inline" /> Hoàn tất</Badge>
        )}
      </button>

      {open && (
        <div className="px-5 pb-5 pt-1 border-t border-[var(--border-color)]/60 space-y-4">
          {failed ? (
            <div className="rounded-md-custom bg-[var(--state-warning)]/8 border border-[var(--state-warning)]/25 p-4">
              <p className="text-sm text-[var(--text-primary)]">
                Phân tích "{t.display_name}" chưa chạy được vì dữ liệu chưa đủ điều kiện.
              </p>
              {t.error_message && (
                <p className="text-xs text-[var(--text-secondary)] mt-1.5">Chi tiết: {t.error_message}</p>
              )}
              {t.description && (
                <p className="text-xs text-[var(--text-secondary)] mt-1.5">Yêu cầu: {t.description}</p>
              )}
              <a
                href={`/p2/pipelines/${pipelineId}/step-2-columns`}
                className="inline-flex items-center gap-1.5 text-sm text-[var(--primary-gold-dark)] font-medium mt-3 hover:underline"
              >
                <ArrowLeftCircle className="w-4 h-4" /> Quay lại Bước 2 để xác nhận cột
              </a>
            </div>
          ) : (
            <>
              {narrative && <NarrativeBlock block={narrative} />}
              {contentBlocks.length > 0 ? (
                contentBlocks.map((b, idx) => <BlockRenderer key={idx} block={b} />)
              ) : (
                <p className="text-sm text-[var(--text-secondary)] py-2">Phân tích hoàn tất, không có biểu đồ để hiển thị.</p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ----------------------------------------------------------------------------
// 5. Next-steps bar
// ----------------------------------------------------------------------------

function NextStepsBar({
  onExportCsv, exporting, onCopySummary,
}: {
  onExportCsv: () => void; exporting: boolean; onCopySummary: (() => void) | null;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 p-4 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] shadow-soft-sm print:hidden">
      <span className="text-sm text-[var(--text-secondary)] mr-1">Bước tiếp theo:</span>
      <Button variant="secondary" onClick={onExportCsv} isLoading={exporting}>
        <Download className="w-4 h-4 mr-2" /> Xuất CSV
      </Button>
      <Button variant="secondary" onClick={() => window.print()}>
        <Printer className="w-4 h-4 mr-2" /> Xuất PDF / In
      </Button>
      <Button variant="secondary" onClick={() => navigator.clipboard.writeText(window.location.href)}>
        <Share2 className="w-4 h-4 mr-2" /> Chia sẻ link
      </Button>
      {onCopySummary && (
        <Button variant="secondary" onClick={onCopySummary}>
          <Copy className="w-4 h-4 mr-2" /> Sao chép tóm tắt
        </Button>
      )}
    </div>
  );
}

// ----------------------------------------------------------------------------
// Block renderers
// ----------------------------------------------------------------------------

function BlockRenderer({ block: b }: { block: ChartBlock }) {
  if (b.type === 'stats' || b.type === 'stats_card') return <StatsBlock block={b} />;
  if (b.type === 'chart')          return <ChartBlockCard      block={b} />;
  if (b.type === 'narrative')      return <NarrativeBlock      block={b} />;
  if (b.type === 'table')          return <TableBlock          block={b} />;
  if (b.type === 'recommendation') return <RecommendationBlock block={b} />;
  return null;
}

function StatsBlock({ block: b }: { block: ChartBlock }) {
  // Two shapes feed this: FE kpis[] (name/value/trend) or the BE 'stats_card'
  // data object. Normalise both; skip nested object/array metadata.
  const kpis: any[] = (b.kpis && b.kpis.length)
    ? b.kpis
    : Object.entries(((b as any).data ?? {}) as Record<string, unknown>)
        .filter(([k, v]) =>
          !['id', 'type', 'title'].includes(k) &&
          (v === null || v === undefined ||
           typeof v === 'number' || typeof v === 'string' || typeof v === 'boolean'))
        .map(([k, v]) => ({
          name: STAT_LABEL[k] ?? k,
          value: v === null || v === undefined ? '—'
               : typeof v === 'number' ? v.toLocaleString('vi-VN') : String(v),
        }));
  return (
    <div className="bg-[var(--bg-app)]/30 rounded-lg-custom border border-[var(--border-color)]/60 p-4">
      {b.title && <h3 className="font-serif text-sm text-[var(--text-primary)] mb-3">{b.title}</h3>}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {(kpis ?? []).map((k, i) => (
          <div key={i} className="rounded-md-custom bg-[var(--bg-card)] border border-[var(--border-color)]/40 p-3">
            <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">{k.name}</p>
            <p className="font-serif text-lg text-[var(--text-primary)] mt-1">{k.value}</p>
            {k.trend_pct != null && (
              <p className={cn(
                'text-xs mt-1',
                (k.trend_is_good ?? k.trend_pct >= 0) ? 'text-[#5C856A]' : 'text-[#9B5050]',
              )}>
                {k.trend_pct >= 0 ? '+' : ''}{k.trend_pct.toFixed(1)}%
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// Factual, data-derived caption (NOT an invented business conclusion — K-3).
// Only for simple [{label,value}] charts: states group count + the top value.
function chartFactCaption(b: ChartBlock): string | null {
  const data = Array.isArray((b as any).data) ? (b as any).data : null;
  if (!data || data.length === 0) return null;
  const row0 = data[0];
  if (typeof row0 !== 'object' || row0 === null) return null;
  const labelKey = Object.keys(row0).find((k) => typeof row0[k] === 'string');
  const valueKey = Object.keys(row0).find((k) => k !== labelKey && typeof Number(row0[k]) === 'number' && Number.isFinite(Number(row0[k])));
  if (!labelKey || !valueKey) return null;
  let top = data[0];
  for (const r of data) if (Number(r[valueKey]) > Number(top[valueKey])) top = r;
  const topVal = Number(top[valueKey]);
  if (!Number.isFinite(topVal)) return null;
  return `${data.length} nhóm · cao nhất: ${String(top[labelKey])} (${topVal.toLocaleString('vi-VN')})`;
}

function ChartBlockCard({ block: b }: { block: ChartBlock }) {
  // Empty-chart collapse: a chart with no data points (e.g. IQR-outlier with no
  // outliers) collapses to a one-line positive badge instead of an empty frame.
  const rows = Array.isArray((b as any).data) ? (b as any).data : null;
  if (rows !== null && rows.length === 0) {
    const isOutlier = /ngoại lệ|outlier|iqr|bất thường/i.test(b.title ?? '');
    return (
      <div className="flex items-center gap-2.5 px-4 py-3 rounded-md-custom bg-[var(--state-success)]/8 border border-[var(--state-success)]/25 text-sm">
        <CheckCircle2 className="w-4 h-4 text-[var(--state-success)] shrink-0" />
        <span className="text-[var(--text-secondary)]">
          {b.title && <span className="font-medium text-[var(--text-primary)]">{b.title}: </span>}
          {isOutlier ? 'Không phát hiện giá trị bất thường trong dữ liệu.' : 'Không có dữ liệu để hiển thị.'}
        </span>
      </div>
    );
  }
  const caption = chartFactCaption(b);
  return (
    <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm">
      {b.title && <h3 className="font-serif text-base text-[var(--text-primary)] mb-1">{b.title}</h3>}
      {caption && <p className="text-xs text-[var(--text-secondary)] mb-3">{caption}</p>}
      <FlexibleChart block={b as any} />
    </div>
  );
}

function NarrativeBlock({ block: b }: { block: ChartBlock }) {
  // Degraded path: AI summary couldn't be generated (LLM timeout/offline). The
  // numbers are complete; render a calm muted notice, NOT a red placeholder.
  const degraded = b.degraded || (b.text ?? '').startsWith(NARRATIVE_PLACEHOLDER_PREFIX);
  if (degraded) {
    return (
      <div
        className="flex items-start gap-3 p-4 rounded-lg-custom bg-[var(--bg-app)]/40 border border-dashed border-[var(--border-color)]"
        title={b.reason ? `AI narrative skipped: ${b.reason}` : undefined}
      >
        <div className="w-8 h-8 rounded-full bg-[var(--bg-card)] border border-[var(--border-color)] flex items-center justify-center shrink-0">
          <Loader2 className="w-4 h-4 text-[var(--text-secondary)]" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-[var(--text-secondary)]">Nhận xét AI đang được tổng hợp</p>
          <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">
            Các số liệu và biểu đồ bên dưới đã đầy đủ. Phần nhận xét bằng lời sẽ xuất hiện khi trợ lý AI sẵn sàng — bạn có thể tải lại trang sau ít phút.
          </p>
        </div>
      </div>
    );
  }
  return (
    <div className="bg-[var(--primary-gold)]/4 rounded-lg-custom border border-[var(--primary-gold)]/20 p-4">
      <div className="flex items-start gap-3 mb-2">
        <div className="w-8 h-8 rounded-full bg-[var(--primary-gold)]/15 flex items-center justify-center shrink-0">
          <Lightbulb className="w-4 h-4 text-[var(--primary-gold-dark)]" />
        </div>
        <div className="flex-1">
          {b.title && <h3 className="font-serif text-base text-[var(--text-primary)]">{b.title}</h3>}
          {b.confidence != null && (
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              Độ tin cậy: <span className="font-medium text-[var(--text-primary)]">{(b.confidence * 100).toFixed(0)}%</span>
            </p>
          )}
        </div>
      </div>
      <p className="text-sm text-[var(--text-primary)] leading-relaxed whitespace-pre-line">{b.text}</p>
    </div>
  );
}

function TableBlock({ block: b }: { block: ChartBlock }) {
  return (
    <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
      {b.title && <h3 className="font-serif text-base text-[var(--text-primary)] px-5 py-4 border-b border-[var(--border-color)]/60">{b.title}</h3>}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[var(--bg-app)]/50">
            <tr>
              {(b.columns ?? []).map((c) => (
                <th key={c} className="px-4 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border-color)]/60">
            {(b.rows ?? []).map((row, i) => (
              <tr key={i}>
                {row.map((v: any, j: number) => (
                  <td key={j} className="px-4 py-2 font-mono text-xs text-[var(--text-primary)]">{String(v ?? '—')}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RecommendationBlock({ block: b }: { block: ChartBlock }) {
  return (
    <div className="bg-[var(--primary-gold)]/4 rounded-lg-custom border border-[var(--primary-gold)]/30 p-5 shadow-soft-sm">
      <div className="flex items-center gap-2 mb-4">
        <Sparkles className="w-5 h-5 text-[var(--primary-gold-dark)]" />
        <h3 className="font-serif text-base text-[var(--text-primary)]">{b.title ?? 'Khuyến nghị hành động'}</h3>
      </div>
      <div className="space-y-3">
        {(b.actions ?? []).map((a, i) => (
          <div key={i} className="rounded-md-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-3">
            <p className="text-sm font-medium text-[var(--text-primary)]">{a.title}</p>
            <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">{a.description}</p>
            {a.impact_vnd != null && (
              <p className="text-xs mt-2 text-[var(--primary-gold-dark)] font-medium">
                Tác động ước tính: {formatVND(a.impact_vnd)}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
