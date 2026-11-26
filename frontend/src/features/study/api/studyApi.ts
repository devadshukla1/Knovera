/**
 * Knovera Study Material & Interactive Quiz API Client (Phase 8).
 */

import { apiFetch } from '@/services/api';
import {
  FillBlankExercise,
  Flashcard,
  MCQQuestion,
  QuestionExplanationResponse,
  QuestionSourcesResponse,
  QuizAttempt,
  QuizAttemptAnswerSubmit,
  QuizAttemptConceptPerformanceResponse,
  QuizAttemptResultResponse,
  QuizAttemptSummary,
  QuizAttemptTrackingResponse,
  QuizHistoryListParams,
  QuizHistorySummary,
  QuizHistoryTrendsResponse,
  RevisionNote,
  TrueFalseQuestion,
  LearnerInteractionEventCreate,
  LearnerInteractionEventResponse,
  LearningInteractionsSummaryResponse,
  LearnerConceptMastery,
  LearnerConceptMasteryHistoryItem,
  LearnerMasterySummary,
} from '../types/study';

export interface GenerateStudyMaterialParams {
  scope?: {
    scope_type: 'workspace' | 'document' | 'chunk' | 'topic';
    document_ids?: string[];
    chunk_ids?: string[];
    topic_id?: string;
  };
  count?: number;
  difficulty?: 'easy' | 'medium' | 'hard';
  topic?: string;
}

