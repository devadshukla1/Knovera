/**
 * Knovera Learning Analytics & Revision Recommendation API Client (Phase 9 C9.7, C9.8).
 */

import { apiFetch } from '@/services/api';
import {
  ActivityTimelineResponse,
  AnalyticsDateFilter,
  AnalyticsOverview,
  ConceptAnalyticsResponse,
  ConceptRevisionResources,
  MasteryAnalyticsResponse,
  QuizPerformance,
  RecommendationPriority,
  RecommendationStatus,
  RecommendationType,
  RevisionRecommendationItem,
  ScoreHistoryResponse,
} from '../types/analytics';

export const analyticsApi = {
  // ---------------------------------------------------------------------------
  // Dashboard Overview & Performance (C9.8)
  // ---------------------------------------------------------------------------

  async getOverview(
    workspaceId: string,
    dateFilter: AnalyticsDateFilter = 'all'
  ): Promise<AnalyticsOverview> {
    const params = new URLSearchParams({ date_filter: dateFilter });
    return apiFetch<AnalyticsOverview>(
      `/workspaces/${encodeURIComponent(workspaceId)}/learning-analytics/overview?${params.toString()}`
    );
  },

  async getQuizPerformance(
    workspaceId: string,
    dateFilter: AnalyticsDateFilter = 'all'
  ): Promise<QuizPerformance> {
    const params = new URLSearchParams({ date_filter: dateFilter });
    return apiFetch<QuizPerformance>(
      `/workspaces/${encodeURIComponent(workspaceId)}/learning-analytics/quiz-performance?${params.toString()}`
    );
  },

  async getScoreHistory(
    workspaceId: string,
    dateFilter: AnalyticsDateFilter = 'all'
  ): Promise<ScoreHistoryResponse> {
    const params = new URLSearchParams({ date_filter: dateFilter });
    return apiFetch<ScoreHistoryResponse>(
      `/workspaces/${encodeURIComponent(workspaceId)}/learning-analytics/score-history?${params.toString()}`
    );
  },

  async getConceptAnalytics(
    workspaceId: string,
    dateFilter: AnalyticsDateFilter = 'all'
  ): Promise<ConceptAnalyticsResponse> {
    const params = new URLSearchParams({ date_filter: dateFilter });
    return apiFetch<ConceptAnalyticsResponse>(
      `/workspaces/${encodeURIComponent(workspaceId)}/learning-analytics/concepts?${params.toString()}`
    );
  },

  async getMasteryOverview(workspaceId: string): Promise<MasteryAnalyticsResponse> {
    return apiFetch<MasteryAnalyticsResponse>(
      `/workspaces/${encodeURIComponent(workspaceId)}/learning-analytics/mastery`
    );
  },

  async getActivityTimeline(
    workspaceId: string,
    limit: number = 30
  ): Promise<ActivityTimelineResponse> {
    const params = new URLSearchParams({ limit: String(limit) });
    return apiFetch<ActivityTimelineResponse>(
      `/workspaces/${encodeURIComponent(workspaceId)}/learning-analytics/activity?${params.toString()}`
    );
  },

  // ---------------------------------------------------------------------------
  // Revision Recommendations (C9.7)
  // ---------------------------------------------------------------------------

  async getRecommendations(
    workspaceId: string,
    params?: {
      priority?: RecommendationPriority;
      type?: RecommendationType;
      status?: RecommendationStatus;
    }
  ): Promise<RevisionRecommendationItem[]> {
    const query = new URLSearchParams();
    if (params?.priority) query.append('priority', params.priority);
    if (params?.type) query.append('recommendation_type', params.type);
    if (params?.status) query.append('status', params.status);

    const queryString = query.toString();
    const subpath = queryString
      ? `/workspaces/${encodeURIComponent(workspaceId)}/recommendations?${queryString}`
      : `/workspaces/${encodeURIComponent(workspaceId)}/recommendations`;

    return apiFetch<RevisionRecommendationItem[]>(subpath);
  },

  async generateRecommendations(
    workspaceId: string,
    options?: { forceRegenerate?: boolean; maxRecommendations?: number }
  ): Promise<RevisionRecommendationItem[]> {
    return apiFetch<RevisionRecommendationItem[]>(
      `/workspaces/${encodeURIComponent(workspaceId)}/recommendations/generate`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          force_regenerate: options?.forceRegenerate ?? false,
          max_recommendations: options?.maxRecommendations ?? 10,
        }),
      }
    );
  },

  async updateRecommendationStatus(
    workspaceId: string,
    recommendationId: string,
    status: RecommendationStatus
  ): Promise<RevisionRecommendationItem> {
    return apiFetch<RevisionRecommendationItem>(
      `/workspaces/${encodeURIComponent(workspaceId)}/recommendations/${encodeURIComponent(recommendationId)}/status`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      }
    );
  },

  async getConceptRevisionResources(
    workspaceId: string,
    conceptId: string
  ): Promise<ConceptRevisionResources> {
    return apiFetch<ConceptRevisionResources>(
      `/workspaces/${encodeURIComponent(workspaceId)}/concepts/${encodeURIComponent(conceptId)}/revision-resources`
    );
  },
};
