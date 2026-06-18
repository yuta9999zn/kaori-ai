// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 17. /p2/data/gold — Gold layer (analytical features, F-032)
// ----------------------------------------------------------------------------
// GET /api/v1/data/gold/features (cursor)
// GET /api/v1/data/gold/features/:id (preview KPIs + last_aggregated_at)
//
// F-032 specifics (PR #80):
//   - Aggregator runs daily 02:00 ICT via cron (job: gold_aggregator)
//   - 90-day cutoff (rows older than 90d are NOT re-aggregated; idempotent upsert)
//   - 12-month ceiling on rolling features
//   - last_aggregated_at displayed prominently on each feature card
//   - "Chờ tổng hợp" badge when current_time - last_aggregated_at > 24h
// ============================================================================

import React, { useState, useEffect } from 'react';
import {
  Sparkles, Search, RefreshCw, Clock, TrendingUp, TrendingDown,
  CheckCircle2, AlertCircle, X, Calendar, ShieldCheck, Lightbulb,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner,
  api, cn, formatVND,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
interface GoldFeature {
  id:      string;
  name:    string;
  domain:  string;          // 'finance' | 'customer' | 'operation' | 'risk'
  description: string;
  rows:    number;
  kpis: Array<{
    name:    string;
    value:   string;          // pre-formatted by backend (incl. VND formatting)
    trend_pct?: number;       // positive = up, negative = down
    trend_is_good?: boolean;  // 'down' on churn_rate is good, 'up' on revenue is good
    timeframe?: string;
  }>;
  is_north_star: boolean;     // F-060 — true for revenue_at_risk_actioned
  last_aggregated_at: string;
  is_stale: boolean;          // backend computes: now - last_aggregated_at > 24h
  status: 'ready' | 'aggregating' | 'failed';
  error?: string;
}

interface AggregatorHealth {
  last_run_at: string;
  next_run_at: string;
  status: 'ok' | 'late' | 'failed';
  stale_feature_count: number;
}

export default function DataGold() {
  const [features, setFeatures] = useState<GoldFeature[]>([]);
  const [health,   setHealth]   = useState<AggregatorHealth | null>(null);
  const [loading,  setLoading]  = useState(true);
  const [problem,  setProblem]  = useState<ProblemDetails | null>(null);
  const [search,   setSearch]   = useState('');
  const [selected, setSelected] = useState<GoldFeature | null>(null);

  async function load() {
    setLoading(true);
    setProblem(null);
    try {
      const [f, h] = await Promise.all([
        api<{ data: GoldFeature[] }>('/api/v1/data/gold/features?limit=200'),
        api<AggregatorHealth>('/api/v1/data/gold/aggregator/health'),
      ]);
      setFeatures(f.data ?? []);
      setHealth(h);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  const filtered = features.filter((f) =>
    !search.trim() || f.name.toLowerCase().includes(search.toLowerCase())
    || f.domain.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <>
      <PageHeader
        title="Gold — chuẩn hoá phân tích"
        description="Bảng feature đã tổng hợp + chuẩn hoá. North Star Metric tính từ đây."
        actions={
          <Button variant="secondary" onClick={load} disabled={loading}>
            <RefreshCw className={'w-4 h-4 mr-2 ' + (loading ? 'animate-spin' : '')} />
            Làm mới
          </Button>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-6">
        {/* Aggregator health card — F-032 cron 02:00 ICT */}
        {health && (
          <div className="rounded-md-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-4 shadow-soft-sm flex items-start gap-4">
            <div className={cn(
              'w-10 h-10 rounded-full flex items-center justify-center shrink-0',
              health.status === 'ok'   ? 'bg-[var(--state-success)]/15 text-[var(--state-success)]'
              : health.status === 'late' ? 'bg-[var(--state-warning)]/15 text-[var(--state-warning)]'
              : 'bg-[var(--state-error)]/15 text-[var(--state-error)]',
            )}>
              {health.status === 'ok' ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <p className="text-sm font-medium text-[var(--text-primary)]">
                  {health.status === 'ok'   && 'Cron tổng hợp đang chạy đúng lịch'}
                  {health.status === 'late' && 'Cron tổng hợp chạy trễ'}
                  {health.status === 'failed' && 'Cron tổng hợp lỗi gần nhất'}
                </p>
                {health.stale_feature_count > 0 && (
                  <Badge variant="warning">
                    {health.stale_feature_count} feature lỗi thời
                  </Badge>
                )}
              </div>
              <p className="text-xs text-[var(--text-secondary)] mt-1">
                <Calendar className="inline w-3 h-3 mr-1" />
                Lần chạy gần nhất: {health.last_run_at} · Lần kế tiếp: {health.next_run_at}{' '}
                <span className="opacity-70">(02:00 ICT mỗi ngày)</span>
              </p>
            </div>
          </div>
        )}

        <ErrorBanner problem={problem} />

        <div className="relative">
          <Search className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm feature Gold theo tên hoặc lĩnh vực..."
            className="w-full bg-[var(--bg-card)] border border-[var(--border-color)] rounded-md-custom pl-9 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)]"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {loading ? (
            <>{[1,2,3,4,5,6].map((i) => <div key={i} className="h-56 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse" />)}</>
          ) : filtered.length === 0 ? (
            <div className="md:col-span-2 lg:col-span-3 p-12 text-center text-[var(--text-secondary)] bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)]">
              Chưa có feature Gold nào.
            </div>
          ) : (
            filtered.map((f) => <GoldCard key={f.id} feature={f} onOpen={() => setSelected(f)} />)
          )}
        </div>

        {/* F-032 reminders */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          <KRuleCard num="F-032" text="Aggregator chạy 02:00 ICT mỗi ngày — idempotent upsert. Dữ liệu cũ hơn 90 ngày không được tổng hợp lại." />
          <KRuleCard num="K-9"   text="Tiền dùng NUMERIC(14,4), tỷ lệ NUMERIC(5,4). Không bao giờ dùng FLOAT." />
          <KRuleCard num="F-060" text="North Star = Σ(revenue_at_risk WHERE churn_risk='HIGH' AND is_actioned=true)." />
        </div>
      </div>

      {selected && <GoldDrawer feature={selected} onClose={() => setSelected(null)} />}
    </>
  );
}

function GoldCard({ feature: f, onOpen }: any) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        'text-left rounded-lg-custom bg-[var(--bg-card)] border p-5 shadow-soft-sm hover:shadow-soft-md hover:-translate-y-0.5 transition-all',
        f.is_north_star ? 'border-[var(--primary-gold)] ring-1 ring-[var(--primary-gold)]/40' : 'border-[var(--border-color)]',
      )}
    >
      <div className="flex items-start justify-between mb-3 gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-serif text-base text-[var(--text-primary)] truncate">{f.name}</h3>
            {f.is_north_star && (
              <span title="North Star Metric">
                <Sparkles className="w-3.5 h-3.5 text-[var(--primary-gold-dark)] shrink-0" />
              </span>
            )}
          </div>
          <p className="text-[11px] text-[var(--text-secondary)] capitalize">{f.domain}</p>
        </div>
        <Badge variant={f.status === 'ready' ? 'success' : f.status === 'aggregating' ? 'warning' : 'error'}>
          {f.status === 'ready' ? 'Sẵn sàng' : f.status === 'aggregating' ? 'Đang tổng hợp' : 'Lỗi'}
        </Badge>
      </div>

      {/* Top KPI preview */}
      {f.kpis.length > 0 && (
        <div className="space-y-2 mb-3">
          {f.kpis.slice(0, 2).map((k: any, i: number) => (
            <div key={i} className="flex items-baseline justify-between">
              <span className="text-[11px] text-[var(--text-secondary)] truncate pr-2">{k.name}</span>
              <div className="flex items-baseline gap-1.5 shrink-0">
                <span className="text-sm font-semibold text-[var(--text-primary)]">{k.value}</span>
                {k.trend_pct != null && <TrendChip pct={k.trend_pct} isGood={k.trend_is_good} />}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="pt-3 border-t border-[var(--border-color)]/60 flex items-center justify-between text-[11px]">
        <span className="text-[var(--text-secondary)] flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {f.last_aggregated_at}
        </span>
        {f.is_stale && <span className="text-[#9E814D] font-medium">Chờ tổng hợp</span>}
      </div>
    </button>
  );
}

function GoldDrawer({ feature: f, onClose }: any) {
  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30" />
      <aside
        className="relative w-full max-w-[640px] bg-[var(--bg-card)] border-l border-[var(--border-color)] overflow-y-auto animate-slide-in-right"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 bg-[var(--bg-card)] border-b border-[var(--border-color)] p-5 flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h2 className="font-serif text-lg text-[var(--text-primary)]">{f.name}</h2>
              {f.is_north_star && <Badge variant="current">North Star</Badge>}
            </div>
            <p className="text-xs text-[var(--text-secondary)]">{f.description}</p>
          </div>
          <button onClick={onClose} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-5">
          <div className="rounded-md-custom bg-[var(--bg-app)]/60 border border-[var(--border-color)] p-4 flex items-start gap-3">
            <Clock className="w-4 h-4 text-[var(--primary-gold-dark)] mt-0.5 shrink-0" />
            <div className="flex-1 text-xs">
              <p className="font-medium text-[var(--text-primary)]">Tổng hợp gần nhất: {f.last_aggregated_at}</p>
              <p className="text-[var(--text-secondary)] mt-1">
                Aggregator chạy 02:00 ICT mỗi ngày. Dữ liệu cũ hơn 90 ngày không tổng hợp lại (F-032).
                Tổng số hàng: <span className="font-medium text-[var(--text-primary)]">{f.rows.toLocaleString('vi-VN')}</span>.
              </p>
            </div>
          </div>

          {f.error && (
            <div className="rounded-md-custom bg-[var(--state-error)]/10 border border-[var(--state-error)]/30 p-3 flex items-start gap-3">
              <AlertCircle className="w-4 h-4 text-[var(--state-error)] shrink-0 mt-0.5" />
              <p className="text-sm text-[#9B5050]">{f.error}</p>
            </div>
          )}

          <div>
            <h3 className="text-[11px] uppercase tracking-wider font-semibold text-[var(--text-secondary)] mb-3">
              KPI ({f.kpis.length})
            </h3>
            <div className="grid grid-cols-2 gap-3">
              {f.kpis.map((k: any, i: number) => (
                <div key={i} className="rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)]/60 p-3">
                  <p className="text-[11px] text-[var(--text-secondary)]">{k.name}</p>
                  <div className="flex items-baseline justify-between mt-1.5 gap-2">
                    <p className="font-serif text-base text-[var(--text-primary)]">{k.value}</p>
                    {k.trend_pct != null && <TrendChip pct={k.trend_pct} isGood={k.trend_is_good} />}
                  </div>
                  {k.timeframe && (
                    <p className="text-[10px] text-[var(--text-secondary)] mt-1">{k.timeframe}</p>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="pt-4 border-t border-[var(--border-color)]/60 flex gap-3">
            <Button
              variant="secondary"
              className="flex-1"
              onClick={() => (window.location.href = `/p2/insights?feature_id=${f.id}`)}
            >
              <Lightbulb className="w-4 h-4 mr-2" />
              Sinh insight
            </Button>
            <Button
              variant="secondary"
              className="flex-1"
              onClick={() => (window.location.href = `/p2/charts/picker?feature_id=${f.id}`)}
            >
              Tạo biểu đồ
            </Button>
          </div>
        </div>
      </aside>
    </div>
  );
}

function TrendChip({ pct, isGood }: { pct: number; isGood?: boolean }) {
  const up = pct >= 0;
  // Color logic: positive trend on a "good-up" KPI (revenue) → success.
  // Positive trend on a "good-down" KPI (churn) → error.
  const positive = isGood == null ? up : isGood === up;
  const cls = positive ? 'text-[#5C856A]' : '#9B5050';
  const Icon = up ? TrendingUp : TrendingDown;
  return (
    <span className="inline-flex items-center gap-0.5 text-[11px] font-medium" style={{ color: positive ? '#5C856A' : '#9B5050' }}>
      <Icon className="w-3 h-3" />
      {Math.abs(pct).toFixed(1)}%
    </span>
  );
}

function KRuleCard({ num, text }: { num: string; text: string }) {
  return (
    <div className="rounded-md-custom bg-[var(--bg-app)]/50 border border-[var(--border-color)] p-3">
      <span className="font-mono text-[10px] font-semibold text-[var(--primary-gold-dark)]">{num}</span>
      <p className="text-[var(--text-secondary)] mt-1 leading-relaxed">{text}</p>
    </div>
  );
}
