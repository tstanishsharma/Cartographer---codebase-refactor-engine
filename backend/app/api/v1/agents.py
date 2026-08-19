"""
Cartographer — Agent Runs Router.

Provides read access to agent run history and real-time trace data.
Full agent invocation is triggered via the chat endpoint.
"""

from __future__ import annotations

import uuid  # noqa: TC003

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import AgentRepo, CurrentUser  # noqa: TC001, TC002

router = APIRouter(prefix="/agents")


class AgentRunResponse(BaseModel):
    id: str
    session_id: str
    status: str
    active_agent: str | None
    user_query: str
    final_response: str | None
    trace: list
    total_tokens: int
    retry_count: int
    duration_seconds: float | None
    created_at: str
    completed_at: str | None


@router.get("/runs/{run_id}", response_model=AgentRunResponse)
async def get_agent_run(
    run_id: uuid.UUID,
    current_user: CurrentUser,
    repo: AgentRepo,
) -> AgentRunResponse:
    """Get a specific agent run with full trace data."""
    run = await repo.get_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Agent run not found.")
    return AgentRunResponse(
        id=str(run.id),
        session_id=str(run.session_id),
        status=run.status,
        active_agent=run.active_agent,
        user_query=run.user_query,
        final_response=run.final_response,
        trace=run.trace,
        total_tokens=run.total_tokens,
        retry_count=run.retry_count,
        duration_seconds=run.duration_seconds,
        created_at=run.created_at.isoformat(),
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
    )


@router.get("/sessions/{session_id}/runs", response_model=list[AgentRunResponse])
async def list_session_runs(
    session_id: uuid.UUID,
    current_user: CurrentUser,
    repo: AgentRepo,
) -> list[AgentRunResponse]:
    """List all agent runs for a session."""
    runs = await repo.get_by_session(session_id)
    return [
        AgentRunResponse(
            id=str(r.id),
            session_id=str(r.session_id),
            status=r.status,
            active_agent=r.active_agent,
            user_query=r.user_query,
            final_response=r.final_response,
            trace=r.trace,
            total_tokens=r.total_tokens,
            retry_count=r.retry_count,
            duration_seconds=r.duration_seconds,
            created_at=r.created_at.isoformat(),
            completed_at=r.completed_at.isoformat() if r.completed_at else None,
        )
        for r in runs
    ]
