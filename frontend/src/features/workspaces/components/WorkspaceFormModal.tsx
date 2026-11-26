import React, { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  workspaceFormSchema,
  WorkspaceFormValues,
} from '../schemas/workspaceSchema';
import { Workspace } from '../types/workspace';
import { AlertCircle, Loader2 } from 'lucide-react';

interface WorkspaceFormModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  workspace?: Workspace | null; // If provided, mode is rename/edit; otherwise create
  onSubmit: (values: WorkspaceFormValues) => Promise<void> | void;
  isLoading?: boolean;
  serverError?: string | null;
}

export const WorkspaceFormModal: React.FC<WorkspaceFormModalProps> = ({
  open,
  onOpenChange,
  workspace,
  onSubmit,
  isLoading = false,
  serverError,
}) => {
  const isEditing = Boolean(workspace);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<WorkspaceFormValues>({
    resolver: zodResolver(workspaceFormSchema),
    defaultValues: {
      name: '',
      description: '',
    },
  });

  // Prepopulate form when modal opens or workspace changes
  useEffect(() => {
    if (open) {
      if (workspace) {
        reset({
          name: workspace.name,
          description: workspace.description || '',
        });
      } else {
        reset({
          name: '',
          description: '',
        });
      }
    }
  }, [open, workspace, reset]);

  const handleFormSubmit = async (values: WorkspaceFormValues) => {
    await onSubmit(values);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {isEditing ? 'Rename Workspace' : 'Create Workspace'}
          </DialogTitle>
          <DialogDescription>
            {isEditing
              ? 'Update the name or description of this workspace.'
              : 'Workspaces organise your research papers, notes, documents, and conversations.'}
          </DialogDescription>
        </DialogHeader>

        {serverError && (
          <div className="flex items-start gap-2.5 rounded-lg border border-danger/30 bg-danger/10 p-3 text-xs text-danger">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <p className="leading-relaxed">{serverError}</p>
          </div>
        )}

        <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="workspace-name" required>
              Workspace Name
            </Label>
            <Input
              id="workspace-name"
              placeholder="e.g. Quantum Computing Notes, Thesis Papers"
              error={Boolean(errors.name)}
              disabled={isLoading}
              {...register('name')}
            />
            {errors.name && (
              <p className="text-xs text-danger">{errors.name.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="workspace-desc">Description (Optional)</Label>
            <textarea
              id="workspace-desc"
              rows={3}
              placeholder="Brief description of research focus, course or goals..."
              disabled={isLoading}
              className="flex w-full rounded-md border border-border bg-surface-muted px-3 py-2 text-sm text-text-primary shadow-sm placeholder:text-text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50"
              {...register('description')}
            />
            {errors.description && (
              <p className="text-xs text-danger">
                {errors.description.message}
              </p>
            )}
          </div>

          <DialogFooter className="pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading} className="gap-2">
              {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}
              <span>{isEditing ? 'Save Changes' : 'Create Workspace'}</span>
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
