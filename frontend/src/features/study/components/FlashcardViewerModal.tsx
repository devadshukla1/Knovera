import React, { useEffect, useRef, useState } from 'react';
import {
  X,
  RotateCw,
  ChevronLeft,
  ChevronRight,
  BookOpen,
  Sparkles,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Flashcard } from '../types/study';

interface FlashcardViewerModalProps {
  cards: Flashcard[];
  isOpen: boolean;
  onClose: () => void;
  initialIndex?: number;
}

export const FlashcardViewerModal: React.FC<FlashcardViewerModalProps> = ({
  cards,
  isOpen,
  onClose,
  initialIndex = 0,
}) => {
  const [currentIndex, setCurrentIndex] = useState(initialIndex);
  const [isFlipped, setIsFlipped] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const previous = document.activeElement as HTMLElement | null;
    dialogRef.current?.querySelector<HTMLElement>('[data-flip-card]')?.focus();
    return () => previous?.focus();
  }, [isOpen]);

  useEffect(() => {
    setCurrentIndex(initialIndex);
    setIsFlipped(false);
  }, [initialIndex, isOpen]);

  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Tab') {
        const items = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>('button:not([disabled]), [tabindex="0"]') ?? []);
        const first = items[0], last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
        return;
      }
      if ((e.key === ' ' || e.key === 'Enter') && e.target instanceof HTMLElement && e.target.closest('button, a, input, textarea, select')) return;
      if (e.key === 'Escape') {
        onClose();
      } else if (e.key === ' ' || e.key === 'Enter') {
        e.preventDefault();
        setIsFlipped((prev) => !prev);
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        handleNext();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        handlePrev();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, currentIndex, cards.length]);

  if (!isOpen || cards.length === 0) return null;

  const currentCard = cards[currentIndex];

  const handleNext = () => {
    if (currentIndex < cards.length - 1) {
      setIsFlipped(false);
      setCurrentIndex((prev) => prev + 1);
    }
  };

  const handlePrev = () => {
    if (currentIndex > 0) {
      setIsFlipped(false);
      setCurrentIndex((prev) => prev - 1);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="Active recall deck"
        className="relative flex flex-col w-full max-w-2xl bg-surface border border-border rounded-2xl shadow-2xl max-h-[calc(100dvh-32px)] overflow-y-auto p-4 sm:p-6 gap-5"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top Header */}
        <div className="flex items-center justify-between border-b border-border/60 pb-3">
          <div className="flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-primary" />
            <span className="font-semibold text-text-primary text-sm tracking-wide">
              Active Recall Deck
            </span>
            <Badge variant="secondary" className="text-xs font-mono ml-2">
              {currentIndex + 1} / {cards.length}
            </Badge>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-text-muted hidden sm:inline">
              <kbd className="px-1.5 py-0.5 bg-surface-muted rounded text-[10px] font-mono border border-border mr-1">
                Space
              </kbd>
              to flip,
              <kbd className="px-1.5 py-0.5 bg-surface-muted rounded text-[10px] font-mono border border-border mx-1">
                ← / →
              </kbd>
              to navigate
            </span>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Close modal"
              className="h-8 w-8 text-text-muted hover:text-text-primary rounded-lg"
              onClick={onClose}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* 3D Flip Card Container */}
        <div
          className="relative w-full h-80 shrink-0 cursor-pointer select-none [perspective:1000px]"
          data-flip-card
          role="button"
          tabIndex={0}
          aria-label={isFlipped ? 'Show question' : 'Reveal answer'}
          aria-pressed={isFlipped}
          onClick={() => setIsFlipped((prev) => !prev)}
        >
          <div
            className={`relative w-full h-full rounded-xl transition-transform duration-300 [transform-style:preserve-3d] ${
              isFlipped ? '[transform:rotateY(180deg)]' : ''
            }`}
          >
            {/* Front Face */}
            <div aria-hidden={isFlipped} className="absolute inset-0 w-full h-full bg-surface-muted/50 border border-border rounded-xl p-5 sm:p-8 overflow-y-auto flex flex-col justify-between [backface-visibility:hidden]">
              <div className="flex items-center justify-between">
                <Badge variant="outline" className="text-xs uppercase font-mono tracking-wider">
                  {currentCard.card_type}
                </Badge>
                <Badge
                  variant="secondary"
                  className="text-xs capitalize font-medium text-text-muted"
                >
                  {currentCard.difficulty}
                </Badge>
              </div>

              <div className="flex flex-col items-center justify-center text-center my-auto">
                <p className="text-xl sm:text-2xl font-semibold text-text-primary leading-relaxed">
                  {currentCard.front}
                </p>
              </div>

              <div className="flex items-center justify-center gap-1.5 text-xs text-text-muted">
                <RotateCw className="h-3.5 w-3.5" />
                <span>Click or tap anywhere to reveal answer</span>
              </div>
            </div>

            {/* Back Face */}
            <div aria-hidden={!isFlipped} className="absolute inset-0 w-full h-full bg-primary/10 border border-primary/30 rounded-xl p-5 sm:p-8 overflow-y-auto flex flex-col justify-between [transform:rotateY(180deg)] [backface-visibility:hidden]">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-primary text-xs font-semibold">
                  <Sparkles className="h-4 w-4" />
                  <span>TARGET ANSWER</span>
                </div>
                {currentCard.topic && (
                  <Badge variant="outline" className="text-xs text-text-muted">
                    {currentCard.topic}
                  </Badge>
                )}
              </div>

              <div className="flex flex-col items-center justify-center text-center my-auto px-4">
                <p className="text-lg sm:text-xl font-medium text-text-primary leading-relaxed">
                  {currentCard.back}
                </p>
              </div>

              {currentCard.source_references && currentCard.source_references.length > 0 && (
                <div className="flex items-center justify-center text-[11px] text-text-muted font-mono truncate">
                  Source: {currentCard.source_references[0].document_title}
                  {currentCard.source_references[0].page_number
                    ? ` (p. ${currentCard.source_references[0].page_number})`
                    : ''}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Bottom Controls */}
        <div className="flex items-center justify-between pt-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handlePrev}
            disabled={currentIndex === 0}
            className="flex items-center gap-1"
          >
            <ChevronLeft className="h-4 w-4" />
            Previous
          </Button>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsFlipped((prev) => !prev)}
            className="flex items-center gap-1.5 text-xs text-text-secondary"
          >
            <RotateCw className="h-3.5 w-3.5" />
            Flip Card
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={handleNext}
            disabled={currentIndex === cards.length - 1}
            className="flex items-center gap-1"
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
};
