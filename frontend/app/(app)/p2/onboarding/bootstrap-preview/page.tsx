// /p2/onboarding/bootstrap-preview — P2-32 Bootstrap Preview (dry-run)
// Phase 2.8 NEW per ADR-0026 + PHASE_2_8_FE_IMPL_SPEC.md §P2-32.
// Permission: MANAGER+ only.
//
// The template reads ?industry_id via useSearchParams(); Next 16 requires a
// Suspense boundary around any client component that does so on a statically
// prerendered route, otherwise the build bails out (missing-suspense-with-csr-bailout).
import { Suspense } from 'react';
import BootstrapPreviewPage from '@/components/p2/templates/76-bootstrap-preview';

export default function Page() {
  return (
    <Suspense fallback={null}>
      <BootstrapPreviewPage />
    </Suspense>
  );
}
