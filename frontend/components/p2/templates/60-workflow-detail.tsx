// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 60. /p2/workflows/[id] — Workflow Builder + Tree Viewer
//                          (P15-S11 Tuần 8 — anh's pivot 2026-05-15)
// ----------------------------------------------------------------------------
// Two-tab page on the same workflow:
//
//   TAB "Builder" — vertical chain of CARDS (steps). Click → edit drawer
//     with title + Vietnamese title + note + hashtags + required documents.
//     Reorder via up/down chevrons (drag-drop is Phase 2 polish).
//
//   TAB "Cây tài liệu" — 3-tier document tree (ADR-0037 Tier-3): each step →
//     📥 đầu vào / 📤 đầu ra / 📎 tham chiếu, each requirement carrying its
//     current document's status badge + version count. From
//     GET /workflows/{id}/document-tree (routers/workflow_documents.py).
//
// Backend (ai-orchestrator/routers/workflow_builder.py + workflow_documents.py):
//   GET  /api/v1/workflows/{id}                    — workflow header
//   GET  /api/v1/workflows/{id}/tree               — flat workflow → cards → docs (legacy)
//   GET  /api/v1/workflows/{id}/document-tree      — 3-tier classified + status + version
//   POST /api/v1/workflows/{id}/nodes              — add card
//   PUT  /api/v1/workflows/{id}/nodes/{nid}        — edit card
//   DELETE /api/v1/workflows/{id}/nodes/{nid}      — remove card
//   POST /api/v1/workflows/{id}/edges              — connect cards (sequence)
// ============================================================================

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Workflow as WorkflowIcon, ArrowLeft, Save, Plus,
  ArrowDown, Trash2, Hash, FileText, ChevronUp, ChevronDown,
  Layers, Upload, ExternalLink, Loader2, X, Tag, FilePlus, Edit3,
  GitBranch, ArrowRight, Network, Building2, Briefcase,
  PlayCircle, PauseCircle, Archive, RotateCcw, CheckCircle2,
  // Path B node icons
  Clock, AlarmClock, Split, Merge, Bell, Boxes,
} from 'lucide-react';

