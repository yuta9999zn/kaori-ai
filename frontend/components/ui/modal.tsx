'use client';

import * as React from 'react';
import { X } from 'lucide-react';
import { cn } from '@/lib/cn';
import { useT } from '@/lib/i18n/provider';

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = 'md',
}: {
  open: boolean;
  onClose: () => void;
  title: React.ReactNode;
  description?: React.ReactNode;
  children?: React.ReactNode;
  footer?: React.ReactNode;
  size?: 'sm' | 'md' | 'lg';
}) {
  const t = useT();
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [open, onClose]);

  if (!open) return null;

  const widthCls = size === 'sm' ? 'max-w-sm' : size === 'lg' ? 'max-w-2xl' : 'max-w-md';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-[#1E1B18]/40 backdrop-blur-[2px]"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        className={cn(
          'relative w-full bg-surface rounded-2xl border border-subtle shadow-card',
          widthCls,
        )}
      >
        <div className="px-6 pt-6 pb-3 flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h2 className="text-h2 font-serif text-[#2E2A24]">{title}</h2>
            {description && (
              <p className="text-small text-[#7A7266] mt-1">{description}</p>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label={t('uiModal.close')}
            className="rounded-lg p-1.5 text-[#A89F90] hover:bg-muted hover:text-[#2E2A24] shrink-0"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        {children && <div className="px-6 pb-4">{children}</div>}
        {footer && (
          <div className="px-6 py-4 border-t border-subtle bg-muted/30 rounded-b-2xl flex justify-end gap-2">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
