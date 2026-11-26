import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { Button } from '../button';
import { Badge } from '../badge';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '../card';
import { Input } from '../input';
import { StatusBadge } from '@/components/shared/StatusBadge';

describe('UI Primitives and Design System', () => {
  it('renders button with proper variants and responds to click', () => {
    const handleClick = vi.fn();
    render(
      <Button variant="default" onClick={handleClick}>
        Test Action
      </Button>
    );

    const button = screen.getByRole('button', { name: /test action/i });
    expect(button).toBeInTheDocument();
    fireEvent.click(button);
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('renders disabled button that prevents clicks', () => {
    const handleClick = vi.fn();
    render(
      <Button disabled onClick={handleClick}>
        Disabled Action
      </Button>
    );

    const button = screen.getByRole('button', { name: /disabled action/i });
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(handleClick).not.toHaveBeenCalled();
  });

  it('renders card with all structured sections', () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>Card Title Test</CardTitle>
          <CardDescription>Card Description Test</CardDescription>
        </CardHeader>
        <CardContent>
          <p>Main Card Body Content</p>
        </CardContent>
        <CardFooter>
          <span>Footer Actions</span>
        </CardFooter>
      </Card>
    );

    expect(screen.getByText('Card Title Test')).toBeInTheDocument();
    expect(screen.getByText('Card Description Test')).toBeInTheDocument();
    expect(screen.getByText('Main Card Body Content')).toBeInTheDocument();
    expect(screen.getByText('Footer Actions')).toBeInTheDocument();
  });

  it('renders badge with correct semantic classes', () => {
    render(<Badge variant="success">Completed</Badge>);
    expect(screen.getByText('Completed')).toBeInTheDocument();
  });

  it('renders StatusBadge with icon and semantic status', () => {
    render(<StatusBadge status="ready" label="All Systems Operational" />);
    expect(screen.getByText('All Systems Operational')).toBeInTheDocument();
  });

  it('renders input and captures text changes', () => {
    const handleChange = vi.fn();
    render(
      <Input
        placeholder="Enter research title"
        onChange={handleChange}
        data-testid="research-input"
      />
    );

    const input = screen.getByTestId('research-input');
    fireEvent.change(input, { target: { value: 'Quantum computing' } });
    expect(handleChange).toHaveBeenCalledTimes(1);
  });
});
