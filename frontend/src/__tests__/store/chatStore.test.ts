import { describe, it, expect, beforeEach } from 'vitest';
import { useChatStore } from '../../store/chatStore';

describe('chatStore', () => {
  beforeEach(() => {
    // Reset store before each test
    useChatStore.setState({
      sessions: [],
      activeSessionId: null,
    });
  });

  it('should initialize with default state', () => {
    const state = useChatStore.getState();
    expect(state.sessions).toEqual([]);
    expect(state.activeSessionId).toBeNull();
  });

  it('should create a new session', () => {
    const sessionId = useChatStore.getState().createSession();
    const state = useChatStore.getState();
    
    expect(sessionId).toBeDefined();
    expect(state.sessions).toHaveLength(1);
    expect(state.sessions[0].id).toBe(sessionId);
    expect(state.activeSessionId).toBe(sessionId);
    expect(state.sessions[0].title).toBe('New Chat');
  });

  it('should set active session', () => {
    const id1 = useChatStore.getState().createSession();
    const id2 = useChatStore.getState().createSession();
    
    useChatStore.getState().setActiveSession(id1);
    expect(useChatStore.getState().activeSessionId).toBe(id1);
  });

  it('should add a message to a session and auto-title on first user message', () => {
    const sessionId = useChatStore.getState().createSession();
    
    const message = {
      id: 'msg1',
      role: 'user' as const,
      content: 'This is a long message that should be truncated for the title'
    };
    
    useChatStore.getState().addMessage(sessionId, message);
    const state = useChatStore.getState();
    const session = state.sessions.find(s => s.id === sessionId);
    
    expect(session?.messages).toHaveLength(1);
    expect(session?.messages[0]).toEqual(message);
    expect(session?.title).toBe('This is a long message that sh...');
  });

  it('should update a streaming message chunk by chunk', () => {
    const sessionId = useChatStore.getState().createSession();
    
    const message = {
      id: 'msg1',
      role: 'assistant' as const,
      content: 'Hello',
      isStreaming: true
    };
    
    useChatStore.getState().addMessage(sessionId, message);
    
    useChatStore.getState().updateStreamingMessage(sessionId, 'msg1', ' World');
    
    const session = useChatStore.getState().sessions.find(s => s.id === sessionId);
    expect(session?.messages[0].content).toBe('Hello World');
  });

  it('should finalize streaming message', () => {
    const sessionId = useChatStore.getState().createSession();
    
    const message = {
      id: 'msg1',
      role: 'assistant' as const,
      content: 'Done',
      isStreaming: true
    };
    
    useChatStore.getState().addMessage(sessionId, message);
    useChatStore.getState().finalizeStreamingMessage(sessionId, 'msg1');
    
    const session = useChatStore.getState().sessions.find(s => s.id === sessionId);
    expect(session?.messages[0].isStreaming).toBe(false);
  });

  it('should set agent state', () => {
    const sessionId = useChatStore.getState().createSession();
    
    const message = {
      id: 'msg1',
      role: 'assistant' as const,
      content: 'Thinking...',
    };
    
    useChatStore.getState().addMessage(sessionId, message);
    useChatStore.getState().setAgentState(sessionId, 'msg1', 'SupervisorAgent');
    
    const session = useChatStore.getState().sessions.find(s => s.id === sessionId);
    expect(session?.messages[0].agentState).toBe('SupervisorAgent');
  });
});
