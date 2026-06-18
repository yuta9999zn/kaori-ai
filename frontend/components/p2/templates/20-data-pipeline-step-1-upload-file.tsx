// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 20. /p2/pipelines/new/upload — Step 1 Upload File (F-017)
// ----------------------------------------------------------------------------
// Drag-drop or click-to-browse. Compute SHA-256 client-side (Web Crypto API)
// before upload to give an immediate dedup hint (K-8). Backend recomputes the
// hash and checks `bronze_files` — on hit returns 200 with `is_duplicate=true`
// and the existing bronze_file_id; on miss creates a new bronze record.
//
// No pipelineId in the URL: pipeline_runs row doesn't exist yet. Backend
// (bronze/ingestor.py) auto-allocates run_id on POST /api/v1/upload and
// returns it. We then route per-file to /p2/pipelines/{run_id}/step-2-columns.
//
// Multi-file (2026-05-04 fix): user can pick / drop several files at once;
// each file is uploaded sequentially and gets its own pipeline_run_id. The
// BE endpoint accepts one file per request, so we loop client-side.
//
// Idempotency-Key auto-attached per file (K-13).
// Status enum after upload: schema_review (next: step-2-columns).
// ============================================================================

import React, { useState, useRef, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  UploadCloud, FileSpreadsheet, X, AlertCircle, CheckCircle2,
  ChevronRight, ShieldCheck, FileDigit, Loader2, Workflow as WorkflowIcon,
  ArrowLeft,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner,
  api, cn, ensureFreshToken,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { WizardStepper } from '@/components/p2/foundation-wizard';
// (NOTE: file 20-24 share the wizard stepper from _foundation_wizard.tsx.)

interface UploadResponse {
  bronze_file_id: string;
  pipeline_run_id: string;
  is_duplicate:   boolean;     // K-8 hit
  rows:           number;
  size_bytes:     number;
  detected_format: 'csv' | 'xlsx' | 'parquet' | 'json';
  next_step_path: string;       // e.g. /p2/pipelines/{id}/step-2-columns
}

type ItemStatus =
  | 'hashing'   // Web Crypto SHA-256 in progress
  | 'ready'     // hashed (or hash skipped), waiting for upload
  | 'uploading'
  | 'success'   // backend persisted, new bronze record
  | 'duplicate' // backend reused existing bronze_file_id (K-8 hit)
  | 'failed';

interface UploadItem {
  id:       string;       // local key, not the BE bronze_file_id
  file:     File;
  sha256:   string;       // empty until hashing finishes (or "" if skipped)
  status:   ItemStatus;
  progress: number;       // 0-100, only meaningful in 'uploading'
  result?:  UploadResponse;
  problem?: ProblemDetails;
}

// Must match the backend ingestor's accepted tabular extensions
// (data-pipeline ingestor.py SUPPORTED_EXTENSIONS) — advertising .json/.parquet
// here let users pick a file the backend then rejects with a 400 (B5 bug).
const ACCEPT = '.csv,.ods,.sql,.tsv,.txt,.xls,.xlsb,.xlsm,.xlsx,.zip';
const MAX_BYTES = 500 * 1024 * 1024; // 500 MB

// API gateway base — must be absolute so XHR routes to the gateway
// (or to MSW intercepting on the same origin in dev mode). Relative
// "/api/v1/..." would resolve to http://localhost:3000 (Next.js dev
// server) which has no /api/v1 route → 404 for both real-BE and MSW
// dev mode. Mirrors the axios client in lib/api/client.ts.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

let _seq = 0;
const nextId = () => `up_${++_seq}_${Date.now().toString(36)}`;

export default function PipelineStep1Upload() {
  const [items, setItems]       = useState<UploadItem[]>([]);
  const [running, setRunning]   = useState(false);   // a sequential upload pass is in flight
  const [problem, setProblem]   = useState<ProblemDetails | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [navigating, setNavigating] = useState(false);   // "Sang Bước 2" clicked — Step 2 fetches schema (~3-4s); show feedback
  const inputRef = useRef<HTMLInputElement>(null);

  // P15-S11 Tuần 8 — workflow card attachment. When the workflow tree
  // viewer's "Tải lên" button redirected here, ?workflow_step_id= and
  // ?workflow_id= are present. We forward the step ID as the
  // X-Workflow-Step-ID header so the BE attaches the upload to that
  // card (mig 053 workflow_step_documents).
  const searchParams = useSearchParams();
  const workflowStepId = searchParams?.get('workflow_step_id') ?? null;
  const workflowId     = searchParams?.get('workflow_id')      ?? null;
  const [workflowCtx, setWorkflowCtx] = useState<{ workflowName: string; stepTitle: string } | null>(null);

  useEffect(() => {
    if (!workflowStepId || !workflowId) return;
    let cancelled = false;
    (async () => {
      try {
        const tree = await api<any>(`/api/v1/workflows/${workflowId}/tree`);
        const node = (tree.nodes || []).find((n: any) => n.node_id === workflowStepId);
        if (!cancelled && node) {
          setWorkflowCtx({
            workflowName: tree.workflow?.name_vi || tree.workflow?.name || 'workflow',
            stepTitle:    node.title_vi || node.title || 'bước',
          });
        }
      } catch {
        // Best-effort header display — upload still works if banner data fails.
      }
    })();
    return () => { cancelled = true; };
  }, [workflowStepId, workflowId]);

  // -------------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------------

  function patchItem(id: string, patch: Partial<UploadItem>) {
    setItems((prev) => prev.map((i) => i.id === id ? { ...i, ...patch } : i));
  }

  // ── Async upload: build the display result + poll the run status until the
  // background Bronze ingest reaches a terminal state. ─────────────────────
  function _resultFor(runId: string, rows: number, file: File): UploadResponse {
    const ext = file.name.toLowerCase().split('.').pop() ?? 'csv';
    const fmt = (['csv', 'xlsx', 'parquet', 'json'].includes(ext) ? ext : 'csv') as UploadResponse['detected_format'];
    return {
      bronze_file_id:  '',
      pipeline_run_id: runId,
      is_duplicate:    false,
      rows:            rows ?? 0,
      size_bytes:      file.size,
      detected_format: fmt,
      next_step_path:  `/p2/pipelines/${runId}/step-2-columns`,
    };
  }

  function pollStatus(itemId: string, runId: string, file: File) {
    const TERMINAL_OK = ['bronze_complete', 'silver_complete', 'analysis_complete',
                         'schema_review', 'unstructured_pending'];
    let tries = 0;
    const tick = async () => {
      tries += 1;
      try {
        const st = await api<any>(`/api/v1/upload/${runId}/status`);
        if (TERMINAL_OK.includes(st.status)) {
          patchItem(itemId, {
            status: 'success', progress: 100,
            result: _resultFor(runId, st.row_count_bronze ?? st.row_count ?? 0, file),
          });
          return;
        }
        if (st.status === 'failed') {
          patchItem(itemId, {
            status: 'failed',
            problem: { title: 'Xử lý file thất bại', detail: st.error_message ?? undefined },
          });
          return;
        }
      } catch {
        // 404 while the background INSERT hasn't landed yet → keep polling.
      }
      if (tries < 150) setTimeout(tick, 2000);   // ~5 min ceiling
      else patchItem(itemId, { status: 'failed', problem: { title: 'Quá thời gian xử lý file' } });
    };
    setTimeout(tick, 1500);
  }

  function removeItem(id: string) {
    setItems((prev) => prev.filter((i) => i.id !== id));
  }

  async function hashItem(item: UploadItem) {
    try {
      const buf  = await item.file.arrayBuffer();
      const hash = await crypto.subtle.digest('SHA-256', buf);
      const hex  = Array.from(new Uint8Array(hash))
        .map((b) => b.toString(16).padStart(2, '0')).join('');
      patchItem(item.id, { sha256: hex, status: 'ready' });
    } catch {
      // K-8 hint is optional — fall back to server-side hashing.
      patchItem(item.id, { sha256: '', status: 'ready' });
    }
  }

  // -------------------------------------------------------------------------
  // File picker (input + drag-drop) — supports multiple
  // -------------------------------------------------------------------------

  function addFiles(files: FileList | File[] | null | undefined) {
    if (!files || files.length === 0) return;
    setProblem(null);

    const accepted: UploadItem[] = [];
    const oversize: string[] = [];

    for (const f of Array.from(files)) {
      if (f.size > MAX_BYTES) {
        oversize.push(`${f.name} (${humanBytes(f.size)})`);
        continue;
      }
      accepted.push({
        id:       nextId(),
        file:     f,
        sha256:   '',
        status:   'hashing',
        progress: 0,
      });
    }

    if (oversize.length > 0) {
      setProblem({
        title:  oversize.length === 1 ? 'File quá lớn' : `${oversize.length} file quá lớn`,
        detail: `Tối đa 500 MB. Bỏ qua: ${oversize.join(', ')}`,
      });
    }
    if (accepted.length === 0) return;

    setItems((prev) => [...prev, ...accepted]);
    // Hash in parallel — Web Crypto is async + cheap, no need to serialise.
    accepted.forEach((it) => { hashItem(it); });
  }

  // -------------------------------------------------------------------------
  // Sequential upload — one file at a time so the BE doesn't get hammered
  // -------------------------------------------------------------------------

  async function uploadOne(item: UploadItem): Promise<void> {
    // Proactively swap an expired/near-expiry access token BEFORE the upload —
    // the raw XHR can't ride api()'s 401-retry, and the 15-min access TTL used
    // to 401 long sessions mid-upload even though the refresh token was valid.
    const freshTok = await ensureFreshToken();
    return new Promise((resolve) => {
      const fd = new FormData();
      fd.append('file', item.file);
      if (item.sha256) fd.append('sha256_hint', item.sha256);

      const xhr = new XMLHttpRequest();
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          patchItem(item.id, { progress: Math.round((e.loaded / e.total) * 100) });
        }
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const res: any = JSON.parse(xhr.responseText);
            const runId = res.run_id ?? res.pipeline_run_id;
            if (res.is_duplicate) {
              // K-8 hit — existing run reused (already processed).
              patchItem(item.id, {
                status: 'duplicate', progress: 100,
                result: _resultFor(runId, res.rows ?? 0, item.file),
              });
            } else if (res.detected_format != null || res.rows != null) {
              // Synchronous result (workflow-card path) — show immediately.
              patchItem(item.id, { status: 'success', progress: 100, result: res });
            } else {
              // Async accepted (202 {run_id, status:'uploading'}) — the heavy
              // Bronze ingest runs in the background; poll until it finishes.
              patchItem(item.id, { status: 'uploading', progress: 100 });
              pollStatus(item.id, runId, item.file);
            }
          } catch (e) {
            patchItem(item.id, {
              status:  'failed',
              problem: { title: 'Phản hồi không hợp lệ từ server' },
            });
          }
        } else {
          let p: ProblemDetails = { title: `HTTP ${xhr.status}` };
          try { p = { ...p, ...JSON.parse(xhr.responseText) }; } catch {}
          patchItem(item.id, { status: 'failed', problem: p });
        }
        resolve();
      };
      xhr.onerror = () => {
        patchItem(item.id, {
          status:  'failed',
          problem: { title: 'Mạng lỗi khi upload', detail: item.file.name },
        });
        resolve();
      };

      xhr.open('POST', `${API_BASE}/api/v1/upload`);
      const tok = freshTok ?? window.localStorage.getItem('kaori.access_token') ?? window.localStorage.getItem('kaori_jwt');
      if (tok) xhr.setRequestHeader('Authorization', `Bearer ${tok}`);
      // Per-file Idempotency-Key — sha256 if computed (retry of same file is
      // dedup-safe), else item.id. No pipelineId yet — upload allocates one.
      const idem = item.sha256
        ? `upload-${item.sha256}`
        : `upload-${item.id}`;
      xhr.setRequestHeader('Idempotency-Key', idem);

      // P15-S11 Tuần 8 — workflow card attachment header. BE ingestor
      // validates the step belongs to the enterprise + writes a
      // workflow_step_documents row per bronze_file.
      if (workflowStepId) {
        xhr.setRequestHeader('X-Workflow-Step-ID', workflowStepId);
      }

      patchItem(item.id, { status: 'uploading', progress: 0, problem: undefined });
      xhr.send(fd);
    });
  }

  async function uploadAll() {
    setRunning(true);
    setProblem(null);
    // Snapshot the queue at submit time so newly-dropped files (during
    // the pass) get picked up on the next click rather than racing.
    const queue = items.filter((i) =>
      i.status === 'ready' || i.status === 'failed');
    for (const it of queue) {
      // Re-fetch latest item state in case user removed it mid-pass.
      const current = await new Promise<UploadItem | undefined>((resolve) =>
        setItems((prev) => { resolve(prev.find((p) => p.id === it.id)); return prev; }));
      if (!current || (current.status !== 'ready' && current.status !== 'failed')) continue;
      await uploadOne(current);
    }
    setRunning(false);
  }

  // -------------------------------------------------------------------------
  // Derived UI state
  // -------------------------------------------------------------------------

  const hashingCount  = items.filter((i) => i.status === 'hashing').length;
  const readyCount    = items.filter((i) => i.status === 'ready' || i.status === 'failed').length;
  const doneCount     = items.filter((i) => i.status === 'success' || i.status === 'duplicate').length;
  const allDone       = items.length > 0 && doneCount === items.length;
  const someActioned  = items.length > 0;

  // First successful (non-duplicate) result wins the "Sang Bước 2" CTA so
  // the user can advance. Duplicates and failures stay in the list for
  // review but don't claim the primary CTA.
  const advance = items.find((i) => i.status === 'success' || i.status === 'duplicate');

  return (
    <>
      <PageHeader
        title="Upload file"
        description={
          workflowCtx
            ? `Đang tải lên cho workflow "${workflowCtx.workflowName}" — bước "${workflowCtx.stepTitle}".`
            : 'Bước 1 / 5 — tải một hoặc nhiều file dữ liệu gốc để bắt đầu pipeline.'
        }
        actions={workflowId ? (
          <a href={`/p2/workflows/${workflowId}`}>
            <Button variant="tertiary" size="md">
              <ArrowLeft className="w-4 h-4 mr-2" /> Quay lại workflow
            </Button>
          </a>
        ) : null}
      />

      <div className="px-6 lg:px-8 py-6 max-w-[900px] mx-auto space-y-6">
        {/* No pipelineId at step 1 — backend allocates run_id on upload.
            Stepper shows step 1 active; previous-step links are inert here. */}
        <WizardStepper current={1} pipelineId="" />

        {workflowCtx && (
          <div className="bg-[var(--primary-gold)]/10 border border-[var(--primary-gold)]/40 rounded-md-custom p-3 flex items-start gap-3">
            <WorkflowIcon className="w-5 h-5 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0 text-xs">
              <p className="font-medium text-[var(--text-primary)]">
                Workflow: <span className="font-serif">{workflowCtx.workflowName}</span>
              </p>
              <p className="text-[var(--text-secondary)] mt-0.5">
                Bước: <span className="font-medium">{workflowCtx.stepTitle}</span>.
                {' '}File upload sẽ được gắn vào bước này — xem ở tab "Cây tài liệu" sau khi upload.
              </p>
            </div>
          </div>
        )}

        {problem && <ErrorBanner problem={problem} />}

        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            addFiles(e.dataTransfer.files);
          }}
          onClick={() => inputRef.current?.click()}
          className={cn(
            'rounded-lg-custom border-2 border-dashed p-12 text-center cursor-pointer transition-all',
            dragOver
              ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/8'
              : 'border-[var(--border-color)] hover:border-[var(--primary-gold)]/40 hover:bg-[var(--bg-app)]/40',
          )}
        >
          <input
            ref={inputRef}
            type="file"
            multiple
            accept={ACCEPT}
            onChange={(e) => {
              addFiles(e.target.files);
              // reset so re-picking the same file fires onChange again
              e.target.value = '';
            }}
            className="hidden"
          />
          <UploadCloud className="w-12 h-12 mx-auto text-[var(--primary-gold-dark)] mb-3" />
          <p className="font-serif text-lg text-[var(--text-primary)] mb-1">
            Kéo thả nhiều file vào đây
          </p>
          <p className="text-sm text-[var(--text-secondary)] mb-4">
            hoặc bấm để chọn từ máy tính (Ctrl/⌘+click để chọn nhiều)
          </p>
          <p className="text-xs text-[var(--text-secondary)]">
            CSV · Excel (.xlsx, .xls) · TSV · ZIP · tối đa 500 MB / file
          </p>
        </div>

        {someActioned && (
          <div className="rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] shadow-soft-sm">
            <div className="flex items-center justify-between px-5 py-3 border-b border-[var(--border-color)]">
              <h3 className="text-sm font-medium text-[var(--text-primary)] flex items-center gap-2">
                <FileSpreadsheet className="w-4 h-4 text-[var(--primary-gold-dark)]" />
                Hàng đợi ({items.length} file
                {items.length > 0 && doneCount > 0 && ` · ${doneCount} xong`}
                {hashingCount > 0 && ` · ${hashingCount} đang hash`})
              </h3>
              <Button
                onClick={uploadAll}
                isLoading={running}
                disabled={running || hashingCount > 0 || readyCount === 0}
                size="sm"
              >
                <UploadCloud className="w-4 h-4 mr-2" />
                Tải lên Bronze
                {readyCount > 0 && ` (${readyCount})`}
              </Button>
            </div>
            <ul className="divide-y divide-[var(--border-color)]/60">
              {items.map((it) => (
                <UploadRow
                  key={it.id}
                  item={it}
                  onRemove={() => removeItem(it.id)}
                  removable={!running && it.status !== 'uploading'}
                />
              ))}
            </ul>
          </div>
        )}

        {advance && (
          <div className="rounded-lg-custom bg-[var(--state-success)]/10 border border-[var(--state-success)]/30 p-5 shadow-soft-sm flex items-center justify-between gap-4">
            <p className="text-sm text-[#5C856A]">
              {allDone ? 'Mọi file đã sẵn sàng cho bước 2.' : 'Có file đã ingest xong — bạn có thể sang bước 2 ngay (các file còn lại vẫn tiếp tục).'}
            </p>
            <Button
              isLoading={navigating}
              onClick={() => {
                setNavigating(true);   // Step 2 fetches the schema on load (~3-4s) — give feedback now
                window.location.href =
                  advance.result?.next_step_path ||
                  `/p2/pipelines/${advance.result?.pipeline_run_id}/step-2-columns`;
              }}
            >
              {navigating ? 'Đang mở Bước 2…' : <>Sang Bước 2 — Cột<ChevronRight className="w-4 h-4 ml-2" /></>}
            </Button>
          </div>
        )}

        <div className="flex items-start gap-3 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            Mỗi file được lưu nguyên vẹn ở <span className="font-medium text-[var(--text-primary)]">Bronze layer</span> (append-only, K-2)
            và tạo một <span className="font-mono">pipeline_run</span> riêng. SHA-256 fingerprint chống upload trùng — nếu
            file đã tồn tại, hệ thống sẽ tái dùng record cũ thay vì ingest lại.
          </p>
        </div>
      </div>
    </>
  );
}

