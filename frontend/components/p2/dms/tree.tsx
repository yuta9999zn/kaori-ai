// Page tree bên trái (bố cục Confluence): lazy expand, node = nghiệp vụ page,
// search-by-title, + Tạo thư mục ngay trong tree. Màu hệ Kaori.
'use client';

import React, { useCallback, useEffect, useState } from 'react';
import {
  ChevronRight, ChevronDown, Folder, BookOpen, Plus, Loader2, Search, Trash2,
} from 'lucide-react';
import { cn, api, type ProblemDetails } from '@/components/p2/foundation';
import { useT } from '@/lib/i18n/provider';

export interface TreeFolder {
  folder_id: string; name_vi: string; path: string;
  child_count: number; file_count: number;
  // đã cấu hình thành TRANG nghiệp vụ (có mô tả/mẫu) — icon khác thư mục thuần
  is_page?: boolean;
}

export function FolderTree({ selected, onSelect, refreshKey, onProblem }: {
  selected: string | null;
  onSelect: (id: string | null) => void;
  refreshKey: number;
  onProblem: (p: ProblemDetails) => void;
}) {
  const t = useT();
  const [roots, setRoots] = useState<TreeFolder[] | null>(null);
  const [children, setChildren] = useState<Record<string, TreeFolder[]>>({});
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [filter, setFilter] = useState('');

  const loadChildren = useCallback(async (parentId: string | null) => {
    const key = parentId ?? '__root__';
    setBusy((b) => ({ ...b, [key]: true }));
    try {
      const r = await api<{ items: TreeFolder[] }>(
        `/api/v1/document-folders${parentId ? `?parent_id=${parentId}` : ''}`);
      if (parentId === null) setRoots(r.items || []);
      else setChildren((c) => ({ ...c, [parentId]: r.items || [] }));
    } catch (e: any) { onProblem(e); }
    finally { setBusy((b) => ({ ...b, [key]: false })); }
  }, [onProblem]);

  useEffect(() => { loadChildren(null); }, [loadChildren, refreshKey]);

  async function toggle(f: TreeFolder) {
    if (open[f.folder_id]) { setOpen((o) => ({ ...o, [f.folder_id]: false })); return; }
    setOpen((o) => ({ ...o, [f.folder_id]: true }));
    if (!children[f.folder_id]) await loadChildren(f.folder_id);
  }

  async function createUnder(parentId: string | null) {
    const name = window.prompt(t('dmsTree.promptFolderName'));
    if (!name?.trim()) return;
    try {
      await api('/api/v1/document-folders', {
        method: 'POST',
        body: JSON.stringify({ name_vi: name.trim(), parent_id: parentId }),
      });
      if (parentId) {
        await loadChildren(parentId);
        setOpen((o) => ({ ...o, [parentId]: true }));
      } else await loadChildren(null);
    } catch (e: any) { onProblem(e); }
  }

  async function remove(f: TreeFolder) {
    if (!window.confirm(t('dmsTree.confirmDelete', { name: f.name_vi }))) return;
    try {
      await api(`/api/v1/document-folders/${f.folder_id}`, { method: 'DELETE' });
      if (selected === f.folder_id) onSelect(null);
      await loadChildren(null);
      setChildren({});
    } catch (e: any) { onProblem(e); }
  }

  function renderNodes(nodes: TreeFolder[], depth: number): React.ReactNode {
    const q = filter.trim().toLowerCase();
    return nodes
      .filter((f) => !q || f.name_vi.toLowerCase().includes(q))
      .map((f) => (
        <div key={f.folder_id}>
          <div className={cn(
            'group flex items-center gap-1 rounded px-1.5 py-1 cursor-pointer',
            selected === f.folder_id
              ? 'bg-[var(--primary-gold)]/15 text-[var(--primary-gold-dark)] font-medium'
              : 'hover:bg-[var(--bg-app)]/60')}
            style={{ paddingLeft: `${6 + depth * 14}px` }}>
            <button onClick={(e) => { e.stopPropagation(); toggle(f); }}
              className="text-[var(--text-secondary)] shrink-0 w-4">
              {f.child_count > 0
                ? (open[f.folder_id] ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />)
                : <span className="inline-block w-3.5" />}
            </button>
            {f.is_page ? (
              <BookOpen className="w-3.5 h-3.5 text-[var(--primary-gold-dark)] shrink-0" aria-label={t('dmsTree.ariaBusinessPage')} />
            ) : (
              <Folder className="w-3.5 h-3.5 text-amber-500/80 shrink-0" aria-label={t('dmsTree.ariaFolder')} />
            )}
            <button onClick={() => onSelect(f.folder_id)} className="flex-1 min-w-0 text-left">
              <span className="text-[13px] truncate block">{f.name_vi}</span>
            </button>
            <span className="text-[9px] text-[var(--text-secondary)] tabular-nums shrink-0 opacity-0 group-hover:opacity-100">
              {f.file_count > 0 && `${f.file_count}`}
            </span>
            <button onClick={(e) => { e.stopPropagation(); createUnder(f.folder_id); }}
              title={t('dmsTree.titleCreateSubfolder')}
              className="opacity-0 group-hover:opacity-100 text-[var(--text-secondary)] hover:text-[var(--primary-gold-dark)] shrink-0">
              <Plus className="w-3 h-3" />
            </button>
            <button onClick={(e) => { e.stopPropagation(); remove(f); }}
              title={t('dmsTree.titleDelete')}
              className="opacity-0 group-hover:opacity-100 text-[var(--text-secondary)] hover:text-[var(--state-error)] shrink-0">
              <Trash2 className="w-3 h-3" />
            </button>
          </div>
          {open[f.folder_id] && children[f.folder_id] && renderNodes(children[f.folder_id], depth + 1)}
          {open[f.folder_id] && !children[f.folder_id] && busy[f.folder_id] && (
            <div className="py-1 text-center"><Loader2 className="w-3 h-3 animate-spin inline text-[var(--text-secondary)]" /></div>
          )}
        </div>
      ));
  }

  return (
    <div className="space-y-2">
      <div className="relative">
        <Search className="w-3.5 h-3.5 text-[var(--text-secondary)] absolute left-2.5 top-1/2 -translate-y-1/2" />
        <input value={filter} onChange={(e) => setFilter(e.target.value)}
          placeholder={t('dmsTree.placeholderFilter')}
          className="w-full pl-8 pr-2 py-1.5 bg-white border border-[var(--border-color)] rounded text-xs focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30" />
      </div>
      {roots === null ? (
        <div className="py-6 text-center"><Loader2 className="w-4 h-4 animate-spin inline text-[var(--text-secondary)]" /></div>
      ) : (
        <div className="space-y-0.5">
          {renderNodes(roots, 0)}
          <button onClick={() => createUnder(null)}
            className="flex items-center gap-1.5 px-1.5 py-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--primary-gold-dark)] w-full">
            <Plus className="w-3.5 h-3.5" /> {t('dmsTree.btnCreateFolder')}
          </button>
          {/* chú giải icon — phân biệt thư mục / trang / file / tài liệu Kaori */}
          <div className="mt-2 pt-2 border-t border-[var(--border-color)]/50 px-1.5 space-y-0.5 text-[10px] text-[var(--text-secondary)]">
            <p className="flex items-center gap-1.5"><Folder className="w-3 h-3 text-amber-500/80" /> {t('dmsTree.legendFolder')} · <BookOpen className="w-3 h-3 text-[var(--primary-gold-dark)]" /> {t('dmsTree.legendPage')}</p>
            <p className="flex items-center gap-1.5"><span className="w-3 h-3 inline-flex items-center justify-center text-emerald-700">▤</span> {t('dmsTree.legendFileUpload')} · <span className="w-3 h-3 inline-flex items-center justify-center text-[var(--primary-gold-dark)]">✎</span> {t('dmsTree.legendDocKaori')}</p>
          </div>
        </div>
      )}
    </div>
  );
}
