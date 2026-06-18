// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 57. /p2/risks/[id] — Risk Detail (F-055 🔵 Phase 2)
// ----------------------------------------------------------------------------
// Drill-down 1 risk:
//   - Header: title + severity badge + status + likelihood/impact pill.
//   - Tab "Tổng quan": description, owner, related insight/decision.
//   - Tab "Mitigation plan": list step + due date + responsible.
//   - Tab "Bằng chứng" (evidence): file/link/insight ref.
//   - Tab "Lịch sử": timeline review (likelihood/impact change theo thời gian).
//
// Wire (Phase 2): `GET /api/v1/risks/{id}`, `PATCH /api/v1/risks/{id}`,
// `POST /api/v1/risks/{id}/mitigations`, `POST .../evidence`. Audit K-6.
// ============================================================================

import React, { useState } from 'react';
import {
  AlertTriangle, ArrowLeft, Save, Trash2, ShieldCheck, FileText,
  ListChecks, History, Paperclip, Link2, Lightbulb, Calendar,
  Plus, CheckCircle2, Clock, ExternalLink, User as UserIcon,
} from 'lucide-react';

import {
  Button, Badge, Input, ErrorBanner, SuccessBanner, api, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
// ============================================================================
// Types
// ============================================================================

type Severity = 'low' | 'medium' | 'high' | 'critical';
type Status   = 'open' | 'mitigating' | 'closed';

interface MitigationStep {
  id:           string;
  title:        string;
  due_date:     string;
  responsible:  string;
  done:         boolean;
}

interface Evidence {
  id:    string;
  kind:  'insight' | 'document' | 'link';
  title: string;
  ref:   string;
  added_at: string;
}

interface ReviewEntry {
  id:           string;
  reviewed_at:  string;
  reviewer:     string;
  likelihood:   number;
  impact:       number;
  note:         string;
}

interface RiskDetail {
  id:           string;
  title:        string;
  description:  string;
  category:     string;
  severity:     Severity;
  status:       Status;
  likelihood:   1 | 2 | 3 | 4 | 5;
  impact:       1 | 2 | 3 | 4 | 5;
  owner:        string;
  mitigation:   MitigationStep[];
  evidence:     Evidence[];
  reviews:      ReviewEntry[];
}

const MOCK: RiskDetail = {
  id:           'rsk_001',
  title:        'Phụ thuộc 1 nhà cung cấp Ollama GPU duy nhất',
  description:  'Toàn bộ inference Qwen 2.5 chạy trên 1 instance Ollama. Nếu instance này lỗi >2h, mọi pipeline mới sẽ bị block — không có failover sang external AI vì policy K-3/K-4 chưa được consent.',
  category:     'Kỹ thuật',
  severity:     'critical',
  status:       'open',
  likelihood:   3,
  impact:       5,
  owner:        'huy@acme.vn',
  mitigation: [
    { id: 'mt_1', title: 'Triển khai Ollama instance phụ ở vùng khác',         due_date: '2026-05-15', responsible: 'huy@acme.vn',  done: true  },
    { id: 'mt_2', title: 'Cấu hình HAProxy failover tự động',                  due_date: '2026-05-20', responsible: 'huy@acme.vn',  done: false },
    { id: 'mt_3', title: 'Đề xuất ban GĐ phê duyệt consent_external dự phòng', due_date: '2026-06-01', responsible: 'minh@acme.vn', done: false },
    { id: 'mt_4', title: 'Drill incident lần đầu',                              due_date: '2026-06-05', responsible: 'lan@acme.vn',  done: false },
  ],
  evidence: [
    { id: 'ev_1', kind: 'insight',  title: 'Insight #ins_42 — Latency Ollama tăng vọt 28/04',           ref: 'ins_42',                            added_at: '2026-04-28T15:00:00+07:00' },
    { id: 'ev_2', kind: 'document', title: 'Báo cáo audit hạ tầng Q1 2026',                              ref: 'doc_q1_infra_2026.pdf',             added_at: '2026-04-15T10:00:00+07:00' },
    { id: 'ev_3', kind: 'link',     title: 'Ollama upstream issue tracker',                              ref: 'https://github.com/ollama/ollama', added_at: '2026-04-10T14:00:00+07:00' },
  ],
  reviews: [
    { id: 'rv_1', reviewed_at: '2026-04-25T10:00:00+07:00', reviewer: 'lan@acme.vn',  likelihood: 3, impact: 5, note: 'Tăng impact từ 4 lên 5 sau insight latency.' },
    { id: 'rv_2', reviewed_at: '2026-04-10T14:00:00+07:00', reviewer: 'huy@acme.vn',  likelihood: 3, impact: 4, note: 'Tạo mới sau audit Q1.' },
  ],
};

const SEVERITY_META: Record<Severity, { label: string; variant: 'success' | 'info' | 'warning' | 'error' }> = {
  low:      { label: 'Thấp',         variant: 'success' },
  medium:   { label: 'Trung',        variant: 'info' },
  high:     { label: 'Cao',          variant: 'warning' },
  critical: { label: 'Nghiêm trọng', variant: 'error' },
};

const STATUS_META: Record<Status, { label: string; variant: 'current' | 'warning' | 'success' }> = {
  open:       { label: 'Mở',         variant: 'current' },
  mitigating: { label: 'Đang xử lý',  variant: 'warning' },
  closed:     { label: 'Đã đóng',     variant: 'success' },
};

// ============================================================================
// Page
// ============================================================================

type Tab = 'overview' | 'mitigation' | 'evidence' | 'history';

export default function RiskDetailPage() {
  const [risk, setRisk] = useState<RiskDetail>(MOCK);
  const [tab, setTab] = useState<Tab>('overview');
  const [submitting, setSubmitting] = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  function patch(p: Partial<RiskDetail>) {
    setRisk((prev) => ({ ...prev, ...p }));
  }

  function toggleStep(id: string) {
    setRisk((prev) => ({
      ...prev,
      mitigation: prev.mitigation.map((s) => s.id === id ? { ...s, done: !s.done } : s),
    }));
  }

  async function onSave() {
    setSubmitting(true);
    setProblem(null);
    setSuccess(null);
    try {
      await api(`/api/v1/risks/${risk.id}`, {
        method: 'PATCH',
        body: JSON.stringify(risk),
      });
      setSuccess('Đã lưu thay đổi.');
    } catch (e: any) {
      setProblem(e);
    } finally {
      setSubmitting(false);
    }
  }

  const sev = SEVERITY_META[risk.severity];
  const stt = STATUS_META[risk.status];
  const score = risk.likelihood * risk.impact;
  const mitigationDone = risk.mitigation.filter((s) => s.done).length;

  return (
    <>
      <PageHeader
        title={risk.title}
        description={`Risk ID: ${risk.id} · ${risk.category} · score L${risk.likelihood}×I${risk.impact} = ${score}`}
        actions={
          <>
            <Badge variant={sev.variant}>{sev.label}</Badge>
            <Badge variant={stt.variant}>{stt.label}</Badge>
            <a href="/p2/risks"><Button variant="tertiary" size="md"><ArrowLeft className="w-4 h-4 mr-2" /> Danh sách</Button></a>
            <Button variant="primary" size="md" onClick={onSave} isLoading={submitting}>
              <Save className="w-4 h-4 mr-2" /> Lưu
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1300px] mx-auto space-y-4">
        {problem && <ErrorBanner problem={problem} />}
        {success && <SuccessBanner message={success} />}

        {/* Tabs */}
        <div className="flex items-center gap-1 border-b border-[var(--border-color)]">
          {[
            { value: 'overview' as Tab,   label: 'Tổng quan',         icon: FileText,    badge: null },
            { value: 'mitigation' as Tab, label: 'Mitigation plan',   icon: ListChecks,  badge: `${mitigationDone}/${risk.mitigation.length}` },
            { value: 'evidence' as Tab,   label: 'Bằng chứng',         icon: Paperclip,   badge: risk.evidence.length.toString() },
            { value: 'history' as Tab,    label: 'Lịch sử review',     icon: History,     badge: risk.reviews.length.toString() },
          ].map((t) => {
            const Icon = t.icon;
            const active = tab === t.value;
            return (
              <button
                key={t.value}
                onClick={() => setTab(t.value)}
                className={cn(
                  'flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors',
                  active
                    ? 'border-[var(--primary-gold)] text-[var(--text-primary)]'
                    : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
                )}
              >
                <Icon className="w-4 h-4" />
                {t.label}
                {t.badge && <Badge variant="default">{t.badge}</Badge>}
              </button>
            );
          })}
        </div>

        {/* Tab content */}
        {tab === 'overview'   && <OverviewTab risk={risk} onPatch={patch} />}
        {tab === 'mitigation' && <MitigationTab risk={risk} onToggleStep={toggleStep} />}
        {tab === 'evidence'   && <EvidenceTab risk={risk} />}
        {tab === 'history'    && <HistoryTab risk={risk} />}

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            Mỗi review (thay đổi likelihood/impact) ghi vào lịch sử + <span className="font-mono">decision_audit_log</span> (K-6).
            Severity tự suy ra từ score; chỉ status/owner/mitigation cần edit thủ công.
          </p>
        </div>
      </div>
    </>
  );
}

// ============================================================================
// Tabs
// ============================================================================

function OverviewTab({
  risk, onPatch,
}: { risk: RiskDetail; onPatch: (p: Partial<RiskDetail>) => void }) {
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 lg:p-6 shadow-soft-sm space-y-5">
      <div>
        <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] mb-2">Mô tả rủi ro</p>
        <textarea
          value={risk.description}
          onChange={(e) => onPatch({ description: e.target.value })}
          rows={4}
          className="w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all resize-none leading-relaxed"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Input label="Owner" value={risk.owner} onChange={(e) => onPatch({ owner: e.target.value })} placeholder="email@workspace.vn" />
        <div className="space-y-2">
          <label className="text-sm font-medium text-[var(--text-primary)]">Trạng thái</label>
          <select
            value={risk.status}
            onChange={(e) => onPatch({ status: e.target.value as Status })}
            className="w-full h-10 px-3 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)]"
          >
            <option value="open">Mở</option>
            <option value="mitigating">Đang xử lý</option>
            <option value="closed">Đã đóng</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <ScoreSlider label="Khả năng (likelihood)" value={risk.likelihood} onChange={(v) => onPatch({ likelihood: v as 1 | 2 | 3 | 4 | 5 })} />
        <ScoreSlider label="Tác động (impact)" value={risk.impact} onChange={(v) => onPatch({ impact: v as 1 | 2 | 3 | 4 | 5 })} />
      </div>

      <div className="bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom p-4 flex items-center justify-between">
        <div>
          <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">Score tự tính</p>
          <p className="font-serif text-2xl text-[var(--text-primary)]">{risk.likelihood} × {risk.impact} = {risk.likelihood * risk.impact}</p>
        </div>
        <ScorePill score={risk.likelihood * risk.impact} />
      </div>
    </div>
  );
}

