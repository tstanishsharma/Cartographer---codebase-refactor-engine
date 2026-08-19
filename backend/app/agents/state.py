"""
Cartographer — Agent State Definition.

The AgentState TypedDict is the single shared state object that flows
through the entire LangGraph multi-agent pipeline.

Every agent reads from and writes to specific fields in this state.
The Supervisor routes based on 'next_agent' and 'status' fields.
"""

from __future__ import annotations

from typing import Any, TypedDict


class Task(TypedDict):
    """A decomposed subtask from the Planner Agent."""

    id: str
    description: str
    agent: str  # Which agent should handle this task
    priority: int
    completed: bool
    result: str | None


class RetrievedChunk(TypedDict):
    """A single retrieved context chunk from hybrid retrieval."""

    chunk_id: str
    file_path: str
    content: str
    language: str
    score: float
    retrieval_source: str  # "vector" | "keyword" | "graph"
    metadata: dict[str, Any]


class CodeEdit(TypedDict):
    """A proposed code modification from the Code Edit Agent."""

    file_path: str
    original_content: str
    new_content: str
    description: str
    line_start: int
    line_end: int


class BlastRadiusResult(TypedDict):
    """Output from the Blast Radius Agent."""

    affected_nodes: list[dict[str, Any]]
    affected_files: list[str]
    risk_level: str  # "low" | "medium" | "high" | "critical"
    risk_score: float  # 0.0 - 1.0
    reasoning: str
    dependency_chain: list[str]


class TestResult(TypedDict):
    """Output from the Test Runner Agent."""

    passed: bool
    total_tests: int
    passed_tests: int
    failed_tests: int
    error_tests: int
    duration_seconds: float
    failures: list[dict[str, str]]
    logs: str
    exit_code: int


class AgentMetrics(TypedDict):
    """Per-agent performance metrics."""

    agent_name: str
    start_time: float
    end_time: float
    duration_ms: float
    tokens_used: int
    retry_count: int


class AgentState(TypedDict, total=False):
    """
    Shared state flowing through the LangGraph pipeline.

    Fields are total=False (optional) so agents can populate
    them incrementally without requiring all fields upfront.

    Required fields (always present after initialization):
        session_id, user_query, repository_id

    All other fields are populated by the relevant agents.
    """

    # ── Core ───────────────────────────────────────────────────────────────
    session_id: str  # ChatSession UUID
    run_id: str  # AgentRun UUID
    user_query: str  # Original user question
    repository_id: str  # Target repository UUID
    user_id: str  # Authenticated user UUID

    # ── Routing ────────────────────────────────────────────────────────────
    next_agent: str  # Which agent to route to next
    status: str  # "running" | "completed" | "failed"

    # ── Planner Agent output ───────────────────────────────────────────────
    task_plan: list[Task]
    current_task_index: int

    # ── Retriever Agent output ─────────────────────────────────────────────
    retrieved_context: list[RetrievedChunk]
    retrieval_query: str  # Possibly rewritten query

    # ── Reasoning Agent output ─────────────────────────────────────────────
    reasoning_output: str
    reasoning_citations: list[str]  # Chunk IDs used in answer

    # ── Blast Radius Agent output ──────────────────────────────────────────
    blast_radius: BlastRadiusResult

    # ── Code Edit Agent output ─────────────────────────────────────────────
    code_edits: list[CodeEdit]
    diff: str  # Unified diff

    # ── Test Runner Agent output ───────────────────────────────────────────
    test_results: TestResult
    sandbox_job_id: str

    # ── Critic Agent output ────────────────────────────────────────────────
    critic_feedback: str
    critic_approved: bool

    # ── Reflection Agent output ────────────────────────────────────────────
    reflection_notes: str
    should_retry: bool
    retry_strategy: str  # "replan" | "retrieve_more" | "abort"

    # ── Memory Agent ──────────────────────────────────────────────────────
    memory: dict[str, Any]  # Session-scoped persistent context

    # ── Error handling ─────────────────────────────────────────────────────
    errors: list[str]
    retry_count: int

    # ── Metrics ────────────────────────────────────────────────────────────
    metrics: list[AgentMetrics]
    total_tokens: int

    # ── Streaming ─────────────────────────────────────────────────────────
    streaming_buffer: str  # Accumulated stream content
