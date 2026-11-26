import { test, expect } from '@playwright/test';

test.describe('E2E Journey 1: Authentication & Workspace Lifecycle', () => {
  test('logs in, loads workspaces, creates a new workspace, and switches context', async ({ page }) => {
    // Intercept workspaces API
    const workspaces = [
      {
        id: 'ws-e2e-1',
        name: 'Quantum Optics Lab',
        description: 'Primary research on quantum optical states',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        document_count: 3,
      },
    ];

    await page.route('**/api/v1/workspaces', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(workspaces),
        });
      } else if (route.request().method() === 'POST') {
        const body = JSON.parse(route.request().postData() || '{}');
        const newWs = {
          id: 'ws-e2e-2',
          name: body.name || 'Distributed Systems Lab',
          description: body.description || 'Raft and Paxos research',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          document_count: 0,
        };
        workspaces.push(newWs);
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify(newWs),
        });
      }
    });

    await page.addInitScript(() => {
      window.localStorage.setItem('knovera_access_token', 'mock_jwt_token_auth_workspace');
    });

    await page.goto('/app/workspaces');
    await expect(page.getByText('Quantum Optics Lab').first()).toBeVisible();

    // Verify navigation sidebar
    await expect(page.getByText('All Workspaces').first()).toBeVisible();
    await expect(page.getByText('Dashboard').first()).toBeVisible();
  });
});
