import React, { useState, useRef, DragEvent } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import {
  UploadCloud,
  X,
  AlertCircle,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
} from 'lucide-react';
import { formatFileSize, getFileIcon } from '../lib/documentUtils';
import { useUploadDocument } from '../hooks/useDocuments';
import { cn } from '@/lib/utils';
import { ApiClientError } from '@/services/api';

interface DocumentUploadModalProps {
  workspaceId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export interface UploadItem {
  id: string;
  file: File;
  status: 'pending' | 'uploading' | 'success' | 'duplicate' | 'error';
  errorMessage?: string;
}

const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024; // 50MB
const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.pptx', '.txt', '.md'];

export const DocumentUploadModal: React.FC<DocumentUploadModalProps> = ({
  workspaceId,
  open,
  onOpenChange,
}) => {
  const [items, setItems] = useState<UploadItem[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const uploadMutation = useUploadDocument(workspaceId);

  const resetState = () => {
    setItems([]);
    setValidationError(null);
    setIsProcessing(false);
    setIsDragging(false);
  };

  const handleClose = () => {
    if (isProcessing) return;
    resetState();
    onOpenChange(false);
  };

  const validateAndAddFiles = (files: FileList | File[]) => {
    setValidationError(null);

    const newItems: UploadItem[] = [];
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const ext = '.' + file.name.split('.').pop()?.toLowerCase();

      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        setValidationError(
          `"${file.name}" has an unsupported format. Supported formats: PDF, DOCX, PPTX, TXT, MD.`
        );
        return;
      }

      if (file.size > MAX_FILE_SIZE_BYTES) {
        setValidationError(
          `"${file.name}" exceeds the maximum 50MB file size limit.`
        );
        return;
      }

      newItems.push({
        id: `${file.name}-${file.size}-${Date.now()}-${i}`,
        file,
        status: 'pending',
      });
    }

    setItems((prev) => [...prev, ...newItems]);
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (!isProcessing) setIsDragging(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    if (!isProcessing && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndAddFiles(e.dataTransfer.files);
    }
  };

  const handleRemoveFile = (id: string) => {
    if (isProcessing) return;
    setItems((prev) => prev.filter((item) => item.id !== id));
  };

  const processUploads = async (targetItems: UploadItem[]) => {
    setIsProcessing(true);
    setValidationError(null);

    for (const item of targetItems) {
      // Set single file to uploading
      setItems((prev) =>
        prev.map((it) => (it.id === item.id ? { ...it, status: 'uploading', errorMessage: undefined } : it))
      );

      try {
        await uploadMutation.mutateAsync(item.file);
        setItems((prev) =>
          prev.map((it) => (it.id === item.id ? { ...it, status: 'success', errorMessage: undefined } : it))
        );
      } catch (err: unknown) {
        let isDuplicate = false;
        let message = 'Upload failed.';

        if (err instanceof ApiClientError) {
          isDuplicate =
            err.status === 409 ||
            err.code === 'DUPLICATE_DOCUMENT' ||
            err.code === 'duplicate_document' ||
            err.message.toLowerCase().includes('already exists') ||
            err.message.toLowerCase().includes('duplicate');
          message = err.message || (isDuplicate ? 'Identical content already exists in workspace.' : 'Upload failed.');
        } else if (err instanceof Error) {
          isDuplicate =
            err.message.includes('409') ||
            err.message.toLowerCase().includes('already exists') ||
            err.message.toLowerCase().includes('duplicate');
          message = err.message;
        }

        setItems((prev) =>
          prev.map((it) =>
            it.id === item.id
              ? {
                  ...it,
                  status: isDuplicate ? 'duplicate' : 'error',
                  errorMessage: message,
                }
              : it
          )
        );
      }
    }

    setIsProcessing(false);
  };

  const handleUploadSubmit = () => {
    const pendingItems = items.filter((it) => it.status === 'pending');
    if (pendingItems.length === 0) {
      setValidationError('Please select or add at least one document to upload.');
      return;
    }
    processUploads(pendingItems);
  };

  const handleRetryFailed = () => {
    const retryableItems = items.filter((it) => it.status === 'error');
    if (retryableItems.length > 0) {
      processUploads(retryableItems);
    }
  };

  // Aggregated outcome counts
  const successCount = items.filter((it) => it.status === 'success').length;
  const duplicateCount = items.filter((it) => it.status === 'duplicate').length;
  const errorCount = items.filter((it) => it.status === 'error').length;
  const pendingCount = items.filter((it) => it.status === 'pending').length;
  const hasCompletedBatch = items.length > 0 && pendingCount === 0 && !isProcessing;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[580px] max-h-[85dvh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <UploadCloud className="h-5 w-5 text-primary" />
            <span>Add Documents to Workspace</span>
          </DialogTitle>
          <DialogDescription>
            Upload study notes, research papers, or slides (PDF, Word DOCX, PowerPoint PPTX, TXT up to 50MB).
          </DialogDescription>
        </DialogHeader>

        {/* Validation Error Banner */}
        {validationError && (
          <div className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger/10 p-3 text-xs text-danger">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <p>{validationError}</p>
          </div>
        )}

        {/* Batch Status Summary when batch has executed */}
        {hasCompletedBatch && (
          <div className="rounded-lg border border-border bg-surface-muted/50 p-3 text-xs space-y-1">
            <p className="font-semibold text-text-primary">Batch Ingestion Results:</p>
            <div className="flex flex-wrap gap-3 text-xs">
              <span className="flex items-center gap-1 text-emerald-400 font-medium">
                <CheckCircle2 className="h-3.5 w-3.5" /> {successCount} Uploaded
              </span>
              {duplicateCount > 0 && (
                <span className="flex items-center gap-1 text-amber-400 font-medium">
                  <AlertTriangle className="h-3.5 w-3.5" /> {duplicateCount} Duplicate (Skipped)
                </span>
              )}
              {errorCount > 0 && (
                <span className="flex items-center gap-1 text-danger font-medium">
                  <AlertCircle className="h-3.5 w-3.5" /> {errorCount} Failed
                </span>
              )}
            </div>
          </div>
        )}

        {/* Drag & Drop Area */}
        <div
          role="button"
          tabIndex={isProcessing ? -1 : 0}
          aria-label="Choose documents or drop files here"
          aria-disabled={isProcessing}
          onKeyDown={(event) => { if (event.target === event.currentTarget && !isProcessing && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); fileInputRef.current?.click(); } }}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !isProcessing && fileInputRef.current?.click()}
          className={cn(
            'flex flex-col items-center justify-center p-5 sm:p-6 rounded-xl border-2 border-dashed transition-colors text-center bg-surface',
            isProcessing ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:border-primary/50 hover:bg-surface-muted/50',
            isDragging ? 'border-primary bg-primary/10' : 'border-border'
          )}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            disabled={isProcessing}
            accept=".pdf,.docx,.pptx,.txt,.md"
            className="hidden"
            onChange={(e) => {
              if (e.target.files) {
                validateAndAddFiles(e.target.files);
              }
            }}
          />
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-surface-muted text-primary mb-2 border border-border">
            <UploadCloud className="h-5 w-5" />
          </div>
          <p className="text-sm font-semibold text-text-primary">
            Click to browse or drag & drop files here
          </p>
          <p className="text-xs text-text-muted mt-1">
            Supports PDF, DOCX, PPTX, TXT & MD (Max 50MB per file)
          </p>
        </div>

