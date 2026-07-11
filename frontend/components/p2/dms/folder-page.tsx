// Folder = nghiệp vụ PAGE (ADR-0042, cơ chế Confluence): mở thư mục là mở một
// trang — mô tả nghiệp vụ (body_md) + mẫu tài liệu gắn trên trang + file mẫu +
// version history của định nghĩa. Tài liệu bên trong xem theo Danh sách hoặc
// Bảng index (Page Properties Report). Màu giữ nguyên hệ Kaori.
'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  FileText, Upload, Loader2, Pencil, History, Download, Sparkles, X,
  ChevronDown, ChevronRight, Table2, List, Paperclip, RotateCcw, Tag,
  FilePlus2, NotebookPen, CheckCircle2, ArrowRight, PlayCircle,
} from 'lucide-react';
import {
  Button, Badge, ErrorBanner, cn, api, API_BASE, type ProblemDetails,
} from '@/components/p2/foundation';
import { useT } from '@/lib/i18n/provider';
import { safeRandomUUID } from '@/lib/uuid';
import { Markdown } from './md';
import { MdToolbar } from './md-toolbar';
import { MetadataForm, CompletenessBadge, StatusLozenge } from './metadata-form';
import { IndexView } from './index-view';
import { InsightPanel } from './insight-panel';
import { AuthoredDocPage } from './authored-doc';
import { NotesPanel } from './notes-panel';
import {
  DocRow, FolderPageData, PageVersion, TemplateDef, FieldDef,
} from './types';

const TOKEN_KEY = 'kaori.access_token';

function fmtTime(iso: string | null): string {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return iso; }
}

