'use client';
import Link from 'next/link';
import { Button } from './button';
import { cn } from '@/lib/cn';

export interface EmptyStateProps {
  icon: any;
  title: string;
  description: string;
  action?: { href: string; label: string };
  secondary?: { href: string; label: string };
  children?: React.ReactNode;
  compact?: boolean;
  className?: string;
}

export function EmptyState({
  icon: Icon, title, description, action, secondary, children, compact, className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'rounded-2xl border border-dashed border-subtle bg-muted/30',
        compact ? 'p-6' : 'py-12 px-6',
        'flex flex-col items-center text-center',
        className,
      )}
    >
      <div
        className={cn(
          'rounded-full bg-brand-50 text-brand-600 mb-4',
          compact ? 'p-3' : 'p-4',
        )}
      >
        <Icon className={compact ? 'w-6 h-6' : 'w-8 h-8'} strokeWidth={1.5} />
      </div>
      <h3 className={cn(compact ? 'text-h3' : 'text-h2', 'font-serif text-[#2E2A24]')}>
        {title}
      </h3>
      <p className="text-body text-[#7A7266] mt-2 max-w-md">{description}</p>
      {children && <div className="mt-4 text-small text-[#7A7266] max-w-md">{children}</div>}
      {(action || secondary) && (
        <div className="mt-6 flex items-center gap-2 flex-wrap justify-center">
          {action && (
            <Button asChild>
              <Link href={action.href}>{action.label}</Link>
            </Button>
          )}
          {secondary && (
            <Button asChild variant="ghost">
              <Link href={secondary.href}>{secondary.label}</Link>
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
