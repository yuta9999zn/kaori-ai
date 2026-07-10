// Tài liệu soạn-trong-Kaori (ADR-0042 P2, mig 140) — mở như một PAGE:
// metadata (Page Properties) + các mục theo bộ khung mẫu (đoạn văn Markdown
// có ==highlight==, bảng đúng cột — kể cả cột link, khối link) + History
// Changes TỰ SINH từ chuỗi phiên bản. Sửa = tạo phiên bản mới.
// Nhãn cột/mục resolve theo 5 ngôn ngữ: locale → en → vi.
'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Loader2, Pencil, Save, X, Plus, Trash2, History, ExternalLink, Sparkles,
  AlertTriangle, ArrowLeft, Link2, Table2, Type,
} from 'lucide-react';
import { Button, Badge, ErrorBanner, cn, api, type ProblemDetails } from '@/components/p2/foundation';
import { useLocale, useT } from '@/lib/i18n/provider';
import { Markdown } from './md';
import { MdToolbar } from './md-toolbar';
import { NotesPanel } from './notes-panel';
import { MetadataForm, StatusLozenge, CompletenessBadge } from './metadata-form';
import {
  AuthoredDoc, DocHistoryRow, FieldDef, LinkVal, SectionContent, SectionDef,
  COLUMN_PRESETS, WIDTH_PRESETS, pickLabel, statusLabel,
} from './types';

function fmtTime(iso: string | null): string {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return iso; }
}

function isLink(v: unknown): v is LinkVal {
  return !!v && typeof v === 'object' && 'url' in (v as any);
}

// ─── table cell (view) ──────────────────────────────────────────────────
function CellView({ col, value }: { col: FieldDef; value: unknown }) {
  if (value == null || value === '') return <span className="text-[var(--text-secondary)]/40">—</span>;
  if (col.kind === 'link' && isLink(value)) {
    return (
      <a href={value.url} target="_blank" rel="noreferrer"
        className="inline-flex items-center gap-1 text-[var(--primary-gold-dark)] hover:underline">
        <ExternalLink className="w-3 h-3 shrink-0" />{value.text || value.url}
      </a>
    );
  }
  if (col.kind === 'status' || col.kind === 'select') return <span>{statusLabel(String(value))}</span>;
  if (col.kind === 'money') return <span className="tabular-nums">{Number(value).toLocaleString('vi-VN')}₫</span>;
  // cell text đi qua Markdown mini — **đậm** / ==highlight== / gạch đầu dòng trong ô
  return <Markdown text={String(value)} className="[&_p]:mb-0.5 [&_p]:text-[13px]" />;
}

