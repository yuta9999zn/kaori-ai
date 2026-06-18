import * as React from 'react';
import { cn } from '@/lib/cn';

export const Select = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement>
>(({ className, children, ...rest }, ref) => (
  <select
    ref={ref}
    className={cn(
      'flex h-10 w-full rounded-xl border border-subtle bg-surface px-3 text-body text-[#2E2A24]',
      'focus:outline-none focus:ring-2 focus:ring-brand-300 disabled:opacity-50',
      'appearance-none bg-no-repeat bg-right pr-9',
      className,
    )}
    style={{
      backgroundImage:
        "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%23A89F90' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'/></svg>\")",
      backgroundPosition: 'right 0.75rem center',
    }}
    {...rest}
  >
    {children}
  </select>
));
Select.displayName = 'Select';
