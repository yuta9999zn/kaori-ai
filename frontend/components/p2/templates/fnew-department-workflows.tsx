// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// /p2/departments/[dept_id]/workflows — Dedicated workflow list per dept
//                                       (P15-S11 Tuần 8 — anh 2026-05-15)
// ----------------------------------------------------------------------------
// Anh's directive: "một phòng ban có thể có rất nhiều workflow, cần thiết kế
// làm sao có thể xem list workflow theo phòng ban".
//
// Flat hub grid breaks when 1 dept owns 10-30 workflow (Vingroup Vinmart Sales
// realistically has: prospect intake, deal qualification, contract drafting,
// fulfillment, post-sale renewal, escalation queue, complaint handling, KPI
// review, monthly close, AR collection — easily 10+ per dept).
//
// This page = drill-down view: dept header + KPI tiles + search/filter +
// cross-link recommender + workflow grid. Reuses Hub WorkflowCard shape but
// scoped exclusively to 1 department_id.
//
// Backend
//   GET /api/v1/departments/{id}                  — dept header + counts
//   GET /api/v1/workflows?department_id={id}      — workflows for this dept
//   GET /api/v1/workflow-cross-links?dept_id={id} — links touching this dept
// ============================================================================

import React, { useEffect, useMemo, useState } from 'react';
import {
  ArrowLeft, Workflow as WorkflowIcon, Plus, Search, Sparkles, ArrowRight,
  FileText, CheckCircle2, Building2, GitBranch, Layers, X,
  ChevronDown, AlertCircle,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, SuccessBanner, api, cn, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { SkeletonCardGrid, SkeletonStatTiles } from '@/components/p2/skeleton';
import { formatProblem } from '@/lib/i18n/messages';
import { useT } from '@/lib/i18n/provider';

// ─── Types ─────────────────────────────────────────────────────────

type WorkflowState = 'DRAFT' | 'TESTING' | 'ACTIVE_BASELINE' | 'ARCHIVED' | 'BROKEN';
type DeptType     = 'marketing' | 'sales' | 'customer_service' | 'warehouse' | 'hr' | 'finance' | 'custom';

interface DepartmentDetail {
  department_id:   string;
  enterprise_id:   string;
  enterprise_name: string | null;
  branch_id:       string | null;
  branch_name:     string | null;
  workspace_id:    string;
  name:            string;
  dept_type:       DeptType;
  status:          string;
  description:     string | null;
  workflow_count:  number;
  active_count:    number;
}

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

interface CrossLink {
  link_id:                 string;
  source_workflow_id:      string;
  target_workflow_id:      string;
  link_type:               string;
  source_workflow_name:    string | null;
  source_workflow_name_vi: string | null;
  source_department_name:  string | null;
  source_enterprise_name:  string | null;
  target_workflow_name:    string | null;
  target_workflow_name_vi: string | null;
  target_department_name:  string | null;
  target_enterprise_name:  string | null;
  crosses_enterprise:      boolean;
  crosses_department:      boolean;
  crosses_branch:          boolean;
  crosses_division:        boolean;
}

const DEPT_META: Record<DeptType, { labelKey: string; color: string; icon: string }> = {
  marketing:        { labelKey: 'templatesFnewDepartmentWorkflows.deptMarketing',        color: 'text-pink-700 bg-pink-50',     icon: '📣' },
  sales:            { labelKey: 'templatesFnewDepartmentWorkflows.deptSales',            color: 'text-blue-700 bg-blue-50',     icon: '💼' },
  customer_service: { labelKey: 'templatesFnewDepartmentWorkflows.deptCustomerService',  color: 'text-purple-700 bg-purple-50', icon: '🎧' },
  warehouse:        { labelKey: 'templatesFnewDepartmentWorkflows.deptWarehouse',        color: 'text-green-700 bg-green-50',   icon: '📦' },
  hr:               { labelKey: 'templatesFnewDepartmentWorkflows.deptHr',               color: 'text-amber-700 bg-amber-50',   icon: '👥' },
  finance:          { labelKey: 'templatesFnewDepartmentWorkflows.deptFinance',          color: 'text-teal-700 bg-teal-50',     icon: '💰' },
  custom:           { labelKey: 'templatesFnewDepartmentWorkflows.deptCustom',           color: 'text-gray-700 bg-gray-50',     icon: '⚙️' },
};

const STATE_META: Record<WorkflowState, { labelKey: string; variant: 'default' | 'success' | 'warning' | 'destructive' }> = {
  DRAFT:           { labelKey: 'templatesFnewDepartmentWorkflows.stateDraft',   variant: 'default' },
  TESTING:         { labelKey: 'templatesFnewDepartmentWorkflows.stateTesting', variant: 'warning' },
  ACTIVE_BASELINE: { labelKey: 'templatesFnewDepartmentWorkflows.stateActive',  variant: 'success' },
  ARCHIVED:        { labelKey: 'templatesFnewDepartmentWorkflows.stateArchived', variant: 'default' },
  BROKEN:          { labelKey: 'templatesFnewDepartmentWorkflows.stateBroken',  variant: 'destructive' },
};

// ─── Page ──────────────────────────────────────────────────────────

export default function DepartmentWorkflowsPage({ departmentId }: { departmentId: string }) {
  const t = useT();
  const [dept, setDept] = useState<DepartmentDetail | null>(null);
  const [workflows, setWorkflows] = useState<WorkflowRow[]>([]);
  const [crossLinks, setCrossLinks] = useState<CrossLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [linksLoading, setLinksLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  const [search, setSearch] = useState('');
  const [stateFilter, setStateFilter] = useState<'all' | WorkflowState>('all');

  // Initial header + workflow list
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const [d, ws] = await Promise.all([
          api<DepartmentDetail>(`/api/v1/departments/${departmentId}`),
          api<WorkflowRow[]>(`/api/v1/workflows?department_id=${encodeURIComponent(departmentId)}&limit=500`),
        ]);
        if (!cancelled) {
          setDept(d);
          setWorkflows(ws ?? []);
        }
      } catch (e: any) {
        if (!cancelled) setProblem(e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [departmentId]);

  // Cross-link fetch (after we know dept exists) — failures are non-fatal.
  useEffect(() => {
    if (!dept) return;
    let cancelled = false;
    setLinksLoading(true);
    (async () => {
      try {
        const wfIds = new Set(workflows.map((w) => w.workflow_id));
        // BE doesn't have a per-dept cross-link endpoint yet; fetch the
        // workspace list and filter client-side. Phase 2 = ?dept_id= filter.
        const all = await api<CrossLink[]>('/api/v1/workflow-cross-links');
        if (cancelled) return;
        const filtered = (all ?? []).filter((l) =>
          wfIds.has(l.source_workflow_id) || wfIds.has(l.target_workflow_id),
        );
        setCrossLinks(filtered);
      } catch {
        // ignore — cross-links is supplementary
      } finally {
        if (!cancelled) setLinksLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [dept, workflows]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return workflows.filter((w) => {
      if (stateFilter !== 'all' && w.state !== stateFilter) return false;
      if (q) {
        const hay = (w.name + ' ' + (w.name_vi || '') + ' ' + (w.description || '')).toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [workflows, search, stateFilter]);

  const stats = useMemo(() => ({
    total:     workflows.length,
    drafts:    workflows.filter((w) => w.state === 'DRAFT').length,
    active:    workflows.filter((w) => w.state === 'ACTIVE_BASELINE').length,
    testing:   workflows.filter((w) => w.state === 'TESTING').length,
    crossLink: crossLinks.length,
  }), [workflows, crossLinks]);

  const meta = dept ? (DEPT_META[dept.dept_type] ?? DEPT_META.custom) : DEPT_META.custom;
  const newWorkflowHref = `/p2/workflows/new?department_id=${encodeURIComponent(departmentId)}${
    dept?.enterprise_id ? `&enterprise_id=${encodeURIComponent(dept.enterprise_id)}` : ''
  }`;

  return (
    <>
      <PageHeader
        title={dept ? `${meta.icon} ${t(meta.labelKey)}` : t('templatesFnewDepartmentWorkflows.deptFallback')}
        description={
          dept
            ? t('templatesFnewDepartmentWorkflows.headerDesc', {
                count: String(dept.workflow_count),
                dept: t(meta.labelKey),
                enterprise: dept.enterprise_name ? `· ${dept.enterprise_name}` : '',
                branch: dept.branch_name ? ` · ${t('templatesFnewDepartmentWorkflows.branchAbbr')} ${dept.branch_name}` : '',
              })
            : t('templatesFnewDepartmentWorkflows.loadingDept')
        }
        actions={
          <>
            <a href="/p2/workflows">
              <Button variant="tertiary" size="md">
                <ArrowLeft className="w-4 h-4 mr-2" /> {t('templatesFnewDepartmentWorkflows.allDepartments')}
              </Button>
            </a>
            <a href={newWorkflowHref}>
              <Button variant="primary" size="md">
                <Plus className="w-4 h-4 mr-2" /> {t('templatesFnewDepartmentWorkflows.createWorkflowForDept')}
              </Button>
            </a>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-6">
        {problem && <ErrorBanner problem={problem} />}

        {/* Stat tiles */}
        {loading ? (
          <SkeletonStatTiles count={5} />
        ) : (
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
            <StatTile label={t('templatesFnewDepartmentWorkflows.statTotal')}     value={stats.total}     icon={WorkflowIcon} />
            <StatTile label={t('templatesFnewDepartmentWorkflows.statActive')}    value={stats.active}    icon={CheckCircle2} tone="text-emerald-700" />
            <StatTile label={t('templatesFnewDepartmentWorkflows.statTesting')}   value={stats.testing}   icon={AlertCircle}  tone="text-amber-700" />
            <StatTile label={t('templatesFnewDepartmentWorkflows.statDrafts')}    value={stats.drafts}    icon={FileText}     tone="text-slate-700" />
            <StatTile label={t('templatesFnewDepartmentWorkflows.statCrossLink')} value={stats.crossLink} icon={GitBranch}    tone="text-violet-700" />
          </div>
        )}

        {/* Org-context strip — shows where this dept sits in the hierarchy */}
        {dept && (
          <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-4 shadow-soft-sm">
            <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)] flex-wrap">
              <Building2 className="w-4 h-4 text-[var(--primary-gold-dark)]" />
              <span className="font-medium text-[var(--text-primary)]">{dept.enterprise_name ?? '—'}</span>
              {dept.branch_name && (
                <>
                  <span>›</span>
                  <span>{t('templatesFnewDepartmentWorkflows.branchAbbr')} {dept.branch_name}</span>
                </>
              )}
              <span>›</span>
              <span className={cn('px-2 py-0.5 rounded text-[11px] font-medium', meta.color)}>
                {t(meta.labelKey)}
              </span>
              <span className="ml-auto inline-flex items-center gap-1 text-[10px]">
                <a
                  href={`/p2/org-tree?enterprise_id=${encodeURIComponent(dept.enterprise_id)}`}
                  className="text-[var(--primary-gold-dark)] hover:underline"
                >
                  {t('templatesFnewDepartmentWorkflows.viewOrgTree')} →
                </a>
              </span>
            </div>
            {dept.description && (
              <p className="mt-2 text-xs text-[var(--text-secondary)] italic">{dept.description}</p>
            )}
          </div>
        )}

        {/* Search + state filter */}
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-3 flex flex-col sm:flex-row gap-3 shadow-soft-sm">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t('templatesFnewDepartmentWorkflows.searchPlaceholder')}
              className="w-full pl-9 pr-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
            />
          </div>
          <div className="relative">
            <select
              value={stateFilter}
              onChange={(e) => setStateFilter(e.target.value as any)}
              className="appearance-none h-9 pl-3 pr-9 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-xs font-medium focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 cursor-pointer"
            >
              <option value="all">{t('templatesFnewDepartmentWorkflows.filterAll')}</option>
              <option value="DRAFT">{t('templatesFnewDepartmentWorkflows.stateDraft')}</option>
              <option value="TESTING">{t('templatesFnewDepartmentWorkflows.stateTesting')}</option>
              <option value="ACTIVE_BASELINE">{t('templatesFnewDepartmentWorkflows.stateActive')}</option>
              <option value="ARCHIVED">{t('templatesFnewDepartmentWorkflows.stateArchived')}</option>
            </select>
            <ChevronDown className="w-3.5 h-3.5 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>
        </div>

        {/* Workflow grid */}
        {loading ? (
          <SkeletonCardGrid count={6} />
        ) : filtered.length === 0 ? (
          <EmptyState newHref={newWorkflowHref} hasAny={workflows.length > 0} />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((w) => <WorkflowCard key={w.workflow_id} wf={w} />)}
          </div>
        )}

        {/* Cross-link panel — show only when this dept actually has any link */}
        {!linksLoading && crossLinks.length > 0 && (
          <CrossLinkPanel links={crossLinks} ownWorkflowIds={new Set(workflows.map((w) => w.workflow_id))} />
        )}
      </div>
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

function WorkflowCard({ wf }: { wf: WorkflowRow }) {
  const t = useT();
  const state = STATE_META[wf.state] ?? STATE_META.DRAFT;
  return (
    <a
      href={`/p2/workflows/${wf.workflow_id}`}
      className="group block bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] hover:border-[var(--primary-gold)]/50 hover:shadow-soft-md transition-all p-5"
    >
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="w-10 h-10 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center shrink-0">
          <WorkflowIcon className="w-5 h-5 text-[var(--primary-gold-dark)]" />
        </div>
        <Badge variant={state.variant}>{t(state.labelKey)}</Badge>
      </div>
      <h3 className="font-serif text-base text-[var(--text-primary)] group-hover:text-[var(--primary-gold-dark)] transition-colors line-clamp-1">
        {wf.name_vi || wf.name}
      </h3>
      {wf.description && (
        <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed line-clamp-2">{wf.description}</p>
      )}
      <div className="mt-3 pt-3 border-t border-[var(--border-color)]/60 flex items-center justify-between text-[11px]">
        <span className="text-[var(--text-secondary)]">v{wf.version}</span>
        <span className="text-[var(--text-secondary)]">
          {wf.source === 'template_based' ? `📋 ${t('templatesFnewDepartmentWorkflows.sourceTemplate')}` :
           wf.source === 'process_mining_discovered' ? `🔍 ${t('templatesFnewDepartmentWorkflows.sourceProcessMining')}` :
                                                       `✏️ ${t('templatesFnewDepartmentWorkflows.sourceSelfBuilt')}`}
        </span>
      </div>
      <div className="mt-3 inline-flex items-center text-xs font-medium text-[var(--primary-gold-dark)] group-hover:translate-x-0.5 transition-transform">
        {t('templatesFnewDepartmentWorkflows.openWorkflow')} <ArrowRight className="w-3 h-3 ml-1" />
      </div>
    </a>
  );
}

function EmptyState({ newHref, hasAny }: { newHref: string; hasAny: boolean }) {
  const t = useT();
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom py-16 text-center px-6">
      <WorkflowIcon className="w-12 h-12 mx-auto text-[var(--text-secondary)]/40 mb-3" />
      <h3 className="font-serif text-lg text-[var(--text-primary)] mb-2">
        {hasAny ? t('templatesFnewDepartmentWorkflows.emptyNoMatchTitle') : t('templatesFnewDepartmentWorkflows.emptyNoWorkflowTitle')}
      </h3>
      <p className="text-sm text-[var(--text-secondary)] max-w-md mx-auto mb-4">
        {hasAny
          ? t('templatesFnewDepartmentWorkflows.emptyNoMatchDesc')
          : t('templatesFnewDepartmentWorkflows.emptyNoWorkflowDesc')}
      </p>
      {!hasAny && (
        <a href={newHref}>
          <Button variant="primary" size="md"><Plus className="w-4 h-4 mr-2" /> {t('templatesFnewDepartmentWorkflows.createFirstWorkflow')}</Button>
        </a>
      )}
    </div>
  );
}

// ─── CrossLinkPanel ────────────────────────────────────────────────
// List cross-workflow links where THIS dept is source or target. Highlights
// the cross-dimension flag (department / enterprise / branch / division) so
// Vingroup HQ user sees at-a-glance which of their workflows trigger work in
// other subsidiaries.

function CrossLinkPanel({ links, ownWorkflowIds }: { links: CrossLink[]; ownWorkflowIds: Set<string> }) {
  const t = useT();
  return (
    <div className="bg-[var(--bg-card)] border border-violet-200 rounded-lg-custom p-5 shadow-soft-sm">
      <header className="flex items-center justify-between mb-3 pb-3 border-b border-violet-100">
        <div className="flex items-center gap-2">
          <GitBranch className="w-5 h-5 text-violet-700" />
          <h3 className="font-serif text-base text-[var(--text-primary)]">
            {t('templatesFnewDepartmentWorkflows.crossLinkTitle')}
          </h3>
        </div>
        <span className="text-xs text-[var(--text-secondary)]">{t('templatesFnewDepartmentWorkflows.crossLinkCount', { count: String(links.length) })}</span>
      </header>

      <div className="space-y-2">
        {links.slice(0, 10).map((l) => {
          const isSource = ownWorkflowIds.has(l.source_workflow_id);
          const ours = isSource ? l : null;  // anchor — direction matters for narrative
          return (
            <div key={l.link_id} className="flex items-center gap-2 text-xs p-2 bg-violet-50/40 rounded">
              <a href={`/p2/workflows/${l.source_workflow_id}`}
                 className="font-medium text-[var(--text-primary)] hover:text-[var(--primary-gold-dark)] truncate max-w-[200px]">
                {l.source_workflow_name_vi || l.source_workflow_name || t('templatesFnewDepartmentWorkflows.unnamedWorkflow')}
              </a>
              <span className="text-[10px] text-violet-700 font-medium px-1.5 py-0.5 rounded bg-violet-100 border border-violet-200 shrink-0">
                {l.link_type}
              </span>
              <ArrowRight className="w-3 h-3 text-violet-600 shrink-0" />
              <a href={`/p2/workflows/${l.target_workflow_id}`}
                 className="font-medium text-[var(--text-primary)] hover:text-[var(--primary-gold-dark)] truncate max-w-[200px]">
                {l.target_workflow_name_vi || l.target_workflow_name || t('templatesFnewDepartmentWorkflows.unnamedWorkflow')}
              </a>
              <div className="ml-auto flex gap-1 flex-wrap shrink-0">
                {l.crosses_department && (
                  <Pill color="amber">→ {t('templatesFnewDepartmentWorkflows.crossesDepartment')}</Pill>
                )}
                {l.crosses_branch && (
                  <Pill color="blue">→ {t('templatesFnewDepartmentWorkflows.crossesBranch')}</Pill>
                )}
                {l.crosses_enterprise && (
                  <Pill color="violet">→ {t('templatesFnewDepartmentWorkflows.crossesEnterprise')}</Pill>
                )}
                {l.crosses_division && (
                  <Pill color="rose">→ {t('templatesFnewDepartmentWorkflows.crossesDivision')}</Pill>
                )}
              </div>
            </div>
          );
        })}
        {links.length > 10 && (
          <p className="text-[11px] text-[var(--text-secondary)] italic text-center pt-2">
            {t('templatesFnewDepartmentWorkflows.crossLinkMore', { count: String(links.length - 10) })}
          </p>
        )}
      </div>
    </div>
  );
}

function Pill({ color, children }: { color: 'amber' | 'blue' | 'violet' | 'rose'; children: React.ReactNode }) {
  const cls = {
    amber:  'bg-amber-50 text-amber-700 border-amber-200',
    blue:   'bg-blue-50 text-blue-700 border-blue-200',
    violet: 'bg-violet-50 text-violet-700 border-violet-200',
    rose:   'bg-rose-50 text-rose-700 border-rose-200',
  }[color];
  return (
    <span className={cn('inline-flex items-center text-[10px] font-medium px-1.5 py-0.5 rounded border', cls)}>
      {children}
    </span>
  );
}
