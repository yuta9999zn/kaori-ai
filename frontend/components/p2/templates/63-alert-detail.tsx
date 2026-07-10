// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 63. /p2/alerts/[id] — Alert Detail (F-058 🔵 Phase 2)
// ----------------------------------------------------------------------------
// Drill-down 1 cảnh báo:
//   - Header: severity + title + status badge.
//   - Body: message dài + diagnostic context (kafka offset, log line, related
//     pipeline / insight / billing item).
//   - Timeline: fired → acknowledged → resolved/snoozed với actor.
//   - Action panel: Acknowledge / Resolve / Snooze (1h/4h/24h) / Comment.
//
// Wire (Phase 2): `GET /api/v1/alerts/{id}`, `POST /alerts/{id}/{ack,resolve,snooze}`,
// `POST /alerts/{id}/comments`.
// ============================================================================

import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle, AlertCircle, Bell, ArrowLeft, MessageSquare, Send,
  CheckCircle2, Clock, Database, Cpu, CreditCard, Zap, ShieldCheck,
  ExternalLink, Loader2, ChevronDown,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, SuccessBanner, api, cn, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
// ============================================================================
// Types
// ============================================================================

type Severity = 'info' | 'warning' | 'critical';
type Status   = 'open' | 'acknowledged' | 'resolved' | 'snoozed';
type Source   = 'system' | 'data' | 'ai' | 'billing';

interface AlertEvent {
  id:       string;
  kind:     'fired' | 'acknowledged' | 'resolved' | 'snoozed' | 'comment';
  actor:    string | null;
  at:       string;
  message?: string;
}

interface AlertDetail {
  id:           string;
  title:        string;
  message:      string;
  severity:     Severity;
  status:       Status;
  source:       Source;
  fired_at:     string;
  ack_by?:      string | null;
  ack_at?:      string | null;
  related_id?:  string | null;
  related_kind?: 'pipeline' | 'insight' | 'invoice' | 'dataset';
  diagnostic_lines: string[];
  events:       AlertEvent[];
}

// ============================================================================
// Mock fixture (1 alert, fully populated)
// ============================================================================

type Translate = (key: string, params?: Record<string, string | number>) => string;

function buildMockAlert(t: Translate): AlertDetail {
  return {
    id: 'al_201',
    title: t('templates63AlertDetail.mockTitle'),
    message: t('templates63AlertDetail.mockMessage'),
    severity: 'critical',
    status: 'open',
    source: 'data',
    fired_at: '2026-04-30T14:32:00+07:00',
    related_id: 'pl_42',
    related_kind: 'pipeline',
    diagnostic_lines: [
      '[2026-04-30 14:32:01] silver/cleaning_engine.py:142 — INVALID_DATE column=ngay_thang value="30/02/2026"',
      '[2026-04-30 14:32:02] kafka.pipeline.events offset=18420 partition=4 → DLQ kaori.dlq.cleaning',
      '[2026-04-30 14:32:02] retry_count=3 max_retries=3 → fail-final',
    ],
    events: [
      { id: 'e1', kind: 'fired',        actor: null,                at: '2026-04-30T14:32:00+07:00' },
    ],
  };
}

function buildSeverityMeta(t: Translate): Record<Severity, { label: string; variant: 'info' | 'warning' | 'error'; icon: any; tone: string }> {
  return {
    info:     { label: t('templates63AlertDetail.sevInfo'),     variant: 'info',    icon: AlertCircle,    tone: 'text-[var(--state-info)]' },
    warning:  { label: t('templates63AlertDetail.sevWarning'),  variant: 'warning', icon: AlertTriangle,  tone: 'text-[var(--state-warning)]' },
    critical: { label: t('templates63AlertDetail.sevCritical'), variant: 'error',   icon: AlertTriangle,  tone: 'text-[var(--state-error)]' },
  };
}

function buildStatusMeta(t: Translate): Record<Status, { label: string; variant: 'default' | 'success' | 'warning' | 'info' | 'current' }> {
  return {
    open:         { label: t('templates63AlertDetail.statusOpen'),         variant: 'current' },
    acknowledged: { label: t('templates63AlertDetail.statusAcknowledged'), variant: 'info' },
    resolved:     { label: t('templates63AlertDetail.statusResolved'),     variant: 'success' },
    snoozed:      { label: t('templates63AlertDetail.statusSnoozed'),      variant: 'default' },
  };
}

