/**
 * Cartographer — TypeScript Type Definitions
 *
 * Mirrors the backend Pydantic response models.
 * Keep in sync with backend schemas.
 */

export interface User {
  id: string
  email: string
  username: string
  full_name: string | null
  avatar_url: string | null
  role: string
  is_active: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

// ── Repository ───────────────────────────────────────────────────────────────

export type RepositoryStatus =
  | 'pending'
  | 'cloning'
  | 'parsing'
  | 'embedding'
  | 'ready'
  | 'failed'
  | 'updating'

export interface Repository {
  id: string
  name: string
  url: string
  description: string | null
  status: RepositoryStatus
  total_files: number
  total_chunks: number
  total_nodes: number
  total_edges: number
  languages: Record<string, number>
  created_at: string
  ingested_at: string | null
}

// ── Graph ─────────────────────────────────────────────────────────────────────

export type NodeType = 'module' | 'class' | 'function' | 'method' | 'import' | 'variable'

export type EdgeType =
  | 'imports'
  | 'calls'
  | 'inherits'
  | 'defines'
  | 'depends_on'
  | 'references'
  | 'implements'
  | 'uses'

export interface GraphNode {
  id: string
  node_type: NodeType
  name: string
  qualified_name: string | null
  file_path: string
  start_line: number
  end_line: number
  metadata: Record<string, unknown>
}

export interface GraphEdge {
  id: string
  source_id: string
  target_id: string
  edge_type: EdgeType
  weight: number
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  total_nodes: number
  total_edges: number
}

// ── Chat ──────────────────────────────────────────────────────────────────────

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
}

export interface ChatSession {
  id: string
  title: string
  repository_id: string | null
  message_count: number
  created_at: string
  updated_at: string
}

export interface ChatSessionDetail extends ChatSession {
  messages: ChatMessage[]
}

// ── Agents ────────────────────────────────────────────────────────────────────

export type AgentName =
  | 'planner'
  | 'retriever'
  | 'reasoning'
  | 'blast_radius'
  | 'code_edit'
  | 'test_runner'
  | 'critic'
  | 'memory'
  | 'supervisor'
  | 'reflection'

export type AgentRunStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface AgentTraceStep {
  step: number
  agent: AgentName
  input: Record<string, unknown>
  output: Record<string, unknown>
  duration_ms: number
  tokens_used: number
  retry_count: number
}

export interface AgentRun {
  id: string
  session_id: string
  status: AgentRunStatus
  active_agent: AgentName | null
  user_query: string
  final_response: string | null
  trace: AgentTraceStep[]
  total_tokens: number
  retry_count: number
  duration_seconds: number | null
  created_at: string
  completed_at: string | null
}

// ── Blast Radius ──────────────────────────────────────────────────────────────

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'

export interface BlastRadiusResult {
  affected_files: string[]
  affected_nodes: Array<{
    name: string
    type: string
    file: string
    relationship: string
  }>
  risk_level: RiskLevel
  risk_score: number
  reasoning: string
  dependency_chain: string[]
}

// ── Sandbox ───────────────────────────────────────────────────────────────────

export type SandboxJobStatus =
  | 'queued'
  | 'initializing'
  | 'running'
  | 'testing'
  | 'completed'
  | 'failed'
  | 'rolled_back'
  | 'timeout'

export interface SandboxJob {
  id: string
  repository_id: string
  status: SandboxJobStatus
  diff: string | null
  test_passed: boolean | null
  test_summary: Record<string, unknown>
  execution_logs: string | null
  duration_seconds: number | null
  created_at: string
}

// ── SSE Events ────────────────────────────────────────────────────────────────

export interface SSETokenEvent {
  type: 'token'
  content: string
}

export interface SSEDoneEvent {
  type: 'done'
  session_id: string
  run_id?: string
}

export interface SSEErrorEvent {
  type: 'error'
  message: string
}

export type SSEEvent = SSETokenEvent | SSEDoneEvent | SSEErrorEvent

// ── API Error ─────────────────────────────────────────────────────────────────

export interface APIError {
  error: string
  message: string
  detail?: unknown
}
