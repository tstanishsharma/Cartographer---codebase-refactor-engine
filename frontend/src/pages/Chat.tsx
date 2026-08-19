import { useState, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'
import { MessageSquare, Send, Copy, RotateCcw, Square, Terminal, FileCode2, ChevronRight, Plus } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useParams, useNavigate } from 'react-router-dom'
import { cn } from '@utils/cn'

import { useChatStore, Message } from '@store/chatStore'
import { Button } from '@components/ui/Button'
import { Input } from '@components/ui/Input'
import { apiClient, createSSEConnection } from '@api/client'

export default function Chat() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  
  const { 
    sessions, 
    activeSessionId, 
    setActiveSession, 
    createSession,
    addMessage,
    updateStreamingMessage,
    finalizeStreamingMessage,
    setAgentState,
    setBackendId
  } = useChatStore()

  const [input, setInput] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const sseRef = useRef<EventSource | null>(null)

  // Sync route with active session
  useEffect(() => {
    if (sessionId && sessionId !== activeSessionId) {
      setActiveSession(sessionId)
    } else if (!sessionId && sessions.length > 0) {
      navigate(`/chat/${sessions[0].id}`, { replace: true })
    } else if (!sessionId && sessions.length === 0) {
      const newId = createSession()
      navigate(`/chat/${newId}`, { replace: true })
    }
  }, [sessionId, activeSessionId, sessions, navigate, setActiveSession, createSession])

  const activeSession = sessions.find(s => s.id === activeSessionId)

  // Auto scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [activeSession?.messages])

  const handleSend = async () => {
    if (!input.trim() || !activeSessionId) return
    const content = input.trim()

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
    }

    addMessage(activeSessionId, userMsg)
    setInput('')
    setIsGenerating(true)

    // Setup assistant message
    const assistantMsgId = crypto.randomUUID()
    const assistantMsg: Message = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      isStreaming: true,
      agentState: 'Planning',
    }
    addMessage(activeSessionId, assistantMsg)

    try {
      // Ensure a backend session exists so messages persist server-side.
      let backendId = activeSession?.backendId
      if (!backendId) {
        const resp = await apiClient.post<{ id: string }>('/api/v1/chat/sessions', {
          title: content.slice(0, 40),
        })
        backendId = resp.data.id
        setBackendId(activeSessionId, backendId)
      }

      // Trigger SSE — stream agent trace + tokens from the LangGraph pipeline.
      sseRef.current = createSSEConnection(
        `/api/v1/chat/sessions/${backendId}/message`,
        (token) => updateStreamingMessage(activeSessionId, assistantMsgId, token),
        () => {
          finalizeStreamingMessage(activeSessionId, assistantMsgId)
          setIsGenerating(false)
          sseRef.current?.close()
        },
        (error) => {
          console.error("SSE Error:", error)
          finalizeStreamingMessage(activeSessionId, assistantMsgId)
          setIsGenerating(false)
        },
        (state) => setAgentState(activeSessionId, assistantMsgId, state),
        { content, repository_id: null }
      )
    } catch (error) {
      console.error('Failed to create chat session:', error)
      finalizeStreamingMessage(activeSessionId, assistantMsgId)
      setIsGenerating(false)
    }
  }

  const stopGeneration = () => {
    if (sseRef.current) {
      sseRef.current.close()
      setIsGenerating(false)
      if (activeSessionId) {
        const lastMsg = activeSession?.messages[activeSession.messages.length - 1]
        if (lastMsg?.isStreaming) {
          finalizeStreamingMessage(activeSessionId, lastMsg.id)
        }
      }
    }
  }

  return (
    <div className="flex h-full bg-background">
      {/* Sidebar - Chat History */}
      <div className="w-64 border-r border-border bg-card/30 hidden md:flex flex-col">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h2 className="font-semibold text-sm">Chat History</h2>
          <Button variant="ghost" size="icon" onClick={() => {
            const newId = createSession()
            navigate(`/chat/${newId}`)
          }}>
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {sessions.map(s => (
            <button
              key={s.id}
              onClick={() => navigate(`/chat/${s.id}`)}
              className={cn(
                "w-full text-left px-3 py-2 text-sm rounded-md transition-colors truncate",
                s.id === activeSessionId 
                  ? "bg-secondary text-foreground font-medium" 
                  : "text-muted-foreground hover:bg-secondary/50"
              )}
            >
              {s.title}
            </button>
          ))}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-6">
          {activeSession?.messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center max-w-md mx-auto">
              <div className="h-12 w-12 rounded-full bg-primary/20 flex items-center justify-center mb-4">
                <MessageSquare className="h-6 w-6 text-primary" />
              </div>
              <h2 className="text-xl font-bold mb-2">How can I help you today?</h2>
              <p className="text-muted-foreground text-sm mb-6">
                Ask questions about your codebase, request a refactor, or have Cartographer analyze the blast radius of a potential change.
              </p>
              <div className="grid grid-cols-1 gap-2 w-full text-sm">
                {["Explain how the authentication flow works.", "Find all references to the User model.", "Refactor the caching logic to use Redis."].map(suggestion => (
                  <button 
                    key={suggestion} 
                    onClick={() => setInput(suggestion)}
                    className="p-3 border rounded-lg bg-card hover:bg-secondary transition-colors text-left text-muted-foreground hover:text-foreground flex items-center justify-between"
                  >
                    <span>{suggestion}</span>
                    <ChevronRight className="h-4 w-4" />
                  </button>
                ))}
              </div>
            </div>
          ) : (
            activeSession?.messages.map((msg, i) => (
              <ChatMessage key={msg.id} message={msg} />
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 md:p-6 border-t border-border bg-background">
          <div className="max-w-4xl mx-auto relative flex items-end gap-2 bg-card border border-border rounded-xl p-2 shadow-sm focus-within:ring-1 focus-within:ring-primary focus-within:border-primary transition-all">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSend()
                }
              }}
              placeholder="Ask Cartographer about your code..."
              className="flex-1 max-h-64 min-h-[44px] bg-transparent border-0 resize-none py-2 px-3 text-sm focus:outline-none focus:ring-0 text-foreground placeholder:text-muted-foreground"
              rows={input.split('\n').length > 1 ? Math.min(input.split('\n').length, 10) : 1}
            />
            {isGenerating ? (
              <Button size="icon" variant="destructive" className="shrink-0 h-10 w-10" onClick={stopGeneration}>
                <Square className="h-4 w-4 fill-current" />
              </Button>
            ) : (
              <Button size="icon" className="shrink-0 h-10 w-10" onClick={handleSend} disabled={!input.trim()}>
                <Send className="h-4 w-4" />
              </Button>
            )}
          </div>
          <div className="text-center mt-3">
            <p className="text-xs text-muted-foreground">Cartographer can make mistakes. Verify important changes.</p>
          </div>
        </div>
      </div>
    </div>
  )
}