function MitigationTab({
  risk, onToggleStep,
}: { risk: RiskDetail; onToggleStep: (id: string) => void }) {
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm font-medium text-[var(--text-primary)] flex items-center gap-2">
          <ListChecks className="w-4 h-4 text-[var(--primary-gold-dark)]" /> Các bước xử lý
        </p>
        <Button variant="primary" size="sm">
          <Plus className="w-3.5 h-3.5 mr-1.5" /> Thêm bước
        </Button>
      </div>
      <ul className="space-y-2">
        {risk.mitigation.map((s, i) => (
          <li
            key={s.id}
            className={cn(
              'flex items-start gap-3 p-3 rounded-md-custom border transition-colors',
              s.done
                ? 'border-[var(--state-success)]/30 bg-[var(--state-success)]/5'
                : 'border-[var(--border-color)] bg-[var(--bg-app)]/40',
            )}
          >
            <button
              onClick={() => onToggleStep(s.id)}
              className={cn(
                'w-5 h-5 rounded-sm-custom border flex items-center justify-center shrink-0 mt-0.5 transition-colors',
                s.done
                  ? 'bg-[var(--state-success)] border-[var(--state-success)]'
                  : 'border-[var(--border-color)] hover:border-[var(--primary-gold)]',
              )}
              aria-label={s.done ? 'Đã làm xong' : 'Đánh dấu xong'}
            >
              {s.done && <CheckCircle2 className="w-4 h-4 text-white" />}
            </button>
            <div className="flex-1 min-w-0">
              <p className={cn('text-sm font-medium', s.done ? 'text-[var(--text-secondary)] line-through' : 'text-[var(--text-primary)]')}>
                Bước {i + 1}: {s.title}
              </p>
              <div className="flex items-center gap-3 mt-1 text-[11px] text-[var(--text-secondary)]">
                <span className="inline-flex items-center gap-1"><Calendar className="w-3 h-3" /> {new Date(s.due_date).toLocaleDateString('vi-VN')}</span>
                <span className="inline-flex items-center gap-1"><UserIcon className="w-3 h-3" /> {s.responsible}</span>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function EvidenceTab({ risk }: { risk: RiskDetail }) {
  const KIND_META = {
    insight:  { label: 'Insight',     icon: Lightbulb,   href: (ref: string) => `/p2/insights/${ref}` },
    document: { label: 'Tài liệu',    icon: FileText,    href: (ref: string) => `#` },
    link:     { label: 'Liên kết',    icon: Link2,       href: (ref: string) => ref },
  };
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm font-medium text-[var(--text-primary)] flex items-center gap-2">
          <Paperclip className="w-4 h-4 text-[var(--primary-gold-dark)]" /> Bằng chứng ({risk.evidence.length})
        </p>
        <Button variant="primary" size="sm">
          <Plus className="w-3.5 h-3.5 mr-1.5" /> Thêm
        </Button>
      </div>
      <ul className="space-y-2">
        {risk.evidence.map((e) => {
          const meta = KIND_META[e.kind];
          const Icon = meta.icon;
          return (
            <li key={e.id} className="flex items-start gap-3 p-3 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-app)]/40">
              <Icon className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <a href={meta.href(e.ref)} className="text-sm font-medium text-[var(--text-primary)] hover:text-[var(--primary-gold-dark)] transition-colors line-clamp-1">
                  {e.title}
                </a>
                <p className="text-[11px] text-[var(--text-secondary)] mt-0.5 font-mono break-all">{e.ref}</p>
                <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">
                  Thêm: {new Date(e.added_at).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
                </p>
              </div>
              {e.kind === 'link' && <ExternalLink className="w-3.5 h-3.5 text-[var(--text-secondary)] mt-1" />}
              <button title="Xoá" className="p-1 text-[var(--text-secondary)] hover:text-[var(--state-error)]">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function HistoryTab({ risk }: { risk: RiskDetail }) {
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
      <p className="text-sm font-medium text-[var(--text-primary)] flex items-center gap-2 mb-4">
        <History className="w-4 h-4 text-[var(--primary-gold-dark)]" /> Lịch sử review ({risk.reviews.length})
      </p>
      <ol className="relative border-l-2 border-[var(--border-color)] ml-3 space-y-4">
        {risk.reviews.map((rv) => (
          <li key={rv.id} className="ml-6 relative">
            <span className="absolute -left-9 top-0 w-7 h-7 rounded-full bg-[var(--bg-card)] border-2 border-[var(--border-color)] flex items-center justify-center">
              <Clock className="w-3.5 h-3.5 text-[var(--primary-gold-dark)]" />
            </span>
            <div className="flex items-baseline justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-[var(--text-primary)]">
                  L{rv.likelihood} × I{rv.impact} = {rv.likelihood * rv.impact}
                </p>
                <p className="text-[11px] text-[var(--text-secondary)]">Bởi {rv.reviewer}</p>
              </div>
              <span className="text-[11px] text-[var(--text-secondary)] shrink-0">
                {new Date(rv.reviewed_at).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
            <p className="text-xs text-[var(--text-primary)] mt-2 leading-relaxed">{rv.note}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}

// ============================================================================
// Helpers
// ============================================================================

function ScoreSlider({
  label, value, onChange,
}: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-[var(--text-primary)]">{label}</label>
        <span className="text-sm font-mono text-[var(--text-primary)]">{value}/5</span>
      </div>
      <input
        type="range"
        min={1}
        max={5}
        step={1}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-2 bg-[var(--border-color)]/40 rounded-full accent-[var(--primary-gold)]"
      />
      <div className="flex justify-between text-[10px] text-[var(--text-secondary)]">
        {['Rất thấp', 'Thấp', 'Trung', 'Cao', 'Rất cao'].map((l) => <span key={l}>{l}</span>)}
      </div>
    </div>
  );
}

function ScorePill({ score }: { score: number }) {
  if (score <= 4)  return <Badge variant="success">Score {score} · Thấp</Badge>;
  if (score <= 9)  return <Badge variant="info">Score {score} · Trung</Badge>;
  if (score <= 15) return <Badge variant="warning">Score {score} · Cao</Badge>;
  return <Badge variant="error">Score {score} · Nghiêm trọng</Badge>;
}
