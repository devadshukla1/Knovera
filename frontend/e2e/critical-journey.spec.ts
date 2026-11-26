import { test, expect } from '@playwright/test';

test.describe('Knovera Critical Journey E2E Test Suite', () => {
  test.beforeEach(async ({ page }) => {
    // Inject mock user auth token and workspace context into localStorage
    await page.addInitScript(() => {
      window.localStorage.setItem('knovera_access_token', 'mock_e2e_jwt_token_for_playwright');
      window.localStorage.setItem(
        'knovera_active_workspace',
        JSON.stringify({
          id: 'ws-e2e-quantum-lab',
          name: 'Quantum Optics & AI Lab',
          description: 'High-energy physics and neural computing workspace',
        })
      );
    });
  });

  test('Step 1: Landing Page & Brand Identity Verification', async ({ page }) => {
    // Intercept backend health check if running standalone
    await page.route('**/api/v1/health', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'healthy',
          app: 'Knovera API',
          version: '1.0.0',
          database: 'connected',
          vector_db: 'ready',
        }),
      });
    });

    await page.goto('/');
    await expect(page).toHaveTitle(/Knovera/i);

    // Verify brand header and tagline
    const brandElement = page.getByText('KNOVERA', { exact: false });
    await expect(brandElement.first()).toBeVisible();
    await expect(page.getByText(/Turn Information into Intelligence/i).first()).toBeVisible();
  });

  test('Step 2: Workspace Navigation & Dashboard Access', async ({ page }) => {
    await page.route('**/api/v1/workspaces', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'ws-e2e-quantum-lab',
            name: 'Quantum Optics & AI Lab',
            description: 'High-energy physics and neural computing workspace',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            document_count: 5,
          },
        ]),
      });
    });

    await page.goto('/app/workspaces');
    await expect(page.getByText('Quantum Optics & AI Lab').first()).toBeVisible();

    // Verify navigation sidebar has Knovera modules
    await expect(page.getByText('All Workspaces').first()).toBeVisible();
    await expect(page.getByText('Research Intelligence').first()).toBeVisible();
  });

  test('Step 3: Document Management Flow', async ({ page }) => {
    await page.route('**/api/v1/workspaces/ws-e2e-quantum-lab/documents', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([
            {
              id: 'doc-quantum-001',
              title: 'Attention Is All You Need.pdf',
              original_filename: 'Attention_Is_All_You_Need.pdf',
              mime_type: 'application/pdf',
              file_size_bytes: 1048576,
              status: 'ready',
              created_at: new Date().toISOString(),
              page_count: 15,
            },
          ]),
        });
      }
    });

    await page.goto('/app/workspaces/ws-e2e-quantum-lab/documents');
    await expect(page.getByText('Attention Is All You Need.pdf').first()).toBeVisible();
  });

  test('Step 4: Research Chat & Source-Grounded Citations', async ({ page }) => {
    // Route chat queries and citation lookups
    await page.route('**/api/v1/workspaces/ws-e2e-quantum-lab/conversations/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'conv-001',
          title: 'Transformer Architecture Query',
          messages: [
            {
              id: 'msg-001',
              role: 'user',
              content: 'What is Multi-Head Attention?',
            },
            {
              id: 'msg-002',
              role: 'assistant',
              content:
                'Multi-head attention allows the model to jointly attend to information from different representation subspaces at different positions [doc-quantum-001:p4].',
              citations: [
                {
                  id: 'cite-001',
                  document_id: 'doc-quantum-001',
                  chunk_id: 'chunk-p4-01',
                  page_number: 4,
                  snippet: 'Multi-head attention allows the model to jointly attend...',
                  document_title: 'Attention Is All You Need.pdf',
                },
              ],
            },
          ],
        }),
      });
    });

    await page.goto('/app/workspaces/ws-e2e-quantum-lab/chat');
    // Verify chat interface loaded
    await expect(page.getByPlaceholder(/Ask a research question/i).first()).toBeVisible();
  });

  test('Step 5: Interactive Study Studio & Quiz Journey', async ({ page }) => {
    await page.route('**/api/v1/workspaces/ws-e2e-quantum-lab/quizzes/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'quiz-001',
          title: 'Quantum & Attention Mechanisms Quiz',
          questions: [
            {
              id: 'q-001',
              question_type: 'mcq',
              prompt: 'Which mechanism replaces recurrence in Transformer architectures?',
              options: ['Self-Attention', 'Convolution', 'Pooling', 'Dropout'],
            },
          ],
        }),
      });
    });

    await page.goto('/app/workspaces/ws-e2e-quantum-lab/study');
    await expect(page.getByText(/Study Studio/i).first()).toBeVisible();
  });

  test('Step 6: Research Intelligence Dashboard & Multi-Paper Synthesis', async ({ page }) => {
    await page.route('**/api/v1/workspaces/ws-e2e-quantum-lab/research/dashboard', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total_papers_analyzed: 12,
          total_findings_extracted: 84,
          total_contradictions_detected: 3,
          coverage_gap_count: 2,
          contradictions: [
            {
              id: 'contra-001',
              finding_a_text: 'Model achieves 94.5% accuracy without pretraining.',
              finding_b_text: 'Pretraining is strictly necessary to exceed 80% accuracy.',
              severity: 'high',
            },
          ],
        }),
      });
    });

    await page.goto('/app/workspaces/ws-e2e-quantum-lab/research/dashboard');
    await expect(page.getByText(/Research Intelligence/i).first()).toBeVisible();
  });
});
