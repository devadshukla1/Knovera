import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Sparkles,
  User,
  AlertTriangle,
  ShieldAlert,
  Copy,
  Check,
  RefreshCw,
} from 'lucide-react';
import { ChatMessage, Citation } from '../types/chat';
import { Button } from '@/components/ui/button';
import { cn, formatRelativeTime } from '@/lib/utils';

interface MessageBubbleProps {
  message: ChatMessage;
  onSelectCitation?: (citation: Citation) => void;
  activeCitationId?: string;
  onRetry?: () => void;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({
  message,
  onSelectCitation,
  activeCitationId,
  onRetry,
}) => {
  const isUser = message.role === 'user';
  const isFailedAssistant = !isUser && (message.status === 'failed' || !message.content?.trim());
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Helper to replace [1], [2], [S1], [S2] tokens with interactive badge buttons
  const renderWithCitations = (child: React.ReactNode): React.ReactNode => {
    if (typeof child !== 'string') return child;
    const parts = child.split(/(\[S?\d+\])/g);
    if (parts.length === 1) return child;

    return parts.map((part, index) => {
      const match = part.match(/^\[S?(\d+)\]$/);
      if (match) {
        const num = parseInt(match[1], 10);
        const foundCitation = message.citations?.find(
          (c) => c.citation_number === num
        );

        if (foundCitation && onSelectCitation) {
          const isActive = activeCitationId === foundCitation.id;
          return (
            <button
              key={index}
              type="button"
              onClick={() => onSelectCitation(foundCitation)}
              className={cn(
                'inline-flex items-center justify-center font-mono text-[11px] font-bold px-1.5 py-0.2 mx-0.5 rounded transition-all cursor-pointer select-none align-baseline',
                isActive
                  ? 'bg-primary text-primary-foreground shadow-sm ring-1 ring-primary'
                  : 'bg-primary/20 text-primary hover:bg-primary/30 border border-primary/35 hover:scale-105'
              )}
              title={`Source: ${foundCitation.document_title} (Page ${foundCitation.page_number || 'N/A'})`}
            >
              [{num}]
            </button>
          );
        }
      }
      return part;
    });
  };

  const renderContent = () => {
    if (isUser) {
      return (
        <div className="whitespace-pre-wrap leading-relaxed text-sm">
          {message.content}
        </div>
      );
    }

    return (
      <div className="chat-markdown prose-neutral text-sm leading-relaxed max-w-none space-y-3">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            h1: ({ children }) => (
              <h1 className="text-lg font-bold mt-4 mb-2 text-text-primary first:mt-0 tracking-tight">
                {children}
              </h1>
            ),
            h2: ({ children }) => (
              <h2 className="text-base font-bold mt-3 mb-1.5 text-text-primary first:mt-0 tracking-tight">
                {children}
              </h2>
            ),
            h3: ({ children }) => (
              <h3 className="text-sm font-semibold mt-2.5 mb-1 text-text-primary first:mt-0">
                {children}
              </h3>
            ),
            p: ({ children }) => (
              <p className="mb-2.5 last:mb-0 leading-relaxed text-sm text-text-primary">
                {React.Children.map(children, renderWithCitations)}
              </p>
            ),
            ul: ({ children }) => (
              <ul className="list-disc pl-5 my-2 space-y-1 text-sm text-text-primary">
                {children}
              </ul>
            ),
            ol: ({ children }) => (
              <ol className="list-decimal pl-5 my-2 space-y-1 text-sm text-text-primary">
                {children}
              </ol>
            ),
            li: ({ children }) => (
              <li className="leading-relaxed">
                {React.Children.map(children, renderWithCitations)}
              </li>
            ),
            strong: ({ children }) => (
              <strong className="font-semibold text-text-primary">
                {children}
              </strong>
            ),
            em: ({ children }) => (
              <em className="italic text-text-primary/90">{children}</em>
            ),
            blockquote: ({ children }) => (
              <blockquote className="border-l-2 border-primary/50 bg-primary/5 rounded-r-md px-3 py-1.5 my-2 text-text-secondary italic text-xs">
                {children}
              </blockquote>
            ),
            code: ({ className, children, ...props }: any) => {
              const match = /language-(\w+)/.exec(className || '');
              const isInline = !match && !String(children).includes('\n');
              if (isInline) {
                return (
                  <code
                    className="bg-surface-muted/90 px-1.5 py-0.5 rounded text-xs font-mono text-primary font-medium border border-border/80"
                    {...props}
                  >
                    {children}
                  </code>
                );
              }
              return (
                <div className="relative group/code my-3 rounded-xl border border-border overflow-hidden bg-surface-muted/80">
                  <div className="flex items-center justify-between px-3.5 py-1.5 bg-surface-muted border-b border-border text-[11px] font-mono text-text-muted">
                    <span>{match ? match[1] : 'code'}</span>
                    <button
                      type="button"
                      onClick={() => navigator.clipboard.writeText(String(children))}
                      className="hover:text-text-primary transition-colors flex items-center gap-1 text-[10px]"
                    >
                      <Copy className="h-3 w-3" />
                      <span>Copy</span>
                    </button>
                  </div>
                  <pre className="p-3.5 overflow-x-auto text-xs font-mono text-text-primary">
                    <code className={className} {...props}>
                      {children}
                    </code>
                  </pre>
                </div>
              );
            },
            table: ({ children }) => (
              <div className="overflow-x-auto my-3 border border-border/80 rounded-xl shadow-sm">
                <table className="min-w-full divide-y divide-border text-xs text-left">
                  {children}
                </table>
              </div>
            ),
            thead: ({ children }) => (
              <thead className="bg-surface-muted/80 font-semibold text-text-primary">{children}</thead>
            ),
            tbody: ({ children }) => (
              <tbody className="divide-y divide-border/60 bg-surface/50">{children}</tbody>
            ),
            tr: ({ children }) => (
              <tr className="hover:bg-surface-muted/30 transition-colors">{children}</tr>
            ),
            th: ({ children }) => (
              <th className="px-3.5 py-2.5 font-semibold text-text-primary">
                {children}
              </th>
            ),
            td: ({ children }) => (
              <td className="px-3.5 py-2.5 text-text-secondary leading-normal">
                {React.Children.map(children, renderWithCitations)}
              </td>
            ),
          }}
        >
          {message.content}
        </ReactMarkdown>
      </div>
    );
  };

  return (
    <div
      className={cn(
        'flex gap-3 max-w-3xl group/bubble',
        isUser ? 'ml-auto flex-row-reverse' : 'mr-auto flex-row'
      )}
    >
      {/* Avatar Icon */}
      <div
        className={cn(
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border text-xs font-semibold select-none shadow-sm',
          isUser
            ? 'bg-surface-muted text-text-primary border-border'
            : 'bg-gradient-to-br from-primary/30 to-accent-purple/20 text-primary border-primary/35 shadow-glow-sm'
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
      </div>

      {/* Bubble Container */}
      <div className="flex flex-col space-y-1.5 min-w-0 flex-1">
        <div
          className={cn(
            'relative rounded-2xl px-4 py-3.5 shadow-elevation-1 transition-all',
            isUser
              ? 'bg-surface-elevated text-text-primary border border-border/90 rounded-tr-sm ml-auto max-w-2xl'
              : 'bg-surface/95 text-text-primary border border-border/80 rounded-tl-sm w-full'
          )}
        >
          {/* Copy Button for Assistant */}
          {!isUser && !isFailedAssistant && (
            <button
              onClick={handleCopy}
              className="absolute top-3 right-3 opacity-0 group-hover/bubble:opacity-100 p-1.5 text-text-muted hover:text-text-primary rounded-lg hover:bg-surface-muted transition-all"
              title="Copy answer"
              aria-label="Copy answer"
            >
              {copied ? (
                <Check className="h-3.5 w-3.5 text-success" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
            </button>
          )}

          {/* Failed Assistant Generation State (Prevents Blank Bubble) */}
          {isFailedAssistant ? (
            <div className="flex flex-col gap-2 text-xs text-destructive">
              <div className="flex items-center gap-2 font-semibold">
                <ShieldAlert className="h-4 w-4 shrink-0" />
                <span>Response generation failed{message.failure_code ? ` (${message.failure_code})` : ''}</span>
              </div>
              <p className="text-text-secondary">
                The AI provider could not complete this request. Verify the server LLM configuration or retry.
              </p>
              {onRetry && (
                <div className="pt-1">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={onRetry}
                    className="h-7 text-xs gap-1.5 border-destructive/30 text-destructive hover:bg-destructive/10"
                  >
                    <RefreshCw className="h-3 w-3" />
                    <span>Retry</span>
                  </Button>
                </div>
              )}
            </div>
          ) : (
            <>
              {/* Evidence Quality Warning Banner if partial or insufficient */}
              {!isUser && message.evidence_status === 'partial' && (
                <div className="mb-3 flex items-center gap-1.5 rounded-lg bg-warning/10 px-3 py-1.5 text-xs text-warning border border-warning/25">
                  <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                  <span>Partial evidence in available sources. Synthesized with caveats.</span>
                </div>
              )}

              {!isUser && message.evidence_status === 'insufficient' && (
                <div className="mb-3 flex items-center gap-1.5 rounded-lg bg-danger/10 px-3 py-1.5 text-xs text-danger border border-danger/25">
                  <ShieldAlert className="h-3.5 w-3.5 shrink-0" />
                  <span>Insufficient evidence in provided documents to support an authoritative answer.</span>
                </div>
              )}

              {/* Formatted Content */}
              {renderContent()}
            </>
          )}

          {/* Bottom Citations List for Assistant */}
          {!isUser && message.citations && message.citations.length > 0 && (
            <div className="mt-4 pt-3 border-t border-border/60 space-y-2">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-text-muted block">
                Citations & Sources
              </span>
              <div className="flex flex-wrap gap-1.5">
                {message.citations.map((c) => (
                  <Button
                    key={c.id}
                    variant="outline"
                    size="sm"
                    onClick={() => onSelectCitation?.(c)}
                    className={cn(
                      'h-6 text-[11px] font-normal px-2.5 py-0 border-border bg-surface-muted/60 text-text-secondary hover:text-text-primary gap-1.5 rounded-md transition-all',
                      activeCitationId === c.id &&
                        'border-primary bg-primary/15 text-primary font-medium shadow-glow-sm ring-1 ring-primary/40'
                    )}
                  >
                    <span className="font-mono font-bold text-primary">[{c.citation_number}]</span>
                    <span className="truncate max-w-[150px]">{c.document_title}</span>
                  </Button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Timestamp */}
        <span
          className={cn(
            'text-[10px] text-text-muted px-1.5',
            isUser ? 'text-right' : 'text-left'
          )}
        >
          {formatRelativeTime(message.created_at)}
        </span>
      </div>
    </div>
  );
};
