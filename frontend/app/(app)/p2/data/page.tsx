// F-NEW3 BE PR #142 wired GET /api/v1/data/explorer (single hub
// endpoint over all 3 Medallion layers). /p2/data lives at the bare
// path (matching the navigation entry); the older /p2/data/explorer
// route mounted the static template with no BE wire.
import DataExplorerPage from '@/components/p2/templates/fnew3-data-explorer';

export default function Page() {
  return <DataExplorerPage />;
}
