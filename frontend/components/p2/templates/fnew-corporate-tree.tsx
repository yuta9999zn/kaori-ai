// @ts-nocheck — template wiring; tighten when proper component lib lands.
'use client';

// ============================================================================
// /p2/org-tree — Cơ cấu tổ chức (P15-S11 Tuần 8 — Vingroup-class)
// ----------------------------------------------------------------------------
// Per anh's directive 2026-05-15: cây phả hệ tập đoàn → mảng → công ty con
// → chi nhánh → phòng ban. Khách hàng kéo thả + click phòng ban tạo workflow.
//
// Phase 1 UX (Build Week):
//   - Tree column (left) — collapsible Group → Divisions → Enterprises.
//   - Inspector (right) — when an enterprise is selected, fetch + show
//     its branches + departments. "Tạo workflow tại phòng X" CTA per dept.
//   - "Di chuyển" select dropdown on enterprise inspector — calls
//     PUT /enterprises/{id}/parent for re-parenting (no full drag-drop —
//     Phase 2 with React Flow).
//
// Backend (ai-orchestrator/routers/corporate_tree.py):
//   GET  /api/v1/corporate-tree/nested
//   GET  /api/v1/enterprises/{id}/org-detail   ← branches + departments
//   PUT  /api/v1/enterprises/{id}/parent       ← re-parent
//   POST /api/v1/corporate-groups, /business-divisions  (Phase 2 inline)
// ============================================================================

