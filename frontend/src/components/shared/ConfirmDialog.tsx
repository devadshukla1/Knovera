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
import { buttonVariants } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmText?: string;
  cancelText?: string;
  isDestructive?: boolean;
  isLoading?: boolean;
  onConfirm: () => void;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  open,
  onOpenChange,
  title,
  description,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  isDestructive = false,
  isLoading = false,
  onConfirm,
}) => {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="bg-surface-elevated/95 border border-border/80 shadow-2xl backdrop-blur-xl max-w-[460px] rounded-2xl p-6">
        <AlertDialogHeader className="space-y-2">
          <AlertDialogTitle className="text-lg font-semibold text-text-primary tracking-tight">
            {title}
          </AlertDialogTitle>
          <AlertDialogDescription className="text-sm text-text-secondary leading-relaxed">
            {description}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter className="mt-5 flex items-center justify-end gap-2.5">
          <AlertDialogCancel
            disabled={isLoading}
            className="border-border hover:bg-surface-muted text-text-secondary hover:text-text-primary h-9 px-4 text-xs font-medium rounded-xl"
          >
            {cancelText}
          </AlertDialogCancel>
          <AlertDialogAction
            disabled={isLoading}
            onClick={(e) => {
              e.preventDefault();
              onConfirm();
            }}
            className={cn(
              buttonVariants({ variant: isDestructive ? 'destructive' : 'default' }),
              'h-9 px-4 text-xs font-medium rounded-xl shadow-sm'
            )}
          >
            {isLoading ? 'Processing...' : confirmText}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
