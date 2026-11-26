import React, { useState, useRef, useEffect, KeyboardEvent } from 'react';
import { Send, Loader2, CornerDownLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface ChatComposerProps {
  onSend: (message: string) => Promise<void> | void;
  isLoading?: boolean;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
}

export const ChatComposer: React.FC<ChatComposerProps> = ({
  onSend,
  isLoading = false,
  disabled = false,
  placeholder = 'Ask a question about your documents...',
  className,
}) => {
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [text]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = async () => {
    const trimmed = text.trim();
    if (!trimmed || isLoading || disabled) return;

    setText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    await onSend(trimmed);
  };

  const canSend = Boolean(text.trim()) && !isLoading && !disabled;

  return (
    <div
      className={cn(
        'chat-composer relative rounded-2xl border border-border/90 bg-surface-elevated/90 p-2.5 shadow-sm transition-colors duration-200 focus-within:border-primary/60 focus-within:shadow-glow-sm focus-within:ring-1 focus-within:ring-primary/30',
        className
      )}
    >
      <textarea
        aria-label="Ask a question about your documents"
        ref={textareaRef}
        rows={1}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled || isLoading}
        className="w-full max-h-44 min-h-[44px] resize-none border-0 bg-transparent px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 leading-relaxed"
      />

      <div className="flex items-center justify-between pt-1 px-1.5 border-t border-border/40 mt-1">
        <div className="flex items-center gap-2 text-[11px] text-text-muted">
          <span className="hidden sm:inline-flex items-center gap-1 font-mono text-[10px] bg-surface-muted/80 px-1.5 py-0.5 rounded border border-border">
            <span>Enter</span>
            <CornerDownLeft className="h-2.5 w-2.5" />
            <span className="text-text-muted/70">to send</span>
          </span>
          <span className="hidden md:inline text-[10px] text-text-muted/60">
            Shift + Enter for new line
          </span>
        </div>

        <Button
          type="button"
          size="sm"
          onClick={handleSubmit}
          disabled={!canSend}
          variant={canSend ? 'glow' : 'secondary'}
          className="h-8 px-3 rounded-lg text-xs font-semibold gap-1.5 transition-all"
          aria-label="Send message"
          title="Send question"
        >
          {isLoading ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>Thinking...</span>
            </>
          ) : (
            <>
              <span>Send</span>
              <Send className="h-3.5 w-3.5" />
            </>
          )}
        </Button>
      </div>
    </div>
  );
};
