// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 62. /p2/approvals — Approval Chains + Functional RBAC config (ADR-0037 Phase 2)
// ----------------------------------------------------------------------------
// Chains:  GET/POST /api/v1/approval-chains · GET /approval-chains/{id}
//          POST /approval-chains/{id}/levels
// Roles:   POST/GET/DELETE /api/v1/user-department-roles
//
// Admin configures the multi-level approval chains a workflow's approval_gate
// references, and grants per-department functional roles (executor/reviewer/
// approver/dept_manager/admin) that drive the RBAC matrix.
// ============================================================================

import React, { useState, useEffect } from 'react';
import {
  GitBranch, Plus, Trash2, Users, ChevronRight, Loader2, Shield, X,
  Inbox, Check, Clock, AlertCircle,
} from 'lucide-react';
import {
  Button, Badge, ErrorBanner, cn, api, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';

function useRoles() {
  const t = useT();
  return [
    { key: 'executor', label: t('templates62ApprovalsConfig.roleExecutor') },
    { key: 'reviewer', label: t('templates62ApprovalsConfig.roleReviewer') },
    { key: 'approver', label: t('templates62ApprovalsConfig.roleApprover') },
    { key: 'dept_manager', label: t('templates62ApprovalsConfig.roleDeptManager') },
    { key: 'admin', label: t('templates62ApprovalsConfig.roleAdmin') },
  ];
}
function useModes() {
  const t = useT();
  return [
    { key: 'one', label: t('templates62ApprovalsConfig.modeOne') },
    { key: 'all', label: t('templates62ApprovalsConfig.modeAll') },
    { key: 'majority', label: t('templates62ApprovalsConfig.modeMajority') },
  ];
}

export default function ApprovalsConfig() {
  const t = useT();
  const [tab, setTab] = useState<'inbox' | 'chains' | 'roles'>('inbox');
  return (
    <>
      <PageHeader title={t('templates62ApprovalsConfig.pageTitle')}
        description={t('templates62ApprovalsConfig.pageDescription')} />
      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-5">
        <div className="flex items-center gap-2">
          {[['inbox', t('templates62ApprovalsConfig.tabInbox'), Inbox], ['chains', t('templates62ApprovalsConfig.tabChains'), GitBranch], ['roles', t('templates62ApprovalsConfig.tabRoles'), Users]].map(([k, label, Icon]: any) => (
            <button key={k} onClick={() => setTab(k)}
              className={cn('inline-flex items-center gap-1.5 text-sm px-3.5 py-2 rounded-md-custom border transition-colors',
                tab === k ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/10 text-[var(--primary-gold-dark)]'
                          : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:bg-[var(--bg-app)]')}>
              <Icon className="w-4 h-4" /> {label}
            </button>
          ))}
        </div>
        {tab === 'inbox' ? <InboxTab /> : tab === 'chains' ? <ChainsTab /> : <RolesTab />}
      </div>
    </>
  );
}

// ─────────────────────── inbox (approver) ───────────────────────
function InboxTab() {
  const t = useT();
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [acting, setActing] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try { setItems((await api<{ pending: any[] }>('/api/v1/approval-inbox')).pending ?? []); }
    catch (e: any) { setProblem(e); } finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  async function decide(it: any, decision: 'approve' | 'reject') {
    let note: string | undefined;
    if (decision === 'reject') {
      note = window.prompt(t('templates62ApprovalsConfig.rejectReasonPrompt')) || '';
      if (!note.trim()) return;
    }
    setActing(it.approval_id); setProblem(null);
    try {
      await api(`/api/v1/workflow-runs/${it.run_id}/approve`, {
        method: 'POST', body: JSON.stringify({ decision, decision_note: note }),
      });
      load();
    } catch (e: any) { setProblem(e); } finally { setActing(null); }
  }

  return (
    <div className="space-y-4">
      <ErrorBanner problem={problem} />
      <p className="text-sm text-[var(--text-secondary)]">{t('templates62ApprovalsConfig.inboxDescription')}</p>
      {loading ? <Spinner /> : items.length === 0 ? (
        <Empty text={t('templates62ApprovalsConfig.inboxEmpty')} />
      ) : (
        <div className="space-y-2.5">
          {items.map((it) => (
            <div key={it.approval_id} className={cn('rounded-lg-custom bg-[var(--bg-card)] border p-4',
              it.overdue ? 'border-[var(--state-error)]/40' : 'border-[var(--border-color)]')}>
              <div className="flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-[var(--text-primary)]">{it.workflow_name}</span>
                    {it.step_title && <span className="text-xs text-[var(--text-secondary)]">· {it.step_title}</span>}
                    {it.is_chained && <Badge variant="info" className="text-[10px]">{t('templates62ApprovalsConfig.levelBadge', { n: it.level_no })}</Badge>}
                  </div>
                  {it.reason_prompt && <p className="text-xs text-[var(--text-secondary)] mt-1">{it.reason_prompt}</p>}
                  <p className={cn('text-[11px] mt-1.5 inline-flex items-center gap-1',
                    it.overdue ? 'text-[var(--state-error)]' : 'text-[var(--text-secondary)]')}>
                    {it.overdue ? <AlertCircle className="w-3 h-3" /> : <Clock className="w-3 h-3" />}
                    {it.overdue ? t('templates62ApprovalsConfig.overdueBy', { min: Math.abs(it.sla_remaining_min) }) : t('templates62ApprovalsConfig.remainingMin', { min: it.sla_remaining_min })}
                    · {t('templates62ApprovalsConfig.rolesLabel', { roles: it.approver_roles.join(', ') })}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <Button variant="secondary" className="!py-1 !px-2.5 !text-xs" isLoading={acting === it.approval_id}
                    onClick={() => decide(it, 'reject')}><X className="w-3.5 h-3.5 mr-1" /> {t('templates62ApprovalsConfig.reject')}</Button>
                  <Button className="!py-1 !px-2.5 !text-xs" isLoading={acting === it.approval_id}
                    onClick={() => decide(it, 'approve')}><Check className="w-3.5 h-3.5 mr-1" /> {t('templates62ApprovalsConfig.approve')}</Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─────────────────────── chains ───────────────────────
function ChainsTab() {
  const t = useT();
  const [chains, setChains] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState(''); const [dept, setDept] = useState('');

  async function load() {
    setLoading(true);
    try { setChains((await api<{ chains: any[] }>('/api/v1/approval-chains')).chains ?? []); }
    catch (e: any) { setProblem(e); } finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  async function create() {
    try {
      await api('/api/v1/approval-chains', { method: 'POST', body: JSON.stringify({ name, department_id: dept }) });
      setCreating(false); setName(''); setDept(''); load();
    } catch (e: any) { setProblem(e); }
  }

  return (
    <div className="space-y-4">
      <ErrorBanner problem={problem} />
      <div className="flex justify-between items-center">
        <p className="text-sm text-[var(--text-secondary)]">{t('templates62ApprovalsConfig.chainsDescPrefix')} <code className="text-[11px] bg-[var(--bg-app)] px-1 rounded">approval_chain_id</code> {t('templates62ApprovalsConfig.chainsDescSuffix')}</p>
        <Button variant="secondary" onClick={() => setCreating(true)}><Plus className="w-4 h-4 mr-1.5" /> {t('templates62ApprovalsConfig.newChain')}</Button>
      </div>
      {creating && (
        <div className="rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-4 flex items-end gap-2 flex-wrap">
          <Field label={t('templates62ApprovalsConfig.chainNameLabel')}><input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} placeholder={t('templates62ApprovalsConfig.chainNamePlaceholder')} /></Field>
          <Field label={t('templates62ApprovalsConfig.deptCodeLabel')}><input className={inputCls} value={dept} onChange={(e) => setDept(e.target.value)} placeholder="UUID" /></Field>
          <Button disabled={!name || !dept} onClick={create}>{t('templates62ApprovalsConfig.create')}</Button>
          <Button variant="secondary" onClick={() => setCreating(false)}>{t('templates62ApprovalsConfig.cancel')}</Button>
        </div>
      )}
      {loading ? <Spinner /> : chains.length === 0 ? <Empty text={t('templates62ApprovalsConfig.chainsEmpty')} /> : (
        <div className="space-y-2">
          {chains.map((c) => (
            <button key={c.chain_id} onClick={() => setOpenId(c.chain_id)}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] hover:bg-[var(--bg-app)]/30 text-left">
              <GitBranch className="w-4 h-4 text-[var(--primary-gold-dark)]" />
              <span className="flex-1 text-sm font-medium text-[var(--text-primary)]">{c.name_vi || c.name}</span>
              <ChevronRight className="w-4 h-4 text-[var(--text-secondary)]" />
            </button>
          ))}
        </div>
      )}
      {openId && <ChainDetail chainId={openId} onClose={() => setOpenId(null)} />}
    </div>
  );
}

function ChainDetail({ chainId, onClose }: { chainId: string; onClose: () => void }) {
  const t = useT();
  const MODES = useModes();
  const [chain, setChain] = useState<any>(null);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [adding, setAdding] = useState(false);
  const [roles, setRoles] = useState('approver'); const [mode, setMode] = useState('one'); const [sla, setSla] = useState('1440');

  async function load() {
    try { setChain(await api<any>(`/api/v1/approval-chains/${chainId}`)); } catch (e: any) { setProblem(e); }
  }
  useEffect(() => { load(); }, [chainId]);

  async function addLevel() {
    try {
      const nextNo = (chain?.levels?.length ?? 0) + 1;
      await api(`/api/v1/approval-chains/${chainId}/levels`, {
        method: 'POST',
        body: JSON.stringify({ level_no: nextNo, approver_roles: roles.split(',').map((r) => r.trim()).filter(Boolean), mode, sla_minutes: Number(sla) }),
      });
      setAdding(false); load();
    } catch (e: any) { setProblem(e); }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={onClose}>
      <div className="w-full max-w-md bg-[var(--bg-app)] h-full overflow-y-auto shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="sticky top-0 bg-[var(--bg-card)] border-b border-[var(--border-color)] px-5 py-4 flex items-center gap-2">
          <button onClick={onClose}><X className="w-5 h-5 text-[var(--text-secondary)]" /></button>
          <h2 className="font-serif text-base text-[var(--text-primary)]">{chain?.name_vi || chain?.name || '…'}</h2>
        </div>
        <div className="p-5 space-y-4">
          <ErrorBanner problem={problem} />
          <div className="space-y-2">
            {(chain?.levels ?? []).map((l: any) => (
              <div key={l.level_id} className="rounded-md-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-3">
                <div className="flex items-center gap-2">
                  <Badge variant="default" className="text-[10px]">{t('templates62ApprovalsConfig.levelBadge', { n: l.level_no })}</Badge>
                  <span className="text-sm text-[var(--text-primary)]">{(l.approver_roles || []).join(', ')}</span>
                  <Badge variant="info" className="text-[10px] ml-auto">{MODES.find((m) => m.key === l.mode)?.label ?? l.mode}</Badge>
                </div>
                <p className="text-[11px] text-[var(--text-secondary)] mt-1">{t('templates62ApprovalsConfig.slaTimeout', { min: l.sla_minutes, timeout: l.on_timeout })}</p>
              </div>
            ))}
            {(chain?.levels ?? []).length === 0 && <Empty text={t('templates62ApprovalsConfig.levelsEmpty')} />}
          </div>
          {adding ? (
            <div className="rounded-md-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-3 space-y-2">
              <Field label={t('templates62ApprovalsConfig.approverRolesLabel')}><input className={inputCls} value={roles} onChange={(e) => setRoles(e.target.value)} placeholder="MANAGER, CFO" /></Field>
              <div className="grid grid-cols-2 gap-2">
                <Field label={t('templates62ApprovalsConfig.modeLabel')}><select className={inputCls} value={mode} onChange={(e) => setMode(e.target.value)}>{MODES.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}</select></Field>
                <Field label={t('templates62ApprovalsConfig.slaMinutesLabel')}><input className={inputCls} type="number" value={sla} onChange={(e) => setSla(e.target.value)} /></Field>
              </div>
              <div className="flex gap-2"><Button onClick={addLevel}>{t('templates62ApprovalsConfig.add')}</Button><Button variant="secondary" onClick={() => setAdding(false)}>{t('templates62ApprovalsConfig.cancel')}</Button></div>
            </div>
          ) : (
            <Button variant="secondary" onClick={() => setAdding(true)}><Plus className="w-4 h-4 mr-1.5" /> {t('templates62ApprovalsConfig.addLevel', { n: (chain?.levels?.length ?? 0) + 1 })}</Button>
          )}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────── roles ───────────────────────
function RolesTab() {
  const t = useT();
  const ROLES = useRoles();
  const [dept, setDept] = useState('');
  const [roles, setRoles] = useState<any[]>([]);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [user, setUser] = useState(''); const [role, setRole] = useState('approver');

  async function load() {
    if (!dept) { setRoles([]); return; }
    try { setRoles((await api<{ roles: any[] }>(`/api/v1/user-department-roles?department_id=${dept}`)).roles ?? []); }
    catch (e: any) { setProblem(e); }
  }
  useEffect(() => { load(); }, [dept]);

  async function grant() {
    try {
      await api('/api/v1/user-department-roles', { method: 'POST', body: JSON.stringify({ user_id: user, department_id: dept, functional_role: role }) });
      setUser(''); load();
    } catch (e: any) { setProblem(e); }
  }
  async function revoke(id: string) {
    try { await api(`/api/v1/user-department-roles/${id}`, { method: 'DELETE' }); load(); } catch (e: any) { setProblem(e); }
  }

  return (
    <div className="space-y-4">
      <ErrorBanner problem={problem} />
      <p className="text-sm text-[var(--text-secondary)]">{t('templates62ApprovalsConfig.rolesDescription')}</p>
      <Field label={t('templates62ApprovalsConfig.deptCodeLabel')}><input className={inputCls} value={dept} onChange={(e) => setDept(e.target.value)} placeholder={t('templates62ApprovalsConfig.deptCodePlaceholder')} /></Field>
      {dept && (
        <>
          <div className="rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-4 flex items-end gap-2 flex-wrap">
            <Field label={t('templates62ApprovalsConfig.userCodeLabel')}><input className={inputCls} value={user} onChange={(e) => setUser(e.target.value)} placeholder={t('templates62ApprovalsConfig.userCodePlaceholder')} /></Field>
            <Field label={t('templates62ApprovalsConfig.roleLabel')}><select className={inputCls} value={role} onChange={(e) => setRole(e.target.value)}>{ROLES.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}</select></Field>
            <Button disabled={!user} onClick={grant}><Shield className="w-4 h-4 mr-1.5" /> {t('templates62ApprovalsConfig.grant')}</Button>
          </div>
          {roles.length === 0 ? <Empty text={t('templates62ApprovalsConfig.rolesEmpty')} /> : (
            <div className="space-y-1.5">
              {roles.map((r) => (
                <div key={r.id} className="flex items-center gap-3 rounded-md-custom bg-[var(--bg-card)] border border-[var(--border-color)] px-4 py-2.5">
                  <Users className="w-4 h-4 text-[var(--text-secondary)]" />
                  <span className="text-sm font-mono text-[var(--text-primary)] truncate flex-1">{r.user_id}</span>
                  <Badge variant="info">{ROLES.find((x) => x.key === r.functional_role)?.label ?? r.functional_role}</Badge>
                  <button onClick={() => revoke(r.id)} className="text-[var(--text-secondary)] hover:text-[var(--state-error)]"><Trash2 className="w-4 h-4" /></button>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

const inputCls = 'w-full h-9 rounded-md-custom border border-[var(--border-color)] bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30';
function Field({ label, children }: any) { return <div className="min-w-[140px] flex-1"><label className="text-[11px] text-[var(--text-secondary)] block mb-1">{label}</label>{children}</div>; }
function Spinner() { return <div className="flex justify-center py-8 text-[var(--text-secondary)]"><Loader2 className="w-5 h-5 animate-spin" /></div>; }
function Empty({ text }: { text: string }) { return <p className="text-sm text-[var(--text-secondary)] py-6 text-center bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)]">{text}</p>; }
