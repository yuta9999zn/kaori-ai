// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 9. /p2/dashboard — Enterprise Dashboard Overview (F-028)
// ----------------------------------------------------------------------------
// 5-state machine driven by GET /api/v1/dashboard/state:
//   empty       → no data uploaded yet → CTA: upload
//   uploading   → file in flight → progress
//   processing  → bronze → silver → gold pipeline running → SSE stream
//   completed   → KPIs + recent runs + alerts + insights
//   error       → RFC 7807 detail + retry
//
// Plus: K-11 quota banner (DISTINCT customer_external_id / month) with
// 80% warn + 95% critical thresholds.
// ============================================================================

import React, { useState, useEffect } from 'react';
import {
  UploadCloud, Activity, Clock, CheckCircle2, XCircle, RefreshCw,
  Plus, MoreVertical, Sparkles, AlertTriangle, ShieldAlert, ArrowRight, Lightbulb,
} from 'lucide-react';

import {
  Button, Badge, QuotaBar, ErrorBanner,
  api, formatVND,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
type DashboardState = 'empty' | 'uploading' | 'processing' | 'completed' | 'error';

type RunStatus = 'schema_review' | 'analyzing' | 'analysis_complete';

interface DashboardSnapshot {
  state: DashboardState;
  kpis: {
    bronze_files:      number;
    pipeline_runs_30d: number;
    insights_30d:      number;
    open_alerts:       number;
    data_processed_gb: number;
    active_users:      number;
  };
  quota: {
    current: number;
    limit:   number;
    plan:    'PILOT' | 'BASIC' | 'MID' | 'MAX' | 'ROI';
    plan_amount_vnd: number;
  };
  recent_runs: Array<{
    id: string;
    name: string;
    template_id: string;
    status: RunStatus;
    progress_pct: number;
    updated_at: string;
  }>;
  alerts: Array<{
    id:       string;
    severity: 'error' | 'warning' | 'info';
    message:  string;
    when:     string;
  }>;
  insights: Array<{
    id:    string;
    title: string;
    type:  'churn' | 'anomaly' | 'opportunity';
    revenue_at_risk_vnd?: number;
    is_actioned?: boolean;
  }>;
}

const STATUS_BADGE: Record<RunStatus, any> = {
  schema_review:    { variant: 'info',    label: 'Đang duyệt cột' },
  analyzing:        { variant: 'warning', label: 'Đang phân tích' },
  analysis_complete:{ variant: 'success', label: 'Hoàn tất' },
};

export default function DashboardOverview() {
  const [snap,    setSnap]    = useState<DashboardSnapshot | null>(null);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setProblem(null);
    try {
      const data = await api<DashboardSnapshot>('/api/v1/dashboard/state');
      setSnap(data);
    } catch (err: any) {
      setProblem(err);
      setSnap({ state: 'error' } as any);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <>
      <PageHeader
        title="Bảng điều khiển"
        description="Tổng quan workspace — pipeline, insight, hạn mức gói cước."
        actions={
          <>
            <Button variant="secondary" onClick={load} disabled={loading}>
              <RefreshCw className={'w-4 h-4 mr-2 ' + (loading ? 'animate-spin' : '')} />
              Làm mới
            </Button>
            <Button onClick={() => (window.location.href = '/p2/pipelines/new')}>
              <Plus className="w-4 h-4 mr-2" />
              Pipeline mới
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-6">
        {loading && !snap && <SkeletonGrid />}

        {snap?.state === 'error' && (
          <ErrorPanel problem={problem} onRetry={load} />
        )}

        {snap && snap.state !== 'error' && (
          <>
            {/* Quota banner — always visible */}
            {snap.quota && (
              <div className="rounded-md-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-5 shadow-soft-sm">
                <div className="flex items-start justify-between mb-4 gap-4">
                  <div>
                    <h3 className="font-serif text-base text-[var(--text-primary)]">
                      Hạn mức tháng này
                    </h3>
                    <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                      Đếm theo <span className="font-medium">khách hàng đã xử lý duy nhất</span> (DISTINCT customer_external_id).
                      Gói {snap.quota.plan} — {formatVND(snap.quota.plan_amount_vnd)}/tháng.
                    </p>
                  </div>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => (window.location.href = '/p2/subscription/upgrade')}
                  >
                    Nâng cấp gói
                  </Button>
                </div>
                <QuotaBar
                  current={snap.quota.current}
                  limit={snap.quota.limit}
                  unit="khách hàng đã xử lý"
                />
              </div>
            )}

            {/* BE returns 'no_data' for a brand-new workspace; treat it as
                'empty' so the user sees the upload CTA instead of a blank page. */}
            {(snap.state === 'empty' || (snap.state as string) === 'no_data') && <EmptyState />}
            {snap.state === 'uploading'  && <UploadingState />}
            {snap.state === 'processing' && <ProcessingState recent={snap.recent_runs ?? []} />}
            {snap.state === 'completed'  && <CompletedState snap={snap} />}
          </>
        )}
      </div>
    </>
  );
}

// ============================================================================
// State subviews
// ============================================================================

function EmptyState() {
  return (
    <div className="rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-12 text-center shadow-soft-sm">
      <div className="mx-auto w-20 h-20 rounded-full bg-[var(--primary-gold)]/15 flex items-center justify-center mb-6">
        <UploadCloud className="w-10 h-10 text-[var(--primary-gold-dark)]" />
      </div>
      <h2 className="font-serif text-2xl text-[var(--text-primary)] mb-3">Chưa có dữ liệu nào</h2>
      <p className="text-sm text-[var(--text-secondary)] max-w-md mx-auto mb-8">
        Tải lên file CSV/Excel đầu tiên — Kaori sẽ tự nhận cột, làm sạch dữ liệu, sinh insight trong vài phút.
      </p>
      <Button onClick={() => (window.location.href = '/p2/pipelines/new')} size="lg">
        <UploadCloud className="w-4 h-4 mr-2" />
        Tải dữ liệu lên
      </Button>
      <p className="text-xs text-[var(--text-secondary)] mt-6">
        Hoặc xem{' '}
        <a href="/docs/getting-started" className="text-[var(--primary-gold-dark)] underline">
          hướng dẫn 5 phút
        </a>
      </p>
    </div>
  );
}

function UploadingState() {
  return (
    <div className="rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-10 text-center shadow-soft-sm">
      <div className="mx-auto w-16 h-16 rounded-full bg-[var(--state-info)]/15 flex items-center justify-center mb-5 animate-pulse">
        <UploadCloud className="w-8 h-8 text-[var(--state-info)]" />
      </div>
      <h2 className="font-serif text-xl text-[var(--text-primary)] mb-2">Đang tải file lên...</h2>
      <p className="text-sm text-[var(--text-secondary)]">Vui lòng giữ kết nối — quá trình tải có thể mất vài phút với file lớn.</p>
    </div>
  );
}

function ProcessingState({ recent }: { recent: any[] }) {
  return (
    <div className="rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-8 shadow-soft-sm">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-full bg-[var(--state-warning)]/15 flex items-center justify-center">
          <Activity className="w-5 h-5 text-[var(--state-warning)] animate-pulse" />
        </div>
        <div>
          <h2 className="font-serif text-lg text-[var(--text-primary)]">Đang xử lý dữ liệu</h2>
          <p className="text-xs text-[var(--text-secondary)]">Bronze → Silver → Gold đang chạy.</p>
        </div>
      </div>
      <div className="space-y-3">
        {recent.slice(0, 3).map((r) => (
          <RunRow key={r.id} run={r} />
        ))}
      </div>
    </div>
  );
}

function CompletedState({ snap }: { snap: DashboardSnapshot }) {
  const kpis = [
    { label: 'Pipeline 30 ngày',       value: snap.kpis.pipeline_runs_30d.toLocaleString('vi-VN') },
    { label: 'Bronze files',           value: snap.kpis.bronze_files.toLocaleString('vi-VN') },
    { label: 'Insight sinh ra',         value: snap.kpis.insights_30d.toLocaleString('vi-VN') },
    { label: 'Cảnh báo mở',            value: snap.kpis.open_alerts.toLocaleString('vi-VN') },
    { label: 'Dữ liệu đã xử lý (GB)', value: snap.kpis.data_processed_gb.toFixed(1) },
    { label: 'Người dùng hoạt động',  value: snap.kpis.active_users.toLocaleString('vi-VN') },
  ];

  return (
    <>
      {/* KPI grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {kpis.map((k) => (
          <div key={k.label} className="rounded-md-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-4 shadow-soft-sm">
            <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">{k.label}</p>
            <p className="font-serif text-2xl text-[var(--text-primary)] mt-1">{k.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent pipelines (2/3) */}
        <div className="lg:col-span-2 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-6 shadow-soft-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-serif text-base text-[var(--text-primary)]">Pipeline gần đây</h3>
            <a href="/p2/pipelines" className="text-xs text-[var(--primary-gold-dark)] hover:underline flex items-center gap-1">
              Xem tất cả <ArrowRight className="w-3.5 h-3.5" />
            </a>
          </div>
          <div className="space-y-2">
            {snap.recent_runs.length === 0 ? (
              <p className="text-sm text-[var(--text-secondary)] text-center py-6">Chưa có pipeline nào.</p>
            ) : snap.recent_runs.map((r) => <RunRow key={r.id} run={r} />)}
          </div>
        </div>

        {/* Alerts (1/3) */}
        <div className="rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-6 shadow-soft-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-serif text-base text-[var(--text-primary)]">Cảnh báo</h3>
            <a href="/p2/alerts" className="text-xs text-[var(--primary-gold-dark)] hover:underline flex items-center gap-1">
              Xem tất cả <ArrowRight className="w-3.5 h-3.5" />
            </a>
          </div>
          {snap.alerts.length === 0 ? (
            <p className="text-sm text-[var(--text-secondary)] text-center py-6">Không có cảnh báo nào.</p>
          ) : (
            <div className="space-y-3">
              {snap.alerts.map((a) => (
                <div key={a.id} className="flex items-start gap-3 p-3 rounded-md-custom bg-[var(--bg-app)]/60">
                  <AlertIcon severity={a.severity} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-[var(--text-primary)]">{a.message}</p>
                    <p className="text-xs text-[var(--text-secondary)] mt-0.5">{a.when}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* North Star insights — preview F-060 (Phase 2 full) */}
      {snap.insights.length > 0 && (
        <div className="rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-6 shadow-soft-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Lightbulb className="w-4 h-4 text-[var(--primary-gold-dark)]" />
              <h3 className="font-serif text-base text-[var(--text-primary)]">Insight ưu tiên</h3>
            </div>
            <a href="/p2/insights" className="text-xs text-[var(--primary-gold-dark)] hover:underline flex items-center gap-1">
              Xem tất cả <ArrowRight className="w-3.5 h-3.5" />
            </a>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {snap.insights.slice(0, 4).map((i) => (
              <a
                key={i.id}
                href={`/p2/insights/${i.id}`}
                className="block p-4 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] hover:border-[var(--primary-gold)]/40 transition-colors"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-[var(--text-primary)]">{i.title}</p>
                    {i.revenue_at_risk_vnd != null && (
                      <p className="text-xs text-[var(--text-secondary)] mt-1">
                        Doanh thu tiềm ẩn rủi ro:{' '}
                        <span className="font-medium text-[#9B5050]">{formatVND(i.revenue_at_risk_vnd)}</span>
                      </p>
                    )}
                  </div>
                  {i.is_actioned ? <Badge variant="success">Đã hành động</Badge> : <Badge variant="warning">Chưa</Badge>}
                </div>
              </a>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

function ErrorPanel({ problem, onRetry }: { problem: ProblemDetails | null; onRetry: () => void }) {
  return (
    <div className="rounded-lg-custom bg-[var(--bg-card)] border border-[var(--state-error)]/30 p-10 text-center shadow-soft-sm">
      <div className="mx-auto w-16 h-16 rounded-full bg-[var(--state-error)]/12 flex items-center justify-center mb-5">
        <ShieldAlert className="w-8 h-8 text-[var(--state-error)]" />
      </div>
      <h2 className="font-serif text-xl text-[var(--text-primary)] mb-2">Không tải được dashboard</h2>
      <div className="max-w-md mx-auto mb-6">
        <ErrorBanner problem={problem} />
      </div>
      <Button onClick={onRetry}>
        <RefreshCw className="w-4 h-4 mr-2" />
        Thử lại
      </Button>
    </div>
  );
}

// ============================================================================
// Helpers
// ============================================================================

function RunRow({ run }: { run: any }) {
  const cfg = STATUS_BADGE[run.status] ?? STATUS_BADGE.schema_review;
  return (
    <a
      href={`/p2/pipelines/${run.id}`}
      className="block p-3 rounded-md-custom hover:bg-[var(--bg-app)]/60 transition-colors border border-transparent hover:border-[var(--border-color)]"
    >
      <div className="flex items-center justify-between gap-4">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-[var(--text-primary)] truncate">{run.name}</p>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">{run.template_id} · cập nhật {run.updated_at}</p>
        </div>
        <Badge variant={cfg.variant}>{cfg.label}</Badge>
      </div>
      {run.status === 'analyzing' && (
        <div className="h-1 mt-2 rounded-full bg-[var(--border-color)]/40 overflow-hidden">
          <div className="h-full bg-[var(--primary-gold)] transition-all duration-500" style={{ width: `${run.progress_pct}%` }} />
        </div>
      )}
    </a>
  );
}

function AlertIcon({ severity }: { severity: 'error' | 'warning' | 'info' }) {
  if (severity === 'error')   return <XCircle       className="w-5 h-5 text-[var(--state-error)] shrink-0 mt-0.5" />;
  if (severity === 'warning') return <AlertTriangle className="w-5 h-5 text-[var(--state-warning)] shrink-0 mt-0.5" />;
  return                              <Activity      className="w-5 h-5 text-[var(--state-info)] shrink-0 mt-0.5" />;
}

function SkeletonGrid() {
  return (
    <div className="space-y-6">
      <div className="h-24 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse" />
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        {[1,2,3,4,5,6].map((i) => <div key={i} className="h-20 rounded-md-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse" />)}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 h-72 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse" />
        <div className="h-72 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse" />
      </div>
    </div>
  );
}
