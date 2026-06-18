// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 15. /p2/data/bronze — Bronze layer (raw ingested files, K-2 append-only)
// ----------------------------------------------------------------------------
// GET /api/v1/data/bronze/files (cursor)
// GET /api/v1/data/bronze/files/:id (preview rows + schema + ingest log)
// POST /api/v1/data/bronze/files/:id/replay (re-run ingestion — does NOT mutate
//   the original Bronze record; produces a new run row per K-2)
//
// K-2 critical:
//   - NO Edit / NO Delete buttons
//   - "Replay ingest" is the only mutation — it APPENDS a new bronze_files row
//   - SHA-256 fingerprint visible per file (K-8 dedup origin)
//   - Append-only banner at top of page so users know why edits are absent
// ============================================================================

import React, { useState, useEffect } from 'react';
import {
  HardDrive, Search, Filter, RefreshCw, Eye, PlayCircle, ShieldCheck,
  FileDigit, AlertCircle, CheckCircle2, Clock, X, ChevronRight,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, Input,
  api, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
type BronzeStatus = 'ingested' | 'parsing' | 'ready' | 'failed';

interface BronzeFile {
  id:          string;
  filename:    string;
  source:      string;     // upload | api | s3 | kafka | snowflake
  format:      string;     // csv | parquet | json
  rows:        number;
  size_bytes:  number;
  sha256:      string;     // K-8 fingerprint
  ingested_at: string;
  status:      BronzeStatus;
  error?:      string;
}

const STATUS_BADGE: Record<BronzeStatus, any> = {
  ingested: { variant: 'info',    label: 'Đã nhận' },
  parsing:  { variant: 'warning', label: 'Đang parse' },
  ready:    { variant: 'success', label: 'Sẵn sàng' },
  failed:   { variant: 'error',   label: 'Lỗi' },
};

export default function DataBronze() {
  const [files,   setFiles]   = useState<BronzeFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [search,  setSearch]  = useState('');
  const [statusFilter, setStatusFilter] = useState<BronzeStatus | 'all'>('all');
  const [selected, setSelected] = useState<BronzeFile | null>(null);
  const [isReplaying, setIsReplaying] = useState(false);

  async function load() {
    setLoading(true);
    setProblem(null);
    try {
      const res = await api<{ data: BronzeFile[] }>('/api/v1/data/bronze/files?limit=200');
      setFiles(res.data ?? []);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  const filtered = files.filter((f) => {
    if (statusFilter !== 'all' && f.status !== statusFilter) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      if (!f.filename.toLowerCase().includes(q) && !f.sha256.toLowerCase().includes(q)) return false;
    }
    return true;
  });

  async function handleReplay(f: BronzeFile) {
    setIsReplaying(true);
    setProblem(null);
    try {
      await api(`/api/v1/data/bronze/files/${f.id}/replay`, { method: 'POST' });
      await load();
      setSelected(null);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setIsReplaying(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Bronze — dữ liệu thô"
        description="Lớp ingest đầu tiên. Append-only — mọi file gốc được giữ nguyên, không sửa, không xoá."
        actions={
          <Button variant="secondary" onClick={load} disabled={loading}>
            <RefreshCw className={'w-4 h-4 mr-2 ' + (loading ? 'animate-spin' : '')} />
            Làm mới
          </Button>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-4">
        {/* K-2 banner — never hide, this is a guarantee */}
        <div className="rounded-md-custom bg-[var(--state-info)]/10 border border-[var(--state-info)]/30 p-4 flex items-start gap-3">
          <ShieldCheck className="w-5 h-5 text-[var(--state-info)] shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-medium text-[#52647D]">Bronze là append-only (K-2)</p>
            <p className="text-xs text-[#52647D]/90 mt-0.5">
              File gốc không bao giờ bị sửa hay xoá. Để xử lý lại, dùng <span className="font-medium">Replay</span> — Kaori sẽ tạo một lần ingest mới đè lên dữ liệu cũ ở Silver, nhưng bản gốc Bronze vẫn nguyên vẹn để có thể truy ngược (audit + replay) sau này.
            </p>
          </div>
        </div>

        <ErrorBanner problem={problem} />

        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Tìm theo tên file hoặc SHA-256..."
              className="w-full bg-[var(--bg-card)] border border-[var(--border-color)] rounded-md-custom pl-9 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)]"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as any)}
            className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-md-custom px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
          >
            <option value="all">Tất cả trạng thái</option>
            <option value="ingested">Đã nhận</option>
            <option value="parsing">Đang parse</option>
            <option value="ready">Sẵn sàng</option>
            <option value="failed">Lỗi</option>
          </select>
        </div>

        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] overflow-hidden shadow-soft-sm">
          {loading ? (
            <div className="p-6 space-y-3">
              {[1,2,3,4].map((i) => <div key={i} className="h-14 rounded-md-custom bg-[var(--bg-app)]/60 animate-pulse" />)}
            </div>
          ) : filtered.length === 0 ? (
            <p className="p-12 text-center text-[var(--text-secondary)]">Chưa có file Bronze nào khớp bộ lọc.</p>
          ) : (
            <table className="w-full">
              <thead className="bg-[var(--bg-app)]/50 border-b border-[var(--border-color)]">
                <tr>
                  <Th>File</Th>
                  <Th>Nguồn</Th>
                  <Th>Hàng</Th>
                  <Th>SHA-256</Th>
                  <Th>Ingested</Th>
                  <Th>Trạng thái</Th>
                  <Th></Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]/60">
                {filtered.map((f) => {
                  const meta = STATUS_BADGE[f.status];
                  return (
                    <tr key={f.id} className="hover:bg-[var(--bg-app)]/40 cursor-pointer" onClick={() => setSelected(f)}>
                      <Td>
                        <div className="flex items-center gap-3">
                          <FileDigit className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0" />
                          <div>
                            <p className="text-sm font-medium text-[var(--text-primary)]">{f.filename}</p>
                            <p className="text-[11px] text-[var(--text-secondary)]">{f.format.toUpperCase()} · {humanBytes(f.size_bytes)}</p>
                          </div>
                        </div>
                      </Td>
                      <Td><span className="text-sm text-[var(--text-secondary)]">{f.source}</span></Td>
                      <Td><span className="text-sm font-mono text-[var(--text-primary)]">{f.rows.toLocaleString('vi-VN')}</span></Td>
                      <Td>
                        <span className="text-[11px] font-mono text-[var(--text-secondary)]" title={f.sha256}>
                          {f.sha256.slice(0, 12)}…
                        </span>
                      </Td>
                      <Td><span className="text-sm text-[var(--text-secondary)]">{f.ingested_at}</span></Td>
                      <Td><Badge variant={meta.variant}>{meta.label}</Badge></Td>
                      <Td><ChevronRight className="w-4 h-4 text-[var(--text-secondary)]" /></Td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {selected && (
        <FileDrawer
          file={selected}
          onClose={() => setSelected(null)}
          onReplay={() => handleReplay(selected)}
          isReplaying={isReplaying}
        />
      )}
    </>
  );
}

function FileDrawer({ file, onClose, onReplay, isReplaying }: any) {
  const meta = STATUS_BADGE[file.status];
  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30" />
      <aside
        className="relative w-full max-w-[560px] bg-[var(--bg-card)] border-l border-[var(--border-color)] overflow-y-auto animate-slide-in-right"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 bg-[var(--bg-card)] border-b border-[var(--border-color)] p-5 flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <h2 className="font-serif text-lg text-[var(--text-primary)] truncate">{file.filename}</h2>
            <div className="flex items-center gap-2 mt-1">
              <Badge variant={meta.variant}>{meta.label}</Badge>
              <span className="text-xs text-[var(--text-secondary)]">{file.format.toUpperCase()} · {humanBytes(file.size_bytes)}</span>
            </div>
          </div>
          <button onClick={onClose} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-5">
          {file.error && (
            <div className="rounded-md-custom bg-[var(--state-error)]/10 border border-[var(--state-error)]/30 p-3 flex items-start gap-3">
              <AlertCircle className="w-4 h-4 text-[var(--state-error)] shrink-0 mt-0.5" />
              <p className="text-sm text-[#9B5050]">{file.error}</p>
            </div>
          )}

          <Section title="Định danh">
            <Field label="ID" value={file.id} mono />
            <Field label="SHA-256 (K-8 fingerprint)" value={file.sha256} mono wrap />
            <Field label="Nguồn" value={file.source} />
            <Field label="Định dạng" value={file.format.toUpperCase()} />
          </Section>

          <Section title="Số liệu">
            <Field label="Số hàng" value={file.rows.toLocaleString('vi-VN')} />
            <Field label="Dung lượng" value={humanBytes(file.size_bytes)} />
            <Field label="Ingested" value={file.ingested_at} />
          </Section>

          <div className="border-t border-[var(--border-color)]/60 pt-5">
            <p className="text-xs text-[var(--text-secondary)] mb-3 leading-relaxed">
              File Bronze không thể sửa hoặc xoá (K-2). Replay sẽ tạo một bản record mới ở Silver dựa trên file gốc — bản Bronze này vẫn giữ nguyên cho audit.
            </p>
            <Button onClick={onReplay} isLoading={isReplaying} className="w-full">
              <PlayCircle className="w-4 h-4 mr-2" />
              Replay ingest
            </Button>
          </div>
        </div>
      </aside>
    </div>
  );
}

function Section({ title, children }: any) {
  return (
    <div>
      <h3 className="text-[11px] uppercase tracking-wider font-semibold text-[var(--text-secondary)] mb-2">{title}</h3>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function Field({ label, value, mono, wrap }: any) {
  return (
    <div className="flex items-start justify-between gap-3 text-sm">
      <span className="text-[var(--text-secondary)]">{label}</span>
      <span className={cn('text-[var(--text-primary)] text-right', mono && 'font-mono text-xs', wrap && 'break-all')}>{value}</span>
    </div>
  );
}

function humanBytes(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`;
  return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function Th({ children }: any) {
  return <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">{children}</th>;
}
function Td({ children, className }: any) {
  return <td className={cn('px-5 py-3', className)}>{children}</td>;
}
