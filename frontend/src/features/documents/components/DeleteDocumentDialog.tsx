import React from 'react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { WorkspaceDocument } from '../types/document';

interface DeleteDocumentDialogProps {
  document: WorkspaceDocument | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  isLoading?: boolean;
}

export const DeleteDocumentDialog: React.FC<DeleteDocumentDialogProps> = ({
  document,
  open,
  onOpenChange,
  onConfirm,
  isLoading = false,
}) => {
  if (!document) return null;

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete Document</AlertDialogTitle>
          <AlertDialogDescription>
            Are you sure you want to remove{' '}
            <strong className="text-text-primary">
              "{document.original_filename}"
            </strong>{' '}
            from this workspace? This will permanently delete the source file,
            extracted text chunks, and its vector embeddings from ChromaDB.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isLoading}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            disabled={isLoading}
            onClick={(e) => {
              e.preventDefault();
              onConfirm();
            }}
          >
            {isLoading ? 'Deleting...' : 'Delete Document'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