        {/* Selected Files List with Individual Outcomes */}
        {items.length > 0 && (
          <div className="space-y-2 flex-1 overflow-y-auto max-h-56 pr-1">
            <div className="flex items-center justify-between text-xs font-semibold text-text-primary">
              <span>Selected Documents ({items.length})</span>
              {isProcessing && (
                <span className="text-primary flex items-center gap-1">
                  <Loader2 className="h-3 w-3 animate-spin" /> Ingesting batch...
                </span>
              )}
            </div>
            <div className="space-y-1.5">
              {items.map((item) => {
                const Icon = getFileIcon(item.file.name);
                return (
                  <div
                    key={item.id}
                    className={cn(
                      'flex items-center justify-between rounded-lg border p-2 text-xs transition-colors',
                      item.status === 'success' && 'border-emerald-500/30 bg-emerald-500/5',
                      item.status === 'duplicate' && 'border-amber-500/30 bg-amber-500/5',
                      item.status === 'error' && 'border-danger/30 bg-danger/5',
                      item.status === 'uploading' && 'border-primary/40 bg-primary/5',
                      item.status === 'pending' && 'border-border bg-surface'
                    )}
                  >
                    <div className="flex items-center gap-2 truncate flex-1 min-w-0 mr-2">
                      <Icon className="h-4 w-4 shrink-0 text-primary" />
                      <div className="truncate flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 truncate">
                          <span className="font-medium text-text-primary truncate">
                            {item.file.name}
                          </span>
                          <span className="text-text-muted shrink-0 text-[10px]">
                            ({formatFileSize(item.file.size)})
                          </span>
                        </div>
                        {item.errorMessage && (
                          <p
                            className={cn(
                              'text-[11px] truncate mt-0.5',
                              item.status === 'duplicate' ? 'text-amber-400' : 'text-danger'
                            )}
                            title={item.errorMessage}
                          >
                            {item.errorMessage}
                          </p>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      {item.status === 'uploading' && (
                        <span className="flex items-center gap-1 text-[11px] text-primary font-medium">
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          Processing
                        </span>
                      )}
                      {item.status === 'success' && (
                        <span className="flex items-center gap-1 text-[11px] text-emerald-400 font-medium">
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          Done
                        </span>
                      )}
                      {item.status === 'duplicate' && (
                        <span className="flex items-center gap-1 text-[11px] text-amber-400 font-medium">
                          <AlertTriangle className="h-3.5 w-3.5" />
                          Duplicate
                        </span>
                      )}
                      {item.status === 'error' && (
                        <span className="flex items-center gap-1 text-[11px] text-danger font-medium">
                          <AlertCircle className="h-3.5 w-3.5" />
                          Failed
                        </span>
                      )}
                      {item.status === 'pending' && !isProcessing && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6 text-text-muted hover:text-danger"
                          onClick={() => handleRemoveFile(item.id)}
                          title="Remove file"
                        >
                          <X className="h-3.5 w-3.5" />
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <DialogFooter className="pt-2 flex sm:justify-between items-center gap-2">
          <div>
            {errorCount > 0 && !isProcessing && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleRetryFailed}
                className="gap-1.5 text-xs text-danger border-danger/40 hover:bg-danger/10"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Retry {errorCount} Failed File{errorCount > 1 ? 's' : ''}
              </Button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
              disabled={isProcessing}
            >
              {hasCompletedBatch && errorCount === 0 ? 'Close' : 'Cancel'}
            </Button>
            {pendingCount > 0 && (
              <Button
                type="button"
                onClick={handleUploadSubmit}
                disabled={isProcessing}
                className="gap-2"
              >
                {isProcessing ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Processing Batch...</span>
                  </>
                ) : (
                  <>
                    <UploadCloud className="h-4 w-4" />
                    <span>Upload {pendingCount > 0 ? `(${pendingCount})` : ''}</span>
                  </>
                )}
              </Button>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
