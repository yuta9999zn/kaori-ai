// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 59. /p2/workflows — Workflows Hub (P15-S11 Tuần 8 — anh's pivot 2026-05-15)
// ----------------------------------------------------------------------------
// Workflow-first FE: doanh nghiệp số hóa quy trình từng phòng ban; mỗi
// phòng ban có nhiều workflow; mỗi workflow có 5-7 bước (card); mỗi card
// chứa note + hashtags + tài liệu cần upload. Khi user upload qua card →
// data lưu theo cây workflow → bước → file.
//
// Backend (mig 053/054 + ai-orchestrator routers/workflow_builder.py):
//   GET  /api/v1/workflows
//   POST /api/v1/workflows
//   GET  /api/v1/workflow-templates
//   POST /api/v1/workflows/from-template
// ============================================================================

import React, { useEffect, useMemo, useState } from 'react';
import {
  Workflow, Plus, Search, Sparkles, ArrowRight, FileText,
  CheckCircle2, Loader2, Layers, ChevronDown, X, GitBranch, LayoutGrid,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, SuccessBanner, api, cn, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { SkeletonCardGrid, SkeletonStatTiles } from '@/components/p2/skeleton';
import { formatProblem } from '@/lib/i18n/messages';

// ─── Types ─────────────────────────────────────────────────────────

type WorkflowState = 'DRAFT' | 'TESTING' | 'ACTIVE_BASELINE' | 'ARCHIVED' | 'BROKEN';
type DeptType     = 'marketing' | 'sales' | 'customer_service' | 'warehouse' | 'hr' | 'finance' | 'custom';

interface WorkflowRow {
  workflow_id:      string;
  enterprise_id:    string;
  department_id:    string;
  branch_id:        string | null;
  name:             string;
  name_vi:          string | null;
  description:      string | null;
  category:         string | null;
  state:            WorkflowState;
  version:          number;
  source:           'user_built' | 'template_based' | 'process_mining_discovered';
  created_at:       string;
  last_modified_at: string;
}

interface WorkflowTemplate {
  template_id:        string;
  display_name:       string;
  display_name_vi:    string;
  description:        string | null;
  department_type:    DeptType;
  category:           string | null;
  estimated_setup_minutes: number;
  node_count:         number;
  edge_count:         number;
}

const DEPT_META: Record<DeptType, { label_vi: string; color: string }> = {
  marketing:        { label_vi: 'Marketing',  color: 'text-pink-700 bg-pink-50' },
  sales:            { label_vi: 'Sales',      color: 'text-blue-700 bg-blue-50' },
  customer_service: { label_vi: 'CSKH',       color: 'text-purple-700 bg-purple-50' },
  warehouse:        { label_vi: 'Kho vận',    color: 'text-green-700 bg-green-50' },
  hr:               { label_vi: 'Nhân sự',    color: 'text-amber-700 bg-amber-50' },
  finance:          { label_vi: 'Tài chính',  color: 'text-teal-700 bg-teal-50' },
  custom:           { label_vi: 'Tùy chỉnh', color: 'text-gray-700 bg-gray-50' },
};

const STATE_META: Record<WorkflowState, { label_vi: string; variant: 'default' | 'success' | 'warning' | 'destructive' }> = {
  DRAFT:           { label_vi: 'Bản nháp',  variant: 'default' },
  TESTING:         { label_vi: 'Đang test', variant: 'warning' },
  ACTIVE_BASELINE: { label_vi: 'Đang chạy', variant: 'success' },
  ARCHIVED:        { label_vi: 'Lưu trữ',   variant: 'default' },
  BROKEN:          { label_vi: 'Lỗi',       variant: 'destructive' },
};

// ─── Page ──────────────────────────────────────────────────────────

export default function WorkflowsHubPage() {
  const [workflows, setWorkflows] = useState<WorkflowRow[]>([]);
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [search, setSearch] = useState('');
  const [deptFilter, setDeptFilter] = useState<'all' | DeptType>('all');
  const [stateFilter, setStateFilter] = useState<'all' | WorkflowState>('all');
  const [pickerOpen, setPickerOpen] = useState(false);
  // Default group-by-dept — anh 2026-05-15: "1 phòng ban có nhiều workflow,
  // phải cho họ tạo và kết nối với phòng ban khác". Flat grid mở rộng khó
  // nhìn khi 1 doanh nghiệp có 30+ workflow nên section per dept là default.
  const [viewMode, setViewMode] = useState<'by_dept' | 'grid'>('by_dept');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [wf, tpl] = await Promise.all([
          api<WorkflowRow[]>('/api/v1/workflows'),
          api<WorkflowTemplate[]>('/api/v1/workflow-templates'),
        ]);
        if (!cancelled) {
          setWorkflows(wf ?? []);
          setTemplates(tpl ?? []);
        }
      } catch (e: any) {
        if (!cancelled) setProblem(e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return workflows.filter((w) => {
      if (deptFilter !== 'all' && deptKeyOf(w) !== deptFilter) return false;
      if (stateFilter !== 'all' && w.state !== stateFilter) return false;
      if (q) {
        const hay = (w.name + ' ' + (w.name_vi || '') + ' ' + (w.description || '')).toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [workflows, search, deptFilter, stateFilter]);

  const stats = useMemo(() => ({
    total:     workflows.length,
    drafts:    workflows.filter((w) => w.state === 'DRAFT').length,
    active:    workflows.filter((w) => w.state === 'ACTIVE_BASELINE').length,
    templates: templates.length,
  }), [workflows, templates]);

  // dept_type → 1 department_id (sniffed from existing workflows).
  // Phase 2: replace by GET /api/v1/departments.
  const deptIdByType = useMemo(() => {
    const map: Partial<Record<DeptType, string>> = {};
    for (const w of workflows) {
      const k = deptKeyOf(w);
      if (!map[k]) map[k] = w.department_id;
    }
    return map;
  }, [workflows]);

  // Group filtered workflows by dept_type for the "by_dept" view.
  const groupedByDept = useMemo(() => {
    const g: Record<DeptType, WorkflowRow[]> = {} as any;
    const order: DeptType[] = ['marketing', 'sales', 'customer_service', 'warehouse', 'hr', 'finance', 'custom'];
    for (const d of order) g[d] = [];
    for (const w of filtered) {
      const k = deptKeyOf(w);
      (g[k] = g[k] || []).push(w);
    }
    return { groups: g, order };
  }, [filtered]);

  async function onCloneTemplate(t: WorkflowTemplate, departmentId: string) {
    setSuccess(null); setProblem(null);
    try {
      const created = await api<WorkflowRow>('/api/v1/workflows/from-template', {
        method: 'POST',
        body: JSON.stringify({ template_id: t.template_id, department_id: departmentId }),
      });
      setWorkflows((prev) => [created, ...prev]);
      setSuccess(`Đã tạo workflow "${created.name}" từ template.`);
      setPickerOpen(false);
    } catch (e: any) {
      setProblem(e);
    }
  }

  return (
    <>
      <PageHeader
        title="Workflow"
        description="Số hóa quy trình phòng ban — kéo các bước, gắn tài liệu, hệ thống tự lưu theo cây workflow → bước → file."
        actions={
          <>
            <Button variant="secondary" size="md" onClick={() => setPickerOpen(true)}>
              <Sparkles className="w-4 h-4 mr-2" /> Từ template
            </Button>
            <a href="/p2/workflows/new">
              <Button variant="primary" size="md">
                <Plus className="w-4 h-4 mr-2" /> Tạo workflow
              </Button>
            </a>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-6">
        {problem && <ErrorBanner problem={problem} />}
        {success && <SuccessBanner message={success} />}

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatTile label="Tổng workflow" value={stats.total} icon={Workflow} />
          <StatTile label="Đang chạy"     value={stats.active}    icon={CheckCircle2} tone="text-emerald-700" />
          <StatTile label="Bản nháp"      value={stats.drafts}    icon={FileText}     tone="text-amber-700" />
          <StatTile label="Template sẵn"  value={stats.templates} icon={Layers}       tone="text-blue-700" />
        </div>

        <Toolbar
          search={search} onSearch={setSearch}
          deptFilter={deptFilter} onDeptFilter={setDeptFilter}
          stateFilter={stateFilter} onStateFilter={setStateFilter}
          viewMode={viewMode} onViewMode={setViewMode}
        />

        {loading ? (
          <SkeletonCardGrid count={6} />
        ) : filtered.length === 0 ? (
          <EmptyState onPickTemplate={() => setPickerOpen(true)} />
        ) : viewMode === 'grid' ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((w) => <WorkflowCard key={w.workflow_id} wf={w} />)}
          </div>
        ) : (
          <div className="space-y-6">
            {groupedByDept.order.map((dept) => {
              const list = groupedByDept.groups[dept] ?? [];
              // Hide non-custom depts that have neither workflows nor sniffed
              // department_id — they're not provisioned for this tenant.
              if (list.length === 0 && !deptIdByType[dept] && dept !== 'custom') return null;
              return (
                <DeptSection
                  key={dept}
                  dept={dept}
                  workflows={list}
                  departmentId={deptIdByType[dept] ?? null}
                  onPickTemplate={() => setPickerOpen(true)}
                />
              );
            })}
          </div>
        )}
      </div>

      {pickerOpen && (
        <TemplatePicker
          templates={templates}
          workflows={workflows}
          onClose={() => setPickerOpen(false)}
          onClone={onCloneTemplate}
        />
      )}
    </>
  );
}

// ─── Sub-components ────────────────────────────────────────────────

function StatTile({
  label, value, icon: Icon, tone = 'text-[var(--text-primary)]',
}: { label: string; value: number; icon: any; tone?: string }) {
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

function Toolbar({
  search, onSearch, deptFilter, onDeptFilter, stateFilter, onStateFilter,
  viewMode, onViewMode,
}: any) {
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-3 flex flex-col lg:flex-row gap-3 shadow-soft-sm">
      <div className="relative flex-1 min-w-[200px]">
        <Search className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
        <input
          type="text"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          placeholder="Tìm workflow theo tên / mô tả…"
          className="w-full pl-9 pr-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
        />
      </div>
      <FilterPill label="Phòng ban" value={deptFilter} onChange={onDeptFilter} options={[
        { value: 'all', label: 'Tất cả' },
        { value: 'marketing', label: 'Marketing' },
        { value: 'sales', label: 'Sales' },
        { value: 'customer_service', label: 'CSKH' },
        { value: 'warehouse', label: 'Kho vận' },
        { value: 'hr', label: 'Nhân sự' },
        { value: 'finance', label: 'Tài chính' },
      ]} />
      <FilterPill label="Trạng thái" value={stateFilter} onChange={onStateFilter} options={[
        { value: 'all', label: 'Tất cả' },
        { value: 'DRAFT', label: 'Bản nháp' },
        { value: 'TESTING', label: 'Đang test' },
        { value: 'ACTIVE_BASELINE', label: 'Đang chạy' },
        { value: 'ARCHIVED', label: 'Lưu trữ' },
      ]} />
      <div className="inline-flex bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom p-0.5">
        <button onClick={() => onViewMode('by_dept')}
                className={cn(
                  'inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded transition-colors',
                  viewMode === 'by_dept'
                    ? 'bg-white text-[var(--primary-gold-dark)] shadow-soft-sm'
                    : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
                )}>
          <Layers className="w-3.5 h-3.5" /> Theo phòng ban
        </button>
        <button onClick={() => onViewMode('grid')}
                className={cn(
                  'inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded transition-colors',
                  viewMode === 'grid'
                    ? 'bg-white text-[var(--primary-gold-dark)] shadow-soft-sm'
                    : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
                )}>
          <LayoutGrid className="w-3.5 h-3.5" /> Tất cả
        </button>
      </div>
    </div>
  );
}

// ─── DeptSection ─────────────────────────────────────────────────
// Section per dept_type. Header has count + "Tạo workflow cho phòng này"
// CTA when departmentId is known. Empty section nudges user to add one.

function DeptSection({
  dept, workflows, departmentId, onPickTemplate,
}: {
  dept: DeptType;
  workflows: WorkflowRow[];
  departmentId: string | null;
  onPickTemplate: () => void;
}) {
  const meta = DEPT_META[dept] ?? DEPT_META.custom;
  const newHref = departmentId
    ? `/p2/workflows/new?department_id=${encodeURIComponent(departmentId)}`
    : '/p2/workflows/new';
  const deptHref = departmentId
    ? `/p2/departments/${encodeURIComponent(departmentId)}/workflows`
    : null;

  return (
    <section className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm">
      <header className="px-5 py-3 border-b border-[var(--border-color)]/60 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          {deptHref ? (
            <a href={deptHref}
               className={cn('text-sm font-medium px-2 py-0.5 rounded hover:underline', meta.color)}>
              {meta.label_vi}
            </a>
          ) : (
            <span className={cn('text-sm font-medium px-2 py-0.5 rounded', meta.color)}>{meta.label_vi}</span>
          )}
          <span className="text-xs text-[var(--text-secondary)]">
            {workflows.length} workflow{workflows.length >= 2 ? ' (có thể nối chéo)' : ''}
          </span>
          {deptHref && workflows.length > 0 && (
            <a href={deptHref}
               className="text-[11px] font-medium text-[var(--primary-gold-dark)] hover:underline">
              Xem trang phòng này →
            </a>
          )}
        </div>
        <div className="flex items-center gap-2">
          {workflows.length >= 2 && (
            <span className="hidden sm:inline-flex items-center gap-1 text-[10px] font-medium text-violet-700 bg-violet-50 border border-violet-200 px-1.5 py-0.5 rounded">
              <GitBranch className="w-3 h-3" /> Cross-link sẵn sàng
            </span>
          )}
          <a href={newHref}>
            <Button variant="secondary" size="sm">
              <Plus className="w-3.5 h-3.5 mr-1" /> Thêm vào phòng này
            </Button>
          </a>
        </div>
      </header>

      {workflows.length === 0 ? (
        <div className="px-5 py-8 text-center">
          <p className="text-sm text-[var(--text-secondary)] mb-2">
            {meta.label_vi} chưa có workflow.
          </p>
          <div className="flex items-center justify-center gap-2">
            <a href={newHref}>
              <Button variant="primary" size="sm"><Plus className="w-3.5 h-3.5 mr-1" /> Tạo trắng</Button>
            </a>
            <Button variant="tertiary" size="sm" onClick={onPickTemplate}>
              <Sparkles className="w-3.5 h-3.5 mr-1" /> Từ template
            </Button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 p-4">
          {workflows.map((w) => <WorkflowCard key={w.workflow_id} wf={w} />)}
        </div>
      )}
    </section>
  );
}

function FilterPill({ label, value, onChange, options }: any) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none h-9 pl-3 pr-9 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-xs font-medium focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 cursor-pointer"
      >
        {options.map((o: any) => <option key={o.value} value={o.value}>{label}: {o.label}</option>)}
      </select>
      <ChevronDown className="w-3.5 h-3.5 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none" />
    </div>
  );
}

