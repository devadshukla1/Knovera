import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  GraduationCap,
  Play,
  ArrowLeft,
  Sparkles,
  Check,
  AlertCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { BlurFade } from '@/components/magicui/BlurFade';
import { studyApi } from '../api/studyApi';

export const QuizSetupPage: React.FC = () => {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const navigate = useNavigate();

  const [title, setTitle] = useState('');
  const [count, setCount] = useState<number>(10);
  const [selectedTypes, setSelectedTypes] = useState<string[]>(['mcq', 'true_false', 'fill_blank']);
  const [difficulty, setDifficulty] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleType = (type: string) => {
    if (selectedTypes.includes(type)) {
      if (selectedTypes.length > 1) {
        setSelectedTypes(selectedTypes.filter((t) => t !== type));
      }
    } else {
      setSelectedTypes([...selectedTypes, type]);
    }
  };

  const handleStartQuiz = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!workspaceId) return;

    try {
      setLoading(true);
      setError(null);

      const attempt = await studyApi.createQuizAttempt(workspaceId, {
        title: title.trim() || undefined,
        count,
        question_types: selectedTypes,
        difficulty: difficulty || undefined,
      });

      navigate(
        `/app/workspaces/${encodeURIComponent(workspaceId)}/study-studio/quiz/${encodeURIComponent(attempt.id)}`
      );
    } catch (err: any) {
      setError(err?.message || 'Failed to start quiz. Make sure study materials have been generated first.');
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col max-w-2xl mx-auto px-4 py-8 gap-8">
      {/* Back button */}
      <BlurFade delay={0.05}>
        <div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(`/app/workspaces/${encodeURIComponent(workspaceId || '')}/study-studio`)}
            className="text-text-muted hover:text-text-primary flex items-center gap-1.5 rounded-lg"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Back to Study Studio</span>
          </Button>
        </div>
      </BlurFade>

      {/* Header */}
      <BlurFade delay={0.1}>
        <div className="space-y-2">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-primary/10 border border-primary/25 text-primary text-xs font-semibold uppercase tracking-wider">
            <GraduationCap className="h-3.5 w-3.5" />
            <span>Interactive Quiz Configurator</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-text-primary">
            Configure Interactive Quiz
          </h1>
          <p className="text-sm text-text-muted">
            Test your knowledge with practice questions drawn deterministically from verified documents in this workspace.
          </p>
        </div>
      </BlurFade>

      {error && (
        <div className="flex items-start gap-3 p-4 bg-destructive/10 border border-destructive/20 rounded-xl text-destructive text-sm animate-in fade-in">
          <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
          <div>
            <strong className="block font-semibold mb-0.5">Could not start quiz</strong>
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Setup Form */}
      <BlurFade delay={0.15}>
        <form onSubmit={handleStartQuiz} className="bg-surface border border-border/80 rounded-xl p-5 sm:p-8 space-y-6 shadow-sm">
          {/* Quiz Title */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-text-muted tracking-wide uppercase">
              Quiz Title (Optional)
            </label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Machine Learning Exam Review"
              className="bg-surface-muted/50 border-border/80 rounded-xl text-sm py-2.5"
            />
          </div>

          {/* Question Types */}
          <div className="space-y-3">
            <label className="text-xs font-semibold text-text-muted tracking-wide uppercase">
              Question Types Included
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[
                { id: 'mcq', label: 'Multiple Choice', desc: '4-option conceptual checks' },
                { id: 'true_false', label: 'True / False', desc: 'Fact & misconception analysis' },
                { id: 'fill_blank', label: 'Fill-in-Blank', desc: 'Precise term recall' },
              ].map((t) => {
                const isChecked = selectedTypes.includes(t.id);
                return (
                  <button
                    key={t.id}
                    type="button"
                    aria-pressed={isChecked}
                    onClick={() => toggleType(t.id)}
                    className={`flex flex-col p-4 rounded-xl border text-left transition-colors ${
                      isChecked
                        ? 'bg-primary/10 border-primary ring-1 ring-primary shadow-sm'
                        : 'bg-surface-muted/30 border-border/80 text-text-muted hover:bg-surface-muted/60'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-bold text-text-primary">{t.label}</span>
                      <div
                        className={`h-4 w-4 rounded flex items-center justify-center transition-colors ${
                          isChecked ? 'bg-primary text-primary-foreground' : 'border border-border/80'
                        }`}
                      >
                        {isChecked && <Check className="h-3 w-3" />}
                      </div>
                    </div>
                    <span className="text-[11px] text-text-muted leading-tight">{t.desc}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Question Count */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-text-muted tracking-wide uppercase">
                Number of Questions
              </label>
              <Badge variant="secondary" className="font-mono text-xs">
                {count} Questions
              </Badge>
            </div>
            <div className="grid grid-cols-4 gap-2">
              {[5, 10, 15, 20].map((n) => (
                <Button
                  key={n}
                  type="button"
                  variant={count === n ? 'default' : 'outline'}
                  size="sm"
                  aria-pressed={count === n}
                  onClick={() => setCount(n)}
                  className={`font-mono text-xs rounded-xl ${
                    count === n ? 'shadow-sm' : 'border-border/80'
                  }`}
                >
                  {n}
                </Button>
              ))}
            </div>
          </div>

          {/* Difficulty Filter */}
          <div className="space-y-3">
            <label className="text-xs font-semibold text-text-muted tracking-wide uppercase">
              Target Difficulty
            </label>
            <div className="grid grid-cols-4 gap-2">
              {[
                { id: '', label: 'Mixed' },
                { id: 'easy', label: 'Easy' },
                { id: 'medium', label: 'Medium' },
                { id: 'hard', label: 'Hard' },
              ].map((d) => (
                <Button
                  key={d.id}
                  type="button"
                  variant={difficulty === d.id ? 'default' : 'outline'}
                  size="sm"
                  aria-pressed={difficulty === d.id}
                  onClick={() => setDifficulty(d.id)}
                  className={`text-xs rounded-xl ${
                    difficulty === d.id ? 'shadow-sm' : 'border-border/80'
                  }`}
                >
                  {d.label}
                </Button>
              ))}
            </div>
          </div>

          {/* Action Button */}
          <div className="pt-4 border-t border-border/80">
            <Button
              type="submit"
              disabled={loading}
              className="w-full bg-primary hover:bg-primary/90 text-primary-foreground py-6 text-base font-semibold flex items-center justify-center gap-2 rounded-xl shadow-md transition-transform active:scale-98"
            >
              {loading ? (
                <>
                  <Sparkles className="h-5 w-5 animate-spin" />
                  <span>Preparing Questions...</span>
                </>
              ) : (
                <>
                  <Play className="h-5 w-5 fill-current" />
                  <span>Begin Interactive Quiz</span>
                </>
              )}
            </Button>
          </div>
        </form>
      </BlurFade>
    </div>
  );
};
