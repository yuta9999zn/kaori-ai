// @ts-nocheck — template; tighten when wiring real chart-registry blocks.
'use client';

// ============================================================================
// /p2/analysis — Tổng quan phân tích (index của nhóm Phân tích)
// ----------------------------------------------------------------------------
// Trang "mọi phân tích từ trước đến giờ" — người dùng xem lại theo 3 nhóm:
//   1. Phân tích pipeline (template thống kê chạy ở Bước 4 wizard)
//        GET /api/v1/analytics/runs        → link step-5 của pipeline run
//   2. Phân tích theo tầng (Cơ bản / Trung cấp / Nâng cao / Phạm vi)
//        GET /api/v1/analysis/runs         → link /p2/analysis/runs/{id}
//   3. Khung phân tích (SWOT / 6W / 2H / Fishbone)
//        GET /api/v1/frameworks            → link /p2/frameworks
// Kèm hàng quick-card mở 4 tầng phân tích. Mỗi nhóm degrade độc lập —
// một API lỗi không che hai nhóm còn lại (tenet 13).
// TODO(i18n): chuyển literal → t() khi generate dictionary đợt kế.
// ============================================================================

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  FlaskConical, Layers, Grid2x2, ChevronRight, Clock, RefreshCw,
  BarChart3, Target, Telescope, Compass,
} from 'lucide-react';

import { Button, Badge, ErrorBanner, cn, api, type ProblemDetails } from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';

const STATUS_VARIANT: Record<string, any> = {
  done: 'success', ready: 'success', completed: 'success',
  running: 'warning', queued: 'default', analyzing: 'warning',
  error: 'error', failed: 'error',
};

const TIER_LABEL: Record<string, string> = {
  basic: 'Cơ bản', intermediate: 'Trung cấp', advanced: 'Nâng cao',
};

const QUICK_TIERS = [
  { href: '/p2/analysis/basic',        icon: BarChart3, title: 'Cơ bản',
    desc: '1 nguồn dữ liệu — thống kê, xu hướng, churn' },
  { href: '/p2/analysis/intermediate', icon: Target,    title: 'Trung cấp',
    desc: '2-5 nguồn Silver/Gold + 1 khung phân tích' },
  { href: '/p2/analysis/advanced',     icon: Telescope, title: 'Nâng cao',
    desc: 'Đa nguồn + so sánh chéo, cần MANAGER duyệt' },
  { href: '/p2/analysis/scope',        icon: Compass,   title: 'Phạm vi',
    desc: 'Cấu hình phạm vi dữ liệu được phân tích' },
];

function fmtTime(iso?: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('vi-VN', {
      day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
}

function HistoryCard({ title, icon: Icon, error, empty, children, viewAllHref }: any) {
  return (
    <div className="rounded-xl border border-[var(--border-default)] bg-[var(--surface-primary)]">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--border-default)]">
        <Icon className="w-4 h-4 text-[var(--text-secondary)]" />
        <h3 className="text-sm font-medium text-[var(--text-primary)] flex-1">{title}</h3>
        {viewAllHref && (
          <Link href={viewAllHref} className="text-xs text-[var(--text-secondary)] hover:underline">
            Mở trang <ChevronRight className="w-3 h-3 inline" />
          </Link>
        )}
      </div>
      {error
        ? <div className="px-4 py-4 text-sm text-[var(--text-secondary)]">Không tải được — thử lại sau.</div>
        : empty
          ? <div className="px-4 py-4 text-sm text-[var(--text-secondary)]">Chưa có phân tích nào.</div>
          : <ul className="divide-y divide-[var(--border-default)]">{children}</ul>}
    </div>
  );
}

function Row({ href, primary, secondary, status, time }: any) {
  const body = (
    <div className="flex items-center gap-3 px-4 py-2.5 hover:bg-[var(--surface-secondary)] transition-colors">
      <div className="flex-1 min-w-0">
        <div className="text-sm text-[var(--text-primary)] truncate">{primary}</div>
        {secondary && <div className="text-xs text-[var(--text-secondary)] truncate">{secondary}</div>}
      </div>
      <Badge variant={STATUS_VARIANT[status] ?? 'default'}>{status}</Badge>
      <span className="text-xs text-[var(--text-secondary)] whitespace-nowrap flex items-center gap-1">
        <Clock className="w-3 h-3" /> {fmtTime(time)}
      </span>
      {href && <ChevronRight className="w-4 h-4 text-[var(--text-secondary)]" />}
    </div>
  );
  return <li>{href ? <Link href={href}>{body}</Link> : body}</li>;
}

