'use client';

// Linear card-chain workflow builder (anh's "Linear Flow với Mũi Tên" spec,
// 2026-05-30). Default builder for SMEs: every step is a card, every step is
// joined by a labelled arrow (incl. if/else branches), config edited IN-PLACE.
// Reads the same workflow_nodes/edges and persists via the page's existing
// handlers — no new API. bpmn-js stays on the separate "BPMN" tab.
//
// Render is a SINGLE synchronous pass: flow() recurses INLINE (no deferred
// child component) so the visited-set is deterministic and branch columns
// always render.

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  KAORI_ACTIONS, KAORI_ACTION_BY_KEY, ACTION_GROUP_LABEL,
} from '@/lib/bpmn/bpmn-elements';
import { api } from '@/components/p2/foundation';
import { useT } from '@/lib/i18n/provider';

// A gate is "đã gán người duyệt" iff it binds a chain OR a non-empty role.
// In this builder the action is stored on node_type_catalog_key (the "Hành động
// Kaori" dropdown), so approval gates carry node_type_catalog_key === 'approval_gate'
// while node_type stays 'step'.
function approvalBound(cfg?: Record<string, any> | null): boolean {
  if (!cfg) return false;
  if (cfg.approval_chain_id) return true;
  const r = cfg.approver_role;
  return Array.isArray(r) ? r.some((x) => String(x).trim()) : !!String(r ?? '').trim();
}

interface Card {
  node_id: string;
  title: string;
  title_vi?: string | null;
  node_type: string;
  node_type_catalog_key?: string | null;
  category?: string;
  decision_config?: Record<string, any>;
  sequence_order?: number;
  lane_name?: string | null;
  // Mig 143 — hạn cuối của bước (lớp theo dõi, ISO date)
  deadline_date?: string | null;
}

// Hạn cuối: '2026-07-20' → 'dd/mm' + cờ quá hạn so với hôm nay (local).
function deadlineInfo(iso?: string | null): { label: string; overdue: boolean } | null {
  if (!iso) return null;
  const d = new Date(iso + 'T00:00:00');
  if (isNaN(d.getTime())) return null;
  const today = new Date(); today.setHours(0, 0, 0, 0);
  return {
    label: d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' }),
    overdue: d < today,
  };
}
interface Edge {
  edge_id: string;
  source_node_id: string;
  target_node_id: string;
  condition?: string | null;
  label?: string | null;
  port_type?: string;
}
type SetEdgeFn = (args: {
  sourceId: string; oldTarget?: string | null; newTarget: string | null;
  condition?: string | null; label?: string | null;
}) => void;

const ICON: Record<string, string> = {
  step: '📋', decision_if_else: '🔀', decision_switch: '🔀', approval_gate: '👆',
  notification: '📧', wait_event: '⏳', sla_timer: '⏰',
  parallel_split: '🔱', parallel_join: '⊕', subworkflow: '📦',
  loop_foreach: '🔁', loop_end: '🔚',
};
const TYPE_LABEL_KEY: Record<string, string> = {
  step: 'workflowLinearbuilderview.typeStep', decision_if_else: 'workflowLinearbuilderview.typeIfElse',
  decision_switch: 'workflowLinearbuilderview.typeSwitch', approval_gate: 'workflowLinearbuilderview.typeApproval',
  notification: 'workflowLinearbuilderview.typeNotification', wait_event: 'workflowLinearbuilderview.typeWaitEvent',
  sla_timer: 'workflowLinearbuilderview.typeSlaTimer',
  parallel_split: 'workflowLinearbuilderview.typeParallelSplit', parallel_join: 'workflowLinearbuilderview.typeParallelJoin',
  subworkflow: 'workflowLinearbuilderview.typeSubworkflow',
  loop_foreach: 'workflowLinearbuilderview.typeLoopForeach', loop_end: 'workflowLinearbuilderview.typeLoopEnd',
};
const DECISIONS = new Set(['decision_if_else', 'decision_switch', 'parallel_split']);
// Control actions (if/else, switch, split, join) ARE offered now — picking one
// promotes the card to a real decision node so the flow forks + the runner
// routes by branch. Map the executor key → structural node_type the fork
// renderer + runtime use. Keys not here stay a plain 'step' (e.g. approval_gate
// keeps node_type 'step' + catalog_key 'approval_gate').
const ACTION_OPTS = KAORI_ACTIONS.filter((a) => !a.trigger);
const CATALOG_TO_NODETYPE: Record<string, string> = {
  if_else: 'decision_if_else', switch: 'decision_switch',
  split: 'parallel_split', join: 'parallel_join',
  loop_foreach: 'loop_foreach', loop_end: 'loop_end',
};
const COMPARE_OPS: { op: string; vi: string }[] = [
  { op: '>=', vi: '≥ (lớn hơn hoặc bằng)' }, { op: '>', vi: '> (lớn hơn)' },
  { op: '<=', vi: '≤ (nhỏ hơn hoặc bằng)' }, { op: '<', vi: '< (nhỏ hơn)' },
  { op: '==', vi: '= (bằng)' }, { op: '!=', vi: '≠ (khác)' },
];
const ACTION_GROUPS = ACTION_OPTS.reduce<Record<string, typeof ACTION_OPTS>>((acc, a) => {
  (acc[a.group] = acc[a.group] || []).push(a); return acc;
}, {});

const isMain = (e: Edge) => (e.port_type ?? 'main') === 'main';
const arrowColor = (label?: string | null) => {
  const t = (label || '').toLowerCase();
  if (/khô|khong|\bno\b|else|từ chối|tu choi|reject|fail|0/.test(t)) return 'reject';
  if (/bổ sung|bo sung|ngoại lệ|ngoai le|chờ|cho|retry|lại|lai/.test(t)) return 'excep';
  return 'main';
};
const COLORS: Record<string, string> = { main: '#2f7dd1', excep: '#c8861a', reject: '#c0392b' };
const nodeDomId = (id: string) => 'wfnode-' + id;

// Tree-style fork connector (org-chart CSS): stem from the parent card down to a
// horizontal bus that spans the children's centres (auto-adapts to differing
// child widths), then a coloured vertical drop into each branch.
const CONNECTOR_CSS = `
.lbw-fork{display:flex;flex-direction:column;align-items:center}
.lbw-stem{width:2px;height:14px}
.lbw-children{display:flex;justify-content:center;align-items:flex-start}
.lbw-child{position:relative;display:flex;flex-direction:column;align-items:center;padding:0 14px}
.lbw-child::before{content:"";position:absolute;top:0;left:0;right:0;height:2px;background:#cbd5e1}
.lbw-child:first-child::before{left:50%}
.lbw-child:last-child::before{right:50%}
.lbw-child:only-child::before{display:none}
.lbw-drop{width:2px;height:16px}
`;

