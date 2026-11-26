import { screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Routes, Route } from 'react-router-dom';
import { LearningAnalyticsPage } from '../pages/LearningAnalyticsPage';
import { analyticsApi } from '../api/analyticsApi';
import { renderWithProviders } from '@/test/test-utils';
import {
  AnalyticsOverview,
  ConceptAnalyticsResponse,
  MasteryAnalyticsResponse,
  QuizPerformance,
  RevisionRecommendationItem,
  ScoreHistoryResponse,
} from '../types/analytics';

vi.mock('../api/analyticsApi', () => ({
  analyticsApi: {
    getOverview: vi.fn(),
    getQuizPerformance: vi.fn(),
    getScoreHistory: vi.fn(),
    getConceptAnalytics: vi.fn(),
    getMasteryOverview: vi.fn(),
    getActivityTimeline: vi.fn(),
    getRecommendations: vi.fn(),
    generateRecommendations: vi.fn(),
    updateRecommendationStatus: vi.fn(),
    getConceptRevisionResources: vi.fn(),
  },
}));

const mockOverview: AnalyticsOverview = {
  total_quiz_attempts: 12,
  completed_attempts: 10,
  evaluated_attempts: 10,
  average_quiz_score: 82.5,
  overall_correct_rate: 85.0,
  total_questions_answered: 40,
  total_correct_answers: 34,
  total_incorrect_answers: 6,
  total_unanswered: 2,
  concepts_assessed: 8,
  concepts_with_sufficient_bkt: 5,
  pending_recommendations_count: 2,
  date_filter: 'all',
};

const mockQuizPerformance: QuizPerformance = {
  total_attempts: 12,
  average_score: 82.5,
  highest_score: 95.0,
  recent_score: 90.0,
  total_answered: 40,
  total_correct: 34,
  total_incorrect: 6,
  total_unanswered: 2,
  correct_rate: 85.0,
};

const mockScoreHistory: ScoreHistoryResponse = {
  total_points: 3,
  points: [
    {
      attempt_id: 'att-1',
      attempt_date: '2026-11-01T10:00:00Z',
      score_percentage: 75.0,
      passed: true,
      total_questions: 5,
      correct_count: 4,
    },
    {
      attempt_id: 'att-2',
      attempt_date: '2026-11-03T10:00:00Z',
      score_percentage: 60.0,
      passed: false,
      total_questions: 5,
      correct_count: 3,
    },
    {
      attempt_id: 'att-3',
      attempt_date: '2026-11-05T10:00:00Z',
      score_percentage: 90.0,
      passed: true,
      total_questions: 5,
      correct_count: 5,
    },
  ],
};

const mockConceptAnalytics: ConceptAnalyticsResponse = {
  total_count: 2,
  concepts: [
    {
      concept_id: 'concept-1',
      concept_name: 'Cosine Similarity',
      category: 'metrics',
      questions_attempted: 6,
      questions_answered: 6,
      correct_answers: 5,
      incorrect_answers: 1,
      unanswered: 0,
      correct_rate: 83.3,
      evidence_sufficiency: 'sufficient',
      bkt_mastery_probability: 0.82,
      bkt_status: 'mastered',
    },
    {
      concept_id: 'concept-2',
      concept_name: 'BM25 Retrieval',
      category: 'retrieval',
      questions_attempted: 3,
      questions_answered: 3,
      correct_answers: 1,
      incorrect_answers: 2,
      unanswered: 0,
      correct_rate: 33.3,
      evidence_sufficiency: 'sufficient',
      bkt_mastery_probability: 0.35,
      bkt_status: 'unlearned',
    },
  ],
};

const mockMastery: MasteryAnalyticsResponse = {
  total_concepts_tracked: 2,
  model_readiness_status: 'evaluation_passed',
  active_model_version: 'v1.0.0-bkt',
  masteries: [
    {
      concept_id: 'concept-1',
      concept_name: 'Cosine Similarity',
      prior_mastery: 0.5,
      posterior_mastery: 0.82,
      predicted_next_mastery: 0.85,
      observation_count: 6,
      correct_count: 5,
      bkt_status: 'mastered',
      is_model_validated: true,
      last_updated_at: '2026-11-05T12:00:00Z',
    },
  ],
};

