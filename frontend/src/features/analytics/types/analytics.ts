/**
 * TypeScript types for Knovera Learning Analytics and Revision Recommendations (Phase 9 C9.7, C9.8).
 */

export type AnalyticsDateFilter = '7d' | '30d' | '90d' | 'all';

export type RecommendationType =
  | 'revise_concept'
  | 'practice_concept'
  | 'reinforce_concept'
  | 'review_source_material'
  | 'insufficient_evidence'
  | 'no_action_needed';

export type RecommendationPriority = 'high' | 'medium' | 'low';

export type RecommendationStatus =
  | 'suggested'
  | 'viewed'
  | 'started'
  | 'completed'
  | 'dismissed'
  | 'expired';

export interface LinkedResourceItem {
  resource_type: 'revision_note' | 'flashcard' | 'question' | 'document_chunk';
  resource_id: string;
  title: string;
  preview?: string | null;
  document_id?: string | null;
  page_number?: number | null;
}

export interface LinkedResources {
  revision_notes?: LinkedResourceItem[];
  flashcards?: LinkedResourceItem[];
  practice_questions?: LinkedResourceItem[];
  source_chunks?: LinkedResourceItem[];
}

export interface RevisionRecommendationItem {
  id: string;
  workspace_id: string;
  user_id: string;
  concept_id: string;
  concept_name?: string | null;
  concept_description?: string | null;
  recommendation_type: RecommendationType;
  priority: RecommendationPriority;
  explanation: string;
  evidence_summary: {
    observation_count?: number;
    evidence_sufficiency?: 'sufficient' | 'sparse' | 'unobserved';
    questions_answered?: number;
    correct_answers?: number;
    incorrect_answers?: number;
    correct_rate?: number;
    bkt_posterior_mastery?: number | null;
    bkt_model_qualified?: boolean;
    bkt_status?: string;
  };
  model_version_id?: string | null;
  status: RecommendationStatus;
  linked_resources: LinkedResources;
  created_at: string;
  updated_at: string;
}

export interface AnalyticsOverview {
  total_quiz_attempts: number;
  completed_attempts: number;
  evaluated_attempts: number;
  average_quiz_score: number;
  overall_correct_rate: number;
  total_questions_answered: number;
  total_correct_answers: number;
  total_incorrect_answers: number;
  total_unanswered: number;
  concepts_assessed: number;
  concepts_with_sufficient_bkt: number;
  pending_recommendations_count: number;
  date_filter: string;
}

export interface QuizPerformance {
  total_attempts: number;
  average_score: number;
  highest_score: number;
  recent_score?: number | null;
  recent_attempt_id?: string | null;
  recent_attempt_date?: string | null;
  total_answered: number;
  total_correct: number;
  total_incorrect: number;
  total_unanswered: number;
  correct_rate: number;
}

export interface ScoreHistoryPoint {
  attempt_id: string;
  attempt_date: string;
  score_percentage: number;
  passed: boolean;
  total_questions: number;
  correct_count: number;
}

export interface ScoreHistoryResponse {
  points: ScoreHistoryPoint[];
  total_points: number;
}

export interface ConceptAnalyticsItem {
  concept_id: string;
  concept_name: string;
  category?: string | null;
  questions_attempted: number;
  questions_answered: number;
  correct_answers: number;
  incorrect_answers: number;
  unanswered: number;
  correct_rate: number;
  evidence_sufficiency: 'sufficient' | 'sparse' | 'unobserved';
  bkt_mastery_probability?: number | null;
  bkt_status?: string | null;
  last_activity_at?: string | null;
}

export interface ConceptAnalyticsResponse {
  concepts: ConceptAnalyticsItem[];
  total_count: number;
}

export interface MasteryAnalyticsItem {
  concept_id: string;
  concept_name: string;
  category?: string | null;
  prior_mastery: number;
  posterior_mastery: number;
  predicted_next_mastery: number;
  observation_count: number;
  correct_count: number;
  bkt_status: string;
  model_version?: string | null;
  is_model_validated: boolean;
  last_updated_at: string;
}

export interface MasteryAnalyticsResponse {
  masteries: MasteryAnalyticsItem[];
  total_concepts_tracked: number;
  model_readiness_status: string;
  active_model_version?: string | null;
}

export interface ActivityTimelineItem {
  event_id: string;
  event_type: string;
  occurred_at: string;
  title: string;
  description: string;
  concept_id?: string | null;
  concept_name?: string | null;
  attempt_id?: string | null;
  metadata?: Record<string, unknown>;
}

export interface ActivityTimelineResponse {
  events: ActivityTimelineItem[];
  total_events: number;
}

export interface ConceptRevisionResources {
  concept_id: string;
  concept_name: string;
  revision_notes: Array<{
    resource_type: string;
    resource_id: string;
    title: string;
    preview?: string | null;
    document_id?: string | null;
  }>;
  flashcards: Array<{
    resource_type: string;
    resource_id: string;
    title: string;
    preview?: string | null;
  }>;
  practice_questions: Array<{
    resource_type: string;
    resource_id: string;
    title: string;
    preview?: string | null;
  }>;
  source_documents: Array<{
    resource_type: string;
    resource_id: string;
    title: string;
    preview?: string | null;
    document_id?: string | null;
    page_number?: number | null;
  }>;
}