function WorkflowCard({ wf }: { wf: WorkflowRow }) {
  const dept = DEPT_META[deptKeyOf(wf)] ?? DEPT_META.custom;
  const state = STATE_META[wf.state] ?? STATE_META.DRAFT;
  return (
    <a
      href={`/p2/workflows/${wf.workflow_id}`}
      className="group block bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] hover:border-[var(--primary-gold)]/50 hover:shadow-soft-md transition-all p-5"
    >
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="w-10 h-10 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center shrink-0">
          <Workflow className="w-5 h-5 text-[var(--primary-gold-dark)]" />
        </div>
        <Badge variant={state.variant}>{state.label_vi}</Badge>
      </div>
      <h3 className="font-serif text-base text-[var(--text-primary)] group-hover:text-[var(--primary-gold-dark)] transition-colors line-clamp-1">
        {wf.name_vi || wf.name}
      </h3>
      {wf.description && (
        <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed line-clamp-2">{wf.description}</p>
      )}
      <div className="mt-3 pt-3 border-t border-[var(--border-color)]/60 flex items-center justify-between text-[11px]">
        <span className={cn('px-2 py-0.5 rounded text-xs font-medium', dept.color)}>{dept.label_vi}</span>
        <span className="text-[var(--text-secondary)]">v{wf.version}</span>
      </div>
      <div className="mt-3 inline-flex items-center text-xs font-medium text-[var(--primary-gold-dark)] group-hover:translate-x-0.5 transition-transform">
        Mở workflow <ArrowRight className="w-3 h-3 ml-1" />
      </div>
    </a>
  );
}

