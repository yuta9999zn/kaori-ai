// Quản lý Mẫu tài liệu (ADR-0042) — bố cục theo Confluence "Manage templates":
// «Mẫu của doanh nghiệp» (user-created, sửa được) + «Mẫu hệ thống» (blueprint,
// chỉ đọc — Nhân bản để tuỳ chỉnh). Schema builder: mỗi dòng = 1 thuộc tính.
'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Loader2, Plus, Copy, Pencil, Save, X, Trash2, GripVertical, FileUp, Sparkles,
} from 'lucide-react';
import {
  Button, Badge, ErrorBanner, cn, api, API_BASE, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { FieldDef, FieldKind, SectionDef, TemplateDef, WIDTH_PRESETS, statusLabel } from './types';
import { safeRandomUUID } from '@/lib/uuid';
import { useT } from '@/lib/i18n/provider';

function kindLabels(t: (key: string, params?: Record<string, string | number>) => string): Record<FieldKind, string> {
  return {
    text: t('dmsTemplateManager.kindText'), long_text: t('dmsTemplateManager.kindLongText'),
    number: t('dmsTemplateManager.kindNumber'), money: t('dmsTemplateManager.kindMoney'),
    date: t('dmsTemplateManager.kindDate'), user: t('dmsTemplateManager.kindUser'),
    department: t('dmsTemplateManager.kindDepartment'), select: t('dmsTemplateManager.kindSelect'),
    status: t('dmsTemplateManager.kindStatus'), link: t('dmsTemplateManager.kindLink'),
  };
}

function slugKey(s: string): string {
  return s.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D')
    .toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 40) || 'truong';
}

