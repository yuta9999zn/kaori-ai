'use client';

// ============================================================================
// /p2/pipelines/[id]/step-1-upload — Bước 1 cho pipeline ĐÃ TỒN TẠI
// ----------------------------------------------------------------------------
// WizardStepper (foundation-wizard) link mọi bước theo dạng
// /p2/pipelines/{id}/{step}; step-1 trước đây chỉ có route /new/upload nên
// bấm ô "Upload" trên stepper của một run có sẵn là 404 (phát hiện đêm
// 10/07 khi chuẩn bị demo AABW). Với run có sẵn, bước Upload đã hoàn tất —
// trang này tóm tắt file gốc ở Bronze (K-2/K-8) + đưa người dùng đi tiếp.
// ============================================================================

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowRight, FileCheck2, Loader2, Upload } from 'lucide-react';

import { api } from '@/components/p2/foundation';
import { WizardStepper } from '@/components/p2/foundation-wizard';

interface RunStatus {
  run_id: string;
  status?: string;
  filename?: string | null;
  row_count_bronze?: number | null;
  row_count_silver?: number | null;
  quality_score?: number | null;
}

export default function ExistingPipelineUploadStep() {
  const params = useParams<{ id: string }>();
  const pipelineId = params?.id ?? '';
  const [run, setRun] = useState<RunStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!pipelineId) return;
    (async () => {
      try {
        setRun(await api<RunStatus>(`/api/v1/upload/${pipelineId}/status`));
      } catch { /* run chưa có status row — vẫn render khung điều hướng */ }
      finally { setLoading(false); }
    })();
  }, [pipelineId]);

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-serif text-[var(--text-primary)]">Tải lên file</h1>
      <p className="text-sm text-[var(--text-secondary)]">
        Bước 1 / 5 — pipeline này đã có file gốc, bước Upload đã hoàn tất.
      </p>

      <WizardStepper pipelineId={pipelineId} current={1} />

      <div className="rounded-xl border border-[var(--border-default)] bg-[var(--surface-primary)] p-5 space-y-3">
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
            <Loader2 className="w-4 h-4 animate-spin" /> Đang tải thông tin file…
          </div>
        ) : (
          <>
            <div className="flex items-center gap-2">
              <FileCheck2 className="w-5 h-5 text-emerald-600" />
              <span className="text-sm font-medium text-[var(--text-primary)]">
                {run?.filename ?? 'File gốc'}
              </span>
            </div>
            <p className="text-xs text-[var(--text-secondary)]">
              File đã được lưu nguyên vẹn ở <strong>Bronze layer</strong> (append-only, K-2)
              {typeof run?.row_count_bronze === 'number' && <> — {run.row_count_bronze} hàng</>}
              {typeof run?.quality_score === 'number' && <> · điểm chất lượng {Number(run.quality_score).toFixed(2)}</>}.
              Không cần (và không thể) upload lại tại đây — muốn nạp file khác, hãy tạo pipeline mới.
            </p>
          </>
        )}
        <div className="flex items-center gap-3 pt-1">
          <Link href={`/p2/pipelines/${pipelineId}/step-2-columns`}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--primary-gold)] px-4 py-2 text-sm font-medium text-white hover:opacity-90">
            Sang Bước 2 — Cột <ArrowRight className="w-4 h-4" />
          </Link>
          <Link href="/p2/pipelines/new"
            className="inline-flex items-center gap-1.5 text-sm text-[var(--text-secondary)] hover:underline">
            <Upload className="w-4 h-4" /> Tải file khác (pipeline mới)
          </Link>
        </div>
      </div>
    </div>
  );
}
