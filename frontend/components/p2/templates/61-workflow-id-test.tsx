// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 61. /p2/workflows/[id]/test — Workflow Test Runner (F-065 🔵 Phase 2)
// ----------------------------------------------------------------------------
// Manual trigger workflow trong sandbox:
//   - Form input variables (mỗi step có sample input).
//   - Bấm "Chạy thử" → mô phỏng từng step lần lượt với delay 600ms.
//   - Mỗi step hiển thị status icon + duration + output snippet.
//   - Sandbox: KHÔNG ghi vào real Kafka topic, KHÔNG send email — chỉ log
//     dry-run (Phase 2 wire `POST /api/v1/workflows/{id}/test?dry_run=true`).
//
// Khác file 60 (builder): test page CHỈ thực thi, không edit step.
// ============================================================================

import React, { useState } from 'react';
import {
  ArrowLeft, FlaskConical, Play, RotateCcw, Database, Brain,
  GitBranch, Bell, Clock, CheckCircle2, AlertTriangle, Loader2,
  ShieldCheck, Eye,
} from 'lucide-react';

import {
  Button, Badge, Input, ErrorBanner, SuccessBanner, cn,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
// ============================================================================
// Types
// ============================================================================

type StepKind = 'data_query' | 'llm_call' | 'condition' | 'notification' | 'wait';
type RunState = 'pending' | 'running' | 'success' | 'failed' | 'skipped';

interface TestStep {
  id:         string;
  kind:       StepKind;
  name:       string;
  state:      RunState;
  duration_ms?: number;
  output?:    string;
  error?:     string;
}

const KIND_META: Record<StepKind, { labelKey: string; icon: any }> = {
  data_query:   { labelKey: 'templates61WorkflowIdTest.kindDataQuery',   icon: Database },
  llm_call:     { labelKey: 'templates61WorkflowIdTest.kindLlmCall',     icon: Brain },
  condition:    { labelKey: 'templates61WorkflowIdTest.kindCondition',   icon: GitBranch },
  notification: { labelKey: 'templates61WorkflowIdTest.kindNotification', icon: Bell },
  wait:         { labelKey: 'templates61WorkflowIdTest.kindWait',        icon: Clock },
};

const STATE_META: Record<RunState, { labelKey: string; variant: 'default' | 'info' | 'success' | 'error' | 'warning'; icon: any }> = {
  pending: { labelKey: 'templates61WorkflowIdTest.statePending', variant: 'default', icon: Clock },
  running: { labelKey: 'templates61WorkflowIdTest.stateRunning', variant: 'info',    icon: Loader2 },
  success: { labelKey: 'templates61WorkflowIdTest.stateSuccess', variant: 'success', icon: CheckCircle2 },
  failed:  { labelKey: 'templates61WorkflowIdTest.stateFailed',  variant: 'error',   icon: AlertTriangle },
  skipped: { labelKey: 'templates61WorkflowIdTest.stateSkipped', variant: 'warning', icon: AlertTriangle },
};

// Initial step list — copy y nguyên từ workflow detail (file 60).
function initialSteps(t: (key: string, params?: Record<string, any>) => string): TestStep[] {
  return [
    { id: 'st_1', kind: 'data_query',   name: t('templates61WorkflowIdTest.stepNameInsight'),   state: 'pending' },
    { id: 'st_2', kind: 'llm_call',     name: t('templates61WorkflowIdTest.stepNameSummarize'), state: 'pending' },
    { id: 'st_3', kind: 'notification', name: t('templates61WorkflowIdTest.stepNameEmailManager'), state: 'pending' },
  ];
}

// ============================================================================
// Page
// ============================================================================

export default function WorkflowTestPage() {
  const t = useT();
  const [steps, setSteps] = useState<TestStep[]>(initialSteps(t));
  const [running, setRunning] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  // Test input variables
  const [insightCutoff, setInsightCutoff] = useState('24h');
  const [recipientEmail, setRecipientEmail] = useState('manager@acme.vn');
  const [forceFailStep, setForceFailStep] = useState<string>('');

  function reset() {
    setSteps(initialSteps(t));
    setRunning(false);
    setCompleted(false);
    setProblem(null);
  }

  async function runTest() {
    if (running) return;
    setRunning(true);
    setCompleted(false);
    setProblem(null);
    setSteps(initialSteps(t));

    // Simulate sequential execution.
    for (let i = 0; i < steps.length; i += 1) {
      const cur = steps[i];

      // Mark running
      setSteps((prev) => prev.map((s, j) => j === i ? { ...s, state: 'running' } : s));
      await new Promise((r) => setTimeout(r, 600));

      // Force-fail toggle
      if (forceFailStep === cur.id) {
        setSteps((prev) => prev.map((s, j) =>
          j === i  ? { ...s, state: 'failed',  duration_ms: 600, error: t('templates61WorkflowIdTest.errForceFail') } :
          j > i    ? { ...s, state: 'skipped' } :
          s,
        ));
        setProblem(t('templates61WorkflowIdTest.problemStepFailed', { name: cur.name }));
        setRunning(false);
        return;
      }

      // Generate fake output
      const outputByKind: Record<StepKind, string> = {
        data_query:   t('templates61WorkflowIdTest.outDataQuery', { cutoff: insightCutoff }),
        llm_call:     t('templates61WorkflowIdTest.outLlmCall'),
        condition:    t('templates61WorkflowIdTest.outCondition'),
        notification: t('templates61WorkflowIdTest.outNotification', { email: recipientEmail }),
        wait:         t('templates61WorkflowIdTest.outWait'),
      };

      setSteps((prev) => prev.map((s, j) => j === i ? {
        ...s, state: 'success', duration_ms: 600, output: outputByKind[cur.kind],
      } : s));
    }

    setCompleted(true);
    setRunning(false);
  }

  return (
    <>
      <PageHeader
        title={t('templates61WorkflowIdTest.pageTitle')}
        description={t('templates61WorkflowIdTest.pageDescription')}
        actions={
          <>
            <Badge variant="info">Phase 2 · F-065</Badge>
            <a href="/p2/workflows/wf_002">
              <Button variant="tertiary" size="md"><ArrowLeft className="w-4 h-4 mr-2" /> {t('templates61WorkflowIdTest.backToBuilder')}</Button>
            </a>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1300px] mx-auto space-y-4">
        {problem && <ErrorBanner problem={{ title: t('templates61WorkflowIdTest.testFailedTitle'), detail: problem }} />}
        {completed && !problem && <SuccessBanner message={t('templates61WorkflowIdTest.testSuccessMsg')} />}

        <div className="grid grid-cols-1 xl:grid-cols-[360px_1fr] gap-4">
          {/* Left: input form */}
          <div className="space-y-4 xl:sticky xl:top-20 self-start">
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
              <div className="flex items-center gap-2 mb-4 pb-3 border-b border-[var(--border-color)]/60">
                <FlaskConical className="w-4 h-4 text-[var(--primary-gold-dark)]" />
                <h3 className="font-serif text-base text-[var(--text-primary)]">{t('templates61WorkflowIdTest.inputVarsHeading')}</h3>
              </div>

              <div className="space-y-3">
                <Input
                  label={t('templates61WorkflowIdTest.insightCutoffLabel')}
                  value={insightCutoff}
                  onChange={(e) => setInsightCutoff(e.target.value)}
                  placeholder="24h"
                  helperText={t('templates61WorkflowIdTest.insightCutoffHelper')}
                />
                <Input
                  label={t('templates61WorkflowIdTest.recipientEmailLabel')}
                  value={recipientEmail}
                  onChange={(e) => setRecipientEmail(e.target.value)}
                  placeholder="manager@acme.vn"
                />
                <div className="space-y-2">
                  <label className="text-sm font-medium text-[var(--text-primary)]">{t('templates61WorkflowIdTest.forceFailLabel')}</label>
                  <select
                    value={forceFailStep}
                    onChange={(e) => setForceFailStep(e.target.value)}
                    className="w-full h-10 px-3 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)]"
                  >
                    <option value="">{t('templates61WorkflowIdTest.forceFailNone')}</option>
                    {steps.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                  <p className="text-xs text-[var(--text-secondary)]">{t('templates61WorkflowIdTest.forceFailHelper')}</p>
                </div>
              </div>
            </div>

            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm space-y-2">
              <Button variant="primary" size="md" onClick={runTest} disabled={running} isLoading={running} className="w-full">
                <Play className="w-4 h-4 mr-2" /> {t('templates61WorkflowIdTest.runTestBtn')}
              </Button>
              <Button variant="secondary" size="md" onClick={reset} disabled={running} className="w-full">
                <RotateCcw className="w-4 h-4 mr-2" /> {t('templates61WorkflowIdTest.resetBtn')}
              </Button>
            </div>

            <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
              <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
              <p>
                {t('templates61WorkflowIdTest.sandboxPrefix')} <span className="font-medium text-[var(--text-primary)]">{t('templates61WorkflowIdTest.no')}</span> {t('templates61WorkflowIdTest.sandboxKafka')}
                <span className="font-medium text-[var(--text-primary)]"> {t('templates61WorkflowIdTest.no')}</span> {t('templates61WorkflowIdTest.sandboxEmail')}
                <span className="font-medium text-[var(--text-primary)]"> {t('templates61WorkflowIdTest.no')}</span> {t('templates61WorkflowIdTest.sandboxBilling')}
              </p>
            </div>
          </div>

          {/* Right: execution log */}
          <div className="space-y-3">
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
              <div className="flex items-center justify-between gap-3 mb-4 pb-3 border-b border-[var(--border-color)]/60">
                <div className="flex items-center gap-2">
                  <Eye className="w-4 h-4 text-[var(--primary-gold-dark)]" />
                  <h3 className="font-serif text-base text-[var(--text-primary)]">{t('templates61WorkflowIdTest.executionProgressHeading')}</h3>
                </div>
                {running && (
                  <span className="inline-flex items-center gap-1 text-xs text-[var(--primary-gold-dark)]">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" /> {t('templates61WorkflowIdTest.runningEllipsis')}
                  </span>
                )}
              </div>

              <ol className="space-y-3">
                {steps.map((s, i) => <StepRow key={s.id} step={s} index={i} />)}
              </ol>
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

function StepRow({ step: s, index }: { step: TestStep; index: number }) {
  const t = useT();
  const kindMeta = KIND_META[s.kind];
  const stMeta = STATE_META[s.state];
  const KindIcon = kindMeta.icon;
  const StateIcon = stMeta.icon;

  return (
    <li className={cn(
      'p-4 rounded-md-custom border transition-colors',
      s.state === 'success' ? 'border-[var(--state-success)]/30 bg-[var(--state-success)]/5' :
      s.state === 'failed'  ? 'border-[var(--state-error)]/30 bg-[var(--state-error)]/5' :
      s.state === 'running' ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/8' :
      s.state === 'skipped' ? 'border-[var(--state-warning)]/30 bg-[var(--state-warning)]/5 opacity-70' :
      'border-[var(--border-color)] bg-[var(--bg-app)]/40',
    )}>
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-md-custom bg-[var(--primary-gold)]/15 flex items-center justify-center shrink-0">
          <KindIcon className="w-4 h-4 text-[var(--primary-gold-dark)]" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)] font-medium">
                {t('templates61WorkflowIdTest.stepIndexKind', { n: index + 1, kind: t(kindMeta.labelKey) })}
              </p>
              <p className="text-sm font-medium text-[var(--text-primary)]">{s.name}</p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {s.duration_ms != null && (
                <span className="text-[11px] text-[var(--text-secondary)] font-mono">{s.duration_ms}ms</span>
              )}
              <Badge variant={stMeta.variant}>
                <StateIcon className={cn('w-3 h-3 mr-1', s.state === 'running' && 'animate-spin')} /> {t(stMeta.labelKey)}
              </Badge>
            </div>
          </div>
          {s.output && (
            <pre className="mt-3 px-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-sm-custom text-[11px] font-mono text-[var(--text-primary)] whitespace-pre-wrap leading-relaxed">
              {s.output}
            </pre>
          )}
          {s.error && (
            <p className="mt-2 text-xs text-[var(--state-error)] leading-relaxed">{s.error}</p>
          )}
        </div>
      </div>
    </li>
  );
}
