import { create } from 'zustand'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  isStreaming?: boolean
  citations?: Array<{ file: string; line: number }>
  agentState?: string
}

export interface ChatSession {
  id: string
  title: string
  createdAt: string
  /** Backend chat session UUID once the first message is sent. */
  backendId?: string
  messages: Message[]
}

interface ChatState {
  sessions: ChatSession[]
  activeSessionId: string | null
  setActiveSession: (id: string) => void
  createSession: () => string
  setBackendId: (sessionId: string, backendId: string) => void
  addMessage: (sessionId: string, message: Message) => void
  updateStreamingMessage: (sessionId: string, messageId: string, chunk: string) => void
  finalizeStreamingMessage: (sessionId: string, messageId: string) => void
  setAgentState: (sessionId: string, messageId: string, state: string) => void
}

export const useChatStore = create<ChatState>((set) => ({
  sessions: [],
  activeSessionId: null,
  setActiveSession: (id) => set({ activeSessionId: id }),
  createSession: () => {
    const newSession: ChatSession = {
      id: crypto.randomUUID(),
      title: 'New Chat',
      createdAt: new Date().toISOString(),
      messages: [],
    }
    set((state) => ({
      sessions: [newSession, ...state.sessions],
      activeSessionId: newSession.id,
    }))
    return newSession.id
  },
  setBackendId: (sessionId, backendId) =>
    set((state) => ({
      sessions: state.sessions.map((s) =>
        s.id === sessionId ? { ...s, backendId } : s
      ),
    })),
  addMessage: (sessionId, message) =>
    set((state) => ({
      sessions: state.sessions.map((s) => {
        if (s.id !== sessionId) return s
        // Auto-title if it's the first message
        const title = s.messages.length === 0 && message.role === 'user' 
          ? message.content.slice(0, 30) + (message.content.length > 30 ? '...' : '') 
          : s.title
        return {
          ...s,
          title,
          messages: [...s.messages, message],
        }
      }),
    })),
  updateStreamingMessage: (sessionId, messageId, chunk) =>
    set((state) => ({
      sessions: state.sessions.map((s) => {
        if (s.id !== sessionId) return s
        return {
          ...s,
          messages: s.messages.map((m) =>
            m.id === messageId ? { ...m, content: m.content + chunk } : m
          ),
        }
      }),
    })),
  finalizeStreamingMessage: (sessionId, messageId) =>
    set((state) => ({
      sessions: state.sessions.map((s) => {
        if (s.id !== sessionId) return s
        return {
          ...s,
          messages: s.messages.map((m) =>
            m.id === messageId ? { ...m, isStreaming: false } : m
          ),
        }
      }),
    })),
  setAgentState: (sessionId, messageId, agentState) =>
    set((state) => ({
      sessions: state.sessions.map((s) => {
        if (s.id !== sessionId) return s
        return {
          ...s,
          messages: s.messages.map((m) =>
            m.id === messageId ? { ...m, agentState } : m
          ),
        }
      }),
    })),
}))
