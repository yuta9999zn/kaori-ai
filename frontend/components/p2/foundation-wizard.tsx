'use client';
// @ts-nocheck
// ============================================================================
// Pipeline wizard helpers — shared across step-1..step-5 (file 20-24)
// ----------------------------------------------------------------------------
// Single source for the 5-step indicator + canonical status badge so all
// wizard pages stay in sync.
// ============================================================================

import React from 'react';
import { Check } from 'lucide-react';
import { Badge, cn } from './foundation';
import { useT } from '@/lib/i18n/provider';

// NOTE: `title` here is an i18n KEY (not display text) — consumers render it
// via `t(s.title)`. WizardStepper below does this internally.
export const WIZARD_STEPS = [
  { n: 1, title: 'foundationWizard.stepUpload',  path: 'step-1-upload'  },
  { n: 2, title: 'foundationWizard.stepColumn',  path: 'step-2-columns' },
  { n: 3, title: 'foundationWizard.stepClean',   path: 'step-3-clean'   },
  { n: 4, title: 'foundationWizard.stepAnalyze', path: 'step-4-analyze' },
  { n: 5, title: 'foundationWizard.stepResults', path: 'step-5-results' },
];

/** Pipeline status enum — DB CHECK constraint (Sprint 7 PR C). */
export type PipelineStatus = 'schema_review' | 'analyzing' | 'analysis_complete' | 'failed';

// NOTE: `label` here is an i18n KEY (not display text) — consumers must
// render it via `t(PIPELINE_STATUS_BADGE[status].label)`.
export const PIPELINE_STATUS_BADGE: Record<PipelineStatus, { variant: any; label: string }> = {
  schema_review:     { variant: 'info',    label: 'foundationWizard.statusSchemaReview' },
  analyzing:         { variant: 'warning', label: 'foundationWizard.statusAnalyzing' },
  analysis_complete: { variant: 'success', label: 'foundationWizard.statusComplete' },
  failed:            { variant: 'error',   label: 'foundationWizard.statusFailed' },
};

/**
 * Renders the 5-step indicator at the top of any wizard step.
 * `current` is 1..5; previous steps are marked done, future are dimmed.
 */
export function WizardStepper({
  current, pipelineId,
}: { current: number; pipelineId: string }) {
  const t = useT();
  return (
    <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-4 shadow-soft-sm">
      <div className="flex items-center justify-between gap-2">
        {WIZARD_STEPS.map((s, idx) => {
          const done = current > s.n;
          const cur  = current === s.n;
          const clickable = done; // only previously-completed steps are revisitable
          const Box = (
            <div className={cn(
              'w-8 h-8 rounded-full flex items-center justify-center transition-colors text-xs font-medium border shrink-0',
              done ? 'bg-[var(--state-success)] text-white border-[var(--state-success)]'
                   : cur  ? 'bg-[var(--primary-gold)] text-[var(--text-primary)] border-[var(--primary-gold)]'
                          : 'bg-[var(--bg-app)] text-[var(--text-secondary)] border-[var(--border-color)]',
            )}>
              {done ? <Check className="w-4 h-4" /> : s.n}
            </div>
          );
          return (
            <React.Fragment key={s.n}>
              <div className={cn('flex items-center gap-3 shrink-0', clickable && 'cursor-pointer')}>
                {clickable ? (
                  <a href={`/p2/pipelines/${pipelineId}/${s.path}`}>{Box}</a>
                ) : Box}
                <span className={cn(
                  'text-sm font-medium hidden md:block',
                  done || cur ? 'text-[var(--text-primary)]' : 'text-[var(--text-secondary)]',
                )}>
                  {t(s.title)}
                </span>
              </div>
              {idx < WIZARD_STEPS.length - 1 && (
                <div className={cn(
                  'flex-1 h-px',
                  done ? 'bg-[var(--state-success)]' : 'bg-[var(--border-color)]',
                )} />
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
