// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 56. /p2/risks — Risks Hub (F-055 🔵 Phase 2)
// ----------------------------------------------------------------------------
// Risk register doanh nghiệp:
//   - Matrix 5×5 (likelihood × impact) với hot spot count.
//   - 4 KPI tile (tổng / critical / overdue mitigation / không có owner).
//   - Bảng list risk với filter status (open/mitigating/closed) + severity
//     (low/medium/high/critical) + category (operational/financial/regulatory/
//     reputational/strategic/technical).
//   - Click row → file 57 detail.
//
// Wire (Phase 2): `GET /api/v1/risks?status=...`. K-6: mọi update ghi audit.
// ============================================================================

import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle, ShieldCheck, Plus, Search, Loader2, ArrowRight,
  ChevronDown, AlertCircle, Sparkles, Calendar, Users as UsersIcon,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, api, cn, type ProblemDetails,
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

interface RiskRow {
  id:           string;
  title:        string;
  category:     Category;
  likelihood:   1 | 2 | 3 | 4 | 5;  // very low → very high
  impact:       1 | 2 | 3 | 4 | 5;
  severity:     Severity;
  status:       Status;
  owner:        string | null;
  mitigation_due?: string | null;
  last_reviewed_at: string;
}

const SEVERITY_META: Record<Severity, { label: string; variant: 'success' | 'info' | 'warning' | 'error' }> = {
  low:      { label: 'Thấp',    variant: 'success' },
  medium:   { label: 'Trung',   variant: 'info' },
  high:     { label: 'Cao',     variant: 'warning' },
  critical: { label: 'Nghiêm trọng', variant: 'error' },
};

const STATUS_META: Record<Status, { label: string; variant: 'current' | 'warning' | 'success' }> = {
  open:       { label: 'Mở',         variant: 'current' },
  mitigating: { label: 'Đang xử lý',  variant: 'warning' },
  closed:     { label: 'Đã đóng',     variant: 'success' },
};

const CATEGORY_LABEL: Record<Category, string> = {
  operational:  'Vận hành',
  financial:    'Tài chính',
  regulatory:   'Pháp lý',
  reputational: 'Thương hiệu',
  strategic:    'Chiến lược',
  technical:    'Kỹ thuật',
};

const MOCK_RISKS: RiskRow[] = [
  { id: 'rsk_001', title: 'Phụ thuộc 1 nhà cung cấp Ollama GPU duy nhất',  category: 'technical',    likelihood: 3, impact: 5, severity: 'critical', status: 'open',       owner: 'huy@acme.vn',  mitigation_due: '2026-05-20', last_reviewed_at: '2026-04-25T10:00:00+07:00' },
  { id: 'rsk_002', title: 'Compliance GDPR cho data EU customer',          category: 'regulatory',   likelihood: 4, impact: 5, severity: 'critical', status: 'mitigating', owner: 'lan@acme.vn',  mitigation_due: '2026-06-01', last_reviewed_at: '2026-04-28T15:00:00+07:00' },
  { id: 'rsk_003', title: 'Churn key-account >5 tỷ/năm',                    category: 'financial',    likelihood: 2, impact: 5, severity: 'high',     status: 'mitigating', owner: 'minh@acme.vn', mitigation_due: '2026-05-15', last_reviewed_at: '2026-04-30T09:00:00+07:00' },
  { id: 'rsk_004', title: 'Nhân sự lead ML rời công ty',                    category: 'operational',  likelihood: 2, impact: 4, severity: 'high',     status: 'open',       owner: null,           mitigation_due: null,        last_reviewed_at: '2026-04-10T14:00:00+07:00' },
  { id: 'rsk_005', title: 'Lộ insight nội bộ qua AI ngoài (PII leak)',     category: 'reputational', likelihood: 2, impact: 5, severity: 'high',     status: 'mitigating', owner: 'lan@acme.vn',  mitigation_due: '2026-05-10', last_reviewed_at: '2026-04-29T11:00:00+07:00' },
  { id: 'rsk_006', title: 'Đối thủ ra sản phẩm AI giá rẻ',                  category: 'strategic',    likelihood: 4, impact: 3, severity: 'medium',   status: 'open',       owner: 'minh@acme.vn', mitigation_due: '2026-07-01', last_reviewed_at: '2026-04-20T10:00:00+07:00' },
  { id: 'rsk_007', title: 'Dataset Bronze hỏng do disk full',                category: 'technical',    likelihood: 2, impact: 3, severity: 'medium',   status: 'mitigating', owner: 'huy@acme.vn',  mitigation_due: '2026-05-05', last_reviewed_at: '2026-04-29T08:00:00+07:00' },
  { id: 'rsk_008', title: 'Pipeline daily job overlap',                      category: 'operational',  likelihood: 3, impact: 2, severity: 'medium',   status: 'closed',     owner: 'huy@acme.vn',  mitigation_due: null,        last_reviewed_at: '2026-04-15T10:00:00+07:00' },
  { id: 'rsk_009', title: 'Customer feedback negative trên social',          category: 'reputational', likelihood: 3, impact: 2, severity: 'low',      status: 'open',       owner: null,           mitigation_due: null,        last_reviewed_at: '2026-04-22T14:00:00+07:00' },
  { id: 'rsk_010', title: 'Quy định thuế mới ảnh hưởng pricing',             category: 'regulatory',   likelihood: 2, impact: 2, severity: 'low',      status: 'open',       owner: 'lan@acme.vn',  mitigation_due: '2026-08-01', last_reviewed_at: '2026-04-18T09:00:00+07:00' },
];

