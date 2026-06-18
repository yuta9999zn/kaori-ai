/**
 * P1 Platform Manager — shared design foundation.
 *
 * Re-export of `components/p2/foundation.tsx`. Both portals share the SAME
 * platform tenant cream/gold/Playfair token set — p2/foundation explicitly
 * cites template `10Component foundation.tsx` (a P1 source template) as
 * its canonical source. Keeping a single physical file avoids drift.
 *
 * If the P1 design system ever diverges (e.g. stricter admin chrome,
 * different state palette), replace this re-export with a copy and edit.
 *
 * Strict TS by re-export: consumers see whatever types p2/foundation
 * declares. The handful of `any` slots inside p2/foundation are scoped
 * to internal helpers — public API surfaces are typed.
 */
export {
  cn,
  formatVND,
  formatVNDLong,
  PRICING,
  parseProblemDetails,
  newIdempotencyKey,
  api,
  GlobalStyles,
  KaoriLogo,
  KaoriLockup,
  Button,
  Label,
  Input,
  PasswordField,
  Checkbox,
  Badge,
  ErrorBanner,
  SuccessBanner,
  QuotaBar,
} from '@/components/p2/foundation';

export type { ProblemDetails } from '@/components/p2/foundation';