const mockRecommendations: RevisionRecommendationItem[] = [
  {
    id: 'rec-1',
    workspace_id: 'ws-test',
    user_id: 'usr-1',
    concept_id: 'concept-2',
    concept_name: 'BM25 Retrieval',
    recommendation_type: 'revise_concept',
    priority: 'high',
    explanation: 'Concept BM25 Retrieval has low mastery (35%). Please revise study notes.',
    evidence_summary: {
      observation_count: 3,
      evidence_sufficiency: 'sufficient',
      questions_answered: 3,
      correct_answers: 1,
      incorrect_answers: 2,
      correct_rate: 33.3,
      bkt_posterior_mastery: 0.35,
      bkt_model_qualified: true,
    },
    status: 'suggested',
    linked_resources: {
      revision_notes: [
        {
          resource_type: 'revision_note',
          resource_id: 'note-1',
          title: 'BM25 Formula & Inverted Index',
        },
      ],
      flashcards: [
        {
          resource_type: 'flashcard',
          resource_id: 'fc-1',
          title: 'What does k1 parameter tune in BM25?',
        },
      ],
    },
    created_at: '2026-11-05T14:00:00Z',
    updated_at: '2026-11-05T14:00:00Z',
  },
];

describe('LearningAnalyticsPage Component (C9.8 & C9.7)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(analyticsApi.getOverview).mockResolvedValue(mockOverview);
    vi.mocked(analyticsApi.getQuizPerformance).mockResolvedValue(mockQuizPerformance);
    vi.mocked(analyticsApi.getScoreHistory).mockResolvedValue(mockScoreHistory);
    vi.mocked(analyticsApi.getConceptAnalytics).mockResolvedValue(mockConceptAnalytics);
    vi.mocked(analyticsApi.getMasteryOverview).mockResolvedValue(mockMastery);
    vi.mocked(analyticsApi.getRecommendations).mockResolvedValue(mockRecommendations);
    vi.mocked(analyticsApi.getActivityTimeline).mockResolvedValue({ events: [], total_events: 0 });
    vi.mocked(analyticsApi.getConceptRevisionResources).mockResolvedValue({
      concept_id: 'concept-2',
      concept_name: 'BM25 Retrieval',
      revision_notes: [],
      flashcards: [],
      practice_questions: [],
      source_documents: [],
    });
  });

  const renderComponent = () =>
    renderWithProviders(
      <Routes>
        <Route path="/workspaces/:workspaceId/learning-analytics" element={<LearningAnalyticsPage />} />
      </Routes>,
      { initialEntries: ['/workspaces/ws-test/learning-analytics'] }
    );

  it('renders page header and overview KPI metrics accurately', async () => {
    renderComponent();

    expect(await screen.findByText('Learning Analytics & Revision Intelligence')).toBeInTheDocument();
    expect(screen.getByText('Phase 9 Learner Intelligence')).toBeInTheDocument();

    // Check KPI values
    await waitFor(() => {
      expect(screen.getByText('12')).toBeInTheDocument(); // total quiz attempts
      expect(screen.getByText('82.5%')).toBeInTheDocument(); // average quiz score
      expect(screen.getByText('85.0%')).toBeInTheDocument(); // accuracy rate
      expect(screen.getByText('8')).toBeInTheDocument(); // concepts assessed
    });
  });

  it('displays revision recommendations with priority badge and evidence', async () => {
    renderComponent();

    expect(await screen.findByText('BM25 Retrieval')).toBeInTheDocument();
    expect(screen.getByText(/high priority/i)).toBeInTheDocument();
    expect(screen.getByText('Revise Concept')).toBeInTheDocument();
    expect(screen.getByText(/Concept BM25 Retrieval has low mastery/i)).toBeInTheDocument();
    expect(screen.getByText('1 Note(s)')).toBeInTheDocument();
    expect(screen.getByText('1 Flashcard(s)')).toBeInTheDocument();
  });

  it('switches between tabs to display performance trends and concept attribution', async () => {
    renderComponent();

    // Click Quiz Performance tab
    const perfTab = await screen.findByRole('button', { name: /Quiz Performance & Trends/i });
    fireEvent.click(perfTab);

    expect(await screen.findByText('Score History Trend')).toBeInTheDocument();
    expect(screen.getByText('70% Pass Benchmark')).toBeInTheDocument();
    expect(screen.getByText('Performance Summary')).toBeInTheDocument();
    expect(screen.getByText('95.0%')).toBeInTheDocument(); // Highest score

    // Click Concept Mastery tab
    const conceptsTab = screen.getByRole('button', { name: /Concept Mastery & Attribution/i });
    fireEvent.click(conceptsTab);

    expect(await screen.findByText('Assessed Concept Attribution')).toBeInTheDocument();
    expect(screen.getByText('Cosine Similarity')).toBeInTheDocument();
    expect(screen.getByText('Validated Active Model')).toBeInTheDocument();
  });

  it('allows opening concept revision resources modal', async () => {
    renderComponent();

    const exploreBtn = await screen.findByRole('button', { name: /Explore Revision Materials/i });
    fireEvent.click(exploreBtn);

    expect(await screen.findByText('Revision Resources')).toBeInTheDocument();
    expect(analyticsApi.getConceptRevisionResources).toHaveBeenCalledWith('ws-test', 'concept-2');
  });
});
