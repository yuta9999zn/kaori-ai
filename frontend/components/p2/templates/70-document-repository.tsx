// @ts-nocheck — template; tighten types when wiring to real API
// ADR-0039 — Kho tài liệu (enterprise Document Repository / DMS).
// Lazy breadcrumb browser: load a folder's direct children + files on navigate
// (never the whole tree). Create folder, upload into folder, search.
'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Folder, FolderPlus, Upload, FileText, ChevronRight, Home, Search,
  Loader2, Trash2, ExternalLink,
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
}
interface Crumb { folder_id: string; name_vi: string; }

const TOKEN_KEY = 'kaori.access_token';

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
          api<{ items: FileRow[] }>(`/api/v1/document-folders/${current}/files`),
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
  }, [current]);

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
    if (!search.trim()) { setResults(null); return; }
    try {
      const r = await api<{ items: any[] }>(`/api/v1/document-repository/search?q=${encodeURIComponent(search.trim())}`);
      setResults(r.items || []);
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

      {/* search */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && runSearch()}
            placeholder="Tìm tài liệu theo tên…"
            className="w-full pl-9 pr-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
          />
        </div>
        <Button variant="secondary" onClick={runSearch}>Tìm</Button>
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
          <p className="text-xs text-[var(--text-secondary)] mb-2">{results.length} kết quả cho “{search}”</p>
          {results.map((r) => (
            <button key={r.doc_id} onClick={() => setCurrent(r.folder_id)}
              className="w-full flex items-center gap-2 px-2 py-2 rounded hover:bg-[var(--bg-app)]/50 text-left">
              <FileText className="w-4 h-4 text-emerald-700 shrink-0" />
              <span className="text-sm flex-1 truncate">{r.name_vi}</span>
              <span className="text-[10px] text-[var(--text-secondary)] font-mono truncate">{r.path}</span>
            </button>
          ))}
        </div>
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

          {/* files in current folder */}
          {files.length > 0 && (
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom divide-y divide-[var(--border-color)]/50">
              {files.map((d) => (
                <div key={d.doc_id} className="flex items-center gap-2 px-3 py-2.5">
                  <FileText className="w-4 h-4 text-emerald-700 shrink-0" />
                  <span className="text-sm flex-1 truncate">{d.name_vi}</span>
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
