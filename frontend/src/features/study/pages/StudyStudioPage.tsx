import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  GraduationCap,
  Play,
  BookOpen,
  Sparkles,
  Plus,
  Clock,
  ChevronRight,
  FileText,
  TrendingUp,
  RotateCcw,
  Search,
  Award,
  CheckCircle2,
  ArrowUpRight,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { BlurFade } from '@/components/magicui/BlurFade';
import { NumberTicker } from '@/components/magicui/NumberTicker';
import { studyApi } from '../api/studyApi';
import {
  Flashcard,
  QuizAttemptSummary,
  QuizHistorySummary,
  QuizHistoryTrendPoint,
  RevisionNote,
} from '../types/study';
import { FlashcardViewerModal } from '../components/FlashcardViewerModal';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';

export const StudyStudioPage: React.FC = () => {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<'quizzes' | 'flashcards' | 'notes'>('quizzes');
  const [loading, setLoading] = useState(true);

  // Data states
  const [attempts, setAttempts] = useState<QuizAttemptSummary[]>([]);
  const [historySummary, setHistorySummary] = useState<QuizHistorySummary | null>(null);
  const [trends, setTrends] = useState<QuizHistoryTrendPoint[]>([]);
  const [statusFilter, setStatusFilter] = useState<'all' | 'evaluated' | 'in_progress'>('all');
  const [searchFilter, setSearchFilter] = useState('');
  const [sortBy, setSortBy] = useState<'created_at' | 'score_percentage'>('created_at');
  const [retakingId, setRetakingId] = useState<string | null>(null);

  const [flashcards, setFlashcards] = useState<Flashcard[]>([]);
  const [notes, setNotes] = useState<RevisionNote[]>([]);

  // Flashcard modal
  const [isViewerOpen, setIsViewerOpen] = useState(false);
  const [selectedCardIdx, setSelectedCardIdx] = useState(0);

  // Generation status
  const [generating, setGenerating] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    if (!workspaceId) return;

    let isMounted = true;
    const loadStudioData = async () => {
      try {
        setLoading(true);
        const [attemptsRes, flashcardsRes, notesRes, summaryRes, trendsRes] = await Promise.all([
          studyApi.listQuizHistory(workspaceId, {
            status: statusFilter === 'all' ? undefined : statusFilter,
            search: searchFilter || undefined,
            sort_by: sortBy,
            limit: 30,
          }),
          studyApi.listFlashcards(workspaceId, { limit: 50 }),
          studyApi.listRevisionNotes(workspaceId, { limit: 20 }),
          studyApi.getQuizHistorySummary(workspaceId).catch(() => null),
          studyApi.getQuizHistoryTrends(workspaceId).catch(() => ({ trends: [] })),
        ]);

        if (isMounted) {
          setAttempts(attemptsRes.items || []);
          setFlashcards(flashcardsRes.items || []);
          setNotes(notesRes.items || []);
          if (summaryRes) setHistorySummary(summaryRes);
          if (trendsRes) setTrends(trendsRes.trends || []);
        }
      } catch (err) {
        console.error('Failed to load study studio data:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    loadStudioData();

    return () => {
      isMounted = false;
    };
  }, [workspaceId, statusFilter, searchFilter, sortBy]);

  const handleRetakeAttempt = async (e: React.MouseEvent, attemptId: string) => {
    e.stopPropagation();
    if (!workspaceId) return;
    try {
      setRetakingId(attemptId);
      const newAttempt = await studyApi.retakeQuizAttempt(workspaceId, attemptId);
      navigate(`/app/workspaces/${encodeURIComponent(workspaceId)}/study-studio/quiz/${encodeURIComponent(newAttempt.id)}`);
    } catch (err: any) {
      console.error('Failed to retake quiz:', err);
      setActionError(err?.message || 'Failed to retake quiz. Please ensure documents are indexed.');
    } finally {
      setRetakingId(null);
    }
  };

  const handleGenerateFlashcards = async () => {
    if (!workspaceId) return;
    try {
      setGenerating(true);
      await studyApi.generateFlashcards(workspaceId, { count: 8 });
      const refreshed = await studyApi.listFlashcards(workspaceId, { limit: 50 });
      setFlashcards(refreshed.items || []);
    } catch (err) {
      console.error('Failed to generate flashcards:', err);
    } finally {
      setGenerating(false);
    }
  };

  const handleGenerateRevisionNotes = async () => {
    if (!workspaceId) return;
    try {
      setGenerating(true);
      await studyApi.generateRevisionNotes(workspaceId);
      const refreshed = await studyApi.listRevisionNotes(workspaceId, { limit: 20 });
      setNotes(refreshed.items || []);
    } catch (err) {
      console.error('Failed to generate notes:', err);
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3">
        <div className="relative">
          <div className="h-10 w-10 rounded-full border-2 border-primary/20 border-t-primary animate-spin" />
          <Sparkles className="h-4 w-4 text-primary absolute inset-0 m-auto" />
        </div>
        <p className="text-xs font-mono text-text-muted">Loading Study Studio intelligence...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen max-w-6xl mx-auto px-4 sm:px-6 py-8 gap-8">
      {/* Studio Header */}
      <BlurFade delay={0.05}>
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-border/80 pb-6">
          <div className="space-y-1.5">
            <div className="inline-flex items-center gap-2 text-primary text-xs font-semibold uppercase tracking-wider">
              <GraduationCap className="h-3.5 w-3.5" />
              <span>Learn with your sources</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-text-primary">
              Study Studio
            </h1>
            <p className="text-sm text-text-muted max-w-2xl">
              Build understanding with quizzes, flashcards, and revision notes from your sources.
            </p>
          </div>

          <Button
            onClick={() => navigate(`/app/workspaces/${encodeURIComponent(workspaceId || '')}/study-studio/quiz-setup`)}
            className="bg-primary hover:bg-primary/90 text-primary-foreground flex items-center gap-2 py-5 px-5 rounded-xl shadow-md font-semibold self-start sm:self-auto transition-transform active:scale-95"
          >
            <Play className="h-4 w-4 fill-current" />
            <span>Start Interactive Quiz</span>
          </Button>
        </div>
      </BlurFade>

      {/* Tabs Bar */}
      <BlurFade delay={0.1}>
        <div className="flex items-center gap-2 border-b border-border/80 overflow-x-auto pb-1" aria-label="Study views">
          {[
            { id: 'quizzes', label: 'Interactive Quizzes', icon: GraduationCap, count: attempts.length },
            { id: 'flashcards', label: 'Flashcards', icon: BookOpen, count: flashcards.length },
            { id: 'notes', label: 'Revision Notes', icon: FileText, count: notes.length },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                aria-pressed={isActive}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold rounded-t-lg transition-all border-b-2 whitespace-nowrap ${
                  isActive
                    ? 'border-primary text-primary bg-primary/10'
                    : 'border-transparent text-text-muted hover:text-text-primary hover:bg-surface-muted/50'
                }`}
              >
                <Icon className="h-4 w-4" />
                <span>{tab.label}</span>
                {tab.count > 0 && (
                  <Badge variant={isActive ? 'default' : 'secondary'} className="text-[10px] px-1.5 py-0 font-mono">
                    {tab.count}
                  </Badge>
                )}
              </button>
            );
          })}
        </div>
      </BlurFade>

      {/* TAB CONTENT: Quizzes */}
      {activeTab === 'quizzes' && (
        <div className="space-y-6">
          {/* Performance Analytics Summary */}
          {historySummary && (
            <BlurFade delay={0.15}>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <Card className="p-4 flex flex-col justify-between bg-surface-muted/40 border-border/80 hover:border-primary/40 transition-colors">
                  <div className="flex items-center justify-between text-text-muted mb-2">
                    <span className="text-xs font-medium">Average Score</span>
                    <Award className="h-4 w-4 text-primary" />
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-2xl sm:text-3xl font-bold font-mono text-text-primary">
                      <NumberTicker value={Math.round(historySummary.average_score)} />
                    </span>
                    <span className="text-sm font-mono text-text-muted">%</span>
                  </div>
                  <span className="text-[10px] text-text-muted mt-1">Across all completed quizzes</span>
                </Card>

                <Card className="p-4 flex flex-col justify-between bg-surface-muted/40 border-border/80 hover:border-emerald-500/40 transition-colors">
                  <div className="flex items-center justify-between text-text-muted mb-2">
                    <span className="text-xs font-medium">Accuracy Rate</span>
                    <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-2xl sm:text-3xl font-bold font-mono text-emerald-400">
                      <NumberTicker value={Math.round(historySummary.overall_correct_rate)} />
                    </span>
                    <span className="text-sm font-mono text-emerald-400/70">%</span>
                  </div>
                  <span className="text-[10px] text-text-muted mt-1">
                    {historySummary.total_correct_answers} of {historySummary.total_questions_answered} questions
                  </span>
                </Card>

                <Card className="p-4 flex flex-col justify-between bg-surface-muted/40 border-border/80 hover:border-primary/40 transition-colors">
                  <div className="flex items-center justify-between text-text-muted mb-2">
                    <span className="text-xs font-medium">Completed</span>
                    <GraduationCap className="h-4 w-4 text-primary" />
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-2xl sm:text-3xl font-bold font-mono text-text-primary">
                      <NumberTicker value={historySummary.completed_attempts} />
                    </span>
                  </div>
                  <span className="text-[10px] text-text-muted mt-1">Evaluated attempts</span>
                </Card>

                <Card className="p-4 flex flex-col justify-between bg-surface-muted/40 border-border/80 hover:border-amber-400/40 transition-colors">
                  <div className="flex items-center justify-between text-text-muted mb-2">
                    <span className="text-xs font-medium">In Progress</span>
                    <Clock className="h-4 w-4 text-amber-400" />
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="text-2xl sm:text-3xl font-bold font-mono text-amber-400">
                      <NumberTicker value={historySummary.in_progress_attempts} />
                    </span>
                  </div>
                  <span className="text-[10px] text-text-muted mt-1">Active sessions</span>
                </Card>
              </div>
            </BlurFade>
          )}

          {/* Chronological Score Trends */}
          {trends && trends.length > 0 && (
            <BlurFade delay={0.2}>
              <div className="bg-surface border border-border/80 rounded-2xl p-5 shadow-sm space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="h-4 w-4 text-primary" />
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                      Score Trajectory
                    </h3>
                  </div>
                  <span className="text-xs font-mono text-text-muted">{trends.length} recorded attempts</span>
                </div>

                <div className="flex items-end gap-2 h-20 pt-2 overflow-x-auto pb-1">
                  {trends.map((pt) => {
                    const heightPct = Math.max(15, Math.min(100, pt.score_percentage));
                    const isHigh = pt.score_percentage >= 80;
                    const isMid = pt.score_percentage >= 50 && pt.score_percentage < 80;
                    return (
                      <div
                        key={pt.attempt_id}
                        title={`${pt.title}: ${pt.score_percentage}%`}
                        className="flex-1 min-w-[32px] max-w-[52px] flex flex-col items-center gap-1 group relative cursor-pointer"
                        onClick={() =>
                          navigate(
                            `/app/workspaces/${encodeURIComponent(workspaceId || '')}/study-studio/quiz/${encodeURIComponent(
                              pt.attempt_id
                            )}/results`
                          )
                        }
                      >
                        <span className="text-[10px] font-mono text-text-muted group-hover:text-primary transition-colors">
                          {Math.round(pt.score_percentage)}%
                        </span>
                        <div className="w-full bg-surface-muted/60 rounded-t-md overflow-hidden flex flex-col justify-end h-12">
                          <div
                            style={{ height: `${heightPct}%` }}
                            className={`w-full transition-all duration-300 rounded-t-md ${
                              isHigh
                                ? 'bg-emerald-500/80 group-hover:bg-emerald-400 group-hover:shadow-[0_0_12px_rgba(16,185,129,0.5)]'
                                : isMid
                                ? 'bg-amber-500/80 group-hover:bg-amber-400 group-hover:shadow-[0_0_12px_rgba(245,158,11,0.5)]'
                                : 'bg-rose-500/80 group-hover:bg-rose-400 group-hover:shadow-[0_0_12px_rgba(244,63,94,0.5)]'
                            }`}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </BlurFade>
          )}

          {/* Filtering and Actions Bar */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-2">
            <div className="flex items-center gap-2 flex-wrap flex-1">
              {/* Search */}
              <div className="relative min-w-[200px] max-w-xs">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-text-muted" />
                <input
                  type="text"
                  placeholder="Search quizzes..."
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  className="w-full bg-surface-muted/50 border border-border/80 rounded-xl pl-9 pr-3 py-2 text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-primary transition-colors"
                />
              </div>

              {/* Status Filters */}
              <div className="flex items-center bg-surface-muted/50 p-1 rounded-xl border border-border/80 text-xs">
                {(['all', 'evaluated', 'in_progress'] as const).map((s) => (
                  <button
                    key={s}
                    onClick={() => setStatusFilter(s)}
                    className={`px-3 py-1 rounded-lg capitalize transition-all ${
                      statusFilter === s
                        ? 'bg-surface text-text-primary font-semibold shadow-xs'
                        : 'text-text-muted hover:text-text-primary'
                    }`}
                  >
                    {s === 'all' ? 'All' : s === 'evaluated' ? 'Completed' : 'In Progress'}
                  </button>
                ))}
              </div>

              {/* Sorting */}
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as any)}
                className="bg-surface-muted/50 border border-border/80 rounded-xl px-3 py-2 text-xs text-text-muted focus:outline-none focus:border-primary transition-colors"
              >
                <option value="created_at">Most Recent</option>
                <option value="score_percentage">Highest Score</option>
              </select>
            </div>

            <Button
              size="sm"
              onClick={() => navigate(`/app/workspaces/${encodeURIComponent(workspaceId || '')}/study-studio/quiz-setup`)}
              className="bg-primary hover:bg-primary/90 text-primary-foreground text-xs flex items-center gap-1.5 shrink-0 rounded-xl py-2 px-3.5"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>New Quiz</span>
            </Button>
          </div>

          {/* List of Attempts */}
          {attempts.length === 0 ? (
            <BlurFade delay={0.25}>
              <div className="bg-surface border border-border border-dashed rounded-2xl p-10 text-center space-y-4">
                <div className="h-12 w-12 rounded-2xl bg-surface-muted/70 flex items-center justify-center mx-auto text-text-muted/60">
                  <GraduationCap className="h-6 w-6" />
                </div>
                <div className="space-y-1">
                  <h3 className="text-base font-semibold text-text-primary">No quiz attempts found</h3>
                  <p className="text-xs text-text-muted max-w-sm mx-auto">
                    {searchFilter || statusFilter !== 'all'
                      ? 'No quiz sessions matched your search or filter criteria.'
                      : 'Take your first interactive quiz based on verified document chunks in this workspace.'}
                  </p>
                </div>
                <Button
                  onClick={() => navigate(`/app/workspaces/${encodeURIComponent(workspaceId || '')}/study-studio/quiz-setup`)}
                  className="bg-primary text-primary-foreground hover:bg-primary/90 text-xs rounded-xl"
                >
                  Launch First Quiz
                </Button>
              </div>
            </BlurFade>
          ) : (
            <div className="grid grid-cols-1 gap-3">
              {attempts.map((att, idx) => (
                <BlurFade key={att.id} delay={0.1 + idx * 0.03}>
                  <div
                    onClick={() => {
                      if (att.status === 'evaluated') {
                        navigate(`/app/workspaces/${encodeURIComponent(workspaceId || '')}/study-studio/quiz/${encodeURIComponent(att.id)}/results`);
                      } else {
                        navigate(`/app/workspaces/${encodeURIComponent(workspaceId || '')}/study-studio/quiz/${encodeURIComponent(att.id)}`);
                      }
                    }}
                    className="flex items-center justify-between bg-surface border border-border/80 hover:border-primary/50 hover:shadow-glow-sm rounded-xl p-4 transition-all cursor-pointer group"
                  >
                    <div className="flex items-center gap-4">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-surface-muted/60 border border-border/80 text-primary group-hover:bg-primary/10 group-hover:border-primary/30 transition-all">
                        <GraduationCap className="h-5 w-5" />
                      </div>
                      <div>
                        <h4 className="text-sm font-semibold text-text-primary group-hover:text-primary transition-colors">
                          {att.title}
                        </h4>
                        <div className="flex items-center gap-2 text-xs text-text-muted mt-0.5">
                          <span className="flex items-center gap-1 font-mono">
                            <Clock className="h-3 w-3" />
                            {new Date(att.started_at).toLocaleDateString()}
                          </span>
                          <span>•</span>
                          <span>{att.total_questions} Questions</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      {att.status === 'evaluated' ? (
                        <Badge className="bg-emerald-500/10 text-emerald-400 border-emerald-500/25 font-mono text-xs px-2 py-0.5">
                          {att.score_percentage}%
                        </Badge>
                      ) : (
                        <Badge variant="secondary" className="text-xs font-medium px-2 py-0.5">
                          In Progress
                        </Badge>
                      )}

                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={retakingId === att.id}
                        onClick={(e) => handleRetakeAttempt(e, att.id)}
                        title="Retake this quiz"
                        className="h-8 px-2 text-xs text-text-muted hover:text-primary hover:bg-primary/10 rounded-lg flex items-center gap-1"
                      >
                        <RotateCcw className={`h-3.5 w-3.5 ${retakingId === att.id ? 'animate-spin' : ''}`} />
                        <span className="hidden sm:inline">Retake</span>
                      </Button>

                      <ChevronRight className="h-4 w-4 text-text-muted group-hover:text-text-primary transition-transform group-hover:translate-x-0.5" />
                    </div>
                  </div>
                </BlurFade>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB CONTENT: Flashcards */}
      {activeTab === 'flashcards' && (
        <div className="space-y-6">
          <BlurFade delay={0.15}>
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-text-primary">Flashcard Decks</h2>
                <p className="text-xs text-text-muted">Active recall cards covering formulas, definitions, and concepts.</p>
              </div>
              <div className="flex items-center gap-2">
                {flashcards.length > 0 && (
                  <Button
                    size="sm"
                    onClick={() => {
                      setSelectedCardIdx(0);
                      setIsViewerOpen(true);
                    }}
                    className="bg-primary text-primary-foreground hover:bg-primary/90 text-xs flex items-center gap-1.5 rounded-xl py-2 px-3.5"
                  >
                    <Play className="h-3.5 w-3.5 fill-current" />
                    <span>Review Deck</span>
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleGenerateFlashcards}
                  disabled={generating}
                  className="text-xs flex items-center gap-1.5 rounded-xl border-border/80"
                >
                  <Sparkles className={`h-3.5 w-3.5 text-primary ${generating ? 'animate-spin' : ''}`} />
                  <span>{generating ? 'Generating...' : 'Generate Cards'}</span>
                </Button>
              </div>
            </div>
          </BlurFade>

          {flashcards.length === 0 ? (
            <BlurFade delay={0.2}>
              <div className="bg-surface border border-border border-dashed rounded-2xl p-10 text-center space-y-4">
                <div className="h-12 w-12 rounded-2xl bg-surface-muted/70 flex items-center justify-center mx-auto text-text-muted/60">
                  <BookOpen className="h-6 w-6" />
                </div>
                <div className="space-y-1">
                  <h3 className="text-base font-semibold text-text-primary">No flashcards generated yet</h3>
                  <p className="text-xs text-text-muted max-w-sm mx-auto">
                    Automatically synthesize concise active-recall cards from your workspace documents.
                  </p>
                </div>
                <Button
                  onClick={handleGenerateFlashcards}
                  disabled={generating}
                  className="bg-primary text-primary-foreground hover:bg-primary/90 text-xs rounded-xl"
                >
                  {generating ? 'Generating...' : 'Synthesize Deck'}
                </Button>
              </div>
            </BlurFade>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {flashcards.map((card, idx) => (
                <BlurFade key={card.id} delay={0.1 + idx * 0.03}>
                  <div
                    onClick={() => {
                      setSelectedCardIdx(idx);
                      setIsViewerOpen(true);
                    }}
                    className="flex flex-col justify-between bg-surface border border-border/80 hover:border-primary/60 hover:shadow-glow-sm rounded-2xl p-5 gap-4 transition-all cursor-pointer group"
                  >
                    <div className="flex items-center justify-between">
                      <Badge variant="outline" className="text-[10px] uppercase font-mono border-primary/25 text-primary bg-primary/5">
                        {card.card_type}
                      </Badge>
                      <Badge variant="secondary" className="text-[10px] capitalize">
                        {card.difficulty}
                      </Badge>
                    </div>

                    <p className="text-sm font-medium text-text-primary group-hover:text-primary transition-colors line-clamp-3">
                      {card.front}
                    </p>

                    <div className="flex items-center justify-between pt-3 border-t border-border/60 text-[11px] text-text-muted">
                      <span className="truncate max-w-[150px]">{card.topic || 'General'}</span>
                      <span className="text-primary font-medium flex items-center gap-1 group-hover:underline">
                        Flip Card <ArrowUpRight className="h-3 w-3" />
                      </span>
                    </div>
                  </div>
                </BlurFade>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB CONTENT: Revision Notes */}
      {activeTab === 'notes' && (
        <div className="space-y-6">
          <BlurFade delay={0.15}>
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-text-primary">Revision Notes</h2>
                <p className="text-xs text-text-muted">Structured notes, formulas, and key concepts.</p>
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={handleGenerateRevisionNotes}
                disabled={generating}
                className="text-xs flex items-center gap-1.5 rounded-xl border-border/80"
              >
                <Sparkles className={`h-3.5 w-3.5 text-primary ${generating ? 'animate-spin' : ''}`} />
                <span>{generating ? 'Generating...' : 'Generate New Notes'}</span>
              </Button>
            </div>
          </BlurFade>

          {notes.length === 0 ? (
            <BlurFade delay={0.2}>
              <div className="bg-surface border border-border border-dashed rounded-2xl p-10 text-center space-y-4">
                <div className="h-12 w-12 rounded-2xl bg-surface-muted/70 flex items-center justify-center mx-auto text-text-muted/60">
                  <FileText className="h-6 w-6" />
                </div>
                <div className="space-y-1">
                  <h3 className="text-base font-semibold text-text-primary">No revision notes yet</h3>
                  <p className="text-xs text-text-muted max-w-sm mx-auto">
                    Generate structured revision guides with formulas, key concepts, and takeaways.
                  </p>
                </div>
                <Button
                  onClick={handleGenerateRevisionNotes}
                  disabled={generating}
                  className="bg-primary text-primary-foreground hover:bg-primary/90 text-xs rounded-xl"
                >
                  {generating ? 'Generating...' : 'Generate Notes'}
                </Button>
              </div>
            </BlurFade>
          ) : (
            <div className="space-y-6">
              {notes.map((note, nIdx) => (
                <BlurFade key={note.id} delay={0.1 + nIdx * 0.05}>
                  <div className="bg-surface border border-border/80 rounded-2xl p-6 sm:p-8 space-y-6 shadow-sm">
                    {/* Note Header */}
                    <div className="flex flex-col sm:flex-row items-start justify-between gap-4 border-b border-border/80 pb-4">
                      <div className="space-y-1.5 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge variant="outline" className="text-[10px] uppercase tracking-wider font-mono bg-primary/5 text-primary border-primary/20">
                            {note.focus ? note.focus.replace(/_/g, ' ') : 'Revision Guide'}
                          </Badge>
                          <Badge variant="outline" className="text-[10px] capitalize font-mono">
                            {note.length || 'standard'} length
                          </Badge>
                          {note.detail_level && (
                            <Badge variant="outline" className="text-[10px] capitalize font-mono text-text-muted">
                              {note.detail_level}
                            </Badge>
                          )}
                        </div>
                        <h3 className="text-xl font-bold text-text-primary tracking-tight">{note.title}</h3>
                        <p className="text-xs sm:text-sm text-text-muted leading-relaxed">{note.overview}</p>
                      </div>
                    </div>

                    {/* Structured Core Sections */}
                    {note.sections && note.sections.length > 0 && (
                      <div className="space-y-5">
                        <span className="text-xs font-semibold text-primary uppercase tracking-wider block">
                          Detailed Study Sections
                        </span>
                        <div className="grid grid-cols-1 gap-4">
                          {note.sections.map((sec, sIdx) => (
                            <div
                              key={sIdx}
                              className="bg-surface-muted/30 border border-border/80 rounded-xl p-4 sm:p-5 space-y-3"
                            >
                              <h4 className="text-sm sm:text-base font-bold text-text-primary flex items-center gap-2">
                                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary/10 text-primary text-[10px] font-mono">
                                  {sIdx + 1}
                                </span>
                                <span>{sec.heading}</span>
                              </h4>
                              {sec.summary && (
                                <p className="text-xs text-text-secondary leading-relaxed pl-7">
                                  {sec.summary}
                                </p>
                              )}

                              {/* Section Bullet Points */}
                              {sec.bullet_points && sec.bullet_points.length > 0 && (
                                <div className="pl-7 pt-1 space-y-1.5">
                                  {sec.bullet_points.map((pt, pIdx) => (
                                    <div key={pIdx} className="flex items-start gap-2 text-xs text-text-muted">
                                      <span className="text-primary mt-1 font-bold">•</span>
                                      <span className="leading-relaxed text-text-primary/90">{pt}</span>
                                    </div>
                                  ))}
                                </div>
                              )}

                              {/* Key Takeaways */}
                              {sec.key_takeaways && sec.key_takeaways.length > 0 && (
                                <div className="mt-3 ml-7 bg-primary/5 border border-primary/15 rounded-lg p-3 text-xs space-y-1">
                                  <span className="text-[10px] uppercase font-semibold text-primary tracking-wider block">
                                    Key Takeaways
                                  </span>
                                  {sec.key_takeaways.map((takeaway, tIdx) => (
                                    <p key={tIdx} className="text-text-secondary leading-relaxed">
                                      ✓ {takeaway}
                                    </p>
                                  ))}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Key Concepts Grid */}
                    {note.key_concepts && note.key_concepts.length > 0 && (
                      <div className="pt-2 space-y-3 border-t border-border/80">
                        <span className="text-xs font-semibold text-text-muted uppercase tracking-wider block">
                          Key Concepts & Terminology
                        </span>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          {note.key_concepts.map((kc, i) => (
                            <div key={i} className="bg-surface-muted/50 border border-border/80 rounded-xl p-3.5 text-xs space-y-1">
                              <strong className="text-primary font-semibold text-xs block">{kc.term}</strong>
                              <p className="text-text-secondary text-[11px] leading-relaxed">{kc.definition}</p>
                              {kc.context && (
                                <span className="text-text-muted text-[10px] block italic pt-1">
                                  Context: {kc.context}
                                </span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Formulas & Algorithms */}
                    {note.formulas && note.formulas.length > 0 && (
                      <div className="pt-2 space-y-3 border-t border-border/80">
                        <span className="text-xs font-semibold text-text-muted uppercase tracking-wider block">
                          Formulas, Equations & Algorithms
                        </span>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          {note.formulas.map((f, i) => (
                            <div key={i} className="bg-surface-muted/70 border border-border/80 rounded-xl p-3.5 text-xs space-y-1.5">
                              <span className="text-text-muted text-[10px] uppercase tracking-wider font-semibold block">
                                {f.name}
                              </span>
                              <div className="bg-surface border border-border rounded-lg p-2.5 overflow-x-auto">
                                <code className="text-text-primary font-mono font-bold text-xs block">
                                  {f.expression}
                                </code>
                              </div>
                              {f.explanation && (
                                <p className="text-text-secondary text-[11px] leading-relaxed">
                                  {f.explanation}
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Important Points */}
                    {note.important_points && note.important_points.length > 0 && (
                      <div className="pt-2 space-y-2 border-t border-border/80">
                        <span className="text-xs font-semibold text-text-muted uppercase tracking-wider block">
                          Important Points & Traps
                        </span>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {note.important_points.map((pt, i) => (
                            <div key={i} className="flex items-start gap-2 bg-amber-500/5 border border-amber-500/15 rounded-xl p-3 text-xs text-text-secondary">
                              <span className="text-amber-500 font-bold">!</span>
                              <span className="leading-relaxed">{pt}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Source References & Citations */}
                    {note.source_references && note.source_references.length > 0 && (
                      <div className="pt-2 space-y-2 border-t border-border/80">
                        <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider block">
                          Source References & Grounding
                        </span>
                        <div className="flex flex-wrap gap-2">
                          {note.source_references.map((ref, i) => (
                            <div
                              key={i}
                              title={ref.text_excerpt || ref.excerpt}
                              className="bg-surface-muted/60 border border-border/80 rounded-lg px-2.5 py-1 text-[10px] text-text-muted font-mono flex items-center gap-1.5"
                            >
                              <FileText className="h-3 w-3 text-primary" />
                              <span>{ref.document_title || 'Document'}</span>
                              {ref.page_number && <span className="text-text-secondary">p. {ref.page_number}</span>}
                              {ref.slide_number && <span className="text-text-secondary">slide {ref.slide_number}</span>}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </BlurFade>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Active Recall Modal */}
      <FlashcardViewerModal
        cards={flashcards}
        isOpen={isViewerOpen}
        onClose={() => setIsViewerOpen(false)}
        initialIndex={selectedCardIdx}
      />

      {/* Action Error Notice Dialog */}
      <ConfirmDialog
        open={Boolean(actionError)}
        onOpenChange={(open) => !open && setActionError(null)}
        title="Notice"
        description={actionError || ''}
        confirmText="Understood"
        cancelText="Close"
        onConfirm={() => setActionError(null)}
      />
    </div>
  );
};