function ChatMessage({ message }: { message: Message }) {
  const isUser = message.role === 'user'

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "flex gap-4 max-w-4xl mx-auto w-full",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      <div className={cn(
        "flex h-8 w-8 shrink-0 items-center justify-center rounded-md border text-xs font-medium",
        isUser ? "bg-primary text-primary-foreground border-transparent" : "bg-card border-border shadow-sm"
      )}>
        {isUser ? 'U' : <Terminal className="h-4 w-4 text-primary" />}
      </div>
      
      <div className={cn(
        "flex flex-col gap-2 min-w-0 max-w-[85%]",
        isUser ? "items-end" : "items-start"
      )}>
        {!isUser && message.agentState && (
          <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground bg-secondary/50 px-2 py-1 rounded border border-border/50">
            {message.isStreaming ? (
              <span className="flex h-2 w-2 rounded-full bg-primary animate-pulse" />
            ) : (
              <span className="flex h-2 w-2 rounded-full bg-green-500" />
            )}
            Agent: {message.agentState}
          </div>
        )}

        <div className={cn(
          "rounded-2xl px-5 py-3.5 text-sm shadow-sm prose prose-sm dark:prose-invert max-w-none break-words",
          isUser ? "bg-primary text-primary-foreground prose-p:text-primary-foreground/90" : "bg-card border border-border"
        )}>
          {isUser ? (
            <p className="whitespace-pre-wrap m-0">{message.content}</p>
          ) : (
            <div className={cn(message.isStreaming && "streaming-cursor")}>
              {message.content ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {message.content}
                </ReactMarkdown>
              ) : (
                <span className="text-muted-foreground animate-pulse">Thinking...</span>
              )}
            </div>
          )}
        </div>

        {!isUser && !message.isStreaming && (
          <div className="flex items-center gap-2 mt-1">
            <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground hover:text-foreground">
              <Copy className="h-3 w-3" />
            </Button>
            <Button variant="ghost" size="icon" className="h-6 w-6 text-muted-foreground hover:text-foreground">
              <RotateCcw className="h-3 w-3" />
            </Button>
          </div>
        )}
      </div>
    </motion.div>
  )
}