export default function LinearBuilderView({
  workflowId, cards, edges, onAddCard, onUpdate, onDelete, onSetEdge, deptName,
}: {
  workflowId?: string;
  cards: Card[];
  edges: Edge[];
  onAddCard: () => void;
  onUpdate: (id: string, patch: Record<string, any>) => void;
  onDelete: (id: string) => void;
  onSetEdge: SetEdgeFn;
  deptName?: string | null;
}) {
  const t = useT();
  const [openId, setOpenId] = useState<string | null>(null);
  const [zoom, setZoom] = useState(100);
  const [savedAt, setSavedAt] = useState(0);
  const [chains, setChains] = useState<any[]>([]);
  // #8 — canonical fields (the dictionary's own columns) feed a <datalist> so
  // condition/loop field inputs suggest real fields, while free-typing still
  // works (the actual record may carry fields outside the dictionary).
  const [fields, setFields] = useState<{ canonical: string; label: string; data_type?: string }[]>([]);
  // Dry-run: a sample record's path through the graph (visited nodes + taken
  // edges + a per-decision trace) so the user sees routing without a real record.
  const [dryOpen, setDryOpen] = useState(false);
  const [dryInput, setDryInput] = useState<Record<string, string>>({});
  const [dryResult, setDryResult] = useState<{ visited: Set<string>; taken: Set<string>; trace: any[] } | null>(null);
  const [dryBusy, setDryBusy] = useState(false);
  const flash = () => setSavedAt(Date.now());

  // Fields the workflow branches on — if_else conditions + switch inputs (scalar)
  // + loop list-refs (a LIST) — so the dry-run panel asks for exactly the inputs
  // that matter, and knows which ones need a list (→ "số phần tử").
  const dryFields = useMemo(() => {
    const m = new Map<string, boolean>();   // field name → isList
    const put = (name: string, isList: boolean) => {
      if (!name) return;
      m.set(name, (m.get(name) ?? false) || isList);
    };
    for (const c of cards) {
      const cfg = c.decision_config ?? {};
      const left = cfg.condition?.left;
      if (typeof left === 'string') put(left.replace(/^\$\.input\./, ''), false);
      if (typeof cfg.input === 'string') put(cfg.input.replace(/^\$\.input\./, ''), false);
      if (c.node_type === 'loop_foreach' && typeof cfg.items === 'string')
        put(cfg.items.replace(/^\$\.input\./, ''), true);
    }
    return [...m.entries()].map(([name, isList]) => ({ name, isList }));
  }, [cards]);

  async function runDry() {
    if (!workflowId) return;
    setDryBusy(true);
    try {
      const listFields = new Set(dryFields.filter((f) => f.isList).map((f) => f.name));
      const input: Record<string, any> = {};
      for (const [k, v] of Object.entries(dryInput)) {
        if (v === '') continue;
        if (listFields.has(k)) {
          // a list field → build N dummy items so the loop "lặp N lần".
          const n = Math.max(0, parseInt(v, 10) || 0);
          input[k] = Array.from({ length: n }, (_, i) => ({ i }));
        } else {
          const num = Number(v);
          input[k] = v.trim() !== '' && !isNaN(num) ? num : v;
        }
      }
      const r = await api<{ visited_node_ids: string[]; taken_edge_ids: string[]; trace: any[] }>(
        `/api/v1/workflows/${workflowId}/dry-run`, { method: 'POST', body: JSON.stringify({ input }) });
      setDryResult({ visited: new Set(r.visited_node_ids), taken: new Set(r.taken_edge_ids), trace: r.trace ?? [] });
    } catch { setDryResult(null); }
    finally { setDryBusy(false); }
  }

  // Approval chains for the tenant — feed the gate's chain-picker. Fetched once;
  // empty list (RLS / none) just falls back to the single-role selector.
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await api<{ chains: any[] }>('/api/v1/approval-chains');
        if (alive) setChains(r.chains ?? []);
      } catch { /* leave empty — role fallback still works */ }
    })();
    return () => { alive = false; };
  }, []);

  // #8 — canonical fields for the condition/loop field <datalist>.
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await api<{ fields: { canonical: string; label: string; data_type?: string }[] }>('/api/v1/schema/fields');
        if (alive) setFields(r.fields ?? []);
      } catch { /* no dictionary → free-typing still works */ }
    })();
    return () => { alive = false; };
  }, []);

  const upd = (id: string, patch: Record<string, any>) => { onUpdate(id, patch); flash(); };
  const setEdge: SetEdgeFn = (a) => { onSetEdge(a); flash(); };
  const toggleOpen = (id: string) => {
    const willOpen = openId !== id;
    setOpenId(willOpen ? id : null);
    if (willOpen && typeof document !== 'undefined')
      setTimeout(() => document.getElementById(nodeDomId(id))
        ?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 60);
  };

  const byId = useMemo(() => new Map(cards.map((c) => [c.node_id, c])), [cards]);
  const mainOut = useMemo(() => {
    const m = new Map<string, Edge[]>();
    for (const e of edges) {
      if (!isMain(e)) continue;
      (m.get(e.source_node_id) ?? m.set(e.source_node_id, []).get(e.source_node_id)!).push(e);
    }
    return m;
  }, [edges]);
  const incoming = useMemo(
    () => new Set(edges.filter(isMain).map((e) => e.target_node_id)),
    [edges],
  );
  const roots = useMemo(() => {
    const r = cards.filter((c) => !incoming.has(c.node_id));
    const list = r.length ? r : cards.slice(0, 1);
    return [...list].sort((a, b) => (a.sequence_order ?? 0) - (b.sequence_order ?? 0));
  }, [cards, incoming]);

  // Sequential step numbers in the SAME DFS order the flow renders (top→down,
  // branch by branch) so the numbers read naturally on the diagram.
  const stepNo = useMemo(() => {
    const m = new Map<string, number>();
    const seen = new Set<string>();
    let n = 0;
    const walk = (id: string) => {
      if (seen.has(id) || !byId.has(id)) return;
      seen.add(id); m.set(id, ++n);
      for (const e of (mainOut.get(id) ?? [])) walk(e.target_node_id);
    };
    roots.forEach((r) => walk(r.node_id));
    cards.forEach((c) => { if (!m.has(c.node_id)) m.set(c.node_id, ++n); });
    return m;
  }, [mainOut, roots, cards, byId]);

  const status = (c: Card) => {
    const outs = mainOut.get(c.node_id) ?? [];
    if (c.node_type === 'decision_if_else' && outs.length < 2) return warn(t('workflowLinearbuilderview.statusNeedTwoBranches'));
    if (c.node_type === 'decision_switch' && outs.length < 2) return warn(t('workflowLinearbuilderview.statusNeedBranchDefault'));
    if (c.node_type === 'parallel_split' && outs.length < 2) return warn(t('workflowLinearbuilderview.statusNeedAtLeastTwoBranches'));
    if (!DECISIONS.has(c.node_type) && c.node_type !== 'parallel_join' && !c.node_type_catalog_key)
      return warn(t('workflowLinearbuilderview.statusNoAction'));
    if (c.node_type_catalog_key === 'approval_gate' && !approvalBound(c.decision_config))
      return warn(t('workflowLinearbuilderview.statusNoApprover'));
    if (c.node_type === 'loop_foreach' && !c.decision_config?.items)
      return warn(t('workflowLinearbuilderview.statusNoLoopList'));
    return { kind: 'ok', text: t('workflowLinearbuilderview.statusReady') };
  };
  function warn(msg: string) { return { kind: 'warn', text: '⚠ ' + msg }; }

  // ── single-pass synchronous recursive render ──
  function renderFlow() {
    const rendered = new Set<string>();

    function flow(id: string, color: string, key: string): React.ReactNode {
      // The INCOMING connector to this node is drawn by the caller (straight
      // arrow or fork drop). flow() only draws the card + its OUTGOING links.
      const c = byId.get(id);
      if (!c) return null;
      if (rendered.has(id)) {
        return (
          <div key={key} className="text-[11px] text-[var(--text-secondary)] rounded-full border border-dashed border-[var(--border-color)] px-3 py-1 bg-white">
            {t('workflowLinearbuilderview.mergedInto', { title: c.title_vi || c.title })}
          </div>
        );
      }
      rendered.add(id);
      const outs = mainOut.get(id) ?? [];

      let outgoing: React.ReactNode;
      if (outs.length === 0) {
        outgoing = (
          <>
            <Arrow color={color} />
            <Terminal kind={color === 'reject' ? 'reject' : 'end'} text={t('workflowLinearbuilderview.terminalEnd')} />
          </>
        );
      } else if (outs.length === 1) {
        outgoing = (
          <>
            <Arrow color={color} onAdd={onAddCard} />
            {flow(outs[0].target_node_id, color, key + '>' + outs[0].edge_id)}
          </>
        );
      } else {
        // FORK — a real tree connector: stem → horizontal bus → per-branch
        // coloured drop + label + arrow into each child card.
        outgoing = (
          <div className="lbw-fork">
            <div className="lbw-stem" style={{ background: COLORS[color] }} />
            <div className="lbw-children">
              {outs.map((e) => {
                const bc = arrowColor(e.label || e.condition);
                const col = COLORS[bc];
                return (
                  <div key={e.edge_id} className="lbw-child">
                    <div className="lbw-drop" style={{ background: col, ['--bc' as any]: col }} />
                    <span className="text-[11px] font-semibold px-2.5 py-0.5 rounded-full border my-1"
                      style={{ color: col, borderColor: col + '55', background: col + '12' }}>
                      {bc === 'reject' ? '❌' : bc === 'excep' ? '⚠' : '✅'} {e.label || e.condition || t('workflowLinearbuilderview.branchFallback')}
                    </span>
                    <Arrow color={bc} />
                    {flow(e.target_node_id, bc, key + '|' + e.edge_id)}
                  </div>
                );
              })}
            </div>
          </div>
        );
      }

      return (
        <div key={key} className="flex flex-col items-center">
          {renderCard(c)}
          {outgoing}
        </div>
      );
    }

    // Leading arrow connects ▶ BẮT ĐẦU → first card of each root chain.
    return roots.map((r, i) => (
      <div key={'r' + i} className="flex flex-col items-center">
        <Arrow color="main" />
        {flow(r.node_id, 'main', 'root' + i)}
      </div>
    ));
  }

  function renderCard(c: Card) {
    const st = status(c);
    const open = openId === c.node_id;
    const isDecision = DECISIONS.has(c.node_type);
    const actionVi = c.node_type_catalog_key
      ? (KAORI_ACTION_BY_KEY[c.node_type_catalog_key]?.vi ?? c.node_type_catalog_key) : null;
    const outs = mainOut.get(c.node_id) ?? [];
    // Dry-run highlight: visited = on the sample record's path; others dim.
    const onPath = dryResult ? dryResult.visited.has(c.node_id) : null;
    return (
      <div id={nodeDomId(c.node_id)}
        className={'w-[300px] bg-white border rounded-xl shadow-sm overflow-hidden transition scroll-mt-24 '
          + (onPath === true ? 'ring-2 ring-emerald-500 border-emerald-400 '
             : onPath === false ? 'opacity-40 border-[var(--border-color)] '
             : open ? 'border-[var(--primary-gold)] ring-1 ring-[var(--primary-gold)]/30 '
                  : 'border-[var(--border-color)] hover:border-[var(--primary-gold)] ')}>
        {/* header — the click target to expand */}
        <button type="button" onClick={() => toggleOpen(c.node_id)}
          className="w-full flex items-center gap-2 px-3 pt-2.5 pb-2 text-left hover:bg-black/[0.025] transition">
          <span className="w-5 h-5 rounded-full bg-[var(--primary-gold)] text-white text-[11px] font-bold grid place-items-center shrink-0">
            {stepNo.get(c.node_id) ?? '•'}
          </span>
          <span className="w-7 h-7 rounded-lg grid place-items-center text-base bg-[var(--bg-app)] shrink-0">
            {ICON[c.node_type] ?? '📋'}
          </span>
          <span className="flex-1 font-bold text-[13.5px] leading-tight">{c.title_vi || c.title}</span>
          <span className="text-[var(--text-secondary)] text-xs shrink-0">{open ? '▾' : '▸'}</span>
        </button>
        <div className="px-3 pb-1.5 text-[11.5px] text-[var(--text-secondary)] leading-relaxed">
          {t('workflowLinearbuilderview.typePrefix')} <b className="text-[var(--text-primary)]">{TYPE_LABEL_KEY[c.node_type] ? t(TYPE_LABEL_KEY[c.node_type]) : c.node_type}</b>
          {deptName ? <> {t('workflowLinearbuilderview.deptPrefix')} <b className="text-[var(--text-primary)]">{deptName}</b></> : null}
          <br />
          {!isDecision && (
            <>{t('workflowLinearbuilderview.actionLabelPrefix')} {actionVi
              ? <><b className="text-[var(--text-primary)]">{actionVi}</b>{' '}
                  <span className="text-[9px] font-bold px-1 py-px rounded bg-violet-100 text-violet-700 border border-violet-200 align-middle"
                    title={t('workflowLinearbuilderview.aiChipTitle')}>AI</span></>
              : <b className="text-amber-700">{t('workflowLinearbuilderview.actionUnassigned')}</b>}</>
          )}
          {(() => {
            const dl = deadlineInfo(c.deadline_date);
            return dl ? (
              <span className={'ml-1.5 text-[10px] font-semibold px-1.5 py-px rounded-full border align-middle '
                + (dl.overdue ? 'bg-rose-50 text-rose-700 border-rose-200' : 'bg-sky-50 text-sky-700 border-sky-200')}
                title={dl.overdue ? t('workflowLinearbuilderview.deadlineOverdueTitle') : t('workflowLinearbuilderview.deadlineDueTitle')}>
                ⏰ {dl.overdue ? t('workflowLinearbuilderview.deadlineOverdue', { date: dl.label }) : t('workflowLinearbuilderview.deadlineDue', { date: dl.label })}
              </span>
            ) : null;
          })()}
        </div>
        <div className="flex items-center justify-between px-3 py-1.5 border-t border-[#f1eee7] bg-[#fcfbf8]">
          <span className={'text-[11px] font-semibold px-2 py-0.5 rounded-full '
            + (st.kind === 'ok' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700')}>
            {st.text}
          </span>
          <div className="flex items-center gap-2">
            <button onClick={() => toggleOpen(c.node_id)}
              className="text-[11px] text-[var(--primary-gold-dark)] hover:underline">
              {open ? t('workflowLinearbuilderview.collapseLabel') : t('workflowLinearbuilderview.editLabel')}
            </button>
            <button onClick={() => onDelete(c.node_id)}
              className="text-[11px] text-rose-500/80 hover:text-rose-600">{t('workflowLinearbuilderview.deleteLabel')}</button>
          </div>
        </div>

        {open && (
          <div className="border-t border-dashed border-[var(--border-color)] bg-[#fbfaf6] p-3 space-y-2">
            <Field label={t('workflowLinearbuilderview.fieldTitleLabel')}>
              <input defaultValue={c.title_vi || c.title}
                onBlur={(e) => { const v = e.target.value.trim(); if (v && v !== (c.title_vi || c.title)) upd(c.node_id, { title: v, title_vi: v }); }}
                className="w-full rounded border border-[var(--border-color)] px-2 py-1 text-sm" />
            </Field>

            <Field label={t('workflowLinearbuilderview.fieldActionLabel')}>
              <select value={c.node_type_catalog_key ?? ''}
                onChange={(e) => {
                  const key = e.target.value;
                  // Control actions promote the card to a decision node so the
                  // flow forks + the runner routes; others map to a plain step.
                  upd(c.node_id, { node_type_catalog_key: key, node_type: CATALOG_TO_NODETYPE[key] ?? 'step' });
                }}
                className="w-full rounded border border-[var(--border-color)] px-2 py-1 text-sm bg-white">
                <option value="">{t('workflowLinearbuilderview.optionUnassignedDesignOnly')}</option>
                {Object.entries(ACTION_GROUPS).map(([g, items]) => (
                  <optgroup key={g} label={ACTION_GROUP_LABEL[g as keyof typeof ACTION_GROUP_LABEL] ?? g}>
                    {items.map((a) => <option key={a.key} value={a.key}>{a.vi}</option>)}
                  </optgroup>
                ))}
              </select>
            </Field>

            {/* #9 — role/lane responsible for this step → BPMN swimlane. */}
            <Field label={t('workflowLinearbuilderview.fieldLaneLabel')}>
              <input defaultValue={c.lane_name ?? ''} placeholder={t('workflowLinearbuilderview.placeholderLaneExample')}
                list="kaori-lanes"
                onBlur={(e) => { const v = e.target.value.trim(); if (v !== (c.lane_name ?? '')) upd(c.node_id, { lane_name: v }); }}
                className="w-full rounded border border-[var(--border-color)] px-2 py-1 text-sm" />
            </Field>

            {/* Mig 143 — hạn cuối của bước (deadline, lớp theo dõi) */}
            <Field label={t('workflowLinearbuilderview.deadlineFieldLabel')}>
              <div className="flex items-center gap-2">
                <input type="date" defaultValue={c.deadline_date ?? ''}
                  onBlur={(e) => {
                    const v = e.target.value;
                    if (v !== (c.deadline_date ?? '')) {
                      upd(c.node_id, v ? { deadline_date: v } : { clear_deadline: true });
                    }
                  }}
                  className="flex-1 rounded border border-[var(--border-color)] px-2 py-1 text-sm bg-white" />
                {c.deadline_date && (
                  <button type="button" onClick={() => upd(c.node_id, { clear_deadline: true })}
                    className="text-[11px] text-[var(--text-secondary)] hover:text-rose-600 underline shrink-0">
                    {t('workflowLinearbuilderview.deadlineClear')}
                  </button>
                )}
              </div>
            </Field>

            {/* Flow control for a NON-branching step: pick the next step (or end).
                Lets the user reroute any step — e.g. send a rejected request
                straight to "Gửi thông báo", skipping "Ghi sổ". Decisions route via
                their own branch editors instead. */}
            {!DECISIONS.has(c.node_type) && (
              <Field label={t('workflowLinearbuilderview.fieldNextStepLabel')}>
                <select value={outs[0]?.target_node_id ?? ''}
                  onChange={(ev) => setEdge({
                    sourceId: c.node_id,
                    oldTarget: outs[0]?.target_node_id ?? null,
                    newTarget: ev.target.value || null,
                    label: outs[0]?.label ?? 'next',
                  })}
                  className="w-full rounded border border-[var(--border-color)] px-2 py-1 text-sm bg-white">
                  <option value="">{t('workflowLinearbuilderview.optionEndNoNext')}</option>
                  {cards.filter((x) => x.node_id !== c.node_id).map((x) =>
                    <option key={x.node_id} value={x.node_id}>{x.title_vi || x.title}</option>)}
                </select>
                {outs.length > 1 && (
                  <p className="text-[10px] text-amber-700/80 mt-0.5">{t('workflowLinearbuilderview.branchCountHint', { n: outs.length })}</p>
                )}
              </Field>
            )}

            {/* If/else decision → condition editor (writes config.condition) +
                explicit Đúng/Sai branch routing the runner understands. */}
            {c.node_type === 'decision_if_else' && (
              <IfElseEditor card={c} cards={cards} edges={edges}
                onChange={(cfg) => upd(c.node_id, { decision_config: cfg })} onSetEdge={setEdge} />
            )}

            {/* Approval gate → bind a chain (preferred) or a single role */}
            {c.node_type_catalog_key === 'approval_gate' && (
              <ApprovalBind card={c} chains={chains} onChange={(cfg) => upd(c.node_id, { decision_config: cfg })} />
            )}

            {c.node_type === 'decision_switch' && (
              <SwitchEditor card={c} cards={cards} edges={edges}
                onChange={(cfg) => upd(c.node_id, { decision_config: cfg })} onSetEdge={setEdge} />
            )}

            {c.node_type === 'loop_foreach' && (
              <LoopEditor card={c} onChange={(patch) => upd(c.node_id, { decision_config: patch })} />
            )}

            {isDecision && c.node_type !== 'decision_if_else' && c.node_type !== 'decision_switch' && (
              <Field label={t('workflowLinearbuilderview.fieldBranchesLabel')}>
                <div className="space-y-1.5">
                  {outs.map((e) => (
                    <div key={e.edge_id} className="flex items-center gap-1.5">
                      <input defaultValue={e.label ?? ''} placeholder={t('workflowLinearbuilderview.placeholderLabelCondition')}
                        onBlur={(ev) => setEdge({ sourceId: c.node_id, oldTarget: e.target_node_id, newTarget: e.target_node_id, label: ev.target.value, condition: e.condition })}
                        className="w-24 rounded border border-[var(--border-color)] px-1.5 py-1 text-xs" />
                      <span className="text-xs">→</span>
                      <select value={e.target_node_id}
                        onChange={(ev) => setEdge({ sourceId: c.node_id, oldTarget: e.target_node_id, newTarget: ev.target.value, label: e.label, condition: e.condition })}
                        className="flex-1 rounded border border-[var(--border-color)] px-1.5 py-1 text-xs bg-white">
                        {cards.filter((x) => x.node_id !== c.node_id).map((x) =>
                          <option key={x.node_id} value={x.node_id}>{x.title_vi || x.title}</option>)}
                      </select>
                      <button className="text-rose-500 text-xs px-1"
                        onClick={() => setEdge({ sourceId: c.node_id, oldTarget: e.target_node_id, newTarget: null })}>✕</button>
                    </div>
                  ))}
                  <AddBranch sourceId={c.node_id} cards={cards} onSetEdge={setEdge} />
                </div>
              </Field>
            )}
          </div>
        )}
      </div>
    );
  }

  const jump = (id: string) => {
    const el = typeof document !== 'undefined' ? document.getElementById(nodeDomId(id)) : null;
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden relative">
      <style>{CONNECTOR_CSS}</style>
      {/* #8 — shared suggestions for every field input (if/else, switch, loop).
          Editors reference it via list="kaori-fields"; free-typing still works. */}
      <datalist id="kaori-fields">
        {fields.map((f) => <option key={f.canonical} value={f.canonical}>{f.label}</option>)}
      </datalist>
      {/* #9 — suggest lanes already used in this workflow + common roles. */}
      <datalist id="kaori-lanes">
        {[...new Set([
          ...cards.map((c) => (c.lane_name ?? '').trim()).filter(Boolean),
          t('workflowLinearbuilderview.laneAccounting'), t('workflowLinearbuilderview.laneDeptHead'),
          t('workflowLinearbuilderview.laneDirector'), t('workflowLinearbuilderview.laneSales'),
          t('workflowLinearbuilderview.laneCustomerCare'),
        ])].map((l) => <option key={l} value={l} />)}
      </datalist>
      {/* top status bar */}
      <div className="flex items-center gap-2 flex-wrap border-b border-[var(--border-color)] px-4 py-2 bg-[#fffdf7] text-xs">
        <span className="font-medium uppercase tracking-wider text-[var(--text-secondary)] mr-1">{t('workflowLinearbuilderview.labelFlow')}</span>
        <Chip onClick={() => jump(roots[0]?.node_id ?? '')}>{t('workflowLinearbuilderview.chipStart')}</Chip>
        <Sep />
        <Chip>{t('workflowLinearbuilderview.chipStepsCount', { n: cards.filter((c) => !DECISIONS.has(c.node_type)).length })}</Chip>
        {cards.filter((c) => DECISIONS.has(c.node_type)).map((d) => (
          <span key={d.node_id} className="contents">
            <Sep /><Chip branch onClick={() => jump(d.node_id)}>🔀 #{stepNo.get(d.node_id)} {d.title_vi || d.title}</Chip>
          </span>
        ))}
        <span className="flex-1" />
        {workflowId && (
          <button onClick={() => setDryOpen((v) => !v)}
            className={'rounded-md-custom border px-3 py-1.5 font-medium transition '
              + (dryOpen ? 'border-emerald-500 bg-emerald-50 text-emerald-700'
                         : 'border-[var(--border-color)] hover:bg-black/5')}>
            {t('workflowLinearbuilderview.btnDryRun')}
          </button>
        )}
        <button onClick={onAddCard}
          className="rounded-md-custom bg-[var(--primary-gold)] text-white px-3 py-1.5 font-medium hover:opacity-90">
          {t('workflowLinearbuilderview.btnAddStep')}
        </button>
      </div>

      {/* dry-run panel — sample record → highlighted path */}
      {dryOpen && (
        <div className="border-b border-emerald-200 bg-emerald-50/60 px-4 py-3 text-xs space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-emerald-800">{t('workflowLinearbuilderview.labelDryRunSample')}</span>
            {dryFields.length === 0 && <span className="text-emerald-700/80">{t('workflowLinearbuilderview.msgNoBranchToTest')}</span>}
            {dryFields.map((f) => (
              <label key={f.name} className="inline-flex items-center gap-1">
                <span className="text-emerald-800">{f.name}{f.isList ? t('workflowLinearbuilderview.suffixElementCount') : ''}</span>
                <input type={f.isList ? 'number' : 'text'} value={dryInput[f.name] ?? ''}
                  onChange={(e) => setDryInput((p) => ({ ...p, [f.name]: e.target.value }))}
                  placeholder={f.isList ? t('workflowLinearbuilderview.placeholderExample3') : t('workflowLinearbuilderview.placeholderValue')}
                  className="w-28 rounded border border-emerald-300 px-2 py-1" />
              </label>
            ))}
            <button onClick={() => void runDry()} disabled={dryBusy}
              className="rounded-md-custom bg-emerald-600 text-white px-3 py-1.5 font-medium hover:opacity-90 disabled:opacity-50">
              {dryBusy ? t('workflowLinearbuilderview.btnRunning') : t('workflowLinearbuilderview.btnRun')}
            </button>
            {dryResult && <button onClick={() => setDryResult(null)} className="text-emerald-700 hover:underline">{t('workflowLinearbuilderview.btnClearHighlight')}</button>}
          </div>
          {dryResult && (
            <div className="rounded bg-white border border-emerald-200 p-2 space-y-0.5">
              <div className="font-medium text-emerald-800">{t('workflowLinearbuilderview.labelRecordPath')}</div>
              {dryResult.trace.length === 0
                ? <div className="text-[var(--text-secondary)]">{t('workflowLinearbuilderview.msgNoBranchPoints')}</div>
                : dryResult.trace.map((tr, i) => (
                  <div key={i} className="text-[var(--text-primary)]">🔀 <b>{tr.title}</b> → {tr.detail}</div>
                ))}
              <div className="text-[10px] text-[var(--text-secondary)] pt-1">{t('workflowLinearbuilderview.msgLegendPath')}</div>
            </div>
          )}
        </div>
      )}

      {/* canvas (vertical grow → internal scroll; zoom) */}
      <div className="overflow-auto" style={{ maxHeight: 'calc(100vh - 250px)', minHeight: 460 }}>
        <div className="p-6 flex flex-col items-center origin-top"
             style={{ transform: `scale(${zoom / 100})`, transformOrigin: 'top center', minWidth: 'max-content' }}>
          <Terminal kind="start" text={t('workflowLinearbuilderview.terminalStart')} />
          {cards.length === 0 ? (
            <div className="text-sm text-[var(--text-secondary)] my-12 text-center">
              <p className="mb-3">{t('workflowLinearbuilderview.msgEmptyWorkflow')}</p>
            </div>
          ) : renderFlow()}
        </div>
      </div>

      {/* zoom controls */}
      <div className="absolute bottom-3 right-3 flex items-center gap-1 bg-white/95 border border-[var(--border-color)] rounded-lg px-1 py-0.5 shadow">
        <button onClick={() => setZoom((z) => Math.max(60, z - 10))} className="w-7 h-6 text-sm">−</button>
        <span className="text-[11px] w-9 text-center text-[var(--text-secondary)]">{zoom}%</span>
        <button onClick={() => setZoom((z) => Math.min(140, z + 10))} className="w-7 h-6 text-sm">+</button>
      </div>

      {/* saved micro-toast */}
      <SavedToast at={savedAt} />
    </div>
  );
}

// ── small pieces ──
function Arrow({ color = 'main', onAdd }: { color?: string; onAdd?: () => void }) {
  const t = useT();
  const c = COLORS[color] ?? COLORS.main;
  return (
    <div className="relative w-px my-0.5 group" style={{ height: 32, background: c }}>
      <div className="absolute left-1/2 -translate-x-1/2"
        style={{ bottom: -1, width: 0, height: 0, borderLeft: '5px solid transparent', borderRight: '5px solid transparent', borderTop: `7px solid ${c}` }} />
      {onAdd && (
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition">
          <button onClick={onAdd}
            className="whitespace-nowrap text-[11px] border border-[var(--primary-gold)] text-[var(--primary-gold-dark)] bg-white rounded-full px-2.5 py-0.5 shadow-sm">
            {t('workflowLinearbuilderview.btnAddStep')}
          </button>
        </div>
      )}
    </div>
  );
}
function Terminal({ kind, text }: { kind: string; text: string }) {
  const cls = kind === 'start' ? 'bg-blue-50 text-blue-700 border-blue-200'
    : kind === 'reject' ? 'bg-rose-50 text-rose-700 border-rose-200'
    : 'bg-emerald-50 text-emerald-700 border-emerald-200';
  return <div className={'inline-flex items-center gap-2 font-bold text-[13px] px-4 py-2 rounded-full border ' + cls}>{text}</div>;
}
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-[11px] uppercase tracking-wide text-[var(--text-secondary)] mb-1">{label}</label>
      {children}
    </div>
  );
}
function Chip({ children, branch, onClick }: { children: React.ReactNode; branch?: boolean; onClick?: () => void }) {
  return <button onClick={onClick}
    className={'inline-flex items-center gap-1 px-2.5 py-1 rounded-full border bg-white transition '
      + (branch ? 'border-[#f0d8a0] bg-[#fff7e6]' : 'border-[var(--border-color)]')
      + (onClick ? ' hover:shadow cursor-pointer' : '')}>{children}</button>;
}
function Sep() { return <span className="text-gray-300 mx-0.5">→</span>; }