export const studyApi = {
  // -------------------------------------------------------------------------
  // Revision Notes (C8.1)
  // -------------------------------------------------------------------------

  async generateRevisionNotes(
    workspaceId: string,
    payload: {
      scope?: any;
      length?: 'concise' | 'standard' | 'comprehensive';
      detail_level?: 'introductory' | 'intermediate' | 'advanced';
      focus?: 'exam_cram' | 'conceptual_learning' | 'technical_depth';
      custom_title?: string;
    } = {}
  ): Promise<RevisionNote> {
    return apiFetch<RevisionNote>(
      `workspaces/${encodeURIComponent(workspaceId)}/study-materials/revision-notes/generate`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
      30000 // Higher timeout for generation
    );
  },

  async listRevisionNotes(
    workspaceId: string,
    params: { limit?: number; offset?: number } = {}
  ): Promise<{ items: RevisionNote[]; total: number }> {
    const query = new URLSearchParams();
    if (params.limit) query.set('limit', String(params.limit));
    if (params.offset) query.set('offset', String(params.offset));
    const qs = query.toString();
    return apiFetch<{ items: RevisionNote[]; total: number }>(
      `workspaces/${encodeURIComponent(workspaceId)}/study-materials/revision-notes${qs ? `?${qs}` : ''}`
    );
  },

  async getRevisionNote(workspaceId: string, noteId: string): Promise<RevisionNote> {
    return apiFetch<RevisionNote>(
      `workspaces/${encodeURIComponent(workspaceId)}/study-materials/revision-notes/${encodeURIComponent(noteId)}`
    );
  },

  // -------------------------------------------------------------------------
  // Multiple-Choice Questions (C8.2)
  // -------------------------------------------------------------------------

  async generateMCQs(
    workspaceId: string,
    payload: GenerateStudyMaterialParams = {}
  ): Promise<MCQQuestion[]> {
    return apiFetch<MCQQuestion[]>(
      `workspaces/${encodeURIComponent(workspaceId)}/study-materials/mcqs/generate`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
      30000
    );
  },

  async listMCQs(
    workspaceId: string,
    params: { difficulty?: string; mode?: 'practice' | 'review'; limit?: number; offset?: number } = {}
  ): Promise<{ items: MCQQuestion[]; total: number; mode: string }> {
    const query = new URLSearchParams();
    if (params.difficulty) query.set('difficulty', params.difficulty);
    query.set('mode', params.mode || 'review');
    if (params.limit) query.set('limit', String(params.limit));
    if (params.offset) query.set('offset', String(params.offset));
    const qs = query.toString();
    return apiFetch<{ items: MCQQuestion[]; total: number; mode: string }>(
      `workspaces/${encodeURIComponent(workspaceId)}/study-materials/mcqs${qs ? `?${qs}` : ''}`
    );
  },

  // -------------------------------------------------------------------------
  // Fill-in-the-Blanks (C8.3)
  // -------------------------------------------------------------------------

  async generateFillBlanks(
    workspaceId: string,
    payload: GenerateStudyMaterialParams = {}
  ): Promise<FillBlankExercise[]> {
    return apiFetch<FillBlankExercise[]>(
      `workspaces/${encodeURIComponent(workspaceId)}/study-materials/fill-blanks/generate`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
      30000
    );
  },

  async listFillBlanks(
    workspaceId: string,
    params: { difficulty?: string; mode?: 'practice' | 'review'; limit?: number; offset?: number } = {}
  ): Promise<{ items: FillBlankExercise[]; total: number; mode: string }> {
    const query = new URLSearchParams();
    if (params.difficulty) query.set('difficulty', params.difficulty);
    query.set('mode', params.mode || 'review');
    if (params.limit) query.set('limit', String(params.limit));
    if (params.offset) query.set('offset', String(params.offset));
    const qs = query.toString();
    return apiFetch<{ items: FillBlankExercise[]; total: number; mode: string }>(
      `workspaces/${encodeURIComponent(workspaceId)}/study-materials/fill-blanks${qs ? `?${qs}` : ''}`
    );
  },

  // -------------------------------------------------------------------------
  // True / False (C8.4)
  // -------------------------------------------------------------------------

  async generateTrueFalse(
    workspaceId: string,
    payload: GenerateStudyMaterialParams & { target_true_ratio?: number } = {}
  ): Promise<TrueFalseQuestion[]> {
    return apiFetch<TrueFalseQuestion[]>(
      `workspaces/${encodeURIComponent(workspaceId)}/study-materials/true-false/generate`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
      30000
    );
  },

  async listTrueFalse(
    workspaceId: string,
    params: { difficulty?: string; mode?: 'practice' | 'review'; limit?: number; offset?: number } = {}
  ): Promise<{ items: TrueFalseQuestion[]; total: number; mode: string }> {
    const query = new URLSearchParams();
    if (params.difficulty) query.set('difficulty', params.difficulty);
    query.set('mode', params.mode || 'review');
    if (params.limit) query.set('limit', String(params.limit));
    if (params.offset) query.set('offset', String(params.offset));
    const qs = query.toString();
    return apiFetch<{ items: TrueFalseQuestion[]; total: number; mode: string }>(
      `workspaces/${encodeURIComponent(workspaceId)}/study-materials/true-false${qs ? `?${qs}` : ''}`
    );
  },

  // -------------------------------------------------------------------------
  // Flashcards (C8.5)
  // -------------------------------------------------------------------------

  async generateFlashcards(
    workspaceId: string,
    payload: GenerateStudyMaterialParams & { card_type?: string } = {}
  ): Promise<Flashcard[]> {
    return apiFetch<Flashcard[]>(
      `workspaces/${encodeURIComponent(workspaceId)}/study-materials/flashcards/generate`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
      30000
    );
  },

  async listFlashcards(
    workspaceId: string,
    params: { card_type?: string; difficulty?: string; limit?: number; offset?: number } = {}
  ): Promise<{ items: Flashcard[]; total: number }> {
    const query = new URLSearchParams();
    if (params.card_type) query.set('card_type', params.card_type);
    if (params.difficulty) query.set('difficulty', params.difficulty);
    if (params.limit) query.set('limit', String(params.limit));
    if (params.offset) query.set('offset', String(params.offset));
    const qs = query.toString();
    return apiFetch<{ items: Flashcard[]; total: number }>(
      `workspaces/${encodeURIComponent(workspaceId)}/study-materials/flashcards${qs ? `?${qs}` : ''}`
    );
  },

  // -------------------------------------------------------------------------
  // Interactive Quiz Attempts (C8.6)
  // -------------------------------------------------------------------------

  async createQuizAttempt(
    workspaceId: string,
    payload: {
      title?: string;
      count?: number;
      difficulty?: string;
      question_types?: string[];
      question_ids?: string[];
    } = {}
  ): Promise<QuizAttempt> {
    return apiFetch<QuizAttempt>(
      `workspaces/${encodeURIComponent(workspaceId)}/quiz-attempts`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }
    );
  },

  async listQuizAttempts(
    workspaceId: string,
    params: { limit?: number; offset?: number } = {}
  ): Promise<{ items: QuizAttemptSummary[]; total: number }> {
    const query = new URLSearchParams();
    if (params.limit) query.set('limit', String(params.limit));
    if (params.offset) query.set('offset', String(params.offset));
    const qs = query.toString();
    return apiFetch<{ items: QuizAttemptSummary[]; total: number }>(
      `workspaces/${encodeURIComponent(workspaceId)}/quiz-attempts${qs ? `?${qs}` : ''}`
    );
  },

  async getQuizAttempt(workspaceId: string, attemptId: string): Promise<QuizAttempt> {
    return apiFetch<QuizAttempt>(
      `workspaces/${encodeURIComponent(workspaceId)}/quiz-attempts/${encodeURIComponent(attemptId)}`
    );
  },

  async saveQuizAnswers(
    workspaceId: string,
    attemptId: string,
    answers: QuizAttemptAnswerSubmit[]
  ): Promise<QuizAttempt> {
    return apiFetch<QuizAttempt>(
      `workspaces/${encodeURIComponent(workspaceId)}/quiz-attempts/${encodeURIComponent(attemptId)}/answers`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers }),
      }
    );
  },

  async submitQuizAttempt(
    workspaceId: string,
    attemptId: string,
    answers?: QuizAttemptAnswerSubmit[]
  ): Promise<QuizAttemptResultResponse> {
    return apiFetch<QuizAttemptResultResponse>(
      `workspaces/${encodeURIComponent(workspaceId)}/quiz-attempts/${encodeURIComponent(attemptId)}/submit`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: answers ? JSON.stringify({ answers }) : undefined,
      }
    );
  },

  async getQuizResults(workspaceId: string, attemptId: string): Promise<QuizAttemptResultResponse> {
    return apiFetch<QuizAttemptResultResponse>(
      `workspaces/${encodeURIComponent(workspaceId)}/quiz-attempts/${encodeURIComponent(attemptId)}/results`
    );
  },

  // -------------------------------------------------------------------------
  // C8.8: Source-Linked Explanations & Citations
  // -------------------------------------------------------------------------

  async getQuestionExplanation(
    workspaceId: string,
    attemptId: string,
    questionId: string
  ): Promise<QuestionExplanationResponse> {
    return apiFetch<QuestionExplanationResponse>(
      `workspaces/${encodeURIComponent(workspaceId)}/quiz-attempts/${encodeURIComponent(attemptId)}/questions/${encodeURIComponent(questionId)}/explanation`
    );
  },

  async getQuestionSources(
    workspaceId: string,
    attemptId: string,
    questionId: string
  ): Promise<QuestionSourcesResponse> {
    return apiFetch<QuestionSourcesResponse>(
      `workspaces/${encodeURIComponent(workspaceId)}/quiz-attempts/${encodeURIComponent(attemptId)}/questions/${encodeURIComponent(questionId)}/sources`
    );
  },

  // -------------------------------------------------------------------------
  // C8.9: Quiz History, Analytics & Retakes
  // -------------------------------------------------------------------------

  async listQuizHistory(
    workspaceId: string,
    params: QuizHistoryListParams = {}
  ): Promise<{ items: QuizAttemptSummary[]; total: number }> {
    const query = new URLSearchParams();
    if (params.status) query.set('status', params.status);
    if (params.search) query.set('search', params.search);
    if (params.sort_by) query.set('sort_by', params.sort_by);
    if (params.sort_order) query.set('sort_order', params.sort_order);
    if (params.limit) query.set('limit', String(params.limit));
    if (params.offset) query.set('offset', String(params.offset));
    const qs = query.toString();
    return apiFetch<{ items: QuizAttemptSummary[]; total: number }>(
      `workspaces/${encodeURIComponent(workspaceId)}/quiz-history${qs ? `?${qs}` : ''}`
    );
  },

  async getQuizHistorySummary(workspaceId: string): Promise<QuizHistorySummary> {
    return apiFetch<QuizHistorySummary>(
      `workspaces/${encodeURIComponent(workspaceId)}/quiz-history/summary`
    );
  },

  async getQuizHistoryTrends(workspaceId: string): Promise<QuizHistoryTrendsResponse> {
    return apiFetch<QuizHistoryTrendsResponse>(
      `workspaces/${encodeURIComponent(workspaceId)}/quiz-history/trends`
    );
  },

  async retakeQuizAttempt(workspaceId: string, attemptId: string): Promise<QuizAttempt> {
    return apiFetch<QuizAttempt>(
      `workspaces/${encodeURIComponent(workspaceId)}/quiz-attempts/${encodeURIComponent(attemptId)}/retake`,
      {
        method: 'POST',
      }
    );
  },

  // -------------------------------------------------------------------------
  // Phase 9: Learner Intelligence (C9.1, C9.2, C9.3)
  // -------------------------------------------------------------------------

  async recordInteractionEvent(
    workspaceId: string,
    payload: LearnerInteractionEventCreate
  ): Promise<LearnerInteractionEventResponse> {
    return apiFetch<LearnerInteractionEventResponse>(
      `workspaces/${encodeURIComponent(workspaceId)}/learning-interactions/events`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }
    );
  },

  async recordInteractionBatch(
    workspaceId: string,
    events: LearnerInteractionEventCreate[]
  ): Promise<LearnerInteractionEventResponse[]> {
    return apiFetch<LearnerInteractionEventResponse[]>(
      `workspaces/${encodeURIComponent(workspaceId)}/learning-interactions/events/batch`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ events }),
      }
    );
  },

  async getAttemptTracking(
    workspaceId: string,
    attemptId: string
  ): Promise<QuizAttemptTrackingResponse> {
    return apiFetch<QuizAttemptTrackingResponse>(
      `workspaces/${encodeURIComponent(workspaceId)}/quiz-attempts/${encodeURIComponent(attemptId)}/tracking`
    );
  },

  async getAttemptConceptPerformance(
    workspaceId: string,
    attemptId: string
  ): Promise<QuizAttemptConceptPerformanceResponse> {
    return apiFetch<QuizAttemptConceptPerformanceResponse>(
      `workspaces/${encodeURIComponent(workspaceId)}/quiz-attempts/${encodeURIComponent(attemptId)}/concept-performance`
    );
  },

  async getLearningInteractionsSummary(
    workspaceId: string
  ): Promise<LearningInteractionsSummaryResponse> {
    return apiFetch<LearningInteractionsSummaryResponse>(
      `workspaces/${encodeURIComponent(workspaceId)}/learning-interactions/summary`
    );
  },

  // -------------------------------------------------------------------------
  // Phase 9: Bayesian Knowledge Tracing (C9.4, C9.5, C9.6)
  // -------------------------------------------------------------------------

  async getMyConceptMasteries(
    workspaceId: string
  ): Promise<LearnerConceptMastery[]> {
    return apiFetch<LearnerConceptMastery[]>(
      `workspaces/${encodeURIComponent(workspaceId)}/bkt/learners/me/mastery`
    );
  },

  async getMyConceptMastery(
    workspaceId: string,
    conceptId: string
  ): Promise<LearnerConceptMastery> {
    return apiFetch<LearnerConceptMastery>(
      `workspaces/${encodeURIComponent(workspaceId)}/bkt/learners/me/concepts/${encodeURIComponent(conceptId)}/mastery`
    );
  },

  async getMyConceptMasteryHistory(
    workspaceId: string,
    conceptId: string
  ): Promise<LearnerConceptMasteryHistoryItem[]> {
    return apiFetch<LearnerConceptMasteryHistoryItem[]>(
      `workspaces/${encodeURIComponent(workspaceId)}/bkt/learners/me/concepts/${encodeURIComponent(conceptId)}/history`
    );
  },

  async getMyMasterySummary(
    workspaceId: string
  ): Promise<LearnerMasterySummary> {
    return apiFetch<LearnerMasterySummary>(
      `workspaces/${encodeURIComponent(workspaceId)}/bkt/learners/me/mastery/summary`
    );
  },
};