// ============================================================================
// Page
// ============================================================================

export default function RisksHubPage() {
  const [risks, setRisks] = useState<RiskRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | Status>('all');
  const [severityFilter, setSeverityFilter] = useState<'all' | Severity>('all');
  const [categoryFilter, setCategoryFilter] = useState<'all' | Category>('all');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await api<{ items: RiskRow[] }>('/api/v1/risks?limit=500');
        if (!cancelled) setRisks(data.items ?? []);
      } catch (e: any) {
        if (!cancelled) {
          setProblem(e);
          setRisks(MOCK_RISKS);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return risks.filter((r) => {
      if (statusFilter !== 'all' && r.status !== statusFilter) return false;
      if (severityFilter !== 'all' && r.severity !== severityFilter) return false;
      if (categoryFilter !== 'all' && r.category !== categoryFilter) return false;
      if (q && !r.title.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [risks, search, statusFilter, severityFilter, categoryFilter]);

  const stats = useMemo(() => {
    const today = new Date();
    return {
      total:     risks.length,
      critical:  risks.filter((r) => r.severity === 'critical' && r.status !== 'closed').length,
      overdue:   risks.filter((r) => r.mitigation_due && new Date(r.mitigation_due) < today && r.status !== 'closed').length,
      no_owner:  risks.filter((r) => !r.owner).length,
    };
  }, [risks]);

  return (
    <>
      <PageHeader
        title="Rủi ro"
        description="Risk register theo ngành. Matrix likelihood × impact giúp ưu tiên xử lý."
        actions={
          <>
            <Badge variant="info">Phase 2 · F-055</Badge>
            <a href="/p2/risks/export"><Button variant="secondary" size="md">Xuất register</Button></a>
            <Button variant="primary" size="md"><Plus className="w-4 h-4 mr-2" /> Thêm rủi ro</Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-6">
        {problem && (
          <ErrorBanner
            problem={{
              ...problem,
              title:  'Đang dùng dữ liệu mẫu',
              detail: `${problem.title}${problem.detail ? ' — ' + problem.detail : ''}. Hiển thị fixture cho tới khi /api/v1/risks sẵn sàng.`,
            }}
          />
        )}

        {/* KPI tiles */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatTile label="Tổng số" value={stats.total} icon={ShieldCheck} tone="text-[var(--text-primary)]" />
          <StatTile label="Nghiêm trọng (chưa đóng)" value={stats.critical} icon={AlertTriangle} tone="text-[var(--state-error)]" />
          <StatTile label="Mitigation quá hạn" value={stats.overdue} icon={Calendar} tone="text-[var(--state-warning)]" />
          <StatTile label="Chưa có owner" value={stats.no_owner} icon={UsersIcon} tone="text-[var(--state-info)]" />
        </div>

        {/* Matrix */}
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
          <FilterPill label="Trạng thái" value={statusFilter} onChange={setStatusFilter} options={[
            { value: 'all',        label: 'Tất cả' },
            { value: 'open',       label: 'Mở' },
            { value: 'mitigating', label: 'Đang xử lý' },
            { value: 'closed',     label: 'Đã đóng' },
          ]} />
          <FilterPill label="Mức" value={severityFilter} onChange={setSeverityFilter} options={[
            { value: 'all',      label: 'Tất cả' },
            { value: 'critical', label: 'Nghiêm trọng' },
            { value: 'high',     label: 'Cao' },
            { value: 'medium',   label: 'Trung' },
            { value: 'low',      label: 'Thấp' },
          ]} />
          <FilterPill label="Danh mục" value={categoryFilter} onChange={setCategoryFilter} options={[
            { value: 'all',          label: 'Tất cả' },
            { value: 'operational',  label: 'Vận hành' },
            { value: 'financial',    label: 'Tài chính' },
            { value: 'regulatory',   label: 'Pháp lý' },
            { value: 'reputational', label: 'Thương hiệu' },
            { value: 'strategic',    label: 'Chiến lược' },
            { value: 'technical',    label: 'Kỹ thuật' },
          ]} />
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
                  <th className="px-5 py-3">Owner</th>
                  <th className="px-5 py-3">Hạn mitigation</th>
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
                  filtered.map((r) => <RiskRowItem key={r.id} risk={r} />)
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <Sparkles className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            Severity tự suy ra từ likelihood × impact: ≤4 = thấp, 5-9 = trung, 10-15 = cao, &gt;15 = nghiêm trọng.
            Mọi update ghi vào <span className="font-mono">decision_audit_log</span> (K-6).
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
  label, value, icon: Icon, tone,
}: { label: string; value: number; icon: any; tone: string }) {
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

function FilterPill({
  label, value, onChange, options,
}: { label: string; value: string; onChange: (v: any) => void; options: { value: string; label: string }[] }) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none h-9 pl-3 pr-9 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-xs font-medium text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 cursor-pointer hover:bg-[var(--bg-card)]"
      >
        {options.map((o) => <option key={o.value} value={o.value}>{label}: {o.label}</option>)}
      </select>
      <ChevronDown className="w-3.5 h-3.5 text-[var(--text-secondary)] absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none" />
    </div>
  );
}

function RiskMatrix({ risks, loading }: { risks: RiskRow[]; loading: boolean }) {
  // Build a 5x5 grid: cells[likelihood][impact] = count.
  const cells: Record<string, RiskRow[]> = {};
  for (const r of risks) {
    if (r.status === 'closed') continue;
    const k = `${r.likelihood}_${r.impact}`;
    cells[k] = cells[k] ? [...cells[k], r] : [r];
  }

  function cellTone(likelihood: number, impact: number): string {
    const score = likelihood * impact;
    if (score <= 4)  return 'bg-[var(--state-success)]/15 border-[var(--state-success)]/30';
    if (score <= 9)  return 'bg-[var(--state-info)]/15 border-[var(--state-info)]/30';
    if (score <= 15) return 'bg-[var(--state-warning)]/15 border-[var(--state-warning)]/30';
    return 'bg-[var(--state-error)]/15 border-[var(--state-error)]/30';
  }

  const LIKELIHOOD_LABELS = ['Rất thấp', 'Thấp', 'Trung', 'Cao', 'Rất cao'];
  const IMPACT_LABELS     = ['Rất thấp', 'Thấp', 'Trung', 'Cao', 'Rất cao'];

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
              {IMPACT_LABELS.map((lbl, i) => (
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
                  {likelihood} · {LIKELIHOOD_LABELS[likelihood - 1]}
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
          { label: 'Thấp (≤4)',           cls: 'bg-[var(--state-success)]/30' },
          { label: 'Trung (5-9)',         cls: 'bg-[var(--state-info)]/30' },
          { label: 'Cao (10-15)',          cls: 'bg-[var(--state-warning)]/40' },
          { label: 'Nghiêm trọng (>15)',  cls: 'bg-[var(--state-error)]/40' },
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
  const isOverdue = r.mitigation_due && new Date(r.mitigation_due) < new Date('2026-05-01') && r.status !== 'closed';

  return (
    <tr className="hover:bg-[var(--bg-app)]/40 transition-colors group">
      <td className="px-5 py-4 max-w-md">
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center justify-center w-9 h-9 rounded-md-custom bg-[var(--primary-gold)]/10 shrink-0">
            <AlertTriangle className="w-4 h-4 text-[var(--primary-gold-dark)]" />
          </span>
          <div className="min-w-0">
            <a href={`/p2/risks/${r.id}`} className="text-sm font-medium text-[var(--text-primary)] group-hover:text-[var(--primary-gold-dark)] transition-colors line-clamp-1">
              {r.title}
            </a>
            <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">
              ID {r.id} · L{r.likelihood} × I{r.impact} = {r.likelihood * r.impact}
            </p>
          </div>
        </div>
      </td>
      <td className="px-5 py-4 text-xs text-[var(--text-secondary)]">{CATEGORY_LABEL[r.category]}</td>
      <td className="px-5 py-4"><Badge variant={sev.variant}>{sev.label}</Badge></td>
      <td className="px-5 py-4"><Badge variant={stt.variant}>{stt.label}</Badge></td>
      <td className="px-5 py-4">
        {r.owner ? (
          <span className="text-xs text-[var(--text-primary)]">{r.owner}</span>
        ) : (
          <span className="text-xs text-[var(--state-error)]">Chưa gán</span>
        )}
      </td>
      <td className="px-5 py-4">
        {r.mitigation_due ? (
          <span className={cn('text-xs', isOverdue ? 'text-[var(--state-error)] font-medium' : 'text-[var(--text-secondary)]')}>
            {new Date(r.mitigation_due).toLocaleDateString('vi-VN')}
            {isOverdue && ' ⚠️'}
          </span>
        ) : (
          <span className="text-xs text-[var(--text-secondary)]">—</span>
        )}
      </td>
      <td className="px-5 py-4 text-right">
        <a href={`/p2/risks/${r.id}`} className="inline-flex items-center text-xs font-medium text-[var(--primary-gold-dark)] hover:underline">
          Chi tiết <ArrowRight className="w-3 h-3 ml-1" />
        </a>
      </td>
    </tr>
  );
}
