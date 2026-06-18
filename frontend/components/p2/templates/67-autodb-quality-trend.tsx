// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 67. /p2/auto-db/quality-trend — Data Quality Trend (F-057 🔵 Phase 2)
// ----------------------------------------------------------------------------
// Theo dõi chất lượng dữ liệu theo thời gian:
//   - 4 KPI tile (avg score / null rate avg / type compliance / freshness avg).
//   - Sparkline 30 ngày cho score tổng (SVG thuần).
//   - Bảng score per dataset với 4 dimension (null/type/uniqueness/freshness).
//   - Click 1 dataset → bottom panel hiển thị breakdown từng cột.
//
// Wire (Phase 2): `GET /api/v1/auto-db/quality?dataset_id=...&period=30d`.
// Score tự tính theo weighted average 4 dimension.
// ============================================================================

import React, { useMemo, useState } from 'react';
import {
  TrendingUp, ArrowLeft, Database, ShieldCheck, AlertCircle,
  CheckCircle2, Clock, Sparkles,
} from 'lucide-react';

import { Button, Badge, cn } from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
// ============================================================================
// Types
// ============================================================================

interface QualityScore {
  null_rate:        number;  // 0-100 (lower better → render as 100-null_rate)
  type_compliance:  number;  // 0-100
  uniqueness:       number;  // 0-100
  freshness:        number;  // 0-100
}

interface DatasetQuality {
  id:              string;
  name:            string;
  domain:          string;
  rows:            number;
  overall:         number;  // 0-100
  scores:          QualityScore;
  trend:           number[]; // last 30 days (0-100)
  column_scores:   { name: string; null_rate: number; type_compliance: number; uniqueness: number }[];
  last_check:      string;
}

const DATASETS: DatasetQuality[] = [
  {
    id: 'ds_orders',    name: 'orders',                domain: 'Bán hàng', rows: 84_120, overall: 91,
    scores: { null_rate: 96, type_compliance: 98, uniqueness: 92, freshness: 78 },
    trend:  [88, 89, 87, 90, 91, 92, 90, 88, 91, 93, 92, 91, 90, 91, 92, 93, 91, 90, 92, 91, 90, 92, 91, 92, 91, 90, 91, 92, 91, 91],
    column_scores: [
      { name: 'order_id',     null_rate: 0,   type_compliance: 100, uniqueness: 100 },
      { name: 'customer_id',  null_rate: 0,   type_compliance: 100, uniqueness: 12 },
      { name: 'order_date',   null_rate: 0.2, type_compliance: 99,  uniqueness: 32 },
      { name: 'total_amount', null_rate: 0.1, type_compliance: 100, uniqueness: 88 },
      { name: 'status',       null_rate: 0,   type_compliance: 100, uniqueness: 0.01 },
      { name: 'note',         null_rate: 32,  type_compliance: 95,  uniqueness: 90 },
    ],
    last_check: '2026-04-30T08:00:00+07:00',
  },
  {
    id: 'ds_customer',  name: 'customer_master',       domain: 'CRM',      rows: 12_540, overall: 96,
    scores: { null_rate: 99, type_compliance: 100, uniqueness: 95, freshness: 90 },
    trend:  [94, 94, 95, 96, 96, 95, 96, 96, 97, 96, 96, 95, 96, 96, 96, 97, 96, 96, 96, 96, 96, 95, 96, 96, 96, 96, 96, 96, 96, 96],
    column_scores: [
      { name: 'customer_id', null_rate: 0,   type_compliance: 100, uniqueness: 100 },
      { name: 'full_name',   null_rate: 0,   type_compliance: 100, uniqueness: 99 },
      { name: 'email',       null_rate: 12,  type_compliance: 99,  uniqueness: 94 },
      { name: 'created_at',  null_rate: 0,   type_compliance: 100, uniqueness: 80 },
    ],
    last_check: '2026-04-30T07:30:00+07:00',
  },
  {
    id: 'ds_finance',   name: 'finance_transactions', domain: 'Tài chính', rows: 142_380, overall: 78,
    scores: { null_rate: 82, type_compliance: 90, uniqueness: 70, freshness: 72 },
    trend:  [75, 76, 77, 76, 78, 79, 78, 76, 75, 77, 78, 79, 78, 78, 79, 78, 77, 78, 78, 79, 78, 78, 77, 78, 78, 78, 78, 77, 78, 78],
    column_scores: [
      { name: 'tx_id',     null_rate: 0,    type_compliance: 100, uniqueness: 100 },
      { name: 'amount',    null_rate: 8,    type_compliance: 92,  uniqueness: 65 },
      { name: 'currency',  null_rate: 0,    type_compliance: 100, uniqueness: 0.05 },
      { name: 'memo',      null_rate: 38,   type_compliance: 80,  uniqueness: 88 },
      { name: 'tx_date',   null_rate: 1,    type_compliance: 99,  uniqueness: 22 },
    ],
    last_check: '2026-04-30T03:14:00+07:00',
  },
  {
    id: 'ds_support',   name: 'support_tickets',      domain: 'Dịch vụ',   rows: 18_904, overall: 82,
    scores: { null_rate: 85, type_compliance: 88, uniqueness: 80, freshness: 75 },
    trend:  [78, 80, 79, 81, 82, 81, 82, 83, 82, 81, 82, 83, 82, 82, 82, 81, 82, 82, 82, 82, 81, 82, 82, 82, 82, 82, 82, 82, 82, 82],
    column_scores: [
      { name: 'ticket_id',  null_rate: 0,  type_compliance: 100, uniqueness: 100 },
      { name: 'subject',    null_rate: 0,  type_compliance: 100, uniqueness: 95 },
      { name: 'priority',   null_rate: 5,  type_compliance: 90,  uniqueness: 0.4 },
      { name: 'assigned_to', null_rate: 25, type_compliance: 95,  uniqueness: 1.2 },
    ],
    last_check: '2026-04-29T11:00:00+07:00',
  },
];

