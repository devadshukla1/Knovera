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
import { Workspace } from '../types/workspace';

interface DeleteWorkspaceDialogProps {
  workspace: Workspace | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  isLoading?: boolean;
  error?: string | null;
}

export const DeleteWorkspaceDialog: React.FC<DeleteWorkspaceDialogProps> = ({
  workspace,
  open,
  onOpenChange,
  onConfirm,
  isLoading = false,
  error = null,
}) => {
  if (!workspace) return null;

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete Workspace</AlertDialogTitle>
          <AlertDialogDescription>
            Are you sure you want to delete{' '}
            <strong className="text-text-primary">"{workspace.name}"</strong>?
            This action is permanent and will remove all associated documents,
            conversations, notes, and derived workspace data.
          </AlertDialogDescription>
        </AlertDialogHeader>
        {error && (
          <div className="rounded-md bg-danger/10 p-3 text-xs text-danger border border-danger/20">
            {error}
          </div>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isLoading}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            disabled={isLoading}
            onClick={(e) => {
              e.preventDefault();
              onConfirm();
            }}
          >
            {isLoading ? 'Deleting...' : 'Delete Workspace'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
