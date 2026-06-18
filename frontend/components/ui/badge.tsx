import * as React from 'react';
import { cn } from '@/lib/cn';

export type BadgeTone = 'brand' | 'success' | 'warning' | 'danger' | 'info' | 'neutral';

// Tones mirror template `7Global Sidebar.jsx` Badge variants — boutique
// muted hues, NOT saturated. Each variant pairs a tinted bg with a deeper
// text colour for AA contrast on the cream canvas.
const toneStyles: Record<BadgeTone, string> = {
  brand:   'bg-brand-50 text-brand-700 border-brand-200/50',
  success: 'bg-success-50 text-success-700 border-success-100/60',
  warning: 'bg-warning-50 text-warning-700 border-warning-100/60',
  danger:  'bg-danger-50 text-danger-700 border-danger-100/60',
  info:    'bg-info-50 text-info-700 border-info-100/60',
  neutral: 'bg-canvas text-ink-muted border-subtle',
};

export function Badge({
  tone = 'neutral',
  className,
  children,
}: {
  tone?: BadgeTone;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-tiny font-medium border',
        toneStyles[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
