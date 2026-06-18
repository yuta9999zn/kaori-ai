import * as React from 'react';
import { cn } from '@/lib/cn';
import { Card, CardContent } from '@/components/ui/card';

export type KpiTone = 'neutral' | 'brand' | 'success' | 'warning' | 'danger' | 'info';

const toneColor: Record<KpiTone, string> = {
  neutral: 'text-[#2E2A24]',
  brand:   'text-brand-700',
  success: 'text-success-700',
  warning: 'text-warning-700',
  danger:  'text-danger-700',
  info:    'text-info-700',
};

export function KpiCard({
  label, value, delta, hint, trendPct, icon, tone = 'neutral', className,
}: {
  label: string;
  value: React.ReactNode;
  delta?: React.ReactNode;
  hint?: React.ReactNode;
  trendPct?: number;
  icon?: React.ReactNode;
  tone?: KpiTone;
  className?: string;
}) {
  const trendLabel = typeof trendPct === 'number'
    ? (trendPct > 0 ? '+' : '') + String(trendPct) + '%'
    : undefined;
  const sub = delta ?? hint ?? trendLabel;
  return (
    <Card className={className}>
      <CardContent className="pt-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-small text-[#7A7266]">{label}</div>
            <div className={cn('text-h1 font-serif font-semibold mt-2 tabular-nums', toneColor[tone])}>
              {value}
            </div>
            {sub && <div className="text-tiny text-[#7A7266] mt-1">{sub}</div>}
          </div>
          {icon && (
            <div className="rounded-xl bg-muted/70 p-2 text-[#7A7266]">
              {icon}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export const KPICard = KpiCard;
