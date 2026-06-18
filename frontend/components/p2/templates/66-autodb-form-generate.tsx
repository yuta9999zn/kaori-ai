// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 66. /p2/auto-db/forms/generate — Form Generator (F-057 🔵 Phase 2)
// ----------------------------------------------------------------------------
// Sinh form CRUD từ schema:
//   - Chọn 1 schema đã active.
//   - Chọn loại form: Create / Edit / List+filter / Detail / Delete confirm.
//   - Tuỳ chọn: validation rule (auto từ NOT NULL + type), label tiếng Việt
//     (auto từ language_dictionary), required/optional toggle.
//   - Live preview render form bên phải.
//   - Click "Sinh code" → trả về Next.js TSX boilerplate (clipboard).
//
// Wire (Phase 2): `POST /api/v1/auto-db/forms/generate` returns code string.
// Phase 1 không có endpoint — preview only.
// ============================================================================

import React, { useMemo, useState } from 'react';
import {
  FileText, ArrowLeft, Database, Sparkles, Copy, Eye, ShieldCheck,
  Loader2, CheckCircle2, FileCode,
} from 'lucide-react';

import {
  Button, Badge, Input, Checkbox, ErrorBanner, SuccessBanner, cn,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
// ============================================================================
// Types
// ============================================================================

type FormKind = 'create' | 'edit' | 'list' | 'detail' | 'delete';

const FORM_KIND_META: Record<FormKind, { label: string; description: string; icon: any }> = {
  create: { label: 'Create',          description: 'Form thêm bản ghi mới.',                 icon: FileText },
  edit:   { label: 'Edit',            description: 'Form sửa 1 bản ghi.',                    icon: FileText },
  list:   { label: 'List + filter',    description: 'Bảng list + filter + pagination.',       icon: FileText },
  detail: { label: 'Detail',           description: 'Trang chi tiết read-only.',              icon: FileText },
  delete: { label: 'Delete confirm',   description: 'Modal xác nhận xoá.',                    icon: FileText },
};

interface SchemaColumn {
  name:     string;
  type:     'integer' | 'numeric' | 'varchar' | 'date' | 'timestamp' | 'boolean';
  nullable: boolean;
  is_pk:    boolean;
  vi_label: string;
}

interface SchemaSummary {
  id:       string;
  name:     string;
  domain:   string;
  columns:  SchemaColumn[];
}

const SCHEMAS: SchemaSummary[] = [
  {
    id: 'sch_orders', name: 'orders', domain: 'Bán hàng',
    columns: [
      { name: 'order_id',     type: 'integer',  nullable: false, is_pk: true,  vi_label: 'Mã đơn hàng' },
      { name: 'customer_id',  type: 'integer',  nullable: false, is_pk: false, vi_label: 'Khách hàng' },
      { name: 'order_date',   type: 'date',     nullable: false, is_pk: false, vi_label: 'Ngày đặt' },
      { name: 'total_amount', type: 'numeric',  nullable: false, is_pk: false, vi_label: 'Tổng tiền' },
      { name: 'status',       type: 'varchar',  nullable: false, is_pk: false, vi_label: 'Trạng thái' },
      { name: 'note',         type: 'varchar',  nullable: true,  is_pk: false, vi_label: 'Ghi chú' },
    ],
  },
  {
    id: 'sch_customers', name: 'customers', domain: 'CRM',
    columns: [
      { name: 'customer_id', type: 'integer',  nullable: false, is_pk: true,  vi_label: 'Mã khách' },
      { name: 'full_name',   type: 'varchar',  nullable: false, is_pk: false, vi_label: 'Họ và tên' },
      { name: 'email',       type: 'varchar',  nullable: true,  is_pk: false, vi_label: 'Email' },
      { name: 'created_at',  type: 'timestamp', nullable: false, is_pk: false, vi_label: 'Ngày tạo' },
    ],
  },
];

// ============================================================================
// Page
// ============================================================================

export default function FormGeneratePage() {
  const [schemaId, setSchemaId] = useState(SCHEMAS[0].id);
  const [formKind, setFormKind] = useState<FormKind>('create');
  const [columnFlags, setColumnFlags] = useState<Record<string, { include: boolean; required: boolean }>>(() => {
    return Object.fromEntries(SCHEMAS[0].columns.map((c) => [c.name, { include: !c.is_pk, required: !c.nullable }]));
  });
  const [generating, setGenerating] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [problem, setProblem] = useState<any>(null);

  const schema = useMemo(() => SCHEMAS.find((s) => s.id === schemaId)!, [schemaId]);

  function selectSchema(id: string) {
    setSchemaId(id);
    const s = SCHEMAS.find((x) => x.id === id)!;
    setColumnFlags(Object.fromEntries(s.columns.map((c) => [c.name, { include: !c.is_pk, required: !c.nullable }])));
  }

  function toggleColumn(name: string, key: 'include' | 'required') {
    setColumnFlags((prev) => ({ ...prev, [name]: { ...prev[name], [key]: !prev[name][key] } }));
  }

  async function onGenerate() {
    setGenerating(true);
    setSuccess(null);
    setProblem(null);
    try {
      // Phase 2 wire endpoint
      await new Promise((r) => setTimeout(r, 1200));
      const code = generateCode(schema, formKind, columnFlags);
      try {
        await navigator.clipboard.writeText(code);
        setSuccess('Đã sinh code TSX và copy vào clipboard. Paste vào file Next.js để dùng.');
      } catch {
        setSuccess('Đã sinh code TSX (xem preview bên phải).');
      }
    } catch (e: any) {
      setProblem(e);
    } finally {
      setGenerating(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Sinh form CRUD"
        description="Chọn schema + loại form → AI sinh form Next.js TSX với label tiếng Việt + validation."
        actions={
          <>
            <Badge variant="info">Phase 2 · F-057</Badge>
            <a href="/p2/auto-db">
              <Button variant="tertiary" size="md"><ArrowLeft className="w-4 h-4 mr-2" /> Auto DB</Button>
            </a>
            <Button variant="primary" size="md" onClick={onGenerate} isLoading={generating} disabled={generating}>
              <Sparkles className="w-4 h-4 mr-2" /> Sinh code
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-4">
        {problem && <ErrorBanner problem={problem} />}
        {success && <SuccessBanner message={success} />}

        <div className="grid grid-cols-1 xl:grid-cols-[420px_1fr] gap-4">
          {/* Left: config */}
          <div className="space-y-4">
            {/* Schema picker */}
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-4 shadow-soft-sm">
              <div className="flex items-center gap-2 mb-3">
                <Database className="w-4 h-4 text-[var(--primary-gold-dark)]" />
                <h3 className="font-serif text-sm text-[var(--text-primary)]">Chọn schema</h3>
              </div>
              <div className="space-y-1.5">
                {SCHEMAS.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => selectSchema(s.id)}
                    className={cn(
                      'w-full text-left p-3 rounded-md-custom border transition-all',
                      schemaId === s.id
                        ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/8'
                        : 'border-[var(--border-color)] bg-[var(--bg-app)] hover:border-[var(--primary-gold)]/40',
                    )}
                  >
                    <p className="font-mono text-sm text-[var(--text-primary)]">{s.name}</p>
                    <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">{s.domain} · {s.columns.length} cột</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Form kind */}
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-4 shadow-soft-sm">
              <div className="flex items-center gap-2 mb-3">
                <FileText className="w-4 h-4 text-[var(--primary-gold-dark)]" />
                <h3 className="font-serif text-sm text-[var(--text-primary)]">Loại form</h3>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {(['create', 'edit', 'list', 'detail', 'delete'] as FormKind[]).map((k) => {
                  const meta = FORM_KIND_META[k];
                  const active = formKind === k;
                  return (
                    <button
                      key={k}
                      onClick={() => setFormKind(k)}
                      className={cn(
                        'text-left p-3 rounded-md-custom border transition-all',
                        active
                          ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/8'
                          : 'border-[var(--border-color)] bg-[var(--bg-app)] hover:border-[var(--primary-gold)]/40',
                      )}
                    >
                      <p className="font-medium text-sm text-[var(--text-primary)]">{meta.label}</p>
                      <p className="text-[11px] text-[var(--text-secondary)] mt-0.5 leading-snug">{meta.description}</p>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Column toggles */}
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-4 shadow-soft-sm">
              <div className="flex items-center gap-2 mb-3">
                <CheckCircle2 className="w-4 h-4 text-[var(--primary-gold-dark)]" />
                <h3 className="font-serif text-sm text-[var(--text-primary)]">Cột muốn hiển thị</h3>
              </div>
              <div className="space-y-1.5">
                {schema.columns.map((c) => (
                  <div key={c.name} className="flex items-center justify-between p-2 rounded-sm-custom hover:bg-[var(--bg-app)]">
                    <Checkbox
                      checked={!!columnFlags[c.name]?.include}
                      onChange={() => toggleColumn(c.name, 'include')}
                      label={
                        <span className="text-sm">
                          <span className="font-mono text-[var(--text-primary)]">{c.name}</span>
                          <span className="text-[11px] text-[var(--text-secondary)] ml-2">{c.vi_label}</span>
                        </span>
                      }
                    />
                    <label className="text-[11px] text-[var(--text-secondary)] flex items-center gap-1.5">
                      <input
                        type="checkbox"
                        checked={!!columnFlags[c.name]?.required}
                        onChange={() => toggleColumn(c.name, 'required')}
                        disabled={!columnFlags[c.name]?.include}
                        className="w-3 h-3 accent-[var(--primary-gold)]"
                      />
                      Required
                    </label>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right: preview */}
          <div className="space-y-4">
            <FormPreview schema={schema} formKind={formKind} columnFlags={columnFlags} />
            <CodePreview schema={schema} formKind={formKind} columnFlags={columnFlags} />
          </div>
        </div>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            Validation auto-derived: NOT NULL → required, NUMERIC → number input + decimal mask, DATE → date picker.
            Label tiếng Việt lấy từ <span className="font-mono">config/language_dictionary.json</span>.
          </p>
        </div>
      </div>
    </>
  );
}

// ============================================================================
// Live preview
// ============================================================================

function FormPreview({
  schema, formKind, columnFlags,
}: { schema: SchemaSummary; formKind: FormKind; columnFlags: Record<string, { include: boolean; required: boolean }> }) {
  const visibleCols = schema.columns.filter((c) => columnFlags[c.name]?.include);

  return (
    <div className="bg-white border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
      <div className="border-b border-[var(--border-color)] px-4 py-2 flex items-center justify-between bg-[var(--bg-app)]">
        <div className="flex items-center gap-2">
          <Eye className="w-4 h-4 text-[var(--primary-gold-dark)]" />
          <span className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">Preview · {FORM_KIND_META[formKind].label}</span>
        </div>
        <span className="text-[11px] text-[var(--text-secondary)] font-mono">{schema.name}</span>
      </div>
      <div className="p-6 lg:p-8 min-h-[300px]">
        {formKind === 'create' || formKind === 'edit' ? (
          <div className="space-y-4 max-w-md">
            {visibleCols.map((c) => (
              <div key={c.name} className="space-y-1.5">
                <label className="text-sm font-medium text-[var(--text-primary)]">
                  {c.vi_label}
                  {columnFlags[c.name]?.required && <span className="text-[var(--state-error)] ml-1">*</span>}
                </label>
                <input
                  type={c.type === 'date' ? 'date' : c.type === 'integer' || c.type === 'numeric' ? 'number' : 'text'}
                  className="w-full h-10 px-3 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)]"
                  placeholder={`Nhập ${c.vi_label.toLowerCase()}`}
                  readOnly
                />
              </div>
            ))}
            <Button variant="primary" size="md" className="w-full">
              {formKind === 'create' ? 'Tạo mới' : 'Cập nhật'}
            </Button>
          </div>
        ) : formKind === 'list' ? (
          <div className="overflow-auto">
            <table className="w-full text-sm text-left border border-[var(--border-color)] rounded-sm-custom">
              <thead className="bg-[var(--bg-app)] border-b border-[var(--border-color)] text-[11px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
                <tr>
                  {visibleCols.map((c) => <th key={c.name} className="px-3 py-2">{c.vi_label}</th>)}
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]/60">
                {[1, 2, 3].map((i) => (
                  <tr key={i}>
                    {visibleCols.map((c) => (
                      <td key={c.name} className="px-3 py-2 text-xs text-[var(--text-primary)]">
                        {c.type === 'numeric' ? '1.245.300₫' : c.type === 'date' ? '2026-04-30' : `Mẫu ${i}`}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : formKind === 'detail' ? (
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-2xl">
            {visibleCols.map((c) => (
              <div key={c.name} className="border border-[var(--border-color)] rounded-md-custom p-3 bg-[var(--bg-app)]/40">
                <dt className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">{c.vi_label}</dt>
                <dd className="text-sm text-[var(--text-primary)] mt-1">
                  {c.type === 'numeric' ? '1.245.300₫' : c.type === 'date' ? '2026-04-30' : 'Giá trị mẫu'}
                </dd>
              </div>
            ))}
          </dl>
        ) : (
          <div className="max-w-md mx-auto bg-[var(--state-error)]/8 border border-[var(--state-error)]/30 rounded-md-custom p-5 text-center">
            <p className="font-serif text-base text-[var(--text-primary)]">Xác nhận xoá?</p>
            <p className="text-xs text-[var(--text-secondary)] mt-1">Hành động này không thể hoàn tác.</p>
            <div className="flex justify-center gap-2 mt-4">
              <Button variant="tertiary" size="sm">Huỷ</Button>
              <Button variant="destructive" size="sm">Xác nhận xoá</Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function CodePreview({
  schema, formKind, columnFlags,
}: { schema: SchemaSummary; formKind: FormKind; columnFlags: Record<string, { include: boolean; required: boolean }> }) {
  const code = generateCode(schema, formKind, columnFlags);
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
      <div className="border-b border-[var(--border-color)] px-4 py-2 flex items-center justify-between bg-[var(--bg-app)]">
        <div className="flex items-center gap-2">
          <FileCode className="w-4 h-4 text-[var(--primary-gold-dark)]" />
          <span className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">Code TSX</span>
        </div>
        <button
          onClick={() => navigator.clipboard?.writeText(code)}
          className="inline-flex items-center gap-1 text-[11px] text-[var(--text-secondary)] hover:text-[var(--primary-gold-dark)] transition-colors"
        >
          <Copy className="w-3.5 h-3.5" /> Copy
        </button>
      </div>
      <pre className="px-4 py-3 text-[11px] font-mono text-[var(--text-primary)] whitespace-pre overflow-auto leading-relaxed max-h-[400px] bg-[var(--bg-app)]/30">
        {code}
      </pre>
    </div>
  );
}

function generateCode(schema: SchemaSummary, formKind: FormKind, columnFlags: Record<string, { include: boolean; required: boolean }>): string {
  const visibleCols = schema.columns.filter((c) => columnFlags[c.name]?.include);
  const componentName = `${schema.name.charAt(0).toUpperCase()}${schema.name.slice(1)}${formKind.charAt(0).toUpperCase()}${formKind.slice(1)}Form`;

  if (formKind === 'create' || formKind === 'edit') {
    return `// Generated by Kaori Auto DB · F-057
import { useState } from 'react';
import { Button, Input } from '@/components/ui';

export default function ${componentName}() {
  const [form, setForm] = useState({
${visibleCols.map((c) => `    ${c.name}: ${c.type === 'integer' || c.type === 'numeric' ? '0' : `''`},`).join('\n')}
  });

  async function onSubmit() {
    await fetch('/api/v1/${schema.name}${formKind === 'edit' ? '/<id>' : ''}', {
      method: '${formKind === 'create' ? 'POST' : 'PUT'}',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    });
  }

  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit(); }} className="space-y-4">
${visibleCols.map((c) => `      <Input label="${c.vi_label}" required={${columnFlags[c.name]?.required ?? false}} value={form.${c.name}} onChange={(e) => setForm({ ...form, ${c.name}: e.target.value })} />`).join('\n')}
      <Button variant="primary" type="submit">${formKind === 'create' ? 'Tạo mới' : 'Cập nhật'}</Button>
    </form>
  );
}`;
  }

  if (formKind === 'list') {
    return `// Generated by Kaori Auto DB · F-057
import { useEffect, useState } from 'react';

export default function ${componentName}() {
  const [items, setItems] = useState([]);
  useEffect(() => {
    fetch('/api/v1/${schema.name}?limit=50').then((r) => r.json()).then((d) => setItems(d.items));
  }, []);

  return (
    <table className="w-full text-sm text-left">
      <thead><tr>
${visibleCols.map((c) => `        <th>${c.vi_label}</th>`).join('\n')}
      </tr></thead>
      <tbody>
        {items.map((it) => (
          <tr key={it.${schema.columns.find((c) => c.is_pk)?.name ?? 'id'}}>
${visibleCols.map((c) => `            <td>{it.${c.name}}</td>`).join('\n')}
          </tr>
        ))}
      </tbody>
    </table>
  );
}`;
  }

  if (formKind === 'detail') {
    return `// Generated by Kaori Auto DB · F-057
export default async function ${componentName}({ params }) {
  const data = await fetch(\`/api/v1/${schema.name}/\${params.id}\`).then((r) => r.json());
  return (
    <dl className="grid grid-cols-2 gap-3">
${visibleCols.map((c) => `      <div><dt>${c.vi_label}</dt><dd>{data.${c.name}}</dd></div>`).join('\n')}
    </dl>
  );
}`;
  }

  return `// Generated by Kaori Auto DB · F-057
export function ${componentName}({ id, onClose }) {
  async function onConfirm() {
    await fetch(\`/api/v1/${schema.name}/\${id}\`, { method: 'DELETE' });
    onClose();
  }
  return (
    <div className="modal">
      <h2>Xác nhận xoá ${schema.name}?</h2>
      <button onClick={onClose}>Huỷ</button>
      <button onClick={onConfirm}>Xác nhận xoá</button>
    </div>
  );
}`;
}
