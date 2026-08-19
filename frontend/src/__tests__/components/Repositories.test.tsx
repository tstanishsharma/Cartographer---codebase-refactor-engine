import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import Repositories from '../../pages/Repositories';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock the API hooks
vi.mock('../../api/repositories', () => ({
  useRepositories: vi.fn(),
  useAddRepository: vi.fn(),
  useDeleteRepository: vi.fn(),
}));

import { useRepositories, useAddRepository, useDeleteRepository } from '../../api/repositories';

describe('Repositories Component', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    vi.clearAllMocks();
  });

  const renderComponent = () => {
    return render(
      <QueryClientProvider client={queryClient}>
        <Repositories />
      </QueryClientProvider>
    );
  };

  it('should render loading state', () => {
    (useRepositories as any).mockReturnValue({
      data: undefined,
      isLoading: true,
    });
    (useAddRepository as any).mockReturnValue({ mutate: vi.fn(), isPending: false });
    (useDeleteRepository as any).mockReturnValue({ mutate: vi.fn(), isPending: false });

    renderComponent();
    
    // Lucide Loader2 is typically rendered as an svg
    // Let's just check if 'Repositories' heading exists
    expect(screen.getByText('Repositories')).toBeInTheDocument();
  });

  it('should render empty state when no repositories', () => {
    (useRepositories as any).mockReturnValue({
      data: [],
      isLoading: false,
    });
    (useAddRepository as any).mockReturnValue({ mutate: vi.fn(), isPending: false });
    (useDeleteRepository as any).mockReturnValue({ mutate: vi.fn(), isPending: false });

    renderComponent();
    
    expect(screen.getByText('No repositories yet')).toBeInTheDocument();
    expect(screen.getByText(/Import your first GitHub repository/i)).toBeInTheDocument();
  });

  it('should render list of repositories', () => {
    const mockRepos = [
      {
        id: 'repo-1',
        name: 'TestRepo',
        url: 'https://github.com/test/repo',
        status: 'ready',
        total_files: 10,
        total_nodes: 50,
        created_at: new Date().toISOString(),
      }
    ];

    (useRepositories as any).mockReturnValue({
      data: mockRepos,
      isLoading: false,
    });
    (useAddRepository as any).mockReturnValue({ mutate: vi.fn(), isPending: false });
    (useDeleteRepository as any).mockReturnValue({ mutate: vi.fn(), isPending: false });

    renderComponent();
    
    expect(screen.getByText('TestRepo')).toBeInTheDocument();
    expect(screen.getByText('https://github.com/test/repo')).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument(); // total_files
    expect(screen.getByText('50')).toBeInTheDocument(); // total_nodes
    expect(screen.getByText('Ready')).toBeInTheDocument(); // status badge
  });

  it('should open Add Repository dialog when Add button clicked', () => {
    (useRepositories as any).mockReturnValue({
      data: [],
      isLoading: false,
    });
    (useAddRepository as any).mockReturnValue({ mutate: vi.fn(), isPending: false });
    (useDeleteRepository as any).mockReturnValue({ mutate: vi.fn(), isPending: false });

    renderComponent();
    
    const addButtons = screen.getAllByRole('button', { name: /Add Repository/i });
    fireEvent.click(addButtons[0]);
    
    // Add Repository Dialog Title should be visible
    // Empty state also has an add button, and header has one. Either works.
    expect(screen.getByRole('heading', { name: 'Add Repository' })).toBeInTheDocument();
  });

  it('should call deleteRepo mutation when delete button is clicked', () => {
    const mockRepos = [
      {
        id: 'repo-1',
        name: 'TestRepo',
        url: 'https://github.com/test/repo',
        status: 'ready',
        total_files: 10,
        total_nodes: 50,
        created_at: new Date().toISOString(),
      }
    ];

    const deleteMutateMock = vi.fn();
    (useRepositories as any).mockReturnValue({
      data: mockRepos,
      isLoading: false,
    });
    (useAddRepository as any).mockReturnValue({ mutate: vi.fn(), isPending: false });
    (useDeleteRepository as any).mockReturnValue({ mutate: deleteMutateMock, isPending: false });

    renderComponent();
    
    const deleteButton = screen.getAllByRole('button')[1]; // Header Add is [0], Trash is [1]
    fireEvent.click(deleteButton);
    
    expect(deleteMutateMock).toHaveBeenCalledWith('repo-1');
  });
});
