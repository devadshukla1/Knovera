import { z } from 'zod';

export const workspaceFormSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, 'Workspace name is required')
    .max(120, 'Workspace name must be 120 characters or fewer'),
  description: z
    .string()
    .trim()
    .max(500, 'Description must be 500 characters or fewer')
    .optional()
    .or(z.literal('')),
});

export type WorkspaceFormValues = z.infer<typeof workspaceFormSchema>;
