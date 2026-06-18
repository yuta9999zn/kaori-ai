// F-039 export — client-side CSV from the list endpoint (BE has no
// /risks/export route; PDF + email are deferred to Phase 2).
import RisksExportPage from '@/components/p2/templates/f039-risks-export';

export default function Page() {
  return <RisksExportPage />;
}