export default function AnalysisOverviewPage() {
  const [pipelineRuns, setPipelineRuns] = useState<any[] | null>(null);
  const [tierRuns, setTierRuns]         = useState<any[] | null>(null);
  const [fwRuns, setFwRuns]             = useState<any[] | null>(null);
  const [errs, setErrs] = useState<{ p?: boolean; t?: boolean; f?: boolean }>({});
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const next: typeof errs = {};
    // Ba nhóm độc lập — Promise.allSettled để một nhóm lỗi không che nhóm khác.
    const [p, t, f] = await Promise.allSettled([
      api<any[]>('/api/v1/analytics/runs?limit=10'),
      api<any>('/api/v1/analysis/runs?limit=10'),
      api<any>('/api/v1/frameworks?limit=10'),
    ]);
    if (p.status === 'fulfilled') setPipelineRuns(p.value ?? []); else next.p = true;
    if (t.status === 'fulfilled') setTierRuns(t.value?.items ?? []); else next.t = true;
    if (f.status === 'fulfilled') setFwRuns(f.value?.items ?? []); else next.f = true;
    setErrs(next);
    setLoading(false);
  }
  useEffect(() => { load(); }, []);

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <PageHeader
        title="Phân tích — Tổng quan"
        subtitle="Mọi phân tích đã chạy, xem lại theo nhóm; chọn tầng để chạy phân tích mới."
        actions={
          <Button variant="secondary" size="sm" onClick={load} disabled={loading}>
            <RefreshCw className={cn('w-4 h-4 mr-1', loading && 'animate-spin')} /> Làm mới
          </Button>
        }
      />

      {/* Quick cards — 4 tầng */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {QUICK_TIERS.map(({ href, icon: Icon, title, desc }) => (
          <Link key={href} href={href}
            className="rounded-xl border border-[var(--border-default)] bg-[var(--surface-primary)] p-4 hover:border-[var(--border-strong)] transition-colors">
            <Icon className="w-5 h-5 mb-2 text-[var(--text-secondary)]" />
            <div className="text-sm font-medium text-[var(--text-primary)]">{title}</div>
            <div className="text-xs text-[var(--text-secondary)] mt-0.5">{desc}</div>
          </Link>
        ))}
      </div>

      {/* Lịch sử theo nhóm */}
      <HistoryCard title="Phân tích pipeline (template thống kê)" icon={FlaskConical}
                   error={errs.p} empty={(pipelineRuns ?? []).length === 0}
                   viewAllHref="/p2/pipelines">
        {(pipelineRuns ?? []).map((r) => (
          <Row key={r.id}
               href={r.run_id ? `/p2/pipelines/${r.run_id}/step-5-results?run_id=${r.id}` : undefined}
               primary={(Array.isArray(r.templates) ? r.templates : []).join(' · ') || 'Phân tích template'}
               secondary={`Pipeline ${String(r.run_id ?? '').slice(0, 8)}`}
               status={r.status} time={r.created_at} />
        ))}
      </HistoryCard>

      <HistoryCard title="Phân tích theo tầng (Cơ bản / Trung cấp / Nâng cao)" icon={Layers}
                   error={errs.t} empty={(tierRuns ?? []).length === 0}
                   viewAllHref="/p2/analysis/hub">
        {(tierRuns ?? []).map((r) => (
          <Row key={r.id} href={`/p2/analysis/runs/${r.id}`}
               primary={r.question || r.framework || TIER_LABEL[r.tier] || r.tier}
               secondary={[TIER_LABEL[r.tier] ?? r.tier, r.framework].filter(Boolean).join(' · ')}
               status={r.status} time={r.started_at ?? r.completed_at} />
        ))}
      </HistoryCard>

      <HistoryCard title="Khung phân tích (SWOT / 6W / 2H / Fishbone)" icon={Grid2x2}
                   error={errs.f} empty={(fwRuns ?? []).length === 0}
                   viewAllHref="/p2/frameworks">
        {(fwRuns ?? []).map((r) => (
          <Row key={r.run_id}
               primary={r.question}
               secondary={r.framework_code?.toUpperCase()}
               status={r.status} time={r.created_at} />
        ))}
      </HistoryCard>
    </div>
  );
}
