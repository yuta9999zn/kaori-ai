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

const KIND_LABEL: Record<FieldKind, string> = {
  text: 'Chữ ngắn', long_text: 'Đoạn văn', number: 'Số', money: 'Tiền (VNĐ)',
  date: 'Ngày', user: 'Người', department: 'Phòng ban', select: 'Chọn 1',
  status: 'Trạng thái', link: 'Link',
};

function slugKey(s: string): string {
  return s.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D')
    .toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 40) || 'truong';
}

// ─── editor drawer ──────────────────────────────────────────────────────
function TemplateEditor({ tpl, onClose, onSaved }: {
  tpl: TemplateDef; onClose: () => void; onSaved: () => void;
}) {
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
        <h3 className="text-sm font-semibold flex-1">Sửa mẫu: {tpl.name_vi}</h3>
        <Button variant="secondary" onClick={onClose}><X className="w-3.5 h-3.5 mr-1" /> Đóng</Button>
        <Button onClick={save} disabled={saving}>
          {saving ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Save className="w-4 h-4 mr-1.5" />}
          Lưu mẫu
        </Button>
      </div>
      {problem && <ErrorBanner problem={problem} />}

      <div className="grid grid-cols-1 sm:grid-cols-[64px_1fr_1fr] gap-2">
        <div>
          <label className="text-xs font-semibold text-[var(--text-secondary)]">Icon</label>
          <input value={icon} onChange={(e) => setIcon(e.target.value)} className={cn(inputCls, 'w-full mt-1 text-center')} placeholder="📄" />
        </div>
        <div>
          <label className="text-xs font-semibold text-[var(--text-secondary)]">Tên mẫu</label>
          <input value={name} onChange={(e) => setName(e.target.value)} className={cn(inputCls, 'w-full mt-1')} />
        </div>
        <div>
          <label className="text-xs font-semibold text-[var(--text-secondary)]">Nhãn tự gắn</label>
          <input value={labels} onChange={(e) => setLabels(e.target.value)} className={cn(inputCls, 'w-full mt-1')} placeholder="loai:hop-dong" />
        </div>
      </div>
      <div>
        <label className="text-xs font-semibold text-[var(--text-secondary)]">Mô tả</label>
        <input value={desc} onChange={(e) => setDesc(e.target.value)} className={cn(inputCls, 'w-full mt-1')} />
      </div>

      {/* thuộc tính — bảng Page Properties của mẫu */}
      <div>
        <div className="flex items-center gap-2 mb-1.5">
          <label className="text-xs font-semibold text-[var(--text-secondary)] flex-1">
            Thuộc tính tài liệu ({fields.length}) — tài liệu theo mẫu này cần khai gì
          </label>
          <button onClick={() => setFields((fs) => [...fs, { key: '', label_vi: '', kind: 'text', required: false }])}
            className="text-xs text-[var(--primary-gold-dark)] hover:underline inline-flex items-center gap-1">
            <Plus className="w-3 h-3" /> Thêm thuộc tính
          </button>
        </div>
        <div className="space-y-1.5">
          {fields.map((f, i) => (
            <div key={i} className="flex items-center gap-1.5 flex-wrap bg-[var(--bg-app)]/40 border border-[var(--border-color)]/60 rounded px-2 py-1.5">
              <GripVertical className="w-3.5 h-3.5 text-[var(--text-secondary)]/50 shrink-0" />
              <input value={f.label_vi} placeholder="Nhãn (vd Hạn chót)"
                onChange={(e) => setField(i, { label_vi: e.target.value, key: f.key || slugKey(e.target.value) })}
                className={cn(inputCls, 'w-36')} />
              <input value={(f as any).label_en || ''} placeholder="EN label" title="Nhãn tiếng Anh (các ngôn ngữ khác fallback EN → VI)"
                onChange={(e) => setField(i, { label_en: e.target.value || undefined } as any)}
                className={cn(inputCls, 'w-32')} />
              <input value={f.key} placeholder="key" title="Khoá kỹ thuật (tự sinh từ nhãn)"
                onChange={(e) => setField(i, { key: slugKey(e.target.value) })}
                className={cn(inputCls, 'w-28 font-mono text-xs')} />
              <select value={f.kind} onChange={(e) => setField(i, { kind: e.target.value as FieldKind })}
                className={cn(inputCls, 'w-28')}>
                {Object.entries(KIND_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              {(f.kind === 'select' || f.kind === 'status') && (
                <input value={(f.options || []).join(', ')} placeholder="lựa chọn, cách nhau dấu phẩy"
                  onChange={(e) => setField(i, { options: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })}
                  className={cn(inputCls, 'flex-1 min-w-[180px]')} />
              )}
              <label className="text-xs flex items-center gap-1 shrink-0">
                <input type="checkbox" checked={!!f.required} onChange={(e) => setField(i, { required: e.target.checked })}
                  className="accent-[var(--primary-gold-dark)]" />
                bắt buộc
              </label>
              <button onClick={() => setFields((fs) => fs.filter((_, j) => j !== i))}
                className="text-[var(--text-secondary)] hover:text-[var(--state-error)] shrink-0">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
          {fields.length === 0 && <p className="text-xs text-[var(--text-secondary)] italic">Chưa có thuộc tính nào.</p>}
        </div>
      </div>

      {/* dàn bài — các mục tài liệu cần có */}
      <div>
        <div className="flex items-center gap-2 mb-1.5">
          <label className="text-xs font-semibold text-[var(--text-secondary)] flex-1">
            Các mục nội dung ({sections.length}) — tài liệu cần có những phần gì
          </label>
          <button onClick={() => setSections((ss) => [...ss, { heading_vi: '', icon: '', hint_vi: '' }])}
            className="text-xs text-[var(--primary-gold-dark)] hover:underline inline-flex items-center gap-1">
            <Plus className="w-3 h-3" /> Thêm mục
          </button>
        </div>
        <div className="space-y-1.5">
          {sections.map((s, i) => (
            <div key={i} className="bg-[var(--bg-app)]/40 border border-[var(--border-color)]/60 rounded px-2 py-1.5 space-y-1.5">
              <div className="flex items-center gap-1.5">
                <input value={s.icon || ''} placeholder="🎯" onChange={(e) => setSection(i, { icon: e.target.value })}
                  className={cn(inputCls, 'w-12 text-center')} />
                <input value={s.heading_vi} placeholder="Tiêu đề mục (vd Phạm vi)"
                  onChange={(e) => setSection(i, { heading_vi: e.target.value, key: (s as any).key || slugKey(e.target.value) })}
                  className={cn(inputCls, 'w-40')} />
                <input value={(s as any).heading_en || ''} placeholder="EN heading"
                  onChange={(e) => setSection(i, { heading_en: e.target.value || undefined } as any)}
                  className={cn(inputCls, 'w-32')} />
                <input value={s.hint_vi || ''} placeholder="Gợi ý nội dung mục này…"
                  onChange={(e) => setSection(i, { hint_vi: e.target.value })}
                  className={cn(inputCls, 'flex-1')} />
                <select value={s.body_kind || 'prose'}
                  onChange={(e) => setSection(i, {
                    body_kind: e.target.value as any,
                    columns: e.target.value === 'table' ? (s.columns || []) : undefined,
                  })}
                  className={cn(inputCls, 'w-24')}>
                  <option value="prose">Văn bản</option>
                  <option value="table">Bảng</option>
                  <option value="checklist">Checklist</option>
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
                      <input value={c.label_vi} placeholder="Nhãn cột (vd Mã lỗi)"
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
                      <select value={c.width ?? ''} title="Độ rộng cột"
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
                        <input value={(c.options || []).join(', ')} placeholder="lựa chọn, phẩy"
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
                    <Plus className="w-3 h-3" /> Thêm cột
                  </button>
                </div>
              )}
            </div>
          ))}
          {sections.length === 0 && <p className="text-xs text-[var(--text-secondary)] italic">Chưa có mục nào.</p>}
        </div>
      </div>
    </div>
  );
}

// ─── list page ──────────────────────────────────────────────────────────
const TOKEN_KEY = 'kaori.access_token';

export default function TemplateManagerPage() {
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
  const analyzing = (templates || []).some((t) => (t.description || '').startsWith('⏳'));
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
          'Idempotency-Key': crypto.randomUUID(),
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
      setProblem(err.title ? err : { title: err?.message || 'Tải file mẫu thất bại' });
    } finally {
      setUploading(false);
    }
  }

  async function clone(src: TemplateDef) {
    const name = window.prompt('Tên mẫu mới (nhân bản từ ' + src.name_vi + '):', src.name_vi + ' — tuỳ chỉnh');
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
    const name = window.prompt('Tên mẫu tài liệu mới (vd "Đơn đề nghị thanh toán"):');
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

  const mine = (templates || []).filter((t) => !t.is_global);
  const globals = (templates || []).filter((t) => t.is_global);

  function row(t: TemplateDef) {
    const isAnalyzing = (t.description || '').startsWith('⏳');
    const isFailed = (t.description || '').startsWith('⚠️');
    return (
      <div key={t.template_id}
        className="flex items-center gap-2.5 px-3 py-2.5 border-b border-[var(--border-color)]/50 last:border-b-0 hover:bg-[var(--bg-app)]/40">
        <span className="text-lg w-7 text-center shrink-0">{t.icon || '📄'}</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">
            {t.name_vi}
            {isAnalyzing && (
              <Badge variant="default" className="ml-1.5 text-[9px] inline-flex items-center gap-1">
                <Loader2 className="w-2.5 h-2.5 animate-spin" /> AI đang phân tích
              </Badge>
            )}
            {!t.is_active && !isAnalyzing && (
              <Badge variant="default" className="ml-1.5 text-[9px]">
                {isFailed ? 'nháp — AI lỗi' : 'nháp — chờ duyệt'}
              </Badge>
            )}
          </p>
          <p className="text-[11px] text-[var(--text-secondary)] truncate">
            {t.metadata_schema.length} thuộc tính · {t.section_outline.length} mục
            {t.description ? ` — ${t.description}` : ''}
          </p>
        </div>
        {(t.default_labels || []).slice(0, 2).map((lb) => (
          <span key={lb} className="hidden sm:inline px-1.5 py-0.5 text-[10px] font-mono rounded bg-[var(--bg-app)]/80 border border-[var(--border-color)] text-[var(--text-secondary)]">{lb}</span>
        ))}
        <button onClick={() => clone(t)} disabled={busy === t.template_id}
          title="Nhân bản để tuỳ chỉnh"
          className="inline-flex items-center gap-1 text-xs text-[var(--text-secondary)] hover:text-[var(--primary-gold-dark)] shrink-0">
          {busy === t.template_id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Copy className="w-3.5 h-3.5" />}
          Nhân bản
        </button>
        {!t.is_global && !isAnalyzing && (
          <button onClick={() => setEditing(t)}
            className="inline-flex items-center gap-1 text-xs text-[var(--primary-gold-dark)] hover:underline shrink-0">
            <Pencil className="w-3.5 h-3.5" /> {t.is_active ? 'Sửa' : 'Duyệt & sửa'}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Mẫu tài liệu"
        description="Định nghĩa loại tài liệu: thuộc tính cần khai (bảng Page Properties) + các mục nội dung cần có. Gắn mẫu vào trang thư mục để tài liệu tải lên tự thừa hưởng."
        actions={
          <div className="flex items-center gap-2">
            <input ref={fileRef} type="file" hidden onChange={onUploadTemplateFile}
              accept=".pdf,.docx,.doc,.md,.txt" />
            <Button variant="secondary" onClick={() => fileRef.current?.click()} disabled={uploading}>
              {uploading ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <FileUp className="w-4 h-4 mr-1.5" />}
              Tạo mẫu từ file
            </Button>
            <Button onClick={createBlank}><Plus className="w-4 h-4 mr-1.5" /> Tạo mẫu mới</Button>
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
            <h2 className="text-sm font-semibold mb-2">Mẫu của doanh nghiệp ({mine.length})</h2>
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom">
              {mine.length === 0 ? (
                <p className="px-3 py-6 text-center text-sm text-[var(--text-secondary)]">
                  Chưa có mẫu riêng — tạo mới hoặc nhân bản một mẫu hệ thống bên dưới.
                </p>
              ) : mine.map(row)}
            </div>
          </section>
          <section>
            <h2 className="text-sm font-semibold mb-2">Mẫu hệ thống ({globals.length}) <span className="text-[11px] font-normal text-[var(--text-secondary)]">— chỉ đọc, nhân bản để tuỳ chỉnh</span></h2>
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom">
              {globals.map(row)}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
