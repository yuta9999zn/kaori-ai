// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 54. /p2/strategy/timeline — Strategy Timeline / Gantt (F-054 🔵 Phase 2)
// ----------------------------------------------------------------------------
// Hiển thị milestone của các initiative trên dải thời gian (quý/tháng):
//   - Mỗi initiative một row, milestone trải dọc theo timeline.
//   - Màu phản ánh trạng thái: completed · in_progress · scheduled · at_risk.
//   - Click milestone → drawer chi tiết (owner, dependency, ghi chú).
//
// Phase 2 (F-054). Wire `GET /api/v1/strategy/timeline?period=2026-Q2`. Render
// thuần CSS grid (không dùng D3) để giữ template gọn.
// ============================================================================

import React, { useMemo, useState } from 'react';
import {
  GanttChartSquare, ArrowLeft, Plus, ZoomIn, ZoomOut, Calendar,
  CheckCircle2, Loader2, Clock, AlertTriangle, X, ShieldCheck,
} from 'lucide-react';

import { Button, Badge, cn } from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
// ============================================================================
// Types & helpers
// ============================================================================

type MilestoneStatus = 'completed' | 'in_progress' | 'scheduled' | 'at_risk';

interface Milestone {
  id:           string;
  title:        string;
  start_date:   string; // ISO
  end_date:     string; // ISO
  status:       MilestoneStatus;
  owner:        string;
  depends_on?:  string[];
  notes?:       string;
}

interface Initiative {
  id:          string;
  name:        string;
  category:    string;
  milestones:  Milestone[];
}

const STATUS_META: Record<MilestoneStatus, { label: string; icon: any; bg: string; border: string; text: string }> = {
  completed:   { label: 'Hoàn thành',  icon: CheckCircle2, bg: 'bg-[var(--state-success)]/15', border: 'border-[var(--state-success)]/40', text: 'text-[#5C856A]' },
  in_progress: { label: 'Đang chạy',    icon: Loader2,      bg: 'bg-[var(--primary-gold)]/15',  border: 'border-[var(--primary-gold)]/40',  text: 'text-[var(--primary-gold-dark)]' },
  scheduled:   { label: 'Đã lên lịch',  icon: Clock,        bg: 'bg-[var(--state-info)]/15',    border: 'border-[var(--state-info)]/40',    text: 'text-[#52647D]' },
  at_risk:     { label: 'At-risk',      icon: AlertTriangle, bg: 'bg-[var(--state-error)]/15',   border: 'border-[var(--state-error)]/40',   text: 'text-[#9B5050]' },
};

// View period: Q2/2026 = April 1 → June 30 (90 days)
const PERIOD_START = new Date('2026-04-01');
const PERIOD_END   = new Date('2026-06-30');
const PERIOD_DAYS  = Math.round((+PERIOD_END - +PERIOD_START) / 86_400_000) + 1;
const TODAY        = new Date('2026-05-01');

function dayOffset(iso: string): number {
  const d = new Date(iso);
  return Math.max(0, Math.min(PERIOD_DAYS, Math.round((+d - +PERIOD_START) / 86_400_000)));
}

const INITIATIVES: Initiative[] = [
  {
    id: 'init_1', name: 'Triển khai Auto DB pilot', category: 'Sản phẩm',
    milestones: [
      { id: 'm_11', title: 'Hoàn thành schema suggestion engine', start_date: '2026-04-01', end_date: '2026-04-15', status: 'completed',   owner: 'huy@acme.vn' },
      { id: 'm_12', title: 'Pilot khách hàng số 1',                start_date: '2026-04-16', end_date: '2026-04-30', status: 'completed',   owner: 'lan@acme.vn', depends_on: ['m_11'] },
      { id: 'm_13', title: 'Pilot khách hàng số 5 — TPHCM',        start_date: '2026-05-01', end_date: '2026-05-15', status: 'in_progress', owner: 'lan@acme.vn', depends_on: ['m_12'] },
      { id: 'm_14', title: 'Báo cáo tổng kết pilot',                start_date: '2026-06-15', end_date: '2026-06-25', status: 'scheduled',   owner: 'minh@acme.vn' },
    ],
  },
  {
    id: 'init_2', name: 'Giảm churn APAC', category: 'Khách hàng',
    milestones: [
      { id: 'm_21', title: 'Phân tích root cause churn',            start_date: '2026-04-05', end_date: '2026-04-20', status: 'completed', owner: 'lan@acme.vn' },
      { id: 'm_22', title: 'Triển khai retention campaign',         start_date: '2026-04-25', end_date: '2026-05-25', status: 'at_risk',   owner: 'minh@acme.vn', depends_on: ['m_21'], notes: 'Trễ 5 ngày — chờ approval ngân sách marketing.' },
      { id: 'm_23', title: 'Đánh giá hiệu quả campaign',            start_date: '2026-06-01', end_date: '2026-06-20', status: 'scheduled', owner: 'lan@acme.vn', depends_on: ['m_22'] },
    ],
  },
  {
    id: 'init_3', name: 'Mở rộng SME', category: 'Doanh thu',
    milestones: [
      { id: 'm_31', title: 'Hoàn thiện gói SME starter',            start_date: '2026-04-01', end_date: '2026-04-30', status: 'completed',   owner: 'huy@acme.vn' },
      { id: 'm_32', title: 'Chiến dịch outbound 200 leads',         start_date: '2026-05-05', end_date: '2026-06-05', status: 'in_progress', owner: 'minh@acme.vn' },
      { id: 'm_33', title: 'Đạt 60 khách SME mới',                  start_date: '2026-06-01', end_date: '2026-06-30', status: 'scheduled',   owner: 'minh@acme.vn', depends_on: ['m_32'] },
    ],
  },
];

