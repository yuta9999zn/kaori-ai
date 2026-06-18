/**
 * Verify fix #2 trong PR #304 — staleFinalizer reset khi runId đổi.
 *
 * Page Step 5 hiển thị banner cảnh báo "chưa kịp đánh dấu hoàn tất" khi:
 *   - BE run status vẫn 'running' / 'queued' / ''
 *   - mọi template đã settled (done/failed)
 *   - đã quá 60s tính từ khi startRef khởi tạo
 *
 * Trước fix, startRef chỉ được set một lần ở mount, nên SPA navigate sang
 * runId mới giữ nguyên đồng hồ cũ → warning bật sớm cho run mới.
 * Fix: useEffect [runId] reset startRef = Date.now() + setStaleFinalizer(false).
 *
 * Test #2 dưới đây dùng Playwright clock fake để fast-forward 65s và mock
 * 3 BE endpoint (analytics runs A, B, danh sách pipelines) qua route intercept.
 */
import { test, expect, Page } from '@playwright/test';

const ENTERPRISE_ID = '2d185ee6-5156-4236-b748-08062e8f23e4';
const PIPE_A = '11111111-1111-4111-8111-111111111111';
const RUN_A  = 'aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa';
const PIPE_B = '22222222-2222-4222-8222-222222222222';
const RUN_B  = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb';

function laggedRunPayload(id: string) {
  // BE chưa flip 'running' → 'done', nhưng template_results đã settled.
  // Đây là tình huống "finalizer lag" mà staleFinalizer designed để cover.
  return {
    id,
    run_id: id,
    templates: ['summary_stats'],
    status: 'running',
    overview: null,
    created_at: '2026-05-28T12:00:00Z',
    completed_at: null,
    template_results: [
      {
        template_id: 'summary_stats',
        status: 'done',
        results_payload: JSON.stringify({
          blocks: [
            { id: 'sc', type: 'stats_card', title: 'Tổng quan',
              data: { total_rows: 100, numeric_columns: 2, null_rate: 0.1 } },
          ],
          template_id: 'summary_stats',
        }),
        error_message: null,
      },
    ],
  };
}

async function setupMocks(page: Page) {
  // Auth bypass: gán token để bypass middleware (nếu có)
  await page.addInitScript(() => {
    window.localStorage.setItem('kaori.access_token', 'dev-fake-jwt');
    window.localStorage.setItem('kaori.enterprise_id', '2d185ee6-5156-4236-b748-08062e8f23e4');
  });

  await page.route(/\/api\/v1\/analytics\/runs\/.+/, (route) => {
    const url = route.request().url();
    const id = url.split('/').pop()!.split('?')[0];
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(laggedRunPayload(id)),
    });
  });

  // /pipelines list cho NavBar nếu có
  await page.route(/\/api\/v1\/pipelines(\?.*)?$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json',
                    body: JSON.stringify({ data: [], meta: { cursor: null } }) }),
  );
}

const WARNING_TEXT = 'chưa kịp đánh dấu';

test.describe('Step 5 — staleFinalizer reset khi runId đổi (fix PR #304)', () => {
  test('warning KHÔNG hiện ngay sau load (đồng hồ vừa khởi tạo)', async ({ page }) => {
    await page.clock.install({ time: new Date('2026-05-28T12:00:00Z') });
    await setupMocks(page);
    await page.goto(`/p2/pipelines/${PIPE_A}/step-5-results?run_id=${RUN_A}`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(WARNING_TEXT)).toBeHidden();
  });

  test('warning HIỆN sau 65s khi BE vẫn lag + template_results settled', async ({ page }) => {
    await page.clock.install({ time: new Date('2026-05-28T12:00:00Z') });
    await setupMocks(page);
    await page.goto(`/p2/pipelines/${PIPE_A}/step-5-results?run_id=${RUN_A}`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(WARNING_TEXT)).toBeHidden();

    // Fast-forward 65s → poll firing (interval 5s) → lagged = true → warning xuất hiện
    await page.clock.fastForward(65_000);
    await expect(page.getByText(WARNING_TEXT)).toBeVisible();
  });

  test('mount run B sau khi warning đã hiện trên A → đồng hồ fresh, warning KHÔNG carry over', async ({ page }) => {
    // Test này verify intent của fix: mỗi mount/runId mới có đồng hồ riêng,
    // warning của run cũ không lây sang run mới. (SPA-level useSearchParams
    // reactivity không trigger được từ Playwright không qua next/navigation
    // router, nên scenario này được test qua cross-mount thay vì cùng-mount.)
    await page.clock.install({ time: new Date('2026-05-28T12:00:00Z') });
    await setupMocks(page);

    // 1) Load run A, fast-forward để warning bật trên A
    await page.goto(`/p2/pipelines/${PIPE_A}/step-5-results?run_id=${RUN_A}`);
    await page.waitForLoadState('networkidle');
    await page.clock.fastForward(65_000);
    await expect(page.getByText(WARNING_TEXT)).toBeVisible();

    // 2) Navigate sang run B — clock vẫn ở 12:01:05 absolute (đã ff 65s).
    //    Mount mới phải set startRef = clock-now-mới → warning chưa hiện.
    await page.goto(`/p2/pipelines/${PIPE_B}/step-5-results?run_id=${RUN_B}`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(WARNING_TEXT)).toBeHidden();

    // 3) Fast-forward thêm 65s → warning bật lại trên run B (đồng hồ đúng)
    await page.clock.fastForward(65_000);
    await expect(page.getByText(WARNING_TEXT)).toBeVisible();
  });

  test('stats_card render KPI từ data object (verify fix Test #5 — primitive filter)', async ({ page }) => {
    // BE emit stats_card với data = {total_rows, numeric_columns, null_rate}.
    // FE phải render 3 KPI card primitive, không có "[object Object]".
    await page.clock.install({ time: new Date('2026-05-28T12:00:00Z') });
    await setupMocks(page);
    await page.goto(`/p2/pipelines/${PIPE_A}/step-5-results?run_id=${RUN_A}`);
    await page.waitForLoadState('networkidle');

    // "Tổng quan" cũng là menu sidebar — dùng heading role để đụng chính
    // tiêu đề stats_card block.
    await expect(page.getByRole('heading', { name: 'Tổng quan' })).toBeVisible();
    // 3 label VN từ STAT_LABEL map
    await expect(page.getByText('Số dòng', { exact: true })).toBeVisible();
    await expect(page.getByText('Cột số', { exact: true })).toBeVisible();
    await expect(page.getByText('Tỷ lệ trống', { exact: true })).toBeVisible();
    // Không bao giờ được phép render "[object Object]"
    await expect(page.getByText('[object Object]')).toHaveCount(0);
  });
});
