import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user
from app.main import app

_TEST_USER_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")


# Mock user for auth bypass
def mock_get_current_user():
    from app.db.models.user import User

    return User(id=_TEST_USER_ID, email="test@example.com")


app.dependency_overrides[get_current_user] = mock_get_current_user


@pytest.fixture
async def async_client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_health_endpoint(async_client):
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_chat_stream(async_client, mocker):
    from app.api.deps import get_agent_repo, get_llm

    mock_session = mocker.Mock()
    mock_session.user_id = app.dependency_overrides[get_current_user]().id
    mock_session.repository_id = uuid.uuid4()
    mock_session.messages = []

    mock_repo = mocker.AsyncMock()
    mock_repo.get_chat_session.return_value = mock_session
    app.dependency_overrides[get_agent_repo] = lambda: mock_repo

    mock_llm = mocker.AsyncMock()

    async def mock_stream(*args, **kwargs):
        yield "hello "
        yield "world"

    mock_llm.stream = mock_stream
    app.dependency_overrides[get_llm] = lambda: mock_llm

    # Mock orchestrator
    mock_orchestrator_cls = mocker.patch("app.services.agents.orchestrator.AgentOrchestrator")
    mock_orchestrator = mocker.AsyncMock()

    async def mock_stream_run(*args, **kwargs):
        yield {"stream_events": [{"message": "thinking..."}]}

    mock_orchestrator.stream_run = mock_stream_run
    mock_orchestrator_cls.return_value = mock_orchestrator

    session_id = str(uuid.uuid4())
    response = await async_client.post(
        f"/api/v1/chat/sessions/{session_id}/message", json={"content": "test"}
    )
    assert response.status_code == 200, f"Error: {response.text}"
    assert "text/event-stream" in response.headers["content-type"]
    content = response.read().decode("utf-8")
    assert 'data: {"type": "token", "content": "hello "}' in content
    assert 'data: {"type": "done"' in content


@pytest.mark.asyncio
async def test_list_repositories(async_client, mocker):
    from app.api.deps import get_repository_repo

    mock_repo = mocker.AsyncMock()
    mock_repo.get_user_repositories.return_value = []
    app.dependency_overrides[get_repository_repo] = lambda: mock_repo

    response = await async_client.get("/api/v1/repositories/")
    assert response.status_code == 200
    assert response.json() == []
