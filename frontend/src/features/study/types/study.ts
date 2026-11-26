/**
 * Knovera Study Material Generation & Interactive Quiz Interfaces (Phase 8).
 */

export type QuestionDifficulty = 'easy' | 'medium' | 'hard';
export type FlashcardType =
  | 'definition'
  | 'concept'
  | 'fact'
  | 'formula'
  | 'algorithm'
  | 'comparison'
  | 'application'
  | 'terminology';

export type QuizAttemptStatus = 'not_started' | 'in_progress' | 'submitted' | 'evaluated' | 'abandoned';

export interface SourceReference {
  chunk_id: string;
  document_id: string;
  document_title: string;
  chunk_index?: number;
  page_number?: number;
  slide_number?: number;
  section_title?: string;
  section_heading?: string;
  text_excerpt?: string;
  excerpt?: string;
  start_char_offset?: number;
  end_char_offset?: number;
}

export interface SourceScope {
  scope_type: 'workspace' | 'document' | 'chunk' | 'topic';
  document_ids?: string[];
  chunk_ids?: string[];
  topic_id?: string;
  max_chunks?: number;
}

// ---------------------------------------------------------------------------
// Revision Notes (C8.1)
// ---------------------------------------------------------------------------

export interface NoteSection {
  heading: string;
  summary: string;
  bullet_points: string[];
  key_takeaways: string[];
}

export interface KeyConceptItem {
  term: string;
  definition: string;
  context?: string;
}

export interface FormulaItem {
  name: string;
  expression: string;
  explanation?: string;
}

