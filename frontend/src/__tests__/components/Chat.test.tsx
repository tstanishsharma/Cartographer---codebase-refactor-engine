import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import Chat from '../../pages/Chat';
import { useChatStore } from '../../store/chatStore';

// Mock the API client SSE connection
vi.mock('../../api/client', () => ({
  apiClient: {
    get: vi.fn().mockResolvedValue({ data: [] }),
    post: vi.fn().mockResolvedValue({ data: { id: 'mock-session-id' } }),
    put: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: {} }),
  },
  createSSEConnection: vi.fn((url, onToken, onDone, onError) => {
    // Simulate streaming after a short delay
    setTimeout(() => {
      onToken('Hello');
      onToken(' World');
      onDone();
    }, 10);
    
    // Return a mock EventSource-like object
    return {
      close: vi.fn(),
    };
  }),
}));

describe('Chat Component', () => {
  beforeEach(() => {
    useChatStore.setState({
      sessions: [],
      activeSessionId: null,
    });
    vi.clearAllMocks();
    
    // Mock scrollIntoView
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  const renderWithRouter = () => {
    return render(
      <MemoryRouter initialEntries={['/chat']}>
        <Chat />
      </MemoryRouter>
    );
  };

  it('should render empty state when no messages', () => {
    renderWithRouter();
    expect(screen.getByText('How can I help you today?')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Ask Cartographer about your code...')).toBeInTheDocument();
  });

  it('should create a session and send a message', async () => {
    renderWithRouter();
    
    const input = screen.getByPlaceholderText('Ask Cartographer about your code...');
    const buttons = screen.getAllByRole('button');
    const sendButton = buttons[buttons.length - 1];
    
    // Type and send message
    fireEvent.change(input, { target: { value: 'Test message' } });
    fireEvent.click(sendButton);
    
    // The user message should be added (appears in chat list and chat view)
    const messages = await screen.findAllByText('Test message');
    expect(messages.length).toBeGreaterThan(0);
    
    // Wait for the mock SSE to stream the response
    await waitFor(() => {
      expect(screen.getByText('Hello World')).toBeInTheDocument();
    });

  });

  it('should stop generation', async () => {
    // Override the mock to stream slowly
    const { createSSEConnection } = await import('../../api/client');
    let mockClose = vi.fn();
    (createSSEConnection as any).mockImplementationOnce((url: string, onToken: any) => {
      setTimeout(() => {
        onToken('Started...');
      }, 0);
      return { close: mockClose };
    });

    renderWithRouter();
    
    const input = screen.getByPlaceholderText('Ask Cartographer about your code...');
    const buttons = screen.getAllByRole('button');
    const sendButton = buttons[buttons.length - 1];
    
    fireEvent.change(input, { target: { value: 'Test stop' } });
    fireEvent.click(sendButton);
    
    // The message started streaming
    expect(await screen.findByText('Started...')).toBeInTheDocument();
    
    // The button should be the last one on the screen (the send/stop button)
    const allButtons = screen.getAllByRole('button');
    const stopButton = allButtons[allButtons.length - 1];
    
    fireEvent.click(stopButton);
    
    expect(mockClose).toHaveBeenCalled();
  });
});