const DIM_LABELS = {
  null_rate:       'Null rate',
  type_compliance: 'Type',
  uniqueness:      'Uniqueness',
  freshness:       'Freshness',
} as const;

// ============================================================================
// Page
// ============================================================================

export default function QualityTrendPage() {
  const [selectedId, setSelectedId] = useState<string>(DATASETS[0].id);
  const selected = useMemo(() => DATASETS.find((d) => d.id === selectedId)!, [selectedId]);

  const stats = useMemo(() => {
    const overallAvg = Math.round(DATASETS.reduce((s, d) => s + d.overall, 0) / DATASETS.length);
    const nullAvg    = Math.round(DATASETS.reduce((s, d) => s + d.scores.null_rate, 0) / DATASETS.length);
    const typeAvg    = Math.round(DATASETS.reduce((s, d) => s + d.scores.type_compliance, 0) / DATASETS.length);
    const freshAvg   = Math.round(DATASETS.reduce((s, d) => s + d.scores.freshness, 0) / DATASETS.length);
    return { overall: overallAvg, null_rate: nullAvg, type: typeAvg, fresh: freshAvg };
  }, []);

  return (
    <>
      <PageHeader
        title="Chất lượng dữ liệu"
        description="Score tổng hợp 4 chiều (null/type/uniqueness/freshness) cho mỗi dataset Gold."
        actions={
          <>
            <Badge variant="info">Phase 2 · F-057</Badge>
            <a href="/p2/auto-db">
              <Button variant="tertiary" size="md"><ArrowLeft className="w-4 h-4 mr-2" /> Auto DB</Button>
            </a>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-6">
        {/* KPI tiles */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatTile label="Score trung bình"    value={stats.overall}   icon={CheckCircle2} tone="text-[var(--state-success)]" suffix="%" />
          <StatTile label="Null compliance avg" value={stats.null_rate} icon={Sparkles}     tone="text-[var(--primary-gold-dark)]" suffix="%" />
          <StatTile label="Type compliance avg" value={stats.type}      icon={Database}     tone="text-[var(--state-info)]" suffix="%" />
          <StatTile label="Freshness avg"       value={stats.fresh}     icon={Clock}        tone="text-[var(--state-warning)]" suffix="%" />
        </div>

        {/* Trend chart for selected */}
        <TrendChart dataset={selected} />

        {/* Per-dataset table */}
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-[var(--border-color)] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-[var(--primary-gold-dark)]" />
              <h3 className="font-serif text-base text-[var(--text-primary)]">Score theo dataset</h3>
            </div>
            <span className="text-[11px] text-[var(--text-secondary)]">Click để xem breakdown từng cột</span>
          </div>
          <div className="overflow-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-[var(--bg-app)] border-b border-[var(--border-color)] text-[11px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
                <tr>
                  <th className="px-5 py-3">Dataset</th>
                  <th className="px-5 py-3">Tổng</th>
                  <th className="px-5 py-3">Null rate</th>
                  <th className="px-5 py-3">Type</th>
                  <th className="px-5 py-3">Uniqueness</th>
                  <th className="px-5 py-3">Freshness</th>
                  <th className="px-5 py-3">Lần check</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]/60">
                {DATASETS.map((d) => (
                  <DatasetRow
                    key={d.id}
                    dataset={d}
                    active={d.id === selectedId}
                    onClick={() => setSelectedId(d.id)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Column breakdown for selected */}
        <ColumnBreakdown dataset={selected} />

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            Score tổng = weighted avg (null × 0.3 + type × 0.3 + uniqueness × 0.2 + freshness × 0.2).
            Score &lt; 70 sẽ tự sinh Alert (file 62) source=data, severity=warning.
          </p>
        </div>
      </div>
    </>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

function StatTile({
  label, value, icon: Icon, tone, suffix,
}: { label: string; value: number; icon: any; tone: string; suffix?: string }) {
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] uppercase tracking-wider font-medium text-[var(--text-secondary)]">{label}</span>
        <Icon className={cn('w-5 h-5', tone)} />
      </div>
      <p className="font-serif text-3xl text-[var(--text-primary)]">{value}{suffix}</p>
    </div>
  );
}

function TrendChart({ dataset }: { dataset: DatasetQuality }) {
  const max = 100;
  const min = Math.min(...dataset.trend) - 5;
  const range = max - min;
  const w = 800;
  const h = 160;
  const step = w / (dataset.trend.length - 1);
  const points = dataset.trend.map((v, i) => `${i * step},${h - ((v - min) / range) * h}`).join(' ');

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-[var(--primary-gold-dark)]" />
          <h3 className="font-serif text-base text-[var(--text-primary)]">
            Trend 30 ngày · <span className="font-mono text-sm">{dataset.name}</span>
          </h3>
        </div>
        <Badge variant={dataset.overall >= 90 ? 'success' : dataset.overall >= 80 ? 'info' : dataset.overall >= 70 ? 'warning' : 'error'}>
          Score {dataset.overall}%
        </Badge>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-40">
        {/* Grid */}
        {[0, 25, 50, 75, 100].map((p) => (
          <line
            key={p}
            x1={0}
            x2={w}
            y1={h - ((p - min) / range) * h}
            y2={h - ((p - min) / range) * h}
            stroke="currentColor"
            strokeOpacity={0.08}
            strokeDasharray="3 3"
            className="text-[var(--text-secondary)]"
          />
        ))}
        {/* Trend line */}
        <polyline
          points={points}
          fill="none"
          stroke="var(--primary-gold-dark)"
          strokeWidth={2}
        />
        {/* Area fill */}
        <polygon
          points={`0,${h} ${points} ${w},${h}`}
          fill="var(--primary-gold)"
          fillOpacity={0.15}
        />
      </svg>
      <div className="flex items-center justify-between mt-3 text-[11px] text-[var(--text-secondary)]">
        <span>30 ngày trước</span>
        <span>Hôm nay</span>
      </div>
    </div>
  );
}

function DatasetRow({
  dataset: d, active, onClick,
}: { dataset: DatasetQuality; active: boolean; onClick: () => void }) {
  return (
    <tr
      onClick={onClick}
      className={cn(
        'cursor-pointer transition-colors',
        active ? 'bg-[var(--primary-gold)]/8' : 'hover:bg-[var(--bg-app)]/40',
      )}
    >
      <td className="px-5 py-3">
        <div>
          <p className="font-mono text-sm text-[var(--text-primary)]">{d.name}</p>
          <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">{d.domain} · {d.rows.toLocaleString('vi-VN')} dòng</p>
        </div>
      </td>
      <td className="px-5 py-3"><ScorePill score={d.overall} /></td>
      <td className="px-5 py-3"><ScoreBar value={d.scores.null_rate} /></td>
      <td className="px-5 py-3"><ScoreBar value={d.scores.type_compliance} /></td>
      <td className="px-5 py-3"><ScoreBar value={d.scores.uniqueness} /></td>
      <td className="px-5 py-3"><ScoreBar value={d.scores.freshness} /></td>
      <td className="px-5 py-3 text-xs text-[var(--text-secondary)]">
        {new Date(d.last_check).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
      </td>
    </tr>
  );
}

function ScoreBar({ value }: { value: number }) {
  const tone =
    value >= 90 ? 'bg-[var(--state-success)]' :
    value >= 80 ? 'bg-[var(--primary-gold)]' :
    value >= 70 ? 'bg-[var(--state-warning)]' :
    'bg-[var(--state-error)]';
  return (
    <div className="flex items-center gap-2 min-w-[100px]">
      <div className="flex-1 h-1.5 rounded-sm-custom bg-[var(--border-color)]/50 overflow-hidden">
        <div className={cn('h-full transition-all', tone)} style={{ width: `${value}%` }} />
      </div>
      <span className="text-[11px] text-[var(--text-secondary)] font-mono w-9 text-right">{value}%</span>
    </div>
  );
}

function ScorePill({ score }: { score: number }) {
  if (score >= 90) return <Badge variant="success">{score}%</Badge>;
  if (score >= 80) return <Badge variant="info">{score}%</Badge>;
  if (score >= 70) return <Badge variant="warning">{score}%</Badge>;
  return <Badge variant="error">{score}%</Badge>;
}

function ColumnBreakdown({ dataset: d }: { dataset: DatasetQuality }) {
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-[var(--border-color)] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-[var(--primary-gold-dark)]" />
          <h3 className="font-serif text-base text-[var(--text-primary)]">
            Breakdown theo cột · <span className="font-mono text-sm">{d.name}</span>
          </h3>
        </div>
        <Badge variant="default">{d.column_scores.length} cột</Badge>
      </div>
      <div className="overflow-auto">
        <table className="w-full text-sm text-left">
          <thead className="bg-[var(--bg-app)] border-b border-[var(--border-color)] text-[11px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
            <tr>
              <th className="px-5 py-3">Cột</th>
              <th className="px-5 py-3">Null rate</th>
              <th className="px-5 py-3">Type compliance</th>
              <th className="px-5 py-3">Uniqueness</th>
              <th className="px-5 py-3">Đánh giá</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border-color)]/60">
            {d.column_scores.map((c) => {
              const issues: string[] = [];
              if (c.null_rate > 30) issues.push('Null rate cao');
              if (c.type_compliance < 90) issues.push('Type không nhất quán');
              if (c.uniqueness > 95 && c.name !== 'id') issues.push('Có thể là cột PK chưa khai báo');
              return (
                <tr key={c.name} className="hover:bg-[var(--bg-app)]/40 transition-colors">
                  <td className="px-5 py-3 font-mono text-sm text-[var(--text-primary)]">{c.name}</td>
                  <td className="px-5 py-3 text-xs text-[var(--text-primary)]">{c.null_rate.toFixed(1)}%</td>
                  <td className="px-5 py-3"><ScoreBar value={c.type_compliance} /></td>
                  <td className="px-5 py-3"><ScoreBar value={c.uniqueness} /></td>
                  <td className="px-5 py-3">
                    {issues.length === 0 ? (
                      <Badge variant="success"><CheckCircle2 className="w-3 h-3 mr-1" /> OK</Badge>
                    ) : (
                      <div className="flex flex-wrap gap-1">
                        {issues.map((i) => <Badge key={i} variant="warning">{i}</Badge>)}
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
