// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 61. /p2/contracts — Contract Library + Detail + e-sign (ADR-0037 Phase 3)
// ----------------------------------------------------------------------------
// GET  /api/v1/contracts[?status=]        — library list
// GET  /api/v1/contracts/{id}             — detail (parties + signatures + turn)
// POST /api/v1/contracts                  — create (draft) + parties
// POST /api/v1/contracts/{id}/send        — nhap → cho_ky
// POST /api/v1/contracts/{id}/sign        — internal click-to-sign
// POST /api/v1/contracts/{id}/reject      — tu_choi
//
// Distinct from /contracts (customer_contracts = Kaori's own sales). These are
// the tenant's business contracts produced by workflows. Business Vietnamese,
// signing timeline, whose-turn gating.
// ============================================================================

import React, { useState, useEffect } from 'react';
import {
  FileSignature, Plus, Send, Check, X, Clock, ShieldCheck, ChevronLeft,
  Loader2, AlertCircle, CheckCircle2, PenLine,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, cn, api, formatVND, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';

const STATUS_VARIANT: Record<string, any> = {
  nhap: 'default', cho_ky: 'warning', hieu_luc: 'success',
  het_han: 'neutral', thanh_ly: 'neutral', tu_choi: 'error',
};

export default function ContractsLibrary() {
  const t = useT();
  const STATUS_FILTERS = [
    { key: '', label: t('templates61Contracts.filterAll') },
    { key: 'cho_ky', label: t('templates61Contracts.filterPendingSign') },
    { key: 'hieu_luc', label: t('templates61Contracts.filterEffective') },
    { key: 'nhap', label: t('templates61Contracts.filterDraft') },
    { key: 'tu_choi', label: t('templates61Contracts.filterRejected') },
  ];
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [filter, setFilter] = useState('');
  const [openId, setOpenId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  async function load() {
    setLoading(true); setProblem(null);
    try {
      const q = filter ? `?status=${filter}` : '';
      const res = await api<{ contracts: any[] }>(`/api/v1/contracts${q}`);
      setRows(res.contracts ?? []);
    } catch (err: any) { setProblem(err); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, [filter]);

  const expiringSoon = rows.filter((r) => {
    if (r.status !== 'hieu_luc' || !r.expires_at) return false;
    const days = (new Date(r.expires_at).getTime() - Date.now()) / 86400000;
    return days >= 0 && days <= 30;
  }).length;

  return (
    <>
      <PageHeader
        title={t('templates61Contracts.title')}
        description={t('templates61Contracts.description')}
        actions={<Button onClick={() => setCreating(true)}><Plus className="w-4 h-4 mr-2" /> {t('templates61Contracts.createContract')}</Button>}
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1280px] mx-auto space-y-5">
        <ErrorBanner problem={problem} />

        {expiringSoon > 0 && (
          <div className="rounded-md-custom bg-[var(--state-warning)]/10 border border-[var(--state-warning)]/35 p-3 flex items-center gap-2.5">
            <Clock className="w-4 h-4 text-[var(--state-warning)] shrink-0" />
            <span className="text-sm text-[#9E814D]"><b>{expiringSoon}</b> {t('templates61Contracts.expiringSoonSuffix')}</span>
          </div>
        )}

        {/* filter tabs */}
        <div className="flex items-center gap-2 flex-wrap">
          {STATUS_FILTERS.map((f) => (
            <button key={f.key} onClick={() => setFilter(f.key)}
              className={cn('text-xs px-3 py-1.5 rounded-md-custom border transition-colors',
                filter === f.key ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/10 text-[var(--primary-gold-dark)]'
                                 : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:bg-[var(--bg-app)]')}>
              {f.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="space-y-2">{[1,2,3].map((i) => <div key={i} className="h-16 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse" />)}</div>
        ) : rows.length === 0 ? (
          <div className="p-12 text-center text-[var(--text-secondary)] bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)]">
            <FileSignature className="w-8 h-8 mx-auto mb-2 opacity-40" />
            {t('templates61Contracts.emptyState')}
          </div>
        ) : (
          <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden divide-y divide-[var(--border-color)]/60">
            {rows.map((c) => (
              <button key={c.contract_id} onClick={() => setOpenId(c.contract_id)}
                className="w-full flex items-center gap-4 px-5 py-3.5 text-left hover:bg-[var(--bg-app)]/30 transition-colors">
                <FileSignature className="w-5 h-5 text-[var(--primary-gold-dark)] shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-[var(--text-primary)] truncate">{c.title}</p>
                  <p className="text-[11px] text-[var(--text-secondary)] font-mono">{c.contract_no}</p>
                </div>
                {c.value_vnd != null && <span className="text-sm text-[var(--text-primary)] shrink-0">{formatVND(c.value_vnd)}</span>}
                <Badge variant={STATUS_VARIANT[c.status] ?? 'default'} className="shrink-0">{c.status_label}</Badge>
              </button>
            ))}
          </div>
        )}

        <div className="flex items-start gap-3 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>{t('templates61Contracts.signatureNote')}</p>
        </div>
      </div>

      {openId && <ContractDetail contractId={openId} onClose={() => setOpenId(null)} onChanged={load} />}
      {creating && <CreateContractModal onClose={() => setCreating(false)} onCreated={(id) => { setCreating(false); load(); setOpenId(id); }} />}
    </>
  );
}

function ContractDetail({ contractId, onClose, onChanged }: { contractId: string; onClose: () => void; onChanged: () => void }) {
  const t = useT();
  const [c, setC] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  async function load() {
    try { setC(await api<any>(`/api/v1/contracts/${contractId}`)); }
    catch (err: any) { setProblem(err); }
  }
  useEffect(() => { load(); }, [contractId]);

  async function act(path: string, body?: any) {
    setBusy(true); setProblem(null);
    try {
      await api(`/api/v1/contracts/${contractId}/${path}`, { method: 'POST', body: body ? JSON.stringify(body) : '{}' });
      await load(); onChanged();
    } catch (err: any) { setProblem(err); }
    finally { setBusy(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={onClose}>
      <div className="w-full max-w-xl bg-[var(--bg-app)] h-full overflow-y-auto shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="sticky top-0 bg-[var(--bg-card)] border-b border-[var(--border-color)] px-5 py-4 flex items-center gap-3 z-10">
          <button onClick={onClose} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]"><ChevronLeft className="w-5 h-5" /></button>
          <div className="flex-1 min-w-0">
            <h2 className="font-serif text-base text-[var(--text-primary)] truncate">{c?.title ?? '…'}</h2>
            <p className="text-[11px] text-[var(--text-secondary)] font-mono">{c?.contract_no}</p>
          </div>
          {c && <Badge variant={STATUS_VARIANT[c.status] ?? 'default'}>{c.status_label}</Badge>}
        </div>

        {!c ? (
          <div className="flex items-center justify-center py-16 text-[var(--text-secondary)]"><Loader2 className="w-5 h-5 animate-spin mr-2" /> {t('templates61Contracts.loading')}</div>
        ) : (
          <div className="p-5 space-y-5">
            <ErrorBanner problem={problem} />

            {/* header facts */}
            <div className="grid grid-cols-2 gap-3">
              {c.value_vnd != null && <Fact label={t('templates61Contracts.factValue')} value={formatVND(c.value_vnd)} />}
              <Fact label={t('templates61Contracts.factSignMode')} value={c.sign_mode === 'all' ? t('templates61Contracts.signModeAll') : t('templates61Contracts.signModeMin', { count: c.required_signatures ?? '?' })} />
              {c.effective_at && <Fact label={t('templates61Contracts.factEffectiveFrom')} value={new Date(c.effective_at).toLocaleDateString('vi-VN')} />}
              {c.expires_at && <Fact label={t('templates61Contracts.factExpires')} value={new Date(c.expires_at).toLocaleDateString('vi-VN')} />}
            </div>

            {/* parties + signing */}
            <div>
              <h3 className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] font-medium mb-2">{t('templates61Contracts.partiesHeading')}</h3>
              <div className="space-y-2">
                {(c.parties ?? []).map((p: any) => (
                  <div key={p.party_id} className="flex items-center gap-3 rounded-md-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-3">
                    <div className="w-7 h-7 rounded-full bg-[var(--bg-app)] flex items-center justify-center text-[10px] text-[var(--text-secondary)] shrink-0">{p.sign_order}</div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-[var(--text-primary)] truncate">{p.party_role}</p>
                      <p className="text-[11px] text-[var(--text-secondary)] truncate">{p.external_name || p.internal_user_id || '—'}</p>
                    </div>
                    {p.has_signed ? (
                      <Badge variant="success" className="text-[10px]"><Check className="w-2.5 h-2.5 mr-0.5 inline" /> {t('templates61Contracts.signed')}</Badge>
                    ) : c.status === 'cho_ky' && p.is_turn ? (
                      <Button variant="secondary" className="!py-1 !px-2.5 !text-xs" isLoading={busy} onClick={() => act('sign', { party_id: p.party_id })}>
                        <PenLine className="w-3.5 h-3.5 mr-1" /> {t('templates61Contracts.sign')}
                      </Button>
                    ) : (
                      <Badge variant="default" className="text-[10px]">{c.status === 'cho_ky' ? t('templates61Contracts.waitingTurn') : t('templates61Contracts.notSigned')}</Badge>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* signatures timeline */}
            {(c.signatures ?? []).length > 0 && (
              <div>
                <h3 className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] font-medium mb-2">{t('templates61Contracts.signHistoryHeading')}</h3>
                <div className="space-y-1.5">
                  {c.signatures.map((s: any) => (
                    <div key={s.signature_id} className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                      <CheckCircle2 className="w-3.5 h-3.5 text-[var(--state-success)] shrink-0" />
                      <span className="text-[var(--text-primary)]">{s.signer_label}</span>
                      <span>· {new Date(s.signed_at).toLocaleString('vi-VN')}</span>
                      <span className="ml-auto font-mono opacity-60">{s.method}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* actions */}
            <div className="flex items-center gap-2 pt-2 border-t border-[var(--border-color)]">
              {c.status === 'nhap' && (
                <Button isLoading={busy} onClick={() => act('send')}><Send className="w-4 h-4 mr-2" /> {t('templates61Contracts.sendForSign')}</Button>
              )}
              {c.status === 'cho_ky' && (
                <Button variant="secondary" isLoading={busy}
                  onClick={() => act('reject', { party_id: c.parties?.[0]?.party_id, reason: 'từ chối' })}>
                  <X className="w-4 h-4 mr-2" /> {t('templates61Contracts.reject')}
                </Button>
              )}
              {c.status === 'hieu_luc' && (
                <p className="text-sm text-[var(--state-success)] flex items-center gap-1.5"><CheckCircle2 className="w-4 h-4" /> {t('templates61Contracts.contractEffective')}</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-3">
      <p className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">{label}</p>
      <p className="text-sm text-[var(--text-primary)] mt-0.5">{value}</p>
    </div>
  );
}

function CreateContractModal({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const t = useT();
  const [title, setTitle] = useState('');
  const [dept, setDept] = useState('');
  const [value, setValue] = useState('');
  const [partyRole, setPartyRole] = useState('Bên A');
  const [partyName, setPartyName] = useState('');
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  async function submit() {
    setBusy(true); setProblem(null);
    try {
      const res = await api<{ contract_id: string }>('/api/v1/contracts', {
        method: 'POST',
        body: JSON.stringify({
          department_id: dept, title,
          value_vnd: value ? Number(value) : null,
          sign_mode: 'all',
          parties: [{ party_role: partyRole, external_name: partyName || null, sign_order: 1 }],
        }),
      });
      onCreated(res.contract_id);
    } catch (err: any) { setProblem(err); }
    finally { setBusy(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/40" onClick={onClose}>
      <div className="w-full max-w-md bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-2xl p-5 space-y-4" onClick={(e) => e.stopPropagation()}>
        <h2 className="font-serif text-base text-[var(--text-primary)]">{t('templates61Contracts.createContract')}</h2>
        <ErrorBanner problem={problem} />
        <Field label={t('templates61Contracts.fieldContractName')}><input className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} placeholder={t('templates61Contracts.placeholderContractName')} /></Field>
        <Field label={t('templates61Contracts.fieldDepartmentId')}><input className={inputCls} value={dept} onChange={(e) => setDept(e.target.value)} placeholder={t('templates61Contracts.placeholderDepartmentId')} /></Field>
        <Field label={t('templates61Contracts.fieldValue')}><input className={inputCls} type="number" value={value} onChange={(e) => setValue(e.target.value)} placeholder="50000000" /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t('templates61Contracts.fieldPartyRole')}><input className={inputCls} value={partyRole} onChange={(e) => setPartyRole(e.target.value)} /></Field>
          <Field label={t('templates61Contracts.fieldSignerName')}><input className={inputCls} value={partyName} onChange={(e) => setPartyName(e.target.value)} placeholder={t('templates61Contracts.placeholderSignerName')} /></Field>
        </div>
        <div className="flex items-center justify-end gap-2 pt-1">
          <Button variant="secondary" onClick={onClose}>{t('templates61Contracts.cancel')}</Button>
          <Button isLoading={busy} disabled={!title || !dept} onClick={submit}>{t('templates61Contracts.create')}</Button>
        </div>
      </div>
    </div>
  );
}

const inputCls = 'w-full h-9 rounded-md-custom border border-[var(--border-color)] bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30';
function Field({ label, children }: any) {
  return <div><label className="text-[11px] text-[var(--text-secondary)] block mb-1">{label}</label>{children}</div>;
}
