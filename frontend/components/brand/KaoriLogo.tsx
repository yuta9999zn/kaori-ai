/**
 * KaoriLogo — lotus-inspired SVG mark.
 *
 * Source: D:\Kaori Document\frontend template\platform tenant\1KaoriLogin.jsx
 * (lines 145-150) and 7Global Sidebar.jsx (lines 227-230). Reused across
 * the brand panels (login / forgot / reset) and the platform sidebar.
 */

interface Props {
  /** Pixel size of the box; SVG scales to fit. Default 24. */
  size?:      number;
  /** Tailwind color class (e.g. "text-[#D4B88A]"). Default: brand-500 */
  className?: string;
  /** Whether to render the extra arc strokes (richer look — used on login). */
  detailed?:  boolean;
}

export function KaoriLogo({ size = 24, className = "text-[var(--color-brand-500)]", detailed = false }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      className={className}
      aria-hidden="true"
    >
      <path
        d="M12 22C12 22 10 16 4 16C4 16 8 13 12 14C16 13 20 16 20 16C14 16 12 22 12 22Z"
        fill="currentColor"
        fillOpacity="0.1"
      />
      <path
        d="M12 14C12 14 10 8 12 2C14 8 12 14 12 14Z"
        fill="currentColor"
        fillOpacity="0.1"
      />
      {detailed && (
        <>
          <path d="M4 16C4 16 1 12 5 8C6.5 11 9.5 13 12 14" strokeLinecap="round" />
          <path d="M20 16C20 16 23 12 19 8C17.5 11 14.5 13 12 14" strokeLinecap="round" />
        </>
      )}
    </svg>
  );
}

/**
 * Composite logomark + wordmark for the sidebar / login header.
 * Mirrors template's 8-square gold-bordered icon + serif "Kaori" + uppercase tagline.
 */
interface LockupProps {
  /** Subtitle under "Kaori" — usually "Platform" or "Workspace". */
  tagline?: string;
  /** When true, hide the wordmark (collapsed sidebar). */
  iconOnly?: boolean;
}

export function KaoriLockup({ tagline = "Platform", iconOnly = false }: LockupProps) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-8 w-8 items-center justify-center rounded-md-custom bg-white shadow-soft-sm border border-[var(--color-subtle)] shrink-0">
        <KaoriLogo size={20} />
      </div>
      {!iconOnly && (
        <div className="flex flex-col overflow-hidden">
          <span className="font-serif text-[17px] leading-none font-semibold text-[var(--color-ink)] tracking-wide">
            Kaori
          </span>
          {tagline && (
            <span className="text-[10px] uppercase tracking-wider font-medium text-[var(--color-ink-muted)] mt-0.5">
              {tagline}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
