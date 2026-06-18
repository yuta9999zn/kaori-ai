import * as React from 'react';
import { cn } from '@/lib/cn';

// Per template `5.1Kaori Platform Shell v2.jsx` — cards use rounded-md-custom
// (12px) + soft-shadow tier instead of the heavier rounded-2xl/shadow-xs combo.
export function Card({ className, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('bg-surface rounded-md-custom border border-subtle shadow-soft-sm transition-shadow hover:shadow-soft-md', className)}
      {...rest}
    />
  );
}

export function CardHeader({ className, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('px-6 pt-6 pb-3', className)} {...rest} />;
}

export function CardTitle({ className, ...rest }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn('text-h2 font-serif text-ink', className)}
      {...rest}
    />
  );
}

export function CardDescription({ className, ...rest }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn('text-small text-ink-muted mt-1', className)} {...rest} />;
}

export function CardContent({ className, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('px-6 pb-6', className)} {...rest} />;
}

export function CardFooter({ className, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('px-6 py-4 border-t border-subtle bg-canvas/60 rounded-b-md-custom', className)}
      {...rest}
    />
  );
}
