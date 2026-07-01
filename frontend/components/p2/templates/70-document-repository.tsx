// @ts-nocheck — template; tighten types when wiring to real API
// ADR-0039 — Kho tài liệu (enterprise Document Repository / DMS).
// Lazy breadcrumb browser: load a folder's direct children + files on navigate
// (never the whole tree). Create folder, upload into folder, search.
'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Folder, FolderPlus, Upload, FileText, ChevronRight, ChevronDown, Home, Search,
  Loader2, Trash2, ExternalLink, CalendarDays, ListTree,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, cn, api, API_BASE, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';

interface FolderRow {
  folder_id: string; name_vi: string; path: string;
  child_count: number; file_count: number;
}
interface FileRow {
  doc_id: string; name_vi: string; doc_type: string | null;
  status: string; version: number; storage_tier: string; uploaded_at: string | null;
  doc_date: string | null; period_kind: string | null;
}
interface Crumb { folder_id: string; name_vi: string; }

const TOKEN_KEY = 'kaori.access_token';

// Mig 138 — time is METADATA, not tree depth. `doc_date` = business date
// (báo cáo ngày 30/06 có thể upload 02/07); period_kind = kỳ báo cáo.
const PERIOD_LABEL: Record<string, string> = {
  day: 'Ngày', week: 'Tuần', month: 'Tháng', quarter: 'Quý', year: 'Năm',
};

function dateQS(dateFrom: string, dateTo: string, periodKind: string): string {
  const p = new URLSearchParams();
  if (dateFrom) p.set('date_from', dateFrom);
  if (dateTo) p.set('date_to', dateTo);
  if (periodKind) p.set('period_kind', periodKind);
  const s = p.toString();
  return s ? `&${s}` : '';
}