// ─── editor drawer ──────────────────────────────────────────────────────
function TemplateEditor({ tpl, onClose, onSaved }: {
  tpl: TemplateDef; onClose: () => void; onSaved: () => void;
}) {
  const t = useT();
  const KIND_LABEL = kindLabels(t);
  const [name, setName] = useState(tpl.name_vi);
  const [icon, setIcon] = useState(tpl.icon || '');
  const [desc, setDesc] = useState(tpl.description || '');
  const [labels, setLabels] = useState(tpl.default_labels.join(', '));
  const [fields, setFields] = useState<FieldDef[]>(tpl.metadata_schema || []);
  const [sections, setSections] = useState<SectionDef[]>(tpl.section_outline || []);
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  function setField(i: number, patch: Partial<FieldDef>) {
    setFields((fs) => fs.map((f, j) => (j === i ? { ...f, ...patch } : f)));
  }
  function setSection(i: number, patch: Partial<SectionDef>) {
    setSections((ss) => ss.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  }

  async function save() {
    setSaving(true);
    setProblem(null);
    try {
      await api(`/api/v1/document-templates/${tpl.template_id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name_vi: name, icon: icon || undefined, description: desc || undefined,
          metadata_schema: fields.filter((f) => f.key && f.label_vi),
          section_outline: sections.filter((s) => s.heading_vi),
          default_labels: labels.split(',').map((s) => s.trim()).filter(Boolean),
          // bản nháp AI (is_active=false) → Lưu là duyệt + kích hoạt
          ...(tpl.is_active ? {} : { is_active: true }),
        }),
      });
      onSaved();
    } catch (e: any) { setProblem(e); } finally { setSaving(false); }
  }

  const inputCls = 'px-2 py-1.5 bg-white border border-[var(--border-color)] rounded text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30';

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--primary-gold)]/40 rounded-lg-custom p-4 space-y-4">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold flex-1">{t('dmsTemplateManager.editorTitle', { name: tpl.name_vi })}</h3>
        <Button variant="secondary" onClick={onClose}><X className="w-3.5 h-3.5 mr-1" /> {t('dmsTemplateManager.close')}</Button>
        <Button onClick={save} disabled={saving}>
          {saving ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Save className="w-4 h-4 mr-1.5" />}
          {t('dmsTemplateManager.saveTemplate')}
        </Button>
      </div>
      {problem && <ErrorBanner problem={problem} />}

      <div className="grid grid-cols-1 sm:grid-cols-[64px_1fr_1fr] gap-2">
        <div>
          <label className="text-xs font-semibold text-[var(--text-secondary)]">{t('dmsTemplateManager.labelIcon')}</label>
          <input value={icon} onChange={(e) => setIcon(e.target.value)} className={cn(inputCls, 'w-full mt-1 text-center')} placeholder="📄" />
        </div>
        <div>
          <label className="text-xs font-semibold text-[var(--text-secondary)]">{t('dmsTemplateManager.labelName')}</label>
          <input value={name} onChange={(e) => setName(e.target.value)} className={cn(inputCls, 'w-full mt-1')} />
        </div>
        <div>
          <label className="text-xs font-semibold text-[var(--text-secondary)]">{t('dmsTemplateManager.labelLabelsAuto')}</label>
          <input value={labels} onChange={(e) => setLabels(e.target.value)} className={cn(inputCls, 'w-full mt-1')} placeholder={t('dmsTemplateManager.placeholderLabelsExample')} />
        </div>
      </div>
      <div>
        <label className="text-xs font-semibold text-[var(--text-secondary)]">{t('dmsTemplateManager.labelDescription')}</label>
        <input value={desc} onChange={(e) => setDesc(e.target.value)} className={cn(inputCls, 'w-full mt-1')} />
      </div>

      {/* thuộc tính — bảng Page Properties của mẫu */}
      <div>
        <div className="flex items-center gap-2 mb-1.5">
          <label className="text-xs font-semibold text-[var(--text-secondary)] flex-1">
            {t('dmsTemplateManager.fieldsHeading', { count: fields.length })}
          </label>
          <button onClick={() => setFields((fs) => [...fs, { key: '', label_vi: '', kind: 'text', required: false }])}
            className="text-xs text-[var(--primary-gold-dark)] hover:underline inline-flex items-center gap-1">
            <Plus className="w-3 h-3" /> {t('dmsTemplateManager.addField')}
          </button>
        </div>
        <div className="space-y-1.5">
          {fields.map((f, i) => (
            <div key={i} className="flex items-center gap-1.5 flex-wrap bg-[var(--bg-app)]/40 border border-[var(--border-color)]/60 rounded px-2 py-1.5">
              <GripVertical className="w-3.5 h-3.5 text-[var(--text-secondary)]/50 shrink-0" />
              <input value={f.label_vi} placeholder={t('dmsTemplateManager.placeholderFieldLabel')}
                onChange={(e) => setField(i, { label_vi: e.target.value, key: f.key || slugKey(e.target.value) })}
                className={cn(inputCls, 'w-36')} />
              <input value={(f as any).label_en || ''} placeholder="EN label" title={t('dmsTemplateManager.titleEnLabelHint')}
                onChange={(e) => setField(i, { label_en: e.target.value || undefined } as any)}
                className={cn(inputCls, 'w-32')} />
              <input value={f.key} placeholder="key" title={t('dmsTemplateManager.titleKeyHint')}
                onChange={(e) => setField(i, { key: slugKey(e.target.value) })}
                className={cn(inputCls, 'w-28 font-mono text-xs')} />
              <select value={f.kind} onChange={(e) => setField(i, { kind: e.target.value as FieldKind })}
                className={cn(inputCls, 'w-28')}>
                {Object.entries(KIND_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              {(f.kind === 'select' || f.kind === 'status') && (
                <input value={(f.options || []).join(', ')} placeholder={t('dmsTemplateManager.placeholderOptionsCsv')}
                  onChange={(e) => setField(i, { options: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })}
                  className={cn(inputCls, 'flex-1 min-w-[180px]')} />
              )}
              <label className="text-xs flex items-center gap-1 shrink-0">
                <input type="checkbox" checked={!!f.required} onChange={(e) => setField(i, { required: e.target.checked })}
                  className="accent-[var(--primary-gold-dark)]" />
                {t('dmsTemplateManager.required')}
              </label>
              <button onClick={() => setFields((fs) => fs.filter((_, j) => j !== i))}
                className="text-[var(--text-secondary)] hover:text-[var(--state-error)] shrink-0">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
          {fields.length === 0 && <p className="text-xs text-[var(--text-secondary)] italic">{t('dmsTemplateManager.noFieldsYet')}</p>}
        </div>
      </div>

      {/* dàn bài — các mục tài liệu cần có */}
      <div>
        <div className="flex items-center gap-2 mb-1.5">
          <label className="text-xs font-semibold text-[var(--text-secondary)] flex-1">
            {t('dmsTemplateManager.sectionsHeading', { count: sections.length })}
          </label>
          <button onClick={() => setSections((ss) => [...ss, { heading_vi: '', icon: '', hint_vi: '' }])}
            className="text-xs text-[var(--primary-gold-dark)] hover:underline inline-flex items-center gap-1">
            <Plus className="w-3 h-3" /> {t('dmsTemplateManager.addSection')}
          </button>
        </div>
        <div className="space-y-1.5">
          {sections.map((s, i) => (
            <div key={i} className="bg-[var(--bg-app)]/40 border border-[var(--border-color)]/60 rounded px-2 py-1.5 space-y-1.5">
              <div className="flex items-center gap-1.5">
                <input value={s.icon || ''} placeholder="🎯" onChange={(e) => setSection(i, { icon: e.target.value })}
                  className={cn(inputCls, 'w-12 text-center')} />
                <input value={s.heading_vi} placeholder={t('dmsTemplateManager.placeholderSectionHeading')}
                  onChange={(e) => setSection(i, { heading_vi: e.target.value, key: (s as any).key || slugKey(e.target.value) })}
                  className={cn(inputCls, 'w-40')} />
                <input value={(s as any).heading_en || ''} placeholder="EN heading"
                  onChange={(e) => setSection(i, { heading_en: e.target.value || undefined } as any)}
                  className={cn(inputCls, 'w-32')} />
                <input value={s.hint_vi || ''} placeholder={t('dmsTemplateManager.placeholderSectionHint')}
                  onChange={(e) => setSection(i, { hint_vi: e.target.value })}
                  className={cn(inputCls, 'flex-1')} />
                <select value={s.body_kind || 'prose'}
                  onChange={(e) => setSection(i, {
                    body_kind: e.target.value as any,
                    columns: e.target.value === 'table' ? (s.columns || []) : undefined,
                  })}
                  className={cn(inputCls, 'w-24')}>
                  <option value="prose">{t('dmsTemplateManager.bodyKindProse')}</option>
                  <option value="table">{t('dmsTemplateManager.bodyKindTable')}</option>
                  <option value="checklist">{t('dmsTemplateManager.bodyKindChecklist')}</option>
                </select>
                <button onClick={() => setSections((ss) => ss.filter((_, j) => j !== i))}
                  className="text-[var(--text-secondary)] hover:text-[var(--state-error)] shrink-0">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* cột của mục dạng Bảng — nhãn VI/EN + kiểu + độ rộng px */}
              {s.body_kind === 'table' && (
                <div className="pl-4 space-y-1">
                  {(s.columns || []).map((c, ci) => (
                    <div key={ci} className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-[10px] text-[var(--text-secondary)] w-4 text-right">{ci + 1}.</span>
                      <input value={c.label_vi} placeholder={t('dmsTemplateManager.placeholderColumnLabel')}
                        onChange={(e) => setSection(i, {
                          columns: (s.columns || []).map((x, j) => j === ci
                            ? { ...x, label_vi: e.target.value, key: x.key || slugKey(e.target.value) } : x),
                        })}
                        className={cn(inputCls, 'w-36')} />
                      <input value={(c as any).label_en || ''} placeholder="EN"
                        onChange={(e) => setSection(i, {
                          columns: (s.columns || []).map((x, j) => j === ci
                            ? { ...x, label_en: e.target.value || undefined } : x) as any,
                        })}
                        className={cn(inputCls, 'w-28')} />
                      <select value={c.kind}
                        onChange={(e) => setSection(i, {
                          columns: (s.columns || []).map((x, j) => j === ci
                            ? { ...x, kind: e.target.value as FieldKind } : x),
                        })}
                        className={cn(inputCls, 'w-24')}>
                        {Object.entries(KIND_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                      </select>
                      <select value={c.width ?? ''} title={t('dmsTemplateManager.titleColumnWidth')}
                        onChange={(e) => setSection(i, {
                          columns: (s.columns || []).map((x, j) => j === ci
                            ? { ...x, width: e.target.value === '' ? undefined : Number(e.target.value) } : x),
                        })}
                        className={cn(inputCls, 'w-24')}>
                        {WIDTH_PRESETS.map((p) => (
                          <option key={p.label} value={p.value ?? ''}>{p.label}</option>
                        ))}
                      </select>
                      {(c.kind === 'select' || c.kind === 'status') && (
                        <input value={(c.options || []).join(', ')} placeholder={t('dmsTemplateManager.placeholderOptionsComma')}
                          onChange={(e) => setSection(i, {
                            columns: (s.columns || []).map((x, j) => j === ci
                              ? { ...x, options: e.target.value.split(',').map((o) => o.trim()).filter(Boolean) } : x),
                          })}
                          className={cn(inputCls, 'flex-1 min-w-[140px]')} />
                      )}
                      <button onClick={() => setSection(i, { columns: (s.columns || []).filter((_, j) => j !== ci) })}
                        className="text-[var(--text-secondary)] hover:text-[var(--state-error)]">
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                  <button onClick={() => setSection(i, {
                    columns: [...(s.columns || []), { key: '', label_vi: '', kind: 'text' as FieldKind }],
                  })}
                    className="text-xs text-[var(--primary-gold-dark)] hover:underline inline-flex items-center gap-1">
                    <Plus className="w-3 h-3" /> {t('dmsTemplateManager.addColumn')}
                  </button>
                </div>
              )}
            </div>
          ))}
          {sections.length === 0 && <p className="text-xs text-[var(--text-secondary)] italic">{t('dmsTemplateManager.noSectionsYet')}</p>}
        </div>
      </div>
    </div>
  );
}

// ─── list page ──────────────────────────────────────────────────────────
const TOKEN_KEY = 'kaori.access_token';

export default function TemplateManagerPage() {
  const t = useT();
  const [templates, setTemplates] = useState<TemplateDef[] | null>(null);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [editing, setEditing] = useState<TemplateDef | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const r = await api<{ items: TemplateDef[] }>('/api/v1/document-templates?include_inactive=true');
      setTemplates(r.items || []);
    } catch (e: any) { setProblem(e); }
  }, []);
  useEffect(() => { load(); }, [load]);

  // đang có bản nháp AI phân tích ('⏳') → poll danh sách tới khi xong
  const analyzing = (templates || []).some((tpl) => (tpl.description || '').startsWith('⏳'));
  useEffect(() => {
    if (!analyzing) return;
    const timer = setInterval(load, 4000);
    return () => clearInterval(timer);
  }, [analyzing, load]);

  async function onUploadTemplateFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    e.target.value = '';
    if (!f) return;
    setUploading(true);
    setProblem(null);
    try {
      const fd = new FormData();
      fd.append('file', f);
      const res = await fetch(`${API_BASE}/api/v1/upload`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${window.localStorage.getItem(TOKEN_KEY) ?? ''}`,
          'Idempotency-Key': safeRandomUUID(),
          'X-Template-Analysis': 'true',
        },
        body: fd,
      });
      const j = await res.json();
      if (!res.ok || !j.run_id) throw { title: j.title || j.detail || `HTTP ${res.status}` } as ProblemDetails;
      const name = f.name.replace(/\.[^.]+$/, '');
      await api('/api/v1/document-templates/from-file', {
        method: 'POST',
        body: JSON.stringify({ run_id: j.run_id, name_vi: name }),
      });
      await load(); // bản nháp '⏳' xuất hiện → poll tự chạy
    } catch (err: any) {
      setProblem(err.title ? err : { title: err?.message || t('dmsTemplateManager.errUploadFailed') });
    } finally {
      setUploading(false);
    }
  }

  async function clone(src: TemplateDef) {
    const name = window.prompt(
      t('dmsTemplateManager.promptCloneName', { name: src.name_vi }),
      t('dmsTemplateManager.cloneDefaultName', { name: src.name_vi }),
    );
    if (!name?.trim()) return;
    setBusy(src.template_id);
    try {
      const created = await api<TemplateDef>('/api/v1/document-templates', {
        method: 'POST',
        body: JSON.stringify({
          type_key: slugKey(name), name_vi: name.trim(), icon: src.icon || undefined,
          description: src.description || undefined, clone_of: src.template_id,
        }),
      });
      await load();
      setEditing(created);
    } catch (e: any) { setProblem(e); } finally { setBusy(null); }
  }

  async function createBlank() {
    const name = window.prompt(t('dmsTemplateManager.promptCreateBlank'));
    if (!name?.trim()) return;
    try {
      const created = await api<TemplateDef>('/api/v1/document-templates', {
        method: 'POST',
        body: JSON.stringify({ type_key: slugKey(name), name_vi: name.trim() }),
      });
      await load();
      setEditing(created);
    } catch (e: any) { setProblem(e); }
  }

  const mine = (templates || []).filter((tpl) => !tpl.is_global);
  const globals = (templates || []).filter((tpl) => tpl.is_global);

  function row(tpl: TemplateDef) {
    const isAnalyzing = (tpl.description || '').startsWith('⏳');
    const isFailed = (tpl.description || '').startsWith('⚠️');
    return (
      <div key={tpl.template_id}
        className="flex items-center gap-2.5 px-3 py-2.5 border-b border-[var(--border-color)]/50 last:border-b-0 hover:bg-[var(--bg-app)]/40">
        <span className="text-lg w-7 text-center shrink-0">{tpl.icon || '📄'}</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">
            {tpl.name_vi}
            {isAnalyzing && (
              <Badge variant="default" className="ml-1.5 text-[9px] inline-flex items-center gap-1">
                <Loader2 className="w-2.5 h-2.5 animate-spin" /> {t('dmsTemplateManager.badgeAiAnalyzing')}
              </Badge>
            )}
            {!tpl.is_active && !isAnalyzing && (
              <Badge variant="default" className="ml-1.5 text-[9px]">
                {isFailed ? t('dmsTemplateManager.badgeDraftAiError') : t('dmsTemplateManager.badgeDraftPendingApproval')}
              </Badge>
            )}
          </p>
          <p className="text-[11px] text-[var(--text-secondary)] truncate">
            {t('dmsTemplateManager.rowStats', { fieldCount: tpl.metadata_schema.length, sectionCount: tpl.section_outline.length })}
            {tpl.description ? ` — ${tpl.description}` : ''}
          </p>
        </div>
        {(tpl.default_labels || []).slice(0, 2).map((lb) => (
          <span key={lb} className="hidden sm:inline px-1.5 py-0.5 text-[10px] font-mono rounded bg-[var(--bg-app)]/80 border border-[var(--border-color)] text-[var(--text-secondary)]">{lb}</span>
        ))}
        <button onClick={() => clone(tpl)} disabled={busy === tpl.template_id}
          title={t('dmsTemplateManager.cloneTitle')}
          className="inline-flex items-center gap-1 text-xs text-[var(--text-secondary)] hover:text-[var(--primary-gold-dark)] shrink-0">
          {busy === tpl.template_id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Copy className="w-3.5 h-3.5" />}
          {t('dmsTemplateManager.cloneButton')}
        </button>
        {!tpl.is_global && !isAnalyzing && (
          <button onClick={() => setEditing(tpl)}
            className="inline-flex items-center gap-1 text-xs text-[var(--primary-gold-dark)] hover:underline shrink-0">
            <Pencil className="w-3.5 h-3.5" /> {tpl.is_active ? t('dmsTemplateManager.editButton') : t('dmsTemplateManager.approveAndEdit')}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title={t('dmsTemplateManager.pageTitle')}
        description={t('dmsTemplateManager.pageDescription')}
        actions={
          <div className="flex items-center gap-2">
            <input ref={fileRef} type="file" hidden onChange={onUploadTemplateFile}
              accept=".pdf,.docx,.doc,.md,.txt" />
            <Button variant="secondary" onClick={() => fileRef.current?.click()} disabled={uploading}>
              {uploading ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <FileUp className="w-4 h-4 mr-1.5" />}
              {t('dmsTemplateManager.uploadFromFile')}
            </Button>
            <Button onClick={createBlank}><Plus className="w-4 h-4 mr-1.5" /> {t('dmsTemplateManager.createNew')}</Button>
          </div>
        }
      />
      {problem && <ErrorBanner problem={problem} />}

      {editing && (
        <TemplateEditor tpl={editing} onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); load(); }} />
      )}

      {templates === null ? (
        <div className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin inline text-[var(--text-secondary)]" /></div>
      ) : (
        <>
          <section>
            <h2 className="text-sm font-semibold mb-2">{t('dmsTemplateManager.mineHeading', { count: mine.length })}</h2>
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom">
              {mine.length === 0 ? (
                <p className="px-3 py-6 text-center text-sm text-[var(--text-secondary)]">
                  {t('dmsTemplateManager.noMineTemplates')}
                </p>
              ) : mine.map(row)}
            </div>
          </section>
          <section>
            <h2 className="text-sm font-semibold mb-2">{t('dmsTemplateManager.globalsHeading', { count: globals.length })} <span className="text-[11px] font-normal text-[var(--text-secondary)]">{t('dmsTemplateManager.globalsHint')}</span></h2>
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom">
              {globals.map(row)}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
