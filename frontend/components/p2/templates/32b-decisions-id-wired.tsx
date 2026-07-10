'use client';

// ============================================================================
// 32b. /p2/decisions/[id] — Decision Detail + Override (F-029 + F-036 BE PR #122)
// ----------------------------------------------------------------------------
// Wires the real BE shape (services/ai-orchestrator/routers/decisions.py):
//
//   GET    /api/v1/decisions/{id}                                    → detail + overrides[]
//   POST   /api/v1/decisions/{id}/action                             → is_actioned toggle (Sprint 7 PR D)
//   POST   /api/v1/decisions/{id}/override                           → 201 + Kafka emit
//   POST   /api/v1/decisions/{id}/override/{oid}/revoke              → 200 + Kafka emit
//
// Replaces the legacy mock template (32-decisions-id.tsx) which assumed a
// richer shape (SHAP placeholder, helpful/unhelpful feedback, framework
// label, revenue_at_risk_vnd) the v0 BE doesn't carry. Those bits land
// with F-041 (SHAP) + F-074 (fine-tuning feedback) — kept in components/
// as the v1 vision reference.
// ============================================================================

import React, { useEffect, useMemo, useState } from 'react';
import {
  ChevronLeft, Gavel, ShieldCheck, AlertTriangle, CheckCircle2,
  CheckSquare, Square, Loader2, FileText, Activity,
  Sparkles, RotateCcw, Plus, X, Save, Lock,
  Brain, TrendingUp, TrendingDown, Minus, Lightbulb,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, SuccessBanner, cn,
  api, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
// ============================================================================
// Types — mirror BE Pydantic shape
// ============================================================================

interface AlternativeConsidered {
  title?:           string;
  rejected_reason?: string;
  confidence?:      number;
  // The BE column is jsonb — older rows may have a different shape; we
  // accept anything object-ish and fall back to JSON.stringify for display.
  [key: string]:    unknown;
}

interface OverrideRow {
  override_id:           string;
  decision_id:           string;
  original_chosen_value: string | null;
  override_value:        string;
  reason:                string;
  overridden_by_user:    string | null;
  overridden_at:         string | null;
  revoked_at:            string | null;
  revoked_by_user:       string | null;
  revoke_reason:         string | null;
  is_active:             boolean;
}

interface DecisionDetail {
  id:                  string;
  decision_id:         string;
  decision_type:       string;
  subject:             string;
  chosen_value:        string;
  confidence:          number | null;
  method:              string | null;
  alternatives:        AlternativeConsidered[];
  uncertainty_flags:   string[];
  reasoning:           string | null;
  needs_user_confirm:  boolean;
  run_id:              string | null;
  created_at:          string | null;
  is_actioned:         boolean;
  actioned_at:         string | null;
  overrides:           OverrideRow[];
}

interface DetailResponse { data: DecisionDetail }

// ============================================================================
// Page
// ============================================================================

export default function DecisionDetailWiredPage({ decisionId }: { decisionId: string }) {
  const t = useT();
  const [d, setD]              = useState<DecisionDetail | null>(null);
  const [loading, setLoading]  = useState(true);
  const [problem, setProblem]  = useState<ProblemDetails | null>(null);
  const [success, setSuccess]  = useState<string | null>(null);

  const [pendingAction, setPendingAction] = useState(false);
  const [overrideOpen, setOverrideOpen]   = useState(false);

  async function load() {
    setLoading(true);
    setProblem(null);
    try {
      const r = await api<DetailResponse>(`/api/v1/decisions/${decisionId}`);
      setD(r.data);
    } catch (e: any) {
      setProblem(e);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { if (decisionId) load(); /* eslint-disable-line react-hooks/exhaustive-deps */ }, [decisionId]);

  async function toggleActioned() {
    if (!d) return;
    const next = !d.is_actioned;
    setPendingAction(true);
    setProblem(null);
    try {
      await api(`/api/v1/decisions/${decisionId}/action`, {
        method: 'POST',
        body:   JSON.stringify({ is_actioned: next }),
      });
      setD({
        ...d,
        is_actioned: next,
        actioned_at: next ? new Date().toISOString() : null,
      });
      setSuccess(next
        ? t('templates32bDecisionsIdWired.msgActionedOn')
        : t('templates32bDecisionsIdWired.msgActionedOff'),
      );
    } catch (e: any) {
      setProblem(e);
    } finally {
      setPendingAction(false);
    }
  }

  async function revokeOverride(o: OverrideRow) {
    const reason = window.prompt(t('templates32bDecisionsIdWired.promptRevokeReason'), '');
    if (reason === null) return;     // cancelled
    setProblem(null);
    try {
      await api(`/api/v1/decisions/${decisionId}/override/${o.override_id}/revoke`, {
        method: 'POST',
        body:   JSON.stringify({ reason: reason.trim() || undefined }),
      });
      setSuccess(t('templates32bDecisionsIdWired.msgOverrideRevoked', { id: o.override_id.slice(0, 8) }));
      await load();
    } catch (e: any) {
      setProblem(e);
    }
  }

  async function onOverrideSaved() {
    setOverrideOpen(false);
    setSuccess(t('templates32bDecisionsIdWired.msgOverrideSaved'));
    await load();
  }

  return (
    <>
      <PageHeader
        title={d?.subject ?? t('templates32bDecisionsIdWired.pageTitleFallback')}
        description={d ? `${d.decision_type} · ${formatDateTime(d.created_at)}` : t('templates32bDecisionsIdWired.pageLoading')}
        actions={
          <Button variant="tertiary" onClick={() => (window.location.href = '/decisions')}>
            <ChevronLeft className="w-4 h-4 mr-1" /> {t('templates32bDecisionsIdWired.backToList')}
          </Button>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-5">
        {problem && (
          <ErrorBanner
            problem={{
              ...problem,
              title:  problem.title ?? t('templates32bDecisionsIdWired.errLoadTitle'),
              detail: problem.detail ?? '',
            }}
          />
        )}
        {success && <SuccessBanner message={success} />}

        {loading && !d ? (
          <SkeletonState />
        ) : !d ? null : (
          <>
            <HeaderCard
              decision={d}
              pendingAction={pendingAction}
              onToggleActioned={toggleActioned}
            />

            {d.reasoning && (
              <Section icon={FileText} title={t('templates32bDecisionsIdWired.reasoningTitle')}>
                <p className="text-sm text-[var(--text-primary)] leading-relaxed whitespace-pre-line">
                  {d.reasoning}
                </p>
              </Section>
            )}

            <ExplainabilitySection decisionId={decisionId} />

            <AlternativesSection alternatives={d.alternatives} />

            <OverrideSection
              overrides={d.overrides}
              onCreate={() => setOverrideOpen(true)}
              onRevoke={revokeOverride}
            />

            <AuditSection decision={d} />
          </>
        )}
      </div>

      {overrideOpen && d && (
        <OverrideEditor
          decisionId={decisionId}
          originalValue={d.chosen_value}
          onClose={() => setOverrideOpen(false)}
          onSaved={onOverrideSaved}
        />
      )}
    </>
  );
}

// ============================================================================
// Header card — KPIs + is_actioned toggle
// ============================================================================

function HeaderCard({
  decision: d, pendingAction, onToggleActioned,
}: {
  decision: DecisionDetail;
  pendingAction: boolean;
  onToggleActioned: () => void;
}) {
  const t = useT();
  const hasActiveOverride = d.overrides.some((o) => o.is_active);
  const activeOverride = d.overrides.find((o) => o.is_active);

  return (
    <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm">
      <div className="flex items-start gap-4 flex-wrap">
        <div className="w-12 h-12 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center shrink-0">
          <Gavel className="w-5 h-5 text-[var(--primary-gold-dark)]" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <Badge variant="current">{d.decision_type}</Badge>
            {d.method && <Badge variant="default">{d.method}</Badge>}
            {d.needs_user_confirm && (
              <Badge variant="warning">
                <AlertTriangle className="w-3 h-3 mr-1 inline" /> {t('templates32bDecisionsIdWired.badgeNeedsConfirm')}
              </Badge>
            )}
            {d.is_actioned && (
              <Badge variant="success">
                <CheckCircle2 className="w-3 h-3 mr-1 inline" /> {t('templates32bDecisionsIdWired.badgeActioned')}
              </Badge>
            )}
            {hasActiveOverride && (
              <Badge variant="error">
                <RotateCcw className="w-3 h-3 mr-1 inline" /> {t('templates32bDecisionsIdWired.badgeOverridden')}
              </Badge>
            )}
          </div>
          <h2 className="font-serif text-xl text-[var(--text-primary)]">{d.subject}</h2>
          {hasActiveOverride && activeOverride ? (
            <p className="text-sm text-[var(--text-secondary)] mt-1 leading-relaxed">
              <span className="line-through">{d.chosen_value}</span>
              {' → '}
              <span className="font-medium text-[var(--text-primary)]">{activeOverride.override_value}</span>
            </p>
          ) : (
            <p className="text-sm text-[var(--text-secondary)] mt-1 leading-relaxed">
              {t('templates32bDecisionsIdWired.aiChosePrefix')} <span className="font-medium text-[var(--text-primary)]">{d.chosen_value}</span>
            </p>
          )}
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
        <KpiTile
          label={t('templates32bDecisionsIdWired.kpiConfidenceLabel')}
          value={d.confidence != null ? `${Math.round((d.confidence ?? 0) * 100)}%` : '—'}
          secondary={
            d.confidence == null ? undefined :
            d.confidence >= 0.8 ? t('templates32bDecisionsIdWired.confidenceHigh') :
            d.confidence >= 0.6 ? t('templates32bDecisionsIdWired.confidenceMedium') : t('templates32bDecisionsIdWired.confidenceLow')
          }
        />
        <KpiTile
          label={t('templates32bDecisionsIdWired.kpiUncertaintyLabel')}
          value={d.uncertainty_flags.length > 0 ? d.uncertainty_flags.join(' · ') : '—'}
          highlight={d.uncertainty_flags.length > 0}
        />
        <div className="rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)]/40 p-3">
          <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">{t('templates32bDecisionsIdWired.kpiActionStatusLabel')}</p>
          <button
            type="button"
            onClick={onToggleActioned}
            disabled={pendingAction}
            className={cn(
              'mt-2 w-full inline-flex items-center justify-center gap-2 px-3 py-2 rounded-md-custom border text-sm font-medium transition-colors',
              d.is_actioned
                ? 'border-[var(--state-success)]/40 bg-[var(--state-success)]/10 text-[#5C856A] hover:bg-[var(--state-success)]/15'
                : 'border-[var(--primary-gold)]/40 bg-[var(--primary-gold)]/10 text-[var(--primary-gold-dark)] hover:bg-[var(--primary-gold)]/15',
              pendingAction && 'opacity-60 cursor-not-allowed',
            )}
          >
            {pendingAction
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : d.is_actioned ? <CheckSquare className="w-4 h-4" /> : <Square className="w-4 h-4" />}
            {d.is_actioned ? t('templates32bDecisionsIdWired.actionUnmark') : t('templates32bDecisionsIdWired.actionMark')}
          </button>
          {d.is_actioned && d.actioned_at && (
            <p className="text-[11px] text-[var(--text-secondary)] mt-1.5 text-center">
              {formatRelative(d.actioned_at)}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Alternatives — accept any-shape jsonb gracefully
// ============================================================================

function AlternativesSection({ alternatives }: { alternatives: AlternativeConsidered[] }) {
  const t = useT();
  return (
    <Section
      icon={Activity}
      title={t('templates32bDecisionsIdWired.altSectionTitle')}
      subtitle={t('templates32bDecisionsIdWired.altSectionSubtitle', { count: alternatives.length })}
    >
      {alternatives.length === 0 ? (
        <p className="text-sm text-[var(--text-secondary)]">{t('templates32bDecisionsIdWired.altNone')}</p>
      ) : (
        <div className="space-y-3">
          {alternatives.map((alt, i) => (
            <div
              key={i}
              className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-app)]/30 p-3"
            >
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <p className="font-medium text-sm text-[var(--text-primary)]">
                  {String(alt.title ?? alt.value ?? t('templates32bDecisionsIdWired.altFallbackTitle', { n: i + 1 }))}
                </p>
                {typeof alt.confidence === 'number' && (
                  <Badge variant="default">
                    {t('templates32bDecisionsIdWired.altConfidenceBadge', { pct: Math.round(alt.confidence * 100) })}
                  </Badge>
                )}
              </div>
              {alt.rejected_reason && (
                <p className="text-xs text-[var(--text-secondary)] mt-1.5 leading-relaxed">
                  <span className="font-medium text-[var(--text-primary)]">{t('templates32bDecisionsIdWired.altRejectedLabel')}</span> {String(alt.rejected_reason)}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </Section>
  );
}

// ============================================================================
// Overrides — history list + create button
// ============================================================================

function OverrideSection({
  overrides, onCreate, onRevoke,
}: {
  overrides: OverrideRow[];
  onCreate: () => void;
  onRevoke: (o: OverrideRow) => void;
}) {
  const t = useT();
  const sorted = useMemo(
    () => [...overrides].sort((a, b) =>
      (b.overridden_at ?? '').localeCompare(a.overridden_at ?? '')),
    [overrides],
  );

  return (
    <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
      <div className="px-5 py-3 border-b border-[var(--border-color)]/60 bg-[var(--primary-gold)]/4 flex items-center gap-3">
        <Sparkles className="w-4 h-4 text-[var(--primary-gold-dark)]" />
        <div className="flex-1 min-w-0">
          <h3 className="font-serif text-base text-[var(--text-primary)]">{t('templates32bDecisionsIdWired.overrideSectionTitle')}</h3>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            {t('templates32bDecisionsIdWired.overrideSectionDescPre')} <span className="font-mono">kaori.feedback.actions</span> {t('templates32bDecisionsIdWired.overrideSectionDescPost')}
          </p>
        </div>
        <Button variant="primary" size="sm" onClick={onCreate}>
          <Plus className="w-4 h-4 mr-1.5" /> {t('templates32bDecisionsIdWired.overrideNewBtn')}
        </Button>
      </div>

      {sorted.length === 0 ? (
        <div className="p-5 text-center">
          <Sparkles className="w-8 h-8 mx-auto text-[var(--text-secondary)]/30 mb-2" />
          <p className="text-sm text-[var(--text-secondary)]">
            {t('templates32bDecisionsIdWired.overrideEmpty')}
          </p>
        </div>
      ) : (
        <ul className="divide-y divide-[var(--border-color)]/60">
          {sorted.map((o) => (
            <OverrideRowItem key={o.override_id} row={o} onRevoke={() => onRevoke(o)} />
          ))}
        </ul>
      )}
    </div>
  );
}

function OverrideRowItem({
  row: o, onRevoke,
}: { row: OverrideRow; onRevoke: () => void }) {
  const t = useT();
  return (
    <li className="px-5 py-4 hover:bg-[var(--bg-app)]/40 transition-colors">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            {o.is_active ? (
              <Badge variant="success">{t('templates32bDecisionsIdWired.overrideActive')}</Badge>
            ) : (
              <Badge variant="default">{t('templates32bDecisionsIdWired.overrideRevoked')}</Badge>
            )}
            <span className="text-xs text-[var(--text-secondary)]">
              {formatRelative(o.overridden_at)} · {o.overridden_by_user?.slice(0, 8) ?? 'system'}…
            </span>
          </div>
          <p className="text-sm text-[var(--text-primary)] mt-1.5">
            <span className="font-mono text-[var(--text-secondary)] line-through">
              {o.original_chosen_value ?? '?'}
            </span>
            {' → '}
            <span className="font-mono font-medium">{o.override_value}</span>
          </p>
          <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">
            <span className="font-medium text-[var(--text-primary)]">{t('templates32bDecisionsIdWired.reasonLabel')}</span> {o.reason}
          </p>
          {!o.is_active && o.revoke_reason && (
            <p className="text-xs text-[var(--text-secondary)] mt-1 italic">
              <span className="font-medium text-[var(--text-primary)]">{t('templates32bDecisionsIdWired.revokeLabel')}</span> {o.revoke_reason}
            </p>
          )}
        </div>
        {o.is_active && (
          <Button variant="tertiary" size="sm" onClick={onRevoke}>
            <RotateCcw className="w-3.5 h-3.5 mr-1" /> {t('templates32bDecisionsIdWired.revokeBtn')}
          </Button>
        )}
      </div>
    </li>
  );
}

// ============================================================================
// Override editor modal
// ============================================================================

function OverrideEditor({
  decisionId, originalValue, onClose, onSaved,
}: {
  decisionId: string;
  originalValue: string;
  onClose: () => void;
  onSaved: () => void | Promise<void>;
}) {
  const t = useT();
  const [overrideValue, setOverrideValue] = useState('');
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  const valid = overrideValue.trim().length > 0
             && overrideValue.trim().length <= 500
             && reason.trim().length > 0
             && reason.trim().length <= 2000;

  async function submit() {
    if (!valid) return;
    setSubmitting(true);
    setProblem(null);
    try {
      await api(`/api/v1/decisions/${decisionId}/override`, {
        method: 'POST',
        body: JSON.stringify({
          override_value: overrideValue.trim(),
          reason:         reason.trim(),
        }),
      });
      await onSaved();
    } catch (e: any) {
      setProblem(e);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-40 bg-[var(--text-primary)]/40 flex items-center justify-center p-4">
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-lg max-w-lg w-full max-h-[90vh] overflow-auto">
        <div className="px-6 py-4 border-b border-[var(--border-color)] flex items-center justify-between">
          <h2 className="font-serif text-xl text-[var(--text-primary)]">{t('templates32bDecisionsIdWired.editorTitle')}</h2>
          <button
            onClick={onClose}
            className="p-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)] rounded-sm-custom"
            aria-label={t('templates32bDecisionsIdWired.closeAriaLabel')}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-6 py-5 space-y-4">
          {problem && (
            <ErrorBanner
              problem={{
                ...problem,
                title:  problem.title ?? t('templates32bDecisionsIdWired.errSaveTitle'),
                detail: problem.detail ?? '',
              }}
            />
          )}

          <div className="rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)]/40 p-3">
            <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] mb-1">{t('templates32bDecisionsIdWired.aiCurrentChoiceLabel')}</p>
            <p className="font-mono text-sm text-[var(--text-primary)]">{originalValue}</p>
          </div>

          <label className="block">
            <span className="text-[11px] uppercase tracking-wider font-medium text-[var(--text-secondary)] mb-1.5 block">
              {t('templates32bDecisionsIdWired.correctValueLabel')}
            </span>
            <input
              type="text"
              value={overrideValue}
              onChange={(e) => setOverrideValue(e.target.value.slice(0, 500))}
              maxLength={500}
              placeholder={t('templates32bDecisionsIdWired.correctValuePlaceholder')}
              className="w-full px-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-sm placeholder:text-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all"
            />
          </label>

          <label className="block">
            <span className="text-[11px] uppercase tracking-wider font-medium text-[var(--text-secondary)] mb-1.5 block">
              {t('templates32bDecisionsIdWired.disagreeReasonLabel')}
            </span>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value.slice(0, 2000))}
              rows={4}
              maxLength={2000}
              placeholder={t('templates32bDecisionsIdWired.disagreeReasonPlaceholder')}
              className="w-full px-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-sm placeholder:text-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] resize-none transition-all"
            />
            <p className="text-xs text-[var(--text-secondary)] mt-1">
              {t('templates32bDecisionsIdWired.reasonCharCount', { count: reason.length })}
            </p>
          </label>

          <div className="rounded-md-custom bg-[var(--primary-gold)]/8 border border-[var(--primary-gold)]/30 p-3 text-xs text-[var(--text-primary)] flex items-start gap-2">
            <Sparkles className="w-3.5 h-3.5 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
            <p>
              {t('templates32bDecisionsIdWired.editorNoticePre')} <span className="font-mono">decision_overrides</span> {t('templates32bDecisionsIdWired.editorNoticeMid')} <span className="font-mono">kaori.feedback.actions</span>{t('templates32bDecisionsIdWired.editorNoticePost')}
            </p>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-[var(--border-color)] flex items-center justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={submitting}>{t('templates32bDecisionsIdWired.cancelBtn')}</Button>
          <Button variant="primary" onClick={submit} disabled={!valid || submitting}>
            {submitting
              ? <><Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> {t('templates32bDecisionsIdWired.savingBtn')}</>
              : <><Save className="w-4 h-4 mr-1.5" /> {t('templates32bDecisionsIdWired.saveOverrideBtn')}</>}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Audit info
// ============================================================================

function AuditSection({ decision: d }: { decision: DecisionDetail }) {
  const t = useT();
  return (
    <Section icon={ShieldCheck} title={t('templates32bDecisionsIdWired.auditSectionTitle')}>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
        <AuditField label="decision_id" value={d.decision_id} mono />
        {d.run_id && <AuditField label="run_id" value={d.run_id} mono />}
        <AuditField label="method" value={d.method ?? '—'} mono />
        <AuditField label="created_at" value={formatDateTime(d.created_at)} />
      </div>
      <p className="text-xs text-[var(--text-secondary)] mt-3 flex items-start gap-1.5">
        <Lock className="w-3.5 h-3.5 mt-0.5 shrink-0" />
        <span>
          {t('templates32bDecisionsIdWired.auditNoticePre')}{' '}
          <span className="font-mono">decision_overrides</span> {t('templates32bDecisionsIdWired.auditNoticePost')}
        </span>
      </p>
    </Section>
  );
}

// ============================================================================
// Shared
// ============================================================================

function Section({
  icon: Icon, title, subtitle, children,
}: { icon: any; title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
      <div className="px-5 py-3 border-b border-[var(--border-color)]/60 flex items-center gap-3 bg-[var(--bg-app)]/40">
        <Icon className="w-4 h-4 text-[var(--primary-gold-dark)]" />
        <div className="flex-1 min-w-0">
          <h3 className="font-serif text-base text-[var(--text-primary)]">{title}</h3>
          {subtitle && <p className="text-xs text-[var(--text-secondary)] mt-0.5">{subtitle}</p>}
        </div>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

function KpiTile({
  label, value, secondary, highlight,
}: { label: string; value: string; secondary?: string; highlight?: boolean }) {
  return (
    <div className={cn(
      'rounded-md-custom p-3 border',
      highlight
        ? 'bg-[var(--primary-gold)]/8 border-[var(--primary-gold)]/30'
        : 'bg-[var(--bg-app)]/40 border-[var(--border-color)]/40',
    )}>
      <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">{label}</p>
      <p className="font-serif text-lg text-[var(--text-primary)] mt-1">{value}</p>
      {secondary && <p className="text-xs text-[var(--text-secondary)] mt-0.5">{secondary}</p>}
    </div>
  );
}

function AuditField({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)]/40 p-3">
      <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">{label}</p>
      <p className={cn('mt-1 break-all text-[var(--text-primary)]', mono ? 'font-mono text-xs' : 'text-sm')}>
        {value}
      </p>
    </div>
  );
}

function SkeletonState() {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="h-32 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse"
        />
      ))}
    </div>
  );
}

function formatDateTime(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('vi-VN', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
}

function formatRelative(iso: string | null): string {
  if (!iso) return '—';
  const diff = Date.now() - +new Date(iso);
  if (Number.isNaN(diff)) return iso;
  if (diff < 60_000)         return 'vừa xong';
  if (diff < 3_600_000)      return `${Math.round(diff / 60_000)} phút trước`;
  if (diff < 86_400_000)     return `${Math.round(diff / 3_600_000)} giờ trước`;
  if (diff < 7 * 86_400_000) return `${Math.round(diff / 86_400_000)} ngày trước`;
  return new Date(iso).toLocaleDateString('vi-VN');
}

// ============================================================================
// F-041 — Explainability section (lazy POST + render)
// ============================================================================

interface ExplainTopFactor {
  factor_name: string;
  direction:   'positive' | 'negative' | 'neutral';
  weight:      number;
  evidence:    string;
}

interface ExplainResp {
  decision_id:            string;
  top_factors:            ExplainTopFactor[];
  narrative:              string;
  confidence_explanation: string;
}

function ExplainabilitySection({ decisionId }: { decisionId: string }) {
  const t = useT();
  const [data, setData]       = useState<ExplainResp | null>(null);
  const [loading, setLoading] = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  async function generate() {
    setLoading(true);
    setProblem(null);
    try {
      const r = await api<ExplainResp>('/api/v1/explainability/explain', {
        method: 'POST',
        body: JSON.stringify({ decision_id: decisionId, consent_external: false }),
      });
      setData(r);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm">
      <div className="flex items-center justify-between mb-3 gap-3">
        <div className="flex items-center gap-2">
          <Brain className="w-4 h-4 text-[var(--primary-gold-dark)]" />
          <h3 className="font-serif text-sm text-[var(--text-primary)]">{t('templates32bDecisionsIdWired.explainTitle')}</h3>
          <Badge variant="info">F-041</Badge>
        </div>
        {!data && (
          <Button onClick={generate} disabled={loading} isLoading={loading} size="sm">
            <Sparkles className="w-3.5 h-3.5 mr-1" />
            {loading ? t('templates32bDecisionsIdWired.explainGenerating') : t('templates32bDecisionsIdWired.explainGenerateBtn')}
          </Button>
        )}
        {data && (
          <Button onClick={generate} disabled={loading} isLoading={loading} variant="tertiary" size="sm">
            <RotateCcw className="w-3.5 h-3.5 mr-1" />
            {t('templates32bDecisionsIdWired.explainRegenerateBtn')}
          </Button>
        )}
      </div>

      {problem && <ErrorBanner problem={problem} />}

      {!data && !problem && !loading && (
        <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
          {t('templates32bDecisionsIdWired.explainIntroPre')}
          <br />
          <span className="font-mono text-[10px]">{t('templates32bDecisionsIdWired.explainIntroNote')}</span>
        </p>
      )}

      {data && (
        <div className="space-y-4">
          <p className="text-sm text-[var(--text-primary)] leading-relaxed">{data.narrative}</p>

          <div className="space-y-2">
            <p className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)] font-medium">{t('templates32bDecisionsIdWired.explainTopFactorsLabel')}</p>
            {data.top_factors.map((f, i) => (
              <ExplainFactorRow key={i} factor={f} />
            ))}
          </div>

          <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
            <Lightbulb className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
            <p><span className="font-medium text-[var(--text-primary)]">{t('templates32bDecisionsIdWired.explainConfidenceLabel')} </span>{data.confidence_explanation}</p>
          </div>
        </div>
      )}
    </div>
  );
}

function ExplainFactorRow({ factor }: { factor: ExplainTopFactor }) {
  const t = useT();
  const Icon = factor.direction === 'positive' ? TrendingUp
    : factor.direction === 'negative' ? TrendingDown
    : Minus;
  const tone = factor.direction === 'positive' ? 'text-[var(--state-success)]'
    : factor.direction === 'negative' ? 'text-[var(--state-error)]'
    : 'text-[var(--text-secondary)]';
  const weightPct = Math.round(factor.weight * 100);
  return (
    <div className="flex items-start gap-3 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)]/60">
      <Icon className={cn('w-4 h-4 shrink-0 mt-0.5', tone)} />
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline justify-between gap-2 flex-wrap">
          <p className="text-sm font-medium text-[var(--text-primary)]">{factor.factor_name}</p>
          <span className="text-[10px] font-mono text-[var(--text-secondary)]">{t('templates32bDecisionsIdWired.explainFactorWeight', { pct: weightPct })}</span>
        </div>
        <p className="text-xs text-[var(--text-secondary)] mt-1 leading-snug">{factor.evidence}</p>
        <div className="mt-1.5 h-1 w-full rounded-full bg-[var(--border-color)]/40 overflow-hidden">
          <div
            className={cn('h-full rounded-full',
              factor.direction === 'positive' ? 'bg-[var(--state-success)]'
              : factor.direction === 'negative' ? 'bg-[var(--state-error)]'
              : 'bg-[var(--text-secondary)]/60',
            )}
            style={{ width: `${weightPct}%` }}
          />
        </div>
      </div>
    </div>
  );
}
