// /p2/decisions root — surface the audit log immediately so anh
// doesn't 404 when navigating to the bare path. The cursor list
// template is what /p2/decisions/log mounts; mounting it here too is
// the simplest fix (no redirect bounce) and matches the BE shape:
// `GET /api/v1/decisions` returns the same envelope either way.
import Template from '@/components/p2/templates/31-decision-log';

export default function Page() {
  return <Template />;
}
