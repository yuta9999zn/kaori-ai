'use client';

// ============================================================================
// /p2/pipelines/[id] — wizard entry redirect
// ----------------------------------------------------------------------------
// The pipeline list (template 18) links each row to /p2/pipelines/{id}, but
// the wizard itself lives under step-2-columns … step-5-results. This index
// route fetches the run status via /api/v1/upload/{id}/status (same endpoint
// the upload step polls) and forwards to the correct step.
//
// Status → step map (BE pipeline_runs.status lifecycle):
//   uploading / bronze_complete / unstructured_pending → step-2 (columns)
//   schema_review                                       → step-2 (columns)
//   cleaning / silver_complete                          → step-3 (clean)
//   analyzing                                           → step-4 (analyze)
//   analysis_complete / done                            → step-5-results
//   failed / error / anything else                      → step-2 (default)
// ============================================================================

import React, { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { api } from '@/components/p2/foundation';
import { useT } from '@/lib/i18n/provider';

function stepPathFor(status: string): string {
  const raw = String(status ?? '').toLowerCase();
  const normalized = ({ done: 'analysis_complete', error: 'failed' } as Record<string, string>)[raw] ?? raw;
  switch (normalized) {
    case 'cleaning':
    case 'silver_complete':
      return 'step-3-clean';
    case 'analyzing':
      return 'step-4-analyze';
    case 'analysis_complete':
      return 'step-5-results';
    case 'uploading':
    case 'bronze_complete':
    case 'unstructured_pending':
    case 'schema_review':
    case 'failed':
    default:
      return 'step-2-columns';
  }
}

export default function PipelineWizardEntry() {
  const t = useT();
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params?.id;

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    (async () => {
      let step = 'step-2-columns';
      try {
        const st = await api<{ status?: string }>(`/api/v1/upload/${id}/status`);
        step = stepPathFor(st?.status ?? '');
      } catch {
        // 404 (status row not yet landed) or any error → start at column step.
        step = 'step-2-columns';
      }
      if (!cancelled) {
        router.replace(`/p2/pipelines/${id}/${step}`);
      }
    })();
    return () => { cancelled = true; };
  }, [id, router]);

  return (
    <div className="flex flex-col items-center justify-center gap-3 py-24 text-[var(--text-secondary)]">
      <Loader2 className="w-6 h-6 animate-spin" />
      <p className="text-sm">{t('idPage3.openingPipeline')}</p>
    </div>
  );
}
