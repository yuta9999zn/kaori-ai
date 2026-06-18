// F-039 BE PR #126 + #140 wired the per-tenant risk register CRUD.
// /p2/risks lives at the bare path (matching the navigation entry); the
// older /p2/risks/hub route mounted the static template with no BE wire.
import RisksHubPage from '@/components/p2/templates/f039-risks-hub';

export default function Page() {
  return <RisksHubPage />;
}
