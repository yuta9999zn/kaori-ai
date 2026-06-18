// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 55. /p2/strategy/review-meetings — Review Meetings (F-054 🔵 Phase 2)
// ----------------------------------------------------------------------------
// Lịch họp review chiến lược (QBR · OKR weekly · Risk monthly):
//   - Cột trái: list cuộc họp (sắp tới + đã qua).
//   - Cột phải: agenda + AI-prepped insight pack (top 3-5 insight chính, biến
//     động OKR, milestone đến hạn) — sinh trước cuộc họp 1h, lưu vào meeting
//     để tham chiếu.
//
// Phase 2 (F-054). Wire `GET /api/v1/strategy/meetings`,
// `GET /api/v1/strategy/meetings/{id}/insights` (LLM job, K-3/K-4/K-5).
// ============================================================================

import React, { useMemo, useState } from 'react';
import {
  CalendarCheck, ArrowLeft, Plus, Sparkles, Users, Clock, FileText,
  CheckCircle2, AlertTriangle, TrendingUp, Target, RefreshCw, ShieldCheck,
} from 'lucide-react';

import { Button, Badge, cn } from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
// ============================================================================
// Types
// ============================================================================

type MeetingKind = 'qbr' | 'okr_weekly' | 'risk_monthly' | 'custom';

interface Meeting {
  id:           string;
  kind:         MeetingKind;
  title:        string;
  scheduled_at: string; // ISO
  duration_min: number;
  attendees:    string[];
  agenda:       string[];
  insight_pack?: InsightPack;
  /** false → ghi chú chưa được điền sau cuộc họp. */
  notes_filled: boolean;
}

interface InsightPack {
  generated_at: string;
  okr_movements: { okr_title: string; delta_pct: number; tone: 'up' | 'down' }[];
  top_insights:  { title: string; severity: 'info' | 'warning' | 'critical' }[];
  upcoming_milestones: { title: string; due_date: string }[];
}

const KIND_LABEL: Record<MeetingKind, string> = {
  qbr:           'QBR',
  okr_weekly:    'OKR Weekly',
  risk_monthly:  'Risk Monthly',
  custom:        'Tuỳ chỉnh',
};

const NOW = new Date('2026-05-01T10:00:00+07:00');

const MEETINGS: Meeting[] = [
  {
    id: 'mtg_1', kind: 'okr_weekly', title: 'OKR Weekly tuần 18',
    scheduled_at: '2026-05-02T09:00:00+07:00', duration_min: 30,
    attendees: ['minh@acme.vn', 'lan@acme.vn', 'huy@acme.vn'],
    agenda: ['Cập nhật KR doanh thu SME', 'Review churn APAC', 'Risks tuần này'],
    notes_filled: false,
    insight_pack: {
      generated_at: '2026-05-02T08:00:00+07:00',
      okr_movements: [
        { okr_title: 'Tăng doanh thu SME 5 tỷ/tháng', delta_pct: 4,  tone: 'up' },
        { okr_title: 'Giảm churn APAC dưới 5%',         delta_pct: -2, tone: 'down' },
        { okr_title: 'Auto DB pilot 3 khách',           delta_pct: 12, tone: 'up' },
      ],
      top_insights: [
        { title: 'Doanh thu SME tăng 18% tuần này nhờ campaign outbound',          severity: 'info' },
        { title: 'Churn APAC tăng nhẹ 0.4 điểm — cần xem retention campaign',     severity: 'warning' },
        { title: 'Pilot khách hàng số 5 đang trễ tiến độ approval',                severity: 'critical' },
      ],
      upcoming_milestones: [
        { title: 'Pilot khách hàng số 5 — TPHCM',         due_date: '2026-05-08' },
        { title: 'Báo cáo retention campaign tháng 4',    due_date: '2026-05-10' },
      ],
    },
  },
  {
    id: 'mtg_2', kind: 'qbr', title: 'QBR Quý 2/2026',
    scheduled_at: '2026-05-15T14:00:00+07:00', duration_min: 90,
    attendees: ['minh@acme.vn', 'lan@acme.vn', 'huy@acme.vn', 'ceo@acme.vn'],
    agenda: ['Review toàn bộ OKR Q2', 'Risk register update', 'Plan Q3 sơ bộ', 'Q&A ban GĐ'],
    notes_filled: false,
  },
  {
    id: 'mtg_3', kind: 'risk_monthly', title: 'Risk Monthly · tháng 5',
    scheduled_at: '2026-05-20T15:00:00+07:00', duration_min: 60,
    attendees: ['lan@acme.vn', 'huy@acme.vn'],
    agenda: ['Review risk register', 'Đánh giá mitigation plan tháng 4', 'Risk mới phát sinh'],
    notes_filled: false,
  },
  {
    id: 'mtg_4', kind: 'okr_weekly', title: 'OKR Weekly tuần 17 (đã qua)',
    scheduled_at: '2026-04-25T09:00:00+07:00', duration_min: 30,
    attendees: ['minh@acme.vn', 'lan@acme.vn'],
    agenda: ['Cập nhật KR doanh thu', 'Review pilot Auto DB'],
    notes_filled: true,
  },
];