import React, { useEffect, useMemo, useState, useCallback } from 'react';
import {
  Building2, Factory, Store, ChevronRight, ChevronDown,
  Workflow as WorkflowIcon, Loader2, Plus, ArrowRightLeft,
  Briefcase, Users, FileText, AlertCircle,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, SuccessBanner, api, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { SkeletonOrgTree } from '@/components/p2/skeleton';
import { SUCCESS } from '@/lib/i18n/messages';

// ─── Types mirror BE shapes ──────────────────────────────────────────

type NodeType = 'group' | 'division' | 'enterprise';

interface TreeNode {
  node_type:    NodeType;
  node_id:      string;
  parent_id:    string | null;
  name:         string;
  display_name: string;
  status:       string;
  sort_order:   number;
  level:        number;
  children:     TreeNode[];
}

interface NestedTreeResponse {
  roots: TreeNode[];
  count: number;
}

interface OrgDetail {
  enterprise: {
    enterprise_id:        string;
    name:                 string;
    industry:             string | null;
    status:               string;
    corporate_group_id:   string | null;
    business_division_id: string | null;
    parent_enterprise_id: string | null;
  };
  branches:    Array<{
    branch_id: string; name: string; code: string | null;
    is_default: boolean; timezone: string; status: string;
  }>;
  departments: Array<{
    department_id: string; branch_id: string | null;
    name: string; dept_type: string; status: string;
    pii_sensitivity: string; description: string | null;
  }>;
}

const DEPT_LABEL: Record<string, string> = {
  marketing:        'Marketing',
  sales:            'Sales',
  customer_service: 'CSKH',
  warehouse:        'Kho vận',
  hr:               'Nhân sự',
  finance:          'Tài chính',
  custom:           'Tùy chỉnh',
};

const NODE_ICON: Record<NodeType, React.ComponentType<any>> = {
  group:      Building2,
  division:   Briefcase,
  enterprise: Store,
};

const NODE_LABEL: Record<NodeType, string> = {
  group:      'Tập đoàn',
  division:   'Mảng kinh doanh',
  enterprise: 'Công ty',
};

// ─── Page ──────────────────────────────────────────────────────────

export default function CorporateTreePage() {
  const [tree, setTree] = useState<NestedTreeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<TreeNode | null>(null);

  const loadTree = useCallback(async () => {
    setLoading(true);
    try {
      const t = await api<NestedTreeResponse>('/api/v1/corporate-tree/nested');
      setTree(t);
      // Auto-expand root + first level so demo has something to look at.
      const ids = new Set<string>();
      for (const r of t.roots) {
        ids.add(r.node_id);
        for (const c of r.children) ids.add(c.node_id);
      }
      setExpanded(ids);
    } catch (e: any) {
      setProblem(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadTree(); }, [loadTree]);

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  const allDivisions = useMemo(() => {
    if (!tree) return [];
    const out: TreeNode[] = [];
    function walk(n: TreeNode) {
      if (n.node_type === 'division') out.push(n);
      n.children.forEach(walk);
    }
    tree.roots.forEach(walk);
    return out;
  }, [tree]);

  async function reparentTo(enterpriseId: string, divisionId: string) {
    setProblem(null); setSuccess(null);
    try {
      await api(`/api/v1/enterprises/${enterpriseId}/parent`, {
        method: 'PUT',
        body: JSON.stringify({ business_division_id: divisionId }),
      });
      setSuccess(SUCCESS.enterprise_moved);
      await loadTree();
    } catch (e: any) {
      setProblem(e);
    }
  }

  return (
    <>
      <PageHeader
        title="Cơ cấu tổ chức"
        description="Cây phả hệ tập đoàn → mảng → công ty con → chi nhánh → phòng ban. Click phòng ban để tạo workflow."
        actions={
          <Badge variant="info">Đa cấp tổ chức</Badge>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1500px] mx-auto space-y-4">
        {problem && <ErrorBanner problem={problem} />}
        {success && <SuccessBanner message={success} />}

        {loading && !tree ? (
          <div className="grid grid-cols-1 xl:grid-cols-[1fr_440px] gap-4">
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-4">
              <SkeletonOrgTree />
            </div>
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 min-h-[300px]" />
          </div>
        ) : !tree || tree.count === 0 ? (
          <EmptyState />
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-[1fr_440px] gap-4">
            <TreeColumn
              roots={tree.roots}
              expanded={expanded}
              selectedId={selected?.node_id ?? null}
              onToggle={toggle}
              onSelect={setSelected}
            />
            <InspectorColumn
              node={selected}
              divisions={allDivisions}
              onReparent={reparentTo}
            />
          </div>
        )}
      </div>
    </>
  );
}

// ─── TreeColumn ────────────────────────────────────────────────────

function TreeColumn({
  roots, expanded, selectedId, onToggle, onSelect,
}: {
  roots: TreeNode[];
  expanded: Set<string>;
  selectedId: string | null;
  onToggle: (id: string) => void;
  onSelect: (n: TreeNode) => void;
}) {
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
      <div className="border-b border-[var(--border-color)] px-4 py-2 bg-[var(--bg-app)]">
        <span className="text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
          <Building2 className="w-4 h-4 inline mr-1.5" /> Cây phả hệ
        </span>
      </div>
      <div className="p-4">
        {roots.map((r) => (
          <TreeRow
            key={r.node_id}
            node={r}
            depth={0}
            expanded={expanded}
            selectedId={selectedId}
            onToggle={onToggle}
            onSelect={onSelect}
          />
        ))}
      </div>
    </div>
  );
}

function TreeRow({
  node, depth, expanded, selectedId, onToggle, onSelect,
}: {
  node: TreeNode; depth: number;
  expanded: Set<string>; selectedId: string | null;
  onToggle: (id: string) => void; onSelect: (n: TreeNode) => void;
}) {
  const Icon = NODE_ICON[node.node_type];
  const isOpen = expanded.has(node.node_id);
  const hasChildren = node.children.length > 0;
  const isSelected = selectedId === node.node_id;

  return (
    <div>
      <button
        onClick={() => onSelect(node)}
        className={cn(
          'group w-full flex items-center gap-2 px-2 py-1.5 rounded-md-custom text-left transition-colors',
          isSelected
            ? 'bg-[var(--primary-gold)]/15 border border-[var(--primary-gold)]/40'
            : 'hover:bg-[var(--bg-app)] border border-transparent',
        )}
        style={{ paddingLeft: `${0.5 + depth * 1.25}rem` }}
      >
        {hasChildren ? (
          <span
            onClick={(e) => { e.stopPropagation(); onToggle(node.node_id); }}
            className="p-0.5 hover:bg-[var(--bg-card)] rounded cursor-pointer"
          >
            {isOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
          </span>
        ) : (
          <span className="w-4" />
        )}
        <Icon className={cn(
          'w-4 h-4 shrink-0',
          node.node_type === 'group'      && 'text-[var(--primary-gold-dark)]',
          node.node_type === 'division'   && 'text-blue-700',
          node.node_type === 'enterprise' && 'text-emerald-700',
        )} />
        <div className="flex-1 min-w-0">
          <span className="text-sm font-medium text-[var(--text-primary)] truncate">
            {node.display_name}
          </span>
        </div>
        <span className="text-[10px] text-[var(--text-secondary)] shrink-0 hidden sm:inline">
          {NODE_LABEL[node.node_type]}
        </span>
        {hasChildren && (
          <span className="text-[10px] text-[var(--text-secondary)] shrink-0">
            ({node.children.length})
          </span>
        )}
      </button>

      {isOpen && hasChildren && (
        <div>
          {node.children.map((c) => (
            <TreeRow
              key={c.node_id}
              node={c}
              depth={depth + 1}
              expanded={expanded}
              selectedId={selectedId}
              onToggle={onToggle}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ─── InspectorColumn ───────────────────────────────────────────────

function InspectorColumn({
  node, divisions, onReparent,
}: {
  node: TreeNode | null;
  divisions: TreeNode[];
  onReparent: (enterpriseId: string, divisionId: string) => void;
}) {
  if (!node) {
    return (
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Briefcase className="w-10 h-10 text-[var(--text-secondary)]/30 mb-2" />
          <p className="text-sm text-[var(--text-secondary)]">Chọn 1 nút trong cây để xem chi tiết.</p>
        </div>
      </div>
    );
  }

  if (node.node_type !== 'enterprise') {
    return (
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm space-y-3">
        <div className="flex items-center gap-2 pb-3 border-b border-[var(--border-color)]/60">
          {React.createElement(NODE_ICON[node.node_type], { className: 'w-5 h-5 text-[var(--primary-gold-dark)]' })}
          <div>
            <h3 className="font-serif text-base text-[var(--text-primary)]">{node.display_name}</h3>
            <p className="text-[11px] text-[var(--text-secondary)]">{NODE_LABEL[node.node_type]}</p>
          </div>
        </div>
        <div className="text-sm text-[var(--text-secondary)]">
          {node.children.length > 0 ? (
            <p>{node.children.length} {node.node_type === 'group' ? 'mảng kinh doanh' : 'công ty con'}</p>
          ) : (
            <p>Chưa có {node.node_type === 'group' ? 'mảng' : 'công ty con'} nào.</p>
          )}
        </div>
        <p className="text-[11px] text-[var(--text-secondary)] italic">
          Chọn 1 công ty (lá) để xem chi nhánh + phòng ban + tạo workflow.
        </p>
      </div>
    );
  }

  return <EnterpriseInspector node={node} divisions={divisions} onReparent={onReparent} />;
}

function EnterpriseInspector({
  node, divisions, onReparent,
}: {
  node: TreeNode;
  divisions: TreeNode[];
  onReparent: (enterpriseId: string, divisionId: string) => void;
}) {
  const [detail, setDetail] = useState<OrgDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [moveOpen, setMoveOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const d = await api<OrgDetail>(`/api/v1/enterprises/${node.node_id}/org-detail`);
        if (!cancelled) setDetail(d);
      } catch (e: any) {
        if (!cancelled) setProblem(e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [node.node_id]);

  const currentDivisionId = detail?.enterprise.business_division_id ?? null;

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm space-y-4 max-h-[760px] overflow-y-auto">
      <div className="flex items-center gap-2 pb-3 border-b border-[var(--border-color)]/60">
        <Store className="w-5 h-5 text-emerald-700" />
        <div className="flex-1 min-w-0">
          <h3 className="font-serif text-base text-[var(--text-primary)]">{node.display_name}</h3>
          <p className="text-[11px] text-[var(--text-secondary)]">Công ty con</p>
        </div>
        <Button size="sm" variant="tertiary" onClick={() => setMoveOpen((o) => !o)}>
          <ArrowRightLeft className="w-3.5 h-3.5 mr-1" /> Di chuyển
        </Button>
      </div>

      {moveOpen && (
        <div className="bg-[var(--bg-app)]/40 border border-[var(--border-color)] rounded-md-custom p-3 space-y-2">
          <p className="text-[11px] text-[var(--text-secondary)]">
            Chọn mảng kinh doanh mới — calls PUT /enterprises/{node.node_id.slice(0, 8)}…/parent.
          </p>
          <div className="grid grid-cols-2 gap-1.5">
            {divisions.map((d) => (
              <button
                key={d.node_id}
                disabled={d.node_id === currentDivisionId}
                onClick={() => { onReparent(node.node_id, d.node_id); setMoveOpen(false); }}
                className={cn(
                  'px-2 py-1.5 rounded-md-custom text-xs text-left transition-colors',
                  d.node_id === currentDivisionId
                    ? 'bg-[var(--primary-gold)]/15 cursor-not-allowed text-[var(--text-secondary)]'
                    : 'border border-[var(--border-color)] hover:border-[var(--primary-gold)]/40 hover:bg-[var(--bg-card)]',
                )}
              >
                {d.display_name}
                {d.node_id === currentDivisionId && <span className="ml-1 text-[10px]">(hiện tại)</span>}
              </button>
            ))}
          </div>
        </div>
      )}

      {problem && <ErrorBanner problem={problem} />}

      {loading ? (
        <div className="flex items-center justify-center py-8 text-[var(--text-secondary)]">
          <Loader2 className="w-4 h-4 animate-spin mr-2" /> Đang tải chi tiết…
        </div>
      ) : !detail ? null : (
        <>
          <section>
            <h4 className="text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)] mb-2">
              <Building2 className="w-3.5 h-3.5 inline mr-1" /> Chi nhánh ({detail.branches.length})
            </h4>
            <div className="space-y-1">
              {detail.branches.length === 0 ? (
                <p className="text-[11px] italic text-[var(--text-secondary)]">Chưa có chi nhánh.</p>
              ) : detail.branches.map((b) => (
                <div key={b.branch_id} className="flex items-center justify-between gap-2 px-2 py-1.5 rounded hover:bg-[var(--bg-app)]/50 text-sm">
                  <span className="font-medium text-[var(--text-primary)]">{b.name}</span>
                  <div className="flex items-center gap-1.5 text-[10px] text-[var(--text-secondary)]">
                    {b.code && <span className="font-mono">{b.code}</span>}
                    {b.is_default && <Badge variant="default">Mặc định</Badge>}
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h4 className="text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)] mb-2">
              <Users className="w-3.5 h-3.5 inline mr-1" /> Phòng ban ({detail.departments.length})
            </h4>
            <div className="space-y-1.5">
              {detail.departments.length === 0 ? (
                <p className="text-[11px] italic text-[var(--text-secondary)]">Chưa có phòng ban.</p>
              ) : detail.departments.map((d) => (
                <div
                  key={d.department_id}
                  className="flex items-center justify-between gap-2 px-2.5 py-2 rounded-md-custom border border-[var(--border-color)] hover:border-[var(--primary-gold)]/40 hover:bg-[var(--bg-app)]/50 transition-colors"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-[var(--text-primary)] truncate">{d.name}</p>
                    <p className="text-[10px] text-[var(--text-secondary)]">{DEPT_LABEL[d.dept_type] || d.dept_type}</p>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <a href={`/p2/departments/${d.department_id}/workflows`}>
                      <Button size="sm" variant="tertiary">
                        <WorkflowIcon className="w-3 h-3 mr-1" /> Xem workflow
                      </Button>
                    </a>
                    <a href={`/p2/workflows/new?department_id=${d.department_id}&enterprise_id=${detail.enterprise.enterprise_id}`}>
                      <Button size="sm" variant="secondary">
                        <Plus className="w-3 h-3 mr-1" /> Tạo mới
                      </Button>
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

// ─── EmptyState ────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom py-16 text-center px-6">
      <Building2 className="w-12 h-12 mx-auto text-[var(--text-secondary)]/40 mb-3" />
      <h3 className="font-serif text-lg text-[var(--text-primary)] mb-2">Chưa có cơ cấu tổ chức</h3>
      <p className="text-sm text-[var(--text-secondary)] max-w-md mx-auto mb-4">
        Workspace của anh chưa khai báo tập đoàn. Apply migration 056 để có demo Vingroup, hoặc tạo
        tập đoàn mới qua API <code className="text-xs font-mono bg-[var(--bg-app)] px-1 py-0.5 rounded">POST /api/v1/corporate-groups</code>.
      </p>
      <div className="text-[11px] text-[var(--text-secondary)] flex items-center justify-center gap-1.5">
        <AlertCircle className="w-3.5 h-3.5" />
        FE inline creation đang đợi Tuần 9 polish.
      </div>
    </div>
  );
}