function buildSourceMeta(t: Translate): Record<Source, { label: string; icon: any }> {
  return {
    system:  { label: t('templates63AlertDetail.srcSystem'), icon: Cpu },
    data:    { label: t('templates63AlertDetail.srcData'),   icon: Database },
    ai:      { label: t('templates63AlertDetail.srcAi'),     icon: Zap },
    billing: { label: t('templates63AlertDetail.srcBilling'), icon: CreditCard },
  };
}

const RELATED_HREF = (kind: AlertDetail['related_kind'], id: string): string => {
  if (kind === 'pipeline') return `/p2/pipelines/${id}`;
  if (kind === 'insight')  return `/p2/insights/${id}`;
  if (kind === 'invoice')  return `/p2/subscription`;
  if (kind === 'dataset')  return `/p2/data/gold`;
  return '#';
};

// ============================================================================
// Page
// ============================================================================

export default function AlertDetailPage() {
  const t = useT();
  const SEVERITY_META = useMemo(() => buildSeverityMeta(t), [t]);
  const STATUS_META   = useMemo(() => buildStatusMeta(t), [t]);
  const SOURCE_META   = useMemo(() => buildSourceMeta(t), [t]);
  const MOCK = useMemo(() => buildMockAlert(t), [t]);

  const [alert, setAlert] = useState<AlertDetail>(MOCK);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [snoozeOpen, setSnoozeOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // Phase 2: read id from URL. Template loads MOCK via fixture.
        const data = await api<AlertDetail>('/api/v1/alerts/al_201');
        if (!cancelled) setAlert(data);
      } catch (e: any) {
        if (!cancelled) setProblem(e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  function appendEvent(ev: Omit<AlertEvent, 'id' | 'at'>) {
    setAlert((prev) => ({
      ...prev,
      events: [...prev.events, { ...ev, id: `e_${Date.now()}`, at: new Date().toISOString() }],
    }));
  }

  async function onAcknowledge() {
    setSubmitting(true);
    try {
      await api(`/api/v1/alerts/${alert.id}/ack`, { method: 'POST' });
      setAlert((p) => ({ ...p, status: 'acknowledged', ack_by: 'me@workspace', ack_at: new Date().toISOString() }));
      appendEvent({ kind: 'acknowledged', actor: 'me@workspace' });
      setSuccess(t('templates63AlertDetail.successAck'));
    } catch (e: any) { setProblem(e); }
    finally { setSubmitting(false); }
  }

  async function onResolve() {
    setSubmitting(true);
    try {
      await api(`/api/v1/alerts/${alert.id}/resolve`, { method: 'POST' });
      setAlert((p) => ({ ...p, status: 'resolved' }));
      appendEvent({ kind: 'resolved', actor: 'me@workspace' });
      setSuccess(t('templates63AlertDetail.successResolve'));
    } catch (e: any) { setProblem(e); }
    finally { setSubmitting(false); }
  }

  async function onSnooze(hours: number) {
    setSubmitting(true);
    setSnoozeOpen(false);
    try {
      await api(`/api/v1/alerts/${alert.id}/snooze`, { method: 'POST', body: JSON.stringify({ hours }) });
      setAlert((p) => ({ ...p, status: 'snoozed' }));
      appendEvent({ kind: 'snoozed', actor: 'me@workspace', message: t('templates63AlertDetail.eventSnoozeMsg', { hours }) });
      setSuccess(t('templates63AlertDetail.successSnooze', { hours }));
    } catch (e: any) { setProblem(e); }
    finally { setSubmitting(false); }
  }

  async function onComment() {
    if (!comment.trim()) return;
    setSubmitting(true);
    try {
      await api(`/api/v1/alerts/${alert.id}/comments`, {
        method: 'POST',
        body: JSON.stringify({ message: comment.trim() }),
      });
      appendEvent({ kind: 'comment', actor: 'me@workspace', message: comment.trim() });
      setComment('');
    } catch (e: any) { setProblem(e); }
    finally { setSubmitting(false); }
  }

  const sev = SEVERITY_META[alert.severity];
  const SevIcon = sev.icon;
  const src = SOURCE_META[alert.source];
  const SrcIcon = src.icon;

  return (
    <>
      <PageHeader
        title={alert.title}
        description={t('templates63AlertDetail.headerDesc', {
          id: alert.id,
          date: new Date(alert.fired_at).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }),
        })}
        actions={
          <>
            <Badge variant={sev.variant}><SevIcon className="w-3 h-3 mr-1" /> {sev.label}</Badge>
            <Badge variant={STATUS_META[alert.status].variant}>{STATUS_META[alert.status].label}</Badge>
            <a href="/p2/alerts">
              <Button variant="tertiary" size="md"><ArrowLeft className="w-4 h-4 mr-2" /> {t('templates63AlertDetail.btnList')}</Button>
            </a>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1300px] mx-auto space-y-4">
        {problem && <ErrorBanner problem={problem} />}
        {success && <SuccessBanner message={success} />}

        <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-4">
          {/* Left: content */}
          <div className="space-y-4">
            {/* Message + meta */}
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 lg:p-6 shadow-soft-sm">
              <div className="flex items-start gap-3 mb-4">
                <div className={cn('w-10 h-10 rounded-md-custom flex items-center justify-center shrink-0',
                  alert.severity === 'critical' ? 'bg-[var(--state-error)]/10' :
                  alert.severity === 'warning'  ? 'bg-[var(--state-warning)]/10' :
                  'bg-[var(--state-info)]/10',
                )}>
                  <SevIcon className={cn('w-5 h-5', sev.tone)} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-[var(--text-primary)] leading-relaxed">{alert.message}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 pt-4 border-t border-[var(--border-color)]/60">
                <MetaCell label={t('templates63AlertDetail.metaSource')}>
                  <span className="inline-flex items-center gap-1 text-sm text-[var(--text-primary)]">
                    <SrcIcon className="w-3.5 h-3.5" /> {src.label}
                  </span>
                </MetaCell>
                <MetaCell label={t('templates63AlertDetail.metaFired')}>
                  <span className="text-sm text-[var(--text-primary)]">
                    {new Date(alert.fired_at).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
                  </span>
                </MetaCell>
                <MetaCell label={t('templates63AlertDetail.metaAckBy')}>
                  <span className="text-sm text-[var(--text-primary)]">{alert.ack_by ?? '—'}</span>
                </MetaCell>
                <MetaCell label={t('templates63AlertDetail.metaStatus')}>
                  <Badge variant={STATUS_META[alert.status].variant}>{STATUS_META[alert.status].label}</Badge>
                </MetaCell>
              </div>

              {alert.related_id && alert.related_kind && (
                <div className="mt-4 pt-4 border-t border-[var(--border-color)]/60">
                  <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] mb-2">{t('templates63AlertDetail.relatedLabel')}</p>
                  <a
                    href={RELATED_HREF(alert.related_kind, alert.related_id)}
                    className="inline-flex items-center gap-2 px-3 py-2 rounded-md-custom bg-[var(--bg-app)] border border-[var(--border-color)] hover:border-[var(--primary-gold)]/40 transition-colors text-sm text-[var(--text-primary)]"
                  >
                    <span className="font-mono">{alert.related_id}</span>
                    <span className="text-xs text-[var(--text-secondary)]">{alert.related_kind}</span>
                    <ExternalLink className="w-3.5 h-3.5 text-[var(--primary-gold-dark)]" />
                  </a>
                </div>
              )}
            </div>

            {/* Diagnostic */}
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
              <h3 className="font-serif text-base text-[var(--text-primary)] mb-3 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-[var(--primary-gold-dark)]" /> {t('templates63AlertDetail.diagnosticTitle')}
              </h3>
              <div className="bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom overflow-hidden">
                <pre className="px-4 py-3 text-[11px] font-mono text-[var(--text-primary)] whitespace-pre-wrap leading-relaxed">
                  {alert.diagnostic_lines.join('\n')}
                </pre>
              </div>
            </div>

            {/* Timeline */}
            <Timeline events={alert.events} />

            {/* Comment */}
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
              <h3 className="font-serif text-base text-[var(--text-primary)] mb-3 flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-[var(--primary-gold-dark)]" /> {t('templates63AlertDetail.commentTitle')}
              </h3>
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={3}
                placeholder={t('templates63AlertDetail.commentPlaceholder')}
                className="w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm placeholder:text-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all resize-none"
              />
              <div className="mt-3 flex justify-end">
                <Button variant="primary" size="sm" onClick={onComment} disabled={!comment.trim() || submitting}>
                  <Send className="w-3.5 h-3.5 mr-1.5" /> {t('templates63AlertDetail.btnPostComment')}
                </Button>
              </div>
            </div>
          </div>

          {/* Right: action panel */}
          <div className="space-y-3 xl:sticky xl:top-20 self-start">
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm space-y-3">
              <h3 className="font-serif text-sm text-[var(--text-primary)] mb-2">{t('templates63AlertDetail.actionsTitle')}</h3>

              <Button
                variant="secondary" size="md"
                onClick={onAcknowledge}
                disabled={submitting || alert.status !== 'open'}
                isLoading={submitting}
                className="w-full"
              >
                <Bell className="w-4 h-4 mr-2" /> {t('templates63AlertDetail.btnAck')}
              </Button>

              <Button
                variant="primary" size="md"
                onClick={onResolve}
                disabled={submitting || alert.status === 'resolved'}
                isLoading={submitting}
                className="w-full"
              >
                <CheckCircle2 className="w-4 h-4 mr-2" /> {t('templates63AlertDetail.btnResolve')}
              </Button>

              <div className="relative">
                <Button
                  variant="tertiary" size="md"
                  onClick={() => setSnoozeOpen(!snoozeOpen)}
                  disabled={submitting || alert.status === 'resolved'}
                  className="w-full"
                >
                  <Clock className="w-4 h-4 mr-2" /> {t('templates63AlertDetail.btnSnooze')}
                  <ChevronDown className="w-3.5 h-3.5 ml-2" />
                </Button>
                {snoozeOpen && (
                  <div className="absolute top-full left-0 right-0 mt-1 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-md-custom shadow-soft-md py-1 animate-slide-up-fade z-20">
                    {[1, 4, 24].map((h) => (
                      <button
                        key={h}
                        onClick={() => onSnooze(h)}
                        className="w-full text-left px-3 py-2 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)]"
                      >
                        {h === 24 ? t('templates63AlertDetail.snooze1Day') : t('templates63AlertDetail.snoozeHours', { h })}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
              <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
              <p>
                {t('templates63AlertDetail.noteBeforeSpan1')} <span className="font-mono">decision_audit_log</span> {t('templates63AlertDetail.noteBetweenSpans')} <span className="font-mono">notification-service</span> {t('templates63AlertDetail.noteAfterSpan2')}
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

function MetaCell({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] mb-1">{label}</p>
      <div>{children}</div>
    </div>
  );
}

function buildEventMeta(t: Translate): Record<AlertEvent['kind'], { label: string; icon: any; tone: string }> {
  return {
    fired:        { label: t('templates63AlertDetail.eventFired'),        icon: AlertTriangle,  tone: 'text-[var(--state-error)]' },
    acknowledged: { label: t('templates63AlertDetail.eventAcknowledged'), icon: Bell,            tone: 'text-[var(--state-info)]' },
    resolved:     { label: t('templates63AlertDetail.eventResolved'),     icon: CheckCircle2,   tone: 'text-[var(--state-success)]' },
    snoozed:      { label: t('templates63AlertDetail.eventSnoozed'),      icon: Clock,           tone: 'text-[var(--text-secondary)]' },
    comment:      { label: t('templates63AlertDetail.eventComment'),      icon: MessageSquare,  tone: 'text-[var(--primary-gold-dark)]' },
  };
}

function Timeline({ events }: { events: AlertEvent[] }) {
  const t = useT();
  const EVENT_META = useMemo(() => buildEventMeta(t), [t]);
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
      <h3 className="font-serif text-base text-[var(--text-primary)] mb-4 flex items-center gap-2">
        <Clock className="w-4 h-4 text-[var(--primary-gold-dark)]" /> {t('templates63AlertDetail.timelineTitle', { count: events.length })}
      </h3>
      <ol className="relative border-l-2 border-[var(--border-color)] ml-3 space-y-4">
        {events.map((ev) => {
          const meta = EVENT_META[ev.kind];
          const Icon = meta.icon;
          return (
            <li key={ev.id} className="ml-6 relative">
              <span className="absolute -left-9 top-0 w-7 h-7 rounded-full bg-[var(--bg-card)] border-2 border-[var(--border-color)] flex items-center justify-center">
                <Icon className={cn('w-3.5 h-3.5', meta.tone)} />
              </span>
              <div className="flex items-baseline justify-between gap-3">
                <p className="text-sm font-medium text-[var(--text-primary)]">
                  {meta.label}
                  {ev.actor && <span className="text-[var(--text-secondary)] font-normal"> {t('templates63AlertDetail.byActor', { actor: ev.actor })}</span>}
                </p>
                <span className="text-[11px] text-[var(--text-secondary)] shrink-0">
                  {new Date(ev.at).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
              {ev.message && <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">{ev.message}</p>}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
