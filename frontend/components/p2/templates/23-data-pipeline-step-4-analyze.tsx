// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 23. /p2/pipelines/{id}/step-4-analyze — Step 4 Analysis Config (F-020)
// ----------------------------------------------------------------------------
// GET  /api/v1/analytics/templates                  → catalog
// POST /api/v1/analytics/runs                        → start analysis
//
// CRITICAL — K-4 (External AI Consent):
//   Default consent_external = false → all LLM calls go to Qwen 14B local.
//   Toggle ON requires user confirmation modal explaining:
//     - PII auto-redacted via guardrails (K-5) BEFORE leaving boundary
//     - Data sent to Claude Sonnet / GPT-4o (named explicitly)
//     - Decision logged to decision_audit_log (K-6) with consent flag
//     - Per-tenant audit accessible at /p2/decisions
//
// K-3 / K-10 also enforced here:
//   - All LLM via llm_router (FE just sets flag)
//   - 1 question = 1 framework (no parallel SWOT+5Why selection)
// ============================================================================

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import {
  ChevronLeft, ShieldCheck, AlertTriangle, Lock, Globe,
  Sparkles, BarChart3, X, Check, Zap,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, Checkbox, cn,
  api,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { WizardStepper } from '@/components/p2/foundation-wizard';

interface AnalysisTemplate {
  id:          string;
  category:    'statistical' | 'ml' | 'forecasting' | 'anomaly';
  name:        string;
  description: string;
  min_rows:          number;     // BE-declared minimum rows for this analysis
  eligible:          boolean;     // BE eligibility for the detected data profile
  estimated_minutes: number;
  needs_external_ai: boolean;
  is_recommended:    boolean;
}

const CATEGORY_LABEL: Record<string, string> = {
  statistical: 'Thống kê',
  ml:          'Machine Learning',
  forecasting: 'Dự báo',
  anomaly:     'Phát hiện bất thường',
};

export default function PipelineStep4Analyze() {
  const params = useParams<{ id: string }>();
  const pipelineId = params?.id ?? '';

  const [templates,  setTemplates]  = useState<AnalysisTemplate[]>([]);
  const [selected,   setSelected]   = useState<Set<string>>(new Set());
  const [consentExt, setConsentExt] = useState(false);
  const [showConsent, setShowConsent] = useState(false);
  const [loading,   setLoading]   = useState(true);
  const [problem,   setProblem]   = useState<ProblemDetails | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function load() {
    setLoading(true);
    setProblem(null);
    try {
      // Real BE: GET /analytics/templates → ARRAY of
      // {template_id, display_name, description, eligible, min_rows, ...}.
      const res = await api<any[]>('/api/v1/analytics/templates');
      const mapped: AnalysisTemplate[] = (res ?? []).map((t: any) => ({
        id:                t.template_id,
        category:          (['statistical', 'ml', 'forecasting', 'anomaly'].includes(t.category) ? t.category : 'statistical'),
        name:              t.display_name,
        description:       t.description,
        min_rows:          t.min_rows ?? 0,
        eligible:          !!t.eligible,
        estimated_minutes: 1,
        needs_external_ai: !!t.needs_external_ai,
        is_recommended:    !!t.eligible,
      }));
      setTemplates(mapped);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  function toggleTemplate(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function handleConsentToggle() {
    if (!consentExt) {
      setShowConsent(true);
    } else {
      setConsentExt(false);
    }
  }

  function confirmConsent() {
    setConsentExt(true);
    setShowConsent(false);
  }

  async function startAnalysis() {
    setSubmitting(true);
    setProblem(null);
    try {
      // Real BE: POST /analytics/runs {run_id, templates, config} → 202
      // {analysis_run_id}. Step 5 reads the analysis_run_id from ?run_id=.
      const res = await api<{ analysis_run_id: string }>('/api/v1/analytics/runs', {
        method: 'POST',
        body: JSON.stringify({
          run_id:    pipelineId,
          templates: Array.from(selected),
          config:    { consent_external: consentExt },
        }),
      });
      window.location.href = `/p2/pipelines/${pipelineId}/step-5-results?run_id=${res.analysis_run_id}`;
    } catch (err: any) {
      setProblem(err);
    } finally {
      setSubmitting(false);
    }
  }

  const blockedSelections = templates.filter((t) => selected.has(t.id) && t.needs_external_ai && !consentExt);

  return (
    <>
      <PageHeader
        title="Phân tích"
        description="Bước 4 / 5 — chọn template phân tích và quyết định nguồn AI."
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1200px] mx-auto space-y-6">
        <WizardStepper current={4} pipelineId={pipelineId} />

        <ErrorBanner problem={problem} />

        <div className={cn(
          'rounded-lg-custom border-2 p-5 shadow-soft-sm transition-colors',
          consentExt
            ? 'bg-[var(--state-warning)]/8 border-[var(--state-warning)]/40'
            : 'bg-[var(--primary-gold)]/8 border-[var(--primary-gold)]/30',
        )}>
          <div className="flex items-start gap-4">
            <div className={cn(
              'w-12 h-12 rounded-full flex items-center justify-center shrink-0',
              consentExt ? 'bg-[var(--state-warning)]/20' : 'bg-[var(--primary-gold)]/20',
            )}>
              {consentExt
                ? <Globe className="w-6 h-6 text-[var(--state-warning)]" />
                : <Lock className="w-6 h-6 text-[var(--primary-gold-dark)]" />}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-3 mb-2 flex-wrap">
                <h3 className="font-serif text-lg text-[var(--text-primary)]">
                  Nguồn AI: {consentExt ? 'Bên ngoài (Claude / GPT-4o)' : 'Qwen 14B nội bộ'}
                </h3>
                <Button
                  size="sm"
                  variant={consentExt ? 'destructive' : 'secondary'}
                  onClick={handleConsentToggle}
                >
                  {consentExt ? 'Tắt AI bên ngoài' : 'Bật AI bên ngoài'}
                </Button>
              </div>
              <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
                {consentExt ? (
                  <>
                    <span className="text-[#9E814D] font-medium">Đang gửi dữ liệu ra ngoài:</span>{' '}
                    PII đã được che (K-5) trước khi rời khỏi server Kaori. Mọi quyết định gửi external sẽ ghi vào{' '}
                    <a href="/p2/decisions" className="underline">decision audit log</a> với cờ <span className="font-mono">consent_external=true</span>.
                  </>
                ) : (
                  <>
                    <span className="text-[var(--text-primary)] font-medium">Riêng tư mặc định:</span>{' '}
                    100% phân tích chạy bằng Qwen 14B trên server Kaori. Dữ liệu không rời khỏi workspace của bạn.
                    Chất lượng đủ tốt cho hầu hết template thống kê / ML cơ bản.
                  </>
                )}
              </p>
            </div>
          </div>
        </div>

        {blockedSelections.length > 0 && (
          <div className="rounded-md-custom bg-[var(--state-error)]/10 border border-[var(--state-error)]/30 p-3 flex items-start gap-3">
            <AlertTriangle className="w-4 h-4 text-[var(--state-error)] shrink-0 mt-0.5" />
            <p className="text-sm text-[#9B5050]">
              {blockedSelections.length} template đang chọn yêu cầu AI bên ngoài (Claude/GPT). Bật consent ở trên hoặc bỏ chọn.
            </p>
          </div>
        )}

        <div>
          <h3 className="font-serif text-base text-[var(--text-primary)] mb-3">
            Template phân tích {selected.size > 0 && <span className="text-sm text-[var(--text-secondary)] font-sans">({selected.size} đang chọn)</span>}
          </h3>
          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {[1,2,3,4].map((i) => <div key={i} className="h-32 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse" />)}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {templates.map((t) => (
                <TemplateCard
                  key={t.id}
                  template={t}
                  selected={selected.has(t.id)}
                  blocked={t.needs_external_ai && !consentExt}
                  onToggle={() => toggleTemplate(t.id)}
                />
              ))}
            </div>
          )}
        </div>

        <div className="flex items-start gap-3 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            Mọi LLM call đi qua <span className="font-medium text-[var(--text-primary)]">llm_router</span> (K-3) — không bao giờ gọi trực tiếp SDK.
            Khi bật consent, PII vẫn được redact (K-5: <span className="font-mono">&lt;EMAIL_1&gt;</span>, <span className="font-mono">&lt;PHONE_1&gt;</span>) trước khi gửi.
            Mỗi run tạo entry trong decision_audit_log (K-6).
          </p>
        </div>

        <div className="flex items-center justify-between">
          <Button
            variant="secondary"
            onClick={() => (window.location.href = `/p2/pipelines/${pipelineId}/step-3-clean`)}
            disabled={submitting}
          >
            <ChevronLeft className="w-4 h-4 mr-1" />
            Quay lại
          </Button>
          <Button
            onClick={startAnalysis}
            isLoading={submitting}
            disabled={selected.size === 0 || blockedSelections.length > 0}
          >
            <Sparkles className="w-4 h-4 mr-2" />
            Bắt đầu phân tích {selected.size} template
          </Button>
        </div>
      </div>

      {showConsent && (
        <ConsentModal
          onCancel={() => setShowConsent(false)}
          onConfirm={confirmConsent}
        />
      )}
    </>
  );
}

function TemplateCard({ template: t, selected, blocked, onToggle }: any) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={cn(
        'text-left rounded-lg-custom bg-[var(--bg-card)] border p-4 shadow-soft-sm transition-all',
        selected
          ? 'border-[var(--primary-gold)] ring-1 ring-[var(--primary-gold)] bg-[var(--primary-gold)]/4'
          : 'border-[var(--border-color)] hover:border-[var(--primary-gold)]/30 hover:shadow-soft-md',
        blocked && 'opacity-60',
      )}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <h4 className="font-medium text-[var(--text-primary)]">{t.name}</h4>
          <Badge variant="default" className="text-[10px]">{CATEGORY_LABEL[t.category] ?? t.category}</Badge>
          {t.is_recommended && <Badge variant="success" className="text-[10px]">Khuyến nghị</Badge>}
          {t.needs_external_ai && (
            <Badge variant="warning" className="text-[10px]">
              <Globe className="w-2.5 h-2.5 mr-0.5 inline" />
              Cần AI bên ngoài
            </Badge>
          )}
        </div>
        <div className={cn(
          'w-5 h-5 rounded-full border flex items-center justify-center shrink-0 mt-0.5',
          selected ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]' : 'border-[var(--border-color)]',
        )}>
          {selected && <Check className="w-3 h-3 text-white" strokeWidth={3} />}
        </div>
      </div>
      <p className="text-sm text-[var(--text-secondary)] leading-relaxed mb-3">{t.description}</p>
      <div className="flex items-center justify-between text-[11px] text-[var(--text-secondary)]">
        <span>≈ {t.estimated_minutes} phút</span>
        {t.min_rows > 0 && <span>Cần ≥ {t.min_rows.toLocaleString('vi-VN')} dòng</span>}
      </div>
      {!t.eligible && !blocked && (
        <p className="text-[11px] text-[#9E814D] mt-2 flex items-center gap-1">
          <AlertTriangle className="w-3 h-3" />
          Dữ liệu hiện tại có thể chưa đủ điều kiện cho phân tích này
        </p>
      )}
      {blocked && (
        <p className="text-[11px] text-[#9B5050] mt-2 flex items-center gap-1">
          <AlertTriangle className="w-3 h-3" />
          Bật consent AI bên ngoài để chọn template này
        </p>
      )}
    </button>
  );
}

