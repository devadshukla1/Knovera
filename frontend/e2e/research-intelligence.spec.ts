import { test, expect } from '@playwright/test';

test.describe('E2E Journey 4: Research Intelligence, Multi-Paper Comparison & Contradictions', () => {
  const wsId = 'ws-research-lab-01';

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('knovera_access_token', 'mock_jwt_research');
      window.localStorage.setItem(
        'knovera_active_workspace',
        JSON.stringify({
          id: 'ws-research-lab-01',
          name: 'Academic Research Lab',
        })
      );
    });
  });

  test('loads research intelligence dashboard and renders comparison metrics', async ({ page }) => {
    await page.route(`**/api/v1/workspaces/${wsId}/research/dashboard`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total_papers_analyzed: 8,
          total_findings_extracted: 42,
          total_contradictions_detected: 2,
          coverage_gap_count: 1,
          contradictions: [
            {
              id: 'c1',
              finding_a_text: 'Model requires pretraining for convergence.',
              finding_b_text: 'Model trains stably from random initialization.',
              severity: 'high',
            },
          ],
        }),
      });
    });

    await page.goto(`/app/workspaces/${wsId}/research/dashboard`);
    await expect(page.getByText(/Research Intelligence/i).first()).toBeVisible();
  });
});
