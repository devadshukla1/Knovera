import { describe, it, expect, vi, beforeEach } from 'vitest';
import { studyApi } from '../api/studyApi';
import * as apiModule from '@/services/api';

vi.mock('@/services/api', async () => {
  const actual = await vi.importActual<typeof apiModule>('@/services/api');
  return {
    ...actual,
    apiFetch: vi.fn(),
  };
});

describe('studyApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('generates True/False questions with target ratio', async () => {
    const mockTfQuestions = [
      {
        id: 'tf-1',
        workspace_id: 'ws-100',
        statement: 'Support Vector Machines find an optimal hyperplane.',
        correct_answer: true,
        explanation: 'SVMs maximize geometric margin.',
        difficulty: 'medium',
        source_references: [],
        created_at: '2026-11-08T00:00:00Z',
      },
    ];

    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce(mockTfQuestions);

    const result = await studyApi.generateTrueFalse('ws-100', {
      count: 2,
      target_true_ratio: 0.5,
    });

    expect(apiModule.apiFetch).toHaveBeenCalledWith(
      'workspaces/ws-100/study-materials/true-false/generate',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      }),
      30000
    );
    expect(result).toEqual(mockTfQuestions);
  });

  it('lists flashcards for a workspace deck', async () => {
    const mockFlashcards = {
      items: [
        {
          id: 'fc-1',
          workspace_id: 'ws-100',
          front: 'What is K-Means?',
          back: 'An unsupervised clustering algorithm.',
          card_type: 'definition',
          difficulty: 'easy',
          source_references: [],
          created_at: '2026-11-08T00:00:00Z',
          updated_at: '2026-11-08T00:00:00Z',
        },
      ],
      total: 1,
    };

    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce(mockFlashcards);

    const result = await studyApi.listFlashcards('ws-100', { limit: 10 });
    expect(apiModule.apiFetch).toHaveBeenCalledWith(
      'workspaces/ws-100/study-materials/flashcards?limit=10'
    );
    expect(result.items).toHaveLength(1);
    expect(result.items[0].card_type).toBe('definition');
  });

  it('creates an interactive quiz attempt', async () => {
    const mockAttempt = {
      id: 'attempt-1',
      workspace_id: 'ws-100',
      user_id: 'user-1',
      title: 'Practice ML Exam',
      status: 'in_progress',
      total_questions: 2,
      answered_count: 0,
      started_at: '2026-11-08T00:00:00Z',
      questions: [
        {
          id: 'q-1',
          question_type: 'mcq',
          question_text: 'What does SVM maximize?',
          difficulty: 'medium',
          options: [
            { id: 'opt-1', option_id: 'A', option_text: 'Margin' },
            { id: 'opt-2', option_id: 'B', option_text: 'Loss' },
          ],
        },
      ],
      saved_answers: {},
    };

    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce(mockAttempt);

    const result = await studyApi.createQuizAttempt('ws-100', {
      title: 'Practice ML Exam',
      count: 2,
      question_types: ['mcq'],
    });

    expect(apiModule.apiFetch).toHaveBeenCalledWith(
      'workspaces/ws-100/quiz-attempts',
      expect.objectContaining({
        method: 'POST',
      })
    );
    expect(result.id).toBe('attempt-1');
    expect(result.questions).toHaveLength(1);
  });

  it('submits quiz attempt and returns evaluation results', async () => {
    const mockResults = {
      attempt_id: 'attempt-1',
      title: 'Practice ML Exam',
      status: 'evaluated',
      total_questions: 1,
      correct_count: 1,
      incorrect_count: 0,
      unanswered_count: 0,
      score_percentage: 100.0,
      started_at: '2026-11-08T00:00:00Z',
      submitted_at: '2026-11-08T00:05:00Z',
      results: [
        {
          question_id: 'q-1',
          question_type: 'mcq',
          question_text: 'What does SVM maximize?',
          difficulty: 'medium',
          learner_answer: 'A',
          correct_answer: 'A',
          is_correct: true,
          explanation: 'SVMs find maximum-margin hyperplanes.',
          source_references: [],
        },
      ],
    };

    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce(mockResults);

    const result = await studyApi.submitQuizAttempt('ws-100', 'attempt-1', [
      { question_id: 'q-1', question_type: 'mcq', selected_answer: 'A' },
    ]);

    expect(apiModule.apiFetch).toHaveBeenCalledWith(
      'workspaces/ws-100/quiz-attempts/attempt-1/submit',
      expect.objectContaining({
        method: 'POST',
      })
    );
    expect(result.score_percentage).toBe(100.0);
    expect(result.results[0].is_correct).toBe(true);
  });

  it('retrieves verified question explanation and sources', async () => {
    const mockExpl = {
      attempt_id: 'attempt-1',
      question_id: 'q-1',
      question_type: 'mcq',
      question_text: 'What does SVM maximize?',
      explanation: 'SVMs find maximum-margin hyperplanes.',
      correct_answer: 'A',
      learner_answer: 'A',
      is_correct: true,
    };
    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce(mockExpl);

    const explRes = await studyApi.getQuestionExplanation('ws-100', 'attempt-1', 'q-1');
    expect(apiModule.apiFetch).toHaveBeenCalledWith(
      'workspaces/ws-100/quiz-attempts/attempt-1/questions/q-1/explanation'
    );
    expect(explRes.is_correct).toBe(true);

    const mockSources = {
      attempt_id: 'attempt-1',
      question_id: 'q-1',
      question_type: 'mcq',
      source_references: [
        {
          document_id: 'doc-1',
          document_title: 'ml.pdf',
          chunk_id: 'chunk-1',
          chunk_index: 0,
          page_number: 1,
          excerpt: 'Support Vector Machines find an optimal hyperplane...',
        },
      ],
    };
    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce(mockSources);

    const sourcesRes = await studyApi.getQuestionSources('ws-100', 'attempt-1', 'q-1');
    expect(apiModule.apiFetch).toHaveBeenCalledWith(
      'workspaces/ws-100/quiz-attempts/attempt-1/questions/q-1/sources'
    );
    expect(sourcesRes.source_references).toHaveLength(1);
    expect(sourcesRes.source_references[0].page_number).toBe(1);
  });

  it('queries quiz history, analytics summary, trends, and retakes', async () => {
    // 1. History listing
    const mockHistory = {
      items: [
        {
          id: 'attempt-1',
          workspace_id: 'ws-100',
          title: 'Calculus Quiz',
          status: 'evaluated',
          total_questions: 5,
          score_percentage: 80.0,
          started_at: '2026-11-08T00:00:00Z',
        },
      ],
      total: 1,
    };
    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce(mockHistory);

    const historyRes = await studyApi.listQuizHistory('ws-100', {
      status: 'evaluated',
      search: 'Calculus',
      sort_by: 'score_percentage',
    });
    expect(apiModule.apiFetch).toHaveBeenCalledWith(
      'workspaces/ws-100/quiz-history?status=evaluated&search=Calculus&sort_by=score_percentage'
    );
    expect(historyRes.total).toBe(1);

    // 2. Summary
    const mockSummary = {
      total_attempts: 1,
      completed_attempts: 1,
      in_progress_attempts: 0,
      average_score: 80.0,
      overall_correct_rate: 80.0,
      total_questions_answered: 5,
      total_correct_answers: 4,
    };
    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce(mockSummary);

    const summaryRes = await studyApi.getQuizHistorySummary('ws-100');
    expect(apiModule.apiFetch).toHaveBeenCalledWith('workspaces/ws-100/quiz-history/summary');
    expect(summaryRes.average_score).toBe(80.0);

    // 3. Trends
    const mockTrends = {
      trends: [
        {
          attempt_id: 'attempt-1',
          title: 'Calculus Quiz',
          score_percentage: 80.0,
          total_questions: 5,
          correct_count: 4,
          completed_at: '2026-11-08T00:10:00Z',
        },
      ],
    };
    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce(mockTrends);

    const trendsRes = await studyApi.getQuizHistoryTrends('ws-100');
    expect(apiModule.apiFetch).toHaveBeenCalledWith('workspaces/ws-100/quiz-history/trends');
    expect(trendsRes.trends).toHaveLength(1);

    // 4. Retake
    const mockRetake = {
      id: 'attempt-2',
      workspace_id: 'ws-100',
      user_id: 'user-1',
      title: 'Retake: Calculus Quiz',
      status: 'in_progress',
      total_questions: 5,
      answered_count: 0,
      started_at: '2026-11-08T01:00:00Z',
      questions: [],
      saved_answers: {},
    };
    vi.mocked(apiModule.apiFetch).mockResolvedValueOnce(mockRetake);

    const retakeRes = await studyApi.retakeQuizAttempt('ws-100', 'attempt-1');
    expect(apiModule.apiFetch).toHaveBeenCalledWith(
      'workspaces/ws-100/quiz-attempts/attempt-1/retake',
      expect.objectContaining({ method: 'POST' })
    );
    expect(retakeRes.title).toBe('Retake: Calculus Quiz');
  });
});
