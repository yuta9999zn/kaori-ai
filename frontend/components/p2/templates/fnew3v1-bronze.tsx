'use client';

// ============================================================================
// /p2/data/bronze — Bronze drill-down (F-NEW3 v1 BE PR #146)
// ----------------------------------------------------------------------------
// Wires:
//   GET /api/v1/data/bronze/files?cursor=&limit=
//   GET /api/v1/data/bronze/files/{file_id}/sample?limit=
//
// Layout:
//   Header  → back link to /p2/data
//   Table   → bronze files (cursor-paginated, default 50/page)
//             columns: source filename · sheet · format · rows × cols ·
//                       run status badge · ingested at · "Xem mẫu" button
//   Modal   → first 50 rows of selected file (auto-detect columns from
//             first row's JSON keys), download CSV client-side button
//
// K-2 reminder: Bronze is append-only — this page is read-only by design.
// ============================================================================

import React, { useEffect, useMemo, useState } from 'react';
import {
  HardDrive, ArrowLeft, Eye, Loader2, ChevronLeft, ChevronRight,
  CheckCircle2, AlertCircle, Activity, X as XIcon, Download, Database,
  Link2,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, api, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import LineageModal from '@/components/p2/templates/fnew3v1-lineage-modal';
import { useT } from '@/lib/i18n/provider';

// ============================================================================
// Types — mirror BE data_explorer.py response
// ============================================================================

interface BronzeFile {
  file_id:           string;
  run_id:            string;
  source_filename:   string;
  run_status:        string;
  sheet_name:        string | null;
  sheet_index:       number;
  detected_purpose:  string | null;
  detected_language: string | null;
  row_count:         number;
  col_count:         number;
  file_format:       string;
  created_at:        string;
}

interface ListResponse {
  data: BronzeFile[];
  meta: { cursor: string | null; limit: number; count: number; has_more: boolean };
}

interface SampleResponse {
  data: {
    file: {
      file_id:         string;
      sheet_name:      string | null;
      row_count:       number;
      col_count:       number;
      file_format:     string;
      source_filename: string;
      created_at:      string;
    };
    rows: Array<{
      row_index:  number;
      raw_data:   Record<string, unknown>;
      row_hash:   string | null;
      created_at: string;
    }>;
    limit: number;
  };
}

const STATUS_VARIANT: Record<string, 'success' | 'warning' | 'error' | 'info' | 'current'> = {
  uploading:         'info',
  bronze_complete:   'success',
  schema_review:     'current',
  silver_complete:   'success',
  analyzing:         'warning',
  analysis_complete: 'success',
  failed:            'error',
  cancelled:         'error',
};
const STATUS_LABEL_KEY: Record<string, string> = {
  uploading:         'templatesFnew3v1Bronze.statusUploading',
  bronze_complete:   'templatesFnew3v1Bronze.statusBronzeComplete',
  schema_review:     'templatesFnew3v1Bronze.statusSchemaReview',
  silver_complete:   'templatesFnew3v1Bronze.statusSilverComplete',
  analyzing:         'templatesFnew3v1Bronze.statusAnalyzing',
  analysis_complete: 'templatesFnew3v1Bronze.statusAnalysisComplete',
  failed:            'templatesFnew3v1Bronze.statusFailed',
  cancelled:         'templatesFnew3v1Bronze.statusCancelled',
};

// ============================================================================
// Page
// ============================================================================

export default function BronzeDrillDownPage() {
  const t = useT();
  const [files, setFiles]               = useState<BronzeFile[]>([]);
  const [loading, setLoading]           = useState(true);
  const [problem, setProblem]           = useState<ProblemDetails | null>(null);
  const [nextCursor, setNextCursor]     = useState<string | null>(null);
  const [cursorStack, setCursorStack]   = useState<string[]>([]);
  const [selected, setSelected]         = useState<BronzeFile | null>(null);
  const [lineageFor, setLineageFor]     = useState<string | null>(null);

  async function loadList(cursor: string | null = null) {
    setLoading(true);
    setProblem(null);
    try {
      const params = new URLSearchParams({ limit: '50' });
      if (cursor) params.set('cursor', cursor);
      const r = await api<ListResponse>(`/api/v1/data/bronze/files?${params}`);
      setFiles(r.data ?? []);
      setNextCursor(r.meta.cursor);
    } catch (e) {
      setProblem(e as ProblemDetails);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setCursorStack([]);
    loadList(null);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function pageNext() {
    if (!nextCursor) return;
    setCursorStack((prev) => [...prev, nextCursor]);
    loadList(nextCursor);
  }
  function pagePrev() {
    if (cursorStack.length === 0) return;
    const prev = cursorStack.slice(0, -1);
    setCursorStack(prev);
    loadList(prev.at(-1) ?? null);
  }

  return (
    <>
      <PageHeader
        title={t('templatesFnew3v1Bronze.title')}
        description={t('templatesFnew3v1Bronze.description')}
        actions={
          <>
            <Badge variant="info">F-NEW3 v1</Badge>
            <a href="/p2/data">
              <Button variant="tertiary" size="md"><ArrowLeft className="w-4 h-4 mr-2" /> {t('templatesFnew3v1Bronze.backToExplore')}</Button>
            </a>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-6">
        {problem && <ErrorBanner problem={problem} />}

        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
          <div className="overflow-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-[var(--bg-app)] border-b border-[var(--border-color)] text-[11px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
                <tr>
                  <th className="px-5 py-3">{t('templatesFnew3v1Bronze.colSourceFile')}</th>
                  <th className="px-5 py-3">{t('templatesFnew3v1Bronze.colFormat')}</th>
                  <th className="px-5 py-3 text-right">{t('templatesFnew3v1Bronze.colRows')}</th>
                  <th className="px-5 py-3 text-right">{t('templatesFnew3v1Bronze.colCols')}</th>
                  <th className="px-5 py-3">{t('templatesFnew3v1Bronze.colStatus')}</th>
                  <th className="px-5 py-3">{t('templatesFnew3v1Bronze.colIngestedAt')}</th>
                  <th className="px-5 py-3 text-right">{t('templatesFnew3v1Bronze.colViewSample')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]/60">
                {loading && files.length === 0 ? (
                  <tr><td colSpan={7} className="px-5 py-12 text-center text-[var(--text-secondary)]">
                    <Loader2 className="w-5 h-5 animate-spin inline mr-2" /> {t('templatesFnew3v1Bronze.loadingFiles')}
                  </td></tr>
                ) : files.length === 0 ? (
                  <tr><td colSpan={7} className="px-5 py-12 text-center">
                    <Database className="w-10 h-10 mx-auto text-[var(--text-secondary)]/40 mb-3" />
                    <p className="text-sm text-[var(--text-secondary)]">
                      {t('templatesFnew3v1Bronze.emptyStatePrefix')}{' '}
                      <a href="/p2/pipelines/new" className="text-[var(--primary-gold-dark)] hover:underline">
                        {t('templatesFnew3v1Bronze.linkPipelineUpload')}
                      </a>.
                    </p>
                  </td></tr>
                ) : (
                  files.map((f) => (
                    <BronzeFileRow
                      key={f.file_id}
                      file={f}
                      onView={() => setSelected(f)}
                      onLineage={() => setLineageFor(f.file_id)}
                    />
                  ))
                )}
              </tbody>
            </table>
          </div>

          {(cursorStack.length > 0 || nextCursor) && (
            <div className="px-5 py-3 border-t border-[var(--border-color)] flex items-center justify-between">
              <Button
                variant="tertiary" size="sm" onClick={pagePrev}
                disabled={cursorStack.length === 0 || loading}
              >
                <ChevronLeft className="w-3.5 h-3.5 mr-1" /> {t('templatesFnew3v1Bronze.pagePrev')}
              </Button>
              <span className="text-xs text-[var(--text-secondary)]">
                {t('templatesFnew3v1Bronze.pageIndicator', { page: cursorStack.length + 1 })}
              </span>
              <Button
                variant="tertiary" size="sm" onClick={pageNext}
                disabled={!nextCursor || loading}
              >
                {t('templatesFnew3v1Bronze.pageNext')} <ChevronRight className="w-3.5 h-3.5 ml-1" />
              </Button>
            </div>
          )}
        </div>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <HardDrive className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            {t('templatesFnew3v1Bronze.footerNotePrefix')}{' '}
            <a href="/p2/data" className="text-[var(--primary-gold-dark)] hover:underline">{t('templatesFnew3v1Bronze.linkPipeline')}</a>.
            {' '}{t('templatesFnew3v1Bronze.footerNoteSuffix')}
          </p>
        </div>
      </div>

      {selected && (
        <SampleModal file={selected} onClose={() => setSelected(null)} />
      )}

      {lineageFor && (
        <LineageModal fileId={lineageFor} onClose={() => setLineageFor(null)} />
      )}
    </>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

function BronzeFileRow({
  file: f, onView, onLineage,
}: { file: BronzeFile; onView: () => void; onLineage: () => void }) {
  const t = useT();
  const variant = STATUS_VARIANT[f.run_status] ?? 'default';
  const label   = STATUS_LABEL_KEY[f.run_status] ? t(STATUS_LABEL_KEY[f.run_status]) : f.run_status;
  const ingested = formatRelative(f.created_at);

  return (
    <tr className="hover:bg-[var(--bg-app)]/40 transition-colors">
      <td className="px-5 py-4">
        <p className="text-sm font-medium text-[var(--text-primary)]">{f.source_filename}</p>
        <p className="text-[11px] text-[var(--text-secondary)] mt-0.5 font-mono">
          {f.file_id.slice(0, 8)}... {f.sheet_name ? `· ${f.sheet_name}` : ''}{f.detected_purpose ? ` · ${f.detected_purpose}` : ''}
        </p>
      </td>
      <td className="px-5 py-4">
        <span className="text-xs uppercase font-medium text-[var(--text-secondary)]">{f.file_format}</span>
      </td>
      <td className="px-5 py-4 text-right text-sm text-[var(--text-primary)]">
        {f.row_count.toLocaleString('vi-VN')}
      </td>
      <td className="px-5 py-4 text-right text-sm text-[var(--text-primary)]">
        {f.col_count}
      </td>
      <td className="px-5 py-4">
        <Badge variant={variant}>{label}</Badge>
      </td>
      <td className="px-5 py-4 text-xs text-[var(--text-secondary)]">{ingested}</td>
      <td className="px-5 py-4 text-right">
        <div className="inline-flex items-center gap-1">
          <Button variant="tertiary" size="sm" onClick={onLineage} title={t('templatesFnew3v1Bronze.lineageTooltip')}>
            <Link2 className="w-3.5 h-3.5" />
          </Button>
          <Button variant="tertiary" size="sm" onClick={onView}>
            <Eye className="w-3.5 h-3.5 mr-1.5" /> {t('templatesFnew3v1Bronze.viewButton')}
          </Button>
        </div>
      </td>
    </tr>
  );
}

function SampleModal({ file, onClose }: { file: BronzeFile; onClose: () => void }) {
  const t = useT();
  const [data, setData]       = useState<SampleResponse['data'] | null>(null);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await api<SampleResponse>(
          `/api/v1/data/bronze/files/${file.file_id}/sample?limit=50`);
        setData(r.data);
      } catch (e) {
        setProblem(e as ProblemDetails);
      } finally {
        setLoading(false);
      }
    })();
  }, [file.file_id]);

  // Auto-detect columns from first row's JSON keys.
  const columns = useMemo(() => {
    if (!data?.rows.length) return [];
    return Object.keys(data.rows[0].raw_data);
  }, [data]);

  function downloadCsv() {
    if (!data) return;
    const header = columns.map(quoteCsv).join(',');
    const lines  = data.rows.map((r) =>
      columns.map((c) => quoteCsv(formatCell(r.raw_data[c]))).join(','),
    );
    const csv = [header, ...lines].join('\r\n');
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `${file.source_filename.replace(/\.[^.]+$/, '')}-sample.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 animate-fade-in">
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-2xl max-w-5xl w-full max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border-color)]">
          <div className="min-w-0">
            <h3 className="font-serif text-lg text-[var(--text-primary)] truncate">
              {file.source_filename}
            </h3>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              {t('templatesFnew3v1Bronze.rowsColsSummary', { rows: file.row_count.toLocaleString('vi-VN'), cols: file.col_count })} ·{' '}
              {file.file_format.toUpperCase()}
              {file.sheet_name && ` · sheet "${file.sheet_name}"`}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button
              variant="tertiary" size="sm" onClick={downloadCsv}
              disabled={!data || data.rows.length === 0}
            >
              <Download className="w-3.5 h-3.5 mr-1" /> {t('templatesFnew3v1Bronze.csvSampleButton')}
            </Button>
            <button onClick={onClose} aria-label={t('templatesFnew3v1Bronze.closeModal')} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
              <XIcon className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-auto p-5">
          {problem && <ErrorBanner problem={problem} />}

          {loading ? (
            <div className="text-center py-12 text-[var(--text-secondary)]">
              <Loader2 className="w-5 h-5 animate-spin inline mr-2" /> {t('templatesFnew3v1Bronze.loadingSample')}
            </div>
          ) : data && data.rows.length > 0 ? (
            <>
              <div className="overflow-auto border border-[var(--border-color)] rounded-md-custom">
                <table className="text-xs text-left w-full">
                  <thead className="bg-[var(--bg-app)] sticky top-0">
                    <tr>
                      <th className="px-3 py-2 font-medium text-[var(--text-secondary)] border-b border-[var(--border-color)]">#</th>
                      {columns.map((c) => (
                        <th key={c} className="px-3 py-2 font-medium text-[var(--text-secondary)] border-b border-[var(--border-color)] whitespace-nowrap">
                          {c}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-color)]/40">
                    {data.rows.map((r) => (
                      <tr key={r.row_index} className="hover:bg-[var(--bg-app)]/40">
                        <td className="px-3 py-1.5 font-mono text-[var(--text-secondary)]">{r.row_index + 1}</td>
                        {columns.map((c) => (
                          <td key={c} className="px-3 py-1.5 text-[var(--text-primary)] whitespace-nowrap max-w-xs truncate">
                            {formatCell(r.raw_data[c])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-[11px] text-[var(--text-secondary)] mt-3">
                {t('templatesFnew3v1Bronze.sampleFooter', {
                  shown: data.rows.length,
                  total: data.file.row_count.toLocaleString('vi-VN'),
                  limit: data.limit,
                })}
              </p>
            </>
          ) : (
            <div className="text-center py-12 text-[var(--text-secondary)]">
              {t('templatesFnew3v1Bronze.noRowsMessage')}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Helpers
// ============================================================================

function formatRelative(iso: string | null): string {
  if (!iso) return '—';
  const diff = Date.now() - +new Date(iso);
  if (Number.isNaN(diff))     return iso;
  if (diff < 60_000)          return 'vừa xong';
  if (diff < 3_600_000)       return `${Math.round(diff / 60_000)} phút trước`;
  if (diff < 86_400_000)      return `${Math.round(diff / 3_600_000)} giờ trước`;
  if (diff < 7 * 86_400_000)  return `${Math.round(diff / 86_400_000)} ngày trước`;
  return new Date(iso).toLocaleDateString('vi-VN');
}

function formatCell(v: unknown): string {
  if (v === null || v === undefined) return '';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

function quoteCsv(value: string): string {
  if (value === '' || value == null) return '';
  if (/[",\r\n]/.test(value)) return '"' + value.replace(/"/g, '""') + '"';
  return value;
}
