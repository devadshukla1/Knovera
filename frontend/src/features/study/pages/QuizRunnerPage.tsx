import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Clock,
  CheckCircle2,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Send,
  HelpCircle,
  FileText,
  Sparkles,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Input } from '@/components/ui/input';
import { BlurFade } from '@/components/magicui/BlurFade';
import { studyApi } from '../api/studyApi';
import { QuizAttempt, QuizQuestionPracticeItem } from '../types/study';

export const QuizRunnerPage: React.FC = () => {
  const { workspaceId, attemptId } = useParams<{ workspaceId: string; attemptId: string }>();
  const navigate = useNavigate();

  const [attempt, setAttempt] = useState<QuizAttempt | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);

  // Local answers state: questionId -> answer
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [submitting, setSubmitting] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [showHint, setShowHint] = useState(false);

  // Elapsed timer
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    if (!workspaceId || !attemptId) return;

    let isMounted = true;
    const fetchAttempt = async () => {
      try {
        setLoading(true);
        const data = await studyApi.getQuizAttempt(workspaceId, attemptId);
        if (!isMounted) return;

        if (data.status === 'evaluated') {
          // If already evaluated, redirect straight to results
          navigate(`/app/workspaces/${encodeURIComponent(workspaceId)}/study-studio/quiz/${encodeURIComponent(attemptId)}/results`);
          return;
        }

        setAttempt(data);
        setAnswers(data.saved_answers || {});

        // Record quiz_resumed / quiz_started interaction event
        studyApi.recordInteractionEvent(workspaceId, {
          event_type: 'quiz_resumed',
          attempt_id: attemptId,
          event_metadata: { client_agent: 'KnoveraUI/Web' },
        }).catch(() => {});

        // Compute elapsed time from started_at
        const start = new Date(data.started_at).getTime();
        const now = Date.now();
        const initialElapsed = Math.max(0, Math.floor((now - start) / 1000));
        setElapsedSeconds(initialElapsed);
      } catch (err: any) {
        if (isMounted) {
          setError(err?.message || 'Failed to load quiz attempt.');
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchAttempt();

    return () => {
      isMounted = false;
    };
  }, [workspaceId, attemptId, navigate]);

  // Timer interval
  useEffect(() => {
    if (loading || submitting || !attempt) return;
    const timer = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [loading, submitting, attempt]);

  // Log question presented / viewed when changing active index
  useEffect(() => {
    if (!workspaceId || !attemptId || !attempt) return;
    const currentQuestion = attempt.questions[currentIndex];
    if (currentQuestion) {
      studyApi.recordInteractionEvent(workspaceId, {
        event_type: 'question_viewed',
        attempt_id: attemptId,
        question_id: currentQuestion.id,
        event_metadata: { index: currentIndex, question_type: currentQuestion.question_type },
      }).catch(() => {});
    }
  }, [workspaceId, attemptId, currentIndex, attempt]);

  const formatTimer = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handleSelectAnswer = (questionId: string, questionType: string, value: any) => {
    const isRevision = answers[questionId] !== undefined;
    const updated = { ...answers, [questionId]: value };
    setAnswers(updated);

    // Asynchronously save answer to backend without blocking UI
    if (workspaceId && attemptId) {
      studyApi.saveQuizAnswers(workspaceId, attemptId, [
        {
          question_id: questionId,
          question_type: questionType,
          selected_answer: value,
        },
      ]).catch((err) => {
        console.warn('Failed to auto-save answer:', err);
      });

      // Record interaction event
      studyApi.recordInteractionEvent(workspaceId, {
        event_type: isRevision ? 'answer_revised' : 'answer_selected',
        attempt_id: attemptId,
        question_id: questionId,
        event_metadata: { question_type: questionType },
      }).catch(() => {});
    }
  };

  const handleSubmit = async () => {
    if (!workspaceId || !attemptId || !attempt) return;

    try {
      setSubmitting(true);
      const answerPayload = attempt.questions.map((q) => ({
        question_id: q.id,
        question_type: q.question_type,
        selected_answer: answers[q.id] !== undefined ? answers[q.id] : null,
      }));

      // Record quiz submission event
      studyApi.recordInteractionEvent(workspaceId, {
        event_type: 'quiz_submitted',
        attempt_id: attemptId,
        event_metadata: { total_answers: Object.keys(answers).length },
      }).catch(() => {});

      await studyApi.submitQuizAttempt(workspaceId, attemptId, answerPayload);
      navigate(`/app/workspaces/${encodeURIComponent(workspaceId)}/study-studio/quiz/${encodeURIComponent(attemptId)}/results`);
    } catch (err: any) {
      setError(err?.message || 'Failed to submit quiz attempt.');
      setSubmitting(false);
      setShowConfirmModal(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3">
        <div className="relative">
          <div className="h-10 w-10 rounded-full border-2 border-primary/20 border-t-primary animate-spin" />
          <Sparkles className="h-4 w-4 text-primary absolute inset-0 m-auto" />
        </div>
        <p className="text-xs font-mono text-text-muted">Loading interactive quiz session...</p>
      </div>
    );
  }

  if (error || !attempt) {
    return (
      <div className="p-8 max-w-2xl mx-auto text-center space-y-4">
        <AlertCircle className="h-10 w-10 text-destructive mx-auto" />
        <h2 className="text-xl font-bold text-text-primary">Unable to load quiz</h2>
        <p className="text-sm text-text-muted">{error || 'Quiz session not found.'}</p>
        <Button onClick={() => navigate(-1)} variant="outline" className="rounded-xl">
          Return to Study Studio
        </Button>
      </div>
    );
  }

  const currentQ: QuizQuestionPracticeItem = attempt.questions[currentIndex];
  const answeredCount = Object.keys(answers).filter(
    (k) => answers[k] !== undefined && answers[k] !== null && String(answers[k]).trim() !== ''
  ).length;
  const progressPercent = Math.round(((currentIndex + 1) / attempt.total_questions) * 100);

  return (
    <div className="flex flex-col min-h-[calc(100vh-4rem)] max-w-4xl mx-auto px-4 py-6 gap-6">
      {/* Top Header Bar */}
      <BlurFade delay={0.05}>
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-surface border border-border/80 p-4 sm:p-5 rounded-2xl shadow-sm">
          <div className="flex flex-col">
            <h1 className="text-base sm:text-lg font-bold text-text-primary truncate">{attempt.title}</h1>
            <div className="flex flex-wrap items-center gap-3 text-xs text-text-muted mt-1">
              <span className="flex items-center gap-1.5 font-mono text-primary bg-primary/10 px-2 py-0.5 rounded-md border border-primary/20">
                <Clock className="h-3 w-3" />
                {formatTimer(elapsedSeconds)}
              </span>
              <span>•</span>
              <span>
                Question <strong className="text-text-primary font-mono">{currentIndex + 1}</strong> of <span className="font-mono">{attempt.total_questions}</span>
              </span>
              <span>•</span>
              <span>
                <strong className="text-primary font-mono">{answeredCount}</strong> / <span className="font-mono">{attempt.total_questions}</span> Answered
              </span>
            </div>
          </div>

          <Button
            onClick={() => setShowConfirmModal(true)}
            className="bg-primary hover:bg-primary/90 text-primary-foreground flex items-center gap-2 self-end sm:self-auto rounded-xl py-2 px-4 shadow-sm transition-transform active:scale-95"
            size="sm"
            disabled={submitting}
          >
            <Send className="h-3.5 w-3.5" />
            <span>Finish & Submit</span>
          </Button>
        </div>
      </BlurFade>

      {/* Progress Bar */}
      <BlurFade delay={0.08}>
        <div className="w-full space-y-1">
          <Progress value={progressPercent} className="h-1.5 bg-surface-muted/60" />
        </div>
      </BlurFade>

      {/* Main Question Card */}
      <BlurFade delay={0.12}>
        <div className="flex flex-col bg-surface border border-border/80 rounded-2xl p-4 sm:p-8 shadow-sm gap-6 min-h-[380px]">
          {/* Meta badges & provenance */}
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="uppercase font-mono text-[11px] tracking-wider border-primary/25 text-primary bg-primary/5">
                {currentQ.question_type === 'mcq'
                  ? 'Multiple Choice'
                  : currentQ.question_type === 'true_false'
                  ? 'True / False'
                  : 'Fill in the Blank'}
              </Badge>
              <Badge variant="secondary" className="capitalize text-[11px]">
                {currentQ.difficulty}
              </Badge>
            </div>

            {currentQ.document_title && (
              <div className="flex items-center gap-1.5 text-xs text-text-muted font-mono truncate max-w-xs bg-surface-muted/60 px-2.5 py-1 rounded-md border border-border/60" title={currentQ.document_title}>
                <FileText className="h-3.5 w-3.5 shrink-0 text-primary" />
                <span className="truncate">{currentQ.document_title}</span>
                {currentQ.page_number && <span className="text-text-secondary">p. {currentQ.page_number}</span>}
              </div>
            )}
          </div>

          {/* Question Text */}
          <div className="my-auto py-3">
            <h2 className="text-lg sm:text-xl font-medium text-text-primary leading-relaxed">
              {currentQ.question_text}
            </h2>
          </div>

          {/* Input Modes */}
          <div className="pt-2">
            {/* MCQ Option Radio Cards */}
            {currentQ.question_type === 'mcq' && currentQ.options && (
              <div className="grid grid-cols-1 gap-3">
                {currentQ.options.map((opt, oIdx) => {
                  const isSelected = answers[currentQ.id] === opt.option_id;
                  const letterKey = ['A', 'B', 'C', 'D'][oIdx] || opt.option_id;
                  return (
                    <button
                      key={opt.option_id}
                      type="button"
                      onClick={() => handleSelectAnswer(currentQ.id, 'mcq', opt.option_id)}
                      aria-pressed={isSelected}
                      className={`flex items-center gap-4 p-4 rounded-xl border text-left transition-colors active:scale-[0.99] ${
                        isSelected
                          ? 'bg-primary/15 border-primary text-text-primary shadow-glow-sm ring-1 ring-primary'
                          : 'bg-surface-muted/30 border-border/80 hover:bg-surface-muted/70 hover:border-border text-text-secondary'
                      }`}
                    >
                      <div
                        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-bold font-mono transition-colors ${
                          isSelected
                            ? 'bg-primary text-primary-foreground shadow-sm'
                            : 'bg-surface-muted border border-border text-text-muted'
                        }`}
                      >
                        {letterKey}
                      </div>
                      <span className="text-sm font-medium flex-1">{opt.option_text}</span>
                    </button>
                  );
                })}
              </div>
            )}

            {/* True / False Intuitive Toggle */}
            {currentQ.question_type === 'true_false' && (
              <div className="grid grid-cols-2 gap-4 max-w-md mx-auto">
                <button
                  type="button"
                  onClick={() => handleSelectAnswer(currentQ.id, 'true_false', true)}
                  className={`flex flex-col items-center justify-center py-6 px-4 rounded-xl border transition-all ${
                    answers[currentQ.id] === true
                      ? 'bg-emerald-500/20 border-emerald-500 text-emerald-400 font-bold shadow-[0_0_15px_rgba(16,185,129,0.25)] ring-1 ring-emerald-500'
                      : 'bg-surface-muted/30 border-border/80 hover:bg-surface-muted text-text-secondary'
                  }`}
                >
                  <CheckCircle2 className="h-6 w-6 mb-2 text-emerald-400" />
                  <span className="text-base tracking-wider font-semibold">TRUE</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleSelectAnswer(currentQ.id, 'true_false', false)}
                  className={`flex flex-col items-center justify-center py-6 px-4 rounded-xl border transition-all ${
                    answers[currentQ.id] === false
                      ? 'bg-rose-500/20 border-rose-500 text-rose-400 font-bold shadow-[0_0_15px_rgba(244,63,94,0.25)] ring-1 ring-rose-500'
                      : 'bg-surface-muted/30 border-border/80 hover:bg-surface-muted text-text-secondary'
                  }`}
                >
                  <AlertCircle className="h-6 w-6 mb-2 text-rose-400" />
                  <span className="text-base tracking-wider font-semibold">FALSE</span>
                </button>
              </div>
            )}

            {/* Fill-in-the-Blank Text Input */}
            {currentQ.question_type === 'fill_blank' && (
              <div className="space-y-4 max-w-xl">
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-text-muted tracking-wide uppercase">
                    Your Answer:
                  </label>
                  <Input
                    value={answers[currentQ.id] || ''}
                    onChange={(e) => handleSelectAnswer(currentQ.id, 'fill_blank', e.target.value)}
                    placeholder="Type missing term or concept..."
                    className="bg-surface-muted/50 border-border/80 text-base py-5 px-4 font-medium rounded-xl"
                    autoFocus
                  />
                </div>

                {currentQ.hint && (
                  <div className="pt-1">
                    {!showHint ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowHint(true)}
                        className="text-xs text-text-muted hover:text-text-primary flex items-center gap-1.5 p-0 h-auto"
                      >
                        <HelpCircle className="h-3.5 w-3.5 text-primary" />
                        <span>Need a hint?</span>
                      </Button>
                    ) : (
                      <div className="bg-primary/10 border border-primary/20 rounded-xl p-3.5 text-xs text-text-secondary flex items-start gap-2.5 animate-in fade-in">
                        <HelpCircle className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                        <span>{currentQ.hint}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </BlurFade>

      {/* Navigation & Question Jump Strip */}
      <BlurFade delay={0.16}>
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2">
          <Button
            variant="outline"
            onClick={() => {
              setShowHint(false);
              setCurrentIndex((prev) => Math.max(0, prev - 1));
            }}
            disabled={currentIndex === 0}
            className="flex items-center gap-1.5 w-full sm:w-auto rounded-xl border-border/80"
          >
            <ChevronLeft className="h-4 w-4" />
            <span>Previous</span>
          </Button>

          {/* Numbered Jump Navigator */}
          <div className="flex items-center gap-1.5 flex-wrap justify-center max-w-md">
            {attempt.questions.map((q, idx) => {
              const isAnswered =
                answers[q.id] !== undefined &&
                answers[q.id] !== null &&
                String(answers[q.id]).trim() !== '';
              const isCurrent = idx === currentIndex;

              return (
                <button
                  key={q.id}
                  type="button"
                  onClick={() => {
                    setShowHint(false);
                    setCurrentIndex(idx);
                  }}
                  className={`h-8 w-8 rounded-lg text-xs font-mono font-medium transition-all ${
                    isCurrent
                      ? 'bg-primary text-primary-foreground font-bold shadow-glow-sm'
                      : isAnswered
                      ? 'bg-primary/20 border border-primary/40 text-primary'
                      : 'bg-surface border border-border/80 text-text-muted hover:bg-surface-muted'
                  }`}
                  title={`Question ${idx + 1} (${isAnswered ? 'Answered' : 'Unanswered'})`}
                >
                  {idx + 1}
                </button>
              );
            })}
          </div>

          <Button
            variant="outline"
            onClick={() => {
              setShowHint(false);
              setCurrentIndex((prev) => Math.min(attempt.total_questions - 1, prev + 1));
            }}
            disabled={currentIndex === attempt.total_questions - 1}
            className="flex items-center gap-1.5 w-full sm:w-auto rounded-xl border-border/80"
          >
            <span>Next</span>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </BlurFade>

      {/* Submission Confirmation Modal */}
      {showConfirmModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-150"
          onClick={() => setShowConfirmModal(false)}
        >
          <div
            className="flex flex-col bg-surface border border-border rounded-2xl p-6 sm:p-7 max-w-md w-full shadow-2xl space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-bold text-text-primary">Ready to Submit Quiz?</h3>

            <div className="text-sm text-text-muted space-y-2">
              <p>
                You have answered <strong className="text-primary font-mono">{answeredCount}</strong> out of{' '}
                <strong className="font-mono">{attempt.total_questions}</strong> questions.
              </p>
              {answeredCount < attempt.total_questions && (
                <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl text-amber-400 text-xs flex items-start gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>
                    You still have {attempt.total_questions - answeredCount} unanswered questions.
                    Unanswered questions will be scored as 0.
                  </span>
                </div>
              )}
              <p className="text-xs">Once submitted, your answers will be evaluated authoritatively against verified evidence.</p>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowConfirmModal(false)}
                disabled={submitting}
                className="rounded-xl border-border/80"
              >
                Continue Quiz
              </Button>
              <Button
                size="sm"
                onClick={handleSubmit}
                disabled={submitting}
                className="bg-primary text-primary-foreground hover:bg-primary/90 rounded-xl px-4"
              >
                {submitting ? 'Evaluating Answers...' : 'Confirm Submission'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