function AddBranch({ sourceId, cards, onSetEdge }:
  { sourceId: string; cards: Card[]; onSetEdge: SetEdgeFn }) {
  const t = useT();
  const [target, setTarget] = useState('');
  const opts = cards.filter((x) => x.node_id !== sourceId);
  return (
    <div className="flex items-center gap-1.5 pt-1">
      <select value={target} onChange={(e) => setTarget(e.target.value)}
        className="flex-1 rounded border border-dashed border-[var(--primary-gold)] px-1.5 py-1 text-xs bg-white">
        <option value="">{t('workflowLinearbuilderview.optionAddBranchGoto')}</option>
        {opts.map((x) => <option key={x.node_id} value={x.node_id}>{x.title_vi || x.title}</option>)}
      </select>
      <button disabled={!target}
        onClick={() => { if (target) { onSetEdge({ sourceId, newTarget: target, label: t('workflowLinearbuilderview.branchFallback') }); setTarget(''); } }}
        className="text-xs text-[var(--primary-gold-dark)] disabled:opacity-40 px-1">{t('workflowLinearbuilderview.btnAdd')}</button>
    </div>
  );
}

// Bind approvers for an approval_gate card: a multi-level chain (preferred) OR a
// single fallback role. Writes decision_config.{approval_chain_id, approver_role,
// timeout_action}. Mirrors what the runtime executor (approval.py) consumes; an
// unbound gate is blocked on Chạy thử/Kích hoạt by _check_approval_gates.
function ApprovalBind({ card, chains, onChange }:
  { card: Card; chains: any[]; onChange: (cfg: Record<string, any>) => void }) {
  const t = useT();
  const cfg = card.decision_config ?? {};
  const chainId = cfg.approval_chain_id ?? '';
  const role = Array.isArray(cfg.approver_role) ? cfg.approver_role[0] : cfg.approver_role;
  const selected = chains.find((c) => c.chain_id === chainId);
  const bound = approvalBound(cfg);
  return (
    <div className="space-y-2 border-l-4 border-amber-400 pl-3 bg-amber-50/50 py-2 rounded-r">
      <p className="text-[10px] text-amber-700/70">
        {t('workflowLinearbuilderview.msgApprovalNote')}
      </p>
      <Field label={t('workflowLinearbuilderview.fieldChainLabel')}>
        <select value={chainId}
          onChange={(e) => onChange({ ...cfg, approval_chain_id: e.target.value || undefined })}
          className="w-full rounded border border-amber-200 px-2 py-1 text-sm bg-white">
          <option value="">{t('workflowLinearbuilderview.optionNoChain')}</option>
          {chains.map((c) => <option key={c.chain_id} value={c.chain_id}>{c.name_vi || c.name}</option>)}
        </select>
      </Field>
      {chains.length === 0 && (
        <p className="text-[11px] text-amber-700/80">
          {t('workflowLinearbuilderview.msgNoChainsYet')}
        </p>
      )}
      {selected && (
        <p className="text-[11px] text-amber-700/80">{t('workflowLinearbuilderview.msgChainBoundPrefix')} <b>{selected.name_vi || selected.name}</b> {t('workflowLinearbuilderview.msgChainBoundSuffix')}</p>
      )}
      {!chainId && (
        <Field label={t('workflowLinearbuilderview.fieldRoleFallbackLabel')}>
          <select value={role ?? ''}
            onChange={(e) => onChange({ ...cfg, approver_role: e.target.value || undefined })}
            className="w-full rounded border border-amber-200 px-2 py-1 text-sm bg-white">
            <option value="">{t('workflowLinearbuilderview.optionChooseRole')}</option>
            <option value="MANAGER">{t('workflowLinearbuilderview.roleManager')}</option>
            <option value="ANALYST">{t('workflowLinearbuilderview.roleAnalyst')}</option>
            <option value="OPERATOR">{t('workflowLinearbuilderview.roleOperator')}</option>
            <option value="ADMIN">{t('workflowLinearbuilderview.roleAdmin')}</option>
          </select>
        </Field>
      )}
      <Field label={t('workflowLinearbuilderview.fieldTimeoutLabel')}>
        <select value={cfg.timeout_action ?? 'escalate'}
          onChange={(e) => onChange({ ...cfg, timeout_action: e.target.value })}
          className="w-full rounded border border-amber-200 px-2 py-1 text-sm bg-white">
          <option value="escalate">{t('workflowLinearbuilderview.optionEscalate')}</option>
          <option value="approve">{t('workflowLinearbuilderview.optionAutoApprove')}</option>
          <option value="reject">{t('workflowLinearbuilderview.optionAutoReject')}</option>
        </select>
      </Field>
      {!bound && (
        <p className="text-[11px] text-rose-600">{t('workflowLinearbuilderview.msgGateUnbound')}</p>
      )}
    </div>
  );
}

