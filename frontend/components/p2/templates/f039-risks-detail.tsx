'use client';

// ============================================================================
// /p2/risks/[riskId] — Risk Detail (F-039 BE PR #126 + #140)
// ----------------------------------------------------------------------------
// Wires:
//   GET    /api/v1/enterprises/risks/{riskId}
//   PATCH  /api/v1/enterprises/risks/{riskId}     (MANAGER only)
//   DELETE /api/v1/enterprises/risks/{riskId}     (MANAGER only — soft delete)
//
// Single-tab layout (Tổng quan & Mitigation). The 3-tab template version
// (Evidence + History + multi-step Mitigation) is intentionally deferred —
// BE only stores `mitigation_plan` text + `mitigation_progress` int + 1
// `due_date`, not a steps array, evidence list, or review history. Those
// are flagged as v1 follow-ups in the F-039 BE commit message.
// ============================================================================

import React, { useEffect, useState } from 'react';
import {
  AlertTriangle, ArrowLeft, Save, Trash2, ShieldCheck, Loader2,
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
type Category =
  | 'operational' | 'financial' | 'regulatory'
  | 'reputational' | 'strategic' | 'technical';

interface RiskDetail {
  risk_id:             string;
  title:               string;
  description:         string | null;
  category:            Category;
  likelihood:          number;
  impact:              number;
  score:               number;
  severity:            Severity;
  status:              Status;
  mitigation_plan:     string | null;
  mitigation_progress: number;
  owner_user_id:       string | null;
  due_date:            string | null;
  source:              'manual' | 'auto';
  created_by_user:     string | null;
  created_at:          string;
  updated_at:          string;
}

const SEVERITY_META: Record<Severity, { label: string; variant: 'success' | 'info' | 'warning' | 'error' }> = {
  low:      { label: 'Thấp',         variant: 'success' },
  medium:   { label: 'Trung',        variant: 'info' },
  high:     { label: 'Cao',          variant: 'warning' },
  critical: { label: 'Nghiêm trọng', variant: 'error' },
};

const STATUS_META: Record<Status, { label: string; variant: 'current' | 'warning' | 'success' }> = {
  open:       { label: 'Mở',         variant: 'current' },
  mitigating: { label: 'Đang xử lý', variant: 'warning' },
  closed:     { label: 'Đã đóng',    variant: 'success' },
};

const CATEGORY_LABEL: Record<Category, string> = {
  operational:  'Vận hành',
  financial:    'Tài chính',
  regulatory:   'Pháp lý',
  reputational: 'Thương hiệu',
  strategic:    'Chiến lược',
  technical:    'Kỹ thuật',
};

const CATEGORIES: Category[] = [
  'operational', 'financial', 'regulatory',
  'reputational', 'strategic', 'technical',
];

// ============================================================================
// Page
// ============================================================================

export default function RiskDetailPage({ riskId }: { riskId: string }) {
  const [risk, setRisk]             = useState<RiskDetail | null>(null);
  const [loading, setLoading]       = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting]     = useState(false);
  const [problem, setProblem]       = useState<ProblemDetails | null>(null);
  const [success, setSuccess]       = useState<string | null>(null);

  // Form state — diverges from `risk` while user edits, snaps back on save.
  const [title, setTitle]                   = useState('');
  const [description, setDescription]       = useState('');
  const [category, setCategory]             = useState<Category>('operational');
  const [likelihood, setLikelihood]         = useState(3);
  const [impact, setImpact]                 = useState(3);
  const [status, setStatus]                 = useState<Status>('open');
  const [mitigationPlan, setMitigationPlan] = useState('');
  const [progress, setProgress]             = useState(0);
  const [ownerUserId, setOwnerUserId]       = useState('');
  const [dueDate, setDueDate]               = useState('');

  function hydrate(r: RiskDetail) {
    setRisk(r);
    setTitle(r.title);
    setDescription(r.description ?? '');
    setCategory(r.category);
    setLikelihood(r.likelihood);
    setImpact(r.impact);
    setStatus(r.status);
    setMitigationPlan(r.mitigation_plan ?? '');
    setProgress(r.mitigation_progress);
    setOwnerUserId(r.owner_user_id ?? '');
    setDueDate(r.due_date ?? '');
  }

  async function load() {
    setLoading(true);
    setProblem(null);
    try {
      const r = await api<{ data: RiskDetail }>(`/api/v1/enterprises/risks/${riskId}`);
      hydrate(r.data);
    } catch (e) {
      setProblem(e as ProblemDetails);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [riskId]);

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setProblem(null);
    setSuccess(null);
    try {
      const r = await api<{ data: RiskDetail }>(`/api/v1/enterprises/risks/${riskId}`, {
        method: 'PATCH',
        body:   JSON.stringify({
          title,
          description:         description || null,
          category,
          likelihood,
          impact,
          status,
          mitigation_plan:     mitigationPlan || null,
          mitigation_progress: progress,
          owner_user_id:       ownerUserId || null,
          due_date:            dueDate      || null,
        }),
      });
      hydrate(r.data);
      setSuccess('Đã lưu thay đổi.');
    } catch (e) {
      setProblem(e as ProblemDetails);
    } finally {
      setSubmitting(false);
    }
  }

  async function onDelete() {
    if (!risk) return;
    if (!window.confirm(
      `Xoá rủi ro "${risk.title}"? Bản ghi sẽ bị soft-delete (vẫn còn trong audit), `
      + 'không hiển thị trong danh sách nữa.'
    )) return;
    setDeleting(true);
    setProblem(null);
    try {
      await api(`/api/v1/enterprises/risks/${riskId}`, { method: 'DELETE' });
      window.location.href = '/p2/risks';
    } catch (e) {
      setProblem(e as ProblemDetails);
      setDeleting(false);
    }
  }

  if (loading || !risk) {
    return (
      <>
        <PageHeader title="Đang tải..." description="" />
        <div className="px-6 py-12 max-w-[1300px] mx-auto">
          {problem ? (
            <ErrorBanner problem={problem} />
          ) : (
            <div className="flex items-center justify-center py-16 text-[var(--text-secondary)]">
              <Loader2 className="w-5 h-5 animate-spin mr-2" /> Đang tải chi tiết rủi ro...
            </div>
          )}
        </div>
      </>
    );
  }

  const score = likelihood * impact;
  const sev = SEVERITY_META[severityFromScore(score)];
  const stt = STATUS_META[status];

  return (
    <>
      <PageHeader
        title={risk.title}
        description={`Risk ID: ${risk.risk_id} · ${CATEGORY_LABEL[risk.category]} · Cập nhật ${new Date(risk.updated_at).toLocaleString('vi-VN')}`}
        actions={
          <>
            <Badge variant={sev.variant}>{sev.label}</Badge>
            <Badge variant={stt.variant}>{stt.label}</Badge>
            <a href="/p2/risks">
              <Button variant="tertiary" size="md"><ArrowLeft className="w-4 h-4 mr-2" /> Danh sách</Button>
            </a>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-4">
        {problem && <ErrorBanner problem={problem} />}
        {success && <SuccessBanner message={success} />}

        <form onSubmit={onSave} className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 lg:p-6 shadow-soft-sm space-y-5">
          <Input
            label="Tên rủi ro"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            maxLength={200}
          />

          <div className="space-y-2">
            <label className="text-sm font-medium text-[var(--text-primary)]">Mô tả</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              placeholder="Mô tả hoàn cảnh, nguy cơ, tác động dự kiến..."
              className="w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all resize-none leading-relaxed"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-[var(--text-primary)]">Danh mục</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value as Category)}
                className="w-full h-10 px-3 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)]"
              >
                {CATEGORIES.map((c) => <option key={c} value={c}>{CATEGORY_LABEL[c]}</option>)}
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-[var(--text-primary)]">Trạng thái</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as Status)}
                className="w-full h-10 px-3 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)]"
              >
                <option value="open">Mở</option>
                <option value="mitigating">Đang xử lý</option>
                <option value="closed">Đã đóng</option>
              </select>
            </div>
            <Input
              label="Hạn xử lý"
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ScoreSlider label="Khả năng (likelihood)" value={likelihood} onChange={setLikelihood} />
            <ScoreSlider label="Tác động (impact)"      value={impact}     onChange={setImpact} />
          </div>

          <div className="bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom p-4 flex items-center justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">Score tự tính</p>
              <p className="font-serif text-2xl text-[var(--text-primary)]">{likelihood} × {impact} = {score}</p>
              <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">DB trigger sẽ ghi lại khi lưu.</p>
            </div>
            <Badge variant={sev.variant}>Score {score} · {sev.label}</Badge>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-[var(--text-primary)]">Kế hoạch xử lý</label>
            <textarea
              value={mitigationPlan}
              onChange={(e) => setMitigationPlan(e.target.value)}
              rows={3}
              placeholder="Bước cụ thể để giảm rủi ro, người chịu trách nhiệm, dependencies..."
              className="w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all resize-none leading-relaxed"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-[var(--text-primary)]">
                Tiến độ xử lý ({progress}%)
              </label>
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={progress}
                onChange={(e) => setProgress(Number(e.target.value))}
                className="w-full h-2 bg-[var(--border-color)]/40 rounded-full accent-[var(--primary-gold)]"
              />
              <div className="flex items-center gap-2">
                <div className="flex-1 h-1.5 bg-[var(--border-color)]/40 rounded-full overflow-hidden">
                  <div className="h-full bg-[var(--primary-gold)]" style={{ width: `${progress}%` }} />
                </div>
              </div>
            </div>
            <Input
              label="Owner (UUID enterprise_users)"
              value={ownerUserId}
              onChange={(e) => setOwnerUserId(e.target.value)}
              placeholder="00000000-0000-0000-0000-000000000000"
            />
          </div>

          <div className="flex items-center justify-between gap-2 pt-3 border-t border-[var(--border-color)]">
            <Button
              variant="tertiary" type="button" size="md"
              onClick={onDelete} disabled={deleting || submitting}
              className="text-[var(--state-error)] hover:bg-[var(--state-error)]/10"
            >
              {deleting ? (
                <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Đang xoá...</>
              ) : (
                <><Trash2 className="w-4 h-4 mr-2" /> Xoá (soft)</>
              )}
            </Button>
            <Button variant="primary" type="submit" size="md" isLoading={submitting} disabled={!title.trim()}>
              <Save className="w-4 h-4 mr-2" /> Lưu thay đổi
            </Button>
          </div>
        </form>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p>
              Score + severity tự suy ra từ likelihood × impact bởi DB trigger.
              Mỗi update bump <span className="font-mono">updated_at</span>; soft-delete chỉ set{' '}
              <span className="font-mono">deleted_at</span> (audit trail bảo toàn).
            </p>
            <p>
              <span className="text-[var(--text-secondary)]/70">
                Phase 2 v1 sẽ thêm: evidence attachments, lịch sử review (likelihood/impact change), tự động đề xuất từ pipeline anomaly.
              </span>
            </p>
          </div>
        </div>
      </div>
    </>
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

function severityFromScore(score: number): Severity {
  if (score >= 15) return 'critical';
  if (score >=  9) return 'high';
  if (score >=  5) return 'medium';
  return 'low';
}
