"""
Cartographer — Chat Router (SSE Streaming).

Endpoints:
  POST /chat/sessions              — create a chat session
  GET  /chat/sessions              — list user's chat sessions
  GET  /chat/sessions/{id}         — get session with messages
  POST /chat/sessions/{id}/message — send message (streaming SSE)
  DELETE /chat/sessions/{id}       — delete session
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import LLM, AgentRepo, CurrentUser

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/chat")


class CreateSessionRequest(BaseModel):
    repository_id: uuid.UUID | None = None
    title: str = "New conversation"


class SendMessageRequest(BaseModel):
    content: str
    repository_id: uuid.UUID | None = None


class SessionResponse(BaseModel):
    id: str
    title: str
    repository_id: str | None
    message_count: int
    created_at: str
    updated_at: str


@router.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_session(
    body: CreateSessionRequest,
    current_user: CurrentUser,
    agent_repo: AgentRepo,
) -> SessionResponse:
    """Create a new chat session."""
    session = await agent_repo.create_chat_session(
        user_id=current_user.id,
        repository_id=body.repository_id,
        title=body.title,
    )
    return _session_response(session)


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    current_user: CurrentUser,
    agent_repo: AgentRepo,
) -> list[SessionResponse]:
    """List all chat sessions for the current user."""
    sessions = await agent_repo.get_user_sessions(current_user.id)
    return [_session_response(s) for s in sessions]


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: uuid.UUID,
    current_user: CurrentUser,
    agent_repo: AgentRepo,
) -> dict:
    """Get session details including full message history."""
    session = await agent_repo.get_chat_session(session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {
        "id": str(session.id),
        "title": session.title,
        "repository_id": str(session.repository_id) if session.repository_id else None,
        "messages": session.messages,
        "created_at": session.created_at.isoformat(),
    }


@router.post("/sessions/{session_id}/message")
async def send_message(
    session_id: uuid.UUID,
    body: SendMessageRequest,
    current_user: CurrentUser,
    agent_repo: AgentRepo,
    llm: LLM,
) -> StreamingResponse:
    """
    Send a message and stream the response via Server-Sent Events (SSE).

    The full multi-agent pipeline runs asynchronously while tokens
    are streamed to the client in real-time.

    SSE event format:
      data: {"type": "token", "content": "..."}
      data: {"type": "done", "run_id": "..."}
      data: {"type": "error", "message": "..."}
    """
    session = await agent_repo.get_chat_session(session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Store user message
    await agent_repo.append_message(session_id, "user", body.content)

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events from the agent pipeline."""
        full_response = ""
        try:
            # Phase 5 & 6 Integration: Use LangGraph Orchestrator
            from app.services.agents.orchestrator import AgentOrchestrator
            from app.services.agents.state import AgentState

            orchestrator = AgentOrchestrator(llm_provider=llm)

            initial_state: AgentState = {
                "session_id": session_id,
                "repository_id": session.repository_id,
                "user_query": body.content,
                "conversation_history": session.messages,
                "retrieval_context": [],
                "graph_context": [],
                "selected_files": [],
                "selected_symbols": [],
                "planner_output": None,
                "blast_radius": None,
                "proposed_diff": None,
                "edit_operations": [],
                "sandbox_status": None,
                "test_results": None,
                "critic_feedback": None,
                "reflection_feedback": None,
                "execution_logs": [],
                "current_agent": "SupervisorAgent",
                "next_agent": None,
                "retry_count": 0,
                "confidence_score": 1.0,
                "latency_metrics": {},
                "token_usage": {},
                "memory_summary": "",
                "citations": [],
                "stream_events": [],
                "errors": [],
            }

            async for state_update in orchestrator.stream_run(initial_state):
                # Send the latest stream events to the frontend
                events = state_update.get("stream_events", [])
                if events:
                    # Just send the last event for now
                    latest_event = events[-1]
                    trace_event = json.dumps(
                        {"type": "agent_trace", "content": latest_event["message"]}
                    )
                    yield f"data: {trace_event}\n\n"

            # For this scaffolding, we generate a final LLM response summarization
            # based on the final state.
            from app.services.llm.base import Message

            summary_prompt = f"Summarize the agent run for query: {body.content}"
            messages = [
                Message(
                    role="system", content="You are Cartographer. Summarize what was just done."
                ),
                Message(role="user", content=summary_prompt),
            ]

            async for token in llm.stream(messages):
                full_response += token
                event = json.dumps({"type": "token", "content": token})
                yield f"data: {event}\n\n"

            # Store assistant response
            await agent_repo.append_message(session_id, "assistant", full_response)

            done_event = json.dumps({"type": "done", "session_id": str(session_id)})
            yield f"data: {done_event}\n\n"

        except Exception as exc:
            logger.error("chat.stream.error", error=str(exc))
            error_event = json.dumps({"type": "error", "message": str(exc)})
            yield f"data: {error_event}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
            "Connection": "keep-alive",
        },
    )


def _session_response(s: object) -> SessionResponse:
    messages = getattr(s, "messages", []) or []
    return SessionResponse(
        id=str(getattr(s, "id", "")),
        title=getattr(s, "title", ""),
        repository_id=str(getattr(s, "repository_id", ""))
        if getattr(s, "repository_id", None)
        else None,
        message_count=len(messages),
        created_at=getattr(s, "created_at", datetime.now(UTC)).isoformat(),
        updated_at=getattr(s, "updated_at", datetime.now(UTC)).isoformat(),
    )