function ConsentModal({ onCancel, onConfirm }: any) {
  const [acked, setAcked] = useState(false);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/40 backdrop-blur-sm" onClick={onCancel}>
      <div
        className="bg-[var(--bg-card)] rounded-lg-custom shadow-soft-lg border border-[var(--border-color)] w-full max-w-[560px] p-6 animate-slide-up-fade"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-[var(--state-warning)]/15 flex items-center justify-center">
              <Globe className="w-5 h-5 text-[var(--state-warning)]" />
            </div>
            <h3 className="font-serif text-lg text-[var(--text-primary)]">Bật AI bên ngoài</h3>
          </div>
          <button onClick={onCancel} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
            <X className="w-5 h-5" />
          </button>
        </div>

        <p className="text-sm text-[var(--text-secondary)] leading-relaxed mb-4">
          Khi bật, một số template sẽ gửi dữ liệu (đã che PII) sang Claude Sonnet hoặc GPT-4o để phân tích phức tạp hơn. Vui lòng đọc kỹ:
        </p>

        <ul className="space-y-2 mb-5 text-sm">
          {[
            { icon: Lock,        text: 'Email / SĐT / Tên / Địa chỉ / CCCD đã được redact thành <EMAIL_1>, <PHONE_1>... (K-5).' },
            { icon: ShieldCheck, text: 'Output từ AI bên ngoài được Guardrails kiểm tra trước khi unmask + hiển thị.' },
            { icon: BarChart3,   text: 'Mỗi quyết định ghi vào decision_audit_log (K-6) với consent flag — bạn xem được tại /p2/decisions.' },
            { icon: Zap,         text: 'External call tốn hạn mức gói cước riêng (xem Subscription).' },
          ].map((item, i) => {
            const Icon = item.icon;
            return (
              <li key={i} className="flex items-start gap-3 p-2 rounded-md-custom bg-[var(--bg-app)]/50 border border-[var(--border-color)]/40">
                <Icon className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
                <span className="text-[var(--text-primary)]">{item.text}</span>
              </li>
            );
          })}
        </ul>

        <div className="mb-5 p-3 rounded-md-custom bg-[var(--state-warning)]/8 border border-[var(--state-warning)]/30">
          <Checkbox
            checked={acked}
            onChange={(e) => setAcked(e.target.checked)}
            label={<span className="text-[#9E814D]">Tôi hiểu rằng dữ liệu (đã che PII) sẽ rời khỏi server Kaori và được Claude / OpenAI xử lý.</span>}
          />
        </div>

        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={onCancel}>Huỷ</Button>
          <Button variant="destructive" onClick={onConfirm} disabled={!acked}>
            Bật AI bên ngoài
          </Button>
        </div>
      </div>
    </div>
  );
}
