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

export const WIZARD_STEPS = [
  { n: 1, title: 'Upload',     path: 'step-1-upload'  },
  { n: 2, title: 'Cột',         path: 'step-2-columns' },
  { n: 3, title: 'Làm sạch',    path: 'step-3-clean'   },
  { n: 4, title: 'Phân tích',   path: 'step-4-analyze' },
  { n: 5, title: 'Kết quả',     path: 'step-5-results' },
];

/** Pipeline status enum — DB CHECK constraint (Sprint 7 PR C). */
export type PipelineStatus = 'schema_review' | 'analyzing' | 'analysis_complete' | 'failed';

export const PIPELINE_STATUS_BADGE: Record<PipelineStatus, { variant: any; label: string }> = {
  schema_review:     { variant: 'info',    label: 'Chờ duyệt cột' },
  analyzing:         { variant: 'warning', label: 'Đang phân tích' },
  analysis_complete: { variant: 'success', label: 'Hoàn tất' },
  failed:            { variant: 'error',   label: 'Lỗi' },
};

/**
 * Renders the 5-step indicator at the top of any wizard step.
 * `current` is 1..5; previous steps are marked done, future are dimmed.
 */
export function WizardStepper({
  current, pipelineId,
}: { current: number; pipelineId: string }) {
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
                  {s.title}
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
