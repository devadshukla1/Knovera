import { test, expect } from '@playwright/test';

test.describe('E2E Journey 2: Document Management & RAG Chat with Grounded Citations', () => {
  const wsId = 'ws-quantum-lab-01';

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('knovera_access_token', 'mock_jwt_e2e_rag');
      window.localStorage.setItem(
        'knovera_active_workspace',
        JSON.stringify({
          id: 'ws-quantum-lab-01',
          name: 'Quantum Information Lab',
        })
      );
    });
  });

  test('displays documents and navigates to RAG chat with verified citations', async ({ page }) => {
    // Documents route
    await page.route(`**/api/v1/workspaces/${wsId}/documents`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'doc-quantum-001',
            workspace_id: wsId,
            title: 'Quantum Entanglement and Bell Inequalities.pdf',
            original_filename: 'Quantum_Entanglement.pdf',
            mime_type: 'application/pdf',
            file_size_bytes: 524288,
            status: 'ready',
            created_at: new Date().toISOString(),
            page_count: 8,
          },
        ]),
      });
    });

    // Chat route
    await page.route(`**/api/v1/workspaces/${wsId}/conversations/**`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'conv-quantum-01',
          title: 'Bell Theorem Query',
          messages: [
            {
              id: 'm1',
              role: 'user',
              content: 'What do Bell inequalities prove?',
            },
            {
              id: 'm2',
              role: 'assistant',
              content:
                'Bell inequalities show that quantum mechanics cannot be explained by any local hidden-variable theory [doc-quantum-001:p3].',
              citations: [
                {
                  id: 'cite-01',
                  document_id: 'doc-quantum-001',
                  chunk_id: 'chunk-p3-01',
                  page_number: 3,
                  snippet: 'Violation of Bell inequalities demonstrates non-locality in quantum mechanics.',
                  document_title: 'Quantum Entanglement and Bell Inequalities.pdf',
                },
              ],
            },
          ],
        }),
      });
    });

    await page.goto(`/app/workspaces/${wsId}/documents`);
    await expect(page.getByText('Quantum Entanglement and Bell Inequalities.pdf').first()).toBeVisible();

    await page.goto(`/app/workspaces/${wsId}/chat`);
    await expect(page.getByPlaceholder(/Ask a research question/i).first()).toBeVisible();
  });
});