// ─── page editor (chế độ Sửa trang — bố cục editor Confluence) ─────────
function PageEditor({ page, docs, onClose, onSaved }: {
  page: FolderPageData;
  docs: DocRow[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const t = useT();
  const [bodyMd, setBodyMd] = useState(page.body_md || '');
  const [templateId, setTemplateId] = useState(page.default_template_id || '');
  const [sampleFileId, setSampleFileId] = useState(page.sample_file_id || '');
  const [labels, setLabels] = useState(page.default_labels.join(', '));
  const [changeNote, setChangeNote] = useState('');
  const [templates, setTemplates] = useState<TemplateDef[]>([]);
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const bodyRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    api<{ items: TemplateDef[] }>('/api/v1/document-templates')
      .then((r) => setTemplates(r.items || []))
      .catch(() => {});
  }, []);

  async function save() {
    setSaving(true);
    setProblem(null);
    try {
      await api(`/api/v1/document-folders/${page.folder_id}/page`, {
        method: 'PATCH',
        body: JSON.stringify({
          body_md: bodyMd,
          default_template_id: templateId || undefined,
          clear_template: !templateId && !!page.default_template_id,
          sample_file_id: sampleFileId || undefined,
          clear_sample: !sampleFileId && !!page.sample_file_id,
          default_labels: labels.split(',').map((s) => s.trim()).filter(Boolean),
          change_note: changeNote || undefined,
        }),
      });
      onSaved();
    } catch (e: any) {
      setProblem(e);
    } finally {
      setSaving(false);
    }
  }

  const sampleCandidates = docs.filter((d) => d.file_id);

  return (
    <div className="space-y-3">
      {/* editor chrome: Đang sửa + Lưu (Publish) — kiểu Confluence */}
      <div className="flex items-center gap-2 border-b border-[var(--border-color)] pb-2">
        <Badge variant="default" className="text-[10px]">{t('dmsFolderPage.editingPageBadge')}</Badge>
        <span className="text-xs text-[var(--text-secondary)] flex-1">
          {t('dmsFolderPage.editingPageHint')}
        </span>
        <input value={changeNote} onChange={(e) => setChangeNote(e.target.value)}
          placeholder={t('dmsFolderPage.changeNotePlaceholder')}
          className="px-2 py-1.5 text-xs bg-white border border-[var(--border-color)] rounded w-56" />
        <Button variant="secondary" onClick={onClose}>{t('dmsFolderPage.cancel')}</Button>
        <Button onClick={save} disabled={saving}>
          {saving ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : null}
          {t('dmsFolderPage.savePage', { version: page.page_version + 1 })}
        </Button>
      </div>

      {problem && <ErrorBanner problem={problem} />}

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-4">
        {/* body — mô tả nghiệp vụ */}
        <div>
          <label className="text-xs font-semibold text-[var(--text-secondary)]">{t('dmsFolderPage.businessDescLabel')}</label>
          <div className="mt-1">
            <MdToolbar target={bodyRef} onChange={setBodyMd} />
            <textarea ref={bodyRef} value={bodyMd} onChange={(e) => setBodyMd(e.target.value)} rows={14}
              placeholder={t('dmsFolderPage.businessDescPlaceholder')}
              className="w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-b-md text-sm font-mono leading-relaxed focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30" />
          </div>
        </div>

        {/* side panel: mẫu + file mẫu + nhãn — kiểu panel phải Confluence */}
        <div className="space-y-3">
          <div>
            <label className="text-xs font-semibold text-[var(--text-secondary)]">{t('dmsFolderPage.folderTemplateLabel')}</label>
            <select value={templateId} onChange={(e) => setTemplateId(e.target.value)}
              className="mt-1 w-full px-2 py-2 bg-white border border-[var(--border-color)] rounded text-sm">
              <option value="">{t('dmsFolderPage.inheritFromParent')}</option>
              {templates.map((tmpl) => (
                <option key={tmpl.template_id} value={tmpl.template_id}>
                  {tmpl.icon ? `${tmpl.icon} ` : ''}{tmpl.name_vi}{tmpl.is_global ? t('dmsFolderPage.systemTemplateSuffix') : ''}
                </option>
              ))}
            </select>
            <p className="mt-1 text-[11px] text-[var(--text-secondary)]">
              {t('dmsFolderPage.folderTemplateHint')}
            </p>
          </div>

          <div>
            <label className="text-xs font-semibold text-[var(--text-secondary)]">{t('dmsFolderPage.sampleFileLabel')}</label>
            <select value={sampleFileId} onChange={(e) => setSampleFileId(e.target.value)}
              className="mt-1 w-full px-2 py-2 bg-white border border-[var(--border-color)] rounded text-sm">
              <option value="">{t('dmsFolderPage.noneOption')}</option>
              {sampleCandidates.map((d) => (
                <option key={d.doc_id} value={d.file_id!}>{d.name_vi}</option>
              ))}
            </select>
            <p className="mt-1 text-[11px] text-[var(--text-secondary)]">
              {t('dmsFolderPage.sampleFileHint')}
            </p>
          </div>

          <div>
            <label className="text-xs font-semibold text-[var(--text-secondary)]">{t('dmsFolderPage.labelsLabel')}</label>
            <input value={labels} onChange={(e) => setLabels(e.target.value)}
              placeholder={t('dmsFolderPage.labelsPlaceholder')}
              className="mt-1 w-full px-2 py-2 bg-white border border-[var(--border-color)] rounded text-sm" />
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── version history (bảng so sánh kiểu Confluence) ─────────────────────
function VersionHistory({ folderId, currentVersion, onClose, onRestored }: {
  folderId: string; currentVersion: number;
  onClose: () => void; onRestored: () => void;
}) {
  const t = useT();
  const [versions, setVersions] = useState<PageVersion[] | null>(null);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [restoring, setRestoring] = useState<number | null>(null);

  useEffect(() => {
    api<{ items: PageVersion[] }>(`/api/v1/document-folders/${folderId}/page/versions`)
      .then((r) => setVersions(r.items || []))
      .catch(setProblem);
  }, [folderId]);

  async function restore(no: number) {
    setRestoring(no);
    try {
      await api(`/api/v1/document-folders/${folderId}/page/restore`, {
        method: 'POST', body: JSON.stringify({ version_no: no }),
      });
      onRestored();
    } catch (e: any) { setProblem(e); } finally { setRestoring(null); }
  }

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-4 space-y-2">
      <div className="flex items-center gap-2">
        <History className="w-4 h-4 text-[var(--primary-gold-dark)]" />
        <h3 className="text-sm font-semibold flex-1">{t('dmsFolderPage.versionHistoryTitle')}</h3>
        <button onClick={onClose} className="text-[var(--text-secondary)] hover:text-[var(--state-error)]"><X className="w-4 h-4" /></button>
      </div>
      {problem && <ErrorBanner problem={problem} />}
      {versions === null ? (
        <div className="py-4 text-center"><Loader2 className="w-4 h-4 animate-spin inline text-[var(--text-secondary)]" /></div>
      ) : versions.length === 0 ? (
        <p className="text-sm text-[var(--text-secondary)]">{t('dmsFolderPage.versionHistoryEmpty')}</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-[var(--text-secondary)]">
              <th className="py-1.5 pr-3">{t('dmsFolderPage.colVersion')}</th>
              <th className="py-1.5 pr-3">{t('dmsFolderPage.colTime')}</th>
              <th className="py-1.5 pr-3">{t('dmsFolderPage.colTemplateAttached')}</th>
              <th className="py-1.5 pr-3">{t('dmsFolderPage.colNote')}</th>
              <th className="py-1.5" />
            </tr>
          </thead>
          <tbody>
            {versions.map((v) => (
              <tr key={v.version_no} className="border-t border-[var(--border-color)]/50">
                <td className="py-2 pr-3 font-mono text-xs">
                  v{v.version_no}{v.version_no === currentVersion && <Badge variant="success" className="ml-1.5 text-[9px]">{t('dmsFolderPage.currentBadge')}</Badge>}
                </td>
                <td className="py-2 pr-3 text-xs text-[var(--text-secondary)]">{fmtTime(v.edited_at)}</td>
                <td className="py-2 pr-3 text-xs">{v.template_snapshot?.name_vi || '—'}</td>
                <td className="py-2 pr-3 text-xs text-[var(--text-secondary)]">{v.change_note || '—'}</td>
                <td className="py-2 text-right">
                  {v.version_no !== currentVersion && (
                    <button onClick={() => restore(v.version_no)} disabled={restoring !== null}
                      className="inline-flex items-center gap-1 text-xs text-[var(--primary-gold-dark)] hover:underline">
                      {restoring === v.version_no ? <Loader2 className="w-3 h-3 animate-spin" /> : <RotateCcw className="w-3 h-3" />}
                      {t('dmsFolderPage.restore')}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ─── create authored document (soạn trong Kaori / AI soạn nháp) ─────────
function CreateDocPanel({ folderId, templateName, onClose, onCreated }: {
  folderId: string; templateName: string | null;
  onClose: () => void; onCreated: (docId: string) => void;
}) {
  const t = useT();
  const [name, setName] = useState('');
  const [prompt, setPrompt] = useState('');
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  async function create(withAI: boolean) {
    if (!name.trim()) { setProblem({ title: t('dmsFolderPage.errNameRequired') } as ProblemDetails); return; }
    if (withAI && !prompt.trim()) { setProblem({ title: t('dmsFolderPage.errPromptRequired') } as ProblemDetails); return; }
    setBusy(true);
    setProblem(null);
    try {
      const r = await api<{ doc_id: string }>('/api/v1/document-repository/authored', {
        method: 'POST',
        body: JSON.stringify({
          folder_id: folderId, name_vi: name.trim(),
          generate_prompt: withAI ? prompt.trim() : undefined,
        }),
      });
      onCreated(r.doc_id);
    } catch (e: any) { setProblem(e); } finally { setBusy(false); }
  }

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--primary-gold)]/40 rounded-lg-custom p-4 space-y-3">
      <div className="flex items-center gap-2">
        <NotebookPen className="w-4 h-4 text-[var(--primary-gold-dark)]" />
        <h3 className="text-sm font-semibold flex-1">{t('dmsFolderPage.createDocTitle')}{templateName ? t('dmsFolderPage.createDocTitleTemplate', { name: templateName }) : ''}</h3>
        <button onClick={onClose} className="text-[var(--text-secondary)] hover:text-[var(--state-error)]"><X className="w-4 h-4" /></button>
      </div>
      {problem && <ErrorBanner problem={problem} />}
      <input value={name} onChange={(e) => setName(e.target.value)}
        placeholder={t('dmsFolderPage.docNamePlaceholder')}
        className="w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30" />
      <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={4}
        placeholder={t('dmsFolderPage.aiPromptPlaceholder')}
        className="w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30" />
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={() => create(false)} disabled={busy}>
          <FilePlus2 className="w-3.5 h-3.5 mr-1.5" /> {t('dmsFolderPage.createEmpty')}
        </Button>
        <Button onClick={() => create(true)} disabled={busy}>
          {busy ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Sparkles className="w-4 h-4 mr-1.5" />}
          {t('dmsFolderPage.createWithAI')}
        </Button>
      </div>
    </div>
  );
}


// ─── doc row + metadata drawer ──────────────────────────────────────────
function DocItem({ d, schema, statusField, onChanged, onOpenAuthored }: {
  d: DocRow; schema: FieldDef[]; statusField: FieldDef | null;
  onChanged: () => void;
  onOpenAuthored: (docId: string) => void;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const statusVal = statusField ? (d.metadata as any)?.[statusField.key] : null;

  // Cầu Kho ↔ pipeline (demo AABW): file BẢNG trong Kho được chấm sạch/bẩn
  // như ở Cây tài liệu workflow — bẩn thì đi tiếp 5 bước làm sạch từ run
  // đã tự tạo lúc upload, sạch thì phân tích thẳng.
  const isTabular = /\.(csv|tsv|xlsx|xls)$/i.test(d.name_vi);
  const [checkingClean, setCheckingClean] = useState(false);
  const [cleanVerdict, setCleanVerdict] = useState<any | null>(null);
  async function checkClean() {
    setCheckingClean(true);
    try {
      const r: any = await api(`/api/v1/document-repository/${d.doc_id}/cleanliness`, { method: 'POST' });
      setCleanVerdict(r);
    } catch (err: any) {
      setCleanVerdict({ error: err?.detail || err?.title || err?.message || 'Không kiểm tra được' });
    } finally {
      setCheckingClean(false);
    }
  }
  const runHref = d.pipeline_run_id ? `/p2/pipelines/${d.pipeline_run_id}` : null;

  if (d.doc_kind === 'authored') {
    // tài liệu soạn trong Kaori → mở như một trang, không phải drawer/file
    return (
      <div className="border-b border-[var(--border-color)]/50 last:border-b-0">
        <div className="flex items-center gap-2 px-3 py-2.5">
          <span className="w-3.5 shrink-0" />
          <NotebookPen className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0" />
          <button onClick={() => onOpenAuthored(d.doc_id)}
            className="text-sm flex-1 truncate text-left font-medium hover:text-[var(--primary-gold-dark)]">
            {d.name_vi}
          </button>
          {d.status === 'generating' && (
            <Badge variant="default" className="text-[10px] inline-flex items-center gap-1">
              <Sparkles className="w-3 h-3" /> {t('dmsFolderPage.aiGenerating')}
            </Badge>
          )}
          {statusVal && statusField && <StatusLozenge value={String(statusVal)} options={statusField.options || []} />}
          <CompletenessBadge value={d.completeness} />
          {d.version > 1 && <span className="text-[10px] font-mono text-[var(--text-secondary)]">v{d.version}</span>}
          <Badge variant="default" className="text-[10px]">{t('dmsFolderPage.kaoriDocBadge')}</Badge>
        </div>
      </div>
    );
  }

  return (
    <div className="border-b border-[var(--border-color)]/50 last:border-b-0">
      <div className="flex items-center gap-2 px-3 py-2.5">
        <button onClick={() => setOpen(!open)} className="text-[var(--text-secondary)] shrink-0">
          {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        </button>
        <FileText className="w-4 h-4 text-emerald-700 shrink-0" />
        <button onClick={() => setOpen(!open)} className="text-sm flex-1 truncate text-left hover:text-[var(--primary-gold-dark)]">
          {d.name_vi}
        </button>
        {statusVal && statusField && <StatusLozenge value={String(statusVal)} options={statusField.options || []} />}
        <CompletenessBadge value={d.completeness} />
        {d.version > 1 && (
          <span title={t('dmsFolderPage.versionTitle', { version: d.version })}
            className="text-[10px] font-mono text-[var(--text-secondary)]">v{d.version}</span>
        )}
        {d.doc_type && <Badge variant="default" className="text-[10px]">.{d.doc_type}</Badge>}
        {isTabular && (
          <button onClick={checkClean} disabled={checkingClean}
            className="text-[11px] text-emerald-700 hover:underline shrink-0 inline-flex items-center gap-1 disabled:opacity-50"
            title="Qwen chấm dữ liệu bảng này đã sạch chưa">
            {checkingClean ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle2 className="w-3 h-3" />}
            Kiểm tra sạch
          </button>
        )}
        {runHref && (
          <a href={runHref}
            className="text-[11px] text-[var(--primary-gold-dark)] hover:underline shrink-0 inline-flex items-center gap-1"
            title="Mở lần chạy dữ liệu đã tạo từ file này (Bronze → 5 bước làm sạch)">
            <PlayCircle className="w-3 h-3" /> Lần chạy dữ liệu
          </a>
        )}
        <a href={`${API_BASE}/api/v1/document-repository/${d.doc_id}/download`}
          target="_blank" rel="noreferrer" title={t('dmsFolderPage.download')}
          onClick={(e) => {
            // đính token vào request qua fetch → blob (raw <a> không mang Bearer)
            e.preventDefault();
            fetch(`${API_BASE}/api/v1/document-repository/${d.doc_id}/download`, {
              headers: { Authorization: `Bearer ${window.localStorage.getItem(TOKEN_KEY) ?? ''}` },
            }).then(async (res) => {
              if (!res.ok) return;
              const blob = await res.blob();
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url; a.download = d.name_vi; a.click();
              URL.revokeObjectURL(url);
            });
          }}
          className="text-[var(--text-secondary)] hover:text-[var(--primary-gold-dark)] shrink-0">
          <Download className="w-3.5 h-3.5" />
        </a>
      </div>
      {cleanVerdict && (
        <div className={cn('mx-10 mb-2.5 rounded-md-custom border p-2.5 space-y-1.5',
          cleanVerdict.error ? 'border-rose-200 bg-rose-50/50'
            : cleanVerdict.is_clean ? 'border-emerald-200 bg-emerald-50/50'
              : 'border-amber-200 bg-amber-50/50')}>
          {cleanVerdict.error ? (
            <p className="text-xs text-rose-700">{String(cleanVerdict.error)}</p>
          ) : (
            <>
              <p className="text-xs font-medium text-[var(--text-primary)]">
                {cleanVerdict.is_clean
                  ? `✓ Dữ liệu SẠCH (điểm ${Number(cleanVerdict.score).toFixed(2)}/1) — dùng phân tích được ngay`
                  : `⚠ Dữ liệu CHƯA SẠCH (điểm ${Number(cleanVerdict.score).toFixed(2)}/1) — nên chạy 5 bước làm sạch`}
              </p>
              {Array.isArray(cleanVerdict.issues) && cleanVerdict.issues.length > 0 && (
                <ul className="text-[11px] text-[var(--text-secondary)] list-disc ml-4 space-y-0.5">
                  {cleanVerdict.issues.slice(0, 5).map((i: any, k: number) => <li key={k}>{i.label}</li>)}
                </ul>
              )}
              {cleanVerdict.narrative && (
                <p className="text-[11px] text-[var(--text-secondary)] italic">{cleanVerdict.narrative}</p>
              )}
              <a href={cleanVerdict.is_clean ? '/p2/analysis/basic' : (runHref ?? '/p2/pipelines/new')}
                 className="inline-flex items-center gap-1 text-[11px] font-medium text-[var(--primary-gold-dark)] hover:underline">
                {cleanVerdict.is_clean ? 'Phân tích ngay' : 'Chạy 5 bước làm sạch'} <ArrowRight className="w-3 h-3" />
              </a>
            </>
          )}
        </div>
      )}
      {open && (
        <div className="px-10 pb-3 space-y-3">
          <MetadataForm doc={d} schema={schema} onSaved={() => onChanged()} />
          <NotesPanel docId={d.doc_id} />
        </div>
      )}
    </div>
  );
}

// ─── the folder page ────────────────────────────────────────────────────
export function FolderPage({ folderId, onUploaded }: {
  folderId: string;
  onUploaded?: () => void;
}) {
  const t = useT();
  const [page, setPage] = useState<FolderPageData | null>(null);
  const [docs, setDocs] = useState<DocRow[]>([]);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [mode, setMode] = useState<'view' | 'edit'>('view');
  const [docView, setDocView] = useState<'list' | 'index'>('list');
  const [showVersions, setShowVersions] = useState(false);
  const [insightScope, setInsightScope] = useState<{ scope_kind: 'group' | 'folder'; scope: Record<string, unknown>; title: string } | null>(null);
  const [uploading, setUploading] = useState(false);
  const [openDoc, setOpenDoc] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setProblem(null);
    try {
      const [p, f] = await Promise.all([
        api<FolderPageData>(`/api/v1/document-folders/${folderId}/page`),
        api<{ items: DocRow[] }>(`/api/v1/document-folders/${folderId}/files?limit=200`),
      ]);
      setPage(p);
      setDocs(f.items || []);
    } catch (e: any) { setProblem(e); }
  }, [folderId]);

  useEffect(() => {
    setMode('view'); setShowVersions(false); setInsightScope(null);
    setOpenDoc(null); setShowCreate(false);
    load();
  }, [load]);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    e.target.value = '';
    if (!f) return;
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
          'X-Folder-ID': folderId,
          'Idempotency-Key': `repo-${hint || safeRandomUUID()}`,
        },
        body: fd,
      });
      if (!res.ok) {
        let detail = `HTTP ${res.status}`;
        try { const j = await res.json(); detail = (typeof j.detail === 'string' ? j.detail : j.detail?.message) || j.title || detail; } catch {}
        throw { title: detail } as ProblemDetails;
      }
      await load();
      onUploaded?.();
    } catch (err: any) {
      setProblem(err.title ? err : { title: err?.message || t('dmsFolderPage.uploadFailed') });
    } finally {
      setUploading(false);
    }
  }

  if (problem && !page) return <ErrorBanner problem={problem} />;
  if (!page) return <div className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin inline text-[var(--text-secondary)]" /></div>;

  // tài liệu soạn đang mở → chiếm toàn vùng nội dung như một trang riêng
  if (openDoc) {
    return <AuthoredDocPage docId={openDoc}
      onBack={() => { setOpenDoc(null); load(); }}
      onSaved={(newId) => setOpenDoc(newId)} />;
  }

  const tpl = page.effective_template;
  const schema = tpl?.metadata_schema || [];
  const statusField = schema.find((f) => f.kind === 'status') || null;

  if (mode === 'edit') {
    return <PageEditor page={page} docs={docs}
      onClose={() => setMode('view')}
      onSaved={() => { setMode('view'); load(); }} />;
  }

  return (
    <div className="space-y-4">
      {problem && <ErrorBanner problem={problem} />}

      {/* page header — kiểu Confluence: icon + title + Edited + actions */}
      <div className="flex items-start gap-3">
        <span className="text-3xl leading-none mt-0.5">{tpl?.icon || '📁'}</span>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-bold truncate">{page.name_vi}</h1>
          <p className="text-[11px] text-[var(--text-secondary)]">
            {t('dmsFolderPage.pageMetaVersion', { version: page.page_version })}
            {page.updated_at && t('dmsFolderPage.pageMetaUpdated', { time: fmtTime(page.updated_at) })}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Button variant="secondary" onClick={() => setShowVersions(!showVersions)}>
            <History className="w-3.5 h-3.5 mr-1.5" /> {t('dmsFolderPage.history')}
          </Button>
          <Button variant="secondary"
            onClick={() => setInsightScope({ scope_kind: 'folder', scope: { folder_id: folderId }, title: page.name_vi })}>
            <Sparkles className="w-3.5 h-3.5 mr-1.5" /> {t('dmsFolderPage.analyzeFolder')}
          </Button>
          <Button onClick={() => setMode('edit')}>
            <Pencil className="w-3.5 h-3.5 mr-1.5" /> {t('dmsFolderPage.editPage')}
          </Button>
        </div>
      </div>

      {/* labels chips */}
      {(page.effective_labels.length > 0) && (
        <div className="flex items-center gap-1.5 flex-wrap">
          <Tag className="w-3 h-3 text-[var(--text-secondary)]" />
          {page.effective_labels.map((lb) => (
            <span key={lb} className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-[var(--bg-app)]/80 border border-[var(--border-color)] text-[var(--text-secondary)]">
              {lb}
            </span>
          ))}
        </div>
      )}

      {showVersions && (
        <VersionHistory folderId={folderId} currentVersion={page.page_version}
          onClose={() => setShowVersions(false)}
          onRestored={() => { setShowVersions(false); load(); }} />
      )}

      {insightScope && <InsightPanel key={JSON.stringify(insightScope.scope)} scope={insightScope} onClose={() => setInsightScope(null)} />}

      {/* body — mô tả nghiệp vụ */}
      {page.body_md ? (
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom px-4 py-3">
          <Markdown text={page.body_md} />
        </div>
      ) : (
        <button onClick={() => setMode('edit')}
          className="w-full text-left px-4 py-3 border border-dashed border-[var(--border-color)] rounded-lg-custom text-sm text-[var(--text-secondary)] hover:border-[var(--primary-gold)]/60">
          {t('dmsFolderPage.noBusinessDesc')}
        </button>
      )}

      {/* properties: mẫu hiệu lực + file mẫu — bảng thuộc tính trên trang */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-md-custom px-3 py-2.5">
          <p className="text-[10px] font-semibold text-[var(--text-secondary)] uppercase">{t('dmsFolderPage.appliedTemplateLabel')}</p>
          {tpl ? (
            <p className="text-sm mt-0.5">
              {tpl.icon} {tpl.name_vi}
              {page.template_inherited_from && (
                <span className="text-[10px] text-[var(--text-secondary)]"> {t('dmsFolderPage.inheritedFromParentSuffix')}</span>
              )}
              <span className="block text-[11px] text-[var(--text-secondary)] mt-0.5">
                {t('dmsFolderPage.schemaFieldsCount', { count: schema.length })}
                {statusField ? t('dmsFolderPage.statusStepsCount', { count: (statusField.options || []).length }) : ''}
                {tpl.section_outline.length > 0 && t('dmsFolderPage.sectionOutlineCount', { count: tpl.section_outline.length })}
              </span>
            </p>
          ) : (
            <p className="text-sm mt-0.5 text-[var(--text-secondary)] italic">{t('dmsFolderPage.noTemplateAttached')}</p>
          )}
        </div>
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-md-custom px-3 py-2.5">
          <p className="text-[10px] font-semibold text-[var(--text-secondary)] uppercase">{t('dmsFolderPage.sampleUploadFileLabel')}</p>
          {page.sample_file_id ? (
            <button
              onClick={() => {
                fetch(`${API_BASE}/api/v1/document-repository/files/${page.sample_file_id}/download`, {
                  headers: { Authorization: `Bearer ${window.localStorage.getItem(TOKEN_KEY) ?? ''}` },
                }).then(async (res) => {
                  if (!res.ok) return;
                  const blob = await res.blob();
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url; a.download = 'file-mau'; a.click();
                  URL.revokeObjectURL(url);
                });
              }}
              className="text-sm mt-0.5 inline-flex items-center gap-1.5 text-[var(--primary-gold-dark)] hover:underline">
              <Paperclip className="w-3.5 h-3.5" /> {t('dmsFolderPage.downloadSampleToFill')}
            </button>
          ) : (
            <p className="text-sm mt-0.5 text-[var(--text-secondary)] italic">{t('dmsFolderPage.noSampleFile')}</p>
          )}
        </div>
      </div>

      {/* docs: toolbar + list/index */}
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold flex-1">{t('dmsFolderPage.docsHeading', { count: docs.length })}</h2>
        {tpl && (
          <div className="flex items-center rounded-md-custom border border-[var(--border-color)] overflow-hidden">
            <button onClick={() => setDocView('list')}
              className={cn('px-2.5 py-1.5 text-xs flex items-center gap-1.5',
                docView === 'list' ? 'bg-[var(--primary-gold)]/15 text-[var(--primary-gold-dark)] font-medium' : 'bg-white text-[var(--text-secondary)]')}>
              <List className="w-3.5 h-3.5" /> {t('dmsFolderPage.listView')}
            </button>
            <button onClick={() => setDocView('index')}
              className={cn('px-2.5 py-1.5 text-xs flex items-center gap-1.5',
                docView === 'index' ? 'bg-[var(--primary-gold)]/15 text-[var(--primary-gold-dark)] font-medium' : 'bg-white text-[var(--text-secondary)]')}>
              <Table2 className="w-3.5 h-3.5" /> {t('dmsFolderPage.indexView')}
            </button>
          </div>
        )}
        <Button variant="secondary" onClick={() => setShowCreate(!showCreate)}>
          <NotebookPen className="w-3.5 h-3.5 mr-1.5" /> {t('dmsFolderPage.createDoc')}
        </Button>
        <input ref={fileRef} type="file" hidden onChange={onUpload}
          accept=".pdf,.docx,.doc,.xlsx,.xls,.csv,.png,.jpg,.jpeg,.tiff,.webp,.pptx,.md,.json,.sql,.zip,.txt" />
        <Button onClick={() => fileRef.current?.click()} disabled={uploading}>
          {uploading ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Upload className="w-4 h-4 mr-1.5" />}
          {t('dmsFolderPage.uploadBtn')}
        </Button>
      </div>

      {showCreate && (
        <CreateDocPanel folderId={folderId} templateName={tpl?.name_vi || null}
          onClose={() => setShowCreate(false)}
          onCreated={(docId) => { setShowCreate(false); setOpenDoc(docId); }} />
      )}
      <p className="text-[11px] text-[var(--text-secondary)] -mt-2">
        {t('dmsFolderPage.dupFileNotePre')}<b>{t('dmsFolderPage.dupFileNoteBold')}</b>{t('dmsFolderPage.dupFileNotePost')}
      </p>

      {docView === 'index' && tpl ? (
        <IndexView template={tpl} folderId={folderId}
          onAnalyzeGroup={(ids) => setInsightScope({
            scope_kind: 'group', scope: { doc_ids: ids },
            title: t('dmsFolderPage.selectedDocsTitle', { count: ids.length }),
          })}
          onOpenDoc={() => setDocView('list')} />
      ) : docs.length === 0 ? (
        <div className="py-8 text-center text-sm text-[var(--text-secondary)] border border-dashed border-[var(--border-color)] rounded-lg-custom">
          {t('dmsFolderPage.emptyFolder')}{page.sample_file_id ? t('dmsFolderPage.emptyFolderSample') : ''}.
        </div>
      ) : (
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom">
          {docs.map((d) => (
            <DocItem key={d.doc_id} d={d} schema={schema} statusField={statusField}
              onChanged={load} onOpenAuthored={setOpenDoc} />
          ))}
        </div>
      )}
    </div>
  );
}