// if/else condition editor. Writes decision_config.condition = {left, op, right}
// (consumed by IfElseExecutor) and routes two explicit branches with tokens the
// runner recognises ('có' → true arm, 'không' → false arm). For else-if tiers,
// chain several if_else cards (Sai → bước kiểm tra tiếp theo).
function IfElseEditor({ card, cards, edges, onChange, onSetEdge }:
  { card: Card; cards: Card[]; edges: Edge[];
    onChange: (cfg: Record<string, any>) => void; onSetEdge: SetEdgeFn }) {
  const t = useT();
  const cfg = card.decision_config ?? {};
  const cond = cfg.condition ?? {};
  const setCond = (patch: Record<string, any>) => onChange({ ...cfg, condition: { ...cond, ...patch } });
  const fieldRaw = typeof cond.left === 'string' ? cond.left.replace(/^\$\.input\./, '') : '';
  const others = cards.filter((x) => x.node_id !== card.node_id);
  const outs = edges.filter((e) => e.source_node_id === card.node_id && (e.port_type ?? 'main') === 'main');
  const TRUE = new Set(['true', 'yes', 'có', 'co', 't', '1', 'pass', 'passed']);
  const trueEdge = outs.find((e) => TRUE.has(String(e.label ?? '').trim().toLowerCase()));
  const falseEdge = outs.find((e) => e !== trueEdge);
  const setBranch = (token: string, oldEdge: Edge | undefined, newTarget: string) =>
    onSetEdge({ sourceId: card.node_id, oldTarget: oldEdge?.target_node_id ?? null,
      newTarget: newTarget || null, label: token });
  return (
    <div className="space-y-2 border-l-4 border-sky-400 pl-3 bg-sky-50/50 py-2 rounded-r">
      <Field label={t('workflowLinearbuilderview.fieldConditionLabel')}>
        <div className="grid grid-cols-[1fr_72px_1fr] gap-1.5 items-center">
          <input key={card.node_id + '-f'} defaultValue={fieldRaw} placeholder={t('workflowLinearbuilderview.placeholderFieldExample')}
            list="kaori-fields"
            onBlur={(e) => { const v = e.target.value.trim(); setCond({ left: v ? `$.input.${v}` : undefined }); }}
            className="min-w-0 rounded border border-sky-200 px-2 py-1 text-sm" />
          <select value={cond.op ?? '>='} onChange={(e) => setCond({ op: e.target.value })}
            className="rounded border border-sky-200 px-1 py-1 text-sm bg-white">
            {COMPARE_OPS.map((o) => <option key={o.op} value={o.op}>{o.op}</option>)}
          </select>
          <input key={card.node_id + '-v'} defaultValue={cond.right ?? ''} placeholder={t('workflowLinearbuilderview.placeholderValueExample')}
            onBlur={(e) => { const v = e.target.value.trim(); const n = Number(v);
              setCond({ right: v === '' ? undefined : (v !== '' && !isNaN(n) ? n : v) }); }}
            className="min-w-0 rounded border border-sky-200 px-2 py-1 text-sm" />
        </div>
        <p className="text-[10px] text-sky-700/80 mt-1">
          {t('workflowLinearbuilderview.msgConditionHintPrefix')} <b>so_tien ≥ 10000000</b>{t('workflowLinearbuilderview.msgConditionHintSuffix')}
        </p>
      </Field>
      <Field label={t('workflowLinearbuilderview.fieldWhenTrueLabel')}>
        <select value={trueEdge?.target_node_id ?? ''} onChange={(e) => setBranch('có', trueEdge, e.target.value)}
          className="w-full rounded border border-sky-200 px-2 py-1 text-sm bg-white">
          <option value="">{t('workflowLinearbuilderview.optionChooseStep')}</option>
          {others.map((x) => <option key={x.node_id} value={x.node_id}>{x.title_vi || x.title}</option>)}
        </select>
      </Field>
      <Field label={t('workflowLinearbuilderview.fieldWhenFalseLabel')}>
        <select value={falseEdge?.target_node_id ?? ''} onChange={(e) => setBranch('không', falseEdge, e.target.value)}
          className="w-full rounded border border-sky-200 px-2 py-1 text-sm bg-white">
          <option value="">{t('workflowLinearbuilderview.optionChooseStep')}</option>
          {others.map((x) => <option key={x.node_id} value={x.node_id}>{x.title_vi || x.title}</option>)}
        </select>
      </Field>
    </div>
  );
}

