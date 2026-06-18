import * as React from 'react';
import { cn } from '@/lib/cn';

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...rest }, ref) => (
    <input
      ref={ref}
      className={cn(
        'flex h-10 w-full rounded-xl border border-subtle bg-surface px-3 text-body text-[#2E2A24] placeholder:text-[#A89F90] focus:outline-none focus:ring-2 focus:ring-brand-300 disabled:opacity-50',
        className,
      )}
      {...rest}
    />
  ),
);
Input.displayName = 'Input';

export const Label = React.forwardRef<
  HTMLLabelElement,
  React.LabelHTMLAttributes<HTMLLabelElement>
>(({ className, ...rest }, ref) => (
  <label
    ref={ref}
    className={cn('text-small font-medium text-[#2E2A24]', className)}
    {...rest}
  />
));
Label.displayName = 'Label';
