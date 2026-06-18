// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 14. /p2/data — Data Explorer (Medallion overview)
// ----------------------------------------------------------------------------
// Hub showing Bronze / Silver / Gold layers side-by-side with counters,
// recent activity, and direct links into each layer page.
//
// Layers (CLAUDE.md §5):
//   Bronze (K-2 append-only)  → MinIO/S3 Parquet  → file count + total rows
//   Silver (K-5 PII-masked)    → ClickHouse        → cleaned + masked
//   Gold   (F-032 strict)       → PostgreSQL MV     → gold_features + last_aggregated_at
// ============================================================================

import React, { useState, useEffect } from 'react';
import {
  HardDrive, Layers, Sparkles, ArrowRight, RefreshCw, Plus, Activity,
  CheckCircle2, AlertCircle, Clock,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner,
  api, cn, formatVND,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
interface ExplorerSnapshot {
  bronze: { file_count: number; row_count_total: number; size_gb: number; last_ingested_at: string | null; failed_24h: number };
  silver: { dataset_count: number; row_count_total: number; quality_avg_pct: number; last_processed_at: string | null };
  gold:   { feature_count: number; row_count_total: number; last_aggregated_at: string | null; stale_count: number };
  recent: Array<{ id: string; layer: 'bronze' | 'silver' | 'gold'; name: string; action: string; at: string; status: 'ok' | 'fail' | 'running' }>;
}

export default function DataExplorer() {
  const [snap,    setSnap]    = useState<ExplorerSnapshot | null>(null);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setProblem(null);
    try {
      setSnap(await api<ExplorerSnapshot>('/api/v1/data/explorer'));
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  return (
    <>
      <PageHeader
        title="Khám phá dữ liệu"
        description="Tổng quan 3 lớp Medallion — Bronze (thô) → Silver (sạch) → Gold (chuẩn hoá phân tích)."
        actions={
          <>
            <Button variant="secondary" onClick={load} disabled={loading}>
              <RefreshCw className={'w-4 h-4 mr-2 ' + (loading ? 'animate-spin' : '')} />
              Làm mới
            </Button>
            <Button onClick={() => (window.location.href = '/p2/pipelines/new')}>
              <Plus className="w-4 h-4 mr-2" />
              Tải dữ liệu
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-6">
        <ErrorBanner problem={problem} />

        {loading && !snap ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {[1,2,3].map((i) => <div key={i} className="h-48 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse" />)}
          </div>
        ) : snap && (
          <>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <LayerCard
                tone="bronze"
                title="Bronze"
                subtitle="Thô · append-only · Parquet"
                icon={HardDrive}
                href="/p2/data/bronze"
                stats={[
                  { label: 'File',    value: snap.bronze.file_count.toLocaleString('vi-VN') },
                  { label: 'Hàng',     value: snap.bronze.row_count_total.toLocaleString('vi-VN') },
                  { label: 'Dung lượng', value: snap.bronze.size_gb.toFixed(1) + ' GB' },
                ]}
                alert={snap.bronze.failed_24h > 0 ? { tone: 'error', text: `${snap.bronze.failed_24h} lần ingest fail trong 24h` } : null}
                meta={snap.bronze.last_ingested_at ? `Ingest gần nhất ${snap.bronze.last_ingested_at}` : 'Chưa có dữ liệu'}
              />
              <LayerCard
                tone="silver"
                title="Silver"
                subtitle="Đã sạch + che PII · ClickHouse"
                icon={Layers}
                href="/p2/data/silver"
                stats={[
                  { label: 'Dataset', value: snap.silver.dataset_count.toLocaleString('vi-VN') },
                  { label: 'Hàng',     value: snap.silver.row_count_total.toLocaleString('vi-VN') },
                  { label: 'Chất lượng TB', value: snap.silver.quality_avg_pct.toFixed(1) + '%' },
                ]}
                alert={snap.silver.quality_avg_pct < 90 ? { tone: 'warning', text: 'Chất lượng dữ liệu trung bình dưới 90%' } : null}
                meta={snap.silver.last_processed_at ? `Xử lý gần nhất ${snap.silver.last_processed_at}` : 'Chưa xử lý'}
              />
              <LayerCard
                tone="gold"
                title="Gold"
                subtitle="Chuẩn hoá phân tích · PostgreSQL MV"
                icon={Sparkles}
                href="/p2/data/gold"
                stats={[
                  { label: 'Feature', value: snap.gold.feature_count.toLocaleString('vi-VN') },
                  { label: 'Hàng',     value: snap.gold.row_count_total.toLocaleString('vi-VN') },
                  { label: 'Lỗi thời', value: snap.gold.stale_count.toLocaleString('vi-VN') },
                ]}
                alert={snap.gold.stale_count > 0 ? { tone: 'warning', text: `${snap.gold.stale_count} feature lỗi thời > 90 ngày` } : null}
                meta={snap.gold.last_aggregated_at ? `Tổng hợp gần nhất ${snap.gold.last_aggregated_at}` : 'Chưa tổng hợp'}
              />
            </div>

            {/* Recent activity across layers */}
            <div className="rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-6 shadow-soft-sm">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-serif text-base text-[var(--text-primary)]">Hoạt động gần đây</h3>
                <a href="/p2/pipelines" className="text-xs text-[var(--primary-gold-dark)] hover:underline flex items-center gap-1">
                  Xem pipeline đầy đủ <ArrowRight className="w-3.5 h-3.5" />
                </a>
              </div>
              {snap.recent.length === 0 ? (
                <p className="text-sm text-[var(--text-secondary)] text-center py-6">Chưa có hoạt động.</p>
              ) : (
                <div className="space-y-2">
                  {snap.recent.map((r) => (
                    <div key={r.id} className="flex items-center gap-4 p-3 rounded-md-custom hover:bg-[var(--bg-app)]/40 transition-colors">
                      <LayerPill layer={r.layer} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-[var(--text-primary)] truncate">{r.name}</p>
                        <p className="text-xs text-[var(--text-secondary)] mt-0.5">{r.action} · {r.at}</p>
                      </div>
                      {r.status === 'ok'      && <CheckCircle2 className="w-4 h-4 text-[var(--state-success)]" />}
                      {r.status === 'fail'    && <AlertCircle  className="w-4 h-4 text-[var(--state-error)]" />}
                      {r.status === 'running' && <Activity     className="w-4 h-4 text-[var(--state-warning)] animate-pulse" />}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* K-rule reminders */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
              <KRuleCard num="K-2" text="Bronze append-only — không sửa, không xoá. Mọi thay đổi qua pipeline mới." />
              <KRuleCard num="K-5" text="Silver che PII trước mọi truy vấn — email/phone/ID hiện dạng <EMAIL_1>." />
              <KRuleCard num="K-9" text="Gold dùng NUMERIC(14,4) cho tiền, NUMERIC(5,4) cho tỷ lệ — không FLOAT." />
            </div>
          </>
        )}
      </div>
    </>
  );
}

function LayerCard({
  tone, title, subtitle, icon: Icon, href, stats, alert, meta,
}: any) {
  const accent = {
    bronze: 'border-l-[#BFA88C]', // gold-dark cho Bronze
    silver: 'border-l-[#A5B4CB]', // info cho Silver
    gold:   'border-l-[var(--primary-gold)]',
  }[tone];
  return (
    <a
      href={href}
      className={cn(
        'block rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] border-l-4 p-5 shadow-soft-sm transition-all hover:shadow-soft-md hover:-translate-y-0.5',
        accent,
      )}
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-md-custom bg-[var(--primary-gold)]/12 flex items-center justify-center">
            <Icon className="w-5 h-5 text-[var(--primary-gold-dark)]" />
          </div>
          <div>
            <h3 className="font-serif text-lg text-[var(--text-primary)]">{title}</h3>
            <p className="text-[11px] text-[var(--text-secondary)]">{subtitle}</p>
          </div>
        </div>
        <ArrowRight className="w-4 h-4 text-[var(--text-secondary)] mt-2" />
      </div>
      <div className="grid grid-cols-3 gap-3 mb-3">
        {stats.map((s: any) => (
          <div key={s.label}>
            <p className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">{s.label}</p>
            <p className="font-serif text-lg text-[var(--text-primary)] mt-0.5">{s.value}</p>
          </div>
        ))}
      </div>
      {alert && (
        <div className={cn(
          'mt-3 px-3 py-2 rounded-sm-custom text-xs',
          alert.tone === 'error'   ? 'bg-[var(--state-error)]/10 text-[#9B5050]'
          : alert.tone === 'warning' ? 'bg-[var(--state-warning)]/10 text-[#9E814D]'
          : 'bg-[var(--state-info)]/10 text-[#52647D]',
        )}>
          {alert.text}
        </div>
      )}
      <p className="text-[11px] text-[var(--text-secondary)] mt-2 flex items-center gap-1.5">
        <Clock className="w-3 h-3" />
        {meta}
      </p>
    </a>
  );
}

function LayerPill({ layer }: { layer: 'bronze' | 'silver' | 'gold' }) {
  const cfg = {
    bronze: { variant: 'warning' as any, label: 'Bronze' },
    silver: { variant: 'info'    as any, label: 'Silver' },
    gold:   { variant: 'current' as any, label: 'Gold' },
  }[layer];
  return <Badge variant={cfg.variant}>{cfg.label}</Badge>;
}

function KRuleCard({ num, text }: { num: string; text: string }) {
  return (
    <div className="rounded-md-custom bg-[var(--bg-app)]/50 border border-[var(--border-color)] p-3">
      <span className="font-mono text-[10px] font-semibold text-[var(--primary-gold-dark)]">{num}</span>
      <p className="text-[var(--text-secondary)] mt-1 leading-relaxed">{text}</p>
    </div>
  );
}
