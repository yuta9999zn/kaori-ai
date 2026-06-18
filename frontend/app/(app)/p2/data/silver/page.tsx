// F-NEW3 v1 BE PR #148 wired GET /api/v1/data/silver/datasets (paginated)
// + GET /api/v1/data/silver/datasets/{id}/sample. This route mounts the
// drill-down list with sample preview modal; the template-mount lived
// here previously without any BE.
import SilverDrillDownPage from '@/components/p2/templates/fnew3v1-silver';

export default function Page() {
  return <SilverDrillDownPage />;
}
