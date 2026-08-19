import uuid
from typing import Any, TypedDict

from pydantic import BaseModel


class Citation(BaseModel):
    file_path: str
    line_number: int | None = None
    content: str
    score: float | None = None


class TaskDependency(BaseModel):
    task_id: str
    depends_on: list[str]
    description: str
    expected_output: str
    required_context: list[str]
    risk_level: str


class PlannerOutput(BaseModel):
    tasks: list[TaskDependency]
    overall_risk: str
    reasoning: str


class BlastRadiusImpact(BaseModel):
    affected_files: list[str]
    affected_functions: list[str]
    dependency_depth: int
    confidence: float
    estimated_risk: str
    visualization_payload: dict[str, Any]


class EditOperation(BaseModel):
    operation_type: str  # SEARCH, REPLACE, INSERT, DELETE, MOVE
    file_path: str
    search_block: str | None = None
    replace_block: str | None = None
    insert_block: str | None = None
    line_start: int | None = None
    line_end: int | None = None


class SandboxResult(BaseModel):
    status: str  # PASS, FAIL, TIMEOUT, ERROR
    stdout: str
    stderr: str
    exit_code: int
    execution_time_sec: float
    coverage_report: str | None = None
    test_report: str | None = None
    git_diff: str | None = None


class CriticFeedback(BaseModel):
    approved: bool
    confidence: float
    correctness_issues: list[str]
    architecture_issues: list[str]
    style_issues: list[str]
    complexity_issues: list[str]
    performance_issues: list[str]
    security_issues: list[str]
    regression_risks: list[str]
    missing_tests: list[str]
    reasoning: str


class ReflectionFeedback(BaseModel):
    failure_summary: str
    root_cause: str
    repair_plan: str
    improved_prompt: str
    should_retry: bool


class AgentState(TypedDict):
    """LangGraph workflow state for Cartographer multi-agent system."""

    session_id: uuid.UUID
    repository_id: uuid.UUID
    user_query: str
    conversation_history: list[dict[str, Any]]

    # Context
    retrieval_context: list[dict[str, Any]]
    graph_context: list[dict[str, Any]]
    selected_files: list[str]
    selected_symbols: list[str]

    # Agent Outputs
    planner_output: PlannerOutput | None
    blast_radius: BlastRadiusImpact | None
    proposed_diff: str | None
    edit_operations: list[EditOperation]

    # Sandbox & Validation
    sandbox_status: SandboxResult | None
    test_results: dict[str, Any] | None
    critic_feedback: CriticFeedback | None
    reflection_feedback: ReflectionFeedback | None
    execution_logs: list[dict[str, Any]]

    # Orchestration State
    current_agent: str
    next_agent: str | None
    retry_count: int
    confidence_score: float

    # Observability & Metrics
    latency_metrics: dict[str, float]
    token_usage: dict[str, int]
    memory_summary: str
    citations: list[Citation]
    stream_events: list[dict[str, Any]]
    errors: list[str]