// switch editor — N-way branch by numeric RANGE (vd duyệt chi theo mức tiền).
// Writes decision_config.{input, cases:[{label,min,max}]}; each case routes an
// edge labelled with its token, plus a "Mặc định" catch-all. Executor
// (SwitchExecutor) matches min ≤ value < max → emits matched_case=label; runner
// routes the edge whose label == matched_case.
function SwitchEditor({ card, cards, edges, onChange, onSetEdge }:
  { card: Card; cards: Card[]; edges: Edge[];
    onChange: (cfg: Record<string, any>) => void; onSetEdge: SetEdgeFn }) {
  const t = useT();
  const cfg = card.decision_config ?? {};
  const inputRaw = typeof cfg.input === 'string' ? cfg.input.replace(/^\$\.input\./, '') : '';
  const cases: any[] = Array.isArray(cfg.cases) ? cfg.cases : [];
  const others = cards.filter((x) => x.node_id !== card.node_id);
  const outs = edges.filter((e) => e.source_node_id === card.node_id && (e.port_type ?? 'main') === 'main');
  const edgeFor = (label: string) =>
    outs.find((e) => String(e.label ?? '').trim().toLowerCase() === String(label ?? '').trim().toLowerCase());
  const setCases = (next: any[]) => onChange({ ...cfg, cases: next });
  const updCase = (i: number, patch: Record<string, any>) =>
    setCases(cases.map((c, j) => (j === i ? { ...c, ...patch } : c)));
  const route = (label: string, target: string) => {
    const e = edgeFor(label);
    onSetEdge({ sourceId: card.node_id, oldTarget: e?.target_node_id ?? null, newTarget: target || null, label });
  };
  const renameLabel = (i: number, oldLabel: string, newLabel: string) => {
    const e = edgeFor(oldLabel);
    if (e && newLabel) onSetEdge({ sourceId: card.node_id, oldTarget: e.target_node_id, newTarget: e.target_node_id, label: newLabel });
    updCase(i, { label: newLabel });
  };
  const removeCase = (i: number) => {
    const e = edgeFor(cases[i]?.label);
    if (e) onSetEdge({ sourceId: card.node_id, oldTarget: e.target_node_id, newTarget: null });
    setCases(cases.filter((_, j) => j !== i));
  };
  const defEdge = edgeFor('default');
  return (
    <div className="space-y-2 border-l-4 border-violet-400 pl-3 bg-violet-50/50 py-2 rounded-r">
      <Field label={t('workflowLinearbuilderview.fieldClassifyByLabel')}>
        <input key={card.node_id + '-sw'} defaultValue={inputRaw} placeholder={t('workflowLinearbuilderview.placeholderFieldExample')}
          list="kaori-fields"
          onBlur={(e) => onChange({ ...cfg, input: e.target.value.trim() ? `$.input.${e.target.value.trim()}` : undefined })}
          className="w-full rounded border border-violet-200 px-2 py-1 text-sm" />
      </Field>
      <label className="block text-[11px] uppercase tracking-wide text-[var(--text-secondary)]">{t('workflowLinearbuilderview.labelLevelsRange')}</label>
      <div className="space-y-1.5">
        {cases.map((cs, i) => {
          const e = edgeFor(cs.label);
          return (
            <div key={i} className="rounded border border-violet-200 bg-white p-1.5 space-y-1">
              <div className="flex items-center gap-1">
                <input defaultValue={cs.label ?? ''} placeholder={t('workflowLinearbuilderview.placeholderLevelNameExample')}
                  onBlur={(ev) => renameLabel(i, cs.label, ev.target.value.trim())}
                  className="flex-1 min-w-0 rounded border border-violet-200 px-2 py-1 text-xs" />
                <button className="text-rose-500 text-xs px-1 shrink-0" onClick={() => removeCase(i)}>✕</button>
              </div>
              <div className="flex items-center gap-1">
                <span className="text-[10px] text-violet-700 shrink-0">{t('workflowLinearbuilderview.textFromGte')}</span>
                <input defaultValue={cs.min ?? ''} placeholder={t('workflowLinearbuilderview.placeholderEmptyMinusInfinity')} type="number" inputMode="numeric"
                  onBlur={(ev) => updCase(i, { min: ev.target.value === '' ? undefined : Number(ev.target.value) })}
                  className="flex-1 min-w-0 rounded border border-violet-200 px-2 py-1 text-xs" />
                <span className="text-[10px] text-violet-700 shrink-0">{t('workflowLinearbuilderview.textToLt')}</span>
                <input defaultValue={cs.max ?? ''} placeholder={t('workflowLinearbuilderview.placeholderEmptyPlusInfinity')} type="number" inputMode="numeric"
                  onBlur={(ev) => updCase(i, { max: ev.target.value === '' ? undefined : Number(ev.target.value) })}
                  className="flex-1 min-w-0 rounded border border-violet-200 px-2 py-1 text-xs" />
              </div>
              {(cs.min != null || cs.max != null) && (
                <div className="text-[10px] text-violet-600">
                  {cs.min != null ? Number(cs.min).toLocaleString('vi-VN') : '−∞'} – {cs.max != null ? Number(cs.max).toLocaleString('vi-VN') : '+∞'} ₫
                </div>
              )}
              <select value={e?.target_node_id ?? ''} onChange={(ev) => route(cs.label, ev.target.value)}
                className="w-full rounded border border-violet-200 px-2 py-1 text-xs bg-white">
                <option value="">{t('workflowLinearbuilderview.optionGotoStep')}</option>
                {others.map((x) => <option key={x.node_id} value={x.node_id}>{x.title_vi || x.title}</option>)}
              </select>
            </div>
          );
        })}
        <button onClick={() => setCases([...cases, { label: `muc${cases.length + 1}` }])}
          className="text-xs text-violet-700 hover:underline">{t('workflowLinearbuilderview.btnAddLevel')}</button>
      </div>
      <Field label={t('workflowLinearbuilderview.fieldDefaultLabel')}>
        <select value={defEdge?.target_node_id ?? ''} onChange={(e) => route('default', e.target.value)}
          className="w-full rounded border border-violet-200 px-2 py-1 text-sm bg-white">
          <option value="">{t('workflowLinearbuilderview.optionChooseStep')}</option>
          {others.map((x) => <option key={x.node_id} value={x.node_id}>{x.title_vi || x.title}</option>)}
        </select>
      </Field>
      <p className="text-[10px] text-violet-700/80">{t('workflowLinearbuilderview.msgLevelsHint')}</p>
    </div>
  );
}

