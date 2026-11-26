import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  TrendingUp,
  Brain,
  CheckCircle2,
  HelpCircle,
  Clock,
  Sparkles,
  RefreshCw,
  Layers,
  BookOpen,
  Filter,
  Check,
  Eye,
  Play,
  X,
  ChevronRight,
  Award,
  BarChart3,
  ListFilter,
  GraduationCap,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { BlurFade } from '@/components/magicui/BlurFade';
import { NumberTicker } from '@/components/magicui/NumberTicker';
import { analyticsApi } from '../api/analyticsApi';
import {
  AnalyticsDateFilter,
  RecommendationPriority,
  RecommendationStatus,
  RecommendationType,
} from '../types/analytics';
import { ConceptResourcesModal } from '../components/ConceptResourcesModal';

export const LearningAnalyticsPage: React.FC = () => {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const queryClient = useQueryClient();

  // Filters & Tab State
  const [dateFilter, setDateFilter] = useState<AnalyticsDateFilter>('all');
  const [activeTab, setActiveTab] = useState<'recommendations' | 'performance' | 'concepts' | 'activity'>('recommendations');
  const [priorityFilter, setPriorityFilter] = useState<'all' | RecommendationPriority>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'completed' | 'dismissed'>('active');
  const [conceptSearch, setConceptSearch] = useState('');

  // Resource inspection modal
  const [selectedConcept, setSelectedConcept] = useState<{ id: string; name: string } | null>(null);

  // Queries
  const { data: overview, isLoading: overviewLoading } = useQuery({
    queryKey: ['analytics-overview', workspaceId, dateFilter],
    queryFn: () => analyticsApi.getOverview(workspaceId!, dateFilter),
    enabled: Boolean(workspaceId),
  });

  const { data: quizPerformance, isLoading: perfLoading } = useQuery({
    queryKey: ['analytics-quiz-perf', workspaceId, dateFilter],
    queryFn: () => analyticsApi.getQuizPerformance(workspaceId!, dateFilter),
    enabled: Boolean(workspaceId),
  });

  const { data: scoreHistory, isLoading: historyLoading } = useQuery({
    queryKey: ['analytics-score-history', workspaceId, dateFilter],
    queryFn: () => analyticsApi.getScoreHistory(workspaceId!, dateFilter),
    enabled: Boolean(workspaceId),
  });

  const { data: conceptAnalytics, isLoading: conceptsLoading } = useQuery({
    queryKey: ['analytics-concepts', workspaceId, dateFilter],
    queryFn: () => analyticsApi.getConceptAnalytics(workspaceId!, dateFilter),
    enabled: Boolean(workspaceId),
  });

  const { data: masteryOverview } = useQuery({
    queryKey: ['analytics-mastery', workspaceId],
    queryFn: () => analyticsApi.getMasteryOverview(workspaceId!),
    enabled: Boolean(workspaceId),
  });

  const { data: recommendations, isLoading: recsLoading } = useQuery({
    queryKey: ['recommendations', workspaceId],
    queryFn: () => analyticsApi.getRecommendations(workspaceId!),
    enabled: Boolean(workspaceId),
  });

  const { data: activityTimeline, isLoading: timelineLoading } = useQuery({
    queryKey: ['analytics-timeline', workspaceId],
    queryFn: () => analyticsApi.getActivityTimeline(workspaceId!, 50),
    enabled: Boolean(workspaceId),
  });

  // Mutations
  const generateRecsMutation = useMutation({
    mutationFn: () => analyticsApi.generateRecommendations(workspaceId!, { forceRegenerate: true }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recommendations', workspaceId] });
      queryClient.invalidateQueries({ queryKey: ['analytics-overview', workspaceId] });
    },
  });

  const updateStatusMutation = useMutation({
    mutationFn: ({ recId, status }: { recId: string; status: RecommendationStatus }) =>
      analyticsApi.updateRecommendationStatus(workspaceId!, recId, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recommendations', workspaceId] });
      queryClient.invalidateQueries({ queryKey: ['analytics-overview', workspaceId] });
    },
  });

  if (!workspaceId) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <p className="text-text-muted">Please select a workspace to view learning analytics.</p>
      </div>
    );
  }

  // Filter recommendations
  const filteredRecs = (recommendations || []).filter((rec) => {
    if (priorityFilter !== 'all' && rec.priority !== priorityFilter) return false;
    if (statusFilter === 'active') {
      return ['suggested', 'viewed', 'started'].includes(rec.status);
    }
    if (statusFilter === 'completed') {
      return rec.status === 'completed';
    }
    if (statusFilter === 'dismissed') {
      return rec.status === 'dismissed' || rec.status === 'expired';
    }
    return true;
  });

  // Filter concepts
  const filteredConcepts = (conceptAnalytics?.concepts || []).filter((c) =>
    c.concept_name.toLowerCase().includes(conceptSearch.toLowerCase()) ||
    (c.category && c.category.toLowerCase().includes(conceptSearch.toLowerCase()))
  );

  const getPriorityBadgeVariant = (priority: RecommendationPriority): 'danger' | 'warning' | 'secondary' => {
    switch (priority) {
      case 'high':
        return 'danger';
      case 'medium':
        return 'warning';
      case 'low':
      default:
        return 'secondary';
    }
  };

  const formatRecType = (type: RecommendationType) => {
    switch (type) {
      case 'revise_concept':
        return 'Revise Concept';
      case 'practice_concept':
        return 'Practice Concept';
      case 'reinforce_concept':
        return 'Reinforce Concept';
      case 'review_source_material':
        return 'Review Source Material';
      case 'insufficient_evidence':
        return 'Needs Practice';
      case 'no_action_needed':
        return 'Proficient';
    }
  };

  return (
    <div className="flex flex-col gap-6 p-4 sm:p-7 lg:p-8 max-w-7xl mx-auto w-full">
      {/* Top Header */}
      <BlurFade delay={0.05}>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/80 pb-6">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-primary">
                Learner Intelligence Engine
              </span>
              <Badge variant="outline" className="text-[10px] font-mono border-primary/30 text-primary bg-primary/5">
                BKT & Analytics
              </Badge>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-text-primary mt-1">
              Learning Analytics & Revision Intelligence
            </h1>
            <p className="text-sm text-text-muted mt-1 max-w-2xl">
              Evidence-grounded learner performance tracking, latent Bayesian Knowledge Tracing (BKT) mastery estimation, and explainable revision recommendations.
            </p>
          </div>

          {/* Date Filter & Regenerate Action */}
          <div className="flex items-center gap-3 shrink-0 flex-wrap">
            <div className="flex items-center bg-surface-muted/60 rounded-xl p-1 border border-border/80">
              {(['7d', '30d', '90d', 'all'] as AnalyticsDateFilter[]).map((filter) => (
                <button
                  key={filter}
                  onClick={() => setDateFilter(filter)}
                  className={`px-3 py-1 text-xs font-medium rounded-lg transition-colors ${
                    dateFilter === filter
                      ? 'bg-primary text-primary-foreground shadow-sm'
                      : 'text-text-secondary hover:text-text-primary'
                  }`}
                >
                  {filter.toUpperCase()}
                </button>
              ))}
            </div>

            <Button
              size="sm"
              variant="outline"
              onClick={() => generateRecsMutation.mutate()}
              disabled={generateRecsMutation.isPending}
              className="gap-2 rounded-xl border-border/80"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${generateRecsMutation.isPending ? 'animate-spin' : ''}`} />
              <span>Generate Recommendations</span>
            </Button>
          </div>
        </div>
      </BlurFade>

      {/* Overview KPI Cards */}
      <BlurFade delay={0.1}>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
          {/* Total Attempts */}
          <Card className="bg-surface border-border/80 hover:border-primary/40 transition-colors">
            <CardHeader className="pb-2">
              <CardDescription className="text-xs flex items-center justify-between">
                <span>Quiz Attempts</span>
                <Award className="h-4 w-4 text-primary" />
              </CardDescription>
              <CardTitle className="text-2xl sm:text-3xl font-bold text-text-primary font-mono">
                {overviewLoading ? <Skeleton className="h-8 w-16" /> : <NumberTicker value={overview?.total_quiz_attempts ?? 0} />}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-[11px] text-text-muted">
                {overview?.completed_attempts ?? 0} completed & evaluated
              </p>
            </CardContent>
          </Card>

          {/* Average Quiz Score */}
          <Card className="bg-surface border-border/80 hover:border-accent/40 transition-colors">
            <CardHeader className="pb-2">
              <CardDescription className="text-xs flex items-center justify-between">
                <span>Avg Quiz Score</span>
                <TrendingUp className="h-4 w-4 text-accent" />
              </CardDescription>
              <CardTitle className="text-2xl sm:text-3xl font-bold text-text-primary font-mono flex items-baseline">
                {overviewLoading ? (
                  <Skeleton className="h-8 w-16" />
                ) : (
                  <>
                    <NumberTicker value={Math.round(overview?.average_quiz_score ?? 0)} />
                    <span className="text-sm font-semibold ml-0.5">%</span>
                  </>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-1.5">
              <Progress value={overview?.average_quiz_score ?? 0} className="h-1.5 bg-surface-muted/60" />
              <p className="text-[11px] text-text-muted">Target threshold: 70%</p>
            </CardContent>
          </Card>

          {/* Accuracy Rate */}
          <Card className="bg-surface border-border/80 hover:border-emerald-500/40 transition-colors">
            <CardHeader className="pb-2">
              <CardDescription className="text-xs flex items-center justify-between">
                <span>Accuracy Rate</span>
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              </CardDescription>
              <CardTitle className="text-2xl sm:text-3xl font-bold text-emerald-400 font-mono flex items-baseline">
                {overviewLoading ? (
                  <Skeleton className="h-8 w-16" />
                ) : (
                  <>
                    <NumberTicker value={Math.round(overview?.overall_correct_rate ?? 0)} />
                    <span className="text-sm font-semibold ml-0.5 text-emerald-400/80">%</span>
                  </>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-[11px] text-text-muted">
                {overview?.total_correct_answers ?? 0} correct of {overview?.total_questions_answered ?? 0} answered
              </p>
            </CardContent>
          </Card>

          {/* Assessed Concepts */}
          <Card className="bg-surface border-border/80 hover:border-violet-500/40 transition-colors">
            <CardHeader className="pb-2">
              <CardDescription className="text-xs flex items-center justify-between">
                <span>Assessed Concepts</span>
                <Layers className="h-4 w-4 text-violet-400" />
              </CardDescription>
              <CardTitle className="text-2xl sm:text-3xl font-bold text-text-primary font-mono">
                {overviewLoading ? <Skeleton className="h-8 w-16" /> : <NumberTicker value={overview?.concepts_assessed ?? 0} />}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-[11px] text-text-muted">
                {overview?.concepts_with_sufficient_bkt ?? 0} with sufficient evidence (N ≥ 3)
              </p>
            </CardContent>
          </Card>

          {/* Pending Recommendations */}
          <Card className="bg-surface border-border/80 hover:border-amber-400/40 transition-colors">
            <CardHeader className="pb-2">
              <CardDescription className="text-xs flex items-center justify-between">
                <span>Recommendations</span>
                <Sparkles className="h-4 w-4 text-amber-400" />
              </CardDescription>
              <CardTitle className="text-2xl sm:text-3xl font-bold text-text-primary font-mono">
                {overviewLoading ? (
                  <Skeleton className="h-8 w-16" />
                ) : (
                  <NumberTicker value={overview?.pending_recommendations_count ?? 0} />
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-[11px] text-text-muted">Active action items</p>
            </CardContent>
          </Card>
        </div>
      </BlurFade>

      {/* Navigation Tabs */}
      <BlurFade delay={0.15}>
        <div className="flex border-b border-border/80 space-x-1 overflow-x-auto">
          <button
            onClick={() => setActiveTab('recommendations')}
            className={`px-4 py-2.5 text-xs sm:text-sm font-medium border-b-2 transition-colors flex items-center gap-2 whitespace-nowrap ${
              activeTab === 'recommendations'
                ? 'border-primary text-primary font-semibold'
                : 'border-transparent text-text-secondary hover:text-text-primary hover:border-border'
            }`}
          >
            <Sparkles className="h-4 w-4" />
            <span>Revision Recommendations</span>
            {overview?.pending_recommendations_count ? (
              <Badge variant="secondary" className="text-[10px] px-1.5 py-0 font-mono">
                {overview.pending_recommendations_count}
              </Badge>
            ) : null}
          </button>

          <button
            onClick={() => setActiveTab('performance')}
            className={`px-4 py-2.5 text-xs sm:text-sm font-medium border-b-2 transition-colors flex items-center gap-2 whitespace-nowrap ${
              activeTab === 'performance'
                ? 'border-primary text-primary font-semibold'
                : 'border-transparent text-text-secondary hover:text-text-primary hover:border-border'
            }`}
          >
            <BarChart3 className="h-4 w-4" />
            <span>Quiz Performance & Trends</span>
          </button>

          <button
            onClick={() => setActiveTab('concepts')}
            className={`px-4 py-2.5 text-xs sm:text-sm font-medium border-b-2 transition-colors flex items-center gap-2 whitespace-nowrap ${
              activeTab === 'concepts'
                ? 'border-primary text-primary font-semibold'
                : 'border-transparent text-text-secondary hover:text-text-primary hover:border-border'
            }`}
          >
            <Brain className="h-4 w-4" />
            <span>Concept Mastery & Attribution</span>
          </button>

          <button
            onClick={() => setActiveTab('activity')}
            className={`px-4 py-2.5 text-xs sm:text-sm font-medium border-b-2 transition-colors flex items-center gap-2 whitespace-nowrap ${
              activeTab === 'activity'
                ? 'border-primary text-primary font-semibold'
                : 'border-transparent text-text-secondary hover:text-text-primary hover:border-border'
            }`}
          >
            <Clock className="h-4 w-4" />
            <span>Activity Timeline</span>
          </button>
        </div>
      </BlurFade>

      {/* TAB CONTENT */}

      {/* 1. REVISION RECOMMENDATIONS TAB */}
      {activeTab === 'recommendations' && (
        <div className="space-y-6">
          {/* Filters Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-surface p-4 rounded-2xl border border-border/80">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-medium text-text-muted flex items-center gap-1.5">
                <Filter className="h-3.5 w-3.5" /> Priority:
              </span>
              {(['all', 'high', 'medium', 'low'] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setPriorityFilter(p)}
                  className={`text-xs px-2.5 py-1 rounded-lg transition-colors ${
                    priorityFilter === p
                      ? 'bg-surface-muted text-text-primary font-semibold border border-border'
                      : 'text-text-muted hover:text-text-secondary'
                  }`}
                >
                  {p.charAt(0).toUpperCase() + p.slice(1)}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-medium text-text-muted flex items-center gap-1.5">
                <ListFilter className="h-3.5 w-3.5" /> Status:
              </span>
              {(['active', 'all', 'completed', 'dismissed'] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
                  className={`text-xs px-2.5 py-1 rounded-lg transition-colors ${
                    statusFilter === s
                      ? 'bg-surface-muted text-text-primary font-semibold border border-border'
                      : 'text-text-muted hover:text-text-secondary'
                  }`}
                >
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Recommendations List */}
          {recsLoading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-32 w-full rounded-2xl" />
              ))}
            </div>
          ) : filteredRecs.length === 0 ? (
            <Card className="bg-surface border-border/80 p-12 text-center rounded-2xl">
              <Sparkles className="h-10 w-10 text-text-muted/50 mx-auto mb-3" />
              <h3 className="text-lg font-semibold text-text-primary">No recommendations found</h3>
              <p className="text-sm text-text-muted max-w-md mx-auto mt-1 mb-4">
                {recommendations && recommendations.length > 0
                  ? 'No recommendations match your active priority and status filters.'
                  : 'Complete quizzes in the Study Studio to assess your concept mastery and generate actionable revision guidance.'}
              </p>
              <div className="flex justify-center gap-3">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => generateRecsMutation.mutate()}
                  disabled={generateRecsMutation.isPending}
                  className="rounded-xl border-border/80"
                >
                  Generate Now
                </Button>
                <Link to={`/app/workspaces/${workspaceId}/study-studio`}>
                  <Button size="sm" className="rounded-xl">Go to Study Studio</Button>
                </Link>
              </div>
            </Card>
          ) : (
            <div className="space-y-4">
              {filteredRecs.map((rec, rIdx) => (
                <BlurFade key={rec.id} delay={0.05 + rIdx * 0.03}>
                  <Card
                    className={`bg-surface border rounded-2xl transition-all ${
                      rec.priority === 'high'
                        ? 'border-red-500/30 hover:border-red-500/60 hover:shadow-[0_0_15px_rgba(239,68,68,0.15)]'
                        : rec.priority === 'medium'
                        ? 'border-amber-500/30 hover:border-amber-500/60 hover:shadow-[0_0_15px_rgba(245,158,11,0.15)]'
                        : 'border-border/80 hover:border-primary/40'
                    }`}
                  >
                    <CardContent className="p-5 sm:p-6 space-y-4">
                      {/* Header Row */}
                      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <Badge variant={getPriorityBadgeVariant(rec.priority)} className="text-[11px] uppercase tracking-wider font-semibold">
                              {rec.priority} Priority
                            </Badge>
                            <Badge variant="outline" className="text-[11px] border-primary/25 text-primary bg-primary/5">
                              {formatRecType(rec.recommendation_type)}
                            </Badge>
                            <Badge variant="secondary" className="text-[11px] font-mono">
                              Status: {rec.status}
                            </Badge>
                          </div>
                          <h3 className="text-lg font-bold text-text-primary mt-1">
                            {rec.concept_name || 'Concept Revision'}
                          </h3>
                        </div>

                        {/* Status Lifecycle Actions */}
                        <div className="flex items-center gap-1.5 shrink-0">
                          {rec.status !== 'started' && rec.status !== 'completed' && (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-8 text-xs text-text-secondary hover:text-text-primary rounded-lg"
                              onClick={() => updateStatusMutation.mutate({ recId: rec.id, status: 'started' })}
                            >
                              <Play className="h-3.5 w-3.5 mr-1 text-primary" /> Start
                            </Button>
                          )}
                          {rec.status !== 'completed' && (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-8 text-xs text-text-secondary hover:text-emerald-400 rounded-lg"
                              onClick={() => updateStatusMutation.mutate({ recId: rec.id, status: 'completed' })}
                            >
                              <Check className="h-3.5 w-3.5 mr-1 text-emerald-400" /> Done
                            </Button>
                          )}
                          {rec.status !== 'dismissed' && (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-8 text-xs text-text-muted hover:text-text-secondary rounded-lg"
                              onClick={() => updateStatusMutation.mutate({ recId: rec.id, status: 'dismissed' })}
                            >
                              <X className="h-3.5 w-3.5" />
                            </Button>
                          )}
                        </div>
                      </div>

                      {/* Explanation */}
                      <p className="text-sm text-text-secondary leading-relaxed bg-surface-muted/40 p-3.5 rounded-xl border border-border/50">
                        {rec.explanation}
                      </p>

                      {/* Evidence Summary & BKT Metrics */}
                      <div className="flex flex-wrap items-center gap-4 text-xs text-text-muted pt-1">
                        <div>
                          <span className="font-semibold text-text-secondary">Questions Answered:</span>{' '}
                          <span className="font-mono">{rec.evidence_summary.questions_answered ?? 0}</span>
                        </div>
                        <div>
                          <span className="font-semibold text-text-secondary">Accuracy:</span>{' '}
                          <span className="font-mono">
                            {rec.evidence_summary.correct_rate !== undefined
                              ? `${rec.evidence_summary.correct_rate.toFixed(1)}%`
                              : 'N/A'}
                          </span>
                        </div>
                        {rec.evidence_summary.bkt_posterior_mastery !== undefined &&
                          rec.evidence_summary.bkt_posterior_mastery !== null && (
                            <div>
                              <span className="font-semibold text-text-secondary">Latent BKT Mastery:</span>{' '}
                              <span className="font-mono text-primary font-semibold">
                                {(rec.evidence_summary.bkt_posterior_mastery * 100).toFixed(0)}%
                              </span>
                              {rec.evidence_summary.bkt_model_qualified ? (
                                <Badge variant="outline" className="ml-1 text-[9px] py-0 px-1 text-emerald-400 border-emerald-400/30">
                                  Validated
                                </Badge>
                              ) : (
                                <Badge variant="outline" className="ml-1 text-[9px] py-0 px-1 text-amber-400 border-amber-400/30">
                                  Descriptive
                                </Badge>
                              )}
                            </div>
                          )}
                      </div>

                      {/* Linked Materials & Resource Action */}
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2 border-t border-border/80">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-medium text-text-muted">Linked Materials:</span>
                          {rec.linked_resources.revision_notes?.length ? (
                            <Badge variant="secondary" className="text-[11px] gap-1">
                              <BookOpen className="h-3 w-3 text-primary" />
                              {rec.linked_resources.revision_notes.length} Note(s)
                            </Badge>
                          ) : null}
                          {rec.linked_resources.flashcards?.length ? (
                            <Badge variant="secondary" className="text-[11px] gap-1">
                              <Layers className="h-3 w-3 text-accent" />
                              {rec.linked_resources.flashcards.length} Flashcard(s)
                            </Badge>
                          ) : null}
                          {rec.linked_resources.practice_questions?.length ? (
                            <Badge variant="secondary" className="text-[11px] gap-1">
                              <HelpCircle className="h-3 w-3 text-amber-400" />
                              {rec.linked_resources.practice_questions.length} Question(s)
                            </Badge>
                          ) : null}
                          {rec.linked_resources.source_chunks?.length ? (
                            <Badge variant="secondary" className="text-[11px] gap-1">
                              <GraduationCap className="h-3 w-3 text-violet-400" />
                              {rec.linked_resources.source_chunks.length} Source Excerpt(s)
                            </Badge>
                          ) : null}
                        </div>

                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() =>
                            setSelectedConcept({
                              id: rec.concept_id,
                              name: rec.concept_name || 'Concept Revision',
                            })
                          }
                          className="text-xs gap-1.5 rounded-xl self-end sm:self-auto"
                        >
                          <Eye className="h-3.5 w-3.5" />
                          <span>Inspect Study Resources</span>
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                </BlurFade>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 2. QUIZ PERFORMANCE & SCORE HISTORY TAB */}
      {activeTab === 'performance' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left 2 Cols: Score History Chart */}
            <Card className="lg:col-span-2 bg-surface border-border">
              <CardHeader>
                <CardTitle className="text-lg font-bold text-text-primary flex items-center justify-between">
                  <span>Score History Trend</span>
                  <Badge variant="outline" className="font-mono text-xs">
                    {scoreHistory?.total_points ?? 0} Attempts
                  </Badge>
                </CardTitle>
                <CardDescription className="text-xs">
                  Sequential quiz scores over time. Dotted line represents 70% passing benchmark.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {historyLoading ? (
                  <Skeleton className="h-64 w-full rounded-lg" />
                ) : !scoreHistory?.points || scoreHistory.points.length === 0 ? (
                  <div className="h-64 flex flex-col items-center justify-center text-center p-6 border border-dashed border-border rounded-lg">
                    <BarChart3 className="h-10 w-10 text-text-muted mb-2" />
                    <p className="text-sm font-medium text-text-primary">No quiz attempts recorded yet</p>
                    <p className="text-xs text-text-muted mt-1 mb-4">
                      Complete quizzes to populate your score trajectory and diagnostic trends.
                    </p>
                    <Link to={`/app/workspaces/${workspaceId}/study-studio`}>
                      <Button size="sm">Start a Quiz</Button>
                    </Link>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {/* SVG / Bar Chart Representation */}
                    <div className="relative h-60 w-full bg-surface-muted/30 rounded-lg p-4 border border-border flex items-end justify-between gap-2 overflow-x-auto">
                      {/* 70% Guideline */}
                      <div
                        className="absolute inset-x-0 border-b border-dashed border-accent/60 flex items-center justify-end px-2 pointer-events-none z-10"
                        style={{ bottom: '70%' }}
                      >
                        <span className="text-[10px] font-mono text-accent bg-surface px-1 rounded shadow-sm">
                          70% Pass Benchmark
                        </span>
                      </div>

                      {scoreHistory.points.map((pt, idx) => {
                        const heightPct = Math.max(pt.score_percentage, 6);
                        const isPassed = pt.score_percentage >= 70;
                        return (
                          <div
                            key={pt.attempt_id}
                            className="flex flex-col items-center flex-1 min-w-[36px] max-w-[60px] h-full justify-end group relative"
                          >
                            {/* Hover tooltip */}
                            <div className="absolute -top-12 opacity-0 group-hover:opacity-100 transition-opacity bg-popover text-popover-foreground text-[10px] p-2 rounded shadow-lg pointer-events-none whitespace-nowrap z-20 border border-border">
                              <p className="font-bold">{pt.score_percentage.toFixed(1)}%</p>
                              <p className="text-text-muted">
                                {pt.correct_count}/{pt.total_questions} correct
                              </p>
                              <p className="text-[9px] text-text-muted">{new Date(pt.attempt_date).toLocaleDateString()}</p>
                            </div>

                            {/* Bar */}
                            <div
                              className={`w-full rounded-t-sm transition-all group-hover:brightness-125 ${
                                isPassed ? 'bg-primary' : 'bg-red-500/70'
                              }`}
                              style={{ height: `${heightPct}%` }}
                            />

                            {/* Bottom Label */}
                            <span className="text-[9px] text-text-muted mt-1 font-mono truncate max-w-full">
                              #{idx + 1}
                            </span>
                          </div>
                        );
                      })}
                    </div>

                    <div className="flex items-center justify-between text-xs text-text-muted px-1">
                      <div className="flex items-center gap-4">
                        <span className="flex items-center gap-1.5">
                          <span className="h-2.5 w-2.5 rounded-full bg-primary" /> ≥ 70% Passed
                        </span>
                        <span className="flex items-center gap-1.5">
                          <span className="h-2.5 w-2.5 rounded-full bg-red-500/70" /> &lt; 70% Needs Review
                        </span>
                      </div>
                      <span>Chronological order</span>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Right 1 Col: Quiz Metrics Breakdown */}
            <Card className="bg-surface border-border">
              <CardHeader>
                <CardTitle className="text-lg font-bold text-text-primary">Performance Summary</CardTitle>
                <CardDescription className="text-xs">Aggregate score breakdown & accuracy metrics</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {perfLoading ? (
                  <Skeleton className="h-48 w-full rounded-lg" />
                ) : (
                  <div className="space-y-4">
                    <div className="flex justify-between items-center pb-2 border-b border-border">
                      <span className="text-xs text-text-muted">Highest Score</span>
                      <span className="text-sm font-bold text-emerald-400 font-mono">
                        {(quizPerformance?.highest_score ?? 0).toFixed(1)}%
                      </span>
                    </div>

                    <div className="flex justify-between items-center pb-2 border-b border-border">
                      <span className="text-xs text-text-muted">Most Recent Score</span>
                      <span className="text-sm font-bold text-primary font-mono">
                        {quizPerformance?.recent_score !== null && quizPerformance?.recent_score !== undefined
                          ? `${quizPerformance.recent_score.toFixed(1)}%`
                          : 'N/A'}
                      </span>
                    </div>

                    <div className="flex justify-between items-center pb-2 border-b border-border">
                      <span className="text-xs text-text-muted">Total Questions Answered</span>
                      <span className="text-sm font-semibold text-text-primary font-mono">
                        {quizPerformance?.total_answered ?? 0}
                      </span>
                    </div>

                    <div className="flex justify-between items-center pb-2 border-b border-border">
                      <span className="text-xs text-text-muted">Correct Answers</span>
                      <span className="text-sm font-semibold text-emerald-400 font-mono">
                        {quizPerformance?.total_correct ?? 0}
                      </span>
                    </div>

                    <div className="flex justify-between items-center pb-2 border-b border-border">
                      <span className="text-xs text-text-muted">Incorrect Answers</span>
                      <span className="text-sm font-semibold text-red-400 font-mono">
                        {quizPerformance?.total_incorrect ?? 0}
                      </span>
                    </div>

                    <div className="flex justify-between items-center">
                      <span className="text-xs text-text-muted">Unanswered Questions</span>
                      <span className="text-sm font-semibold text-text-muted font-mono">
                        {quizPerformance?.total_unanswered ?? 0}
                      </span>
                    </div>

                    <div className="pt-2">
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-text-muted">Overall Correct Rate</span>
                        <span className="font-semibold text-primary font-mono">
                          {(quizPerformance?.correct_rate ?? 0).toFixed(1)}%
                        </span>
                      </div>
                      <Progress value={quizPerformance?.correct_rate ?? 0} className="h-2" />
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* 3. CONCEPT MASTERY & ATTRIBUTION TAB */}
      {activeTab === 'concepts' && (
        <div className="space-y-6">
          {/* BKT Model Readiness Status Banner */}
          <div className="bg-surface border border-border p-4 rounded-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary border border-primary/20">
                <Brain className="h-5 w-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold text-text-primary">Bayesian Knowledge Tracing (BKT) Engine</h3>
                  {masteryOverview?.model_readiness_status === 'evaluation_passed' ? (
                    <Badge variant="outline" className="text-[10px] bg-emerald-500/10 text-emerald-400 border-emerald-500/30">
                      Validated Active Model
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="text-[10px] bg-amber-500/10 text-amber-400 border-amber-500/30">
                      Status: {masteryOverview?.model_readiness_status ?? 'Descriptive'}
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-text-muted mt-0.5">
                  Estimates latent knowledge probability P(L) using 4 BKT parameters (prior, transition, slip, guess).
                  {masteryOverview?.active_model_version && ` Active version: ${masteryOverview.active_model_version}.`}
                </p>
              </div>
            </div>

            <div className="text-xs text-text-muted shrink-0 text-right">
              <div>
                <span className="font-semibold text-text-secondary">Tracked Concepts:</span>{' '}
                {masteryOverview?.total_concepts_tracked ?? 0}
              </div>
              <p className="text-[10px] text-text-muted mt-0.5">Updated sequentially per learner interaction</p>
            </div>
          </div>

          {/* Concepts Table */}
          <Card className="bg-surface border-border">
            <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <CardTitle className="text-lg font-bold text-text-primary">Assessed Concept Attribution</CardTitle>
                <CardDescription className="text-xs">
                  Concept-level quiz performance, evidence sufficiency, and latent mastery estimation.
                </CardDescription>
              </div>

              {/* Search */}
              <div className="w-full sm:w-64">
                <input
                  type="text"
                  placeholder="Filter concepts..."
                  value={conceptSearch}
                  onChange={(e) => setConceptSearch(e.target.value)}
                  className="w-full rounded-md border border-border bg-surface-muted px-3 py-1.5 text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
            </CardHeader>
            <CardContent>
              {conceptsLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3, 4].map((i) => (
                    <Skeleton key={i} className="h-14 w-full rounded-md" />
                  ))}
                </div>
              ) : filteredConcepts.length === 0 ? (
                <div className="text-center py-12 text-text-muted">
                  <Brain className="h-10 w-10 mx-auto mb-2 opacity-50" />
                  <p className="text-sm font-medium">No concepts found</p>
                  <p className="text-xs text-text-muted mt-1">
                    {conceptSearch ? 'No concepts match your search.' : 'No concepts have been assessed yet. Take a quiz to begin.'}
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-border text-text-muted font-medium">
                        <th className="pb-3 font-semibold">Concept Name</th>
                        <th className="pb-3 font-semibold">Category</th>
                        <th className="pb-3 font-semibold text-center">Answered</th>
                        <th className="pb-3 font-semibold text-center">Correct Rate</th>
                        <th className="pb-3 font-semibold text-center">Evidence</th>
                        <th className="pb-3 font-semibold text-center">BKT Mastery</th>
                        <th className="pb-3 font-semibold text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {filteredConcepts.map((concept) => {
                        const hasBkt =
                          concept.bkt_mastery_probability !== null &&
                          concept.bkt_mastery_probability !== undefined;
                        const bktPct = hasBkt ? (concept.bkt_mastery_probability! * 100).toFixed(0) : null;

                        return (
                          <tr key={concept.concept_id} className="hover:bg-surface-muted/30 transition-colors">
                            <td className="py-3 font-medium text-text-primary">
                              {concept.concept_name}
                            </td>
                            <td className="py-3 text-text-muted font-mono">
                              {concept.category || 'general'}
                            </td>
                            <td className="py-3 text-center text-text-secondary font-mono">
                              {concept.questions_answered} ({concept.correct_answers}C / {concept.incorrect_answers}I)
                            </td>
                            <td className="py-3 text-center">
                              <div className="inline-flex items-center gap-2">
                                <span className="font-mono font-semibold text-text-primary">
                                  {concept.correct_rate.toFixed(0)}%
                                </span>
                                <div className="w-12 bg-surface-muted rounded-full h-1.5 overflow-hidden">
                                  <div
                                    className={`h-full ${
                                      concept.correct_rate >= 70 ? 'bg-emerald-400' : 'bg-red-400'
                                    }`}
                                    style={{ width: `${Math.min(concept.correct_rate, 100)}%` }}
                                  />
                                </div>
                              </div>
                            </td>
                            <td className="py-3 text-center">
                              {concept.evidence_sufficiency === 'sufficient' ? (
                                <Badge variant="outline" className="text-[10px] text-emerald-400 border-emerald-400/30">
                                  Sufficient (≥3)
                                </Badge>
                              ) : concept.evidence_sufficiency === 'sparse' ? (
                                <Badge variant="outline" className="text-[10px] text-amber-400 border-amber-400/30">
                                  Sparse (&lt;3)
                                </Badge>
                              ) : (
                                <Badge variant="secondary" className="text-[10px]">
                                  Unobserved
                                </Badge>
                              )}
                            </td>
                            <td className="py-3 text-center">
                              {hasBkt ? (
                                <div className="inline-flex items-center gap-1.5">
                                  <span className="font-mono font-semibold text-primary">{bktPct}%</span>
                                  <div className="w-10 bg-surface-muted rounded-full h-1.5 overflow-hidden">
                                    <div
                                      className="h-full bg-primary"
                                      style={{ width: `${Math.min(Number(bktPct), 100)}%` }}
                                    />
                                  </div>
                                </div>
                              ) : (
                                <span className="text-[10px] text-text-muted italic">Model Pending</span>
                              )}
                            </td>
                            <td className="py-3 text-right">
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() =>
                                  setSelectedConcept({
                                    id: concept.concept_id,
                                    name: concept.concept_name,
                                  })
                                }
                                className="h-7 text-xs text-primary hover:text-primary hover:bg-primary/10"
                              >
                                View Resources <ChevronRight className="h-3 w-3 ml-0.5" />
                              </Button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* 4. ACTIVITY TIMELINE TAB */}
      {activeTab === 'activity' && (
        <Card className="bg-surface border-border">
          <CardHeader>
            <CardTitle className="text-lg font-bold text-text-primary">Educational Interaction Timeline</CardTitle>
            <CardDescription className="text-xs">
              Chronological log of learner interactions, quiz submissions, and knowledge mapping events.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {timelineLoading ? (
              <div className="space-y-4">
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-16 w-full rounded-md" />
                ))}
              </div>
            ) : !activityTimeline?.events || activityTimeline.events.length === 0 ? (
              <div className="text-center py-12 text-text-muted">
                <Clock className="h-10 w-10 mx-auto mb-2 opacity-50" />
                <p className="text-sm font-medium">No activity recorded yet</p>
                <p className="text-xs text-text-muted mt-1">Interactions will stream here as you take quizzes.</p>
              </div>
            ) : (
              <div className="relative pl-6 space-y-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-border">
                {activityTimeline.events.map((event) => (
                  <div key={event.event_id} className="relative group">
                    {/* Bullet dot */}
                    <div className="absolute -left-6 top-1.5 h-3.5 w-3.5 rounded-full border-2 border-surface bg-primary group-hover:scale-125 transition-transform" />

                    <div className="bg-surface-muted/30 p-3 rounded-lg border border-border/50 hover:border-border transition-colors space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-text-primary">{event.title}</span>
                        <span className="text-[10px] text-text-muted font-mono">
                          {new Date(event.occurred_at).toLocaleString()}
                        </span>
                      </div>
                      <p className="text-xs text-text-secondary">{event.description}</p>
                      {event.concept_name && (
                        <div className="pt-1">
                          <Badge variant="outline" className="text-[10px] font-mono">
                            Concept: {event.concept_name}
                          </Badge>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Revision Resources Inspection Modal */}
      <ConceptResourcesModal
        workspaceId={workspaceId}
        conceptId={selectedConcept?.id ?? null}
        conceptName={selectedConcept?.name}
        onClose={() => setSelectedConcept(null)}
      />
    </div>
  );
};
