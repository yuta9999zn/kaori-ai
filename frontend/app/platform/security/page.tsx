import { redirect } from 'next/navigation';

/**
 * /platform/security has no landing of its own — bounce to the MFA tab
 * (first child in the security tab bar).
 */
export default function PlatformSecurityIndexPage() {
  redirect('/platform/security/mfa');
}
