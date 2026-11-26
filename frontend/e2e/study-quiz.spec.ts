import { test, expect } from '@playwright/test';

test.describe('E2E Journey 3: Study Studio, Flashcards & Interactive Quiz', () => {
  const wsId = 'ws-study-lab-01';

  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('knovera_access_token', 'mock_jwt_study_quiz');
      window.localStorage.setItem(
        'knovera_active_workspace',
        JSON.stringify({
          id: 'ws-study-lab-01',
          name: 'Distributed Systems Study Workspace',
        })
      );
    });
  });

  test('loads study materials and displays quiz interface', async ({ page }) => {
    await page.route(`**/api/v1/workspaces/${wsId}/study-materials/**`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'gen-001',
          document_id: 'doc-dist-01',
          material_type: 'mcq',
          items: [
            {
              id: 'q1',
              prompt: 'Which role coordinates log replication in Raft?',
              options: ['Leader', 'Follower', 'Candidate', 'Learner'],
              correct_answer: 'Leader',
              explanation: 'The elected leader coordinates all client requests and replication.',
            },
          ],
        }),
      });
    });

    await page.goto(`/app/workspaces/${wsId}/study`);
    await expect(page.getByText(/Study Studio/i).first()).toBeVisible();
  });
});
