// Schema-driven Page-Properties form (ADR-0042) — bảng thuộc tính kiểu
// Confluence: field render theo kind (user = người thật, date = typed date,
// status = lozenge controlled vocabulary). Validation là trust-first: BE trả
// warnings + completeness, FE hiển thị — không chặn.
'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { Loader2, Save, AlertTriangle } from 'lucide-react';
import { Button, Badge, cn, api } from '@/components/p2/foundation';
import { useLocale, useT } from '@/lib/i18n/provider';
import {
  FieldDef, DocRow, EnterpriseUser, pickLabel, statusTone, statusLabel, TONE_CLS,
} from './types';

let _usersCache: EnterpriseUser[] | null = null;
async function loadUsers(): Promise<EnterpriseUser[]> {
  if (_usersCache) return _usersCache;
  try {
    const r = await api<{ data: EnterpriseUser[] }>('/api/v1/enterprises/users?limit=200');
    _usersCache = (r as any).data ?? (r as any).items ?? [];
  } catch {
    _usersCache = [];
  }
  return _usersCache!;
}

export function StatusLozenge({ value, options }: { value: string; options: string[] }) {
  return (
    <span className={cn(
      'inline-block px-1.5 py-0.5 rounded border text-[10px] font-semibold uppercase tracking-wide',
      TONE_CLS[statusTone(value, options)])}>
      {statusLabel(value)}
    </span>
  );
}

export function CompletenessBadge({ value }: { value: number | null | undefined }) {
  const t = useT();
  if (value == null) return <Badge variant="default" className="text-[10px]">{t('dmsMetadataForm.completenessEmpty')}</Badge>;
  if (value >= 1) return <Badge variant="success" className="text-[10px]">{t('dmsMetadataForm.completenessFull')}</Badge>;
  return (
    <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded border bg-amber-50 text-amber-700 border-amber-200">
      <AlertTriangle className="w-3 h-3" /> {(value * 100).toFixed(0)}% {t('dmsMetadataForm.completenessSuffix')}
    </span>
  );
}

function FieldInput({ f, value, users, onChange }: {
  f: FieldDef; value: any; users: EnterpriseUser[];
  onChange: (v: any) => void;
}) {
  const t = useT();
  const base = 'w-full px-2 py-1.5 bg-white border border-[var(--border-color)] rounded text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30';
  switch (f.kind) {
    case 'long_text':
      return <textarea rows={3} className={base} value={value ?? ''} onChange={(e) => onChange(e.target.value)} />;
    case 'number':
    case 'money':
      return <input type="number" min={f.kind === 'money' ? 0 : undefined} className={base}
        value={value ?? ''} onChange={(e) => onChange(e.target.value === '' ? undefined : Number(e.target.value))} />;
    case 'date':
      return <input type="date" className={base} value={value ?? ''} onChange={(e) => onChange(e.target.value || undefined)} />;
    case 'user':
      return (
        <select className={base} value={value ?? ''} onChange={(e) => onChange(e.target.value || undefined)}>
          <option value="">{t('dmsMetadataForm.selectUserPlaceholder')}</option>
          {users.map((u) => <option key={u.id} value={u.id}>{u.name || u.email}</option>)}
          {value && !users.some((u) => u.id === value) && <option value={value}>{value}</option>}
        </select>
      );
    case 'select':
    case 'status':
      return (
        <select className={base} value={value ?? ''} onChange={(e) => onChange(e.target.value || undefined)}>
          <option value="">{t('dmsMetadataForm.selectPlaceholder')}</option>
          {(f.options || []).map((o) => <option key={o} value={o}>{statusLabel(o)}</option>)}
        </select>
      );
    default:
      return <input className={base} value={value ?? ''} onChange={(e) => onChange(e.target.value || undefined)} />;
  }
}

export function MetadataForm({ doc, schema, onSaved }: {
  doc: DocRow;
  schema: FieldDef[];
  onSaved: (updated: { metadata: Record<string, unknown>; completeness: number | null }) => void;
}) {
  const { locale } = useLocale();
  const t = useT();
  const [values, setValues] = useState<Record<string, any>>((doc.metadata as any) || {});
  const [users, setUsers] = useState<EnterpriseUser[]>([]);
  const [saving, setSaving] = useState(false);
  const [warnings, setWarnings] = useState<{ key: string; code: string; message_vi: string }[]>([]);
  const needsUsers = useMemo(() => schema.some((f) => f.kind === 'user'), [schema]);

  useEffect(() => { setValues((doc.metadata as any) || {}); setWarnings([]); }, [doc.doc_id]);
  useEffect(() => { if (needsUsers) loadUsers().then(setUsers); }, [needsUsers]);

  async function save() {
    setSaving(true);
    try {
      const r = await api<{
        metadata: Record<string, unknown>; completeness: number | null;
        warnings: { key: string; code: string; message_vi: string }[];
      }>(`/api/v1/document-repository/${doc.doc_id}/metadata`, {
        method: 'PATCH',
        body: JSON.stringify({ metadata: values }),
      });
      setValues(r.metadata as any);
      setWarnings(r.warnings || []);
      onSaved({ metadata: r.metadata, completeness: r.completeness });
    } catch (e: any) {
      setWarnings([{ key: '', code: 'error', message_vi: e?.title || t('dmsMetadataForm.saveFailed') }]);
    } finally {
      setSaving(false);
    }
  }

  if (!schema.length) {
    return (
      <p className="text-xs text-[var(--text-secondary)] italic">
        {t('dmsMetadataForm.noTemplateHint')}
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {/* bảng thuộc tính kiểu Confluence Page Properties */}
      <div className="border border-[var(--border-color)] rounded-md-custom overflow-hidden">
        {schema.map((f) => (
          <div key={f.key} className="grid grid-cols-[160px_1fr] border-b border-[var(--border-color)]/60 last:border-b-0">
            <div className="px-3 py-2 bg-[var(--bg-app)]/60 text-xs font-semibold flex items-center gap-1">
              {pickLabel(f, locale)}{f.required && <span className="text-[var(--state-error)]">*</span>}
            </div>
            <div className="px-2 py-1.5">
              <FieldInput f={f} value={values[f.key]} users={users}
                onChange={(v) => setValues((s) => ({ ...s, [f.key]: v }))} />
            </div>
          </div>
        ))}
      </div>

      {warnings.length > 0 && (
        <div className="text-[11px] space-y-0.5">
          {warnings.map((w, i) => (
            <p key={i} className="text-amber-700 flex items-center gap-1">
              <AlertTriangle className="w-3 h-3 shrink-0" /> {w.message_vi}
            </p>
          ))}
        </div>
      )}

      <div className="flex justify-end">
        <Button onClick={save} disabled={saving}>
          {saving ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Save className="w-4 h-4 mr-1.5" />}
          {t('dmsMetadataForm.saveButton')}
        </Button>
      </div>
    </div>
  );
}
