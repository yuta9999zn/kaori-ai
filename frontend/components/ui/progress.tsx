import { cn } from '@/lib/cn';

export function Progress({
  value,
  max = 100,
  tone = 'brand',
  className,
}: {
  value: number;
  max?: number;
  tone?: 'brand' | 'success' | 'warning' | 'danger';
  className?: string;
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const color = {
    brand:   'bg-brand-500',
    success: 'bg-success-500',
    warning: 'bg-warning-500',
    danger:  'bg-danger-500',
  }[tone];
  return (
    <div className={cn('w-full h-2 rounded-full bg-muted overflow-hidden', className)}>
      <div
        className={cn('h-full transition-all duration-500 rounded-full', color)}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
