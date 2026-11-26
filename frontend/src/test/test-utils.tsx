import React from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, MemoryRouterProps } from 'react-router-dom';
import { ThemeProvider } from '@/context/ThemeContext';

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

export function renderWithProviders(
  ui: React.ReactElement,
  options?: Omit<RenderOptions, 'wrapper'> & {
    initialEntries?: MemoryRouterProps['initialEntries'];
    queryClient?: QueryClient;
  }
) {
  const queryClient = options?.queryClient ?? createTestQueryClient();
  const initialEntries = options?.initialEntries ?? ['/'];

  return render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider defaultTheme="dark">
        <MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
    options
  );
}
