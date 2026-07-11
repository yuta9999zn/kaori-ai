// SearchableSelect — combobox có ô tìm kiếm trên đầu (yêu cầu UX 11/07):
// gõ để lọc theo TÊN (không phân biệt hoa thường, khớp gần đúng) hoặc theo
// SỐ THỨ TỰ của option trong danh sách (gõ "3" → option thứ 3 nổi lên đầu).
// Thay thế <select> thuần ở những chỗ danh sách dài; không thêm lib ngoài.
'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, Search, Check } from 'lucide-react';
import { cn } from '@/components/p2/foundation';
import { useT } from '@/lib/i18n/provider';

export interface SelectOption {
  value: string;
  label: string;
}

// bỏ dấu tiếng Việt để "gan dung" khớp "gần đúng"
function fold(s: string): string {
  return (s || '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/đ/g, 'd').replace(/Đ/g, 'D')
    .toLowerCase();
}

export function SearchableSelect({
  value, onChange, options, placeholder = '— Chọn —', className, disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  options: SelectOption[];
  placeholder?: string;
  className?: string;
  disabled?: boolean;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setQ('');
    // focus ô tìm ngay khi mở
    const id = setTimeout(() => inputRef.current?.focus(), 0);
    function onDoc(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', onDoc);
    return () => { clearTimeout(id); document.removeEventListener('mousedown', onDoc); };
  }, [open]);

  const filtered = useMemo(() => {
    const needle = fold(q.trim());
    if (!needle) return options.map((o, i) => ({ ...o, idx: i + 1 }));
    const withIdx = options.map((o, i) => ({ ...o, idx: i + 1 }));
    // số thuần → ưu tiên khớp số thứ tự, vẫn kèm khớp tên
    const byName = withIdx.filter((o) => fold(o.label).includes(needle));
    if (/^\d+$/.test(needle)) {
      const byIdx = withIdx.filter((o) => String(o.idx).startsWith(needle));
      const seen = new Set(byIdx.map((o) => o.value));
      return [...byIdx, ...byName.filter((o) => !seen.has(o.value))];
    }
    return byName;
  }, [q, options]);

  const current = options.find((o) => o.value === value);

  return (
    <div ref={rootRef} className={cn('relative', className)}>
      <button type="button" disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        className={cn(
          'w-full flex items-center gap-1.5 px-2.5 py-2 bg-white border border-[var(--border-color)]',
          'rounded-md-custom text-sm text-left disabled:opacity-50',
          open && 'ring-2 ring-[var(--primary-gold)]/30',
        )}>
        <span className={cn('flex-1 truncate', !current && 'text-[var(--text-secondary)]')}>
          {current?.label ?? placeholder}
        </span>
        <ChevronDown className="w-3.5 h-3.5 text-[var(--text-secondary)] shrink-0" />
      </button>

      {open && (
        <div className="absolute z-50 mt-1 w-full min-w-[220px] bg-white border border-[var(--border-color)] rounded-md-custom shadow-lg overflow-hidden">
          <div className="relative border-b border-[var(--border-color)]/70">
            <Search className="w-3.5 h-3.5 text-[var(--text-secondary)] absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input ref={inputRef} value={q} onChange={(e) => setQ(e.target.value)}
              placeholder={t('searchableSelect.searchPlaceholder')}
              className="w-full pl-8 pr-2 py-2 text-sm focus:outline-none"
              onKeyDown={(e) => {
                if (e.key === 'Escape') setOpen(false);
                if (e.key === 'Enter' && filtered.length > 0) {
                  onChange(filtered[0].value); setOpen(false);
                }
              }} />
          </div>
          <div className="max-h-64 overflow-y-auto">
            {filtered.length === 0 && (
              <p className="px-3 py-2.5 text-xs text-[var(--text-secondary)]">{t('searchableSelect.noMatch')}</p>
            )}
            {filtered.map((o) => (
              <button key={o.value || `__empty_${o.idx}`} type="button"
                onClick={() => { onChange(o.value); setOpen(false); }}
                className={cn(
                  'w-full flex items-center gap-2 px-2.5 py-2 text-sm text-left hover:bg-[var(--bg-app)]/60',
                  o.value === value && 'bg-[var(--primary-gold)]/10',
                )}>
                <span className="text-[10px] text-[var(--text-secondary)] font-mono w-6 shrink-0 text-right">{o.idx}.</span>
                <span className="flex-1 truncate">{o.label}</span>
                {o.value === value && <Check className="w-3.5 h-3.5 text-[var(--primary-gold-dark)] shrink-0" />}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
