import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cn } from '@/lib/cn';
import { Loader2 } from 'lucide-react';

type Variant = 'default' | 'primary' | 'outline' | 'ghost' | 'destructive';
type Size = 'sm' | 'md' | 'lg';

// Variants per template `5.1Kaori Platform Shell v2.jsx` lines 156-163.
// Gold buttons use DARK text (not white) — template intent is muted, boutique.
const variantStyles: Record<Variant, string> = {
  default:     'bg-brand-500 text-ink hover:bg-brand-600 active:scale-[0.98] shadow-soft-sm border border-transparent',
  primary:     'bg-brand-500 text-ink hover:bg-brand-600 active:scale-[0.98] shadow-soft-sm border border-transparent',
  outline:     'bg-white border border-subtle text-ink hover:bg-canvas active:scale-[0.98] shadow-sm',
  ghost:       'bg-transparent text-ink-muted hover:text-ink hover:bg-canvas active:scale-[0.98]',
  destructive: 'bg-danger-700 text-white hover:bg-danger-800 active:scale-[0.98] shadow-soft-sm border border-transparent',
};
const sizeStyles: Record<Size, string> = {
  sm: 'h-8 px-3 text-xs gap-1.5 rounded-sm-custom',
  md: 'h-10 px-4 text-sm gap-2 rounded-md-custom',
  lg: 'h-12 px-6 text-base gap-2.5 rounded-md-custom',
};

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  asChild?: boolean;
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'md', asChild = false, loading = false, disabled, children, ...rest }, ref) => {
    const Comp: any = asChild ? Slot : 'button';
    const content = (
      <>
        {loading && <Loader2 className="w-4 h-4 animate-spin" />}
        {children}
      </>
    );
    return (
      <Comp
        ref={ref}
        className={cn(
          'inline-flex items-center justify-center font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50 disabled:opacity-50 disabled:pointer-events-none',
          variantStyles[variant],
          sizeStyles[size],
          className,
        )}
        disabled={disabled || loading}
        {...rest}
      >
        {asChild ? children : content}
      </Comp>
    );
  },
);
Button.displayName = 'Button';
