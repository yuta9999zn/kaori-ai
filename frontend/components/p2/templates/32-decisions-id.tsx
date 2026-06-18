// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 32. /p2/decisions/:id — Decision Detail (F-029 + F-036 🔵 Phase 2 SHAP)
// ----------------------------------------------------------------------------
// GET   /api/v1/decisions/:id
// POST  /api/v1/decisions/:id/action  (UPSERT decision_actions, Sprint 7 PR D)
// POST  /api/v1/decisions/:id/feedback (F-036 — Phase 2 retrain trigger)
//
// Phase 1 ships:
//   - Full audit panel (K-6): confidence, alternatives_considered, prompt_hash,
//     llm_provider, decision_audit_log row pointer
//   - is_actioned manual toggle (Sprint 7 PR D, North Star side table)
//   - Linkage to insight + pipeline + audit log
//
// Phase 2 (F-036) placeholder cards visible but disabled:
//   - SHAP explanation panel (per-feature attribution)
//   - User override / counter-decision flow
//   - Feedback → retrain queue
// ============================================================================

import React, { useState, useEffect } from 'react';
import { usePathname } from 'next/navigation';
import {
  ChevronLeft, Gavel, ShieldCheck, AlertTriangle, CheckCircle2,
  CheckSquare, Square, Loader2, FileText, Activity, Lightbulb,
  Sparkles, ThumbsUp, ThumbsDown, Lock, Database, Clock, Globe,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, SuccessBanner, cn,
  api, formatVND,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
type Framework = 'NONE' | 'SWOT' | '6W' | '2H' | 'Fishbone' | 'MoM' | 'YoY';
type RiskLabel = 'HIGH' | 'MEDIUM' | 'LOW';

interface AlternativeConsidered {
  title:           string;
  rejected_reason: string;
  confidence:      number;
}

interface Decision {
  id:                       string;
  title:                    string;
  summary:                  string;
  long_recommendation:      string;
  framework:                Framework;
  confidence:               number;
  churn_risk_label?:        RiskLabel;
  revenue_at_risk_vnd:      number;

  alternatives_considered:  AlternativeConsidered[];
  audit_log_id:             string;
  prompt_hash:              string;
  llm_provider:             'qwen-2.5-internal' | 'claude-sonnet' | 'gpt-4o';
  consent_external_at_dispatch: boolean;

  insight_id?:              string;
  insight_title?:           string;
  pipeline_id?:             string;

  is_actioned:              boolean;
  actioned_at?:             string;
  actioned_by?:             string;

  created_at:               string;
}

const FRAMEWORK_LABEL: Record<Framework, string> = {
  NONE:     'Tự do',
  SWOT:     'SWOT',
  '6W':     '6W',
  '2H':     '2H',
  Fishbone: 'Fishbone',
  MoM:      'MoM',
  YoY:      'YoY',
};

const RISK_BADGE: Record<RiskLabel, { variant: any; label: string }> = {
  HIGH:   { variant: 'error',   label: 'Churn cao' },
  MEDIUM: { variant: 'warning', label: 'Churn vừa' },
  LOW:    { variant: 'default', label: 'Churn thấp' },
};

const PROVIDER_BADGE: Record<Decision['llm_provider'], { variant: any; label: string; icon: any }> = {
  'qwen-2.5-internal': { variant: 'success', label: 'Qwen 2.5 nội bộ', icon: Lock },
  'claude-sonnet':     { variant: 'warning', label: 'Claude Sonnet',  icon: Globe },
  'gpt-4o':            { variant: 'warning', label: 'GPT-4o',          icon: Globe },
};

export default function DecisionDetailPage() {
  // usePathname() works in SSR + client; reading `window.location.pathname`
  // at component body crashes Next prerender with "window is not defined".
  const pathname   = usePathname() ?? '';
  const decisionId = pathname.split('/').filter(Boolean).pop() ?? '';

  const [d,        setD]        = useState<Decision | null>(null);
  const [loading,  setLoading]  = useState(true);
  const [problem,  setProblem]  = useState<ProblemDetails | null>(null);
  const [success,  setSuccess]  = useState<string | null>(null);

  const [pendingAction, setPendingAction]   = useState(false);
  const [feedbackSent,  setFeedbackSent]    = useState<'helpful' | 'unhelpful' | null>(null);

  async function load() {
    setLoading(true);
    setProblem(null);
    try {
      const data = await api<Decision>(`/api/v1/decisions/${decisionId}`);
      setD(data);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { if (decisionId) load(); }, [decisionId]);

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
      setD({ ...d, is_actioned: next, actioned_at: next ? new Date().toISOString() : undefined });
      setSuccess(next ? 'Đã đánh dấu đã hành động — tính vào North Star' : 'Đã bỏ đánh dấu');
    } catch (err: any) {
      setProblem(err);
    } finally {
      setPendingAction(false);
    }
  }

  async function sendFeedback(kind: 'helpful' | 'unhelpful') {
    if (!d) return;
    try {
      await api(`/api/v1/decisions/${decisionId}/feedback`, {
        method: 'POST',
        body:   JSON.stringify({ kind }),
      });
      setFeedbackSent(kind);
      setSuccess('Cảm ơn bạn — feedback sẽ vào hàng đợi retrain (F-036, Phase 2)');
    } catch (err: any) {
      setProblem(err);
    }
  }

  return (
    <>
      <PageHeader
        title={d?.title ?? 'Quyết định'}
        description={d ? `Tạo lúc ${d.created_at} · ${FRAMEWORK_LABEL[d.framework]}` : 'Đang tải...'}
        actions={
          <Button variant="tertiary" onClick={() => (window.location.href = '/p2/decisions')}>
            <ChevronLeft className="w-4 h-4 mr-1" />
            Quay lại
          </Button>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-5">
        <ErrorBanner problem={problem} />
        {success && <SuccessBanner message={success} />}

        {loading && !d ? (
          <div className="space-y-4">
            {[1,2,3].map((i) => (
              <div key={i} className="h-40 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse" />
            ))}
          </div>
        ) : d ? (
          <>
            {/* Header strip with North Star toggle */}
            <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm">
              <div className="flex items-start gap-4 flex-wrap">
                <div className="w-12 h-12 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center shrink-0">
                  <Gavel className="w-5 h-5 text-[var(--primary-gold-dark)]" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2 mb-2">
                    <Badge variant="current">{FRAMEWORK_LABEL[d.framework]}</Badge>
                    {d.churn_risk_label && (
                      <Badge variant={RISK_BADGE[d.churn_risk_label].variant}>
                        {RISK_BADGE[d.churn_risk_label].label}
                      </Badge>
                    )}
                    <Badge variant={PROVIDER_BADGE[d.llm_provider].variant}>
                      {React.createElement(PROVIDER_BADGE[d.llm_provider].icon, { className: 'w-3 h-3 mr-1 inline' })}
                      {PROVIDER_BADGE[d.llm_provider].label}
                    </Badge>
                    {d.is_actioned && (
                      <Badge variant="success">
                        <CheckCircle2 className="w-3 h-3 mr-1 inline" />
                        Đã hành động
                      </Badge>
                    )}
                  </div>
                  <h2 className="font-serif text-xl text-[var(--text-primary)]">{d.title}</h2>
                  <p className="text-sm text-[var(--text-secondary)] mt-1 leading-relaxed">{d.summary}</p>
                </div>
              </div>

              <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
                <KpiTile label="Độ tin cậy AI" value={`${Math.round(d.confidence * 100)}%`} secondary={d.confidence >= 0.8 ? 'Cao' : d.confidence >= 0.6 ? 'Vừa' : 'Thấp'} />
                <KpiTile
                  label="Doanh thu rủi ro"
                  value={d.revenue_at_risk_vnd > 0 ? formatVND(d.revenue_at_risk_vnd) : '—'}
                  secondary={d.revenue_at_risk_vnd > 0 ? 'Đóng góp North Star khi đã hành động' : undefined}
                  highlight={d.revenue_at_risk_vnd > 0}
                />
                <div className="rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)]/40 p-3">
                  <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">Trạng thái hành động</p>
                  <button
                    type="button"
                    onClick={toggleActioned}
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
                    {d.is_actioned ? 'Bỏ đánh dấu' : 'Đánh dấu đã hành động'}
                  </button>
                  {d.is_actioned && d.actioned_at && (
                    <p className="text-[11px] text-[var(--text-secondary)] mt-1.5 text-center">
                      {d.actioned_by ?? 'Bạn'} · {d.actioned_at}
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* Recommendation */}
            <Section icon={Lightbulb} title="Khuyến nghị chi tiết">
              <p className="text-sm text-[var(--text-primary)] leading-relaxed whitespace-pre-line">{d.long_recommendation}</p>
            </Section>

            {/* Alternatives considered (K-6) */}
            <Section
              icon={Activity}
              title="Phương án đã cân nhắc"
              subtitle={`${d.alternatives_considered.length} phương án bị từ chối · audit log K-6`}
            >
              {d.alternatives_considered.length === 0 ? (
                <p className="text-sm text-[var(--text-secondary)]">Không có phương án thay thế ghi nhận.</p>
              ) : (
                <div className="space-y-3">
                  {d.alternatives_considered.map((alt, i) => (
                    <div key={i} className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-app)]/30 p-3">
                      <div className="flex items-start justify-between gap-3 flex-wrap">
                        <p className="font-medium text-sm text-[var(--text-primary)]">{alt.title}</p>
                        <Badge variant="default">Confidence {(alt.confidence * 100).toFixed(0)}%</Badge>
                      </div>
                      <p className="text-xs text-[var(--text-secondary)] mt-1.5 leading-relaxed">
                        <span className="font-medium text-[var(--text-primary)]">Bị từ chối:</span> {alt.rejected_reason}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </Section>

            {/* Audit panel (K-6) */}
            <Section icon={ShieldCheck} title="Audit log (K-6)">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                <AuditField label="audit_log_id" value={d.audit_log_id} mono />
                <AuditField label="prompt_hash" value={d.prompt_hash} mono />
                <AuditField label="llm_provider" value={d.llm_provider} mono />
                <AuditField
                  label="consent_external_at_dispatch"
                  value={d.consent_external_at_dispatch ? 'true' : 'false'}
                  mono
                />
              </div>
              <a
                href={`/api/v1/audit/${d.audit_log_id}`}
                className="mt-3 inline-flex items-center text-xs font-medium text-[var(--primary-gold-dark)] hover:underline"
              >
                <FileText className="w-3.5 h-3.5 mr-1" />
                Xem raw audit log
              </a>
            </Section>

            {/* Linkage */}
            <Section icon={Database} title="Nguồn gốc">
              <ul className="space-y-1.5 text-sm">
                {d.insight_id && (
                  <li className="flex items-center gap-2">
                    <Lightbulb className="w-4 h-4 text-[var(--text-secondary)]" />
                    Insight nguồn:
                    <a href={`/p2/insights/${d.insight_id}`} className="text-[var(--primary-gold-dark)] hover:underline">
                      {d.insight_title ?? d.insight_id}
                    </a>
                  </li>
                )}
                {d.pipeline_id && (
                  <li className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-[var(--text-secondary)]" />
                    Pipeline:
                    <a href={`/p2/pipelines/${d.pipeline_id}`} className="text-[var(--primary-gold-dark)] hover:underline">
                      {d.pipeline_id}
                    </a>
                  </li>
                )}
                <li className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                  <Clock className="w-3.5 h-3.5" />
                  {d.created_at}
                </li>
              </ul>
            </Section>

            {/* Phase 2 — SHAP + override (disabled placeholder) */}
            <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden opacity-80">
              <div className="px-5 py-3 border-b border-[var(--border-color)]/60 bg-[var(--primary-gold)]/4 flex items-center gap-3">
                <Sparkles className="w-4 h-4 text-[var(--primary-gold-dark)]" />
                <div className="flex-1">
                  <h3 className="font-serif text-base text-[var(--text-primary)]">SHAP + Override</h3>
                  <p className="text-xs text-[var(--text-secondary)] mt-0.5">F-036 · Phase 2 — sẽ giải thích AI ra quyết định bằng feature attribution</p>
                </div>
                <Badge variant="info">Sắp ra mắt</Badge>
              </div>
              <div className="p-5 grid grid-cols-1 sm:grid-cols-3 gap-3">
                {['Feature 1', 'Feature 2', 'Feature 3'].map((f) => (
                  <div key={f} className="rounded-md-custom border border-dashed border-[var(--border-color)] bg-[var(--bg-app)]/30 p-3 h-24 flex flex-col items-center justify-center text-[var(--text-secondary)]">
                    <Lock className="w-4 h-4 mb-1" />
                    <span className="text-xs">{f}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Feedback bar */}
            <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-4 shadow-soft-sm flex items-center justify-between gap-3 flex-wrap">
              <div>
                <p className="font-serif text-base text-[var(--text-primary)]">Khuyến nghị này có hữu ích không?</p>
                <p className="text-xs text-[var(--text-secondary)] mt-0.5">Feedback của bạn sẽ vào hàng đợi retrain Phase 2 (F-036).</p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant={feedbackSent === 'helpful' ? 'primary' : 'secondary'}
                  size="sm"
                  onClick={() => sendFeedback('helpful')}
                  disabled={feedbackSent !== null}
                >
                  <ThumbsUp className="w-3.5 h-3.5 mr-1.5" />
                  Hữu ích
                </Button>
                <Button
                  variant={feedbackSent === 'unhelpful' ? 'destructive' : 'secondary'}
                  size="sm"
                  onClick={() => sendFeedback('unhelpful')}
                  disabled={feedbackSent !== null}
                >
                  <ThumbsDown className="w-3.5 h-3.5 mr-1.5" />
                  Chưa phù hợp
                </Button>
              </div>
            </div>
          </>
        ) : null}
      </div>
    </>
  );
}

// ----------------------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------------------

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

function AuditField({
  label, value, mono,
}: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)]/40 p-3">
      <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">{label}</p>
      <p className={cn('mt-1 break-all text-[var(--text-primary)]', mono ? 'font-mono text-xs' : 'text-sm')}>
        {value}
      </p>
    </div>
  );
}
