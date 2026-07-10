// Page Properties Report (ADR-0042) — index tự tổng hợp: cột lấy từ
// metadata_schema của mẫu, không ai phải maintain bảng tay. Multi-select
// để "Phân tích nhóm đã chọn".
'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { Loader2, FileText, Sparkles } from 'lucide-react';
import { Button, ErrorBanner, cn, api, type ProblemDetails } from '@/components/p2/foundation';
import { useLocale, useT } from '@/lib/i18n/provider';
import { FieldDef, IndexRow, TemplateDef, pickLabel, statusLabel } from './types';
import { StatusLozenge, CompletenessBadge } from './metadata-form';

function cellValue(f: FieldDef, row: IndexRow, users: Record<string, string>): React.ReactNode {
  const v = row.metadata?.[f.key];
  if (v == null || v === '') return <span className="text-[var(--text-secondary)]/50">—</span>;
  if (f.kind === 'status') return <StatusLozenge value={String(v)} options={f.options || []} />;
  if (f.kind === 'user') return <span>{users[String(v)] || String(v).slice(0, 8)}</span>;
  if (f.kind === 'money') return <span className="tabular-nums">{Number(v).toLocaleString('vi-VN')}₫</span>;
  if (f.kind === 'select') return <span>{statusLabel(String(v))}</span>;
  return <span className="truncate">{String(v)}</span>;
}

export function IndexView({ template, folderId, onAnalyzeGroup, onOpenDoc }: {
  template: TemplateDef;
  folderId: string;
  onAnalyzeGroup: (docIds: string[]) => void;
  onOpenDoc: (docId: string, folderId: string) => void;
}) {
  const { locale } = useLocale();
  const t = useT();
  const [rows, setRows] = useState<IndexRow[] | null>(null);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [users, setUsers] = useState<Record<string, string>>({});
  const schema = template.metadata_schema || [];

  const load = useCallback(async () => {
    setProblem(null);
    try {
      const r = await api<{ items: IndexRow[] }>(
        `/api/v1/document-repository/index?template_id=${template.template_id}&folder_id=${folderId}&limit=200`);
      setRows(r.items || []);
    } catch (e: any) { setProblem(e); }
  }, [template.template_id, folderId]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!schema.some((f) => f.kind === 'user')) return;
    api<{ data: { id: string; name: string; email: string }[] }>('/api/v1/enterprises/users?limit=200')
      .then((r) => {
        const m: Record<string, string> = {};
        ((r as any).data ?? []).forEach((u: any) => { m[u.id] = u.name || u.email; });
        setUsers(m);
      })
      .catch(() => {});
  }, [template.template_id]);

  if (problem) return <ErrorBanner problem={problem} />;
  if (rows === null)
    return <div className="py-8 text-center"><Loader2 className="w-5 h-5 animate-spin inline text-[var(--text-secondary)]" /></div>;
  if (rows.length === 0)
    return <p className="py-6 text-center text-sm text-[var(--text-secondary)]">{t('dmsIndexView.emptyState')}</p>;

  const toggle = (id: string) => setSelected((s) => {
    const n = new Set(s);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });

  return (
    <div className="space-y-2">
      {selected.size > 0 && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-[var(--text-secondary)]">{t('dmsIndexView.selectedCount', { count: selected.size })}</span>
          <Button variant="secondary" onClick={() => onAnalyzeGroup([...selected])}>
            <Sparkles className="w-3.5 h-3.5 mr-1.5" /> {t('dmsIndexView.analyzeGroup')}
          </Button>
        </div>
      )}
      <div className="overflow-x-auto border border-[var(--border-color)] rounded-lg-custom bg-[var(--bg-card)]">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[var(--bg-app)]/60 text-left">
              <th className="px-2 py-2 w-8">
                <input type="checkbox" className="accent-[var(--primary-gold-dark)]"
                  checked={selected.size === rows.length}
                  onChange={() => setSelected(selected.size === rows.length ? new Set() : new Set(rows.map((r) => r.doc_id)))} />
              </th>
              <th className="px-3 py-2 text-xs font-semibold">{t('dmsIndexView.colDocument')}</th>
              {schema.map((f) => (
                <th key={f.key} className="px-3 py-2 text-xs font-semibold whitespace-nowrap">{pickLabel(f, locale)}</th>
              ))}
              <th className="px-3 py-2 text-xs font-semibold whitespace-nowrap">{t('dmsIndexView.colInfo')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.doc_id} className="border-t border-[var(--border-color)]/50 hover:bg-[var(--bg-app)]/40">
                <td className="px-2 py-2">
                  <input type="checkbox" className="accent-[var(--primary-gold-dark)]"
                    checked={selected.has(r.doc_id)} onChange={() => toggle(r.doc_id)} />
                </td>
                <td className="px-3 py-2 max-w-[260px]">
                  <button onClick={() => onOpenDoc(r.doc_id, r.folder_id)}
                    className="flex items-center gap-1.5 text-left hover:text-[var(--primary-gold-dark)]">
                    <FileText className="w-3.5 h-3.5 text-emerald-700 shrink-0" />
                    <span className="truncate font-medium">{r.name_vi}</span>
                    {r.version > 1 && <span className="text-[10px] font-mono text-[var(--text-secondary)]">v{r.version}</span>}
                  </button>
                </td>
                {schema.map((f) => (
                  <td key={f.key} className={cn('px-3 py-2 max-w-[200px]', f.kind === 'long_text' && 'max-w-[280px]')}>
                    {cellValue(f, r, users)}
                  </td>
                ))}
                <td className="px-3 py-2"><CompletenessBadge value={r.completeness} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
