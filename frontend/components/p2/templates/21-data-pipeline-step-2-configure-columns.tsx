// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 21. /p2/pipelines/{id}/step-2-columns — Step 2 Schema Review (F-018)
// ----------------------------------------------------------------------------
// POST /api/v1/schema          {run_id} → {sheets:[{mappings:[...]}]}
// GET  /api/v1/schema/fields   → {fields:[{canonical,label,data_type,description}]}
// POST /api/v1/schema/confirm  {run_id, overrides:[{source_column, canonical_name, data_type}]}
//
// Executive redesign (pipeline UX review): a CEO/PM/kế-toán shouldn't face a
// technical table of "canonical / fuzzy / confidence". Each column is now a
// CARD that asks, in business Vietnamese, "Đây là thông tin gì?" — answered by
// a dropdown of real field labels (from /schema/fields, the dictionary's own
// single source of truth, NOT a FE hardcode). Plus:
//   • progress "X/N cột đã xác nhận" + ~2 phút estimate,
//   • 🔴 cần xác nhận / 🟡 kiểm tra nhanh / 🟢 đã chuẩn grouping,
//   • Impact Preview: which analyses unlock as columns are confirmed,
//   • "Xác nhận tất cả đề xuất AI" fast path,
//   • conflict detection when two columns claim the same unique field,
//   • picking a field auto-sets its format (no "string"/"numeric" jargon).
// ============================================================================