function isPast(m: Meeting) { return new Date(m.scheduled_at) < NOW; }

// ============================================================================
// Page
// ============================================================================

export default function ReviewMeetingsPage() {
  const upcoming = useMemo(
    () => MEETINGS.filter((m) => !isPast(m)).sort((a, b) => +new Date(a.scheduled_at) - +new Date(b.scheduled_at)),
    [],
  );
  const past = useMemo(
    () => MEETINGS.filter(isPast).sort((a, b) => +new Date(b.scheduled_at) - +new Date(a.scheduled_at)),
    [],
  );

  const [selectedId, setSelectedId] = useState<string>(upcoming[0]?.id ?? past[0]?.id ?? '');
  const selected = useMemo(() => MEETINGS.find((m) => m.id === selectedId) ?? null, [selectedId]);

  return (
    <>
      <PageHeader
        title="Họp review"
        description="Lịch họp QBR · OKR weekly · Risk monthly với insight pack chuẩn bị sẵn từ Kaori AI."
        actions={
          <>
            <Badge variant="info">Phase 2 · F-054</Badge>
            <a href="/p2/strategy"><Button variant="tertiary" size="md"><ArrowLeft className="w-4 h-4 mr-2" /> Tổng quan</Button></a>
            <Button variant="primary" size="md">
              <Plus className="w-4 h-4 mr-2" /> Tạo cuộc họp
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto">
        <div className="grid grid-cols-1 xl:grid-cols-[380px_1fr] gap-4">
          {/* Left list */}
          <div className="space-y-4">
            <ListSection title="Sắp tới" badge={upcoming.length}>
              {upcoming.length === 0 ? (
                <p className="text-xs text-[var(--text-secondary)] py-3 text-center">Không có cuộc họp sắp tới.</p>
              ) : (
                upcoming.map((m) => (
                  <MeetingListItem
                    key={m.id}
                    meeting={m}
                    active={m.id === selectedId}
                    onSelect={() => setSelectedId(m.id)}
                  />
                ))
              )}
            </ListSection>
            <ListSection title="Đã qua" badge={past.length}>
              {past.length === 0 ? (
                <p className="text-xs text-[var(--text-secondary)] py-3 text-center">Chưa có lịch sử họp.</p>
              ) : (
                past.map((m) => (
                  <MeetingListItem
                    key={m.id}
                    meeting={m}
                    active={m.id === selectedId}
                    onSelect={() => setSelectedId(m.id)}
                    muted
                  />
                ))
              )}
            </ListSection>
          </div>

          {/* Right detail */}
          {selected ? (
            <MeetingDetail meeting={selected} />
          ) : (
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-12 text-center">
              <CalendarCheck className="w-12 h-12 mx-auto text-[var(--text-secondary)]/30 mb-3" />
              <p className="text-sm text-[var(--text-secondary)]">Chọn 1 cuộc họp để xem agenda + insight pack.</p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

function ListSection({ title, badge, children }: { title: string; badge: number; children: React.ReactNode }) {
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-4 shadow-soft-sm">
      <div className="flex items-center gap-2 mb-3">
        <CalendarCheck className="w-4 h-4 text-[var(--primary-gold-dark)]" />
        <h3 className="font-serif text-sm text-[var(--text-primary)]">{title}</h3>
        <Badge variant="default">{badge}</Badge>
      </div>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function MeetingListItem({
  meeting: m, active, onSelect, muted,
}: { meeting: Meeting; active: boolean; onSelect: () => void; muted?: boolean }) {
  const dt = new Date(m.scheduled_at);
  const pastDone = m.notes_filled && muted;
  return (
    <button
      onClick={onSelect}
      className={cn(
        'w-full text-left p-3 rounded-md-custom border transition-all',
        active
          ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/8'
          : muted
            ? 'border-[var(--border-color)] bg-[var(--bg-app)] hover:bg-[var(--bg-card)]'
            : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--primary-gold)]/40',
      )}
    >
      <div className="flex items-start justify-between gap-2 mb-1">
        <p className="font-medium text-sm text-[var(--text-primary)] line-clamp-2">{m.title}</p>
        <Badge variant={pastDone ? 'success' : muted ? 'default' : 'info'}>
          {pastDone ? 'Đã ghi chú' : KIND_LABEL[m.kind]}
        </Badge>
      </div>
      <div className="flex items-center gap-3 text-[11px] text-[var(--text-secondary)]">
        <span className="inline-flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {dt.toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
        </span>
        <span className="inline-flex items-center gap-1">
          <Users className="w-3 h-3" /> {m.attendees.length}
        </span>
      </div>
    </button>
  );
}

function MeetingDetail({ meeting: m }: { meeting: Meeting }) {
  const dt = new Date(m.scheduled_at);
  return (
    <div className="space-y-4">
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 lg:p-6 shadow-soft-sm">
        <div className="flex items-start justify-between gap-3 mb-4 pb-4 border-b border-[var(--border-color)]/60">
          <div>
            <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] mb-1">{KIND_LABEL[m.kind]}</p>
            <h2 className="font-serif text-xl text-[var(--text-primary)]">{m.title}</h2>
          </div>
          <Badge variant="current">
            <Clock className="w-3 h-3 mr-1" />
            {dt.toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
            {' · '}{m.duration_min} phút
          </Badge>
        </div>

        {/* Agenda */}
        <div className="space-y-2 mb-4">
          <p className="text-sm font-medium text-[var(--text-primary)] flex items-center gap-2">
            <FileText className="w-4 h-4 text-[var(--primary-gold-dark)]" /> Agenda
          </p>
          <ul className="space-y-1.5 ml-6 list-disc text-sm text-[var(--text-primary)]">
            {m.agenda.map((a) => <li key={a}>{a}</li>)}
          </ul>
        </div>

        {/* Attendees */}
        <div className="space-y-2">
          <p className="text-sm font-medium text-[var(--text-primary)] flex items-center gap-2">
            <Users className="w-4 h-4 text-[var(--primary-gold-dark)]" /> Tham dự ({m.attendees.length})
          </p>
          <div className="flex flex-wrap gap-1.5">
            {m.attendees.map((email) => (
              <span key={email} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-sm-custom bg-[var(--bg-app)] border border-[var(--border-color)] text-xs text-[var(--text-primary)]">
                <span className="w-5 h-5 rounded-full bg-[var(--primary-gold)]/15 text-[10px] font-semibold text-[var(--primary-gold-dark)] flex items-center justify-center">
                  {email.slice(0, 2).toUpperCase()}
                </span>
                {email}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Insight pack */}
      {m.insight_pack ? (
        <InsightPackCard pack={m.insight_pack} />
      ) : (
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] border-dashed rounded-lg-custom p-6 text-center">
          <Sparkles className="w-10 h-10 mx-auto text-[var(--primary-gold-dark)]/40 mb-3" />
          <p className="text-sm text-[var(--text-primary)] font-medium">Insight pack chưa được tạo</p>
          <p className="text-xs text-[var(--text-secondary)] mt-1 mb-4">Kaori AI sẽ tự sinh trước cuộc họp 1h. Hoặc tạo ngay:</p>
          <Button variant="primary" size="sm">
            <RefreshCw className="w-3.5 h-3.5 mr-1.5" /> Sinh insight ngay (K-3)
          </Button>
        </div>
      )}

      <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
        <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
        <p>
          Insight pack đi qua <span className="font-mono">llm_router.py</span> (K-3). Mặc định Qwen 2.5 nội bộ — chỉ dùng AI ngoài
          khi workspace bật consent_external và đã PII-mask (K-4 + K-5).
        </p>
      </div>
    </div>
  );
}

function InsightPackCard({ pack: p }: { pack: InsightPack }) {
  const SEVERITY_META = {
    info:     { icon: TrendingUp,    tone: 'text-[var(--state-info)]' },
    warning:  { icon: AlertTriangle, tone: 'text-[var(--state-warning)]' },
    critical: { icon: AlertTriangle, tone: 'text-[var(--state-error)]' },
  };

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
      <div className="flex items-center justify-between gap-3 pb-3 border-b border-[var(--border-color)]/60 mb-4">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-[var(--primary-gold-dark)]" />
          <h3 className="font-serif text-base text-[var(--text-primary)]">Insight pack</h3>
        </div>
        <span className="text-[11px] text-[var(--text-secondary)]">
          Sinh lúc {new Date(p.generated_at).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>

      {/* OKR movements */}
      <div className="mb-4">
        <p className="text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)] mb-2 flex items-center gap-1.5">
          <Target className="w-3.5 h-3.5" /> Biến động OKR
        </p>
        <div className="space-y-1.5">
          {p.okr_movements.map((o) => (
            <div key={o.okr_title} className="flex items-center justify-between text-sm py-1.5 px-3 rounded-sm-custom bg-[var(--bg-app)]">
              <span className="text-[var(--text-primary)] truncate">{o.okr_title}</span>
              <span className={cn('font-medium text-xs', o.tone === 'up' ? 'text-[var(--state-success)]' : 'text-[var(--state-error)]')}>
                {o.tone === 'up' ? '▲' : '▼'} {Math.abs(o.delta_pct)}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Top insights */}
      <div className="mb-4">
        <p className="text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)] mb-2">Insight chính</p>
        <div className="space-y-2">
          {p.top_insights.map((ins) => {
            const meta = SEVERITY_META[ins.severity];
            const Icon = meta.icon;
            return (
              <div key={ins.title} className="flex items-start gap-2 py-2 px-3 rounded-sm-custom bg-[var(--bg-app)]">
                <Icon className={cn('w-4 h-4 shrink-0 mt-0.5', meta.tone)} />
                <span className="text-sm text-[var(--text-primary)] leading-relaxed">{ins.title}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Upcoming milestones */}
      <div>
        <p className="text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)] mb-2">Milestone đến hạn</p>
        <div className="space-y-1.5">
          {p.upcoming_milestones.map((mile) => (
            <div key={mile.title} className="flex items-center justify-between text-sm py-1.5 px-3 rounded-sm-custom bg-[var(--bg-app)]">
              <span className="text-[var(--text-primary)] truncate">{mile.title}</span>
              <span className="text-xs text-[var(--text-secondary)] flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" /> {mile.due_date}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
