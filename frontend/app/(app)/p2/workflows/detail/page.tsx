// Legacy alias — anh's earlier templates used /detail. The canonical
// route is /p2/workflows/[id]. This page redirects to the hub when hit
// directly so we don't break old bookmarks.
import { redirect } from 'next/navigation';

export default function Page() {
  redirect('/p2/workflows');
}