function EmptyState({ onPickTemplate }: { onPickTemplate: () => void }) {
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom py-16 text-center px-6">
      <Workflow className="w-12 h-12 mx-auto text-[var(--text-secondary)]/40 mb-3" />
      <h3 className="font-serif text-lg text-[var(--text-primary)] mb-2">Chưa có workflow nào</h3>
      <p className="text-sm text-[var(--text-secondary)] max-w-md mx-auto mb-4">
        Tạo workflow từ template (Sales / Marketing / CSKH / Kho vận / HR / Tài chính) hoặc bắt đầu trắng.
      </p>
      <Button variant="primary" size="md" onClick={onPickTemplate}>
        <Sparkles className="w-4 h-4 mr-2" /> Xem template
      </Button>
    </div>
  );
}

// ─── Template Picker Modal ────────────────────────────────────────

function TemplatePicker({
  templates, workflows, onClose, onClone,
}: {
  templates: WorkflowTemplate[];
  workflows: WorkflowRow[];
  onClose: () => void;
  onClone: (t: WorkflowTemplate, departmentId: string) => void;
}) {
  // Map dept_type → department_id from existing workflows. The first
  // workflow we see for a given dept tells us the UUID. For depts the
  // tenant has no workflow yet, we surface a guidance message.
  const deptIdByType: Record<string, string> = useMemo(() => {
    const map: Record<string, string> = {};
    for (const w of workflows) {
      const key = deptKeyOf(w);
      if (!map[key]) map[key] = w.department_id;
    }
    return map;
  }, [workflows]);

  const [selected, setSelected] = useState<WorkflowTemplate | null>(null);

  const grouped = useMemo(() => {
    const g: Record<DeptType, WorkflowTemplate[]> = {} as any;
    for (const t of templates) {
      if (!g[t.department_type]) g[t.department_type] = [];
      g[t.department_type].push(t);
    }
    return g;
  }, [templates]);

  function handlePick(t: WorkflowTemplate) {
    const did = deptIdByType[t.department_type];
    if (!did) { setSelected(t); return; }
    onClone(t, did);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-[var(--bg-card)] rounded-lg-custom shadow-soft-md max-w-4xl w-full max-h-[85vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-6 py-4 border-b border-[var(--border-color)] flex items-center justify-between">
          <div>
            <h3 className="font-serif text-lg text-[var(--text-primary)]">Chọn template workflow</h3>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              {templates.length} template — 3 cho mỗi phòng ban × 6 phòng ban
            </p>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-[var(--bg-app)] rounded-md-custom">
            <X className="w-5 h-5 text-[var(--text-secondary)]" />
          </button>
        </div>
        <div className="overflow-y-auto p-6 space-y-6 flex-1">
          {Object.entries(grouped).map(([dept, items]) => {
            const meta = DEPT_META[dept as DeptType];
            return (
              <div key={dept}>
                <h4 className={cn('text-sm font-medium mb-3 inline-block px-2 py-0.5 rounded', meta?.color)}>
                  {meta?.label_vi || dept}
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {(items as WorkflowTemplate[]).map((t) => (
                    <button
                      key={t.template_id}
                      onClick={() => handlePick(t)}
                      className="text-left p-4 rounded-md-custom border border-[var(--border-color)] hover:border-[var(--primary-gold)] hover:bg-[var(--primary-gold)]/5 transition-all"
                    >
                      <h5 className="font-serif text-sm text-[var(--text-primary)] mb-1">{t.display_name_vi}</h5>
                      <p className="text-[11px] text-[var(--text-secondary)] line-clamp-2 mb-2">{t.description}</p>
                      <div className="flex items-center gap-2 text-[10px] text-[var(--text-secondary)]">
                        <Layers className="w-3 h-3" /> {t.node_count} bước · ~{t.estimated_setup_minutes} phút
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
          {selected && !deptIdByType[selected.department_type] && (
            <ErrorBanner problem={{
              title: 'Chưa có phòng ban',
              detail: `Workspace chưa có phòng ban ${DEPT_META[selected.department_type]?.label_vi}. ` +
                      `Yêu cầu MANAGER tạo phòng ban trước khi clone template.`,
            }} />
          )}
        </div>
      </div>
    </div>
  );
}

function deptKeyOf(w: WorkflowRow): DeptType {
  // Build Week: dept inferred from category since /api/v1/departments
  // isn't wired yet. Phase 2 = join with departments table.
  const cat = (w.category || '').toLowerCase();
  if (cat.includes('campaign') || cat.includes('onboarding') || cat.includes('recovery')) return 'marketing';
  if (cat.includes('pipeline') || cat.includes('risk'))   return 'sales';
  if (cat.includes('ticket') || cat.includes('refund') || cat.includes('escalation')) return 'customer_service';
  if (cat.includes('reorder') || cat.includes('alert') || cat.includes('quality'))    return 'warehouse';
  if (cat.includes('hiring') || cat.includes('onboarding') || cat.includes('exit'))   return 'hr';
  if (cat.includes('ap') || cat.includes('ar') || cat.includes('forecast'))           return 'finance';
  return 'custom';
}
