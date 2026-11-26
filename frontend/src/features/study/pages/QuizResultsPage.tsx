import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  CheckCircle2,
  XCircle,
  AlertCircle,
  ArrowLeft,
  RotateCcw,
  Sparkles,
  FileText,
  Award,
  Layers,
  Target,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { BlurFade } from '@/components/magicui/BlurFade';
import { NumberTicker } from '@/components/magicui/NumberTicker';
import { studyApi } from '../api/studyApi';
import { ConceptPerformanceMetric, LearnerConceptMastery, QuizAttemptResultResponse } from '../types/study';

export const QuizResultsPage: React.FC = () => {
  const { workspaceId, attemptId } = useParams<{ workspaceId: string; attemptId: string }>();
  const navigate = useNavigate();

  const [results, setResults] = useState<QuizAttemptResultResponse | null>(null);
  const [conceptMetrics, setConceptMetrics] = useState<ConceptPerformanceMetric[]>([]);
  const [bktMasteries, setBktMasteries] = useState<Record<string, LearnerConceptMastery>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterMode, setFilterMode] = useState<'all' | 'incorrect' | 'correct'>('all');
  const [retaking, setRetaking] = useState(false);

  const handleRetake = async () => {
    if (!workspaceId || !attemptId) return;
    try {
      setRetaking(true);
      const newAttempt = await studyApi.retakeQuizAttempt(workspaceId, attemptId);
      navigate(`/app/workspaces/${encodeURIComponent(workspaceId)}/study-studio/quiz/${encodeURIComponent(newAttempt.id)}`);
    } catch (err: any) {
      console.error('Failed to retake quiz:', err);
      setError(err?.message || 'Failed to initiate quiz retake.');
    } finally {
      setRetaking(false);
    }
  };

  useEffect(() => {
    if (!workspaceId || !attemptId) return;

    let isMounted = true;
    const fetchResults = async () => {
      try {
        setLoading(true);
        const [resultsData, conceptData, masteryData] = await Promise.all([
          studyApi.getQuizResults(workspaceId, attemptId),
          studyApi.getAttemptConceptPerformance(workspaceId, attemptId).catch(() => null),
          studyApi.getMyConceptMasteries(workspaceId).catch(() => []),
        ]);
        if (isMounted) {
          setResults(resultsData);
          if (conceptData?.concepts) {
            setConceptMetrics(conceptData.concepts);
          }
          if (Array.isArray(masteryData)) {
            const map: Record<string, LearnerConceptMastery> = {};
            masteryData.forEach((m) => {
              map[m.concept_id] = m;
            });
            setBktMasteries(map);
          }
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err?.message || 'Failed to load quiz evaluation results.');
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchResults();

    return () => {
      isMounted = false;
    };
  }, [workspaceId, attemptId]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3">
        <div className="relative">
          <div className="h-10 w-10 rounded-full border-2 border-primary/20 border-t-primary animate-spin" />
          <Sparkles className="h-4 w-4 text-primary absolute inset-0 m-auto" />
        </div>
        <p className="text-xs font-mono text-text-muted">Loading verified evaluation report...</p>
      </div>
    );
  }

  if (error || !results) {
    return (
      <div className="p-8 max-w-2xl mx-auto text-center space-y-4">
        <AlertCircle className="h-10 w-10 text-danger mx-auto" />
        <h2 className="text-xl font-bold text-text-primary">Unable to load results</h2>
        <p className="text-sm text-text-muted">{error || 'Results not found.'}</p>
        <Button onClick={() => navigate(`/app/workspaces/${encodeURIComponent(workspaceId || '')}/study-studio`)} variant="outline" className="rounded-xl">
          Return to Study Studio
        </Button>
      </div>
    );
  }

  const filteredItems = results.results.filter((item) => {
    if (filterMode === 'correct') return item.is_correct;
    if (filterMode === 'incorrect') return !item.is_correct;
    return true;
  });

  const getScoreColor = (pct: number) => {
    if (pct >= 80) return 'text-emerald-400 border-emerald-500/40 bg-emerald-500/10 shadow-[0_0_20px_rgba(16,185,129,0.2)]';
    if (pct >= 50) return 'text-amber-400 border-amber-500/40 bg-amber-500/10 shadow-[0_0_20px_rgba(245,158,11,0.2)]';
    return 'text-rose-400 border-rose-500/40 bg-rose-500/10 shadow-[0_0_20px_rgba(244,63,94,0.2)]';
  };

  return (
    <div className="flex flex-col max-w-4xl mx-auto px-4 sm:px-7 py-7 gap-6">
      {/* Top Breadcrumb & Return */}
      <BlurFade delay={0.05}>
        <div className="flex items-center justify-between">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(`/app/workspaces/${encodeURIComponent(workspaceId || '')}/study-studio`)}
            className="text-text-muted hover:text-text-primary flex items-center gap-1.5 rounded-lg"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Back to Study Studio</span>
          </Button>

          <Badge variant="outline" className="font-mono text-xs border-primary/25 text-primary bg-primary/5">
            Evaluation Report
          </Badge>
        </div>
      </BlurFade>

      {/* Hero Score Summary Card */}
      <BlurFade delay={0.1}>
        <div className="flex flex-col md:flex-row items-center justify-between bg-surface border border-border/80 rounded-2xl p-6 sm:p-8 shadow-sm gap-6">
          <div className="flex flex-col items-center md:items-start text-center md:text-left gap-2">
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-semibold uppercase tracking-wider">
              <Award className="h-3.5 w-3.5" />
              <span>Quiz Completed</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-text-primary">{results.title}</h1>
            <p className="text-xs text-text-muted">
              Submitted at {results.submitted_at ? new Date(results.submitted_at).toLocaleString() : 'Just now'}
            </p>
          </div>

          {/* Score Ring / Metric */}
          <div className="flex items-center gap-6">
            <div
              className={`flex flex-col items-center justify-center h-28 w-28 rounded-2xl border-2 font-mono ${getScoreColor(
                results.score_percentage
              )}`}
            >
              <div className="flex items-baseline">
                <span className="text-3xl font-extrabold">
                  <NumberTicker value={results.score_percentage} />
                </span>
                <span className="text-sm font-semibold ml-0.5">%</span>
              </div>
              <span className="text-[10px] uppercase tracking-wider font-semibold opacity-80">Score</span>
            </div>

            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="bg-surface-muted/50 border border-border/80 rounded-xl p-3 min-w-[76px]">
                <span className="text-lg font-bold text-emerald-400 font-mono">
                  {results.correct_count}
                </span>
                <p className="text-[11px] text-text-muted">Correct</p>
              </div>
              <div className="bg-surface-muted/50 border border-border/80 rounded-xl p-3 min-w-[76px]">
                <span className="text-lg font-bold text-rose-400 font-mono">
                  {results.incorrect_count}
                </span>
                <p className="text-[11px] text-text-muted">Incorrect</p>
              </div>
              <div className="bg-surface-muted/50 border border-border/80 rounded-xl p-3 min-w-[76px]">
                <span className="text-lg font-bold text-text-muted font-mono">
                  {results.unanswered_count}
                </span>
                <p className="text-[11px] text-text-muted">Skipped</p>
              </div>
            </div>
          </div>
        </div>
      </BlurFade>

      {/* Concept Intelligence Breakdown (C9.3) */}
      {conceptMetrics.length > 0 && (
        <BlurFade delay={0.15}>
          <div className="flex flex-col bg-surface border border-border/80 rounded-2xl p-6 shadow-sm gap-4">
            <div className="flex items-center justify-between border-b border-border/80 pb-3">
              <div className="flex items-center gap-2">
                <Target className="h-4 w-4 text-primary" />
                <h2 className="text-base font-semibold text-text-primary">Concept Mastery Attribution</h2>
                <Badge variant="outline" className="text-[11px] font-mono border-primary/25 text-primary">
                  {conceptMetrics.length} Canonical Concepts
                </Badge>
              </div>
              <span className="text-xs text-text-muted hidden sm:inline">
                Attributed via Knowledge Graph & deterministic provenance
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {conceptMetrics.map((cm) => {
                const bkt = bktMasteries[cm.concept_id];
                const bktProb = bkt
                  ? Math.round(bkt.predicted_next_mastery_probability * 100)
                  : null;

                return (
                  <div
                    key={cm.concept_id}
                    className="flex flex-col justify-between p-3.5 bg-surface-muted/40 border border-border/80 rounded-xl gap-2.5"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex flex-col">
                        <span className="text-sm font-semibold text-text-primary line-clamp-1" title={cm.concept_name}>
                          {cm.concept_name}
                        </span>
                        <span className="text-[10px] text-text-muted uppercase font-mono tracking-wider">
                          {cm.category}
                        </span>
                      </div>
                      <Badge
                        variant="outline"
                        className={`font-mono text-xs shrink-0 ${
                          cm.correct_rate >= 80
                            ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'
                            : cm.correct_rate >= 50
                            ? 'text-amber-400 border-amber-500/30 bg-amber-500/10'
                            : 'text-rose-400 border-rose-500/30 bg-rose-500/10'
                        }`}
                      >
                        {cm.correct_rate}% Quiz
                      </Badge>
                    </div>

                    <div className="space-y-1">
                      <Progress value={cm.correct_rate} className="h-1.5" />
                      <div className="flex items-center justify-between text-[11px] text-text-muted font-mono pt-0.5">
                        <span>
                          {cm.correct_answers} / {cm.questions_answered} correct
                        </span>
                        {cm.unanswered > 0 && (
                          <span className="text-amber-400/80">{cm.unanswered} skipped</span>
                        )}
                      </div>
                    </div>

                    {/* BKT Model Inference Layer */}
                    {bkt && (
                      <div className="pt-2 border-t border-border/60 flex items-center justify-between text-xs font-mono">
                        <span className="text-[11px] text-text-muted">BKT Latent P(L):</span>
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-primary">{bktProb}%</span>
                          <Badge
                            variant="secondary"
                            className="text-[9px] px-1.5 py-0 uppercase"
                          >
                            {bkt.status === 'insufficient_data'
                              ? `Sparse (${bkt.observation_count} obs)`
                              : bkt.status}
                          </Badge>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </BlurFade>
      )}

      {/* Review Section */}
      <BlurFade delay={0.2}>
        <div className="flex flex-col gap-4">
          {/* Filter bar */}
          <div className="flex items-center justify-between flex-wrap gap-3 border-b border-border/80 pb-3">
            <div className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-primary" />
              <h2 className="text-base font-semibold text-text-primary">Question Review</h2>
              <Badge variant="secondary" className="text-xs font-mono">
                {filteredItems.length}
              </Badge>
            </div>

            <div className="flex items-center gap-1.5 bg-surface-muted/50 p-1 rounded-xl border border-border/80">
              <Button
                variant={filterMode === 'all' ? 'secondary' : 'ghost'}
                size="sm"
                onClick={() => setFilterMode('all')}
                className="text-xs h-7 px-2.5 rounded-lg"
              >
                All ({results.total_questions})
              </Button>
              <Button
                variant={filterMode === 'incorrect' ? 'secondary' : 'ghost'}
                size="sm"
                onClick={() => setFilterMode('incorrect')}
                className="text-xs h-7 px-2.5 text-rose-400 hover:text-rose-300 rounded-lg"
              >
                Missed ({results.incorrect_count + results.unanswered_count})
              </Button>
              <Button
                variant={filterMode === 'correct' ? 'secondary' : 'ghost'}
                size="sm"
                onClick={() => setFilterMode('correct')}
                className="text-xs h-7 px-2.5 text-emerald-400 hover:text-emerald-300 rounded-lg"
              >
                Correct ({results.correct_count})
              </Button>
            </div>
          </div>

          {/* Question Review Cards */}
          <div className="space-y-4">
            {filteredItems.map((item, idx) => {
              const isUnanswered = item.learner_answer === null || item.learner_answer === undefined || String(item.learner_answer).trim() === '';

              return (
                <div
                  key={item.question_id}
                  className={`flex flex-col bg-surface border rounded-2xl p-6 gap-4 shadow-sm transition-all ${
                    item.is_correct
                      ? 'border-emerald-500/30 hover:border-emerald-500/50'
                      : isUnanswered
                      ? 'border-amber-500/30 hover:border-amber-500/50'
                      : 'border-rose-500/30 hover:border-rose-500/50'
                  }`}
                >
                  {/* Header row */}
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono font-bold text-text-muted">
                        #{idx + 1}
                      </span>
                      <Badge variant="outline" className="text-[10px] uppercase font-mono">
                        {item.question_type}
                      </Badge>
                      <Badge variant="secondary" className="text-[10px] capitalize">
                        {item.difficulty}
                      </Badge>
                    </div>

                    <div className="flex items-center gap-1.5">
                      {item.is_correct ? (
                        <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-400 bg-emerald-500/10 px-2.5 py-0.5 rounded-full border border-emerald-500/20">
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          Correct
                        </span>
                      ) : isUnanswered ? (
                        <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-400 bg-amber-500/10 px-2.5 py-0.5 rounded-full border border-amber-500/20">
                          <AlertCircle className="h-3.5 w-3.5" />
                          Unanswered
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-xs font-medium text-rose-400 bg-rose-500/10 px-2.5 py-0.5 rounded-full border border-rose-500/20">
                          <XCircle className="h-3.5 w-3.5" />
                          Incorrect
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Question Stem */}
                  <p className="text-base font-medium text-text-primary leading-relaxed">
                    {item.question_text}
                  </p>

                  {/* Comparison Box: Your Answer vs Correct Answer */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                    <div className="bg-surface-muted/60 border border-border/80 rounded-xl p-3.5">
                      <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider block mb-1">
                        Your Answer
                      </span>
                      <p
                        className={`text-sm font-medium ${
                          item.is_correct
                            ? 'text-emerald-400'
                            : isUnanswered
                            ? 'text-text-muted italic'
                            : 'text-rose-400'
                        }`}
                      >
                        {isUnanswered ? 'No answer given' : String(item.learner_answer)}
                      </p>
                    </div>

                    <div className="bg-primary/10 border border-primary/20 rounded-xl p-3.5">
                      <span className="text-[10px] font-semibold text-primary uppercase tracking-wider block mb-1">
                        Verified Answer
                      </span>
                      <p className="text-sm font-medium text-text-primary">
                        {String(item.correct_answer)}
                      </p>
                    </div>
                  </div>

                  {/* Factual Explanation */}
                  {item.explanation && (
                    <div className="bg-surface-muted/30 border border-border/60 rounded-xl p-4 text-xs text-text-secondary leading-relaxed">
                      <strong className="text-text-primary block mb-1 font-semibold">
                        Explanation:
                      </strong>
                      {item.explanation}
                    </div>
                  )}

                  {/* Source Citations */}
                  {item.source_references && item.source_references.length > 0 && (
                    <div className="flex items-center gap-2 pt-1 text-[11px] text-text-muted font-mono truncate">
                      <FileText className="h-3.5 w-3.5 shrink-0 text-primary" />
                      <span>
                        {item.source_references[0].document_title}
                        {item.source_references[0].page_number
                          ? ` (p. ${item.source_references[0].page_number})`
                          : ''}
                      </span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </BlurFade>

      {/* Bottom Action Footer */}
      <BlurFade delay={0.25}>
        <div className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-border/80">
          <Button
            variant="outline"
            onClick={() => navigate(`/app/workspaces/${encodeURIComponent(workspaceId || '')}/study-studio`)}
            className="rounded-xl border-border/80"
          >
            Study Studio Home
          </Button>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              disabled={retaking}
              onClick={handleRetake}
              className="flex items-center gap-2 border-primary/30 text-primary hover:bg-primary/10 rounded-xl"
            >
              <RotateCcw className={`h-4 w-4 ${retaking ? 'animate-spin' : ''}`} />
              <span>{retaking ? 'Cloning Quiz...' : 'Retake Quiz'}</span>
            </Button>

            <Button
              onClick={() => navigate(`/app/workspaces/${encodeURIComponent(workspaceId || '')}/study-studio/quiz-setup`)}
              className="bg-primary hover:bg-primary/90 text-primary-foreground flex items-center gap-2 rounded-xl"
            >
              <Sparkles className="h-4 w-4" />
              <span>New Quiz</span>
            </Button>
          </div>
        </div>
      </BlurFade>
    </div>
  );
};