// Loop editor — config.items (list ref) + item_var. The BODY is the chain of
// steps between this node and the matching loop_end; the runner (Phase B) runs
// it once per item. Sends PARTIAL patches — updateCard deep-merges decision_config.
function LoopEditor({ card, onChange }:
  { card: Card; onChange: (patch: Record<string, any>) => void }) {
  const t = useT();
  const cfg = card.decision_config ?? {};
  const itemsRaw = typeof cfg.items === 'string' ? cfg.items.replace(/^\$\.input\./, '') : '';
  const itemVar = cfg.item_var || 'item';
  return (
    <div className="space-y-2 border-l-4 border-teal-400 pl-3 bg-teal-50/50 py-2 rounded-r">
      <Field label={t('workflowLinearbuilderview.fieldLoopOverLabel')}>
        <input key={card.node_id + '-loop'} defaultValue={itemsRaw} placeholder={t('workflowLinearbuilderview.placeholderLoopFieldExample')}
          list="kaori-fields"
          onBlur={(e) => onChange({ items: e.target.value.trim() ? `$.input.${e.target.value.trim()}` : undefined })}
          className="w-full rounded border border-teal-200 px-2 py-1 text-sm" />
      </Field>
      <Field label={t('workflowLinearbuilderview.fieldItemVarLabel')}>
        <input key={card.node_id + '-iv'} defaultValue={cfg.item_var ?? 'item'} placeholder="item"
          onBlur={(e) => onChange({ item_var: e.target.value.trim() || undefined })}
          className="w-full rounded border border-teal-200 px-2 py-1 text-sm" />
      </Field>
      <p className="text-[10px] text-teal-700/80">
        {t('workflowLinearbuilderview.msgLoopBodyHintPrefix')} <code className="bg-white px-1 rounded">$.{itemVar}.&lt;trường&gt;</code>.
      </p>
    </div>
  );
}

function SavedToast({ at }: { at: number }) {
  const t = useT();
  const [show, setShow] = useState(false);
  useEffect(() => {
    if (!at) return;
    setShow(true);
    const timer = setTimeout(() => setShow(false), 1500);
    return () => clearTimeout(timer);
  }, [at]);
  if (!show) return null;
  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 bg-emerald-600 text-white text-xs px-3 py-1.5 rounded-full shadow-lg">
      {t('workflowLinearbuilderview.toastSaved')}
    </div>
  );
}
