// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 52. /p2/strategy — Strategy Hub (F-054 🔵 Phase 2)
// ----------------------------------------------------------------------------
// Trang tổng quan chiến lược: 3 module card (OKR · Lộ trình · Họp review) +
// KPI tile chiến lược + AI suggestion banner gợi ý objective dựa trên insight
// gần đây.
//
// Phase 1 chưa có module Strategy chính thức (chỉ có Decision Log). Phase 2
// (F-054) wire `GET /api/v1/strategy/summary` cho tile + suggestion. Hiện
// hub render fixture cho preview.
// ============================================================================

import React, { useEffect, useState } from 'react';
import {
  Target, GanttChartSquare, CalendarCheck, ArrowRight, Sparkles,
  TrendingUp, AlertCircle, CheckCircle2, Layers,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, api, cn, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
// ============================================================================
// Types
// ============================================================================

interface ModuleCard {
  code:        string;
  title:       string;
  description: string;
  href:        string;
  icon:        any;
  metric?:     { label: string; value: string };
}

const MODULES: ModuleCard[] = [
  {
    code: 'okr',
    title: 'OKR',
    description: 'Objective + 3 Key Results · cập nhật progress hàng tuần.',
    href: '/p2/strategy/okr',
    icon: Target,
    metric: { label: '8 OKR đang chạy · 3 at-risk', value: 'Q2 2026' },
  },
  {
    code: 'timeline',
    title: 'Lộ trình',
    description: 'Gantt-style milestone + phụ thuộc giữa các initiative.',
    href: '/p2/strategy/timeline',
    icon: GanttChartSquare,
    metric: { label: '12 milestone · 4 đến hạn tuần này', value: '2026' },
  },
  {
    code: 'review',
    title: 'Họp review',
    description: 'Lịch họp định kỳ + AI-prepped insight pack trước mỗi cuộc.',
    href: '/p2/strategy/review-meetings',
    icon: CalendarCheck,
    metric: { label: 'Cuộc họp gần nhất 2026-04-25', value: 'Hằng tháng' },
  },
];

interface StrategySummary {
  okr_total:      number;
  okr_on_track:   number;
  okr_at_risk:    number;
  okr_off_track:  number;
  next_milestone: { title: string; due_date: string } | null;
  next_meeting:   { title: string; scheduled_at: string } | null;
}

const MOCK_SUMMARY: StrategySummary = {
  okr_total:     8,
  okr_on_track:  4,
  okr_at_risk:   3,
  okr_off_track: 1,
  next_milestone: { title: 'Pilot khách hàng số 5 — TPHCM', due_date: '2026-05-08' },
  next_meeting:   { title: 'QBR Quý 2/2026',                scheduled_at: '2026-05-15T14:00:00+07:00' },
};

// ============================================================================
// Page
// ============================================================================

export default function StrategyHubPage() {
  const [summary, setSummary] = useState<StrategySummary>(MOCK_SUMMARY);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await api<StrategySummary>('/api/v1/strategy/summary');
        if (!cancelled) setSummary(data);
      } catch (e: any) {
        if (!cancelled) {
          setProblem(e);
          // Keep MOCK fallback
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <>
      <PageHeader
        title="Chiến lược"
        description="Theo dõi OKR, milestone và lịch họp review của workspace."
        actions={<Badge variant="info">Phase 2 · F-054</Badge>}
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1200px] mx-auto space-y-6">
        {problem && (
          <ErrorBanner
            problem={{
              ...problem,
              title:  'Đang dùng dữ liệu mẫu',
              detail: `${problem.title}${problem.detail ? ' — ' + problem.detail : ''}. Hub hiển thị fixture cho tới khi /api/v1/strategy/summary sẵn sàng.`,
            }}
          />
        )}

        {/* OKR overview tile */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          <SummaryTile label="OKR tổng" value={loading ? '–' : summary.okr_total.toString()} icon={Layers} tone="text-[var(--text-primary)]" />
          <SummaryTile label="On-track"  value={loading ? '–' : summary.okr_on_track.toString()}  icon={CheckCircle2} tone="text-[var(--state-success)]" />
          <SummaryTile label="At-risk"   value={loading ? '–' : summary.okr_at_risk.toString()}    icon={TrendingUp}    tone="text-[var(--state-warning)]" />
          <SummaryTile label="Off-track" value={loading ? '–' : summary.okr_off_track.toString()}  icon={AlertCircle}   tone="text-[var(--state-error)]" />
        </div>

        {/* AI suggestion */}
        <SuggestionBanner />

        {/* 3 module card */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {MODULES.map((m) => <ModuleTile key={m.code} module={m} />)}
        </div>

        {/* Up-next strip */}
        {(summary.next_milestone || summary.next_meeting) && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {summary.next_milestone && (
              <UpNextCard
                title="Milestone sắp đến hạn"
                primary={summary.next_milestone.title}
                secondary={`Hạn: ${summary.next_milestone.due_date}`}
                icon={GanttChartSquare}
                href="/p2/strategy/timeline"
              />
            )}
            {summary.next_meeting && (
              <UpNextCard
                title="Cuộc họp tiếp theo"
                primary={summary.next_meeting.title}
                secondary={new Date(summary.next_meeting.scheduled_at).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                icon={CalendarCheck}
                href="/p2/strategy/review-meetings"
              />
            )}
          </div>
        )}
      </div>
    </>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

function SummaryTile({
  label, value, icon: Icon, tone,
}: { label: string; value: string; icon: any; tone: string }) {
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] uppercase tracking-wider font-medium text-[var(--text-secondary)]">{label}</span>
        <Icon className={cn('w-5 h-5', tone)} />
      </div>
      <p className="font-serif text-3xl text-[var(--text-primary)]">{value}</p>
    </div>
  );
}

function ModuleTile({ module: m }: { module: ModuleCard }) {
  const Icon = m.icon;
  return (
    <a
      href={m.href}
      className="group block bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] hover:border-[var(--primary-gold)]/50 hover:shadow-soft-md transition-all p-5"
    >
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="w-10 h-10 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center">
          <Icon className="w-5 h-5 text-[var(--primary-gold-dark)]" />
        </div>
        <Badge variant="info">P2</Badge>
      </div>
      <h3 className="font-serif text-lg text-[var(--text-primary)] group-hover:text-[var(--primary-gold-dark)] transition-colors">{m.title}</h3>
      <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">{m.description}</p>
      {m.metric && (
        <div className="mt-3 pt-3 border-t border-[var(--border-color)]/60">
          <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">{m.metric.value}</p>
          <p className="text-xs text-[var(--text-primary)] mt-1">{m.metric.label}</p>
        </div>
      )}
      <div className="mt-3 inline-flex items-center text-xs font-medium text-[var(--primary-gold-dark)] group-hover:translate-x-0.5 transition-transform">
        Vào module <ArrowRight className="w-3 h-3 ml-1" />
      </div>
    </a>
  );
}

function SuggestionBanner() {
  return (
    <div className="bg-gradient-to-br from-[var(--primary-gold)]/10 to-[var(--bg-card)] border border-[var(--primary-gold)]/30 rounded-lg-custom p-5 shadow-soft-sm">
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-md-custom bg-[var(--primary-gold)]/15 flex items-center justify-center shrink-0">
            <Sparkles className="w-5 h-5 text-[var(--primary-gold-dark)]" />
          </div>
          <div>
            <h3 className="font-serif text-base text-[var(--text-primary)]">Gợi ý từ Kaori</h3>
            <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed max-w-2xl">
              Insight tuần qua cho thấy churn APAC tăng <span className="font-medium text-[var(--text-primary)]">12%</span>. Hãy cân nhắc OKR
              <span className="font-medium text-[var(--text-primary)]"> "Giảm churn APAC xuống dưới 5% Q2/2026"</span> với 3 KR cụ thể.
            </p>
          </div>
        </div>
        <a href="/p2/strategy/okr?suggestion=apac-churn">
          <Button variant="primary" size="sm">
            Tạo OKR <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
          </Button>
        </a>
      </div>
    </div>
  );
}

function UpNextCard({
  title, primary, secondary, icon: Icon, href,
}: { title: string; primary: string; secondary: string; icon: any; href: string }) {
  return (
    <a href={href} className="block bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm hover:border-[var(--primary-gold)]/40 transition-all">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="w-4 h-4 text-[var(--primary-gold-dark)]" />
        <span className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] font-medium">{title}</span>
      </div>
      <p className="font-serif text-base text-[var(--text-primary)]">{primary}</p>
      <p className="text-xs text-[var(--text-secondary)] mt-1">{secondary}</p>
    </a>
  );
}
