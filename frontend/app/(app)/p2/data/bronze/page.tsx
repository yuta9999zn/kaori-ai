// F-NEW3 v1 BE PR #146 wired GET /api/v1/data/bronze/files (paginated)
// + GET /api/v1/data/bronze/files/{id}/sample. This route mounts the
// drill-down list with sample preview modal; the template-mount lived
// here previously without any BE.
import BronzeDrillDownPage from '@/components/p2/templates/fnew3v1-bronze';

export default function Page() {
  return <BronzeDrillDownPage />;
}
