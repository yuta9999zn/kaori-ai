// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 45. /p2/frameworks/mom-yoy — MoM / YoY (F-034 🔵 Phase 2)
// ----------------------------------------------------------------------------
// So sánh tháng-trên-tháng + năm-trên-năm cho 1 metric. Cho phép chọn metric
// + range; AI tóm tắt biến động + giả thuyết driver.
// ============================================================================

import React, { useEffect, useState } from 'react';
import {
  ChevronLeft, TrendingUp, TrendingDown, Sparkles, ShieldCheck, Lock, Globe,
  Database, Calendar, BarChart2, Activity,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, Checkbox, cn,
  api, formatVND, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
type Granularity = 'mom' | 'yoy';

interface MetricChoice { id: string; label: string; unit: 'vnd' | 'count' | 'pct'; }

interface MoMYoYResult {
  metric_label:  string;
  current_period: { label: string; value: number };
  previous_period: { label: string; value: number };
  delta_pct:     number;
  narrative:     string;
  drivers:       string[];
  confidence:    number;
}

export default function MoMYoYPage() {
  const [granularity, setGranularity] = useState<Granularity>('mom');
  const [metrics, setMetrics] = useState<MetricChoice[]>([]);
  const [metricId, setMetricId] = useState('');
  const [consentExternal, setConsentExternal] = useState(false);
  const [result, setResult] = useState<MoMYoYResult | null>(null);
  const [running, setRunning] = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  useEffect(() => {
    api<{ items: MetricChoice[] }>('/api/v2/enterprise/frameworks/mom-yoy/metrics')
      .then((r) => { setMetrics(r.items); if (r.items[0]) setMetricId(r.items[0].id); })
      .catch((err) => setProblem(err));
  }, []);

  async function generate() {
    setRunning(true);
    setProblem(null);
    try {
      const r = await api<MoMYoYResult>('/api/v2/enterprise/frameworks/generate', {
        method: 'POST',
        body:   JSON.stringify({ framework: granularity === 'mom' ? 'MoM' : 'YoY', metric_id: metricId, consent_external: consentExternal }),
      });
      setResult(r);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setRunning(false);
    }
  }

  function formatValue(v: number) {
    const m = metrics.find((m) => m.id === metricId);
    if (m?.unit === 'vnd') return formatVND(v);
    if (m?.unit === 'pct') return `${v.toFixed(1)}%`;
    return v.toLocaleString('vi-VN');
  }

  const trendUp   = result ? result.delta_pct >= 0 : null;
  const trendIcon = trendUp ? TrendingUp : TrendingDown;

  return (
    <>
      <PageHeader
        title="MoM / YoY"
        description="So sánh tháng-trên-tháng + năm-trên-năm cho 1 metric với AI narrative."
        actions={
          <>
            <Badge variant="info">Phase 2 · F-034</Badge>
            <Button variant="tertiary" onClick={() => (window.location.href = '/p2/frameworks')}>
              <ChevronLeft className="w-4 h-4 mr-1" />
              Khung khác
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-5">
        <ErrorBanner problem={problem} />

        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-medium text-[var(--text-primary)]">Loại so sánh</label>
              <div className="mt-1 flex gap-1.5">
                {(['mom', 'yoy'] as Granularity[]).map((g) => (
                  <button
                    key={g}
                    type="button"
                    onClick={() => setGranularity(g)}
                    className={cn(
                      'flex-1 px-3 py-2 text-sm rounded-md-custom border',
                      granularity === g
                        ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/10 text-[var(--primary-gold-dark)] font-medium'
                        : 'border-[var(--border-color)] bg-[var(--bg-card)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
                    )}
                  >
                    {g === 'mom' ? 'Month-over-Month' : 'Year-over-Year'}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-sm font-medium text-[var(--text-primary)]">Metric</label>
              <div className="relative mt-1">
                <Database className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
                <select value={metricId} onChange={(e) => setMetricId(e.target.value)} className="w-full pl-9 pr-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30">
                  {metrics.length === 0 && <option value="">— Chưa có metric —</option>}
                  {metrics.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
                </select>
              </div>
            </div>
          </div>

          <div className={cn('p-3 rounded-md-custom border-2', consentExternal ? 'border-[var(--state-warning)]/50 bg-[var(--state-warning)]/5' : 'border-[var(--state-success)]/40 bg-[var(--state-success)]/5')}>
            <Checkbox
              checked={consentExternal}
              onChange={() => setConsentExternal(!consentExternal)}
              label={
                <span className="inline-flex items-center gap-2">
                  {consentExternal ? <Globe className="w-4 h-4 text-[var(--state-warning)]" /> : <Lock className="w-4 h-4 text-[var(--state-success)]" />}
                  {consentExternal ? 'AI bên ngoài (PII đã mask)' : 'Qwen nội bộ'}
                </span>
              }
            />
          </div>

          <Button onClick={generate} isLoading={running} disabled={!metricId || true} className="w-full" title="Phase 2 — Sắp ra mắt">
            <Sparkles className="w-4 h-4 mr-2" />
            Chạy {granularity.toUpperCase()}
          </Button>
        </div>

        {/* Result */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-[var(--border-color)]/60">
            <h3 className="font-serif text-base text-[var(--text-primary)]">Kết quả</h3>
          </div>
          <div className="p-5 space-y-4">
            {result ? (
              <>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)]/40 p-3">
                    <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">Kỳ này · {result.current_period.label}</p>
                    <p className="font-serif text-xl text-[var(--text-primary)] mt-1">{formatValue(result.current_period.value)}</p>
                  </div>
                  <div className="rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)]/40 p-3">
                    <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">Kỳ trước · {result.previous_period.label}</p>
                    <p className="font-serif text-xl text-[var(--text-primary)] mt-1">{formatValue(result.previous_period.value)}</p>
                  </div>
                  <div className={cn(
                    'rounded-md-custom p-3 border',
                    trendUp ? 'bg-[var(--state-success)]/8 border-[var(--state-success)]/30' : 'bg-[var(--state-error)]/8 border-[var(--state-error)]/30',
                  )}>
                    <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">Biến động</p>
                    <p className={cn(
                      'font-serif text-xl mt-1 inline-flex items-center gap-1',
                      trendUp ? 'text-[#5C856A]' : 'text-[#9B5050]',
                    )}>
                      {React.createElement(trendIcon, { className: 'w-4 h-4' })}
                      {result.delta_pct >= 0 ? '+' : ''}{result.delta_pct.toFixed(1)}%
                    </p>
                  </div>
                </div>

                <div>
                  <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] mb-1">Narrative</p>
                  <p className="text-sm text-[var(--text-primary)] leading-relaxed whitespace-pre-line">{result.narrative}</p>
                </div>

                <div>
                  <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] mb-1">Drivers nghi ngờ</p>
                  <ul className="space-y-1 text-sm text-[var(--text-primary)] list-disc list-inside">
                    {result.drivers.map((d, i) => <li key={i}>{d}</li>)}
                  </ul>
                </div>

                <Badge variant="default">Confidence {(result.confidence * 100).toFixed(0)}%</Badge>
              </>
            ) : (
              <div className="rounded-md-custom border border-dashed border-[var(--border-color)] p-8 text-center text-[var(--text-secondary)]">
                <BarChart2 className="w-10 h-10 mx-auto mb-2 text-[var(--primary-gold-dark)]" />
                <p className="text-sm">Chọn metric + chạy để xem so sánh.</p>
              </div>
            )}
          </div>
        </div>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <Calendar className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>MoM / YoY luôn chạy trên Gold feature đã aggregated (F-032). Stale &gt; 24h sẽ cảnh báo.</p>
        </div>
      </div>
    </>
  );
}
