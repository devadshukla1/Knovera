import { screen, fireEvent, render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { FlashcardViewerModal } from '../components/FlashcardViewerModal';
import { Flashcard } from '../types/study';

const mockCards: Flashcard[] = [
  {
    id: 'fc-1',
    workspace_id: 'ws-1',
    front: 'What is the margin in SVMs?',
    back: 'The geometric distance 2/||w|| between supporting hyperplanes.',
    card_type: 'concept',
    difficulty: 'medium',
    topic: 'Support Vector Machines',
    source_references: [
      {
        chunk_id: 'c-1',
        document_id: 'd-1',
        document_title: 'ml_intro.pdf',
        chunk_index: 0,
        page_number: 1,
      },
    ],
    created_at: '2026-11-08T00:00:00Z',
    updated_at: '2026-11-08T00:00:00Z',
  },
  {
    id: 'fc-2',
    workspace_id: 'ws-1',
    front: 'What is K-Means clustering?',
    back: 'An unsupervised algorithm partitioning observations into k clusters.',
    card_type: 'definition',
    difficulty: 'easy',
    topic: 'Clustering',
    source_references: [],
    created_at: '2026-11-08T00:00:00Z',
    updated_at: '2026-11-08T00:00:00Z',
  },
];

describe('FlashcardViewerModal', () => {
  it('renders front prompt and metadata when open', () => {
    const handleClose = vi.fn();
    render(
      <FlashcardViewerModal
        cards={mockCards}
        isOpen={true}
        onClose={handleClose}
      />
    );

    expect(screen.getByText('What is the margin in SVMs?')).toBeInTheDocument();
    expect(screen.getByText('concept')).toBeInTheDocument();
    expect(screen.getByText('1 / 2')).toBeInTheDocument();
  });

  it('flips card to reveal back answer upon click or flip button', () => {
    render(
      <FlashcardViewerModal
        cards={mockCards}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    const flipButton = screen.getByRole('button', { name: /flip card/i });
    fireEvent.click(flipButton);

    expect(
      screen.getByText('The geometric distance 2/||w|| between supporting hyperplanes.')
    ).toBeInTheDocument();
  });

  it('navigates to next card', () => {
    render(
      <FlashcardViewerModal
        cards={mockCards}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    const nextButton = screen.getByRole('button', { name: /next/i });
    fireEvent.click(nextButton);

    expect(screen.getByText('What is K-Means clustering?')).toBeInTheDocument();
    expect(screen.getByText('2 / 2')).toBeInTheDocument();
  });

  it('invokes onClose when clicking close button', () => {
    const handleClose = vi.fn();
    render(
      <FlashcardViewerModal
        cards={mockCards}
        isOpen={true}
        onClose={handleClose}
      />
    );

    const closeBtn = screen.getByRole('button', { name: /close modal/i });
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });
});