import React, { useState, useEffect, useMemo } from 'react';
import { useParams } from 'next/navigation';
import {
  CheckCircle2, AlertCircle, AlertTriangle, ChevronLeft, ChevronRight,
  ChevronDown, HelpCircle, Sparkles, Trash2, Undo2, Check, X, CheckCheck,
  Type, Hash, Calendar, ToggleLeft, Mail, Phone, Coins, Tag, Lock,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, cn,
  api,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { WizardStepper } from '@/components/p2/foundation-wizard';
import { useT } from '@/lib/i18n/provider';

type ColumnType = 'string' | 'integer' | 'numeric' | 'date' | 'boolean' | 'email' | 'phone' | 'currency' | 'category';
type Tier = 'confirm' | 'review' | 'ok' | 'empty';

interface CanonicalField {
  canonical:   string;
  label:       string;
  data_type:   string;
  description?: string;
}

interface ColumnMapping {
  detected_name:    string;
  canonical_name:   string;   // canonical slug, '' when unidentified
  type:             ColumnType;
  confidence:       number;
  method:           string;
  null_pct:         number;
  sample_values:    string[];
  is_pii:           boolean;
  is_empty:         boolean;
  looks_unnamed:    boolean;
  header_looks_like_data: boolean;
  sniffed:          boolean;
  tier:             Tier;
  edited:           boolean;
  confirmed:        boolean;   // user explicitly accepted
  skipped:          boolean;
  custom:           boolean;   // "Khác — nhập tên khác" free-text mode
}

const CUSTOM = '__custom__';

// Business-language type tags — never show "string"/"numeric".
const TYPE_KEY: Record<ColumnType, string> = {
  string: 'typeString', integer: 'typeNumber', numeric: 'typeNumber', currency: 'typeCurrency',
  date: 'typeDate', phone: 'typePhone', email: 'typeEmail', boolean: 'typeBoolean', category: 'typeCategory',
};
const TYPE_ICON: Record<ColumnType, any> = {
  string: Type, integer: Hash, numeric: Hash, currency: Coins,
  date: Calendar, phone: Phone, email: Mail, boolean: ToggleLeft, category: Tag,
};

function _mapType(dt: string): ColumnType {
  const t = (dt || '').toLowerCase();
  if (t === 'text' || t === 'string') return 'string';
  return (['integer', 'numeric', 'date', 'boolean', 'email', 'phone', 'currency', 'category'].includes(t)
    ? t : 'string') as ColumnType;
}

function _slug(s: string): string {
  return (s || '').toLowerCase().trim().replace(/\s+/g, '_');
}

function _computeTier(m: { method: string; is_empty: boolean; looks_unnamed: boolean; header_looks_like_data: boolean; sniffed: boolean; confidence: number; }): Tier {
  if (m.is_empty || m.looks_unnamed) return 'empty';
  if (m.method === 'no_match' || m.header_looks_like_data) return 'confirm';
  if (m.method === 'exact_match' && m.confidence >= 0.99 && !m.sniffed) return 'ok';
  return 'review';
}

const TIER_DOT: Record<Tier, string> = {
  confirm: 'bg-[var(--state-error)]',
  review:  'bg-[#C9A227]',
  ok:      'bg-[var(--state-success)]',
  empty:   'bg-[var(--text-secondary)]',
};
const TIER_KEYS: Record<Tier, { labelKey: string; hintKey: string }> = {
  confirm: { labelKey: 'tierConfirmLabel', hintKey: 'tierConfirmHint' },
  review:  { labelKey: 'tierReviewLabel', hintKey: 'tierReviewHint' },
  ok:      { labelKey: 'tierOkLabel', hintKey: 'tierOkHint' },
  empty:   { labelKey: 'tierEmptyLabel', hintKey: 'tierEmptyHint' },
};
function tierMeta(t: (key: string, params?: Record<string, any>) => string, tier: Tier): { label: string; hint: string; dot: string } {
  const { labelKey, hintKey } = TIER_KEYS[tier];
  return {
    label: t(`templates21DataPipelineStep2ConfigureColumns.${labelKey}`),
    hint: t(`templates21DataPipelineStep2ConfigureColumns.${hintKey}`),
    dot: TIER_DOT[tier],
  };
}

// Impact Preview — which analyses unlock from the confirmed fields. This is a
// UX guidance panel (product capabilities), evaluated against the REAL confirmed
// canonicals; it mirrors the analytics template requirements. `need` = all
// required; `any` = at least one of.
const CAPABILITIES: { key: string; need: string[]; any?: string[] }[] = [
  { key: 'capRevenueByTime',    need: ['date'], any: ['amount', 'revenue', 'unit_price'] },
  { key: 'capCustomerSegment',  need: [], any: ['gender', 'age', 'customer_external_id'] },
  { key: 'capChurnRisk',        need: ['customer_external_id', 'date'] },
  { key: 'capPaymentMethod',    need: ['payment_method'] },
  { key: 'capTopProducts',      need: ['product'], any: ['quantity', 'amount', 'revenue'] },
];

// Canonicals that must map from at most ONE column (a hard conflict if two claim it).
const UNIQUE_CANONICALS = new Set(['customer_external_id', 'date', 'order_id']);

export default function PipelineStep2Columns() {
  const t = useT();
  const params = useParams<{ id: string }>();
  const pipelineId = params?.id ?? '';

  const [mappings, setMappings] = useState<ColumnMapping[]>([]);
  const [fields,   setFields]   = useState<CanonicalField[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [problem,  setProblem]  = useState<ProblemDetails | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [open, setOpen] = useState<Record<Tier, boolean>>({
    confirm: true, review: true, ok: false, empty: false,
  });

  async function loadFields() {
    try {
      const res = await api<{ fields: CanonicalField[] }>(`/api/v1/schema/fields`);
      setFields(res.fields ?? []);
    } catch { /* non-blocking — dropdown falls back to free-text only */ }
  }

  async function load() {
    setLoading(true);
    setProblem(null);
    try {
      const res = await api<{ sheets: any[] }>(`/api/v1/schema`, {
        method: 'POST',
        body: JSON.stringify({ run_id: pipelineId }),
      });
      const flat: ColumnMapping[] = (res.sheets ?? []).flatMap((s: any) =>
        (s.mappings ?? []).map((m: any) => {
          const flags = (m.uncertainty_flags ?? []).map((f: any) => String(f));
          const method = m.method ?? 'no_match';
          const base = {
            detected_name:  m.source_column,
            canonical_name: method === 'no_match' ? '' : m.canonical_name,
            type:           _mapType(m.data_type),
            confidence:     m.confidence ?? 0,
            method,
            null_pct:       m.null_pct ?? 0,
            sample_values:  m.sample_values ?? [],
            is_pii:         flags.some((f: string) => f.includes('PII')),
            is_empty:       !!m.is_empty,
            looks_unnamed:  !!m.looks_unnamed,
            header_looks_like_data: !!m.header_looks_like_data,
            sniffed:        flags.includes('VALUE_SNIFFED_TYPE'),
          };
          return { ...base, tier: _computeTier(base), edited: false, confirmed: false, skipped: false, custom: false };
        }),
      );
      setMappings(flat);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { if (pipelineId) { loadFields(); load(); } }, [pipelineId]);

  function update(detected: string, patch: Partial<ColumnMapping>) {
    setMappings((prev) => prev.map((m) =>
      m.detected_name === detected ? { ...m, ...patch } : m));
  }

  // Pick a field from the dropdown → set canonical + auto-set its format.
  function pickField(detected: string, value: string) {
    if (value === CUSTOM) {
      update(detected, { custom: true, canonical_name: '', edited: true, confirmed: false });
      return;
    }
    const f = fields.find((x) => x.canonical === value);
    update(detected, {
      custom: false,
      canonical_name: value,
      type: f ? _mapType(f.data_type) : 'string',
      edited: true,
      confirmed: !!value,   // a concrete pick counts as confirmed
    });
  }

  function confirmCol(detected: string) { update(detected, { confirmed: true, skipped: false }); }
  function skipCol(detected: string)    { update(detected, { skipped: true, confirmed: false }); }
  function unskipCol(detected: string)  { update(detected, { skipped: false }); }

  function skipAllEmpty() {
    setMappings((prev) => prev.map((m) => (m.tier === 'empty' ? { ...m, skipped: true } : m)));
  }
  function confirmAllAI() {
    // Accept every AI suggestion that has a canonical guess (skip the unidentified
    // and the blanks — those still need a human pick / skip).
    setMappings((prev) => prev.map((m) =>
      (m.tier !== 'empty' && m.canonical_name && !m.skipped)
        ? { ...m, confirmed: true } : m));
  }

  async function confirm() {
    setConfirming(true);
    setProblem(null);
    try {
      await api(`/api/v1/schema/confirm`, {
        method: 'POST',
        body: JSON.stringify({
          run_id: pipelineId,
          overrides: mappings.filter((m) => !m.skipped).map((m) => ({
            source_column:  m.detected_name,
            canonical_name: m.canonical_name || _slug(m.detected_name),
            data_type:      m.type,
          })),
        }),
      });
      window.location.href = `/p2/pipelines/${pipelineId}/step-3-clean`;
    } catch (err: any) {
      setProblem(err);
    } finally {
      setConfirming(false);
    }
  }

  const groups = useMemo(() => {
    const g: Record<Tier, ColumnMapping[]> = { confirm: [], review: [], ok: [], empty: [] };
    mappings.forEach((m) => g[m.tier].push(m));
    return g;
  }, [mappings]);

  // A column is "resolved" when explicitly confirmed, auto-OK, or skipped.
  const total    = mappings.length;
  const resolved = mappings.filter((m) => m.confirmed || m.tier === 'ok' || m.skipped).length;
  const pct      = total ? Math.round((resolved / total) * 100) : 0;

  // Confirmed canonical set (for the impact preview).
  const activeCanonicals = useMemo(() => {
    const s = new Set<string>();
    mappings.forEach((m) => {
      if (!m.skipped && m.canonical_name && (m.confirmed || m.tier === 'ok')) s.add(m.canonical_name);
    });
    return s;
  }, [mappings]);

  // Conflicts: a canonical claimed by >1 non-skipped column. Hard if a unique one.
  const conflicts = useMemo(() => {
    const byCanon: Record<string, string[]> = {};
    mappings.forEach((m) => {
      if (m.skipped || !m.canonical_name) return;
      (byCanon[m.canonical_name] ??= []).push(m.detected_name);
    });
    const dup: Record<string, string[]> = {};
    Object.entries(byCanon).forEach(([c, cols]) => { if (cols.length > 1) dup[c] = cols; });
    return dup;
  }, [mappings]);
  const hardConflicts = Object.keys(conflicts).filter((c) => UNIQUE_CANONICALS.has(c));
  const conflictCols = useMemo(() => new Set(Object.values(conflicts).flat()), [conflicts]);

  const labelFor = useMemo(() => {
    const m: Record<string, string> = {};
    fields.forEach((f) => { m[f.canonical] = f.label; });
    return m;
  }, [fields]);

  return (
    <>
      <PageHeader
        title={t('templates21DataPipelineStep2ConfigureColumns.pageTitle')}
        description={t('templates21DataPipelineStep2ConfigureColumns.pageDescription')}
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1280px] mx-auto space-y-5">
        <WizardStepper current={2} pipelineId={pipelineId} />
        <ErrorBanner problem={problem} />

        {/* Header banner + progress */}
        {!loading && total > 0 && (
          <div className="rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-4 shadow-soft-sm space-y-3">
            <p className="text-sm text-[var(--text-primary)]">
              {t('templates21DataPipelineStep2ConfigureColumns.headerIntro')} <b>{t('templates21DataPipelineStep2ConfigureColumns.headerCount', { total })}</b>{t('templates21DataPipelineStep2ConfigureColumns.headerMid')} <b>{t('templates21DataPipelineStep2ConfigureColumns.headerMinutes')}</b>
            </p>
            <div className="flex items-center gap-3">
              <div className="flex-1 h-2.5 rounded-full bg-[var(--bg-app)] overflow-hidden">
                <div className="h-2.5 rounded-full bg-[var(--state-success)] transition-all" style={{ width: `${pct}%` }} />
              </div>
              <span className="text-xs font-medium text-[var(--text-secondary)] shrink-0">{t('templates21DataPipelineStep2ConfigureColumns.progressLabel', { resolved, total })}</span>
            </div>
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <button
                onClick={confirmAllAI}
                className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md-custom border border-[var(--primary-gold)]/40 bg-[var(--primary-gold)]/8 text-[var(--primary-gold-dark)] hover:bg-[var(--primary-gold)]/15 transition-colors"
              >
                <CheckCheck className="w-3.5 h-3.5" /> {t('templates21DataPipelineStep2ConfigureColumns.confirmAllAi')}
              </button>
              <span className="text-xs text-[var(--text-secondary)]">{t('templates21DataPipelineStep2ConfigureColumns.editBelowHint')}</span>
            </div>
          </div>
        )}

        {/* Conflict warning */}
        {Object.keys(conflicts).length > 0 && (
          <div className="rounded-md-custom bg-[var(--state-warning)]/10 border border-[var(--state-warning)]/35 p-3 flex items-start gap-3">
            <AlertTriangle className="w-4 h-4 text-[var(--state-warning)] shrink-0 mt-0.5" />
            <div className="text-sm text-[#9E814D]">
              <b>{t('templates21DataPipelineStep2ConfigureColumns.conflictHeading')}</b>{' '}
              {Object.entries(conflicts).map(([c, cols]) => (
                <span key={c} className="block text-xs mt-1">
                  «{labelFor[c] ?? c}»: {cols.join(', ')}
                  {UNIQUE_CANONICALS.has(c) && <span className="text-[var(--state-error)]"> — {t('templates21DataPipelineStep2ConfigureColumns.conflictUniqueOnly')}</span>}
                </span>
              ))}
              {hardConflicts.length > 0 && <p className="text-xs mt-1.5">{t('templates21DataPipelineStep2ConfigureColumns.conflictFixBeforeContinue')}</p>}
            </div>
          </div>
        )}

        <div className="grid lg:grid-cols-[1fr_300px] gap-5 items-start">
          {/* Column cards */}
          <div className="space-y-5">
            {loading ? (
              <div className="grid sm:grid-cols-2 gap-3">
                {[1, 2, 3, 4].map((i) => <div key={i} className="h-44 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse" />)}
              </div>
            ) : total === 0 ? (
              <p className="p-12 text-center text-[var(--text-secondary)] bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)]">
                {t('templates21DataPipelineStep2ConfigureColumns.noColumnsDetected')}
              </p>
            ) : (
              (['confirm', 'review', 'ok', 'empty'] as Tier[]).map((tier) => {
                const rows = groups[tier];
                if (rows.length === 0) return null;
                return (
                  <TierGroup
                    key={tier}
                    tier={tier}
                    rows={rows}
                    isOpen={open[tier]}
                    onToggle={() => setOpen((o) => ({ ...o, [tier]: !o[tier] }))}
                    fields={fields}
                    onPick={pickField}
                    onUpdate={update}
                    onConfirm={confirmCol}
                    onSkip={skipCol}
                    onUnskip={unskipCol}
                    onSkipAll={skipAllEmpty}
                    conflictCols={conflictCols}
                  />
                );
              })
            )}
          </div>

          {/* Impact preview (sticky on desktop) */}
          {!loading && total > 0 && (
            <ImpactPreview active={activeCanonicals} fields={fields} />
          )}
        </div>

        <div className="flex items-start gap-3 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <CheckCircle2 className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            {t('templates21DataPipelineStep2ConfigureColumns.footerNote')}
          </p>
        </div>

        <div className="flex items-center justify-between">
          <Button
            variant="secondary"
            onClick={() => (window.location.href = `/p2/pipelines/${pipelineId}/step-1-upload`)}
            disabled={confirming}
          >
            <ChevronLeft className="w-4 h-4 mr-1" /> {t('templates21DataPipelineStep2ConfigureColumns.back')}
          </Button>
          <Button onClick={confirm} isLoading={confirming} disabled={total === 0 || hardConflicts.length > 0}>
            {hardConflicts.length > 0 ? t('templates21DataPipelineStep2ConfigureColumns.fixConflictsFirst') : t('templates21DataPipelineStep2ConfigureColumns.confirmAndNext')}
            <ChevronRight className="w-4 h-4 ml-1" />
          </Button>
        </div>
      </div>
    </>
  );
}

// ── Tier group (header + card grid) ──────────────────────────────────────────
function TierGroup({ tier, rows, isOpen, onToggle, fields, onPick, onUpdate, onConfirm, onSkip, onUnskip, onSkipAll, conflictCols }: any) {
  const t = useT();
  const meta = tierMeta(t, tier as Tier);
  return (
    <div>
      <button onClick={onToggle} className="w-full flex items-center gap-3 mb-3 text-left">
        <span className={cn('w-2.5 h-2.5 rounded-full shrink-0', meta.dot)} />
        <div className="flex-1 min-w-0">
          <span className="text-sm font-semibold text-[var(--text-primary)]">{meta.label}</span>
          <span className="ml-2 text-sm text-[var(--text-secondary)]">({rows.length})</span>
          <p className="text-xs text-[var(--text-secondary)]">{meta.hint}</p>
        </div>
        {tier === 'empty' && (
          <span role="button" tabIndex={0}
            onClick={(e) => { e.stopPropagation(); onSkipAll(); }}
            className="text-xs px-3 py-1.5 rounded-md-custom border border-[var(--border-color)] bg-white hover:bg-[var(--bg-app)] text-[var(--text-secondary)] inline-flex items-center gap-1.5 shrink-0">
            <Trash2 className="w-3 h-3" /> {t('templates21DataPipelineStep2ConfigureColumns.skipAll')}
          </span>
        )}
        <ChevronDown className={cn('w-4 h-4 text-[var(--text-secondary)] shrink-0 transition-transform', isOpen ? '' : '-rotate-90')} />
      </button>
      {isOpen && (
        <div className="grid sm:grid-cols-2 gap-3">
          {rows.map((m: ColumnMapping) => (
            <ColumnCard key={m.detected_name} m={m} fields={fields}
              onPick={onPick} onUpdate={onUpdate} onConfirm={onConfirm}
              onSkip={onSkip} onUnskip={onUnskip}
              conflicted={conflictCols.has(m.detected_name)} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Single column card ────────────────────────────────────────────────────────
function ColumnCard({ m, fields, onPick, onUpdate, onConfirm, onSkip, onUnskip, conflicted }: any) {
  const t = useT();
  const TypeIcon = TYPE_ICON[m.type] ?? Type;
  const ai = aiBadge(t, m);
  const selectValue = m.custom ? CUSTOM : (m.canonical_name || '');

  return (
    <div className={cn(
      'rounded-lg-custom border bg-[var(--bg-card)] p-4 shadow-soft-sm flex flex-col gap-3 transition-colors',
      m.skipped ? 'opacity-50 border-[var(--border-color)]'
      : conflicted ? 'border-[var(--state-warning)]/60 ring-1 ring-[var(--state-warning)]/30'
      : m.confirmed ? 'border-[var(--state-success)]/50'
      : 'border-[var(--border-color)]',
    )}>
      {/* Header: detected name + type tag + flags */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-medium text-[var(--text-primary)] break-all leading-tight">{m.detected_name || t('templates21DataPipelineStep2ConfigureColumns.emptyPlaceholder')}</p>
          <div className="flex items-center gap-1.5 mt-1 flex-wrap">
            <span className="inline-flex items-center gap-1 text-[11px] text-[var(--text-secondary)] bg-[var(--bg-app)]/60 rounded px-1.5 py-0.5">
              <TypeIcon className="w-3 h-3" /> {t(`templates21DataPipelineStep2ConfigureColumns.${TYPE_KEY[m.type]}`)}
            </span>
            {m.is_pii && <Badge variant="current" className="text-[10px]"><Lock className="w-2.5 h-2.5 mr-0.5 inline" /> {t('templates21DataPipelineStep2ConfigureColumns.sensitive')}</Badge>}
            {m.null_pct >= 5 && (
              <span className={cn('text-[11px]', m.null_pct >= 25 ? 'text-[var(--state-error)]' : 'text-[#9E814D]')}>
                {t('templates21DataPipelineStep2ConfigureColumns.nullPct', { pct: m.null_pct.toFixed(0) })}
              </span>
            )}
          </div>
        </div>
        {!m.skipped && <AiTag ai={ai} confirmed={m.confirmed} />}
      </div>

      {/* Sample values */}
      {m.sample_values.length > 0 && (
        <p className="text-xs text-[var(--text-secondary)] truncate" title={m.sample_values.join(' | ')}>
          {t('templates21DataPipelineStep2ConfigureColumns.exampleLabel')} <span className="text-[var(--text-primary)]">{m.sample_values.slice(0, 3).join(' · ')}</span>
        </p>
      )}

      {/* "Đây là thông tin gì?" */}
      <div>
        <label className="text-[11px] text-[var(--text-secondary)] flex items-center gap-1 mb-1">
          {t('templates21DataPipelineStep2ConfigureColumns.whatIsThisLabel')}
          <HelpTip text={t('templates21DataPipelineStep2ConfigureColumns.whatIsThisHelp')} />
        </label>
        <select
          value={selectValue}
          disabled={m.skipped}
          onChange={(e) => onPick(m.detected_name, e.target.value)}
          className={cn(
            'w-full h-9 rounded-md-custom border bg-white px-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30',
            !selectValue && !m.custom ? 'border-[var(--state-error)]/50 text-[var(--state-error)]' : 'border-[var(--border-color)]',
          )}
        >
          <option value="">{t('templates21DataPipelineStep2ConfigureColumns.selectFieldPlaceholder')}</option>
          {fields.map((f: CanonicalField) => (
            <option key={f.canonical} value={f.canonical}>{f.label}</option>
          ))}
          <option value={CUSTOM}>{t('templates21DataPipelineStep2ConfigureColumns.selectFieldCustom')}</option>
        </select>
        {m.custom && (
          <input
            type="text"
            value={m.canonical_name}
            placeholder={t('templates21DataPipelineStep2ConfigureColumns.customFieldPlaceholder')}
            disabled={m.skipped}
            onChange={(e) => onUpdate(m.detected_name, { canonical_name: e.target.value, confirmed: !!e.target.value })}
            className="w-full h-9 mt-2 rounded-md-custom border border-[var(--border-color)] bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
          />
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 mt-auto pt-1">
        {m.skipped ? (
          <button onClick={() => onUnskip(m.detected_name)}
            className="text-xs inline-flex items-center gap-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
            <Undo2 className="w-3.5 h-3.5" /> {t('templates21DataPipelineStep2ConfigureColumns.restore')}
          </button>
        ) : (
          <>
            <button
              onClick={() => onConfirm(m.detected_name)}
              disabled={!m.canonical_name || m.confirmed}
              className={cn(
                'flex-1 text-xs inline-flex items-center justify-center gap-1 h-8 rounded-md-custom border transition-colors',
                m.confirmed
                  ? 'border-[var(--state-success)]/50 bg-[var(--state-success)]/10 text-[var(--state-success)] cursor-default'
                  : m.canonical_name
                    ? 'border-[var(--primary-gold)]/40 bg-[var(--primary-gold)]/8 text-[var(--primary-gold-dark)] hover:bg-[var(--primary-gold)]/15'
                    : 'border-[var(--border-color)] text-[var(--text-secondary)]/50 cursor-not-allowed',
              )}
            >
              {m.confirmed ? <><Check className="w-3.5 h-3.5" /> {t('templates21DataPipelineStep2ConfigureColumns.confirmed')}</> : <><Check className="w-3.5 h-3.5" /> {t('templates21DataPipelineStep2ConfigureColumns.confirm')}</>}
            </button>
            <button onClick={() => onSkip(m.detected_name)}
              className="text-xs inline-flex items-center gap-1 h-8 px-2.5 rounded-md-custom border border-[var(--border-color)] text-[var(--text-secondary)] hover:bg-[var(--bg-app)]">
              <X className="w-3.5 h-3.5" /> {t('templates21DataPipelineStep2ConfigureColumns.skip')}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// AI suggestion badge: 🟢 tự tin cao / 🟡 chưa chắc / 🔴 cần bạn chọn.
function aiBadge(t: (key: string, params?: Record<string, any>) => string, m: ColumnMapping): { variant: any; label: string } {
  if (m.method === 'no_match' || !m.canonical_name) return { variant: 'warning', label: t('templates21DataPipelineStep2ConfigureColumns.aiNeedsPick') };
  if (m.method === 'exact_match' && m.confidence >= 0.9 && !m.sniffed) return { variant: 'success', label: t('templates21DataPipelineStep2ConfigureColumns.aiHighConfidence') };
  if (m.sniffed) return { variant: 'info', label: t('templates21DataPipelineStep2ConfigureColumns.aiGuessedFromData') };
  if (m.confidence >= 0.6) return { variant: 'current', label: t('templates21DataPipelineStep2ConfigureColumns.aiUncertain') };
  return { variant: 'warning', label: t('templates21DataPipelineStep2ConfigureColumns.aiNeedsPick') };
}

function AiTag({ ai, confirmed }: { ai: { variant: any; label: string }; confirmed: boolean }) {
  const t = useT();
  if (confirmed) return <Badge variant="success" className="text-[10px] shrink-0"><Check className="w-2.5 h-2.5 mr-0.5 inline" /> {t('templates21DataPipelineStep2ConfigureColumns.confirmed')}</Badge>;
  return <Badge variant={ai.variant} className="text-[10px] shrink-0">{ai.label}</Badge>;
}

// ── Impact preview ────────────────────────────────────────────────────────────
function ImpactPreview({ active, fields }: { active: Set<string>; fields: CanonicalField[] }) {
  const t = useT();
  const labelFor: Record<string, string> = {};
  fields.forEach((f) => { labelFor[f.canonical] = f.label; });

  const rows = CAPABILITIES.map((cap) => {
    const needOk = cap.need.every((c) => active.has(c));
    const anyOk = !cap.any || cap.any.some((c) => active.has(c));
    const ready = needOk && anyOk;
    const missing = [
      ...cap.need.filter((c) => !active.has(c)),
      ...(!anyOk && cap.any ? [cap.any[0]] : []),
    ];
    return { ...cap, ready, missing };
  });

  return (
    <div className="rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-4 shadow-soft-sm lg:sticky lg:top-4">
      <h3 className="font-serif text-sm text-[var(--text-primary)] mb-1">{t('templates21DataPipelineStep2ConfigureColumns.impactHeading')}</h3>
      <p className="text-[11px] text-[var(--text-secondary)] mb-3">{t('templates21DataPipelineStep2ConfigureColumns.impactSubheading')}</p>
      <div className="space-y-2.5">
        {rows.map((c) => (
          <div key={c.key} className="flex items-start gap-2">
            {c.ready
              ? <CheckCircle2 className="w-4 h-4 text-[var(--state-success)] shrink-0 mt-0.5" />
              : <AlertCircle className="w-4 h-4 text-[var(--text-secondary)]/50 shrink-0 mt-0.5" />}
            <div className="min-w-0">
              <p className={cn('text-sm', c.ready ? 'text-[var(--text-primary)]' : 'text-[var(--text-secondary)]')}>{t(`templates21DataPipelineStep2ConfigureColumns.${c.key}`)}</p>
              {!c.ready && c.missing.length > 0 && (
                <p className="text-[11px] text-[var(--text-secondary)]">
                  {t('templates21DataPipelineStep2ConfigureColumns.impactNeeds', { items: c.missing.map((x) => labelFor[x] ?? x).join(' + ') })}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Lightweight hover tooltip.
function HelpTip({ text }: { text: string }) {
  return (
    <span className="relative group inline-flex">
      <HelpCircle className="w-3.5 h-3.5 text-[var(--text-secondary)] cursor-help" />
      <span className="pointer-events-none absolute left-1/2 -translate-x-1/2 top-full mt-1.5 z-20 hidden group-hover:block w-60 rounded-md-custom bg-[var(--text-primary)] text-white text-[11px] leading-relaxed normal-case font-normal px-3 py-2 shadow-soft-md">
        {text}
      </span>
    </span>
  );
}