import {
  Button, Badge, Input, ErrorBanner, SuccessBanner, api, cn, API_BASE,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { SkeletonWorkflowDetail, SkeletonTreeTab, SkeletonReportsTab } from '@/components/p2/skeleton';
import { formatProblem, SUCCESS } from '@/lib/i18n/messages';
import BpmnPanel from '@/components/bpmn/BpmnPanel';
import LinearBuilderView from '@/components/p2/workflow/LinearBuilderView';

// ─── Shapes mirror BE response ───────────────────────────────────

interface WorkflowOut {
  workflow_id:      string;
  enterprise_id:    string;
  department_id:    string;
  branch_id:        string | null;
  name:             string;
  name_vi:          string | null;
  description:      string | null;
  category:         string | null;
  state:            string;
  version:          number;
  source:           string;
  created_at:       string;
  last_modified_at: string;
}

interface RequiredDoc { kind: string; name: string; required: boolean }

// Path B 2026-05-15 — 10 enterprise node types (4 cũ + 6 mới: wait_event /
// sla_timer / parallel_split / parallel_join / subworkflow / notification).
// Schema codes giữ nguyên kỹ thuật; UI labels relabel sang ngôn ngữ
// business (Quyết định / Phân loại / Phê duyệt / Chờ sự kiện / Hạn xử lý /
// Chạy song song / Hợp nhánh / Quy trình con / Thông báo).
type WorkflowNodeType =
  | 'step'
  | 'decision_if_else'
  | 'decision_switch'
  | 'approval_gate'
  | 'wait_event'
  | 'sla_timer'
  | 'parallel_split'
  | 'parallel_join'
  | 'subworkflow'
  | 'notification';

interface CardNode {
  node_id:                 string;
  workflow_id:             string;
  title:                   string;
  title_vi:                string | null;
  note:                    string | null;
  hashtags:                string[];
  required_document_types: RequiredDoc[];
  expected_mapping_template_id: string | null;
  node_type:               WorkflowNodeType | string;
  category:                string;
  side_effect_class:       string;
  position_x:              number;
  position_y:              number;
  sequence_order:          number;
  decision_config?:        Record<string, any>;
  attached_documents?:     AttachedDoc[];   // only present in tree response
}

interface AttachedDoc {
  attachment_id: string;
  file_id:       string;
  filename:      string;
  row_count:     number;
  sha256:        string;
  document_kind: string | null;
  uploaded_at:   string | null;
  uploaded_by:   string | null;
  notes:         string | null;
}

interface EdgeOut {
  edge_id:        string;
  source_node_id: string;
  target_node_id: string;
  condition:      string | null;
  label:          string | null;
  port_type?:     string;            // ADR-0035 B5 — 'main' (default) | ai_tool/ai_memory/ai_model
}

interface TreeResponse {
  workflow: WorkflowOut;
  nodes:    CardNode[];
  edges:    EdgeOut[];
}

// ─── Page ────────────────────────────────────────────────────────

export default function WorkflowDetailPage({ workflowId }: { workflowId: string }) {
  const [tab, setTab] = useState<'builder' | 'bpmn' | 'tree' | 'reports'>('builder');
  const [tree, setTree] = useState<TreeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [selectedCardId, setSelectedCardId] = useState<string | null>(null);
  // UAT #14 — feedback controls for state transitions.
  const [confirmingTransition, setConfirmingTransition] = useState<string | null>(null);
  const [transitionBusy, setTransitionBusy] = useState(false);
  const [toast, setToast] = useState<{ kind: 'success' | 'error'; msg: string } | null>(null);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4500);
    return () => clearTimeout(t);
  }, [toast]);

  const loadTree = useCallback(async () => {
    setLoading(true);
    try {
      const t = await api<TreeResponse>(`/api/v1/workflows/${workflowId}/tree`);
      setTree(t);
      if (!selectedCardId && t.nodes.length > 0) setSelectedCardId(t.nodes[0].node_id);
    } catch (e: any) {
      setProblem(e);
    } finally {
      setLoading(false);
    }
  }, [workflowId, selectedCardId]);

  useEffect(() => { loadTree(); }, [loadTree]);

  const cards = tree?.nodes ?? [];
  const sortedCards = useMemo(
    () => [...cards].sort((a, b) => a.sequence_order - b.sequence_order),
    [cards],
  );
  const selected = useMemo(
    () => sortedCards.find((n) => n.node_id === selectedCardId) ?? null,
    [sortedCards, selectedCardId],
  );

  // ─── card mutations ─────────────────────────────────────

  async function addCard() {
    // Persist any in-flight node edit before we POST + reload the tree, so the
    // reload doesn't clobber an un-flushed action/field change (the
    // "action resets to Chưa gán" race when adding a step mid-edit).
    await flushAll();
    const nextOrder = (sortedCards.at(-1)?.sequence_order ?? 0) + 1;
    // Where to attach the new step? NOT sortedCards.at(-1): the highest
    // sequence_order node is often the tail of whichever BRANCH sorts last
    // (e.g. a switch's `default` branch), so wiring from it chained every new
    // step onto that branch — the phantom "Bước 9→…→14" chain anh saw, which
    // then propagated straight into the BPMN diagram. Attach to the real
    // MAIN-flow tail instead: a node with no outgoing 'main' edge that is not
    // itself a fork. Only auto-wire when that tail is UNAMBIGUOUS (exactly one
    // open end); with multiple open branch ends we leave the step unattached
    // and let the user pick which branch it belongs to.
    const FORK_TYPES = ['decision_if_else', 'decision_switch', 'parallel_split'];
    const mainEdges = (tree?.edges ?? []).filter((e) => (e.port_type ?? 'main') === 'main');
    const hasMainOut = new Set(mainEdges.map((e) => String(e.source_node_id)));
    const openEnds = sortedCards.filter(
      (c) => !hasMainOut.has(String(c.node_id)) && !FORK_TYPES.includes(c.node_type),
    );
    try {
      const created = await api<CardNode>(`/api/v1/workflows/${workflowId}/nodes`, {
        method: 'POST',
        body: JSON.stringify({
          title: `Bước ${nextOrder}`,
          title_vi: `Bước ${nextOrder}`,
          note: '',
          hashtags: [],
          required_document_types: [],
          sequence_order: nextOrder,
          position_x: 100 + (nextOrder - 1) * 220,
          position_y: 100,
        }),
      });
      const autoWired = openEnds.length === 1;
      if (autoWired) {
        try {
          await api(`/api/v1/workflows/${workflowId}/edges`, {
            method: 'POST',
            body: JSON.stringify({
              source_node_id: openEnds[0].node_id,
              target_node_id: created.node_id,
              label: 'next',
              port_type: 'main',
            }),
          });
        } catch { /* edge add is best-effort */ }
      }
      await loadTree();
      setSelectedCardId(created.node_id);
      if (autoWired || sortedCards.length === 0) {
        setSuccess(SUCCESS.node_added);
      } else {
        // No single trunk tail → don't guess a branch. Tell the user to wire it.
        setToast({
          kind: 'success',
          msg: 'Đã thêm bước — workflow đang có nhiều nhánh/điểm cuối nên bước mới chưa tự nối. Hãy nối nó vào nhánh mong muốn.',
        });
      }
    } catch (e: any) {
      setProblem(e);
    }
  }

  // Debounced node-update with optimistic local apply.
  //
  // Each onChange in the CardEditor fires updateCard → we (a) apply the
  // patch locally so the UI stays responsive, (b) accumulate patches
  // per node in a ref, (c) restart a 600ms timer that flushes the
  // accumulated patch to BE. This collapses bursts of keystrokes into
  // a single PUT — avoids the gateway rate limit (60/min) tripping and
  // avoids race conditions where mid-edit empty strings reach BE.
  const pendingPatchesRef = useRef<Record<string, Partial<CardNode>>>({});
  const debounceTimerRef  = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const treeRef = useRef(tree);
  useEffect(() => { treeRef.current = tree; }, [tree]);
  const DEBOUNCE_MS = 600;

  const flushPatch = useCallback(async (nodeId: string) => {
    const patch = pendingPatchesRef.current[nodeId];
    if (!patch || Object.keys(patch).length === 0) return;
    delete pendingPatchesRef.current[nodeId];
    // pendingPatchesRef already holds the FULL merged decision_config (built in
    // updateCard from tree ∪ prior-pending ∪ this-edit), so send it directly. We
    // do NOT re-read the tree here — a tree reload from an unrelated op
    // (addCard / edge wiring while building a loop) could have stripped a field
    // that hasn't flushed yet. The pending ref is independent of those reloads,
    // so the user's edits survive (the loop `item_var` loss).
    try {
      await api(`/api/v1/workflows/${workflowId}/nodes/${nodeId}`, {
        method: 'PUT',
        body: JSON.stringify(patch),
      });
    } catch (e: any) {
      setProblem(e);
    }
  }, [workflowId]);

  function updateCard(nodeId: string, patch: Partial<CardNode>) {
    // Optimistic local apply + accumulate the FULL merged decision_config into
    // pendingPatchesRef. decision_config is a UNION of: the latest tree value
    // (BE + optimistic) ∪ prior unsent pending edits ∪ this edit (this wins).
    // Computed inside the updater so `prev` is the latest committed tree, and
    // the union with prior-pending means a tree reload between edits can't strip
    // an unsent field (if_else `left` / switch `input` / loop `item_var` loss).
    setTree((prev) => {
      if (!prev) return prev;
      const nodes = prev.nodes.map((n) => {
        if (n.node_id !== nodeId) return n;
        const prevPending: any = pendingPatchesRef.current[nodeId] ?? {};
        let nextDC: any;
        if ((patch as any).decision_config) {
          const treeDC = (n as any).decision_config || {};
          const pendDC = prevPending.decision_config || {};
          const inc = (patch as any).decision_config || {};
          nextDC = { ...treeDC, ...pendDC, ...inc };
          const cond = { ...(treeDC.condition || {}), ...(pendDC.condition || {}), ...(inc.condition || {}) };
          if (Object.keys(cond).length) nextDC.condition = cond;
        }
        pendingPatchesRef.current[nodeId] = {
          ...prevPending, ...patch,
          ...(nextDC ? { decision_config: nextDC } : {}),
        };
        return { ...n, ...patch, ...(nextDC ? { decision_config: nextDC } : {}) };
      });
      return { ...prev, nodes };
    });

    // 3. Restart debounce timer.
    const existing = debounceTimerRef.current[nodeId];
    if (existing) clearTimeout(existing);
    debounceTimerRef.current[nodeId] = setTimeout(() => {
      void flushPatch(nodeId);
    }, DEBOUNCE_MS);
  }

  // Flush ALL pending debounced node edits NOW (cancel their 600ms timers and
  // PUT immediately). Call before any op that reloads the tree (addCard /
  // deleteCard / edge wiring): otherwise loadTree overwrites the optimistic
  // local state with a BE snapshot that predates the in-flight edit — the race
  // where picking a Kaori action then clicking "Thêm bước" reset the action
  // dropdown back to "Chưa gán".
  const flushAll = useCallback(async () => {
    Object.values(debounceTimerRef.current).forEach((t) => t && clearTimeout(t));
    debounceTimerRef.current = {};
    await Promise.all(
      Object.keys(pendingPatchesRef.current).map((id) => flushPatch(id)),
    );
  }, [flushPatch]);

  async function deleteCard(nodeId: string) {
    await flushAll();
    if (!confirm('Xoá bước này khỏi workflow? Tài liệu đã upload không bị xoá khỏi Bronze.')) return;
    try {
      await api(`/api/v1/workflows/${workflowId}/nodes/${nodeId}`, { method: 'DELETE' });
      await loadTree();
      if (selectedCardId === nodeId) setSelectedCardId(null);
      setSuccess(SUCCESS.node_deleted);
    } catch (e: any) {
      setProblem(e);
    }
  }

  // P0 (WORKFLOW_BUILDER_REDESIGN §6) — bind a decision branch to a real target
  // node by creating/deleting a workflow_edge. The branch's target_node_id in
  // decision_config is the UI mirror; the EDGE is the source-of-truth topology
  // the runner + dangling-branch validator read. Reconcile = drop the old edge
  // (matched by source + previous target) then upsert the new one.
  async function setBranchEdge(args: {
    sourceId: string; oldTarget?: string | null; newTarget: string | null;
    condition?: string | null; label?: string | null;
  }) {
    const { sourceId, oldTarget, newTarget, condition, label } = args;
    try {
      if (oldTarget && oldTarget !== newTarget) {
        const stale = (tree?.edges ?? []).find(
          (e) => String(e.source_node_id) === String(sourceId) &&
                 String(e.target_node_id) === String(oldTarget),
        );
        if (stale) {
          await api(`/api/v1/workflows/${workflowId}/edges/${stale.edge_id}`, { method: 'DELETE' });
        }
      }
      if (newTarget) {
        await api(`/api/v1/workflows/${workflowId}/edges`, {
          method: 'POST',
          body: JSON.stringify({
            source_node_id: sourceId,
            target_node_id: newTarget,
            condition: condition || null,
            label: label || null,
            port_type: 'main',
          }),
        });
      }
      await loadTree();
    } catch (e: any) {
      setProblem(e);
    }
  }

  // ─── Run workflow (commit 1 BE — POST /workflows/{id}/run) ─────────
  // The Run button fires the in-process executor. Backend pre-flight
  // rejects with 422 + missing_node_types[] if any node lacks an
  // executor — we surface those node types so the manager knows the gap.
  const [runBusy, setRunBusy] = useState(false);
  const [lastRunId, setLastRunId] = useState<string | null>(null);

  async function runWorkflow() {
    setSuccess(null); setProblem(null); setRunBusy(true);
    try {
      const idemKey = `wf-run-${workflowId}-${Date.now()}`;
      const resp = await api(`/api/v1/workflows/${workflowId}/run`, {
        method: 'POST',
        headers: { 'Idempotency-Key': idemKey },
        body: JSON.stringify({
          input_data: {},
          trigger_source: 'manual',
        }),
      });
      const runId = resp?.run_id;
      if (runId) {
        setLastRunId(runId);
        setSuccess(`Đã khởi chạy workflow. Run ID: ${runId}`);
        setToast({ kind: 'success', msg: 'Workflow đang chạy — kiểm tra tab Lịch sử chạy.' });
      } else {
        setSuccess('Workflow được khởi chạy nhưng không nhận được run_id.');
      }
    } catch (e: any) {
      setProblem(e);
      // Pre-flight 422: list missing node types so the user knows what
      // needs implementation in the next executor wave.
      const missing = Array.isArray(e?.missing_node_types) ? e.missing_node_types : [];
      const errMsg = missing.length
        ? `Workflow có node chưa có executor: ${missing.join(', ')}`
        : e?.title || 'Không thể khởi chạy workflow.';
      setToast({ kind: 'error', msg: errMsg });
    } finally {
      setRunBusy(false);
    }
  }

  async function transitionState(targetState: string) {
    setSuccess(null); setProblem(null);
    setTransitionBusy(true);
    try {
      await api(`/api/v1/workflows/${workflowId}`, {
        method: 'PUT',
        body: JSON.stringify({ state: targetState }),
      });
      await loadTree();
      const label: Record<string, string> = {
        DRAFT: 'Đã chuyển về bản nháp.',
        TESTING: 'Đã chuyển sang trạng thái Test.',
        ACTIVE_BASELINE: 'Đã kích hoạt workflow.',
        ARCHIVED: 'Đã lưu trữ workflow.',
      };
      const msg = label[targetState] || 'Đã cập nhật trạng thái.';
      setSuccess(msg);
      setToast({ kind: 'success', msg });
      if (typeof window !== 'undefined') window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (e: any) {
      setProblem(e);
      // RFC 7807 dangling-branch envelope carries .issues[] — surface the
      // first one in the toast so the manager doesn't have to scroll.
      const firstIssue = Array.isArray(e?.issues) && e.issues[0]
        ? `${e.issues[0].node_type ?? 'Node'} cần thêm nhánh`
        : null;
      const errMsg = e?.title || firstIssue || 'Không thể cập nhật trạng thái.';
      setToast({ kind: 'error', msg: errMsg });
      if (typeof window !== 'undefined') window.scrollTo({ top: 0, behavior: 'smooth' });
    } finally {
      setTransitionBusy(false);
      setConfirmingTransition(null);
    }
  }

  // UAT #14 — pre-flight checks for ACTIVE_BASELINE so we can disable the
  // activate button + tell the manager why. Mirrors the BE dangling-branch
  // guard (K-17 decision nodes must have all branches wired).
  const activationBlockers = useMemo<string[]>(() => {
    if (!tree) return [];
    const issues: string[] = [];
    if (sortedCards.length === 0) {
      issues.push('Workflow chưa có bước nào — thêm ít nhất 1 bước trước khi kích hoạt.');
      return issues;
    }
    // Count only 'main' (data-flow) edges — ai_* side ports (ADR-0035) aren't
    // flow steps. Thresholds mirror the BE dangling-branch validator
    // (workflow_builder.py): if_else ≥2, switch ≥(cases+default), split ≥2.
    // BE stays the authoritative gate (PUT state surfaces .issues[]); this is
    // the inline pre-flight so the manager sees gaps without clicking activate.
    const outDegree: Record<string, number> = {};
    for (const e of tree.edges) {
      if ((e.port_type ?? 'main') !== 'main') continue;
      outDegree[e.source_node_id] = (outDegree[e.source_node_id] ?? 0) + 1;
    }
    for (const n of sortedCards) {
      const out = outDegree[n.node_id] ?? 0;
      const lbl = n.title_vi || n.title || 'Bước chưa đặt tên';
      const cfg = n.decision_config ?? {};
      if (n.node_type === 'decision_if_else' && out < 2) {
        issues.push(`"${lbl}" (Quyết định) cần ≥2 nhánh nối tới bước — hiện ${out}.`);
      } else if (n.node_type === 'decision_switch') {
        const need = Math.max(2, (Array.isArray(cfg.cases) ? cfg.cases.length : 0) + (cfg.default ? 1 : 0));
        if (out < need) issues.push(`"${lbl}" (Phân loại) cần ${need} nhánh (case + default) — hiện ${out}.`);
      } else if (n.node_type === 'parallel_split') {
        const need = Math.max(2, Number(cfg.branch_count ?? 2));
        if (out < need) issues.push(`"${lbl}" (Chạy song song) cần ${need} nhánh — hiện ${out}.`);
      } else if (n.node_type === 'approval_gate' || n.node_type_catalog_key === 'approval_gate') {
        // The linear builder stores "Phê duyệt" on node_type_catalog_key while
        // node_type stays 'step' — detect the gate by either field.
        if (out < 1) issues.push(`"${lbl}" (Phê duyệt) cần ít nhất 1 bước kế tiếp.`);
        const hasChain = !!cfg.approval_chain_id;
        const hasRole = Array.isArray(cfg.approver_role)
          ? cfg.approver_role.some((r: any) => String(r).trim())
          : !!String(cfg.approver_role ?? '').trim();
        if (!hasChain && !hasRole) {
          issues.push(`"${lbl}" (Phê duyệt) chưa gắn chuỗi duyệt hoặc vai trò — cổng rỗng quyền.`);
        }
      }
    }
    return issues;
  }, [tree, sortedCards]);
  const canActivate = activationBlockers.length === 0;

  async function moveCard(nodeId: string, dir: -1 | 1) {
    const idx = sortedCards.findIndex((n) => n.node_id === nodeId);
    const swap = sortedCards[idx + dir];
    if (!swap) return;
    const a = sortedCards[idx];
    try {
      await Promise.all([
        api(`/api/v1/workflows/${workflowId}/nodes/${a.node_id}`, {
          method: 'PUT',
          body: JSON.stringify({ sequence_order: swap.sequence_order }),
        }),
        api(`/api/v1/workflows/${workflowId}/nodes/${swap.node_id}`, {
          method: 'PUT',
          body: JSON.stringify({ sequence_order: a.sequence_order }),
        }),
      ]);
      await loadTree();
    } catch (e: any) {
      setProblem(e);
    }
  }

  if (loading && !tree) {
    return (
      <>
        <PageHeader title="Đang tải workflow…" description="" />
        <div className="px-6 lg:px-8 py-6 max-w-[1500px] mx-auto">
          <SkeletonWorkflowDetail />
        </div>
      </>
    );
  }

  if (!tree) {
    return (
      <>
        <PageHeader title="Không mở được workflow" description="" />
        <div className="px-6 lg:px-8 py-6 max-w-2xl mx-auto">
          <ErrorBanner
            problem={problem || { title: formatProblem({ status: 404 }) }}
          />
          <div className="mt-4 text-center">
            <a href="/p2/workflows">
              <Button variant="primary" size="md">
                <ArrowLeft className="w-4 h-4 mr-2" /> Quay lại danh sách
              </Button>
            </a>
          </div>
        </div>
      </>
    );
  }

  const wf = tree.workflow;

  return (
    <>
      <PageHeader
        title={wf.name_vi || wf.name}
        description={wf.description || `Workflow · ${sortedCards.length} bước · v${wf.version}`}
        actions={
          <>
            <Badge variant={
              wf.state === 'ACTIVE_BASELINE' ? 'success' :
              wf.state === 'TESTING'         ? 'warning' :
              wf.state === 'ARCHIVED'        ? 'default' :
              wf.state === 'BROKEN'          ? 'destructive' :
                                                'default'
            }>
              {wf.state === 'DRAFT'           ? 'Bản nháp' :
               wf.state === 'TESTING'         ? 'Đang test' :
               wf.state === 'ACTIVE_BASELINE' ? 'Đang chạy' :
               wf.state === 'ARCHIVED'        ? 'Đã lưu trữ' :
               wf.state}
            </Badge>

            {wf.state === 'DRAFT' && (
              <>
                <Button
                  variant="secondary" size="md"
                  onClick={() => transitionState('TESTING')}
                  title="Chuyển sang trạng thái test trước khi kích hoạt"
                  disabled={transitionBusy}
                >
                  <PlayCircle className="w-4 h-4 mr-2" /> Chạy thử
                </Button>
                <Button
                  variant="primary" size="md"
                  onClick={() => setConfirmingTransition('ACTIVE_BASELINE')}
                  disabled={!canActivate || transitionBusy}
                  title={canActivate
                    ? 'Kết thúc thiết kế và kích hoạt workflow'
                    : `Chưa thể kích hoạt: ${activationBlockers[0]}`}
                >
                  <CheckCircle2 className="w-4 h-4 mr-2" /> Kết thúc & Kích hoạt
                </Button>
              </>
            )}

            {wf.state === 'TESTING' && (
              <>
                <Button
                  variant="tertiary" size="md"
                  onClick={() => transitionState('DRAFT')}
                  disabled={transitionBusy}
                >
                  <RotateCcw className="w-4 h-4 mr-2" /> Quay lại nháp
                </Button>
                <Button
                  variant="primary" size="md"
                  onClick={() => setConfirmingTransition('ACTIVE_BASELINE')}
                  disabled={!canActivate || transitionBusy}
                  title={canActivate
                    ? 'Hoàn tất Test và kích hoạt workflow chính thức'
                    : `Chưa thể kích hoạt: ${activationBlockers[0]}`}
                >
                  <CheckCircle2 className="w-4 h-4 mr-2" /> Hoàn tất Test → Kích hoạt
                </Button>
              </>
            )}

            {wf.state === 'ACTIVE_BASELINE' && (
              <>
                <Button
                  variant="primary" size="md"
                  onClick={runWorkflow}
                  disabled={runBusy}
                  title="Chạy workflow ngay với input rỗng. Pre-flight kiểm tra node executor có đủ không."
                >
                  {runBusy
                    ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Đang khởi chạy…</>
                    : <><PlayCircle className="w-4 h-4 mr-2" /> Chạy ngay</>}
                </Button>
                <Button
                  variant="tertiary" size="md"
                  onClick={() => transitionState('DRAFT')}
                  title="Tạm dừng để chỉnh sửa"
                >
                  <PauseCircle className="w-4 h-4 mr-2" /> Tạm dừng
                </Button>
                <Button
                  variant="secondary" size="md"
                  onClick={() => {
                    if (confirm('Lưu trữ workflow này? Sẽ ẩn khỏi danh sách chính nhưng dữ liệu giữ nguyên.'))
                      transitionState('ARCHIVED');
                  }}
                >
                  <Archive className="w-4 h-4 mr-2" /> Lưu trữ
                </Button>
              </>
            )}

            {wf.state === 'ARCHIVED' && (
              <Button
                variant="secondary" size="md"
                onClick={() => transitionState('DRAFT')}
                title="Khôi phục workflow đã lưu trữ"
              >
                <RotateCcw className="w-4 h-4 mr-2" /> Khôi phục
              </Button>
            )}

            <a href="/p2/workflows">
              <Button variant="tertiary" size="md"><ArrowLeft className="w-4 h-4 mr-2" /> Danh sách</Button>
            </a>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1500px] mx-auto space-y-4">
        {problem && <ErrorBanner problem={problem} />}
        {success && <SuccessBanner message={success} />}

        {lastRunId && (
          <div
            role="status"
            className="flex items-center gap-3 p-3 rounded-md-custom bg-[var(--state-success)]/10 border border-[var(--state-success)]/30 text-[#166534]"
          >
            <PlayCircle className="h-5 w-5 shrink-0 text-[var(--state-success)]" />
            <div className="flex-1 min-w-0 text-sm">
              <span className="font-medium">Run đang chạy:</span>{' '}
              <code className="text-xs bg-white/70 px-2 py-0.5 rounded">{lastRunId}</code>{' '}
              · Trạng thái cập nhật trong tab Lịch sử chạy
            </div>
            <button
              onClick={() => setLastRunId(null)}
              className="text-xs px-2 py-1 hover:bg-white/60 rounded"
              aria-label="Đóng"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* UAT #14 — surface activation blockers inline so the manager
            sees them without hovering the button. */}
        {(wf.state === 'DRAFT' || wf.state === 'TESTING') && activationBlockers.length > 0 && (
          <div
            role="status"
            className="flex items-start gap-3 p-3 rounded-md-custom bg-[var(--state-warning)]/10 border border-[var(--state-warning)]/30 text-[#8B6914]"
          >
            <AlarmClock className="h-5 w-5 shrink-0 mt-0.5 text-[var(--state-warning)]" />
            <div className="flex-1 min-w-0 space-y-1">
              <p className="text-sm font-medium">Cần hoàn thiện trước khi kích hoạt:</p>
              <ul className="list-disc pl-4 text-xs space-y-0.5">
                {activationBlockers.slice(0, 5).map((b, i) => <li key={i}>{b}</li>)}
                {activationBlockers.length > 5 && (
                  <li className="opacity-70">…và {activationBlockers.length - 5} vấn đề khác.</li>
                )}
              </ul>
            </div>
          </div>
        )}

        <Tabs tab={tab} onChange={setTab} />

        {tab === 'builder' && (
          <LinearBuilderView
            workflowId={workflowId}
            cards={sortedCards}
            edges={tree.edges}
            onAddCard={addCard}
            onUpdate={updateCard}
            onDelete={deleteCard}
            onSetEdge={setBranchEdge}
            deptName={wf.department_name}
          />
        )}

        {tab === 'bpmn' && (
          <BpmnPanel workflowId={wf.workflow_id} />
        )}

        {tab === 'tree' && (
          <TreeView
            workflowId={wf.workflow_id}
            cards={sortedCards}
          />
        )}

        {tab === 'reports' && (
          <ReportsTab workflowId={wf.workflow_id} />
        )}
      </div>

      {/* UAT #14 — confirm modal + toast for state transitions. */}
      {confirmingTransition && (
        <ActivateConfirmModal
          targetState={confirmingTransition}
          cardsCount={sortedCards.length}
          onCancel={() => setConfirmingTransition(null)}
          onConfirm={() => transitionState(confirmingTransition)}
          busy={transitionBusy}
        />
      )}
      {toast && (
        <FloatingToast
          kind={toast.kind}
          message={toast.msg}
          onDismiss={() => setToast(null)}
        />
      )}
    </>
  );
}

// ─── UAT #14 — Confirm modal + Toast (inline, no extra deps) ─────

function ActivateConfirmModal({
  targetState, cardsCount, onCancel, onConfirm, busy,
}: {
  targetState: string;
  cardsCount: number;
  onCancel: () => void;
  onConfirm: () => void;
  busy: boolean;
}) {
  const isActivate = targetState === 'ACTIVE_BASELINE';
  return (
    <div
      role="dialog" aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 animate-fade-in"
      onClick={busy ? undefined : onCancel}
    >
      <div
        className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-lg w-full max-w-md mx-4 p-6 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center shrink-0">
            <CheckCircle2 className="w-5 h-5 text-[var(--primary-gold-dark)]" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-serif text-base text-[var(--text-primary)]">
              {isActivate ? 'Kích hoạt workflow?' : 'Xác nhận chuyển trạng thái?'}
            </h3>
            <p className="text-xs text-[var(--text-secondary)] mt-1">
              {isActivate
                ? `Workflow ${cardsCount} bước sẽ chuyển sang chạy chính thức. Mọi file upload sau khi kích hoạt sẽ chạy theo workflow này. Anh có thể tạm dừng để chỉnh sửa lại bất cứ lúc nào.`
                : 'Hành động này sẽ thay đổi trạng thái workflow.'}
            </p>
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-3 border-t border-[var(--border-color)]/60">
          <Button variant="tertiary" size="md" onClick={onCancel} disabled={busy}>
            Hủy
          </Button>
          <Button variant="primary" size="md" onClick={onConfirm} disabled={busy}>
            {busy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <CheckCircle2 className="w-4 h-4 mr-2" />}
            {isActivate ? 'Kích hoạt' : 'Xác nhận'}
          </Button>
        </div>
      </div>
    </div>
  );
}

function FloatingToast({
  kind, message, onDismiss,
}: { kind: 'success' | 'error'; message: string; onDismiss: () => void }) {
  const isSuccess = kind === 'success';
  return (
    <div
      role="status" aria-live="polite"
      className={cn(
        'fixed top-6 right-6 z-[60] max-w-sm rounded-md-custom border shadow-soft-lg px-4 py-3 flex items-start gap-3 animate-slide-up-fade',
        isSuccess
          ? 'bg-[var(--state-success)]/95 border-[var(--state-success)] text-white'
          : 'bg-[var(--state-error)]/95 border-[var(--state-error)] text-white',
      )}
    >
      <CheckCircle2 className={cn('w-5 h-5 shrink-0', !isSuccess && 'hidden')} />
      <X className={cn('w-5 h-5 shrink-0', isSuccess && 'hidden')} />
      <p className="text-sm flex-1">{message}</p>
      <button
        onClick={onDismiss}
        aria-label="Đóng thông báo"
        className="opacity-70 hover:opacity-100 transition-opacity shrink-0"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}

// ─── Tabs ────────────────────────────────────────────────────────

function Tabs({ tab, onChange }: { tab: 'builder' | 'bpmn' | 'tree' | 'reports'; onChange: (t: any) => void }) {
  return (
    <div className="flex items-center gap-1 border-b border-[var(--border-color)]">
      {[
        { key: 'builder', label: 'Builder', icon: Edit3 },
        { key: 'bpmn',    label: 'BPMN',    icon: Network },
        { key: 'tree',    label: 'Cây tài liệu', icon: Layers },
        { key: 'reports', label: 'Báo cáo',     icon: GitBranch },
      ].map((t) => {
        const Icon = t.icon;
        const active = tab === t.key;
        return (
          <button
            key={t.key}
            onClick={() => onChange(t.key)}
            className={cn(
              'inline-flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
              active
                ? 'border-[var(--primary-gold)] text-[var(--primary-gold-dark)]'
                : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
            )}
          >
            <Icon className="w-4 h-4" /> {t.label}
          </button>
        );
      })}
    </div>
  );
}

// ─── BuilderView ─────────────────────────────────────────────────

// P0 — callback that binds a decision branch to a target node via a real edge.
type SetEdgeFn = (args: {
  sourceId: string; oldTarget?: string | null; newTarget: string | null;
  condition?: string | null; label?: string | null;
}) => void;

function BuilderView({
  cards, edges, selected, onSelect, onAddCard, onUpdate, onDelete, onMove, onSetEdge,
}: {
  cards: CardNode[];
  edges: EdgeOut[];
  selected: CardNode | null;
  onSelect: (id: string) => void;
  onAddCard: () => void;
  onUpdate: (id: string, patch: Partial<CardNode>) => void;
  onDelete: (id: string) => void;
  onMove: (id: string, dir: -1 | 1) => void;
  onSetEdge: SetEdgeFn;
}) {
  return (
    <div className="grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-4">
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
        <div className="border-b border-[var(--border-color)] px-4 py-2 flex items-center justify-between bg-[var(--bg-app)]">
          <span className="text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
            <WorkflowIcon className="w-4 h-4 inline mr-1.5" /> Luồng bước
          </span>
          <Button size="sm" variant="primary" onClick={onAddCard}>
            <Plus className="w-3.5 h-3.5 mr-1" /> Thêm bước
          </Button>
        </div>
        <div className="p-6 min-h-[480px] flex flex-col items-center">
          <div className="w-32 h-12 rounded-full bg-emerald-100 border-2 border-emerald-300 flex items-center justify-center text-sm font-medium text-emerald-800">
            ▶ Bắt đầu
          </div>

          {cards.length === 0 ? (
            <div className="text-sm text-[var(--text-secondary)] my-12 text-center">
              <p className="mb-3">Workflow trống — bấm "Thêm bước" ở trên.</p>
              <Button size="sm" variant="secondary" onClick={onAddCard}>
                <Plus className="w-3.5 h-3.5 mr-1" /> Thêm bước đầu tiên
              </Button>
            </div>
          ) : (
            cards.map((c, i) => (
              <React.Fragment key={c.node_id}>
                <Connector from={i === 0 ? undefined : cards[i - 1]} edges={edges} nodes={cards} />
                <CardBox
                  card={c}
                  index={i}
                  total={cards.length}
                  active={selected?.node_id === c.node_id}
                  onClick={() => onSelect(c.node_id)}
                  onDelete={() => onDelete(c.node_id)}
                  onMoveUp={() => onMove(c.node_id, -1)}
                  onMoveDown={() => onMove(c.node_id, 1)}
                />
              </React.Fragment>
            ))
          )}

          {cards.length > 0 && <Connector from={cards[cards.length - 1]} edges={edges} nodes={cards} />}
          <div className="w-32 h-12 rounded-full bg-gray-100 border-2 border-gray-300 flex items-center justify-center text-sm font-medium text-gray-700">
            ■ Kết thúc
          </div>
        </div>
      </div>

      <CardEditor card={selected} nodes={cards} edges={edges} onUpdate={onUpdate} onSetEdge={onSetEdge} />
    </div>
  );
}

// ─── Node-type visual style table ────────────────────────────────
//
// Anh's feedback 2026-05-15: if_else + switch trông giống step. Tách ra:
//   • icon riêng (GitBranch / Network / CheckCircle2 / numbered)
//   • accent border bên trái 4px theo màu node_type
//   • badge nhỏ ghi loại bước (Quyết định / Chọn nhánh / Cần duyệt)
//   • hint dòng tóm tắt decision_config / approver

const NODE_TYPE_STYLES: Record<string, {
  icon: React.ElementType | null;
  label: string;
  accent: string;       // tailwind class — left border + bg tint
  iconBg: string;
  iconText: string;
  badgeBg: string;
  badgeText: string;
}> = {
  decision_if_else: {
    icon: GitBranch,
    label: 'Quyết định',
    accent: 'border-l-4 border-l-amber-500',
    iconBg: 'bg-amber-100',
    iconText: 'text-amber-700',
    badgeBg: 'bg-amber-50',
    badgeText: 'text-amber-800',
  },
  decision_switch: {
    icon: Network,
    label: 'Phân loại',
    accent: 'border-l-4 border-l-violet-500',
    iconBg: 'bg-violet-100',
    iconText: 'text-violet-700',
    badgeBg: 'bg-violet-50',
    badgeText: 'text-violet-800',
  },
  approval_gate: {
    icon: CheckCircle2,
    label: 'Phê duyệt',
    accent: 'border-l-4 border-l-emerald-500',
    iconBg: 'bg-emerald-100',
    iconText: 'text-emerald-700',
    badgeBg: 'bg-emerald-50',
    badgeText: 'text-emerald-800',
  },
  step: {
    icon: null,
    label: 'Bước nghiệp vụ',
    accent: '',
    iconBg: 'bg-[var(--primary-gold)]/15',
    iconText: 'text-[var(--primary-gold-dark)]',
    badgeBg: 'bg-slate-50',
    badgeText: 'text-slate-600',
  },
  wait_event: {
    icon: Clock,
    label: 'Chờ sự kiện',
    accent: 'border-l-4 border-l-blue-400',
    iconBg: 'bg-blue-100',
    iconText: 'text-blue-700',
    badgeBg: 'bg-blue-50',
    badgeText: 'text-blue-800',
  },
  sla_timer: {
    icon: AlarmClock,
    label: 'Hạn xử lý',
    accent: 'border-l-4 border-l-rose-500',
    iconBg: 'bg-rose-100',
    iconText: 'text-rose-700',
    badgeBg: 'bg-rose-50',
    badgeText: 'text-rose-800',
  },
  parallel_split: {
    icon: Split,
    label: 'Chạy song song',
    accent: 'border-l-4 border-l-indigo-500',
    iconBg: 'bg-indigo-100',
    iconText: 'text-indigo-700',
    badgeBg: 'bg-indigo-50',
    badgeText: 'text-indigo-800',
  },
  parallel_join: {
    icon: Merge,
    label: 'Hợp nhánh',
    accent: 'border-l-4 border-l-indigo-500',
    iconBg: 'bg-indigo-100',
    iconText: 'text-indigo-700',
    badgeBg: 'bg-indigo-50',
    badgeText: 'text-indigo-800',
  },
  subworkflow: {
    icon: Boxes,
    label: 'Quy trình con',
    accent: 'border-l-4 border-l-slate-500',
    iconBg: 'bg-slate-100',
    iconText: 'text-slate-700',
    badgeBg: 'bg-slate-50',
    badgeText: 'text-slate-700',
  },
  notification: {
    icon: Bell,
    label: 'Thông báo',
    accent: 'border-l-4 border-l-sky-500',
    iconBg: 'bg-sky-100',
    iconText: 'text-sky-700',
    badgeBg: 'bg-sky-50',
    badgeText: 'text-sky-800',
  },
};

function nodeStyle(t: string) {
  return NODE_TYPE_STYLES[t] ?? NODE_TYPE_STYLES.step;
}

function isDecisionType(t: string) {
  return t === 'decision_if_else' || t === 'decision_switch';
}

// ─── Doc status — required vs attached  ──────────────────────────
//
// Cards declare required_document_types[] with {kind, name, required}.
// We count how many of the required-kinds have at least one attached
// document, so the card can show "2/3 tài liệu" with colour coding.
// Kind matching mirrors the BE normaliser in ingestor._normalize_kind:
//   image / img / jpeg / jpg / png / tiff / webp  → 'image'
//   word / doc → 'docx'   ·   excel / spreadsheet → 'xlsx'

const _kindAlias: Record<string, string> = {
  image: 'image', img: 'image', jpeg: 'image', jpg: 'image',
  png: 'image', tiff: 'image', webp: 'image',
  word: 'docx', doc: 'docx',
  excel: 'xlsx', spreadsheet: 'xlsx',
};
function normalizeKind(k: string | null | undefined): string {
  const x = (k ?? '').toLowerCase().replace(/^\./, '').trim();
  return _kindAlias[x] ?? x;
}

interface DocStatus {
  required_count:     number;
  required_satisfied: number;
  attached_count:     number;
  missing_kinds:      string[];
  is_complete:        boolean;       // all required kinds have ≥1 doc
  has_unstructured:   boolean;       // any attached doc is unstructured (pdf/image/docx)
}
function computeDocStatus(card: CardNode): DocStatus {
  const required = (card.required_document_types || []).filter((r) => r.required);
  const attached = card.attached_documents || [];
  const attachedKinds = new Set(attached.map((d) => normalizeKind(d.document_kind)));
  const missing: string[] = [];
  let satisfied = 0;
  for (const r of required) {
    if (attachedKinds.has(normalizeKind(r.kind))) satisfied += 1;
    else missing.push(r.kind);
  }
  const unstructuredKinds = new Set(['pdf','docx','image','pptx','md']);
  const hasUnstructured = attached.some((d) =>
    unstructuredKinds.has(normalizeKind(d.document_kind)),
  );
  return {
    required_count:     required.length,
    required_satisfied: satisfied,
    attached_count:     attached.length,
    missing_kinds:      missing,
    is_complete:        required.length === 0 || satisfied === required.length,
    has_unstructured:   hasUnstructured,
  };
}

// Compact tài-liệu badge for the Builder card row + Tree tab header.
// Renders one of:
//   "<n> tài liệu"          — no required kinds; informative only
//   "<m>/<n> tài liệu"      — has required; green if complete, amber if missing
//   "<n> tài liệu (file scan)" — unstructured docs present (DocSage pending)
function DocStatusBadge({ card }: { card: CardNode }) {
  const s = computeDocStatus(card);
  if (s.required_count === 0 && s.attached_count === 0) return null;

  // No required — pure informational
  if (s.required_count === 0) {
    return (
      <span
        title={s.has_unstructured
          ? "Có tài liệu dạng PDF/Word/ảnh — Stage 6 DocSage chưa bật, chưa tự trích nội dung."
          : `${s.attached_count} tài liệu đã đính kèm`}
        className="inline-flex items-center text-[10px] font-medium text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded"
      >
        <FileText className="w-2.5 h-2.5 mr-0.5" />
        {s.attached_count} tài liệu
        {s.has_unstructured && (
          <span className="ml-1 text-amber-700">(scan)</span>
        )}
      </span>
    );
  }

  // Has required — colour by completion
  const cls = s.is_complete
    ? 'text-emerald-700 bg-emerald-50 border border-emerald-200'
    : 'text-amber-700 bg-amber-50 border border-amber-200';
  const tip = s.is_complete
    ? `Đủ ${s.required_count} tài liệu bắt buộc.`
    : `Còn thiếu: ${s.missing_kinds.join(', ')}`;
  return (
    <span
      title={tip}
      className={cn('inline-flex items-center text-[10px] font-medium px-1.5 py-0.5 rounded', cls)}
    >
      <FileText className="w-2.5 h-2.5 mr-0.5" />
      {s.required_satisfied}/{s.required_count} tài liệu
      {!s.is_complete && <span className="ml-1">· thiếu</span>}
    </span>
  );
}

function decisionSummary(card: CardNode): string | null {
  if (card.node_type === 'decision_if_else') {
    const cfg = card.decision_config ?? {};
    if (Array.isArray(cfg.branches) && cfg.branches.length > 0) {
      const elseIf = cfg.branches.filter((b: any) => b.kind === 'else_if').length;
      const hasElse = cfg.branches.some((b: any) => b.kind === 'else');
      const parts = ['if'];
      if (elseIf > 0) parts.push(`${elseIf} × else if`);
      if (hasElse) parts.push('else');
      return parts.join(' · ');
    }
    const cond = cfg.condition;
    return cond ? `Nếu: ${String(cond)}` : 'Chưa cấu hình điều kiện';
  }
  if (card.node_type === 'decision_switch') {
    const cfg = card.decision_config ?? {};
    const cases = Array.isArray(cfg.cases) ? cfg.cases.length : 0;
    const hasDefault = !!cfg.default;
    const expr = cfg.expression || cfg.switch_field;
    if (cases > 0 || hasDefault) {
      return `${expr ? expr + ' → ' : ''}${cases} case${hasDefault ? ' + default' : ''}`;
    }
    return 'Chưa cấu hình case';
  }
  if (card.node_type === 'approval_gate') {
    const cfg = card.decision_config ?? {};
    if (cfg.approval_chain_id) return 'Phê duyệt theo chuỗi duyệt (đa cấp)';
    const role = Array.isArray(cfg.approver_role) ? cfg.approver_role.join(', ') : cfg.approver_role;
    return role ? `Phê duyệt bởi: ${String(role)}` : 'Chưa gắn chuỗi/vai trò duyệt';
  }
  if (card.node_type === 'wait_event') {
    const ev = card.decision_config?.event_type;
    const timeout = card.decision_config?.timeout_minutes;
    if (ev) return `Chờ: ${ev}${timeout ? ` (tối đa ${timeout} phút)` : ''}`;
    return 'Chưa chọn sự kiện chờ';
  }
  if (card.node_type === 'sla_timer') {
    const mins = card.decision_config?.deadline_minutes;
    const action = card.decision_config?.on_timeout_action;
    if (mins) return `Hạn ${mins} phút${action ? ` → ${action}` : ''}`;
    return 'Chưa cấu hình hạn';
  }
  if (card.node_type === 'parallel_split') {
    const n = card.decision_config?.branch_count;
    return n ? `Tách ${n} nhánh song song` : 'Cấu hình số nhánh';
  }
  if (card.node_type === 'parallel_join') {
    const mode = card.decision_config?.join_mode;
    return `Đợi nhánh xong${mode ? ` (${mode})` : ''}`;
  }
  if (card.node_type === 'subworkflow') {
    const tgt = card.decision_config?.target_workflow_name || card.decision_config?.target_workflow_id;
    return tgt ? `Gọi: ${String(tgt).slice(0, 36)}` : 'Chưa chọn workflow con';
  }
  if (card.node_type === 'notification') {
    const channel = card.decision_config?.channel;
    const recipients = card.decision_config?.recipients;
    const n = Array.isArray(recipients) ? recipients.length : 0;
    if (channel || n) return `${channel || 'kênh'} → ${n} người nhận`;
    return 'Chưa cấu hình thông báo';
  }
  return null;
}

function nodeTitle(nodes: CardNode[], id: string): string {
  const n = nodes.find((x) => String(x.node_id) === String(id));
  return n ? (n.title_vi || n.title) : '(bước đã xoá)';
}

// Smart connector — vẽ nhánh out cho decision/approval node
function Connector({ from, edges = [], nodes = [] }: { from?: CardNode; edges?: EdgeOut[]; nodes?: CardNode[] }) {
  // P0 — REAL fork: when a node is wired to ≥2 target nodes via main edges,
  // draw the diverging branches to their ACTUAL targets (by name), not just
  // decorative chips on a single spine. This is the fix for "nhánh đã chia
  // trong doc nhưng FE không thấy". Lane view (P1) will lay these out fully.
  const outs = from
    ? edges.filter((e) => (e.port_type ?? 'main') === 'main' &&
                          String(e.source_node_id) === String(from.node_id))
    : [];
  if (from && outs.length >= 2) {
    const cols = Math.min(outs.length, 3);
    return (
      <div className="flex flex-col items-center my-1.5 gap-1 w-full max-w-[460px]">
        <div className="w-px h-3 bg-amber-300" />
        <Split className="w-3.5 h-3.5 text-amber-500" />
        <div className="grid gap-1.5 w-full" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0,1fr))` }}>
          {outs.map((e, i) => (
            <div key={e.edge_id} className="flex flex-col items-center gap-0.5 px-1 min-w-0">
              <span className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded border bg-amber-50 text-amber-800 border-amber-200 max-w-full">
                <GitBranch className="w-2.5 h-2.5 shrink-0" />
                <span className="truncate">{e.label || e.condition || `nhánh ${i + 1}`}</span>
              </span>
              <ArrowDown className="w-3 h-3 text-amber-500" />
              <span className="text-[10px] text-[var(--text-secondary)] truncate max-w-full"
                    title={nodeTitle(nodes, e.target_node_id)}>
                {nodeTitle(nodes, e.target_node_id)}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Default plain connector (step → next)
  if (!from || from.node_type === 'step' || !from.node_type) {
    return (
      <div className="flex flex-col items-center my-1.5">
        <div className="w-px h-6 bg-[var(--border-color)]" />
        <ArrowDown className="w-3 h-3 text-[var(--text-secondary)]" />
      </div>
    );
  }

  // if_else — render 1 chip per branch
  if (from.node_type === 'decision_if_else') {
    const cfg = from.decision_config ?? {};
    const branches: any[] = Array.isArray(cfg.branches) && cfg.branches.length > 0
      ? cfg.branches
      : [{ kind: 'if', condition: cfg.condition, label: 'ĐÚNG' },
         { kind: 'else',                          label: 'SAI'  }];
    return (
      <div className="flex flex-col items-center my-1.5 gap-1">
        <div className="flex flex-wrap gap-1 justify-center max-w-[440px]">
          {branches.slice(0, 6).map((b, i) => {
            const isElse = b.kind === 'else';
            const isIf = b.kind === 'if';
            const tag = isIf ? 'IF' : isElse ? 'ELSE' : `ELSE IF ${i}`;
            const text = b.label || (isElse ? 'Mặc định' : (b.condition ? String(b.condition).slice(0, 24) : '…'));
            return (
              <span key={i}
                    className={cn(
                      'inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded border',
                      isIf      ? 'bg-amber-500/15 text-amber-900 border-amber-300' :
                      isElse    ? 'bg-slate-100 text-slate-700 border-slate-300' :
                                  'bg-amber-100 text-amber-800 border-amber-200',
                    )}>
                <span className="font-bold">{tag}</span>
                <span className="truncate max-w-[140px]">{text}</span>
              </span>
            );
          })}
          {branches.length > 6 && (
            <span className="text-[10px] text-amber-600 italic">+{branches.length - 6} nhánh</span>
          )}
        </div>
        <div className="w-px h-3 bg-amber-300 border-l-2 border-dashed border-amber-400" />
        <ArrowDown className="w-3 h-3 text-amber-500" />
      </div>
    );
  }

  // switch — render 1 chip per case + default
  if (from.node_type === 'decision_switch') {
    const cfg = from.decision_config ?? {};
    const cases: any[] = Array.isArray(cfg.cases) ? cfg.cases.slice(0, 6) : [];
    const def = cfg.default;
    const expr = cfg.expression || cfg.switch_field;
    return (
      <div className="flex flex-col items-center my-1.5 gap-1">
        {expr && (
          <span className="text-[10px] font-mono text-violet-800 bg-violet-100 px-1.5 py-0.5 rounded">
            {String(expr)}
          </span>
        )}
        {cases.length === 0 && !def ? (
          <span className="text-[10px] text-violet-500 italic">Switch — chưa có case</span>
        ) : (
          <div className="flex flex-wrap gap-1 justify-center max-w-[440px]">
            {cases.map((c, i) => (
              <span key={i}
                    className="inline-flex items-center gap-1 text-[10px] font-medium text-violet-800 bg-violet-50 px-1.5 py-0.5 rounded border border-violet-200">
                <span className="font-bold">⇢</span>
                <span className="truncate max-w-[140px]">{String(c?.label || c?.value || `case ${i + 1}`)}</span>
              </span>
            ))}
            {def && (
              <span className="inline-flex items-center gap-1 text-[10px] font-medium text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded border border-slate-300">
                <span className="font-bold">DEFAULT</span>
                <span className="truncate max-w-[120px]">{String(def?.label || 'Mặc định')}</span>
              </span>
            )}
            {Array.isArray(cfg.cases) && cfg.cases.length > 6 && (
              <span className="text-[10px] text-violet-600 italic">+{cfg.cases.length - 6} case</span>
            )}
          </div>
        )}
        <div className="w-px h-3 bg-violet-300 border-l-2 border-dashed border-violet-400" />
        <ArrowDown className="w-3 h-3 text-violet-500" />
      </div>
    );
  }

  if (from.node_type === 'approval_gate') {
    return (
      <div className="flex flex-col items-center my-1.5 gap-0.5">
        <span className="inline-flex items-center text-[10px] font-medium text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
          ✓ Sau khi duyệt
        </span>
        <div className="w-px h-4 bg-emerald-300 border-l-2 border-dashed border-emerald-400" />
        <ArrowDown className="w-3 h-3 text-emerald-500" />
      </div>
    );
  }

  if (from.node_type === 'parallel_split') {
    const n = Math.max(2, Math.min(6, Number(from.decision_config?.branch_count ?? 2)));
    return (
      <div className="flex flex-col items-center my-1.5 gap-1">
        <span className="inline-flex items-center text-[10px] font-medium text-indigo-700 bg-indigo-50 border border-indigo-200 px-1.5 py-0.5 rounded">
          ⇶ Tách {n} nhánh song song
        </span>
        <div className="flex gap-2">
          {Array.from({ length: n }).map((_, i) => (
            <div key={i} className="flex flex-col items-center">
              <div className="w-px h-4 bg-indigo-300 border-l-2 border-dashed border-indigo-400" />
              <ArrowDown className="w-3 h-3 text-indigo-500" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (from.node_type === 'parallel_join') {
    const mode = from.decision_config?.join_mode;
    return (
      <div className="flex flex-col items-center my-1.5 gap-0.5">
        <span className="inline-flex items-center text-[10px] font-medium text-indigo-700 bg-indigo-50 border border-indigo-200 px-1.5 py-0.5 rounded">
          ⊕ Hợp nhánh{mode ? ` (${mode})` : ''}
        </span>
        <div className="w-px h-4 bg-indigo-300 border-l-2 border-dashed border-indigo-400" />
        <ArrowDown className="w-3 h-3 text-indigo-500" />
      </div>
    );
  }

  if (from.node_type === 'sla_timer') {
    const mins = from.decision_config?.deadline_minutes;
    const action = from.decision_config?.on_timeout_action;
    return (
      <div className="flex flex-col items-center my-1.5 gap-0.5">
        <span className="inline-flex items-center text-[10px] font-medium text-rose-700 bg-rose-50 border border-rose-200 px-1.5 py-0.5 rounded">
          ⏱ {mins ? `${mins} phút` : 'Đặt hạn'}
          {action ? ` → ${action}` : ''}
        </span>
        <div className="w-px h-4 bg-rose-300 border-l-2 border-dashed border-rose-400" />
        <ArrowDown className="w-3 h-3 text-rose-500" />
      </div>
    );
  }

  if (from.node_type === 'wait_event') {
    const ev = from.decision_config?.event_type;
    return (
      <div className="flex flex-col items-center my-1.5 gap-0.5">
        <span className="inline-flex items-center text-[10px] font-medium text-blue-700 bg-blue-50 border border-blue-200 px-1.5 py-0.5 rounded">
          ⌛ Chờ {ev ? `${ev}` : 'sự kiện'}
        </span>
        <div className="w-px h-4 bg-blue-300 border-l-2 border-dashed border-blue-400" />
        <ArrowDown className="w-3 h-3 text-blue-500" />
      </div>
    );
  }

  if (from.node_type === 'subworkflow') {
    const tgt = from.decision_config?.target_workflow_name || 'workflow con';
    return (
      <div className="flex flex-col items-center my-1.5 gap-0.5">
        <span className="inline-flex items-center text-[10px] font-medium text-slate-700 bg-slate-100 border border-slate-300 px-1.5 py-0.5 rounded">
          ⤵ Sau khi {String(tgt).slice(0, 30)} xong
        </span>
        <div className="w-px h-4 bg-slate-300 border-l-2 border-dashed border-slate-400" />
        <ArrowDown className="w-3 h-3 text-slate-500" />
      </div>
    );
  }

  if (from.node_type === 'notification') {
    const channel = from.decision_config?.channel;
    return (
      <div className="flex flex-col items-center my-1.5 gap-0.5">
        <span className="inline-flex items-center text-[10px] font-medium text-sky-700 bg-sky-50 border border-sky-200 px-1.5 py-0.5 rounded">
          📤 Đã gửi qua {channel || 'kênh'}
        </span>
        <div className="w-px h-4 bg-sky-300 border-l-2 border-dashed border-sky-400" />
        <ArrowDown className="w-3 h-3 text-sky-500" />
      </div>
    );
  }

  // fallback
  return (
    <div className="flex flex-col items-center my-1.5">
      <div className="w-px h-6 bg-[var(--border-color)]" />
      <ArrowDown className="w-3 h-3 text-[var(--text-secondary)]" />
    </div>
  );
}

function CardBox({
  card, index, total, active, onClick, onDelete, onMoveUp, onMoveDown,
}: {
  card: CardNode; index: number; total: number; active: boolean;
  onClick: () => void; onDelete: () => void;
  onMoveUp: () => void; onMoveDown: () => void;
}) {
  const style = nodeStyle(card.node_type || 'step');
  const Icon = style.icon;
  const summary = decisionSummary(card);
  const isDecision = isDecisionType(card.node_type || '');

  return (
    <div
      onClick={onClick}
      className={cn(
        'group relative w-full max-w-[460px] rounded-md-custom border-2 cursor-pointer transition-all p-3.5',
        style.accent,
        active
          ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/8 shadow-soft-md'
          : 'border-[var(--border-color)] bg-[var(--bg-app)] hover:border-[var(--primary-gold)]/40',
      )}
    >
      <div className="flex items-start gap-3">
        <div className={cn(
          'w-9 h-9 rounded-md-custom flex items-center justify-center shrink-0',
          style.iconBg, style.iconText,
          'text-sm font-bold',
        )}>
          {Icon ? <Icon className="w-4 h-4" strokeWidth={2.25} /> : (index + 1)}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <p className="text-sm font-medium text-[var(--text-primary)] line-clamp-1">
              {card.title_vi || card.title}
            </p>
            <span className={cn(
              'inline-flex items-center text-[10px] font-medium px-1.5 py-0.5 rounded',
              style.badgeBg, style.badgeText,
            )}>
              {style.label}
            </span>
          </div>
          {card.note && <p className="text-[11px] text-[var(--text-secondary)] line-clamp-1 mt-0.5">{card.note}</p>}
          {summary && (
            <p className={cn(
              'text-[11px] mt-1 font-medium line-clamp-1',
              isDecision ? 'text-amber-700' : 'text-emerald-700',
              card.node_type === 'decision_switch' ? 'text-violet-700' : '',
            )}>
              {summary}
            </p>
          )}
          <div className="flex flex-wrap gap-1 mt-1.5">
            {card.hashtags.slice(0, 3).map((h) => (
              <span key={h} className="inline-flex items-center text-[10px] font-medium text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded">
                #{h}
              </span>
            ))}
            <DocStatusBadge card={card} />
          </div>
        </div>
        <div className="opacity-0 group-hover:opacity-100 flex flex-col gap-1 transition-opacity">
          <button onClick={(e) => { e.stopPropagation(); onMoveUp(); }}  disabled={index === 0}
                  className="p-0.5 hover:bg-[var(--bg-card)] rounded disabled:opacity-30">
            <ChevronUp className="w-3 h-3" />
          </button>
          <button onClick={(e) => { e.stopPropagation(); onMoveDown(); }} disabled={index === total - 1}
                  className="p-0.5 hover:bg-[var(--bg-card)] rounded disabled:opacity-30">
            <ChevronDown className="w-3 h-3" />
          </button>
          <button onClick={(e) => { e.stopPropagation(); onDelete(); }}
                  className="p-0.5 hover:bg-rose-50 rounded text-[var(--text-secondary)] hover:text-rose-600">
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── CardEditor ──────────────────────────────────────────────────

function CardEditor({
  card, nodes, edges, onUpdate, onSetEdge,
}: {
  card: CardNode | null;
  nodes: CardNode[];
  edges: EdgeOut[];
  onUpdate: (id: string, patch: Partial<CardNode>) => void;
  onSetEdge: SetEdgeFn;
}) {
  if (!card) {
    return (
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Edit3 className="w-10 h-10 text-[var(--text-secondary)]/30 mb-2" />
          <p className="text-sm text-[var(--text-secondary)]">Chọn 1 bước để chỉnh nội dung.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm space-y-4 max-h-[760px] overflow-y-auto">
      <div className="flex items-center gap-2 pb-3 border-b border-[var(--border-color)]/60">
        <Edit3 className="w-4 h-4 text-[var(--primary-gold-dark)]" />
        <h3 className="font-serif text-sm text-[var(--text-primary)]">Chỉnh bước</h3>
      </div>

      <Input
        label="Tên bước (English / internal)"
        value={card.title}
        onChange={(e) => onUpdate(card.node_id, { title: e.target.value })}
      />
      <Input
        label="Tên bước (Tiếng Việt)"
        value={card.title_vi ?? ''}
        onChange={(e) => onUpdate(card.node_id, { title_vi: e.target.value })}
      />

      <div className="space-y-1.5">
        <label className="text-sm font-medium text-[var(--text-primary)]">Loại bước</label>
        <select
          value={card.node_type}
          onChange={(e) => onUpdate(card.node_id, { node_type: e.target.value as any })}
          className="w-full h-9 px-3 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
        >
          <optgroup label="Nghiệp vụ cơ bản">
            <option value="step">Bước nghiệp vụ — công việc thông thường</option>
            <option value="approval_gate">Phê duyệt — chờ cấp trên ký</option>
            <option value="notification">Thông báo — gửi email / Zalo / Teams</option>
          </optgroup>
          <optgroup label="Quyết định nghiệp vụ">
            <option value="decision_if_else">Quyết định — rẽ theo điều kiện (đúng / sai / khác)</option>
            <option value="decision_switch">Phân loại — rẽ theo nhiều giá trị (Bronze / Silver / Gold…)</option>
          </optgroup>
          <optgroup label="Điều phối thời gian">
            <option value="wait_event">Chờ sự kiện — chờ khách ký / thanh toán / phản hồi</option>
            <option value="sla_timer">Hạn xử lý — đếm ngược + cảnh báo / leo thang</option>
          </optgroup>
          <optgroup label="Điều phối nâng cao">
            <option value="parallel_split">Chạy song song — tách N nhánh đồng thời</option>
            <option value="parallel_join">Hợp nhánh — đợi các nhánh song song xong</option>
            <option value="subworkflow">Quy trình con — gọi workflow khác</option>
          </optgroup>
        </select>
        <p className="text-[10px] text-[var(--text-secondary)]">
          Build Week: lưu metadata để hiển thị + audit. Runtime evaluate
          (chạy theo điều kiện thật) sẽ bật cùng Temporal Phase 2.
        </p>
      </div>

      {card.node_type === 'decision_if_else' && (
        <IfElseBranchesEditor
          config={card.decision_config ?? {}}
          onChange={(cfg) => onUpdate(card.node_id, { decision_config: cfg })}
          nodeId={card.node_id}
          nodes={nodes}
          edges={edges}
          onSetEdge={onSetEdge}
        />
      )}

      {card.node_type === 'decision_switch' && (
        <SwitchCasesEditor
          config={card.decision_config ?? {}}
          onChange={(cfg) => onUpdate(card.node_id, { decision_config: cfg })}
          nodeId={card.node_id}
          nodes={nodes}
          edges={edges}
          onSetEdge={onSetEdge}
        />
      )}

      {card.node_type === 'approval_gate' && (
        <ApprovalGateEditor
          config={card.decision_config ?? {}}
          onChange={(cfg) => onUpdate(card.node_id, { decision_config: cfg })}
        />
      )}

      {card.node_type === 'wait_event' && (
        <WaitEventEditor
          config={card.decision_config ?? {}}
          onChange={(cfg) => onUpdate(card.node_id, { decision_config: cfg })}
        />
      )}

      {card.node_type === 'sla_timer' && (
        <SlaTimerEditor
          config={card.decision_config ?? {}}
          onChange={(cfg) => onUpdate(card.node_id, { decision_config: cfg })}
        />
      )}

      {card.node_type === 'parallel_split' && (
        <ParallelSplitEditor
          config={card.decision_config ?? {}}
          onChange={(cfg) => onUpdate(card.node_id, { decision_config: cfg })}
        />
      )}

      {card.node_type === 'parallel_join' && (
        <ParallelJoinEditor
          config={card.decision_config ?? {}}
          onChange={(cfg) => onUpdate(card.node_id, { decision_config: cfg })}
        />
      )}

      {card.node_type === 'subworkflow' && (
        <SubworkflowEditor
          config={card.decision_config ?? {}}
          onChange={(cfg) => onUpdate(card.node_id, { decision_config: cfg })}
        />
      )}

      {card.node_type === 'notification' && (
        <NotificationEditor
          config={card.decision_config ?? {}}
          onChange={(cfg) => onUpdate(card.node_id, { decision_config: cfg })}
        />
      )}

      <div className="space-y-1.5">
        <label className="text-sm font-medium text-[var(--text-primary)]">Ghi chú</label>
        <textarea
          value={card.note ?? ''}
          onChange={(e) => onUpdate(card.node_id, { note: e.target.value })}
          rows={3}
          placeholder="Mô tả công việc, người chịu trách nhiệm, lưu ý đặc biệt…"
          className="w-full px-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-xs text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
        />
      </div>

      <HashtagsEditor
        hashtags={card.hashtags}
        onChange={(v) => onUpdate(card.node_id, { hashtags: v })}
      />

      <DocsEditor
        docs={card.required_document_types}
        onChange={(v) => onUpdate(card.node_id, { required_document_types: v })}
      />
    </div>
  );
}

function HashtagsEditor({ hashtags, onChange }: { hashtags: string[]; onChange: (v: string[]) => void }) {
  const [draft, setDraft] = useState('');
  function addTag() {
    const t = draft.trim().replace(/^#/, '');
    if (!t) return;
    if (!hashtags.includes(t)) onChange([...hashtags, t]);
    setDraft('');
  }
  return (
    <div className="space-y-1.5">
      <label className="text-sm font-medium text-[var(--text-primary)]">
        <Hash className="w-3.5 h-3.5 inline mr-1" /> Hashtag
      </label>
      <div className="flex flex-wrap gap-1 mb-1.5">
        {hashtags.map((h) => (
          <span key={h} className="inline-flex items-center gap-1 text-[11px] font-medium text-blue-700 bg-blue-50 px-2 py-0.5 rounded">
            #{h}
            <button onClick={() => onChange(hashtags.filter((x) => x !== h))} className="text-blue-700 hover:text-blue-900">
              <X className="w-2.5 h-2.5" />
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addTag(); } }}
          placeholder="prospect_data, q1_campaign…"
          className="flex-1 px-3 py-1.5 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-xs focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
        />
        <button onClick={addTag} className="px-3 py-1.5 text-xs font-medium text-[var(--primary-gold-dark)] hover:bg-[var(--primary-gold)]/10 rounded-md-custom">
          + Thêm
        </button>
      </div>
    </div>
  );
}

function DocsEditor({
  docs, onChange,
}: { docs: RequiredDoc[]; onChange: (v: RequiredDoc[]) => void }) {
  function update(i: number, patch: Partial<RequiredDoc>) {
    onChange(docs.map((d, idx) => idx === i ? { ...d, ...patch } : d));
  }
  function add() {
    onChange([...docs, { kind: 'csv', name: 'Tài liệu mới', required: false }]);
  }
  return (
    <div className="space-y-1.5">
      <label className="text-sm font-medium text-[var(--text-primary)]">
        <FilePlus className="w-3.5 h-3.5 inline mr-1" /> Tài liệu cần nộp
      </label>
      {docs.length === 0 && (
        <p className="text-[11px] text-[var(--text-secondary)] italic">Chưa có tài liệu yêu cầu.</p>
      )}
      {docs.map((d, i) => (
        <div key={i} className="flex items-center gap-2">
          <select
            value={d.kind}
            onChange={(e) => update(i, { kind: e.target.value })}
            className="h-8 px-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-xs focus:outline-none"
          >
            <option value="csv">CSV</option>
            <option value="xlsx">Excel</option>
            <option value="docx">Word</option>
            <option value="pdf">PDF</option>
            <option value="image">Hình</option>
            <option value="json">JSON</option>
            <option value="other">Khác</option>
          </select>
          <input
            type="text"
            value={d.name}
            onChange={(e) => update(i, { name: e.target.value })}
            placeholder="Tên tài liệu"
            className="flex-1 h-8 px-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-xs focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
          />
          <label className="flex items-center gap-1 text-[11px] text-[var(--text-secondary)] cursor-pointer">
            <input
              type="checkbox"
              checked={d.required}
              onChange={(e) => update(i, { required: e.target.checked })}
              className="w-3.5 h-3.5 accent-[var(--primary-gold)]"
            />
            bắt buộc
          </label>
          <button onClick={() => onChange(docs.filter((_, idx) => idx !== i))}
                  className="p-1 text-[var(--text-secondary)] hover:text-rose-600">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      ))}
      <button onClick={add} className="text-xs font-medium text-[var(--primary-gold-dark)] hover:underline">
        + Thêm tài liệu
      </button>
    </div>
  );
}

// ─── IfElseBranchesEditor ────────────────────────────────────────
//
// decision_config schema (extended 2026-05-15 per anh's spec):
//   {
//     branches: [
//       { id, kind: "if"|"else_if"|"else", condition?: string, label?: string },
//       ...
//     ]
//   }
// First branch MUST be kind="if"; "else" — if present — MUST be last.

interface IfBranch { id: string; kind: 'if' | 'else_if' | 'else'; condition?: string; label?: string; target_node_id?: string | null }

function genId() { return 'b' + Math.random().toString(36).slice(2, 9); }

function normalizeBranches(config: Record<string, any>): IfBranch[] {
  // Migrate legacy { condition: "..." } → single if branch.
  if (Array.isArray(config?.branches) && config.branches.length > 0) {
    return config.branches.map((b: any, idx: number) => ({
      id:             b.id ?? genId(),
      kind:           idx === 0 ? 'if' : (b.kind === 'else' ? 'else' : 'else_if'),
      condition:      b.condition ?? '',
      label:          b.label ?? '',
      target_node_id: b.target_node_id ?? null,
    }));
  }
  // Legacy single-condition or empty
  return [{
    id: genId(),
    kind: 'if',
    condition: config?.condition ?? '',
    label: config?.label ?? '',
    target_node_id: null,
  }];
}

// P0 — dropdown that binds a branch/case to a target node (creates a real edge
// via onSetEdge upstream). Shows "đã nối / chưa nối" so dangling branches are
// obvious before the user tries to activate (matches the BE dangling guard).
function BranchTargetSelect({
  sourceId, nodes, value, onChange,
}: {
  sourceId: string;
  nodes: CardNode[];
  value: string | null | undefined;
  onChange: (targetId: string | null) => void;
}) {
  const candidates = nodes.filter((n) => n.node_id !== sourceId);
  return (
    <div className="flex items-center gap-1.5">
      <ArrowRight className="w-3 h-3 text-[var(--text-secondary)] shrink-0" />
      <select
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value || null)}
        className="flex-1 h-7 px-2 bg-white border border-[var(--border-color)] rounded text-[11px] focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
      >
        <option value="">— Chưa nối tới bước nào —</option>
        {candidates.map((n) => (
          <option key={n.node_id} value={n.node_id}>{n.title_vi || n.title}</option>
        ))}
      </select>
      {value
        ? <span className="text-[10px] font-medium text-emerald-600 shrink-0">✓ đã nối</span>
        : <span className="text-[10px] font-medium text-amber-600 shrink-0">⚠ chưa nối</span>}
    </div>
  );
}

function ifBranchLabel(b: IfBranch, idx: number): string {
  return b.label || (b.kind === 'if' ? 'IF' : b.kind === 'else' ? 'ELSE' : `ELSE IF ${idx}`);
}

function IfElseBranchesEditor({
  config, onChange, nodeId, nodes, edges, onSetEdge,
}: {
  config: Record<string, any>;
  onChange: (cfg: Record<string, any>) => void;
  nodeId: string;
  nodes: CardNode[];
  edges: EdgeOut[];
  onSetEdge: SetEdgeFn;
}) {
  const branches = useMemo(() => normalizeBranches(config), [config]);

  // The EDGE is the source of truth for a branch's target — derive it by
  // matching the branch's stable label. Reading from edges (not decision_config)
  // avoids the debounced-node-PUT race that would otherwise revert the selector
  // after loadTree(). Returns null when the branch isn't wired yet.
  function targetOf(b: IfBranch, idx: number): string | null {
    const lbl = ifBranchLabel(b, idx);
    const e = edges.find((x) => String(x.source_node_id) === String(nodeId) && (x.label || '') === lbl);
    return e ? String(e.target_node_id) : null;
  }

  function commit(next: IfBranch[]) {
    onChange({ ...config, branches: next });
  }

  function update(idx: number, patch: Partial<IfBranch>) {
    commit(branches.map((b, i) => i === idx ? { ...b, ...patch } : b));
  }

  // P0 — pick the node this branch flows to → create/replace the real edge.
  function setTarget(idx: number, targetId: string | null) {
    const b = branches[idx];
    onSetEdge({
      sourceId: nodeId,
      oldTarget: targetOf(b, idx),
      newTarget: targetId,
      condition: b.condition ?? null,
      label: ifBranchLabel(b, idx),
    });
  }

  function addElseIf() {
    // Insert else_if before "else" if exists, else append.
    const elseIdx = branches.findIndex((b) => b.kind === 'else');
    const newBr: IfBranch = { id: genId(), kind: 'else_if', condition: '', label: '' };
    if (elseIdx === -1) commit([...branches, newBr]);
    else commit([...branches.slice(0, elseIdx), newBr, ...branches.slice(elseIdx)]);
  }

  function addElse() {
    if (branches.some((b) => b.kind === 'else')) return;
    commit([...branches, { id: genId(), kind: 'else', label: '' }]);
  }

  function remove(idx: number) {
    if (branches[idx].kind === 'if') return;   // protect first branch
    // Drop this branch's edge too so we don't leave an orphan in the DAG.
    const b = branches[idx];
    const cur = targetOf(b, idx);
    if (cur) {
      onSetEdge({ sourceId: nodeId, oldTarget: cur, newTarget: null,
                  condition: b.condition ?? null, label: ifBranchLabel(b, idx) });
    }
    commit(branches.filter((_, i) => i !== idx));
  }

  const hasElse = branches.some((b) => b.kind === 'else');

  return (
    <div className="space-y-2 border-l-4 border-amber-400 pl-3 bg-amber-50/40 py-2 rounded-r-md">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-amber-900">
          <GitBranch className="w-3.5 h-3.5 inline mr-1" />
          Các nhánh điều kiện
        </label>
        <span className="text-[10px] text-amber-700">
          {branches.length} nhánh{hasElse ? ' (gồm else)' : ''}
        </span>
      </div>

      {branches.map((b, i) => (
        <div key={b.id} className="bg-white border border-amber-200 rounded-md p-2 space-y-1.5">
          <div className="flex items-center justify-between gap-2">
            <span className={cn(
              'inline-flex items-center text-[10px] font-bold px-1.5 py-0.5 rounded',
              b.kind === 'if'      ? 'bg-amber-500 text-white' :
              b.kind === 'else_if' ? 'bg-amber-200 text-amber-900' :
                                     'bg-slate-200 text-slate-800',
            )}>
              {b.kind === 'if' ? 'IF' : b.kind === 'else_if' ? `ELSE IF ${i}` : 'ELSE'}
            </span>
            {b.kind !== 'if' && (
              <button onClick={() => remove(i)}
                      className="p-0.5 text-rose-600 hover:bg-rose-50 rounded"
                      title="Xóa nhánh">
                <X className="w-3 h-3" />
              </button>
            )}
          </div>

          {b.kind !== 'else' && (
            <input
              type="text"
              value={b.condition ?? ''}
              onChange={(e) => update(i, { condition: e.target.value })}
              placeholder={i === 0 ? 'VD: order_total > 1000000' : 'VD: order_total > 500000'}
              className="w-full h-8 px-2 bg-[var(--bg-app)] border border-amber-200 rounded text-xs font-mono focus:outline-none focus:ring-2 focus:ring-amber-300"
            />
          )}
          <input
            type="text"
            value={b.label ?? ''}
            onChange={(e) => update(i, { label: e.target.value })}
            placeholder={
              b.kind === 'if' ? 'Nhãn (VD: Đơn lớn)' :
              b.kind === 'else_if' ? 'Nhãn (VD: Đơn vừa)' :
                                     'Nhãn (VD: Đơn nhỏ / mặc định)'
            }
            className="w-full h-8 px-2 bg-white border border-amber-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-amber-300"
          />
          <BranchTargetSelect
            sourceId={nodeId}
            nodes={nodes}
            value={targetOf(b, i)}
            onChange={(t) => setTarget(i, t)}
          />
        </div>
      ))}

      <div className="flex gap-2 pt-1">
        <button
          onClick={addElseIf}
          className="text-[11px] font-medium text-amber-800 hover:bg-amber-100 px-2 py-1 rounded">
          + Thêm else if
        </button>
        {!hasElse && (
          <button
            onClick={addElse}
            className="text-[11px] font-medium text-slate-700 hover:bg-slate-100 px-2 py-1 rounded">
            + Thêm else (mặc định)
          </button>
        )}
      </div>
      <p className="text-[10px] text-amber-700/80">
        Đánh giá tuần tự: nhánh đầu tiên thỏa điều kiện sẽ chạy. Phase 2 evaluate; Phase 1 lưu metadata để render + audit.
      </p>
    </div>
  );
}

// ─── SwitchCasesEditor ───────────────────────────────────────────
//
// decision_config schema:
//   {
//     expression: "customer.tier",
//     cases: [ { id, value, label }, ... ],
//     default: { id, label } | null
//   }

interface SwitchCase { id: string; value?: string; label?: string; target_node_id?: string | null }

function normalizeSwitch(config: Record<string, any>): { expression: string; cases: SwitchCase[]; default: SwitchCase | null } {
  const expression = String(config?.expression ?? config?.switch_field ?? '');
  let cases: SwitchCase[] = [];
  if (Array.isArray(config?.cases)) {
    cases = config.cases.map((c: any) => ({
      id:             c.id ?? genId(),
      value:          c.value ?? '',
      label:          c.label ?? '',
      target_node_id: c.target_node_id ?? null,
    }));
  }
  const def = config?.default ?? null;
  return {
    expression,
    cases,
    default: def
      ? { id: def.id ?? genId(), label: def.label ?? 'Mặc định', target_node_id: def.target_node_id ?? null }
      : null,
  };
}

function switchCaseLabel(c: SwitchCase, idx: number): string {
  return c.label || c.value || `case ${idx + 1}`;
}

function SwitchCasesEditor({
  config, onChange, nodeId, nodes, edges, onSetEdge,
}: {
  config: Record<string, any>;
  onChange: (cfg: Record<string, any>) => void;
  nodeId: string;
  nodes: CardNode[];
  edges: EdgeOut[];
  onSetEdge: SetEdgeFn;
}) {
  const state = useMemo(() => normalizeSwitch(config), [config]);

  // Edge is source of truth — derive a case/default target by its stable label
  // (see IfElseBranchesEditor.targetOf for why we read edges, not config).
  function targetByLabel(lbl: string): string | null {
    const e = edges.find((x) => String(x.source_node_id) === String(nodeId) && (x.label || '') === lbl);
    return e ? String(e.target_node_id) : null;
  }
  const targetOfCase = (c: SwitchCase, idx: number) => targetByLabel(switchCaseLabel(c, idx));
  const targetOfDefault = () => targetByLabel('DEFAULT');

  function commit(next: { expression: string; cases: SwitchCase[]; default: SwitchCase | null }) {
    onChange({ ...config, expression: next.expression, cases: next.cases, default: next.default });
  }

  function updateExpr(e: string) {
    commit({ ...state, expression: e });
  }

  function updateCase(idx: number, patch: Partial<SwitchCase>) {
    commit({ ...state, cases: state.cases.map((c, i) => i === idx ? { ...c, ...patch } : c) });
  }

  function addCase() {
    commit({ ...state, cases: [...state.cases, { id: genId(), value: '', label: '', target_node_id: null }] });
  }

  function removeCase(idx: number) {
    const c = state.cases[idx];
    const cur = targetOfCase(c, idx);
    if (cur) {
      onSetEdge({ sourceId: nodeId, oldTarget: cur, newTarget: null,
                  condition: c.value ?? null, label: switchCaseLabel(c, idx) });
    }
    commit({ ...state, cases: state.cases.filter((_, i) => i !== idx) });
  }

  // P0 — bind a case (or default) to its target node via a real edge.
  function setCaseTarget(idx: number, targetId: string | null) {
    const c = state.cases[idx];
    onSetEdge({ sourceId: nodeId, oldTarget: targetOfCase(c, idx), newTarget: targetId,
                condition: c.value ?? null, label: switchCaseLabel(c, idx) });
  }

  function setDefaultTarget(targetId: string | null) {
    if (!state.default) return;
    onSetEdge({ sourceId: nodeId, oldTarget: targetOfDefault(), newTarget: targetId,
                condition: null, label: 'DEFAULT' });
  }

  function addDefault() {
    if (state.default) return;
    commit({ ...state, default: { id: genId(), label: 'Mặc định', target_node_id: null } });
  }

  function removeDefault() {
    const cur = targetOfDefault();
    if (cur) {
      onSetEdge({ sourceId: nodeId, oldTarget: cur, newTarget: null,
                  condition: null, label: 'DEFAULT' });
    }
    commit({ ...state, default: null });
  }

  function updateDefault(label: string) {
    commit({ ...state, default: state.default ? { ...state.default, label } : null });
  }

  return (
    <div className="space-y-2 border-l-4 border-violet-400 pl-3 bg-violet-50/40 py-2 rounded-r-md">
      <label className="text-sm font-medium text-violet-900 flex items-center">
        <Network className="w-3.5 h-3.5 inline mr-1" />
        Switch — biểu thức & nhánh case
      </label>

      <div className="space-y-1">
        <label className="text-[11px] text-violet-700">Biểu thức / field cần đánh giá</label>
        <input
          type="text"
          value={state.expression}
          onChange={(e) => updateExpr(e.target.value)}
          placeholder="VD: customer.tier  hoặc  order.status"
          className="w-full h-8 px-2 bg-white border border-violet-200 rounded text-xs font-mono focus:outline-none focus:ring-2 focus:ring-violet-300"
        />
      </div>

      <div className="space-y-1.5">
        {state.cases.length === 0 && (
          <p className="text-[11px] italic text-violet-700/70">Chưa có case nào — bấm "Thêm case" ở dưới.</p>
        )}
        {state.cases.map((c, i) => (
          <div key={c.id} className="bg-white border border-violet-200 rounded-md p-2 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center text-[10px] font-bold px-1.5 py-0.5 rounded bg-violet-500 text-white">
                CASE {i + 1}
              </span>
              <button onClick={() => removeCase(i)}
                      className="p-0.5 text-rose-600 hover:bg-rose-50 rounded"
                      title="Xóa case">
                <X className="w-3 h-3" />
              </button>
            </div>
            <input
              type="text"
              value={c.value ?? ''}
              onChange={(e) => updateCase(i, { value: e.target.value })}
              placeholder='Giá trị (VD: "platinum")'
              className="w-full h-8 px-2 bg-[var(--bg-app)] border border-violet-200 rounded text-xs font-mono focus:outline-none focus:ring-2 focus:ring-violet-300"
            />
            <input
              type="text"
              value={c.label ?? ''}
              onChange={(e) => updateCase(i, { label: e.target.value })}
              placeholder="Nhãn (VD: Khách VIP)"
              className="w-full h-8 px-2 bg-white border border-violet-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-violet-300"
            />
            <BranchTargetSelect
              sourceId={nodeId}
              nodes={nodes}
              value={targetOfCase(c, i)}
              onChange={(t) => setCaseTarget(i, t)}
            />
          </div>
        ))}
        {state.default && (
          <div className="bg-white border border-slate-300 rounded-md p-2 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-500 text-white">
                DEFAULT
              </span>
              <button onClick={removeDefault}
                      className="p-0.5 text-rose-600 hover:bg-rose-50 rounded"
                      title="Xóa default">
                <X className="w-3 h-3" />
              </button>
            </div>
            <input
              type="text"
              value={state.default.label ?? ''}
              onChange={(e) => updateDefault(e.target.value)}
              placeholder="Nhãn nhánh mặc định"
              className="w-full h-8 px-2 bg-white border border-slate-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-slate-300"
            />
            <BranchTargetSelect
              sourceId={nodeId}
              nodes={nodes}
              value={targetOfDefault()}
              onChange={(t) => setDefaultTarget(t)}
            />
          </div>
        )}
      </div>

      <div className="flex gap-2 pt-1">
        <button onClick={addCase}
                className="text-[11px] font-medium text-violet-800 hover:bg-violet-100 px-2 py-1 rounded">
          + Thêm case
        </button>
        {!state.default && (
          <button onClick={addDefault}
                  className="text-[11px] font-medium text-slate-700 hover:bg-slate-100 px-2 py-1 rounded">
            + Thêm default
          </button>
        )}
      </div>
      <p className="text-[10px] text-violet-700/80">
        Mỗi giá trị bằng `expression` rẽ sang 1 nhánh case. `default` chạy khi không case nào khớp.
      </p>
    </div>
  );
}

// ─── WaitEventEditor ─────────────────────────────────────────────
// "Chờ sự kiện" — workflow pauses until external event arrives or timeout.
//
// config: { event_type: 'customer_signed'|'payment_received'|'external_signal',
//           event_name?: string, timeout_minutes?: number }

// ─── ApprovalGateEditor ──────────────────────────────────────────
// Cổng phê duyệt. Ưu tiên gắn CHUỖI DUYỆT (đa cấp + SLA + escalation, cấu hình
// ở "Duyệt & Phân quyền"); nếu chưa có chuỗi thì chọn 1 VAI TRÒ duyệt đơn làm
// fallback. Runtime (approval.py) đọc approval_chain_id → nạp cấp 1; nếu trống
// thì dùng approver_role. Một cổng không chuỗi + không vai trò = rỗng quyền,
// bị chặn khi Chạy thử/Kích hoạt (workflow_builder._check_approval_gates).
function ApprovalGateEditor({
  config, onChange,
}: { config: Record<string, any>; onChange: (cfg: Record<string, any>) => void }) {
  const [chains, setChains] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const chainId = config.approval_chain_id ?? '';
  const role = Array.isArray(config.approver_role) ? config.approver_role[0] : config.approver_role;

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await api<{ chains: any[] }>('/api/v1/approval-chains');
        if (alive) setChains(r.chains ?? []);
      } catch { /* RLS/empty → leave list empty, fallback role still works */ }
      finally { if (alive) setLoading(false); }
    })();
    return () => { alive = false; };
  }, []);

  const selected = chains.find((c) => c.chain_id === chainId);

  return (
    <div className="space-y-2.5 border-l-4 border-amber-400 pl-3 bg-amber-50/40 py-2 rounded-r-md">
      <label className="text-sm font-medium text-amber-900 flex items-center">
        <GitBranch className="w-3.5 h-3.5 inline mr-1" /> Ai được duyệt bước này?
      </label>

      {/* Chuỗi duyệt — ưu tiên */}
      <div className="space-y-1">
        <label className="text-[11px] text-amber-800">Chuỗi duyệt (đa cấp)</label>
        <select
          value={chainId}
          onChange={(e) => onChange({ ...config, approval_chain_id: e.target.value || undefined })}
          className="w-full h-9 px-2 bg-white border border-amber-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-amber-300"
        >
          <option value="">— Không dùng chuỗi (chọn vai trò bên dưới) —</option>
          {chains.map((c) => (
            <option key={c.chain_id} value={c.chain_id}>{c.name_vi || c.name}</option>
          ))}
        </select>
        {loading && <p className="text-[10px] text-amber-700/70 flex items-center"><Loader2 className="w-3 h-3 mr-1 animate-spin" />Đang tải chuỗi duyệt…</p>}
        {!loading && chains.length === 0 && (
          <p className="text-[10px] text-amber-700/80">
            Chưa có chuỗi duyệt nào. Tạo ở <span className="font-medium">Duyệt &amp; Phân quyền → Chuỗi duyệt</span>, hoặc chọn vai trò fallback.
          </p>
        )}
        {selected && (
          <p className="text-[10px] text-amber-700/80">✓ Gắn chuỗi: <span className="font-medium">{selected.name_vi || selected.name}</span> — gate mở ở cấp 1, đi theo các cấp đã cấu hình.</p>
        )}
      </div>

      {/* Vai trò fallback — chỉ khi không gắn chuỗi */}
      {!chainId && (
        <div className="space-y-1">
          <label className="text-[11px] text-amber-800">Vai trò duyệt (fallback)</label>
          <select
            value={role ?? ''}
            onChange={(e) => onChange({ ...config, approver_role: e.target.value || undefined })}
            className="w-full h-9 px-2 bg-white border border-amber-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-amber-300"
          >
            <option value="">— Chọn vai trò —</option>
            <option value="MANAGER">MANAGER (Quản lý)</option>
            <option value="ANALYST">ANALYST (Phân tích)</option>
            <option value="OPERATOR">OPERATOR (Vận hành)</option>
            <option value="ADMIN">ADMIN (Quản trị)</option>
          </select>
        </div>
      )}

      {/* Khi quá hạn SLA */}
      <div className="space-y-1">
        <label className="text-[11px] text-amber-800">Khi quá hạn duyệt</label>
        <select
          value={config.timeout_action ?? 'escalate'}
          onChange={(e) => onChange({ ...config, timeout_action: e.target.value })}
          className="w-full h-8 px-2 bg-white border border-amber-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-amber-300"
        >
          <option value="escalate">Báo cấp trên (escalate)</option>
          <option value="approve">Tự duyệt</option>
          <option value="reject">Tự từ chối</option>
        </select>
      </div>

      {!chainId && !String(role ?? '').trim() && (
        <p className="text-[10px] text-red-600">⚠ Cổng rỗng quyền — chưa gắn chuỗi hoặc vai trò. Workflow sẽ bị chặn khi Chạy thử/Kích hoạt.</p>
      )}
    </div>
  );
}

function WaitEventEditor({
  config, onChange,
}: { config: Record<string, any>; onChange: (cfg: Record<string, any>) => void }) {
  return (
    <div className="space-y-2 border-l-4 border-blue-400 pl-3 bg-blue-50/40 py-2 rounded-r-md">
      <label className="text-sm font-medium text-blue-900 flex items-center">
        <Clock className="w-3.5 h-3.5 inline mr-1" /> Chờ sự kiện gì?
      </label>
      <select
        value={config.event_type ?? 'customer_signed'}
        onChange={(e) => onChange({ ...config, event_type: e.target.value })}
        className="w-full h-9 px-2 bg-white border border-blue-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
      >
        <option value="customer_signed">Khách ký hợp đồng</option>
        <option value="payment_received">Khách thanh toán</option>
        <option value="document_uploaded">Khách upload tài liệu</option>
        <option value="approval_received">Cấp trên phản hồi</option>
        <option value="external_signal">Sự kiện hệ thống ngoài (webhook)</option>
        <option value="custom">Tùy chỉnh</option>
      </select>
      {config.event_type === 'custom' && (
        <input
          type="text"
          value={config.event_name ?? ''}
          onChange={(e) => onChange({ ...config, event_name: e.target.value })}
          placeholder="Tên sự kiện (VD: vendor_response_received)"
          className="w-full h-8 px-2 bg-white border border-blue-200 rounded text-xs font-mono focus:outline-none focus:ring-2 focus:ring-blue-300"
        />
      )}
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-[11px] text-blue-700">Hết hạn (phút)</label>
          <input
            type="number"
            min={1}
            value={config.timeout_minutes ?? ''}
            onChange={(e) => onChange({ ...config, timeout_minutes: e.target.value ? Number(e.target.value) : null })}
            placeholder="VD: 2880 (= 2 ngày)"
            className="w-full h-8 px-2 bg-white border border-blue-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
          />
        </div>
        <div>
          <label className="text-[11px] text-blue-700">Khi hết hạn</label>
          <select
            value={config.on_timeout ?? 'continue'}
            onChange={(e) => onChange({ ...config, on_timeout: e.target.value })}
            className="w-full h-8 px-2 bg-white border border-blue-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
          >
            <option value="continue">Tiếp tục workflow</option>
            <option value="abort">Hủy workflow</option>
            <option value="escalate">Báo cấp trên</option>
          </select>
        </div>
      </div>
      <p className="text-[10px] text-blue-700/80">
        Phase 1 lưu metadata. Phase 2 Temporal worker đăng ký signal listener.
      </p>
    </div>
  );
}

// ─── SlaTimerEditor ──────────────────────────────────────────────
// "Hạn xử lý" — workflow tracks deadline; when breached triggers action.

function SlaTimerEditor({
  config, onChange,
}: { config: Record<string, any>; onChange: (cfg: Record<string, any>) => void }) {
  return (
    <div className="space-y-2 border-l-4 border-rose-400 pl-3 bg-rose-50/40 py-2 rounded-r-md">
      <label className="text-sm font-medium text-rose-900 flex items-center">
        <AlarmClock className="w-3.5 h-3.5 inline mr-1" /> Hạn xử lý
      </label>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-[11px] text-rose-700">Thời hạn (phút)</label>
          <input
            type="number"
            min={1}
            value={config.deadline_minutes ?? ''}
            onChange={(e) => onChange({ ...config, deadline_minutes: e.target.value ? Number(e.target.value) : null })}
            placeholder="VD: 480 (= 8h)"
            className="w-full h-8 px-2 bg-white border border-rose-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-rose-300"
          />
        </div>
        <div>
          <label className="text-[11px] text-rose-700">Cảnh báo trước (phút)</label>
          <input
            type="number"
            min={0}
            value={config.warn_before_minutes ?? ''}
            onChange={(e) => onChange({ ...config, warn_before_minutes: e.target.value ? Number(e.target.value) : null })}
            placeholder="VD: 60"
            className="w-full h-8 px-2 bg-white border border-rose-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-rose-300"
          />
        </div>
      </div>
      <div>
        <label className="text-[11px] text-rose-700">Khi quá hạn</label>
        <select
          value={config.on_timeout_action ?? 'notify'}
          onChange={(e) => onChange({ ...config, on_timeout_action: e.target.value })}
          className="w-full h-8 px-2 bg-white border border-rose-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-rose-300"
        >
          <option value="notify">Cảnh báo nhẹ</option>
          <option value="escalate">Leo thang lên cấp trên</option>
          <option value="reassign">Giao cho người khác</option>
          <option value="abort">Hủy workflow</option>
        </select>
      </div>
      <input
        type="text"
        value={config.escalate_to ?? ''}
        onChange={(e) => onChange({ ...config, escalate_to: e.target.value })}
        placeholder="Người nhận leo thang (VD: department_manager / @giamdocsales)"
        className="w-full h-8 px-2 bg-white border border-rose-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-rose-300"
      />
      <p className="text-[10px] text-rose-700/80">
        Phase 2 Temporal kích hoạt timer tự động. Phase 1 báo cáo SLA breach
        qua dashboard.
      </p>
    </div>
  );
}

// ─── ParallelSplitEditor ─────────────────────────────────────────

function ParallelSplitEditor({
  config, onChange,
}: { config: Record<string, any>; onChange: (cfg: Record<string, any>) => void }) {
  const branches: Array<{ id: string; label: string }> = Array.isArray(config.branches)
    ? config.branches
    : Array.from({ length: Number(config.branch_count ?? 2) }, (_, i) => ({
        id: `pb${i + 1}`,
        label: `Nhánh ${i + 1}`,
      }));

  function update(idx: number, label: string) {
    const next = branches.map((b, i) => i === idx ? { ...b, label } : b);
    onChange({ ...config, branches: next, branch_count: next.length });
  }
  function add() {
    if (branches.length >= 6) return;
    onChange({
      ...config,
      branches: [...branches, { id: `pb${branches.length + 1}`, label: `Nhánh ${branches.length + 1}` }],
      branch_count: branches.length + 1,
    });
  }
  function remove(idx: number) {
    if (branches.length <= 2) return;
    const next = branches.filter((_, i) => i !== idx);
    onChange({ ...config, branches: next, branch_count: next.length });
  }

  return (
    <div className="space-y-2 border-l-4 border-indigo-500 pl-3 bg-indigo-50/40 py-2 rounded-r-md">
      <label className="text-sm font-medium text-indigo-900 flex items-center">
        <Split className="w-3.5 h-3.5 inline mr-1" /> Chạy song song
      </label>
      <p className="text-[10px] text-indigo-700">
        VD: gửi review hợp đồng cho Pháp chế + Tài chính + Vận hành cùng lúc.
      </p>
      {branches.map((b, i) => (
        <div key={b.id} className="flex items-center gap-2">
          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-indigo-500 text-white shrink-0">
            #{i + 1}
          </span>
          <input
            type="text"
            value={b.label}
            onChange={(e) => update(i, e.target.value)}
            placeholder={`Tên nhánh ${i + 1}`}
            className="flex-1 h-8 px-2 bg-white border border-indigo-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-indigo-300"
          />
          {branches.length > 2 && (
            <button onClick={() => remove(i)} className="p-0.5 text-rose-600 hover:bg-rose-50 rounded">
              <X className="w-3 h-3" />
            </button>
          )}
        </div>
      ))}
      {branches.length < 6 && (
        <button onClick={add} className="text-[11px] font-medium text-indigo-800 hover:bg-indigo-100 px-2 py-1 rounded">
          + Thêm nhánh
        </button>
      )}
    </div>
  );
}

// ─── ParallelJoinEditor ──────────────────────────────────────────

function ParallelJoinEditor({
  config, onChange,
}: { config: Record<string, any>; onChange: (cfg: Record<string, any>) => void }) {
  return (
    <div className="space-y-2 border-l-4 border-indigo-500 pl-3 bg-indigo-50/40 py-2 rounded-r-md">
      <label className="text-sm font-medium text-indigo-900 flex items-center">
        <Merge className="w-3.5 h-3.5 inline mr-1" /> Hợp nhánh — điều kiện join
      </label>
      <div>
        <label className="text-[11px] text-indigo-700">Khi nào tiếp tục?</label>
        <select
          value={config.join_mode ?? 'all'}
          onChange={(e) => onChange({ ...config, join_mode: e.target.value })}
          className="w-full h-8 px-2 bg-white border border-indigo-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-indigo-300"
        >
          <option value="all">Tất cả nhánh xong (AND)</option>
          <option value="any">Bất kỳ nhánh nào xong (OR)</option>
          <option value="n_of_m">N trên tổng số (đa số)</option>
        </select>
      </div>
      {config.join_mode === 'n_of_m' && (
        <div>
          <label className="text-[11px] text-indigo-700">N (số nhánh cần xong)</label>
          <input
            type="number"
            min={1}
            value={config.n_required ?? ''}
            onChange={(e) => onChange({ ...config, n_required: e.target.value ? Number(e.target.value) : null })}
            placeholder="VD: 2 (2 trên 3 reviewer OK)"
            className="w-full h-8 px-2 bg-white border border-indigo-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-indigo-300"
          />
        </div>
      )}
      <p className="text-[10px] text-indigo-700/80">
        Phase 2 Temporal worker đếm token từ split tương ứng.
      </p>
    </div>
  );
}

// ─── SubworkflowEditor ───────────────────────────────────────────

function SubworkflowEditor({
  config, onChange,
}: { config: Record<string, any>; onChange: (cfg: Record<string, any>) => void }) {
  const [workflows, setWorkflows] = React.useState<Array<{ workflow_id: string; name: string; name_vi: string | null }>>([]);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await api<any[]>('/api/v1/workflows?limit=200');
        if (!cancelled) setWorkflows((list ?? []).map((w) => ({
          workflow_id: w.workflow_id, name: w.name, name_vi: w.name_vi,
        })));
      } catch {}
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="space-y-2 border-l-4 border-slate-500 pl-3 bg-slate-50/40 py-2 rounded-r-md">
      <label className="text-sm font-medium text-slate-900 flex items-center">
        <Boxes className="w-3.5 h-3.5 inline mr-1" /> Quy trình con
      </label>
      <p className="text-[10px] text-slate-700">
        VD: trong quy trình "Mở tài khoản khách" gọi quy trình con "KYC".
      </p>
      <select
        value={config.target_workflow_id ?? ''}
        onChange={(e) => {
          const wf = workflows.find((w) => w.workflow_id === e.target.value);
          onChange({
            ...config,
            target_workflow_id: e.target.value || null,
            target_workflow_name: wf ? (wf.name_vi || wf.name) : null,
          });
        }}
        className="w-full h-9 px-2 bg-white border border-slate-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-slate-300"
      >
        <option value="">— chọn workflow con —</option>
        {workflows.map((w) => (
          <option key={w.workflow_id} value={w.workflow_id}>
            {w.name_vi || w.name}
          </option>
        ))}
      </select>
      <div>
        <label className="text-[11px] text-slate-700">Chế độ chạy</label>
        <select
          value={config.run_mode ?? 'sync'}
          onChange={(e) => onChange({ ...config, run_mode: e.target.value })}
          className="w-full h-8 px-2 bg-white border border-slate-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-slate-300"
        >
          <option value="sync">Đồng bộ — đợi xong rồi đi tiếp</option>
          <option value="async">Bất đồng bộ — fire & forget</option>
        </select>
      </div>
    </div>
  );
}

// ─── NotificationEditor ──────────────────────────────────────────

function NotificationEditor({
  config, onChange,
}: { config: Record<string, any>; onChange: (cfg: Record<string, any>) => void }) {
  const recipients: string[] = Array.isArray(config.recipients) ? config.recipients : [];
  const [draft, setDraft] = React.useState('');

  function addRecipient() {
    const v = draft.trim();
    if (!v || recipients.includes(v)) return;
    onChange({ ...config, recipients: [...recipients, v] });
    setDraft('');
  }
  function remove(r: string) {
    onChange({ ...config, recipients: recipients.filter((x) => x !== r) });
  }

  return (
    <div className="space-y-2 border-l-4 border-sky-500 pl-3 bg-sky-50/40 py-2 rounded-r-md">
      <label className="text-sm font-medium text-sky-900 flex items-center">
        <Bell className="w-3.5 h-3.5 inline mr-1" /> Thông báo
      </label>
      <div>
        <label className="text-[11px] text-sky-700">Kênh</label>
        <select
          value={config.channel ?? 'email'}
          onChange={(e) => onChange({ ...config, channel: e.target.value })}
          className="w-full h-8 px-2 bg-white border border-sky-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-sky-300"
        >
          <option value="email">Email</option>
          <option value="zalo">Zalo</option>
          <option value="teams">MS Teams</option>
          <option value="telegram">Telegram</option>
          <option value="sms">SMS</option>
          <option value="in_app">Trong app</option>
        </select>
      </div>
      <div>
        <label className="text-[11px] text-sky-700">Người nhận</label>
        <div className="flex flex-wrap gap-1 mb-1.5">
          {recipients.map((r) => (
            <span key={r} className="inline-flex items-center gap-1 text-[11px] font-medium text-sky-700 bg-sky-100 px-2 py-0.5 rounded">
              {r}
              <button onClick={() => remove(r)} className="text-sky-700 hover:text-rose-600"><X className="w-2.5 h-2.5" /></button>
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addRecipient(); } }}
            placeholder="email / @user / role:MANAGER / dept:sales"
            className="flex-1 h-8 px-2 bg-white border border-sky-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-sky-300"
          />
          <button onClick={addRecipient} className="px-3 py-1 text-xs font-medium text-sky-800 hover:bg-sky-100 rounded">+ Thêm</button>
        </div>
      </div>
      <div>
        <label className="text-[11px] text-sky-700">Mẫu nội dung</label>
        <textarea
          value={config.template ?? ''}
          onChange={(e) => onChange({ ...config, template: e.target.value })}
          rows={2}
          placeholder="VD: Đơn {{order_id}} cần duyệt — xem tại {{link}}"
          className="w-full px-2 py-1.5 bg-white border border-sky-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-sky-300"
        />
      </div>
    </div>
  );
}

// ─── TreeView ────────────────────────────────────────────────────

interface CrossLink {
  link_id:                 string;
  source_workflow_id:      string;
  target_workflow_id:      string;
  link_type:               'triggers' | 'depends_on' | 'notifies' | 'data_handoff';
  condition:               string | null;
  label:                   string | null;
  is_active:               boolean;
  source_workflow_name:    string | null;
  source_workflow_name_vi: string | null;
  source_enterprise_name:  string | null;
  source_node_title:       string | null;
  source_node_title_vi:    string | null;
  source_department_name:  string | null;
  source_dept_type:        string | null;
  target_workflow_name:    string | null;
  target_workflow_name_vi: string | null;
  target_enterprise_name:  string | null;
  target_node_title:       string | null;
  target_node_title_vi:    string | null;
  target_department_name:  string | null;
  target_dept_type:        string | null;
  crosses_enterprise:      boolean;
  crosses_department:      boolean;
  crosses_branch:          boolean;
  crosses_division:        boolean;
  crosses_corporate_group: boolean;
}

// ADR-0037 Tier-3 — document status + class metadata (business Vietnamese).
const DOC_STATUS_META: Record<string, { label: string; variant: any }> = {
  cho_nop:         { label: 'Chờ nộp',         variant: 'default' },
  da_nop:          { label: 'Đã nộp',          variant: 'info' },
  dang_xem_xet:    { label: 'Đang xem xét',    variant: 'warning' },
  da_duyet:        { label: 'Đã duyệt',        variant: 'success' },
  tu_choi:         { label: 'Từ chối',         variant: 'error' },
  yeu_cau_bo_sung: { label: 'Yêu cầu bổ sung', variant: 'warning' },
  het_han:         { label: 'Hết hạn',         variant: 'error' },
};
const DOC_CLASS_META: Record<string, { label: string; ring: string; tint: string }> = {
  input:     { label: '📥 Tài liệu đầu vào',   ring: 'border-[#6B8CAE]/40', tint: 'text-[#5470A0]' },
  output:    { label: '📤 Tài liệu đầu ra',    ring: 'border-[#5C856A]/40', tint: 'text-[#5C856A]' },
  reference: { label: '📎 Tài liệu tham chiếu', ring: 'border-[var(--border-color)]', tint: 'text-[var(--text-secondary)]' },
};

interface DocSlot {
  requirement_id: string | null;
  name_vi: string;
  description: string | null;
  is_required: boolean;
  status: string;
  version_count: number;
  document: any | null;
}
interface DocStep {
  node_id: string; title: string; lane_name: string | null;
  input: DocSlot[]; output: DocSlot[]; reference: DocSlot[]; doc_count: number;
}

function TreeView({ workflowId, cards }: { workflowId: string; cards: CardNode[] }) {
  const [crossLinks, setCrossLinks] = React.useState<CrossLink[]>([]);
  const [linksLoading, setLinksLoading] = React.useState(true);
  const [steps, setSteps] = React.useState<DocStep[] | null>(null);
  const [treeLoading, setTreeLoading] = React.useState(true);

  // ADR-0037 — the 3-tier document tree (class + status + version). Extracted
  // so the per-step config modal can trigger a refetch after add/delete —
  // otherwise the outer "X mục tài liệu" / per-step "X tài liệu" badges stay
  // stale until a full page reload (the bug anh hit on 2026-06-01).
  const loadSteps = React.useCallback(async () => {
    try {
      const t = await api<{ steps: DocStep[] }>(`/api/v1/workflows/${workflowId}/document-tree`);
      setSteps(t.steps ?? []);
    } catch {
      setSteps([]);
    }
  }, [workflowId]);

  React.useEffect(() => {
    let cancelled = false;
    setTreeLoading(true);
    setLinksLoading(true);
    (async () => {
      await loadSteps();
      if (!cancelled) setTreeLoading(false);
      try {
        const links = await api<CrossLink[]>(`/api/v1/workflow-cross-links?workflow_id=${workflowId}`);
        if (!cancelled) setCrossLinks(links ?? []);
      } catch {
        // Best-effort.
      } finally {
        if (!cancelled) setLinksLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [workflowId, loadSteps]);

  const totalDocs = (steps ?? []).reduce((s, st) => s + st.doc_count, 0);

  return (
    <div className="space-y-4">
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
        <div className="flex items-center justify-between mb-4 pb-3 border-b border-[var(--border-color)]/60">
          <div>
            <h3 className="font-serif text-base text-[var(--text-primary)]">Cây tài liệu</h3>
            <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">
              Mỗi bước → tài liệu <span className="text-[#5470A0]">đầu vào</span> cần nộp ·{' '}
              <span className="text-[#5C856A]">đầu ra</span> được tạo · <span>tham chiếu</span> để làm theo.
            </p>
          </div>
          <Badge variant="default">{totalDocs} mục tài liệu</Badge>
        </div>

        {treeLoading ? (
          <div className="flex items-center justify-center py-8 text-[var(--text-secondary)] text-sm">
            <Loader2 className="w-4 h-4 animate-spin mr-2" /> Đang tải cây tài liệu…
          </div>
        ) : !steps || steps.length === 0 ? (
          <p className="text-sm text-[var(--text-secondary)] py-8 text-center">
            Workflow chưa có bước nào, hoặc chưa cấu hình tài liệu cho bước.
          </p>
        ) : (
          <div className="space-y-3">
            {steps.map((st, i) => <DocStepCard key={st.node_id} index={i} step={st} workflowId={workflowId} onMutated={loadSteps} />)}
          </div>
        )}
      </div>

      <CrossLinksSection
        workflowId={workflowId}
        links={crossLinks}
        loading={linksLoading}
      />
    </div>
  );
}

function DocStepCard({ index, step, workflowId, onMutated }: { index: number; step: DocStep; workflowId: string; onMutated: () => void }) {
  const [open, setOpen] = React.useState(true);
  const [configuring, setConfiguring] = React.useState(false);
  const classes: Array<'input' | 'output' | 'reference'> = ['input', 'output', 'reference'];
  const hasAny = classes.some((c) => (step[c] ?? []).length > 0);
  return (
    <div className="rounded-lg-custom border border-[var(--border-color)] bg-[var(--bg-app)]/20 overflow-hidden">
      <button onClick={() => setOpen((p) => !p)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-[var(--bg-app)]/40 transition-colors">
        <span className="w-6 h-6 rounded-full bg-[var(--primary-gold)]/15 text-[var(--primary-gold-dark)] text-xs font-semibold flex items-center justify-center shrink-0">
          {index + 1}
        </span>
        <span className="font-medium text-sm text-[var(--text-primary)] flex-1 min-w-0 truncate">{step.title || 'Bước'}</span>
        {step.lane_name && <Badge variant="default" className="text-[10px]">{step.lane_name}</Badge>}
        <span
          role="button" tabIndex={0}
          onClick={(e) => { e.stopPropagation(); setConfiguring(true); }}
          className="text-[11px] text-[var(--primary-gold-dark)] hover:underline shrink-0 inline-flex items-center gap-1">
          <FilePlus className="w-3.5 h-3.5" /> Cấu hình
        </span>
        <span className="text-[11px] text-[var(--text-secondary)] shrink-0">{step.doc_count} tài liệu</span>
        <ChevronDown className={cn('w-4 h-4 text-[var(--text-secondary)] shrink-0 transition-transform', open ? '' : '-rotate-90')} />
      </button>
      {open && (
        <div className="px-4 pb-4 pt-1 space-y-3">
          {classes.map((cls) => {
            const slots = step[cls];
            if (!slots || slots.length === 0) return null;
            const meta = DOC_CLASS_META[cls];
            return (
              <div key={cls} className={cn('rounded-md-custom border bg-[var(--bg-card)] p-3', meta.ring)}>
                <p className={cn('text-[11px] font-medium mb-2', meta.tint)}>{meta.label}</p>
                <div className="space-y-1.5">
                  {slots.map((slot, j) => <DocSlotRow key={slot.requirement_id ?? j} slot={slot}
                    workflowId={workflowId} nodeId={step.node_id} onMutated={onMutated} />)}
                </div>
              </div>
            );
          })}
          {!hasAny && <p className="text-xs text-[var(--text-secondary)] py-2">Chưa cấu hình tài liệu cho bước này — bấm "Cấu hình".</p>}
        </div>
      )}
      {configuring && <RequirementConfigModal workflowId={workflowId} nodeId={step.node_id} title={step.title}
        onClose={() => setConfiguring(false)} onMutated={onMutated} />}
    </div>
  );
}

// ADR-0037 Phase 1 — configure the input/output/reference documents a step needs.
function RequirementConfigModal({ workflowId, nodeId, title, onClose, onMutated }: any) {
  const [reqs, setReqs] = React.useState<any[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [cls, setCls] = React.useState('input');
  const [name, setName] = React.useState('');
  const [required, setRequired] = React.useState(true);
  const CLASS_OPT = [['input', '📥 Đầu vào'], ['output', '📤 Đầu ra'], ['reference', '📎 Tham chiếu']];

  async function load() {
    setLoading(true);
    try { setReqs((await api<any>(`/api/v1/workflows/${workflowId}/nodes/${nodeId}/doc-requirements`)).requirements ?? []); }
    catch { /* empty */ } finally { setLoading(false); }
  }
  React.useEffect(() => { load(); }, [nodeId]);

  async function add() {
    if (!name) return;
    await api(`/api/v1/workflows/${workflowId}/nodes/${nodeId}/doc-requirements`, {
      method: 'POST', body: JSON.stringify({ doc_class: cls, name_vi: name, is_required: required }),
    });
    setName(''); load(); onMutated?.();
  }
  async function del(id: string) { await api(`/api/v1/doc-requirements/${id}`, { method: 'DELETE' }); load(); onMutated?.(); }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/40" onClick={onClose}>
      <div className="w-full max-w-lg bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-2xl p-5 space-y-4" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h2 className="font-serif text-base text-[var(--text-primary)]">Tài liệu cần thiết — {title}</h2>
          <button onClick={onClose}><X className="w-5 h-5 text-[var(--text-secondary)]" /></button>
        </div>
        {loading ? <div className="py-6 text-center text-[var(--text-secondary)]"><Loader2 className="w-5 h-5 animate-spin inline" /></div> : (
          <div className="space-y-1.5 max-h-64 overflow-y-auto">
            {reqs.length === 0 && <p className="text-sm text-[var(--text-secondary)] py-2">Chưa có tài liệu nào.</p>}
            {reqs.map((r) => (
              <div key={r.requirement_id} className="flex items-center gap-2 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] px-3 py-2">
                <span className="text-xs">{CLASS_OPT.find((o) => o[0] === r.doc_class)?.[1]?.split(' ')[0]}</span>
                <span className="text-sm text-[var(--text-primary)] flex-1 truncate">{r.name_vi}{r.is_required && <span className="text-[var(--state-error)]"> *</span>}</span>
                <button onClick={() => del(r.requirement_id)} className="text-[var(--text-secondary)] hover:text-[var(--state-error)]"><Trash2 className="w-3.5 h-3.5" /></button>
              </div>
            ))}
          </div>
        )}
        <div className="flex items-end gap-2 pt-2 border-t border-[var(--border-color)]">
          <div className="w-28"><label className="text-[11px] text-[var(--text-secondary)] block mb-1">Loại</label>
            <select value={cls} onChange={(e) => setCls(e.target.value)} className="w-full h-9 rounded-md-custom border border-[var(--border-color)] bg-white px-2 text-sm">
              {CLASS_OPT.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </select>
          </div>
          <div className="flex-1"><label className="text-[11px] text-[var(--text-secondary)] block mb-1">Tên tài liệu</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Đơn yêu cầu, CMND…"
              className="w-full h-9 rounded-md-custom border border-[var(--border-color)] bg-white px-3 text-sm" />
          </div>
          <label className="flex items-center gap-1 text-xs text-[var(--text-secondary)] h-9"><input type="checkbox" checked={required} onChange={(e) => setRequired(e.target.checked)} /> Bắt buộc</label>
          <Button onClick={add} disabled={!name}><Plus className="w-4 h-4" /></Button>
        </div>
      </div>
    </div>
  );
}

function DocSlotRow({ slot, workflowId, nodeId, onMutated }: {
  slot: DocSlot; workflowId: string; nodeId: string; onMutated: () => void;
}) {
  const sm = DOC_STATUS_META[slot.status] ?? DOC_STATUS_META.cho_nop;
  const [viewing, setViewing] = React.useState(false);
  const [uploading, setUploading] = React.useState(false);
  const [upErr, setUpErr] = React.useState<string | null>(null);
  const fileRef = React.useRef<HTMLInputElement>(null);
  const attId = slot.document?.attachment_id;

  // ADR-0037 Phase 0 — fetch bytes with the canonical Bearer (a plain <a> can't
  // carry the header) then open the blob in a new tab.
  async function view() {
    if (!attId) return;
    setViewing(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/workflow-documents/${attId}/download`, {
        headers: { Authorization: `Bearer ${window.localStorage.getItem('kaori.access_token') ?? ''}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const url = URL.createObjectURL(await res.blob());
      window.open(url, '_blank');
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch {
      /* file bytes may not be stored yet (uploaded before Phase 0) */
    } finally {
      setViewing(false);
    }
  }

  // ADR-0037 Tier-3 — fulfil this requirement by uploading a real document.
  // Tagged with X-Workflow-Step-ID + X-Requirement-ID so the data-pipeline
  // ingestor lands it as a CLASSIFIED workflow_step_documents instance
  // (status 'da_nop') linked to bronze + sha256-deduped (K-8) — NOT through the
  // analytics column-mapping wizard (wrong tool for a PDF/đơn). The gateway
  // injects enterprise/user from the JWT (K-12); we never send those.
  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    e.target.value = '';  // allow re-picking the same filename
    if (!f) return;
    setUploading(true);
    setUpErr(null);
    try {
      let hint = '';
      try {
        const dig = await crypto.subtle.digest('SHA-256', await f.arrayBuffer());
        hint = Array.from(new Uint8Array(dig)).map((b) => b.toString(16).padStart(2, '0')).join('');
      } catch { /* sha256 hint is best-effort (K-8 dedup still works server-side) */ }
      const fd = new FormData();
      fd.append('file', f);
      if (hint) fd.append('sha256_hint', hint);
      const headers: Record<string, string> = {
        Authorization: `Bearer ${window.localStorage.getItem('kaori.access_token') ?? ''}`,
        'X-Workflow-Step-ID': nodeId,
        'Idempotency-Key': `wsdoc-${hint || crypto.randomUUID()}`,
      };
      if (slot.requirement_id) headers['X-Requirement-ID'] = slot.requirement_id;
      const res = await fetch(`${API_BASE}/api/v1/upload`, { method: 'POST', headers, body: fd });
      if (!res.ok) {
        let detail = `HTTP ${res.status}`;
        try {
          const j = await res.json();
          detail = (typeof j.detail === 'string' ? j.detail : j.detail?.message) || j.title || detail;
        } catch { /* non-JSON error body */ }
        throw new Error(detail);
      }
      onMutated();  // refetch the tree → slot flips to "Đã nộp" + file appears, no reload
    } catch (err: any) {
      setUpErr(err?.message || 'Nộp file thất bại');
    } finally {
      setUploading(false);
    }
  }

  const canUpload = !!slot.requirement_id && slot.status !== 'da_duyet';

  // Option 1 — analyze the uploaded document → summary + key fields + risks.
  const [analyzing, setAnalyzing] = React.useState(false);
  const [analysis, setAnalysis] = React.useState<any | null>(null);
  async function analyze() {
    if (!attId) return;
    setAnalyzing(true);
    const prevId = analysis?.analysis_id;
    try {
      await api(`/api/v1/workflow-documents/${attId}/analyze`, { method: 'POST' });
      for (let i = 0; i < 20; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        const r: any = await api(`/api/v1/workflow-documents/${attId}/analysis`);
        if (r?.status === 'done' && r.analysis_id !== prevId) { setAnalysis(r); break; }
      }
    } catch { /* best-effort */ } finally { setAnalyzing(false); }
  }

  return (
    <div className="py-1">
      <div className="flex items-center gap-2">
        <span className="text-sm text-[var(--text-primary)] flex-1 min-w-0 truncate">
          {slot.name_vi}
          {slot.is_required && slot.status === 'cho_nop' && <span className="text-[var(--state-error)] ml-1">*</span>}
        </span>
        {slot.version_count > 1 && (
          <span className="text-[10px] text-[var(--text-secondary)] font-mono">v{slot.version_count}</span>
        )}
        {slot.document?.filename && (
          <button onClick={view} disabled={viewing}
            className="text-[11px] text-[var(--primary-gold-dark)] hover:underline truncate max-w-[180px] inline-flex items-center gap-1"
            title={`Xem ${slot.document.filename}`}>
            {viewing ? <Loader2 className="w-3 h-3 animate-spin" /> : <ExternalLink className="w-3 h-3" />}
            {slot.document.filename}
          </button>
        )}
        {slot.document?.attachment_id && (
          <button onClick={analyze} disabled={analyzing}
            className="text-[11px] text-purple-700 hover:underline shrink-0 inline-flex items-center gap-1 disabled:opacity-50"
            title="Phân tích tài liệu (tóm tắt + trường khoá + rủi ro)">
            {analyzing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Tag className="w-3 h-3" />}
            Phân tích
          </button>
        )}
        {canUpload && (
          <>
            <input ref={fileRef} type="file" hidden onChange={onPick}
              accept=".pdf,.docx,.doc,.xlsx,.xls,.csv,.png,.jpg,.jpeg,.tiff,.webp,.pptx,.md" />
            <button onClick={() => fileRef.current?.click()} disabled={uploading}
              className="text-[11px] text-[var(--primary-gold-dark)] hover:underline shrink-0 inline-flex items-center gap-1 disabled:opacity-50"
              title={slot.document ? 'Nộp bản mới' : 'Nộp file'}>
              {uploading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Upload className="w-3 h-3" />}
              {slot.document ? 'Nộp lại' : 'Nộp file'}
            </button>
          </>
        )}
        <Badge variant={sm.variant} className="text-[10px] shrink-0">{sm.label}</Badge>
        {upErr && <span className="text-[10px] text-[var(--state-error)] shrink-0 truncate max-w-[120px]" title={upErr}>{upErr}</span>}
      </div>

      {analysis?.status === 'done' && (
        <div className="mt-1.5 ml-2 rounded-md-custom border border-purple-200 bg-purple-50/50 p-2.5 space-y-1.5">
          {analysis.summary && <p className="text-xs text-[var(--text-primary)]">{analysis.summary}</p>}
          {Array.isArray(analysis.key_fields) && analysis.key_fields.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {analysis.key_fields.map((f: any, i: number) => (
                <span key={i} className="text-[10px] bg-white border border-purple-200 rounded px-1.5 py-0.5">
                  <span className="text-[var(--text-secondary)]">{f.label}:</span> <span className="font-medium">{f.value}</span>
                </span>
              ))}
            </div>
          )}
          {Array.isArray(analysis.risks) && analysis.risks.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {analysis.risks.map((r: any, i: number) => (
                <span key={i} className={cn('text-[10px] rounded px-1.5 py-0.5 border',
                  r.severity === 'high' ? 'bg-rose-50 text-rose-700 border-rose-200' : 'bg-amber-50 text-amber-700 border-amber-200')}
                  title={r.snippet}>
                  ⚠ {r.keyword}
                </span>
              ))}
            </div>
          )}
          <p className="text-[10px] text-[var(--text-secondary)] italic">
            {analysis.model === 'qwen2.5-local' ? 'Qwen + quét rủi ro' : 'Quét rủi ro (Qwen tạm offline)'} · gợi ý AI, không phải phán quyết
          </p>
        </div>
      )}
    </div>
  );
}

function CrossLinksSection({
  workflowId, links, loading,
}: { workflowId: string; links: CrossLink[]; loading: boolean }) {
  const incoming = links.filter((l) => l.target_workflow_id === workflowId);
  const outgoing = links.filter((l) => l.source_workflow_id === workflowId);

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-[var(--border-color)]/60">
        <div>
          <h3 className="font-serif text-base text-[var(--text-primary)]">
            <Network className="w-4 h-4 inline mr-1.5 text-[var(--primary-gold-dark)]" />
            Workflow liên quan
          </h3>
          <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">
            Liên kết workflow giữa phòng ban / công ty / mảng / tập đoàn — Phase 2 sẽ tự trigger qua Temporal.
          </p>
        </div>
        <Badge variant="default">{links.length} liên kết</Badge>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-4 text-[var(--text-secondary)] text-sm">
          <Loader2 className="w-4 h-4 animate-spin mr-2" /> Đang tải liên kết…
        </div>
      ) : links.length === 0 ? (
        <p className="text-[11px] italic text-[var(--text-secondary)] py-2">
          Workflow này chưa có liên kết. Tạo cross-link qua{' '}
          <code className="font-mono text-[10px] bg-[var(--bg-app)] px-1 py-0.5 rounded">
            POST /api/v1/workflow-cross-links
          </code>.
        </p>
      ) : (
        <div className="space-y-4">
          {incoming.length > 0 && (
            <CrossLinkList title="Workflow trigger workflow này (→)" direction="incoming" links={incoming} />
          )}
          {outgoing.length > 0 && (
            <CrossLinkList title="Workflow này trigger sang (←)" direction="outgoing" links={outgoing} />
          )}
        </div>
      )}
    </div>
  );
}

function CrossLinkList({
  title, direction, links,
}: { title: string; direction: 'incoming' | 'outgoing'; links: CrossLink[] }) {
  return (
    <div>
      <h4 className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] font-medium mb-2">
        {title}
      </h4>
      <div className="space-y-1.5">
        {links.map((l) => <CrossLinkRow key={l.link_id} link={l} direction={direction} />)}
      </div>
    </div>
  );
}

function CrossLinkRow({ link: l, direction }: { link: CrossLink; direction: 'incoming' | 'outgoing' }) {
  const otherWorkflow = direction === 'outgoing' ? l.target_workflow_id : l.source_workflow_id;
  const otherName = direction === 'outgoing'
    ? (l.target_workflow_name_vi || l.target_workflow_name || 'workflow')
    : (l.source_workflow_name_vi || l.source_workflow_name || 'workflow');
  const otherEnterprise = direction === 'outgoing' ? l.target_enterprise_name : l.source_enterprise_name;
  const otherDept = direction === 'outgoing' ? l.target_department_name : l.source_department_name;

  const linkTypeLabel: Record<CrossLink['link_type'], { vi: string; color: string }> = {
    triggers:      { vi: 'Trigger',     color: 'text-emerald-700 bg-emerald-50' },
    depends_on:    { vi: 'Phụ thuộc',   color: 'text-amber-700 bg-amber-50' },
    notifies:      { vi: 'Thông báo',   color: 'text-blue-700 bg-blue-50' },
    data_handoff:  { vi: 'Bàn giao DL', color: 'text-purple-700 bg-purple-50' },
  };
  const lt = linkTypeLabel[l.link_type];

  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-md-custom border border-[var(--border-color)] hover:bg-[var(--bg-app)]/50 text-sm">
      <span className={cn('text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0', lt.color)}>
        {lt.vi}
      </span>
      <ArrowRight className="w-3 h-3 text-[var(--text-secondary)] shrink-0" />
      <div className="flex-1 min-w-0">
        <a
          href={`/p2/workflows/${otherWorkflow}`}
          className="text-sm font-medium text-[var(--text-primary)] hover:text-[var(--primary-gold-dark)] truncate block"
        >
          {otherName}
        </a>
        <p className="text-[10px] text-[var(--text-secondary)] truncate">
          {otherEnterprise || '—'}
          {otherDept ? ` · ${otherDept}` : ''}
        </p>
      </div>
      <CrossDimensionBadges link={l} />
    </div>
  );
}

function CrossDimensionBadges({ link: l }: { link: CrossLink }) {
  const flags: Array<{ on: boolean; label: string; color: string }> = [
    { on: l.crosses_department,      label: 'khác phòng',  color: 'text-blue-700 bg-blue-50' },
    { on: l.crosses_enterprise,      label: 'khác cty',    color: 'text-amber-700 bg-amber-50' },
    { on: l.crosses_branch,          label: 'khác CN',     color: 'text-teal-700 bg-teal-50' },
    { on: l.crosses_division,        label: 'khác mảng',   color: 'text-purple-700 bg-purple-50' },
    { on: l.crosses_corporate_group, label: 'khác T.đoàn', color: 'text-rose-700 bg-rose-50' },
  ];
  const visible = flags.filter((f) => f.on);
  if (visible.length === 0) {
    return <span className="text-[10px] text-[var(--text-secondary)] shrink-0">cùng phòng</span>;
  }
  return (
    <div className="flex items-center gap-1 shrink-0">
      {visible.map((f) => (
        <span key={f.label} className={cn('text-[10px] px-1 py-0.5 rounded', f.color)}>
          {f.label}
        </span>
      ))}
    </div>
  );
}

function TreeStep({ index, card, workflowId }: { index: number; card: CardNode; workflowId: string }) {
  const docs = card.attached_documents ?? [];
  return (
    <div className="border border-[var(--border-color)] rounded-md-custom overflow-hidden">
      <div className="flex items-center justify-between gap-3 px-3 py-2 bg-[var(--bg-app)] border-b border-[var(--border-color)]/60">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-6 h-6 rounded-md-custom bg-[var(--primary-gold)]/15 flex items-center justify-center text-xs font-bold text-[var(--primary-gold-dark)]">
            {index + 1}
          </div>
          <span className="text-sm font-medium text-[var(--text-primary)] truncate">
            {card.title_vi || card.title}
          </span>
          {card.hashtags.slice(0, 2).map((h) => (
            <span key={h} className="text-[10px] font-medium text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded">
              #{h}
            </span>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <DocStatusBadge card={card} />
          <UploadButton workflowId={workflowId} nodeId={card.node_id} />
        </div>
      </div>
      <div className="p-3 space-y-1.5">
        {docs.length === 0 ? (
          <p className="text-[11px] text-[var(--text-secondary)] italic">Chưa có file nào.</p>
        ) : (
          docs.map((d) => (
            <div key={d.attachment_id} className="flex items-center justify-between gap-2 text-xs px-2 py-1.5 hover:bg-[var(--bg-app)] rounded">
              <div className="flex items-center gap-2 min-w-0">
                <FileText className="w-3.5 h-3.5 text-[var(--text-secondary)] shrink-0" />
                <span className="text-[var(--text-primary)] truncate" title={d.filename}>{d.filename}</span>
                {d.document_kind && (
                  <span className="text-[10px] text-[var(--text-secondary)] uppercase">.{d.document_kind}</span>
                )}
              </div>
              <div className="flex items-center gap-3 text-[10px] text-[var(--text-secondary)] shrink-0">
                <span>{d.row_count} dòng</span>
                {d.uploaded_at && <span>{new Date(d.uploaded_at).toLocaleDateString('vi-VN')}</span>}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function UploadButton({ workflowId, nodeId }: { workflowId: string; nodeId: string }) {
  // Build Week: simple link to the pipeline wizard pre-populated with the
  // workflow_step_id. The Pipeline Wizard (already wired Tuần 8 Step 4.1)
  // will pick up the header and pass it through ingest_file.
  // We use a query param so the pipeline-wizard FE can read it.
  const href = `/p2/pipelines/new?workflow_id=${workflowId}&workflow_step_id=${nodeId}`;
  return (
    <a href={href}>
      <Button size="sm" variant="secondary">
        <Upload className="w-3 h-3 mr-1" /> Tải lên
      </Button>
    </a>
  );
}

// ─── Reports tab — Phase 2 (mig 058 stats endpoint) ─────────────────

interface WorkflowStats {
  workflow_id:     string;
  workflow_name:   string;
  department_id:   string;
  node_count:      number;
  edge_count:      number;
  folder_count:    number;
  total_files:     number;
  files_per_step:  Record<string, number>;
  files_per_kind:  Record<string, number>;
  cross_links:     { incoming: number; outgoing: number };
  recent_kpis:     Array<{
    kpi_code: string; raw_value: number | null; classification: string | null;
    period_kind: string | null; period_end: string | null; computed_at: string | null;
  }>;
}

function ReportsTab({ workflowId }: { workflowId: string }) {
  const [stats, setStats] = React.useState<WorkflowStats | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [problem, setProblem] = React.useState<ProblemDetails | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const s = await api<WorkflowStats>(`/api/v1/workflows/${workflowId}/stats`);
        if (!cancelled) setStats(s);
      } catch (e: any) {
        if (!cancelled) setProblem(e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [workflowId]);

  if (loading) {
    return <SkeletonReportsTab />;
  }
  if (problem || !stats) {
    return (
      <ErrorBanner
        problem={problem || { title: formatProblem({ status: 404 }) }}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatBox label="Tổng bước"   value={stats.node_count}    icon={Layers}     tone="text-[var(--primary-gold-dark)]" />
        <StatBox label="Mũi tên nối" value={stats.edge_count}    icon={GitBranch}  tone="text-blue-700" />
        <StatBox label="Folder"      value={stats.folder_count}  icon={FilePlus}   tone="text-purple-700" />
        <StatBox label="Tổng file"   value={stats.total_files}   icon={FileText}   tone="text-emerald-700" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <KvCard
          title="File theo loại tài liệu"
          icon={FileText}
          rows={Object.entries(stats.files_per_kind).map(([kind, count]) => ({
            label: `.${kind}`,
            value: `${count} file`,
          }))}
          emptyText="Chưa có file nào upload qua workflow này."
        />
        <KvCard
          title="Liên kết với workflow khác"
          icon={Network}
          rows={[
            { label: 'Trigger sang (outgoing)', value: `${stats.cross_links.outgoing}` },
            { label: 'Được trigger (incoming)', value: `${stats.cross_links.incoming}` },
          ]}
        />
      </div>

      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
        <h3 className="font-serif text-base text-[var(--text-primary)] mb-3">
          KPI gần nhất (theo phòng ban)
        </h3>
        {stats.recent_kpis.length === 0 ? (
          <p className="text-xs italic text-[var(--text-secondary)]">
            Chưa có lần compute KPI cho phòng ban này. Chạy <code className="text-[10px] font-mono bg-[var(--bg-app)] px-1 rounded">reasoning/kpi_engine/</code> rồi
            reload trang.
          </p>
        ) : (
          <div className="space-y-1.5">
            {stats.recent_kpis.slice(0, 10).map((k, i) => (
              <div key={i} className="flex items-center justify-between gap-2 px-2 py-1.5 rounded hover:bg-[var(--bg-app)]/50">
                <span className="text-sm font-medium text-[var(--text-primary)]">{k.kpi_code}</span>
                <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                  <span className="font-mono">{k.raw_value !== null ? k.raw_value.toFixed(2) : 'N/A'}</span>
                  {k.classification && (
                    <span className={cn(
                      'px-1.5 py-0.5 rounded text-[10px]',
                      k.classification === 'good'     && 'bg-emerald-50 text-emerald-700',
                      k.classification === 'warning'  && 'bg-amber-50 text-amber-700',
                      k.classification === 'critical' && 'bg-rose-50 text-rose-700',
                    )}>
                      {k.classification}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <AdvisorCard workflowId={workflowId} />
    </div>
  );
}

// ─── ADR-0040 — Qwen Workflow Advisor card ──────────────────────────────
const ADVISOR_SEV = {
  high:   { label: 'Nghiêm trọng', cls: 'bg-rose-50 text-rose-700 border-rose-200' },
  medium: { label: 'Cần lưu ý',    cls: 'bg-amber-50 text-amber-700 border-amber-200' },
  low:    { label: 'Nhẹ',          cls: 'bg-slate-50 text-slate-600 border-slate-200' },
} as const;

interface AdvisorFinding {
  category: string; severity: 'high' | 'medium' | 'low';
  step_id: string | null; title: string; detail: string;
  suggestion: string; confidence: number;
}
interface AdvisorReview {
  status: 'done' | 'never_run';
  review_id?: string;
  run_mode?: string; model?: string; overall_health?: number | null;
  findings?: AdvisorFinding[]; narrative?: string | null; created_at?: string;
}

function AdvisorCard({ workflowId }: { workflowId: string }) {
  const [review, setReview]   = React.useState<AdvisorReview | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [running, setRunning] = React.useState(false);
  const [err, setErr]         = React.useState<string | null>(null);

  const fetchLatest = React.useCallback(async () => {
    try {
      const r = await api<AdvisorReview>(`/api/v1/workflows/${workflowId}/advisor`);
      setReview(r);
      return r;
    } catch (e: any) {
      setErr(e?.detail?.message || e?.title || e?.message || 'Lỗi tải đánh giá');
      return null;
    } finally {
      setLoading(false);
    }
  }, [workflowId]);

  React.useEffect(() => { fetchLatest(); }, [fetchLatest]);

  async function runAdvisor() {
    setRunning(true);
    setErr(null);
    const prevId = review?.review_id;
    try {
      await api(`/api/v1/workflows/${workflowId}/advisor/run`, { method: 'POST' });
      // advisor runs in a BackgroundTask — poll for the new review row (~30s)
      for (let i = 0; i < 15; i++) {
        await new Promise((res) => setTimeout(res, 2000));
        const r = await fetchLatest();
        if (r?.status === 'done' && r.review_id !== prevId) break;
      }
    } catch (e: any) {
      setErr(e?.detail?.message || e?.title || e?.message || 'Không chạy được đánh giá');
    } finally {
      setRunning(false);
    }
  }

  const health = review?.overall_health;
  const healthPct = (health !== null && health !== undefined) ? Math.round(health * 100) : null;
  const healthTone = healthPct === null ? 'text-[var(--text-secondary)]'
    : healthPct >= 80 ? 'text-emerald-700'
    : healthPct >= 50 ? 'text-amber-700' : 'text-rose-700';
  const findings = review?.findings ?? [];

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
      <div className="flex items-center justify-between mb-1">
        <h3 className="font-serif text-base text-[var(--text-primary)]">
          Đánh giá workflow (Qwen)
        </h3>
        <Button variant="secondary" onClick={runAdvisor} disabled={running}>
          {running
            ? <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />Đang phân tích…</>
            : <><Tag className="w-3.5 h-3.5 mr-1.5" />Đánh giá</>}
        </Button>
      </div>
      <p className="text-[11px] text-[var(--text-secondary)] mb-3">
        Gợi ý của AI (có độ tin cậy) — phát hiện bước thiếu hành động, nhánh sai, cổng
        duyệt rỗng, tài liệu thiếu… Không phải phán quyết tuyệt đối.
      </p>

      {loading && <p className="text-xs text-[var(--text-secondary)]"><Loader2 className="w-3 h-3 mr-1 inline animate-spin" />Đang tải…</p>}
      {err && <ErrorBanner problem={{ title: err }} />}

      {!loading && review?.status === 'never_run' && (
        <p className="text-xs italic text-[var(--text-secondary)]">
          Chưa phân tích. Bấm <strong>Đánh giá</strong> để Kaori kiểm tra workflow.
        </p>
      )}

      {!loading && review?.status === 'done' && (
        <div className="space-y-3">
          <div className="flex items-baseline gap-3">
            <span className={cn('text-3xl font-semibold', healthTone)}>{healthPct}%</span>
            <span className="text-xs text-[var(--text-secondary)]">
              sức khoẻ quy trình · {findings.length} phát hiện ·
              {review.run_mode === 'runtime' ? ' có dữ liệu chạy' : ' phân tích cấu trúc'}
              {review.model && review.model !== 'rules-only' ? ' · Qwen' : ''}
            </span>
          </div>

          {review.narrative && (
            <p className="text-sm text-[var(--text-primary)] bg-[var(--bg-app)]/50 rounded-md-custom p-3 border border-[var(--border-color)]">
              {review.narrative}
            </p>
          )}

          {findings.length === 0 ? (
            <p className="text-xs text-emerald-700 inline-flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" />Không phát hiện vấn đề nào.
            </p>
          ) : (
            <div className="space-y-2">
              {findings.map((f, i) => {
                const meta = ADVISOR_SEV[f.severity] ?? ADVISOR_SEV.low;
                return (
                  <div key={i} className={cn('rounded-md-custom border p-3', meta.cls)}>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-white/60">{meta.label}</span>
                      <span className="text-sm font-medium">{f.title}</span>
                    </div>
                    <p className="text-xs opacity-90">{f.detail}</p>
                    <p className="text-xs mt-1 opacity-90"><strong>Gợi ý:</strong> {f.suggestion}</p>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StatBox({
  label, value, icon: Icon, tone,
}: { label: string; value: number; icon: any; tone: string }) {
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-4 shadow-soft-sm">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] uppercase tracking-wider font-medium text-[var(--text-secondary)]">
          {label}
        </span>
        <Icon className={cn('w-4 h-4', tone)} />
      </div>
      <p className="font-serif text-2xl text-[var(--text-primary)]">{value}</p>
    </div>
  );
}

function KvCard({
  title, icon: Icon, rows, emptyText,
}: {
  title: string; icon: any;
  rows: Array<{ label: string; value: string }>;
  emptyText?: string;
}) {
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-4 shadow-soft-sm">
      <h4 className="text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)] mb-2">
        <Icon className="w-3.5 h-3.5 inline mr-1.5" /> {title}
      </h4>
      {rows.length === 0 ? (
        <p className="text-[11px] italic text-[var(--text-secondary)]">{emptyText || 'Chưa có dữ liệu.'}</p>
      ) : (
        <div className="space-y-1">
          {rows.map((r, i) => (
            <div key={i} className="flex items-center justify-between text-sm">
              <span className="text-[var(--text-secondary)]">{r.label}</span>
              <span className="font-medium text-[var(--text-primary)]">{r.value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
