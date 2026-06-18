'use client';
import { useState, useRef, useEffect } from 'react';
import { Globe, Check, ChevronDown } from 'lucide-react';
import { useLocale } from '@/lib/i18n/provider';
import { LOCALE_META, LOCALES, type Locale } from '@/lib/i18n/dictionary';
import { cn } from '@/lib/cn';

export function LocalePicker({ compact = false }: { compact?: boolean }) {
  const { locale, setLocale } = useLocale();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  const current = LOCALE_META[locale];

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        className={cn(
          'inline-flex items-center gap-2 rounded-xl border border-subtle bg-surface px-3 py-1.5 text-small transition-colors hover:bg-muted',
          open && 'ring-2 ring-brand-500/30 border-brand-200',
        )}
        aria-label="Change language"
        aria-expanded={open}
      >
        {compact ? (
          <span className="text-base leading-none" aria-hidden>{current.flag}</span>
        ) : (
          <>
            <Globe className="w-4 h-4 text-[#7A7266]" />
            <span className="text-base leading-none" aria-hidden>{current.flag}</span>
            <span className="text-[#2E2A24]">{current.native}</span>
          </>
        )}
        <ChevronDown className={cn('w-3.5 h-3.5 text-[#7A7266] transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-48 rounded-2xl border border-subtle bg-surface shadow-lg z-50 overflow-hidden">
          {(LOCALES as readonly Locale[]).map(l => {
            const meta = LOCALE_META[l];
            const active = l === locale;
            return (
              <button
                key={l}
                onClick={() => { setLocale(l); setOpen(false); }}
                className={cn(
                  'w-full flex items-center gap-3 px-3 py-2.5 text-small transition-colors',
                  active ? 'bg-brand-50 text-brand-700 font-medium' : 'text-[#2E2A24] hover:bg-muted',
                )}
              >
                <span className="text-lg leading-none" aria-hidden>{meta.flag}</span>
                <span className="flex-1 text-left">{meta.native}</span>
                {active && <Check className="w-4 h-4 text-brand-600" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