// ============================================================================
// Per-file row
// ============================================================================

function UploadRow({
  item: it, onRemove, removable,
}: {
  item: UploadItem;
  onRemove: () => void;
  removable: boolean;
}) {
  return (
    <li className="px-5 py-3 flex items-start gap-3">
      <FileSpreadsheet className="w-4 h-4 text-[var(--primary-gold-dark)] mt-1 shrink-0" />
      <div className="flex-1 min-w-0 space-y-1">
        <div className="flex items-baseline gap-2">
          <p className="text-sm font-medium text-[var(--text-primary)] truncate">{it.file.name}</p>
          <span className="text-[11px] text-[var(--text-secondary)]">{humanBytes(it.file.size)}</span>
        </div>

        {it.sha256 && (
          <p className="text-[10px] font-mono text-[var(--text-secondary)] truncate">
            sha256: {it.sha256.slice(0, 16)}…
          </p>
        )}

        {it.status === 'uploading' && (
          <div className="space-y-1">
            <div className="flex items-baseline justify-between text-[11px]">
              <span className="text-[var(--text-secondary)]">Đang upload...</span>
              <span className="font-medium text-[var(--text-primary)]">{it.progress}%</span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-[var(--border-color)]/40 overflow-hidden">
              <div
                className="h-full bg-[var(--primary-gold)] transition-all duration-200"
                style={{ width: `${it.progress}%` }}
              />
            </div>
          </div>
        )}

        {it.status === 'failed' && it.problem && (
          <p className="text-[11px] text-[var(--state-error)]">
            {it.problem.title}{it.problem.detail ? ` — ${it.problem.detail}` : ''}
          </p>
        )}

        {it.status === 'success' && it.result && (
          <p className="text-[11px] text-[#5C856A]">
            {/* Defensive: a 200 with a partial/odd body (or a detector that
                returned null) must NOT crash the React tree via .toUpperCase()
                on undefined. */}
            ✓ {(it.result.detected_format ?? '?').toUpperCase()} · {(it.result.rows ?? 0).toLocaleString('vi-VN')} hàng ·{' '}
            <a
              href={it.result.next_step_path || `/p2/pipelines/${it.result.pipeline_run_id}/step-2-columns`}
              className="text-[var(--primary-gold-dark)] hover:underline"
            >
              sang bước 2 →
            </a>
          </p>
        )}

        {it.status === 'duplicate' && it.result && (
          <p className="text-[11px] text-[#52647D]">
            ↺ File đã upload trước đó — tái dùng <span className="font-mono">{(it.result.bronze_file_id ?? '').slice(0, 8)}…</span>
          </p>
        )}
      </div>

      <StatusBadge status={it.status} />

      <button
        onClick={onRemove}
        disabled={!removable}
        title={removable ? 'Xoá khỏi hàng đợi' : 'Đang upload — không xoá được'}
        className="text-[var(--text-secondary)] hover:text-[var(--state-error)] disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
      >
        <X className="w-4 h-4" />
      </button>
    </li>
  );
}

function StatusBadge({ status }: { status: ItemStatus }) {
  if (status === 'hashing') return (
    <Badge variant="default"><Loader2 className="w-3 h-3 mr-1 animate-spin" /> Hash</Badge>
  );
  if (status === 'ready')   return <Badge variant="default">Sẵn sàng</Badge>;
  if (status === 'uploading') return (
    <Badge variant="info"><Loader2 className="w-3 h-3 mr-1 animate-spin" /> Tải lên</Badge>
  );
  if (status === 'success') return (
    <Badge variant="success"><CheckCircle2 className="w-3 h-3 mr-1" /> Mới</Badge>
  );
  if (status === 'duplicate') return (
    <Badge variant="info"><FileDigit className="w-3 h-3 mr-1" /> Trùng</Badge>
  );
  return (
    <Badge variant="error"><AlertCircle className="w-3 h-3 mr-1" /> Lỗi</Badge>
  );
}

function humanBytes(b: number): string {
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`;
  return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`;
}