// ============================================================================
// Page
// ============================================================================

export default function StrategyTimelinePage() {
  const [zoom, setZoom] = useState<'month' | 'quarter'>('quarter');
  const [selected, setSelected] = useState<Milestone | null>(null);

  const months = useMemo(() => {
    // List of {label, startOffset, days} for each month spanned by the period.
    const result: { label: string; startOffset: number; days: number }[] = [];
    let cursor = new Date(PERIOD_START);
    while (cursor <= PERIOD_END) {
      const monthStart = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
      const monthEnd = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0);
      const startOffset = Math.max(0, Math.round((+monthStart - +PERIOD_START) / 86_400_000));
      const days = Math.min(PERIOD_DAYS, Math.round((+monthEnd - +monthStart) / 86_400_000) + 1);
      result.push({ label: cursor.toLocaleString('vi-VN', { month: 'short', year: 'numeric' }), startOffset, days });
      cursor = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1);
    }
    return result;
  }, []);

  return (
    <>
      <PageHeader
        title="Lộ trình"
        description="Milestone của các initiative theo quý. Click thanh để xem chi tiết."
        actions={
          <>
            <Badge variant="info">Phase 2 · F-054</Badge>
            <a href="/p2/strategy"><Button variant="tertiary" size="md"><ArrowLeft className="w-4 h-4 mr-2" /> Tổng quan</Button></a>
            <Button variant="primary" size="md">
              <Plus className="w-4 h-4 mr-2" /> Thêm milestone
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1500px] mx-auto space-y-4">
        {/* Toolbar */}
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-3 flex items-center justify-between flex-wrap gap-3 shadow-soft-sm">
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-[var(--primary-gold-dark)]" />
            <span className="text-sm text-[var(--text-primary)] font-medium">Q2 2026 · 1/4 → 30/6</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setZoom('month')}
              className={cn('p-1.5 rounded-sm-custom border transition-colors',
                zoom === 'month' ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/10 text-[var(--text-primary)]' : 'border-transparent text-[var(--text-secondary)] hover:bg-[var(--bg-app)]')}
              title="Theo tháng"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
            <button
              onClick={() => setZoom('quarter')}
              className={cn('p-1.5 rounded-sm-custom border transition-colors',
                zoom === 'quarter' ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/10 text-[var(--text-primary)]' : 'border-transparent text-[var(--text-secondary)] hover:bg-[var(--bg-app)]')}
              title="Theo quý"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <div className="border-l border-[var(--border-color)] pl-3 ml-2 flex items-center gap-3 text-[11px] text-[var(--text-secondary)]">
              {(['completed', 'in_progress', 'scheduled', 'at_risk'] as MilestoneStatus[]).map((s) => {
                const m = STATUS_META[s];
                return (
                  <span key={s} className="inline-flex items-center gap-1">
                    <span className={cn('w-2.5 h-2.5 rounded-sm-custom border', m.bg, m.border)} />
                    {m.label}
                  </span>
                );
              })}
            </div>
          </div>
        </div>

        {/* Gantt grid */}
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
          {/* Month header */}
          <div className="grid grid-cols-[260px_1fr] border-b border-[var(--border-color)] bg-[var(--bg-app)]">
            <div className="px-4 py-3 text-[11px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
              Initiative
            </div>
            <div className="relative h-10">
              <div className="flex h-full">
                {months.map((m, i) => (
                  <div
                    key={m.label}
                    className={cn(
                      'flex items-center justify-center text-[11px] font-medium uppercase tracking-wider text-[var(--text-secondary)]',
                      i < months.length - 1 && 'border-r border-[var(--border-color)]',
                    )}
                    style={{ width: `${(m.days / PERIOD_DAYS) * 100}%` }}
                  >
                    {m.label}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Body */}
          <div className="divide-y divide-[var(--border-color)]/60">
            {INITIATIVES.map((init) => (
              <div key={init.id} className="grid grid-cols-[260px_1fr]">
                <div className="px-4 py-4 border-r border-[var(--border-color)]/60 flex flex-col gap-1 justify-center">
                  <p className="text-sm font-medium text-[var(--text-primary)] line-clamp-2">{init.name}</p>
                  <p className="text-[11px] text-[var(--text-secondary)]">{init.category} · {init.milestones.length} milestone</p>
                </div>
                <div className="relative py-4 min-h-[68px]">
                  {/* Today line */}
                  <div
                    className="absolute top-0 bottom-0 w-px bg-[var(--state-error)]/50 z-10"
                    style={{ left: `${(dayOffset(TODAY.toISOString()) / PERIOD_DAYS) * 100}%` }}
                    title={`Hôm nay ${TODAY.toLocaleDateString('vi-VN')}`}
                  />
                  {init.milestones.map((m, i) => (
                    <MilestoneBar
                      key={m.id}
                      milestone={m}
                      row={i}
                      onClick={() => setSelected(m)}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            Đường đỏ dọc = hôm nay ({TODAY.toLocaleDateString('vi-VN')}). Phụ thuộc giữa milestone hiển thị bằng <code>depends_on</code>
            ở drawer chi tiết — Phase 2 sẽ vẽ arrow nối tự động.
          </p>
        </div>
      </div>

      {/* Drawer */}
      {selected && <DetailDrawer milestone={selected} onClose={() => setSelected(null)} />}
    </>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

function MilestoneBar({
  milestone: m, row, onClick,
}: { milestone: Milestone; row: number; onClick: () => void }) {
  const startOffset = dayOffset(m.start_date);
  const endOffset   = dayOffset(m.end_date);
  const widthPct    = Math.max(2, ((endOffset - startOffset) / PERIOD_DAYS) * 100);
  const leftPct     = (startOffset / PERIOD_DAYS) * 100;
  const meta = STATUS_META[m.status];
  const Icon = meta.icon;

  return (
    <button
      onClick={onClick}
      className={cn(
        'absolute h-7 rounded-md-custom border flex items-center px-2 gap-1.5 text-[11px] font-medium hover:shadow-soft-md transition-all overflow-hidden',
        meta.bg, meta.border, meta.text,
      )}
      style={{
        left:  `${leftPct}%`,
        width: `${widthPct}%`,
        top:   `${4 + row * 32}px`,
      }}
    >
      <Icon className={cn('w-3 h-3 shrink-0', m.status === 'in_progress' && 'animate-spin')} />
      <span className="truncate">{m.title}</span>
    </button>
  );
}

function DetailDrawer({
  milestone: m, onClose,
}: { milestone: Milestone; onClose: () => void }) {
  const meta = STATUS_META[m.status];
  const Icon = meta.icon;
  return (
    <>
      <div className="fixed inset-0 bg-[var(--text-primary)]/30 backdrop-blur-sm z-40" onClick={onClose} />
      <aside className="fixed top-0 right-0 bottom-0 w-full max-w-md bg-[var(--bg-card)] border-l border-[var(--border-color)] shadow-soft-lg z-50 overflow-y-auto animate-slide-up-fade">
        <div className="p-5 border-b border-[var(--border-color)] flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] mb-1">Milestone</p>
            <h3 className="font-serif text-lg text-[var(--text-primary)] leading-snug">{m.title}</h3>
          </div>
          <button onClick={onClose} className="p-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] mb-2">Trạng thái</p>
            <Badge variant={
              m.status === 'completed' ? 'success' : m.status === 'at_risk' ? 'error' :
              m.status === 'in_progress' ? 'current' : 'info'
            }>
              <Icon className="w-3 h-3 mr-1" /> {meta.label}
            </Badge>
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">Bắt đầu</p>
              <p className="text-[var(--text-primary)] mt-0.5">{new Date(m.start_date).toLocaleDateString('vi-VN')}</p>
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">Kết thúc</p>
              <p className="text-[var(--text-primary)] mt-0.5">{new Date(m.end_date).toLocaleDateString('vi-VN')}</p>
            </div>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] mb-1">Chủ</p>
            <p className="text-sm text-[var(--text-primary)]">{m.owner}</p>
          </div>
          {m.depends_on && m.depends_on.length > 0 && (
            <div>
              <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] mb-2">Phụ thuộc</p>
              <div className="flex flex-wrap gap-1.5">
                {m.depends_on.map((id) => <Badge key={id} variant="default">{id}</Badge>)}
              </div>
            </div>
          )}
          {m.notes && (
            <div>
              <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] mb-1">Ghi chú</p>
              <p className="text-sm text-[var(--text-primary)] leading-relaxed">{m.notes}</p>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