// ─── section (view) ─────────────────────────────────────────────────────
function SectionView({ sec, odef, locale, index }: {
  sec: SectionContent; odef: SectionDef | undefined; locale: string; index: number;
}) {
  const t = useT();
  const heading = (odef && pickLabel(odef, locale, 'heading'))
    || pickLabel(sec as any, locale, 'heading') || sec.key;
  const columns = odef?.columns || sec.columns || [];
  return (
    <section>
      <h2 className="text-base font-semibold mb-1.5">
        {odef?.icon ? `${odef.icon} ` : ''}{index + 1}. {heading}
      </h2>
      {sec.body_md && <Markdown text={sec.body_md} className="mb-2" />}
      {sec.rows && sec.rows.length > 0 && columns.length > 0 && (
        <div className="overflow-x-auto border border-[var(--border-color)] rounded-md-custom mb-2">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[var(--bg-app)]/60 text-left">
                <th className="px-2 py-1.5 text-xs font-semibold w-10">#</th>
                {columns.map((c) => (
                  <th key={c.key}
                    style={c.width ? { width: c.width, minWidth: c.width } : undefined}
                    className="px-2.5 py-1.5 text-xs font-semibold whitespace-nowrap">
                    {pickLabel(c, locale)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sec.rows.map((row, i) => (
                <tr key={i} className="border-t border-[var(--border-color)]/50 align-top">
                  <td className="px-2 py-1.5 text-xs text-[var(--text-secondary)] tabular-nums">{i + 1}</td>
                  {columns.map((c) => (
                    <td key={c.key}
                      style={c.width ? { width: c.width, minWidth: c.width } : undefined}
                      className={cn('px-2.5 py-1.5', !c.width && 'max-w-[280px]')}>
                      <CellView col={c} value={row[c.key]} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {sec.links && sec.links.length > 0 && (
        <ul className="mb-2 space-y-0.5">
          {sec.links.map((l, i) => (
            <li key={i}>
              <a href={l.url} target="_blank" rel="noreferrer"
                className="inline-flex items-center gap-1 text-sm text-[var(--primary-gold-dark)] hover:underline">
                <ExternalLink className="w-3 h-3" />{l.text || l.url}
              </a>
            </li>
          ))}
        </ul>
      )}
      {!sec.body_md && (!sec.rows || !sec.rows.length) && (!sec.links || !sec.links.length) && (
        <p className="text-xs italic text-[var(--text-secondary)] mb-2">{t('dmsAuthoredDoc.emptySection')}</p>
      )}
    </section>
  );
}

// ─── section (edit) ─────────────────────────────────────────────────────
function CellInput({ col, value, onChange }: {
  col: FieldDef; value: unknown; onChange: (v: unknown) => void;
}) {
  const t = useT();
  const cls = 'w-full px-1.5 py-1 bg-white border border-[var(--border-color)]/70 rounded text-xs focus:outline-none focus:ring-1 focus:ring-[var(--primary-gold)]/40';
  if (col.kind === 'link') {
    const lv = isLink(value) ? value : { text: '', url: '' };
    return (
      <div className="space-y-1 min-w-[150px]">
        <input className={cls} placeholder={t('dmsAuthoredDoc.placeholderDisplayName')} value={lv.text}
          onChange={(e) => onChange({ ...lv, text: e.target.value })} />
        <input className={cls} placeholder="https://…" value={lv.url}
          onChange={(e) => onChange({ ...lv, url: e.target.value })} />
      </div>
    );
  }
  if (col.kind === 'select' || col.kind === 'status') {
    return (
      <select className={cls} value={String(value ?? '')}
        onChange={(e) => onChange(e.target.value || undefined)}>
        <option value="">—</option>
        {(col.options || []).map((o) => <option key={o} value={o}>{statusLabel(o)}</option>)}
      </select>
    );
  }
  if (col.kind === 'long_text') {
    return <textarea rows={2} className={cls} value={String(value ?? '')}
      onChange={(e) => onChange(e.target.value || undefined)} />;
  }
  if (col.kind === 'date') {
    return <input type="date" className={cls} value={String(value ?? '')}
      onChange={(e) => onChange(e.target.value || undefined)} />;
  }
  if (col.kind === 'number' || col.kind === 'money') {
    return <input type="number" className={cls} value={value == null ? '' : String(value)}
      onChange={(e) => onChange(e.target.value === '' ? undefined : Number(e.target.value))} />;
  }
  return <input className={cls} value={String(value ?? '')}
    onChange={(e) => onChange(e.target.value || undefined)} />;
}

function SectionEdit({ sec, odef, locale, onChange, onRemove }: {
  sec: SectionContent; odef: SectionDef | undefined; locale: string;
  onChange: (s: SectionContent) => void;
  onRemove?: () => void;
}) {
  const t = useT();
  const columns = odef?.columns || sec.columns || [];
  const heading = (odef && pickLabel(odef, locale, 'heading')) || sec.heading_vi || sec.key;
  const taRef = useRef<HTMLTextAreaElement>(null);
  const isCustom = !odef; // mục ngoài mẫu → sửa được tiêu đề, xoá được
  return (
    <section className="border border-[var(--border-color)]/70 rounded-md-custom p-3 space-y-2">
      <div className="flex items-center gap-2">
        {isCustom ? (
          <input value={sec.heading_vi || ''} placeholder={t('dmsAuthoredDoc.placeholderSectionTitle')}
            onChange={(e) => onChange({ ...sec, heading_vi: e.target.value })}
            className="text-sm font-semibold flex-1 px-2 py-1 bg-white border border-[var(--border-color)] rounded focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30" />
        ) : (
          <p className="text-sm font-semibold flex-1">{odef?.icon} {heading}
            {odef?.hint_vi && <span className="ml-2 text-[11px] font-normal text-[var(--text-secondary)]">{odef.hint_vi}</span>}
          </p>
        )}
        {isCustom && onRemove && (
          <button onClick={onRemove} title={t('dmsAuthoredDoc.deleteSectionTooltip')}
            className="text-[var(--text-secondary)] hover:text-[var(--state-error)] shrink-0">
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
      <div>
        <MdToolbar target={taRef} onChange={(v) => onChange({ ...sec, body_md: v })} />
        <textarea ref={taRef} rows={3} value={sec.body_md || ''}
          placeholder={t('dmsAuthoredDoc.bodyMdPlaceholder')}
          onChange={(e) => onChange({ ...sec, body_md: e.target.value })}
          className="w-full px-2 py-1.5 bg-white border border-[var(--border-color)] rounded-b rounded-t-none text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30" />
      </div>

      {/* links đính kèm của mục */}
      {(sec.links || []).map((l, i) => (
        <div key={i} className="flex items-center gap-1.5">
          <Link2 className="w-3.5 h-3.5 text-[var(--text-secondary)] shrink-0" />
          <input value={l.text} placeholder={t('dmsAuthoredDoc.placeholderDisplayName')}
            onChange={(e) => onChange({ ...sec, links: (sec.links || []).map((x, j) => j === i ? { ...x, text: e.target.value } : x) })}
            className="px-2 py-1 bg-white border border-[var(--border-color)] rounded text-xs w-48" />
          <input value={l.url} placeholder="https://…"
            onChange={(e) => onChange({ ...sec, links: (sec.links || []).map((x, j) => j === i ? { ...x, url: e.target.value } : x) })}
            className="px-2 py-1 bg-white border border-[var(--border-color)] rounded text-xs flex-1" />
          <button onClick={() => onChange({ ...sec, links: (sec.links || []).filter((_, j) => j !== i) })}
            className="text-[var(--text-secondary)] hover:text-[var(--state-error)]"><Trash2 className="w-3.5 h-3.5" /></button>
        </div>
      ))}
      <button onClick={() => onChange({ ...sec, links: [...(sec.links || []), { text: '', url: '' }] })}
        className="inline-flex items-center gap-1 text-xs text-[var(--primary-gold-dark)] hover:underline">
        <Link2 className="w-3 h-3" /> {t('dmsAuthoredDoc.attachLink')}
      </button>
      {columns.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left">
                {columns.map((c, ci) => (
                  <th key={c.key} className="px-1.5 py-1 text-[10px] font-semibold text-[var(--text-secondary)] whitespace-nowrap align-bottom">
                    {pickLabel(c, locale)}
                    {isCustom && (
                      // độ rộng cột: 4 mức chọn sẵn — không px tự do để khỏi vỡ layout
                      <select value={c.width ?? ''} title={t('dmsAuthoredDoc.columnWidthTooltip')}
                        onChange={(e) => {
                          const w = e.target.value === '' ? undefined : Number(e.target.value);
                          onChange({
                            ...sec,
                            columns: (sec.columns || []).map((x, j) => j === ci ? { ...x, width: w } : x),
                          });
                        }}
                        className="ml-1 px-1 py-0 text-[10px] font-normal bg-white border border-[var(--border-color)]/60 rounded">
                        {WIDTH_PRESETS.map((p) => (
                          <option key={p.label} value={p.value ?? ''}>{p.label}</option>
                        ))}
                      </select>
                    )}
                  </th>
                ))}
                <th className="w-8" />
              </tr>
            </thead>
            <tbody>
              {(sec.rows || []).map((row, i) => (
                <tr key={i} className="align-top">
                  {columns.map((c) => (
                    <td key={c.key} className="px-1 py-1 min-w-[110px]">
                      <CellInput col={c} value={row[c.key]}
                        onChange={(v) => {
                          const rows = [...(sec.rows || [])];
                          rows[i] = { ...rows[i], [c.key]: v };
                          onChange({ ...sec, rows });
                        }} />
                    </td>
                  ))}
                  <td className="px-1 py-1.5">
                    <button onClick={() => onChange({ ...sec, rows: (sec.rows || []).filter((_, j) => j !== i) })}
                      className="text-[var(--text-secondary)] hover:text-[var(--state-error)]">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button onClick={() => onChange({ ...sec, rows: [...(sec.rows || []), {}] })}
            className="mt-1 inline-flex items-center gap-1 text-xs text-[var(--primary-gold-dark)] hover:underline">
            <Plus className="w-3 h-3" /> {t('dmsAuthoredDoc.addRow')}
          </button>
        </div>
      )}
    </section>
  );
}

// ─── thêm mục tự do (văn bản / bảng) — tài liệu không mẫu vẫn soạn đủ ───
function slugKey(s: string): string {
  return s.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D')
    .toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 40) || 'muc';
}

function AddSectionBar({ existingKeys, onAdd }: {
  existingKeys: string[];
  onAdd: (sec: SectionContent) => void;
}) {
  const t = useT();
  const [tableOpen, setTableOpen] = useState(false);
  const [heading, setHeading] = useState('');
  const [picked, setPicked] = useState<string[]>([]);

  function uniqueKey(base: string): string {
    let k = base, i = 2;
    while (existingKeys.includes(k)) k = `${base}_${i++}`;
    return k;
  }

  return (
    <div className="border border-dashed border-[var(--border-color)] rounded-md-custom p-3 space-y-2">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs text-[var(--text-secondary)]">{t('dmsAuthoredDoc.addSectionLabel')}</span>
        <Button variant="secondary" onClick={() => onAdd({
          key: uniqueKey('muc_van_ban'), heading_vi: t('dmsAuthoredDoc.defaultNewSectionHeading'), body_md: '',
        })}>
          <Type className="w-3.5 h-3.5 mr-1.5" /> {t('dmsAuthoredDoc.textSection')}
        </Button>
        <Button variant="secondary" onClick={() => setTableOpen(!tableOpen)}>
          <Table2 className="w-3.5 h-3.5 mr-1.5" /> {t('dmsAuthoredDoc.tableSection')}
        </Button>
      </div>
      {tableOpen && (
        <div className="space-y-2">
          <input value={heading} onChange={(e) => setHeading(e.target.value)}
            placeholder={t('dmsAuthoredDoc.tableTitlePlaceholder')}
            className="px-2 py-1.5 bg-white border border-[var(--border-color)] rounded text-sm w-64" />
          {/* cột chọn từ BỘ CHUẨN — bấm để bật/tắt, giữ thứ tự bấm */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[11px] text-[var(--text-secondary)]">{t('dmsAuthoredDoc.pickColumnsLabel')}</span>
            {COLUMN_PRESETS.map((p) => {
              const on = picked.includes(p.key);
              return (
                <button key={p.key} type="button"
                  onClick={() => setPicked((s) => on ? s.filter((k) => k !== p.key) : [...s, p.key])}
                  className={cn('px-2 py-1 rounded border text-xs',
                    on ? 'bg-[var(--primary-gold)]/15 border-[var(--primary-gold)]/60 text-[var(--primary-gold-dark)] font-medium'
                       : 'bg-white border-[var(--border-color)] text-[var(--text-secondary)] hover:border-[var(--primary-gold)]/40')}>
                  {p.label_vi}
                </button>
              );
            })}
          </div>
          <div className="flex justify-end">
            <Button disabled={picked.length === 0} onClick={() => {
              const columns = picked
                .map((k) => COLUMN_PRESETS.find((p) => p.key === k)!)
                .map((p) => ({ ...p }));
              onAdd({
                key: uniqueKey(slugKey(heading || 'bang')),
                heading_vi: heading || t('dmsAuthoredDoc.defaultNewTableHeading'), columns, rows: [{}],
              });
              setTableOpen(false); setHeading(''); setPicked([]);
            }}>
              <Plus className="w-3.5 h-3.5 mr-1" /> {t('dmsAuthoredDoc.createTableBtn', { count: picked.length })}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}


// ─── the authored document page ─────────────────────────────────────────
export function AuthoredDocPage({ docId, onBack, onSaved }: {
  docId: string;
  onBack: () => void;
  onSaved?: (newDocId: string) => void;
}) {
  const t = useT();
  const { locale } = useLocale();
  const [doc, setDoc] = useState<AuthoredDoc | null>(null);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [mode, setMode] = useState<'view' | 'edit'>('view');
  const [draft, setDraft] = useState<SectionContent[]>([]);
  const [changeNote, setChangeNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [warnings, setWarnings] = useState<{ message_vi: string }[]>([]);
  const [history, setHistory] = useState<DocHistoryRow[] | null>(null);
  const [showRegen, setShowRegen] = useState(false);
  const [regenPrompt, setRegenPrompt] = useState('');
  const pollRef = useRef(0);

  const load = useCallback(async (id: string) => {
    setProblem(null);
    try {
      const d = await api<AuthoredDoc>(`/api/v1/document-repository/${id}/content`);
      setDoc(d);
      // đang AI soạn → poll tới khi active (job nền, không chặn request path)
      if (d.status === 'generating' && pollRef.current++ < 60) {
        setTimeout(() => load(id), 3000);
      } else {
        api<{ items: DocHistoryRow[] }>(`/api/v1/document-repository/${id}/history`)
          .then((h) => setHistory(h.items || [])).catch(() => {});
      }
    } catch (e: any) { setProblem(e); }
  }, []);

  useEffect(() => { pollRef.current = 0; load(docId); }, [docId, load]);

  if (problem && !doc) return <div><Button variant="secondary" onClick={onBack}><ArrowLeft className="w-3.5 h-3.5 mr-1" /> {t('dmsAuthoredDoc.back')}</Button><div className="mt-2"><ErrorBanner problem={problem} /></div></div>;
  if (!doc) return <div className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin inline text-[var(--text-secondary)]" /></div>;

  const outlineByKey: Record<string, SectionDef> = {};
  (doc.section_outline || []).forEach((s) => { if (s.key) outlineByKey[String(s.key)] = s; });
  const sections = doc.content?.sections || [];
  // hiển thị theo thứ tự outline; mục ngoài outline xếp cuối
  const ordered = [
    ...(doc.section_outline || []).map((o) => sections.find((s) => s.key === o.key)).filter(Boolean) as SectionContent[],
    ...sections.filter((s) => !outlineByKey[s.key]),
  ];

  function startEdit() {
    // draft đầy đủ theo outline (mục chưa có trong content vẫn sửa được)
    const draftSecs = (doc!.section_outline || []).map((o) =>
      sections.find((s) => s.key === o.key) || { key: String(o.key) });
    sections.filter((s) => !outlineByKey[s.key]).forEach((s) => draftSecs.push(s));
    setDraft(JSON.parse(JSON.stringify(draftSecs)));
    setWarnings([]);
    setMode('edit');
  }

  async function save() {
    setSaving(true);
    try {
      const r = await api<{ doc_id: string; version: number; warnings: { message_vi: string }[] }>(
        `/api/v1/document-repository/${doc!.doc_id}/content`, {
          method: 'PATCH',
          body: JSON.stringify({ content: { sections: draft }, change_note: changeNote || undefined }),
        });
      setWarnings(r.warnings || []);
      setMode('view');
      setChangeNote('');
      onSaved?.(r.doc_id);
      await load(r.doc_id);
    } catch (e: any) { setProblem(e); } finally { setSaving(false); }
  }

  return (
    <div className="space-y-4">
      {problem && <ErrorBanner problem={problem} />}

      {/* header */}
      <div className="flex items-start gap-3">
        <button onClick={onBack} className="mt-1 text-[var(--text-secondary)] hover:text-[var(--primary-gold-dark)]">
          <ArrowLeft className="w-4 h-4" />
        </button>
        <span className="text-2xl leading-none">{doc.template_icon || '📝'}</span>
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-bold truncate">{doc.name_vi}</h1>
          <p className="text-[11px] text-[var(--text-secondary)]">
            {doc.template_name ? t('dmsAuthoredDoc.templatePrefix', { name: doc.template_name }) : ''}
            v{doc.version}{doc.is_current ? '' : t('dmsAuthoredDoc.oldVersionSuffix')} · {fmtTime(doc.uploaded_at)}
            {doc.change_reason ? ` · ${doc.change_reason}` : ''}
          </p>
        </div>
        {doc.status === 'generating' ? (
          <Badge variant="default" className="text-[10px] inline-flex items-center gap-1">
            <Sparkles className="w-3 h-3" /> {t('dmsAuthoredDoc.aiGenerating')}
          </Badge>
        ) : mode === 'view' ? (
          <div className="flex items-center gap-2">
            {doc.is_current && (
              <Button variant="secondary" onClick={() => setShowRegen(!showRegen)}>
                <Sparkles className="w-3.5 h-3.5 mr-1.5" /> {t('dmsAuthoredDoc.aiRegenerate')}
              </Button>
            )}
            <Button onClick={startEdit}><Pencil className="w-3.5 h-3.5 mr-1.5" /> {t('dmsAuthoredDoc.editContent')}</Button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <input value={changeNote} onChange={(e) => setChangeNote(e.target.value)}
              placeholder={t('dmsAuthoredDoc.changeNotePlaceholder')}
              className="px-2 py-1.5 text-xs bg-white border border-[var(--border-color)] rounded w-48" />
            <Button variant="secondary" onClick={() => setMode('view')}><X className="w-3.5 h-3.5 mr-1" /> {t('dmsAuthoredDoc.cancel')}</Button>
            <Button onClick={save} disabled={saving}>
              {saving ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Save className="w-4 h-4 mr-1.5" />}
              {t('dmsAuthoredDoc.saveVersion', { version: doc.version + 1 })}
            </Button>
          </div>
        )}
      </div>

      {doc.status === 'generating' && (
        <p className="text-sm text-[var(--text-secondary)] flex items-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin" />
          {t('dmsAuthoredDoc.aiDraftingStatus')}
        </p>
      )}

      {showRegen && doc.status !== 'generating' && (
        <div className="bg-[var(--bg-card)] border border-[var(--primary-gold)]/40 rounded-lg-custom p-3 space-y-2">
          <p className="text-xs text-[var(--text-secondary)]">
            {t('dmsAuthoredDoc.regenDesc')}
          </p>
          <textarea value={regenPrompt} onChange={(e) => setRegenPrompt(e.target.value)} rows={3}
            className="w-full px-2 py-1.5 bg-white border border-[var(--border-color)] rounded text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30" />
          <div className="flex justify-end">
            <Button disabled={!regenPrompt.trim()} onClick={async () => {
              try {
                await api(`/api/v1/document-repository/${doc.doc_id}/regenerate`, {
                  method: 'POST',
                  body: JSON.stringify({ generate_prompt: regenPrompt.trim() }),
                });
                setShowRegen(false);
                pollRef.current = 0;
                load(doc.doc_id);
              } catch (e: any) { setProblem(e); }
            }}>
              <Sparkles className="w-3.5 h-3.5 mr-1.5" /> {t('dmsAuthoredDoc.regenerate')}
            </Button>
          </div>
        </div>
      )}

      {warnings.length > 0 && (
        <div className="text-[11px] space-y-0.5">
          {warnings.map((w, i) => (
            <p key={i} className="text-amber-700 flex items-center gap-1">
              <AlertTriangle className="w-3 h-3 shrink-0" /> {w.message_vi}
            </p>
          ))}
        </div>
      )}

      {/* Page Properties */}
      {doc.status !== 'generating' && mode === 'view' && (
        <MetadataForm
          doc={{ ...doc, doc_type: null, storage_tier: 'hot', doc_date: null, period_kind: null } as any}
          schema={doc.metadata_schema || []}
          onSaved={() => load(doc.doc_id)} />
      )}

      {/* sections */}
      {mode === 'view' ? (
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom px-4 py-3 space-y-4">
          {ordered.length === 0 && doc.status !== 'generating' && (
            <p className="text-sm text-[var(--text-secondary)] italic">{t('dmsAuthoredDoc.noContentYet')}</p>
          )}
          {ordered.map((sec, i) => (
            <SectionView key={sec.key} sec={sec} odef={outlineByKey[sec.key]} locale={locale} index={i} />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {draft.map((sec, i) => (
            <SectionEdit key={sec.key} sec={sec} odef={outlineByKey[sec.key]} locale={locale}
              onChange={(s) => setDraft((d) => d.map((x, j) => (j === i ? s : x)))}
              onRemove={() => setDraft((d) => d.filter((_, j) => j !== i))} />
          ))}
          <AddSectionBar existingKeys={draft.map((s) => s.key)}
            onAdd={(sec) => setDraft((d) => [...d, sec])} />
        </div>
      )}

      {/* Ghi chú (Confluence page comments) */}
      {mode === 'view' && doc.status !== 'generating' && <NotesPanel docId={doc.doc_id} />}

      {/* History Changes — tự sinh từ chuỗi phiên bản */}
      {history && history.length > 0 && mode === 'view' && (
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom px-4 py-3">
          <h2 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
            <History className="w-4 h-4 text-[var(--primary-gold-dark)]" />
            {t('dmsAuthoredDoc.historyHeading')} <span className="text-[10px] font-normal text-[var(--text-secondary)]">{t('dmsAuthoredDoc.historyHint')}</span>
          </h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-[var(--text-secondary)]">
                <th className="py-1 pr-3">{t('dmsAuthoredDoc.colVersion')}</th>
                <th className="py-1 pr-3">{t('dmsAuthoredDoc.colTime')}</th>
                <th className="py-1">{t('dmsAuthoredDoc.colContent')}</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h) => (
                <tr key={h.doc_id} className="border-t border-[var(--border-color)]/50">
                  <td className="py-1.5 pr-3 font-mono text-xs">
                    v{h.version}{h.is_current && <Badge variant="success" className="ml-1.5 text-[9px]">{t('dmsAuthoredDoc.current')}</Badge>}
                  </td>
                  <td className="py-1.5 pr-3 text-xs text-[var(--text-secondary)]">{fmtTime(h.uploaded_at)}</td>
                  <td className="py-1.5 text-xs">
                    {h.is_current || h.doc_id === doc.doc_id ? (
                      <span>{h.change_reason || t('dmsAuthoredDoc.defaultChangeReason')}</span>
                    ) : (
                      <button onClick={() => load(h.doc_id)} className="text-[var(--primary-gold-dark)] hover:underline">
                        {h.change_reason || t('dmsAuthoredDoc.defaultChangeReason')} {t('dmsAuthoredDoc.viewThisVersion')}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