export default function DocumentRepositoryPage() {
  const [current, setCurrent] = useState<string | null>(null);   // null = root
  const [crumbs, setCrumbs] = useState<Crumb[]>([]);
  const [folders, setFolders] = useState<FolderRow[]>([]);
  const [files, setFiles] = useState<FileRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [creating, setCreating] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [search, setSearch] = useState('');
  const [results, setResults] = useState<any[] | null>(null);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [periodKind, setPeriodKind] = useState('');
  const [view, setView] = useState<'tree' | 'time'>('tree');
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setProblem(null);
    setResults(null);
    try {
      const fRes = await api<{ items: FolderRow[] }>(
        `/api/v1/document-folders${current ? `?parent_id=${current}` : ''}`);
      setFolders(fRes.items || []);
      if (current) {
        const [filesRes, crumbRes] = await Promise.all([
          api<{ items: FileRow[] }>(
            `/api/v1/document-folders/${current}/files?limit=200${dateQS(dateFrom, dateTo, '')}`),
          api<{ items: Crumb[] }>(`/api/v1/document-folders/${current}/breadcrumb`),
        ]);
        setFiles(filesRes.items || []);
        setCrumbs(crumbRes.items || []);
      } else {
        setFiles([]);
        setCrumbs([]);
      }
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }, [current, dateFrom, dateTo]);

  useEffect(() => { load(); }, [load]);

  async function createFolder() {
    const name = window.prompt('Tên thư mục mới (vd "Tài chính", "2024", "Quý 1"):');
    if (!name?.trim()) return;
    setCreating(true);
    try {
      await api('/api/v1/document-folders', {
        method: 'POST',
        body: JSON.stringify({ name_vi: name.trim(), parent_id: current }),
      });
      await load();
    } catch (err: any) {
      setProblem(err);
    } finally {
      setCreating(false);
    }
  }

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    e.target.value = '';
    if (!f || !current) return;
    setUploading(true);
    setProblem(null);
    try {
      let hint = '';
      try {
        const dig = await crypto.subtle.digest('SHA-256', await f.arrayBuffer());
        hint = Array.from(new Uint8Array(dig)).map((b) => b.toString(16).padStart(2, '0')).join('');
      } catch { /* best-effort */ }
      const fd = new FormData();
      fd.append('file', f);
      if (hint) fd.append('sha256_hint', hint);
      const res = await fetch(`${API_BASE}/api/v1/upload`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${window.localStorage.getItem(TOKEN_KEY) ?? ''}`,
          'X-Folder-ID': current,
          'Idempotency-Key': `repo-${hint || crypto.randomUUID()}`,
        },
        body: fd,
      });
      if (!res.ok) {
        let detail = `HTTP ${res.status}`;
        try { const j = await res.json(); detail = (typeof j.detail === 'string' ? j.detail : j.detail?.message) || j.title || detail; } catch {}
        throw { title: detail } as ProblemDetails;
      }
      await load();
    } catch (err: any) {
      setProblem(err.title ? err : { title: err?.message || 'Tải lên thất bại' });
    } finally {
      setUploading(false);
    }
  }

  async function delFolder(id: string, name: string) {
    if (!window.confirm(`Xoá thư mục "${name}" và toàn bộ bên trong? (xoá mềm)`)) return;
    try {
      await api(`/api/v1/document-folders/${id}`, { method: 'DELETE' });
      await load();
    } catch (err: any) { setProblem(err); }
  }

  async function runSearch() {
    // Filters count as a query too — "mọi báo cáo tuần của quý 2" needs no name.
    if (!search.trim() && !dateFrom && !dateTo && !periodKind) { setResults(null); return; }
    try {
      const r = await api<{ items: any[] }>(
        `/api/v1/document-repository/search?q=${encodeURIComponent(search.trim())}${dateQS(dateFrom, dateTo, periodKind)}`);
      setResults(r.items || []);
    } catch (err: any) { setProblem(err); }
  }

  async function setDocMeta(docId: string, patch: { doc_date?: string; period_kind?: string }) {
    try {
      await api(`/api/v1/document-repository/${docId}`, {
        method: 'PATCH',
        body: JSON.stringify(patch),
      });
      await load();
    } catch (err: any) { setProblem(err); }
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Kho tài liệu"
        description="Lưu trữ tài liệu doanh nghiệp theo cây thư mục (Năm → Quý → Loại hồ sơ) — dùng chung kho byte Bronze, chống trùng SHA-256."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="secondary" onClick={createFolder} disabled={creating}>
              {creating ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <FolderPlus className="w-4 h-4 mr-1.5" />}
              Tạo thư mục
            </Button>
            {current && (
              <>
                <input ref={fileRef} type="file" hidden onChange={onUpload}
                  accept=".pdf,.docx,.doc,.xlsx,.xls,.csv,.png,.jpg,.jpeg,.tiff,.webp,.pptx,.md,.json,.sql,.zip" />
                <Button onClick={() => fileRef.current?.click()} disabled={uploading}>
                  {uploading ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Upload className="w-4 h-4 mr-1.5" />}
                  Tải lên
                </Button>
              </>
            )}
          </div>
        }
      />

      {/* search + date filters (mig 138 — lọc theo ngày nghiệp vụ, không phải ngày upload) */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="relative flex-1 max-w-md min-w-[220px]">
          <Search className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && runSearch()}
            placeholder="Tìm tài liệu theo tên…"
            className="w-full pl-9 pr-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
          />
        </div>
        <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)}
          title="Từ ngày (theo ngày chứng từ)"
          className="px-2 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm text-[var(--text-secondary)]" />
        <span className="text-xs text-[var(--text-secondary)]">→</span>
        <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)}
          title="Đến ngày"
          className="px-2 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm text-[var(--text-secondary)]" />
        <select value={periodKind} onChange={(e) => setPeriodKind(e.target.value)}
          title="Kỳ báo cáo"
          className="px-2 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm text-[var(--text-secondary)]">
          <option value="">Mọi kỳ</option>
          <option value="day">Báo cáo ngày</option>
          <option value="week">Báo cáo tuần</option>
          <option value="month">Báo cáo tháng</option>
          <option value="quarter">Báo cáo quý</option>
          <option value="year">Báo cáo năm</option>
        </select>
        <Button variant="secondary" onClick={runSearch}>Tìm</Button>
        {(dateFrom || dateTo || periodKind) && (
          <button onClick={() => { setDateFrom(''); setDateTo(''); setPeriodKind(''); setResults(null); }}
            className="text-xs text-[var(--text-secondary)] hover:text-[var(--state-error)] underline">
            Xoá lọc
          </button>
        )}
        <div className="ml-auto flex items-center rounded-md-custom border border-[var(--border-color)] overflow-hidden">
          <button onClick={() => setView('tree')}
            className={cn('px-2.5 py-2 text-xs flex items-center gap-1.5',
              view === 'tree' ? 'bg-[var(--primary-gold)]/15 text-[var(--primary-gold-dark)] font-medium' : 'bg-white text-[var(--text-secondary)]')}>
            <ListTree className="w-3.5 h-3.5" /> Cây thư mục
          </button>
          <button onClick={() => setView('time')}
            className={cn('px-2.5 py-2 text-xs flex items-center gap-1.5',
              view === 'time' ? 'bg-[var(--primary-gold)]/15 text-[var(--primary-gold-dark)] font-medium' : 'bg-white text-[var(--text-secondary)]')}>
            <CalendarDays className="w-3.5 h-3.5" /> Theo thời gian
          </button>
        </div>
      </div>

      {/* breadcrumb */}
      <div className="flex items-center gap-1 text-sm text-[var(--text-secondary)] flex-wrap">
        <button onClick={() => setCurrent(null)} className="inline-flex items-center gap-1 hover:text-[var(--primary-gold-dark)]">
          <Home className="w-3.5 h-3.5" /> Kho
        </button>
        {crumbs.map((c) => (
          <React.Fragment key={c.folder_id}>
            <ChevronRight className="w-3.5 h-3.5 opacity-50" />
            <button onClick={() => setCurrent(c.folder_id)}
              className={cn('hover:text-[var(--primary-gold-dark)]', c.folder_id === current && 'text-[var(--text-primary)] font-medium')}>
              {c.name_vi}
            </button>
          </React.Fragment>
        ))}
      </div>

      {problem && <ErrorBanner problem={problem} />}

      {loading ? (
        <div className="py-10 text-center text-[var(--text-secondary)]"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : results !== null ? (
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-4">
          <p className="text-xs text-[var(--text-secondary)] mb-2">
            {results.length} kết quả{search.trim() ? ` cho “${search}”` : ''}
            {(dateFrom || dateTo) && ` · ${dateFrom || '…'} → ${dateTo || '…'}`}
            {periodKind && ` · ${PERIOD_LABEL[periodKind]}`}
          </p>
          {results.map((r) => (
            <button key={r.doc_id} onClick={() => setCurrent(r.folder_id)}
              className="w-full flex items-center gap-2 px-2 py-2 rounded hover:bg-[var(--bg-app)]/50 text-left">
              <FileText className="w-4 h-4 text-emerald-700 shrink-0" />
              <span className="text-sm flex-1 truncate">{r.name_vi}</span>
              {r.doc_date && (
                <span className="text-[10px] text-[var(--text-secondary)] shrink-0 inline-flex items-center gap-1">
                  <CalendarDays className="w-3 h-3" />{r.doc_date}
                </span>
              )}
              {r.period_kind && <Badge variant="default" className="text-[10px] shrink-0">{PERIOD_LABEL[r.period_kind]}</Badge>}
              <span className="text-[10px] text-[var(--text-secondary)] font-mono truncate">{r.path}</span>
            </button>
          ))}
        </div>
      ) : view === 'time' ? (
        <TimeTree
          periodKind={periodKind}
          onPick={async (from, to) => {
            // A bucket click lists that period's documents across ALL folders.
            setDateFrom(from); setDateTo(to);
            try {
              const r = await api<{ items: any[] }>(
                `/api/v1/document-repository/search?q=${dateQS(from, to, periodKind)}`);
              setResults(r.items || []);
            } catch (err: any) { setProblem(err); }
          }}
        />
      ) : (
        <div className="space-y-3">
          {/* folders */}
          {folders.length === 0 && files.length === 0 ? (
            <div className="py-10 text-center text-[var(--text-secondary)] text-sm">
              {current ? 'Thư mục trống. Tạo thư mục con hoặc tải tài liệu lên.' : 'Chưa có thư mục nào. Bấm “Tạo thư mục” để bắt đầu (vd theo Năm → Quý → Loại hồ sơ).'}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {folders.map((f) => (
                <div key={f.folder_id}
                  className="group flex items-center gap-2 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-md-custom px-3 py-2.5 hover:border-[var(--primary-gold)]/50">
                  <button onClick={() => setCurrent(f.folder_id)} className="flex items-center gap-2 flex-1 min-w-0 text-left">
                    <Folder className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0" />
                    <span className="text-sm font-medium truncate">{f.name_vi}</span>
                    <span className="text-[10px] text-[var(--text-secondary)] shrink-0">{f.child_count} mục · {f.file_count} file</span>
                  </button>
                  <button onClick={() => delFolder(f.folder_id, f.name_vi)}
                    className="opacity-0 group-hover:opacity-100 text-[var(--text-secondary)] hover:text-[var(--state-error)] shrink-0">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* files in current folder — TimeTree defined at file bottom */}
          {files.length > 0 && (
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom divide-y divide-[var(--border-color)]/50">
              {files.map((d) => (
                <div key={d.doc_id} className="flex items-center gap-2 px-3 py-2.5">
                  <FileText className="w-4 h-4 text-emerald-700 shrink-0" />
                  <span className="text-sm flex-1 truncate">{d.name_vi}</span>
                  {/* mig 138 — ngày chứng từ + kỳ, sửa inline (khác ngày upload) */}
                  <input type="date" value={d.doc_date || ''}
                    onChange={(e) => e.target.value && setDocMeta(d.doc_id, { doc_date: e.target.value })}
                    title="Ngày chứng từ của tài liệu (báo cáo ngày 30/06 upload 02/07 → chọn 30/06)"
                    className="px-1.5 py-0.5 text-[11px] bg-transparent border border-[var(--border-color)]/60 rounded text-[var(--text-secondary)] shrink-0" />
                  <select value={d.period_kind || ''}
                    onChange={(e) => e.target.value && setDocMeta(d.doc_id, { period_kind: e.target.value })}
                    title="Kỳ báo cáo"
                    className="px-1 py-0.5 text-[11px] bg-transparent border border-[var(--border-color)]/60 rounded text-[var(--text-secondary)] shrink-0">
                    <option value="">— kỳ —</option>
                    <option value="day">Ngày</option>
                    <option value="week">Tuần</option>
                    <option value="month">Tháng</option>
                    <option value="quarter">Quý</option>
                    <option value="year">Năm</option>
                  </select>
                  {d.version > 1 && <span className="text-[10px] font-mono text-[var(--text-secondary)]">v{d.version}</span>}
                  {d.doc_type && <Badge variant="default" className="text-[10px]">.{d.doc_type}</Badge>}
                  {d.storage_tier !== 'hot' && <span className="text-[10px] text-[var(--text-secondary)]">{d.storage_tier}</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════
// TimeTree — cây ẢO Năm → Quý → Tháng → Ngày (mig 138).
// Thời gian là metadata, không phải folder vật lý: mỗi cấp là một lần
// GROUP BY trên COALESCE(doc_date, uploaded_at) — không nổ thư mục,
// và báo cáo tuần (vắt qua 2 tháng) vẫn lọc được qua kỳ/khoảng ngày.
// ═══════════════════════════════════════════════════════════════════

interface Bucket { doc_count: number; year: number; quarter?: number; month?: number; day?: number; }

function bucketRange(b: Bucket): [string, string] {
  const pad = (n: number) => String(n).padStart(2, '0');
  if (b.day != null) {
    const d = `${b.year}-${pad(b.month!)}-${pad(b.day)}`;
    return [d, d];
  }
  if (b.month != null) {
    const last = new Date(b.year, b.month, 0).getDate();
    return [`${b.year}-${pad(b.month)}-01`, `${b.year}-${pad(b.month)}-${pad(last)}`];
  }
  if (b.quarter != null) {
    const m0 = (b.quarter - 1) * 3 + 1;
    const last = new Date(b.year, m0 + 2, 0).getDate();
    return [`${b.year}-${pad(m0)}-01`, `${b.year}-${pad(m0 + 2)}-${pad(last)}`];
  }
  return [`${b.year}-01-01`, `${b.year}-12-31`];
}

function bucketLabel(b: Bucket): string {
  if (b.day != null) return `Ngày ${String(b.day).padStart(2, '0')}`;
  if (b.month != null) return `Tháng ${b.month}`;
  if (b.quarter != null) return `Quý ${b.quarter}`;
  return `Năm ${b.year}`;
}

function bucketKey(b: Bucket): string {
  return [b.year, b.quarter ?? '', b.month ?? '', b.day ?? ''].join('-');
}

function TimeTree({ periodKind, onPick }: {
  periodKind: string;
  onPick: (from: string, to: string) => void;
}) {
  const NEXT: Record<string, string | null> = { year: 'quarter', quarter: 'month', month: 'day', day: null };
  const [years, setYears] = useState<Bucket[] | null>(null);
  const [children, setChildren] = useState<Record<string, Bucket[]>>({});
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [err, setErr] = useState<ProblemDetails | null>(null);

  useEffect(() => {
    api<{ buckets: Bucket[] }>('/api/v1/document-repository/timeline?granularity=year')
      .then((r) => setYears(r.buckets || []))
      .catch(setErr);
  }, []);

  async function toggle(b: Bucket, level: string) {
    const key = bucketKey(b);
    if (open[key]) { setOpen((o) => ({ ...o, [key]: false })); return; }
    setOpen((o) => ({ ...o, [key]: true }));
    const next = NEXT[level];
    if (!next || children[key]) return;
    const p = new URLSearchParams({ granularity: next, year: String(b.year) });
    if (b.quarter != null) p.set('quarter', String(b.quarter));
    if (b.month != null) p.set('month', String(b.month));
    try {
      const r = await api<{ buckets: Bucket[] }>(`/api/v1/document-repository/timeline?${p}`);
      setChildren((c) => ({ ...c, [key]: r.buckets || [] }));
    } catch (e: any) { setErr(e); }
  }

  function renderLevel(buckets: Bucket[], level: string, depth: number) {
    return buckets.map((b) => {
      const key = bucketKey(b);
      const expandable = NEXT[level] !== null;
      const [from, to] = bucketRange(b);
      return (
        <div key={key}>
          <div className="flex items-center gap-1.5 py-1.5 px-2 rounded hover:bg-[var(--bg-app)]/50"
            style={{ paddingLeft: `${8 + depth * 20}px` }}>
            {expandable ? (
              <button onClick={() => toggle(b, level)} className="text-[var(--text-secondary)] shrink-0">
                {open[key] ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
              </button>
            ) : <span className="w-3.5 shrink-0" />}
            <CalendarDays className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0" />
            <button onClick={() => (expandable ? toggle(b, level) : onPick(from, to))}
              className="text-sm font-medium hover:text-[var(--primary-gold-dark)]">
              {bucketLabel(b)}
            </button>
            <button onClick={() => onPick(from, to)}
              title="Xem tài liệu trong khoảng này"
              className="ml-auto text-[10px] text-[var(--text-secondary)] hover:text-[var(--primary-gold-dark)] tabular-nums">
              {b.doc_count} tài liệu →
            </button>
          </div>
          {open[key] && children[key] && renderLevel(children[key], NEXT[level]!, depth + 1)}
          {open[key] && !children[key] && expandable && (
            <div className="py-1 text-center"><Loader2 className="w-3.5 h-3.5 animate-spin inline text-[var(--text-secondary)]" /></div>
          )}
        </div>
      );
    });
  }

  if (err) return <ErrorBanner problem={err} />;
  if (years === null)
    return <div className="py-10 text-center text-[var(--text-secondary)]"><Loader2 className="w-5 h-5 animate-spin inline" /></div>;
  if (years.length === 0)
    return <div className="py-10 text-center text-sm text-[var(--text-secondary)]">Chưa có tài liệu nào để xếp theo thời gian.</div>;

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-2">
      <p className="px-2 pt-1 pb-2 text-[11px] text-[var(--text-secondary)]">
        Cây thời gian ảo — nhóm theo <b>ngày chứng từ</b> (tài liệu chưa gán ngày dùng ngày tải lên).
        Bấm số lượng để xem tài liệu trong kỳ{periodKind ? ` (đang lọc: ${PERIOD_LABEL[periodKind]})` : ''}.
      </p>
      {renderLevel(years, 'year', 0)}
    </div>
  );
}
