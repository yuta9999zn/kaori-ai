'use client';

// ============================================================================
// /p2/risks — Risk Register Hub (F-039 BE PR #126 + #140)
// ----------------------------------------------------------------------------
// Wires the per-tenant risk register:
//
//   GET   /api/v1/enterprises/risks?status=&severity=&category=&page=&limit=
//   GET   /api/v1/enterprises/risks/severity-rollup
//   POST  /api/v1/enterprises/risks                            (MANAGER only)
//
// Layout:
//   Header  → 4 KPI tiles (total open / critical / overdue / no owner)
//   Matrix  → 5×5 likelihood × impact heat map (counts)
//   Toolbar → search + status + severity + category filters
//   Table   → clickable rows → /p2/risks/{riskId}
//
// Score + severity are computed by the BE trigger (migration 033). FE just
// renders. Category is the migration 034 follow-up — six buckets matching
// the V3 UI dropdown.
// ============================================================================

import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle, ShieldCheck, Plus, Search, Loader2, ArrowRight,
  ChevronDown, AlertCircle, Sparkles, Calendar, Users as UsersIcon,
  X as XIcon,
} from 'lucide-react';

import {
  Button, Badge, Input, ErrorBanner, SuccessBanner, api, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
// ============================================================================
// Types — mirror BE EnterpriseRiskController.toJson()
// ============================================================================

type Severity = 'low' | 'medium' | 'high' | 'critical';
type Status   = 'open' | 'mitigating' | 'closed';
type Category =
  | 'operational' | 'financial' | 'regulatory'
  | 'reputational' | 'strategic' | 'technical';

interface RiskRow {
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

interface ListResponse {
  data: RiskRow[];
  meta: { total: number; page: number; limit: number };
}

interface RollupResponse {
  data: {
    by_severity: { critical: number; high: number; medium: number; low: number };
    open_total:  number;
  };
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

export default function RisksHubPage() {
  const [risks, setRisks] = useState<RiskRow[]>([]);
  const [rollup, setRollup] = useState<RollupResponse['data'] | null>(null);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | Status>('all');
  const [severityFilter, setSeverityFilter] = useState<'all' | Severity>('all');
  const [categoryFilter, setCategoryFilter] = useState<'all' | Category>('all');

  const [showCreate, setShowCreate] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);

  async function loadAll() {
    setLoading(true);
    setProblem(null);
    try {
      // Pull a generous slice — heat map needs the full set, not just one page.
      const [list, rl] = await Promise.all([
        api<ListResponse>('/api/v1/enterprises/risks?limit=200'),
        api<RollupResponse>('/api/v1/enterprises/risks/severity-rollup'),
      ]);
      setRisks(list.data ?? []);
      setRollup(rl.data ?? null);
    } catch (e) {
      setProblem(e as ProblemDetails);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return risks.filter((r) => {
      if (statusFilter   !== 'all' && r.status   !== statusFilter)   return false;
      if (severityFilter !== 'all' && r.severity !== severityFilter) return false;
      if (categoryFilter !== 'all' && r.category !== categoryFilter) return false;
      if (q && !r.title.toLowerCase().includes(q))                   return false;
      return true;
    });
  }, [risks, search, statusFilter, severityFilter, categoryFilter]);

  const stats = useMemo(() => {
    const today = new Date();
    return {
      total:    rollup?.open_total ?? risks.filter((r) => r.status !== 'closed').length,
      critical: rollup?.by_severity.critical ?? 0,
      overdue:  risks.filter((r) =>
                  r.due_date && new Date(r.due_date) < today && r.status !== 'closed').length,
      no_owner: risks.filter((r) => !r.owner_user_id && r.status !== 'closed').length,
    };
  }, [risks, rollup]);

  return (
    <>
      <PageHeader
        title="Rủi ro"
        description="Risk register theo doanh nghiệp. Score = likelihood × impact, severity tự suy ra."
        actions={
          <>
            <Badge variant="info">F-039</Badge>
            <a href="/p2/risks/export"><Button variant="secondary" size="md">Xuất CSV</Button></a>
            <Button variant="primary" size="md" onClick={() => setShowCreate(true)}>
              <Plus className="w-4 h-4 mr-2" /> Thêm rủi ro
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-6">
        {problem && <ErrorBanner problem={problem} />}
        {success && <SuccessBanner message={success} />}

        {/* KPI tiles */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatTile label="Tổng đang mở"             value={stats.total}    icon={ShieldCheck}    tone="text-[var(--text-primary)]" />
          <StatTile label="Nghiêm trọng (chưa đóng)" value={stats.critical} icon={AlertTriangle}  tone="text-[var(--state-error)]" />
          <StatTile label="Hạn mitigation đã quá"     value={stats.overdue}  icon={Calendar}       tone="text-[var(--state-warning)]" />
          <StatTile label="Chưa có owner"             value={stats.no_owner} icon={UsersIcon}      tone="text-[var(--state-info)]" />
        </div>

        {/* Heat map */}
        <RiskMatrix risks={risks} loading={loading} />

        {/* Toolbar */}
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-3 flex flex-col lg:flex-row items-stretch lg:items-center gap-3 shadow-soft-sm">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Tìm theo tên rủi ro..."
              className="w-full pl-9 pr-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-sm placeholder:text-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all"
            />
          </div>
          <FilterPill
            label="Trạng thái" value={statusFilter} onChange={setStatusFilter}
            options={[
              { value: 'all',        label: 'Tất cả' },
              { value: 'open',       label: 'Mở' },
              { value: 'mitigating', label: 'Đang xử lý' },
              { value: 'closed',     label: 'Đã đóng' },
            ]}
          />
          <FilterPill
            label="Mức" value={severityFilter} onChange={setSeverityFilter}
            options={[
              { value: 'all',      label: 'Tất cả' },
              { value: 'critical', label: 'Nghiêm trọng' },
              { value: 'high',     label: 'Cao' },
              { value: 'medium',   label: 'Trung' },
              { value: 'low',      label: 'Thấp' },
            ]}
          />
          <FilterPill
            label="Danh mục" value={categoryFilter} onChange={setCategoryFilter}
            options={[
              { value: 'all', label: 'Tất cả' },
              ...CATEGORIES.map((c) => ({ value: c, label: CATEGORY_LABEL[c] })),
            ]}
          />
        </div>

        {/* Table */}
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
          <div className="overflow-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-[var(--bg-app)] border-b border-[var(--border-color)] text-[11px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
                <tr>
                  <th className="px-5 py-3">Rủi ro</th>
                  <th className="px-5 py-3">Danh mục</th>
                  <th className="px-5 py-3">Mức độ</th>
                  <th className="px-5 py-3">Trạng thái</th>
                  <th className="px-5 py-3">Tiến độ</th>
                  <th className="px-5 py-3">Hạn xử lý</th>
                  <th className="px-5 py-3 text-right">Xem</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]/60">
                {loading ? (
                  <tr><td colSpan={7} className="px-5 py-16 text-center text-[var(--text-secondary)]">
                    <Loader2 className="w-5 h-5 animate-spin inline mr-2" /> Đang tải...
                  </td></tr>
                ) : filtered.length === 0 ? (
                  <tr><td colSpan={7} className="px-5 py-16 text-center">
                    <ShieldCheck className="w-10 h-10 mx-auto text-[var(--state-success)]/40 mb-3" />
                    <p className="text-sm text-[var(--text-secondary)]">Không có rủi ro nào khớp bộ lọc.</p>
                  </td></tr>
                ) : (
                  filtered.map((r) => <RiskRowItem key={r.risk_id} risk={r} />)
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <Sparkles className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            Severity tự suy ra từ likelihood × impact: ≥15 nghiêm trọng, ≥9 cao, ≥5 trung, còn lại thấp.
            DB trigger ghi sẵn trên mỗi insert/update — FE chỉ render.
          </p>
        </div>
      </div>

      {showCreate && (
        <CreateRiskModal
          onClose={() => setShowCreate(false)}
          onCreated={(title) => {
            setShowCreate(false);
            setSuccess(`Đã thêm rủi ro: ${title}`);
            loadAll();
          }}
        />
      )}
    </>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

function StatTile({
  label, value, icon: Icon, tone,
}: { label: string; value: number; icon: React.ComponentType<{ className?: string }>; tone: string }) {
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

function FilterPill<T extends string>({
  label, value, onChange, options,
}: {
  label: string;
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as T)}
        className="appearance-none h-9 pl-3 pr-9 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-xs font-medium text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 cursor-pointer hover:bg-[var(--bg-card)]"
      >
        {options.map((o) => <option key={o.value} value={o.value}>{label}: {o.label}</option>)}
      </select>
      <ChevronDown className="w-3.5 h-3.5 text-[var(--text-secondary)] absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none" />
    </div>
  );
}

function RiskMatrix({ risks, loading }: { risks: RiskRow[]; loading: boolean }) {
  const cells: Record<string, RiskRow[]> = {};
  for (const r of risks) {
    if (r.status === 'closed') continue;
    const k = `${r.likelihood}_${r.impact}`;
    cells[k] = cells[k] ? [...cells[k], r] : [r];
  }

  function cellTone(likelihood: number, impact: number): string {
    const score = likelihood * impact;
    if (score <= 4)  return 'bg-[var(--state-success)]/15 border-[var(--state-success)]/30';
    if (score <= 8)  return 'bg-[var(--state-info)]/15 border-[var(--state-info)]/30';
    if (score <= 14) return 'bg-[var(--state-warning)]/15 border-[var(--state-warning)]/30';
    return 'bg-[var(--state-error)]/15 border-[var(--state-error)]/30';
  }

  const LABELS = ['Rất thấp', 'Thấp', 'Trung', 'Cao', 'Rất cao'];

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
      <div className="flex items-center gap-2 mb-3">
        <AlertCircle className="w-4 h-4 text-[var(--primary-gold-dark)]" />
        <h3 className="font-serif text-base text-[var(--text-primary)]">Ma trận khả năng × tác động</h3>
        <Badge variant="default">{Object.values(cells).flat().length} rủi ro mở</Badge>
      </div>
      <div className="overflow-x-auto">
        <table className="border-separate border-spacing-1">
          <thead>
            <tr>
              <th className="text-left text-[11px] text-[var(--text-secondary)] uppercase tracking-wider font-medium px-2 py-1">
                Khả năng \ Tác động
              </th>
              {LABELS.map((lbl, i) => (
                <th key={lbl} className="text-[11px] text-[var(--text-secondary)] uppercase tracking-wider font-medium px-2 py-1">
                  {i + 1} · {lbl}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[5, 4, 3, 2, 1].map((likelihood) => (
              <tr key={likelihood}>
                <td className="text-[11px] text-[var(--text-secondary)] uppercase tracking-wider font-medium px-2 py-1 text-right">
                  {likelihood} · {LABELS[likelihood - 1]}
                </td>
                {[1, 2, 3, 4, 5].map((impact) => {
                  const items = cells[`${likelihood}_${impact}`] ?? [];
                  return (
                    <td key={impact} className="p-0">
                      <div className={cn(
                        'min-w-[80px] h-16 rounded-md-custom border flex items-center justify-center transition-all',
                        cellTone(likelihood, impact),
                      )}>
                        {loading ? (
                          <Loader2 className="w-4 h-4 animate-spin text-[var(--text-secondary)]" />
                        ) : (
                          <span className="text-2xl font-serif text-[var(--text-primary)]">
                            {items.length || ''}
                          </span>
                        )}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex items-center gap-3 text-[11px] text-[var(--text-secondary)] flex-wrap">
        {[
          { label: 'Thấp (≤4)',          cls: 'bg-[var(--state-success)]/30' },
          { label: 'Trung (5-8)',        cls: 'bg-[var(--state-info)]/30' },
          { label: 'Cao (9-14)',         cls: 'bg-[var(--state-warning)]/40' },
          { label: 'Nghiêm trọng (≥15)', cls: 'bg-[var(--state-error)]/40' },
        ].map((l) => (
          <span key={l.label} className="inline-flex items-center gap-1.5">
            <span className={cn('w-3 h-3 rounded-sm-custom', l.cls)} />
            {l.label}
          </span>
        ))}
      </div>
    </div>
  );
}

function RiskRowItem({ risk: r }: { risk: RiskRow }) {
  const sev = SEVERITY_META[r.severity];
  const stt = STATUS_META[r.status];
  const isOverdue = r.due_date && new Date(r.due_date) < new Date() && r.status !== 'closed';

  return (
    <tr className="hover:bg-[var(--bg-app)]/40 transition-colors group">
      <td className="px-5 py-4 max-w-md">
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center justify-center w-9 h-9 rounded-md-custom bg-[var(--primary-gold)]/10 shrink-0">
            <AlertTriangle className="w-4 h-4 text-[var(--primary-gold-dark)]" />
          </span>
          <div className="min-w-0">
            <a href={`/p2/risks/${r.risk_id}`} className="text-sm font-medium text-[var(--text-primary)] group-hover:text-[var(--primary-gold-dark)] transition-colors line-clamp-1">
              {r.title}
            </a>
            <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">
              L{r.likelihood} × I{r.impact} = {r.score}
            </p>
          </div>
        </div>
      </td>
      <td className="px-5 py-4 text-xs text-[var(--text-secondary)]">{CATEGORY_LABEL[r.category]}</td>
      <td className="px-5 py-4"><Badge variant={sev.variant}>{sev.label}</Badge></td>
      <td className="px-5 py-4"><Badge variant={stt.variant}>{stt.label}</Badge></td>
      <td className="px-5 py-4 min-w-[120px]">
        <div className="flex items-center gap-2">
          <div className="flex-1 h-1.5 bg-[var(--border-color)]/40 rounded-full overflow-hidden">
            <div className="h-full bg-[var(--primary-gold)]" style={{ width: `${r.mitigation_progress}%` }} />
          </div>
          <span className="text-[11px] font-mono text-[var(--text-secondary)] w-9 text-right">{r.mitigation_progress}%</span>
        </div>
      </td>
      <td className="px-5 py-4">
        {r.due_date ? (
          <span className={cn('text-xs', isOverdue ? 'text-[var(--state-error)] font-medium' : 'text-[var(--text-secondary)]')}>
            {new Date(r.due_date).toLocaleDateString('vi-VN')}
            {isOverdue && ' ⚠️'}
          </span>
        ) : (
          <span className="text-xs text-[var(--text-secondary)]">—</span>
        )}
      </td>
      <td className="px-5 py-4 text-right">
        <a href={`/p2/risks/${r.risk_id}`} className="inline-flex items-center text-xs font-medium text-[var(--primary-gold-dark)] hover:underline">
          Chi tiết <ArrowRight className="w-3 h-3 ml-1" />
        </a>
      </td>
    </tr>
  );
}

// ============================================================================
// Create modal
// ============================================================================

function CreateRiskModal({
  onClose, onCreated,
}: { onClose: () => void; onCreated: (title: string) => void }) {
  const [title, setTitle]                   = useState('');
  const [description, setDescription]       = useState('');
  const [category, setCategory]             = useState<Category>('operational');
  const [likelihood, setLikelihood]         = useState(3);
  const [impact, setImpact]                 = useState(3);
  const [status, setStatus]                 = useState<Status>('open');
  const [mitigationPlan, setMitigationPlan] = useState('');
  const [progress, setProgress]             = useState(0);
  const [dueDate, setDueDate]               = useState('');

  const [submitting, setSubmitting] = useState(false);
  const [problem, setProblem]       = useState<ProblemDetails | null>(null);

  const score = likelihood * impact;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setProblem(null);
    try {
      await api('/api/v1/enterprises/risks', {
        method: 'POST',
        body:   JSON.stringify({
          title,
          description:         description || null,
          category,
          likelihood,
          impact,
          status,
          mitigation_plan:     mitigationPlan || null,
          mitigation_progress: progress,
          due_date:            dueDate || null,
        }),
      });
      onCreated(title);
    } catch (e) {
      setProblem(e as ProblemDetails);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 animate-fade-in">
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border-color)]">
          <h3 className="font-serif text-lg text-[var(--text-primary)]">Thêm rủi ro mới</h3>
          <button onClick={onClose} aria-label="Đóng" className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
            <XIcon className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={onSubmit} className="p-5 space-y-4">
          {problem && <ErrorBanner problem={problem} />}

          <Input
            label="Tên rủi ro *"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Ví dụ: Phụ thuộc vào 1 nhà cung cấp duy nhất"
            required
            maxLength={200}
          />

          <div className="space-y-2">
            <label className="text-sm font-medium text-[var(--text-primary)]">Mô tả</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Mô tả chi tiết hoàn cảnh, nguy cơ..."
              className="w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all resize-none"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-[var(--text-primary)]">Danh mục *</label>
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
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ScoreSlider label="Khả năng (likelihood) *" value={likelihood} onChange={setLikelihood} />
            <ScoreSlider label="Tác động (impact) *"      value={impact}     onChange={setImpact} />
          </div>

          <div className="bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom p-3 flex items-center justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">Score tự tính</p>
              <p className="font-serif text-xl text-[var(--text-primary)]">{likelihood} × {impact} = {score}</p>
            </div>
            <Badge variant={SEVERITY_META[severityFromScore(score)].variant}>
              {SEVERITY_META[severityFromScore(score)].label}
            </Badge>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-[var(--text-primary)]">Kế hoạch xử lý</label>
            <textarea
              value={mitigationPlan}
              onChange={(e) => setMitigationPlan(e.target.value)}
              rows={2}
              placeholder="Bước cụ thể để giảm rủi ro..."
              className="w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all resize-none"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-[var(--text-primary)]">Tiến độ xử lý ({progress}%)</label>
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={progress}
                onChange={(e) => setProgress(Number(e.target.value))}
                className="w-full h-2 bg-[var(--border-color)]/40 rounded-full accent-[var(--primary-gold)]"
              />
            </div>
            <Input
              label="Hạn xử lý"
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
            />
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-[var(--border-color)]">
            <Button variant="tertiary" type="button" onClick={onClose} disabled={submitting}>Huỷ</Button>
            <Button variant="primary" type="submit" isLoading={submitting} disabled={!title.trim()}>
              <Plus className="w-4 h-4 mr-2" /> Tạo rủi ro
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

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