export interface RevisionNote {
  id: string;
  workspace_id: string;
  generation_id?: string;
  title: string;
  overview: string;
  length: 'concise' | 'standard' | 'comprehensive';
  detail_level: 'introductory' | 'intermediate' | 'advanced';
  focus: 'exam_cram' | 'conceptual_learning' | 'technical_depth';
  sections: NoteSection[];
  key_concepts: KeyConceptItem[];
  important_points: string[];
  formulas: FormulaItem[];
  quick_summary: string[];
  source_references: SourceReference[];
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// MCQs (C8.2)
// ---------------------------------------------------------------------------

export interface MCQOptionPractice {
  id: string;
  option_id: string; // 'A', 'B', 'C', 'D'
  option_text: string;
}

export interface MCQOptionReview extends MCQOptionPractice {
  is_correct: boolean;
}

export interface MCQQuestion {
  id: string;
  workspace_id: string;
  generation_id?: string;
  question_text: string;
  difficulty: QuestionDifficulty;
  question_type: string;
  topic_tags: string[];
  options: (MCQOptionPractice | MCQOptionReview)[];
  correct_option_id?: string;
  explanation?: string;
  source_references?: SourceReference[];
  created_at: string;
}

// ---------------------------------------------------------------------------
// Fill-in-the-Blanks (C8.3)
// ---------------------------------------------------------------------------

export interface FillBlankExercise {
  id: string;
  workspace_id: string;
  generation_id?: string;
  sentence_with_blank: string;
  original_sentence?: string;
  canonical_answer?: string;
  accepted_answers?: string[];
  target_start_offset?: number;
  target_end_offset?: number;
  difficulty: QuestionDifficulty;
  hint?: string;
  explanation?: string;
  source_reference?: SourceReference;
  created_at: string;
}

// ---------------------------------------------------------------------------
// True / False Questions (C8.4)
// ---------------------------------------------------------------------------

export interface TrueFalseQuestion {
  id: string;
  workspace_id: string;
  generation_id?: string;
  statement: string;
  correct_answer?: boolean;
  explanation?: string;
  difficulty: QuestionDifficulty;
  topic?: string;
  validation_status?: string;
  source_references?: SourceReference[];
  created_at: string;
}

// ---------------------------------------------------------------------------
// Flashcards (C8.5)
// ---------------------------------------------------------------------------

export interface Flashcard {
  id: string;
  workspace_id: string;
  generation_id?: string;
  front: string;
  back: string;
  card_type: FlashcardType;
  difficulty: QuestionDifficulty;
  topic?: string;
  validation_status?: string;
  source_references?: SourceReference[];
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Interactive Quizzes (C8.6)
// ---------------------------------------------------------------------------

export interface QuizQuestionPracticeItem {
  id: string;
  question_type: 'mcq' | 'true_false' | 'fill_blank';
  question_text: string;
  difficulty: QuestionDifficulty;
  options?: MCQOptionPractice[];
  hint?: string;
  document_title?: string;
  page_number?: number;
}

export interface QuizAttempt {
  id: string;
  workspace_id: string;
  user_id: string;
  title: string;
  status: QuizAttemptStatus;
  total_questions: number;
  answered_count: number;
  started_at: string;
  submitted_at?: string;
  questions: QuizQuestionPracticeItem[];
  saved_answers: Record<string, any>;
}

export interface QuizAttemptSummary {
  id: string;
  workspace_id: string;
  title: string;
  status: QuizAttemptStatus;
  total_questions: number;
  correct_answers_count?: number;
  score_percentage?: number;
  started_at: string;
  submitted_at?: string;
}

export interface QuizAttemptAnswerSubmit {
  question_id: string;
  question_type: string;
  selected_answer: any;
}

export interface QuizAttemptResultDetail {
  question_id: string;
  question_type: string;
  question_text: string;
  difficulty: QuestionDifficulty;
  learner_answer: any;
  correct_answer: any;
  is_correct: boolean;
  explanation: string;
  source_references: SourceReference[];
}

export interface QuizAttemptResultResponse {
  attempt_id: string;
  title: string;
  status: QuizAttemptStatus;
  total_questions: number;
  correct_count: number;
  incorrect_count: number;
  unanswered_count: number;
  score_percentage: number;
  started_at: string;
  submitted_at?: string;
  results: QuizAttemptResultDetail[];
}

// ---------------------------------------------------------------------------
// C8.8: Explanations & Sources
// ---------------------------------------------------------------------------

export interface QuestionExplanationResponse {
  attempt_id: string;
  question_id: string;
  question_type: string;
  question_text: string;
  explanation: string;
  correct_answer: any;
  learner_answer?: any;
  is_correct?: boolean;
}

export interface QuestionSourcesResponse {
  attempt_id: string;
  question_id: string;
  question_type: string;
  source_references: SourceReference[];
}

// ---------------------------------------------------------------------------
// C8.9: History & Analytics
// ---------------------------------------------------------------------------

export interface QuizHistorySummary {
  total_attempts: number;
  completed_attempts: number;
  in_progress_attempts: number;
  average_score: number;
  overall_correct_rate: number;
  total_questions_answered: number;
  total_correct_answers: number;
}

export interface QuizHistoryTrendPoint {
  attempt_id: string;
  title: string;
  score_percentage: number;
  total_questions: number;
  correct_count: number;
  completed_at: string;
}

export interface QuizHistoryTrendsResponse {
  trends: QuizHistoryTrendPoint[];
}

export interface QuizHistoryListParams {
  status?: string;
  search?: string;
  sort_by?: 'created_at' | 'score_percentage';
  sort_order?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

// ---------------------------------------------------------------------------
// Phase 9: Learner Intelligence Foundation (C9.1, C9.2, C9.3)
// ---------------------------------------------------------------------------

export type LearnerEventType =
  | 'question_presented'
  | 'question_viewed'
  | 'question_skipped'
  | 'question_flagged'
  | 'question_navigated'
  | 'answer_selected'
  | 'answer_saved'
  | 'answer_revised'
  | 'answer_submitted'
  | 'hint_opened'
  | 'explanation_opened'
  | 'correct_answer_revealed'
  | 'source_opened'
  | 'source_page_navigated'
  | 'quiz_started'
  | 'quiz_resumed'
  | 'quiz_paused'
  | 'quiz_submitted'
  | 'quiz_evaluated';

export interface LearnerInteractionEventCreate {
  event_type: LearnerEventType;
  attempt_id?: string;
  question_id?: string;
  concept_id?: string;
  client_occurred_at?: string;
  event_metadata?: Record<string, any>;
  idempotency_key?: string;
  schema_version?: string;
}

export interface LearnerInteractionEventResponse {
  id: string;
  workspace_id: string;
  user_id: string;
  attempt_id?: string;
  question_id?: string;
  concept_id?: string;
  event_type: string;
  occurred_at: string;
  client_occurred_at?: string;
  event_metadata: Record<string, any>;
  idempotency_key?: string;
  schema_version: string;
  created_at: string;
}

export interface ConceptPerformanceMetric {
  concept_id: string;
  concept_name: string;
  category: string;
  questions_attempted: number;
  questions_answered: number;
  correct_answers: number;
  incorrect_answers: number;
  unanswered: number;
  correct_rate: number;
}

export interface QuizAttemptConceptPerformanceResponse {
  attempt_id: string;
  title: string;
  status: string;
  evaluated_at?: string;
  concepts: ConceptPerformanceMetric[];
}

export interface QuestionTrackingMetric {
  question_id: string;
  question_type: string;
  display_order: number;
  is_answered: boolean;
  is_correct?: boolean;
  selected_answer?: any;
  response_duration_ms?: number;
  revision_count: number;
  hint_opened: boolean;
  explanation_opened: boolean;
  source_opened: boolean;
  mapped_concepts: string[];
}

export interface QuizAttemptTrackingResponse {
  attempt_id: string;
  workspace_id: string;
  user_id: string;
  title: string;
  status: string;
  started_at: string;
  submitted_at?: string;
  total_duration_seconds?: number;
  total_questions: number;
  answered_count: number;
  unanswered_count: number;
  correct_count: number;
  incorrect_count: number;
  score_percentage: number;
  questions: QuestionTrackingMetric[];
  concept_performance: ConceptPerformanceMetric[];
}

export interface LearningInteractionsSummaryResponse {
  workspace_id: string;
  total_events: number;
  events_by_type: Record<string, number>;
  active_attempts_count: number;
  total_hints_opened: number;
  total_explanations_opened: number;
  total_sources_opened: number;
}

// ---------------------------------------------------------------------------
// Phase 9: Bayesian Knowledge Tracing (C9.4, C9.5, C9.6)
// ---------------------------------------------------------------------------

export type BKTStatus = 'insufficient_data' | 'developing' | 'mastered';

export interface LearnerConceptMastery {
  id: string;
  workspace_id: string;
  user_id: string;
  concept_id: string;
  concept_name?: string;
  concept_category?: string;
  model_version_id?: string;
  posterior_mastery_probability: number;
  predicted_next_mastery_probability: number;
  observation_count: number;
  last_attempt_id?: string;
  last_question_id?: string;
  last_observation_correct?: boolean;
  status: BKTStatus;
  last_updated_at: string;
  created_at: string;
}

export interface LearnerConceptMasteryHistoryItem {
  id: string;
  workspace_id: string;
  user_id: string;
  concept_id: string;
  mastery_id: string;
  attempt_id: string;
  question_id: string;
  observation_correct: boolean;
  prior_mastery: number;
  posterior_mastery: number;
  predicted_next_mastery: number;
  p_init: number;
  p_transit: number;
  p_guess: number;
  p_slip: number;
  model_version: string;
  sequence_index: number;
  occurred_at: string;
  created_at: string;
}

export interface LearnerMasterySummary {
  workspace_id: string;
  user_id: string;
  total_concepts_evaluated: number;
  mastered_count: number;
  developing_count: number;
  insufficient_data_count: number;
  average_mastery_probability: number;
  items: LearnerConceptMastery[];
}

