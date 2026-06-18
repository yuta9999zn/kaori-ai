// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 26. /p2/insights/:id — Insight Detail (F-025)
// ----------------------------------------------------------------------------
// GET    /api/v1/insights/:id
// POST   /api/v1/insights/:id/convert  → returns { decision_id }
// PATCH  /api/v1/insights/:id          → { status, bookmarked, dismissed_reason }
//
// 3-tuyến block per Sprint 7 product spec:
//   1. CHUYỆN GÌ (What)      — observed metric, supporting chart, time window
//   2. VÌ SAO (Why)          — root-cause hypothesis, evidence, confidence
//   3. NÊN LÀM GÌ (What-to-do) — recommendation list with impact_vnd + owner
//
// Convert-to-decision creates a row in `decisions` and a placeholder
// `decision_actions` row (Sprint 7 PR D / North Star).
// ============================================================================

import React, { useState, useEffect } from 'react';
import { usePathname } from 'next/navigation';
import {
  ChevronLeft, Lightbulb, Bookmark, Gavel, Clock, Database,
  AlertTriangle, CheckCircle2, X, ShieldCheck,
  Activity, BarChart2, Target, FileText,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, SuccessBanner, cn,
  api, formatVND,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
type Impact   = 'HIGH' | 'MEDIUM' | 'LOW';
type Status   = 'NEW' | 'REVIEWED' | 'CONVERTED' | 'DISMISSED';
type Source   = 'bronze' | 'silver' | 'gold';

interface RecommendedAction {
  title:        string;
  description:  string;
  owner_role?:  'MANAGER' | 'OPERATOR' | 'ANALYST';
  impact_vnd?:  number;
  framework?:   'SWOT' | '6W' | '2H' | 'Fishbone' | 'MoM' | 'YoY';
}

interface Insight {
  id:                   string;
  title:                string;
  description:          string;
  metric_name:          string;
  metric_value:         string;
  metric_window:        string;
  trend_pct?:           number;
  impact:               Impact;
  status:               Status;
  source:               Source;
  source_table:         string;
  revenue_at_risk_vnd:  number;
  churn_risk_label?:    'HIGH' | 'MEDIUM' | 'LOW';
  bookmarked:           boolean;

  // 3-tuyến content
  what_observed:        string;
  why_hypothesis:       string;
  why_evidence:         string[];
  why_confidence:       number;
  recommendations:      RecommendedAction[];

  // Linkage
  pipeline_id?:         string;
  pipeline_title?:      string;
  decision_id?:         string;
  is_actioned?:         boolean;
  audit_log_link?:      string;

  created_at:           string;
}

const IMPACT_BADGE: Record<Impact, { variant: any; label: string }> = {
  HIGH:   { variant: 'error',   label: 'Tác động cao' },
  MEDIUM: { variant: 'warning', label: 'Tác động vừa' },
  LOW:    { variant: 'default', label: 'Tác động thấp' },
};

const STATUS_BADGE: Record<Status, { variant: any; label: string }> = {
  NEW:       { variant: 'info',    label: 'Mới' },
  REVIEWED:  { variant: 'default', label: 'Đã xem' },
  CONVERTED: { variant: 'success', label: 'Đã ra quyết định' },
  DISMISSED: { variant: 'default', label: 'Đã bỏ qua' },
};

export default function InsightDetailPage() {
  // usePathname() works in SSR + client; reading `window.location.pathname`
  // at component body crashes Next prerender with "window is not defined".
  const pathname  = usePathname() ?? '';
  const insightId = pathname.split('/').filter(Boolean).pop() ?? '';

  const [ins,     setIns]     = useState<Insight | null>(null);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [converting,   setConverting]   = useState(false);
  const [showDismiss,  setShowDismiss]  = useState(false);
  const [dismissReason, setDismissReason] = useState('');

  async function load() {
    setLoading(true);
    setProblem(null);
    try {
      const data = await api<Insight>(`/api/v1/insights/${insightId}`);
      setIns(data);
      // Mark REVIEWED on first open if NEW (best-effort)
      if (data.status === 'NEW') {
        api(`/api/v1/insights/${insightId}`, {
          method: 'PATCH',
          body:   JSON.stringify({ status: 'REVIEWED' }),
        }).catch(() => { /* swallow */ });
      }
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { if (insightId) load(); }, [insightId]);

  async function convertToDecision() {
    if (!ins) return;
    setConverting(true);
    setProblem(null);
    try {
      const res = await api<{ decision_id: string }>(`/api/v1/insights/${insightId}/convert`, {
        method: 'POST',
        body:   JSON.stringify({}),
      });
      setSuccess('Đã tạo quyết định mới — chuyển trang...');
      setTimeout(() => { window.location.href = `/p2/decisions/${res.decision_id}`; }, 600);
    } catch (err: any) {
      setProblem(err);
      setConverting(false);
    }
  }

  async function dismiss() {
    if (!ins || !dismissReason.trim()) return;
    setConverting(true);
    try {
      await api(`/api/v1/insights/${insightId}`, {
        method: 'PATCH',
        body:   JSON.stringify({ status: 'DISMISSED', dismissed_reason: dismissReason.trim() }),
      });
      setShowDismiss(false);
      setSuccess('Đã bỏ qua insight');
      load();
    } catch (err: any) {
      setProblem(err);
    } finally {
      setConverting(false);
    }
  }

  async function toggleBookmark() {
    if (!ins) return;
    try {
      await api(`/api/v1/insights/${insightId}`, {
        method: 'PATCH',
        body:   JSON.stringify({ bookmarked: !ins.bookmarked }),
      });
      setIns({ ...ins, bookmarked: !ins.bookmarked });
    } catch (err: any) {
      setProblem(err);
    }
  }

  return (
    <>
      <PageHeader
        title={ins?.title ?? 'Insight'}
        description={ins ? `Khám phá ${ins.created_at} từ ${ins.source_table}` : 'Đang tải...'}
        actions={
          <Button variant="tertiary" onClick={() => (window.location.href = '/p2/insights')}>
            <ChevronLeft className="w-4 h-4 mr-1" />
            Quay lại
          </Button>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-6">
        <ErrorBanner problem={problem} />
        {success && <SuccessBanner message={success} />}

        {loading && !ins ? (
          <div className="space-y-4">
            {[1,2,3].map((i) => (
              <div key={i} className="h-48 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse" />
            ))}
          </div>
        ) : ins ? (
          <>
            {/* Header strip */}
            <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm">
              <div className="flex items-start gap-4 flex-wrap">
                <div className="w-12 h-12 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center shrink-0">
                  <Lightbulb className="w-5 h-5 text-[var(--primary-gold-dark)]" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2 mb-2">
                    <Badge variant={IMPACT_BADGE[ins.impact].variant}>{IMPACT_BADGE[ins.impact].label}</Badge>
                    <Badge variant={STATUS_BADGE[ins.status].variant}>{STATUS_BADGE[ins.status].label}</Badge>
                    {ins.churn_risk_label === 'HIGH' && (
                      <Badge variant="error">
                        <AlertTriangle className="w-3 h-3 mr-1 inline" />
                        Churn cao
                      </Badge>
                    )}
                    {ins.is_actioned && (
                      <Badge variant="success">
                        <CheckCircle2 className="w-3 h-3 mr-1 inline" />
                        Đã hành động
                      </Badge>
                    )}
                  </div>
                  <h2 className="font-serif text-xl text-[var(--text-primary)] leading-snug">{ins.title}</h2>
                  <p className="text-sm text-[var(--text-secondary)] mt-1 leading-relaxed">{ins.description}</p>
                </div>
                <button
                  onClick={toggleBookmark}
                  className={cn(
                    'p-2 rounded-md-custom border transition-colors shrink-0',
                    ins.bookmarked
                      ? 'border-[var(--primary-gold)]/40 bg-[var(--primary-gold)]/10 text-[var(--primary-gold-dark)]'
                      : 'border-[var(--border-color)] bg-[var(--bg-card)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
                  )}
                  aria-label={ins.bookmarked ? 'Bỏ đánh dấu' : 'Đánh dấu'}
                >
                  <Bookmark className={cn('w-4 h-4', ins.bookmarked && 'fill-current')} />
                </button>
              </div>

              {ins.revenue_at_risk_vnd > 0 && (
                <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <KpiTile label="Metric" value={`${ins.metric_value}`} secondary={ins.metric_name} />
                  <KpiTile
                    label="Cửa sổ thời gian"
                    value={ins.metric_window}
                    secondary={ins.trend_pct != null ? `${ins.trend_pct >= 0 ? '+' : ''}${ins.trend_pct.toFixed(1)}% so với kỳ trước` : undefined}
                  />
                  <KpiTile
                    label="Doanh thu rủi ro"
                    value={formatVND(ins.revenue_at_risk_vnd)}
                    secondary="Đóng góp vào North Star"
                    highlight
                  />
                </div>
              )}
            </div>

            {/* 3-tuyến — What */}
            <Tuyen
              num={1}
              icon={Activity}
              title="Chuyện gì đang xảy ra"
              subtitle="Quan sát từ dữ liệu — đã được audit (K-6)"
            >
              <p className="text-sm text-[var(--text-primary)] leading-relaxed whitespace-pre-line">
                {ins.what_observed}
              </p>
              <div className="mt-4 rounded-md-custom bg-[var(--bg-app)]/40 border border-dashed border-[var(--border-color)] h-48 flex flex-col items-center justify-center text-[var(--text-secondary)]">
                <BarChart2 className="w-10 h-10 text-[var(--primary-gold-dark)] mb-2" />
                <p className="text-sm font-medium text-[var(--text-primary)]">Biểu đồ supporting</p>
                <p className="text-xs mt-1">Render qua chart-registry (F-027)</p>
              </div>
            </Tuyen>

            {/* 3-tuyến — Why */}
            <Tuyen
              num={2}
              icon={Lightbulb}
              title="Vì sao xảy ra"
              subtitle={`Giả thuyết AI · Độ tin cậy ${(ins.why_confidence * 100).toFixed(0)}%`}
            >
              <p className="text-sm text-[var(--text-primary)] leading-relaxed whitespace-pre-line mb-4">
                {ins.why_hypothesis}
              </p>
              <div className="space-y-2">
                <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">Bằng chứng hỗ trợ</p>
                <ul className="space-y-1.5">
                  {ins.why_evidence.map((ev, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-[var(--text-primary)]">
                      <CheckCircle2 className="w-4 h-4 text-[var(--state-success)] shrink-0 mt-0.5" />
                      <span>{ev}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="mt-3 flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
                <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
                <p>
                  Giả thuyết do Qwen 2.5 nội bộ tạo (K-3), không gửi dữ liệu ra ngoài.
                  Cần xác nhận của con người trước khi hành động — đây <span className="font-medium text-[var(--text-primary)]">không phải</span> chẩn đoán cuối cùng.
                </p>
              </div>
            </Tuyen>

            {/* 3-tuyến — What-to-do */}
            <Tuyen
              num={3}
              icon={Target}
              title="Nên làm gì"
              subtitle={`${ins.recommendations.length} khuyến nghị có thể chuyển thành quyết định`}
            >
              <div className="space-y-3">
                {ins.recommendations.map((r, i) => (
                  <div key={i} className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-app)]/30 p-4">
                    <div className="flex items-start justify-between gap-3 flex-wrap">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-[var(--text-primary)]">{r.title}</p>
                        <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">{r.description}</p>
                      </div>
                      {r.impact_vnd != null && r.impact_vnd > 0 && (
                        <Badge variant="success">
                          {formatVND(r.impact_vnd)}
                        </Badge>
                      )}
                    </div>
                    <div className="mt-2 flex items-center gap-3 text-[11px] text-[var(--text-secondary)]">
                      {r.owner_role && (
                        <span>Người phụ trách: <span className="font-medium text-[var(--text-primary)]">{r.owner_role}</span></span>
                      )}
                      {r.framework && (
                        <span>Khung: <span className="font-medium text-[var(--text-primary)]">{r.framework}</span></span>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-4 flex flex-col sm:flex-row gap-2">
                {ins.status !== 'CONVERTED' && ins.status !== 'DISMISSED' && (
                  <>
                    <Button
                      onClick={convertToDecision}
                      isLoading={converting}
                      className="flex-1"
                    >
                      <Gavel className="w-4 h-4 mr-2" />
                      Chuyển thành quyết định
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() => setShowDismiss(true)}
                      className="sm:w-auto"
                    >
                      <X className="w-4 h-4 mr-2" />
                      Bỏ qua
                    </Button>
                  </>
                )}
                {ins.status === 'CONVERTED' && ins.decision_id && (
                  <Button onClick={() => (window.location.href = `/p2/decisions/${ins.decision_id}`)} className="flex-1">
                    <Gavel className="w-4 h-4 mr-2" />
                    Xem quyết định liên kết
                  </Button>
                )}
              </div>
            </Tuyen>

            {/* Linkage / audit */}
            <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-4 shadow-soft-sm">
              <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] mb-2">Liên kết & nguồn gốc</p>
              <ul className="space-y-1.5 text-sm">
                <li className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-[var(--text-secondary)]" />
                  Nguồn dữ liệu: <span className="font-mono text-xs text-[var(--text-primary)]">{ins.source_table}</span>
                  <Badge variant="default" className="ml-1">{ins.source.toUpperCase()}</Badge>
                </li>
                {ins.pipeline_id && (
                  <li className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-[var(--text-secondary)]" />
                    Pipeline: <a href={`/p2/pipelines/${ins.pipeline_id}`} className="text-[var(--primary-gold-dark)] hover:underline">{ins.pipeline_title ?? ins.pipeline_id}</a>
                  </li>
                )}
                {ins.audit_log_link && (
                  <li className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-[var(--text-secondary)]" />
                    <a href={ins.audit_log_link} className="text-[var(--primary-gold-dark)] hover:underline">Xem audit log (K-6)</a>
                  </li>
                )}
                <li className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                  <Clock className="w-3.5 h-3.5" />
                  {ins.created_at}
                </li>
              </ul>
            </div>
          </>
        ) : null}

        {/* Dismiss modal */}
        {showDismiss && (
          <div className="fixed inset-0 z-50 bg-[var(--text-primary)]/40 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-lg w-full max-w-md p-5 animate-slide-up-fade">
              <h3 className="font-serif text-lg text-[var(--text-primary)]">Bỏ qua insight này?</h3>
              <p className="text-sm text-[var(--text-secondary)] mt-1">
                Vui lòng nhập lý do để team có context cho lần phân tích sau.
              </p>
              <textarea
                value={dismissReason}
                onChange={(e) => setDismissReason(e.target.value)}
                rows={3}
                placeholder="Ví dụ: Đã xử lý ngoài hệ thống, dữ liệu sai, không liên quan kinh doanh..."
                className="mt-3 w-full px-3 py-2 text-sm bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)]"
              />
              <div className="mt-4 flex items-center gap-2 justify-end">
                <Button variant="tertiary" onClick={() => setShowDismiss(false)}>Huỷ</Button>
                <Button
                  variant="destructive"
                  onClick={dismiss}
                  isLoading={converting}
                  disabled={!dismissReason.trim()}
                >
                  Xác nhận bỏ qua
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

// ----------------------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------------------

function KpiTile({
  label, value, secondary, highlight,
}: { label: string; value: string; secondary?: string; highlight?: boolean }) {
  return (
    <div className={cn(
      'rounded-md-custom p-3 border',
      highlight
        ? 'bg-[var(--primary-gold)]/8 border-[var(--primary-gold)]/30'
        : 'bg-[var(--bg-app)]/40 border-[var(--border-color)]/40',
    )}>
      <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">{label}</p>
      <p className="font-serif text-lg text-[var(--text-primary)] mt-1">{value}</p>
      {secondary && <p className="text-xs text-[var(--text-secondary)] mt-0.5">{secondary}</p>}
    </div>
  );
}

function Tuyen({
  num, icon: Icon, title, subtitle, children,
}: {
  num: number;
  icon: any;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
      <div className="px-5 py-3 border-b border-[var(--border-color)]/60 flex items-center gap-3 bg-[var(--bg-app)]/40">
        <div className="w-8 h-8 rounded-full bg-[var(--primary-gold)]/15 flex items-center justify-center shrink-0">
          <span className="font-serif text-xs text-[var(--primary-gold-dark)]">{num}</span>
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-serif text-base text-[var(--text-primary)] inline-flex items-center gap-2">
            <Icon className="w-4 h-4 text-[var(--primary-gold-dark)]" />
            {title}
          </h3>
          {subtitle && <p className="text-xs text-[var(--text-secondary)] mt-0.5">{subtitle}</p>}
        </div>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}
